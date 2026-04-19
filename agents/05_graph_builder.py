"""
GraphBuilderAgent - Builds knowledge graph of relationships between conversations.

This agent processes enriched conversations and builds a knowledge graph using
NetworkX, identifying relationships based on shared tags, concepts, temporal
proximity, shared people, and semantic similarity.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

import networkx as nx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from agents.extractor import EnrichedConversation


console = Console()


@dataclass
class NodeInfo:
    """Information about a node in the knowledge graph.

    Attributes:
        node_id: Unique identifier for the node.
        node_type: Type of node (conversation, concept, tag, person).
        label: Display label for the node.
        metadata: Additional metadata for the node.
        importance_score: Calculated importance score (PageRank-style).
    """
    node_id: str
    node_type: str
    label: str
    metadata: dict[str, Any] = field(default_factory=dict)
    importance_score: float = 0.0


@dataclass
class EdgeInfo:
    """Information about an edge in the knowledge graph.

    Attributes:
        source: Source node ID.
        target: Target node ID.
        relationship: Type of relationship.
        weight: Edge weight (strength of relationship).
        metadata: Additional metadata for the edge.
    """
    source: str
    target: str
    relationship: str
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class NetworkXKnowledgeGraph:
    """Knowledge graph containing conversations, concepts, tags, and people.

    Builds and maintains a graph structure representing relationships between
    different elements extracted from conversations. Uses NetworkX for graph
    algorithms like PageRank and community detection.

    This class provides the runtime graph operations, while the dataclass
    KnowledgeGraph in models.py is used for serialization.

    Attributes:
        graph: NetworkX graph containing nodes and edges.
        nodes: Dictionary of node information by ID.
        edges: List of edge information.
        communities: Detected community clusters.
    """

    def __init__(self) -> None:
        """Initialize an empty knowledge graph."""
        self.graph: nx.Graph = nx.Graph()
        self.nodes: dict[str, NodeInfo] = {}
        self.edges: list[EdgeInfo] = []
        self.communities: dict[int, list[str]] = {}
        self._importance_scores: dict[str, float] = {}

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add a node to the knowledge graph.

        Args:
            node_id: Unique identifier for the node.
            node_type: Type of node (conversation, concept, tag, person).
            label: Display label for the node.
            metadata: Additional metadata for the node.
        """
        if metadata is None:
            metadata = {}

        node_info = NodeInfo(
            node_id=node_id,
            node_type=node_type,
            label=label,
            metadata=metadata,
        )
        self.nodes[node_id] = node_info
        self.graph.add_node(
            node_id,
            node_type=node_type,
            label=label,
            **metadata,
        )

    def add_edge(
        self,
        source: str,
        target: str,
        relationship: str,
        weight: float = 1.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add an edge between two nodes.

        Args:
            source: Source node ID.
            target: Target node ID.
            relationship: Type of relationship.
            weight: Edge weight (strength of relationship).
            metadata: Additional metadata for the edge.
        """
        if metadata is None:
            metadata = {}

        # Update weight if edge already exists
        if self.graph.has_edge(source, target):
            existing_weight = self.graph[source][target].get("weight", 1.0)
            weight = existing_weight + weight

        edge_info = EdgeInfo(
            source=source,
            target=target,
            relationship=relationship,
            weight=weight,
            metadata=metadata,
        )
        self.edges.append(edge_info)
        self.graph.add_edge(
            source,
            target,
            relationship=relationship,
            weight=weight,
            **metadata,
        )

    def calculate_importance_scores(self) -> dict[str, float]:
        """Calculate PageRank-style importance scores for all nodes.

        Returns:
            Dictionary mapping node IDs to importance scores.
        """
        if len(self.graph.nodes) == 0:
            return {}

        try:
            # Use PageRank algorithm
            scores = nx.pagerank(self.graph, weight="weight")
        except nx.PowerIterationFailedConvergence:
            # Fallback to degree centrality if PageRank fails
            scores = nx.degree_centrality(self.graph)

        # Update node importance scores
        for node_id, score in scores.items():
            if node_id in self.nodes:
                self.nodes[node_id].importance_score = score

        self._importance_scores = scores
        return scores

    def identify_communities(self) -> dict[int, list[str]]:
        """Identify clusters/communities in the graph.

        Returns:
            Dictionary mapping community IDs to lists of node IDs.
        """
        if len(self.graph.nodes) < 2:
            self.communities = {0: list(self.graph.nodes)}
            return self.communities

        try:
            # Use Louvain community detection
            from networkx.algorithms.community import louvain_communities
            communities = louvain_communities(self.graph, weight="weight")
            self.communities = {i: list(comm) for i, comm in enumerate(communities)}
        except ImportError:
            # Fallback to connected components
            components = list(nx.connected_components(self.graph))
            self.communities = {i: list(comp) for i, comp in enumerate(components)}

        return self.communities

    def get_node_neighbors(self, node_id: str, limit: int = 10) -> list[tuple[str, float]]:
        """Get the most connected neighbors of a node.

        Args:
            node_id: The node to find neighbors for.
            limit: Maximum number of neighbors to return.

        Returns:
            List of (neighbor_id, weight) tuples sorted by weight.
        """
        if node_id not in self.graph:
            return []

        neighbors = []
        for neighbor in self.graph.neighbors(node_id):
            weight = self.graph[node_id][neighbor].get("weight", 1.0)
            neighbors.append((neighbor, weight))

        # Sort by weight descending
        neighbors.sort(key=lambda x: x[1], reverse=True)
        return neighbors[:limit]

    def get_conversation_connections(
        self,
        conversation_id: str,
        min_weight: float = 0.5,
    ) -> list[tuple[str, float, str]]:
        """Get related conversations with their connection strength.

        Args:
            conversation_id: The conversation node ID.
            min_weight: Minimum weight threshold for connections.

        Returns:
            List of (conversation_id, weight, relationship_type) tuples.
        """
        connections = []
        node_id = f"conv:{conversation_id}"

        if node_id not in self.graph:
            return connections

        for neighbor in self.graph.neighbors(node_id):
            edge_data = self.graph[node_id][neighbor]
            weight = edge_data.get("weight", 1.0)
            relationship = edge_data.get("relationship", "related")

            if weight >= min_weight and neighbor.startswith("conv:"):
                conv_id = neighbor[5:]  # Remove "conv:" prefix
                connections.append((conv_id, weight, relationship))

        # Sort by weight descending
        connections.sort(key=lambda x: x[1], reverse=True)
        return connections

    def to_dict(self) -> dict[str, Any]:
        """Export the knowledge graph to a dictionary.

        Returns:
            Dictionary representation of the graph.
        """
        return {
            "nodes": [
                {
                    "id": node_id,
                    "type": info.node_type,
                    "label": info.label,
                    "importance_score": info.importance_score,
                    "metadata": info.metadata,
                }
                for node_id, info in self.nodes.items()
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "relationship": edge.relationship,
                    "weight": edge.weight,
                    "metadata": edge.metadata,
                }
                for edge in self.edges
            ],
            "communities": self.communities,
            "stats": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "total_communities": len(self.communities),
                "node_types": self._count_node_types(),
            },
        }

    def to_json(self, indent: int = 2) -> str:
        """Export the knowledge graph to JSON string.

        Args:
            indent: JSON indentation level.

        Returns:
            JSON string representation of the graph.
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def _count_node_types(self) -> dict[str, int]:
        """Count nodes by type.

        Returns:
            Dictionary mapping node types to counts.
        """
        counts: dict[str, int] = defaultdict(int)
        for node_info in self.nodes.values():
            counts[node_info.node_type] += 1
        return dict(counts)

    def to_model(self) -> "KnowledgeGraph":
        """Convert to the dataclass KnowledgeGraph model for serialization.

        Returns:
            KnowledgeGraph dataclass instance from models.py.
        """
        from agents.models import KnowledgeGraph as ModelKnowledgeGraph
        from agents.models import KnowledgeNode, KnowledgeEdge

        model_nodes: dict[str, KnowledgeNode] = {}
        for node_id, info in self.nodes.items():
            connections = [n for n in self.graph.neighbors(node_id)]
            model_nodes[node_id] = KnowledgeNode(
                id=node_id,
                node_type=info.node_type,
                label=info.label,
                metadata={**info.metadata, "importance_score": info.importance_score},
                connections=connections,
            )

        model_edges: list[KnowledgeEdge] = [
            KnowledgeEdge(
                source=edge.source,
                target=edge.target,
                edge_type=edge.relationship,
                weight=edge.weight,
                metadata=edge.metadata,
            )
            for edge in self.edges
        ]

        # Convert communities to string keys for model compatibility
        clusters = {str(k): v for k, v in self.communities.items()}

        return ModelKnowledgeGraph(
            nodes=model_nodes,
            edges=model_edges,
            clusters=clusters,
            metadata={
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "node_types": self._count_node_types(),
            },
        )


# Alias for backward compatibility
KnowledgeGraph = NetworkXKnowledgeGraph


class GraphBuilderAgent:
    """Agent that builds a knowledge graph from enriched conversations.

    Analyzes relationships between conversations based on shared tags, concepts,
    temporal proximity, shared people, and semantic similarity.

    Attributes:
        temporal_window_days: Days within which conversations are considered temporally related.
        min_shared_concepts: Minimum shared concepts for a concept-based connection.
        min_shared_tags: Minimum shared tags for a tag-based connection.
    """

    def __init__(
        self,
        temporal_window_days: int = 7,
        min_shared_concepts: int = 2,
        min_shared_tags: int = 1,
    ) -> None:
        """Initialize the GraphBuilderAgent.

        Args:
            temporal_window_days: Days within which conversations are temporally related.
            min_shared_concepts: Minimum shared concepts for concept-based connection.
            min_shared_tags: Minimum shared tags for tag-based connection.
        """
        self.temporal_window_days = temporal_window_days
        self.min_shared_concepts = min_shared_concepts
        self.min_shared_tags = min_shared_tags

    def _normalize_term(self, term: str) -> str:
        """Normalize a term for consistent matching.

        Args:
            term: The term to normalize.

        Returns:
            Normalized term string.
        """
        return term.lower().strip()

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity between two strings.

        Uses Jaccard similarity on word sets for efficiency.

        Args:
            text1: First text string.
            text2: Second text string.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        if not text1 or not text2:
            return 0.0

        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0

    async def _add_conversation_nodes(
        self,
        graph: NetworkXKnowledgeGraph,
        conversations: list[EnrichedConversation],
    ) -> None:
        """Add conversation nodes to the graph.

        Args:
            graph: The knowledge graph to add nodes to.
            conversations: List of enriched conversations.
        """
        for conv in conversations:
            node_id = f"conv:{conv.id}"
            graph.add_node(
                node_id=node_id,
                node_type="conversation",
                label=conv.title,
                metadata={
                    "created_at": conv.created_at.isoformat(),
                    "category": conv.category,
                    "summary": conv.summary,
                    "message_count": len(conv.messages),
                },
            )

    async def _add_concept_nodes(
        self,
        graph: NetworkXKnowledgeGraph,
        conversations: list[EnrichedConversation],
    ) -> None:
        """Add concept nodes and link them to conversations.

        Args:
            graph: The knowledge graph to add nodes to.
            conversations: List of enriched conversations.
        """
        concept_counts: dict[str, int] = defaultdict(int)

        # First pass: count concept occurrences
        for conv in conversations:
            for concept in conv.concepts:
                normalized = self._normalize_term(concept)
                concept_counts[normalized] += 1

        # Second pass: add nodes and edges
        for conv in conversations:
            conv_node_id = f"conv:{conv.id}"
            for concept in conv.concepts:
                normalized = self._normalize_term(concept)
                concept_node_id = f"concept:{normalized}"

                if concept_node_id not in graph.nodes:
                    graph.add_node(
                        node_id=concept_node_id,
                        node_type="concept",
                        label=concept,
                        metadata={"occurrence_count": concept_counts[normalized]},
                    )

                graph.add_edge(
                    source=conv_node_id,
                    target=concept_node_id,
                    relationship="discusses",
                    weight=1.0,
                )

    async def _add_tag_nodes(
        self,
        graph: NetworkXKnowledgeGraph,
        conversations: list[EnrichedConversation],
    ) -> None:
        """Add tag nodes and link them to conversations.

        Args:
            graph: The knowledge graph to add nodes to.
            conversations: List of enriched conversations.
        """
        tag_counts: dict[str, int] = defaultdict(int)

        # Count tag occurrences
        for conv in conversations:
            for tag in conv.tags:
                normalized = self._normalize_term(tag)
                tag_counts[normalized] += 1

        # Add nodes and edges
        for conv in conversations:
            conv_node_id = f"conv:{conv.id}"
            for tag in conv.tags:
                normalized = self._normalize_term(tag)
                tag_node_id = f"tag:{normalized}"

                if tag_node_id not in graph.nodes:
                    graph.add_node(
                        node_id=tag_node_id,
                        node_type="tag",
                        label=tag,
                        metadata={"occurrence_count": tag_counts[normalized]},
                    )

                # Weight based on tag confidence if available
                weight = conv.tag_confidence.get(tag, 1.0)
                graph.add_edge(
                    source=conv_node_id,
                    target=tag_node_id,
                    relationship="tagged_with",
                    weight=weight,
                )

    async def _add_people_nodes(
        self,
        graph: NetworkXKnowledgeGraph,
        conversations: list[EnrichedConversation],
    ) -> None:
        """Add people nodes and link them to conversations.

        Args:
            graph: The knowledge graph to add nodes to.
            conversations: List of enriched conversations.
        """
        people_counts: dict[str, int] = defaultdict(int)

        # Count people occurrences
        for conv in conversations:
            for person in conv.people_mentioned:
                normalized = self._normalize_term(person)
                people_counts[normalized] += 1

        # Add nodes and edges
        for conv in conversations:
            conv_node_id = f"conv:{conv.id}"
            for person in conv.people_mentioned:
                normalized = self._normalize_term(person)
                person_node_id = f"person:{normalized}"

                if person_node_id not in graph.nodes:
                    graph.add_node(
                        node_id=person_node_id,
                        node_type="person",
                        label=person,
                        metadata={"mention_count": people_counts[normalized]},
                    )

                graph.add_edge(
                    source=conv_node_id,
                    target=person_node_id,
                    relationship="mentions",
                    weight=1.0,
                )

    async def _add_temporal_edges(
        self,
        graph: NetworkXKnowledgeGraph,
        conversations: list[EnrichedConversation],
    ) -> None:
        """Add edges between temporally proximate conversations.

        Args:
            graph: The knowledge graph to add edges to.
            conversations: List of enriched conversations.
        """
        window = timedelta(days=self.temporal_window_days)

        for i, conv1 in enumerate(conversations):
            conv1_node = f"conv:{conv1.id}"
            for conv2 in conversations[i + 1:]:
                conv2_node = f"conv:{conv2.id}"

                time_diff = abs(conv1.created_at - conv2.created_at)
                if time_diff <= window:
                    # Weight inversely proportional to time difference
                    days_diff = time_diff.total_seconds() / 86400
                    weight = max(0.1, 1.0 - (days_diff / self.temporal_window_days))

                    graph.add_edge(
                        source=conv1_node,
                        target=conv2_node,
                        relationship="temporal_proximity",
                        weight=weight * 0.5,  # Lower weight than content-based
                        metadata={"days_apart": days_diff},
                    )

    async def _add_shared_concept_edges(
        self,
        graph: NetworkXKnowledgeGraph,
        conversations: list[EnrichedConversation],
    ) -> None:
        """Add edges between conversations sharing concepts.

        Args:
            graph: The knowledge graph to add edges to.
            conversations: List of enriched conversations.
        """
        for i, conv1 in enumerate(conversations):
            concepts1 = {self._normalize_term(c) for c in conv1.concepts}
            conv1_node = f"conv:{conv1.id}"

            for conv2 in conversations[i + 1:]:
                concepts2 = {self._normalize_term(c) for c in conv2.concepts}
                conv2_node = f"conv:{conv2.id}"

                shared = concepts1 & concepts2
                if len(shared) >= self.min_shared_concepts:
                    weight = len(shared) / max(len(concepts1), len(concepts2), 1)
                    graph.add_edge(
                        source=conv1_node,
                        target=conv2_node,
                        relationship="shared_concepts",
                        weight=weight,
                        metadata={"shared_concepts": list(shared)},
                    )

    async def _add_shared_tag_edges(
        self,
        graph: NetworkXKnowledgeGraph,
        conversations: list[EnrichedConversation],
    ) -> None:
        """Add edges between conversations sharing tags.

        Args:
            graph: The knowledge graph to add edges to.
            conversations: List of enriched conversations.
        """
        for i, conv1 in enumerate(conversations):
            tags1 = {self._normalize_term(t) for t in conv1.tags}
            conv1_node = f"conv:{conv1.id}"

            for conv2 in conversations[i + 1:]:
                tags2 = {self._normalize_term(t) for t in conv2.tags}
                conv2_node = f"conv:{conv2.id}"

                shared = tags1 & tags2
                if len(shared) >= self.min_shared_tags:
                    weight = len(shared) / max(len(tags1), len(tags2), 1)
                    graph.add_edge(
                        source=conv1_node,
                        target=conv2_node,
                        relationship="shared_tags",
                        weight=weight * 1.5,  # Tags are strong signals
                        metadata={"shared_tags": list(shared)},
                    )

    async def _add_shared_people_edges(
        self,
        graph: NetworkXKnowledgeGraph,
        conversations: list[EnrichedConversation],
    ) -> None:
        """Add edges between conversations mentioning the same people.

        Args:
            graph: The knowledge graph to add edges to.
            conversations: List of enriched conversations.
        """
        for i, conv1 in enumerate(conversations):
            people1 = {self._normalize_term(p) for p in conv1.people_mentioned}
            conv1_node = f"conv:{conv1.id}"

            for conv2 in conversations[i + 1:]:
                people2 = {self._normalize_term(p) for p in conv2.people_mentioned}
                conv2_node = f"conv:{conv2.id}"

                shared = people1 & people2
                if shared:
                    weight = len(shared) / max(len(people1), len(people2), 1)
                    graph.add_edge(
                        source=conv1_node,
                        target=conv2_node,
                        relationship="shared_people",
                        weight=weight,
                        metadata={"shared_people": list(shared)},
                    )

    async def _add_semantic_similarity_edges(
        self,
        graph: NetworkXKnowledgeGraph,
        conversations: list[EnrichedConversation],
        similarity_threshold: float = 0.3,
    ) -> None:
        """Add edges between conversations with similar summaries.

        Args:
            graph: The knowledge graph to add edges to.
            conversations: List of enriched conversations.
            similarity_threshold: Minimum similarity for edge creation.
        """
        for i, conv1 in enumerate(conversations):
            conv1_node = f"conv:{conv1.id}"

            for conv2 in conversations[i + 1:]:
                conv2_node = f"conv:{conv2.id}"

                similarity = self._calculate_text_similarity(conv1.summary, conv2.summary)
                if similarity >= similarity_threshold:
                    graph.add_edge(
                        source=conv1_node,
                        target=conv2_node,
                        relationship="semantic_similarity",
                        weight=similarity,
                        metadata={"similarity_score": similarity},
                    )

    def _display_graph_stats(self, graph: NetworkXKnowledgeGraph) -> None:
        """Display statistics about the knowledge graph.

        Args:
            graph: The knowledge graph to analyze.
        """
        stats = graph._count_node_types()

        table = Table(title="Knowledge Graph Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Nodes", str(len(graph.nodes)))
        table.add_row("Total Edges", str(len(graph.edges)))
        table.add_row("Communities", str(len(graph.communities)))

        for node_type, count in sorted(stats.items()):
            table.add_row(f"  {node_type.capitalize()} nodes", str(count))

        # Top importance scores
        if graph._importance_scores:
            top_nodes = sorted(
                graph._importance_scores.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]

            table.add_row("", "")
            table.add_row("[bold]Top 5 Important Nodes[/bold]", "")
            for node_id, score in top_nodes:
                if node_id in graph.nodes:
                    label = graph.nodes[node_id].label[:30]
                    table.add_row(f"  {label}", f"{score:.4f}")

        console.print(table)

    async def process(
        self,
        conversations: list[EnrichedConversation],
    ) -> NetworkXKnowledgeGraph:
        """Build a knowledge graph from enriched conversations.

        Args:
            conversations: List of enriched conversations to process.

        Returns:
            KnowledgeGraph containing nodes and relationships.
        """
        if not conversations:
            console.print("[yellow]No conversations to process[/yellow]")
            return NetworkXKnowledgeGraph()

        console.print(f"\n[bold blue]Building knowledge graph from {len(conversations)} conversations[/bold blue]")

        graph = NetworkXKnowledgeGraph()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            # Add all node types
            task = progress.add_task("[cyan]Adding nodes...", total=4)

            await self._add_conversation_nodes(graph, conversations)
            progress.advance(task)

            await self._add_concept_nodes(graph, conversations)
            progress.advance(task)

            await self._add_tag_nodes(graph, conversations)
            progress.advance(task)

            await self._add_people_nodes(graph, conversations)
            progress.advance(task)

            # Add relationship edges
            task = progress.add_task("[cyan]Building relationships...", total=5)

            await self._add_shared_tag_edges(graph, conversations)
            progress.advance(task)

            await self._add_shared_concept_edges(graph, conversations)
            progress.advance(task)

            await self._add_temporal_edges(graph, conversations)
            progress.advance(task)

            await self._add_shared_people_edges(graph, conversations)
            progress.advance(task)

            await self._add_semantic_similarity_edges(graph, conversations)
            progress.advance(task)

            # Calculate importance and communities
            task = progress.add_task("[cyan]Analyzing graph...", total=2)

            graph.calculate_importance_scores()
            progress.advance(task)

            graph.identify_communities()
            progress.advance(task)

        console.print("\n[bold green]Knowledge graph built successfully![/bold green]")
        self._display_graph_stats(graph)

        return graph
