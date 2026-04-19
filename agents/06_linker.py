"""
LinkerAgent - Creates bidirectional Obsidian wikilinks between related notes.

This agent uses the knowledge graph to determine which notes should link to each
other, creating Obsidian-compatible wikilinks based on graph connections, shared
concepts, and chronological sequences.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import Field
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from agents.extractor import EnrichedConversation
from agents.graph_builder import NetworkXKnowledgeGraph


console = Console()


class LinkedConversation(EnrichedConversation):
    """Conversation with Obsidian wikilink connections.

    Extends EnrichedConversation with link information for Obsidian notes.

    Attributes:
        related_notes: Titles of related conversations to link to.
        concept_links: Concepts that should be linked to concept pages.
        backlinks: Notes that should link back to this conversation.
        link_metadata: Additional metadata about each link relationship.
    """
    related_notes: list[str] = Field(
        default_factory=list,
        description="Titles of related conversations"
    )
    concept_links: list[str] = Field(
        default_factory=list,
        description="Concepts to link to concept pages"
    )
    backlinks: list[str] = Field(
        default_factory=list,
        description="Notes that should link back to this conversation"
    )
    link_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about link relationships"
    )

    class Config:
        frozen = False
        extra = "ignore"


@dataclass
class LinkCandidate:
    """Candidate for a potential link between notes.

    Attributes:
        target_id: ID of the target conversation.
        target_title: Title of the target conversation.
        score: Relevance score for the link.
        relationship_types: Types of relationships that suggest this link.
        shared_elements: Shared concepts, tags, or people that connect the notes.
    """
    target_id: str
    target_title: str
    score: float
    relationship_types: list[str] = field(default_factory=list)
    shared_elements: dict[str, list[str]] = field(default_factory=dict)


class LinkerAgent:
    """Agent that creates bidirectional Obsidian wikilinks.

    Uses the knowledge graph to determine optimal links between notes based on
    connection strength, shared concepts, and chronological sequences.

    Attributes:
        max_related_notes: Maximum number of related notes to link.
        max_concept_links: Maximum number of concept links per note.
        min_connection_weight: Minimum weight threshold for linking.
        link_to_concepts: Whether to create links to concept pages.
    """

    def __init__(
        self,
        max_related_notes: int = 10,
        max_concept_links: int = 15,
        min_connection_weight: float = 0.3,
        link_to_concepts: bool = True,
        link_to_people: bool = True,
        link_to_tags: bool = False,
    ) -> None:
        """Initialize the LinkerAgent.

        Args:
            max_related_notes: Maximum related notes to link per conversation.
            max_concept_links: Maximum concept links per conversation.
            min_connection_weight: Minimum connection weight for linking.
            link_to_concepts: Whether to create links to concept pages.
            link_to_people: Whether to create links to people pages.
            link_to_tags: Whether to create links to tag pages.
        """
        self.max_related_notes = max_related_notes
        self.max_concept_links = max_concept_links
        self.min_connection_weight = min_connection_weight
        self.link_to_concepts = link_to_concepts
        self.link_to_people = link_to_people
        self.link_to_tags = link_to_tags

    def _sanitize_for_wikilink(self, text: str) -> str:
        """Sanitize text for use in Obsidian wikilinks.

        Args:
            text: Text to sanitize.

        Returns:
            Sanitized text safe for wikilinks.
        """
        # Remove characters that are problematic in wikilinks
        invalid_chars = ['[', ']', '|', '#', '^', '\\']
        result = text
        for char in invalid_chars:
            result = result.replace(char, '')
        return result.strip()

    def _format_wikilink(self, title: str, alias: Optional[str] = None) -> str:
        """Format a title as an Obsidian wikilink.

        Args:
            title: The page title to link to.
            alias: Optional display alias for the link.

        Returns:
            Formatted Obsidian wikilink string.
        """
        sanitized_title = self._sanitize_for_wikilink(title)
        if alias and alias != sanitized_title:
            sanitized_alias = self._sanitize_for_wikilink(alias)
            return f"[[{sanitized_title}|{sanitized_alias}]]"
        return f"[[{sanitized_title}]]"

    def _calculate_link_candidates(
        self,
        conversation: EnrichedConversation,
        all_conversations: dict[str, EnrichedConversation],
        graph: NetworkXKnowledgeGraph,
    ) -> list[LinkCandidate]:
        """Calculate potential link candidates for a conversation.

        Args:
            conversation: The source conversation.
            all_conversations: Dictionary of all conversations by ID.
            graph: The knowledge graph.

        Returns:
            List of LinkCandidate objects sorted by score.
        """
        conv_node_id = f"conv:{conversation.id}"
        candidates: dict[str, LinkCandidate] = {}

        if conv_node_id not in graph.graph:
            return []

        # Find all conversation neighbors in the graph
        for neighbor in graph.graph.neighbors(conv_node_id):
            if not neighbor.startswith("conv:"):
                continue

            target_id = neighbor[5:]  # Remove "conv:" prefix
            if target_id == conversation.id or target_id not in all_conversations:
                continue

            target_conv = all_conversations[target_id]

            # Get edge data
            edge_data = graph.graph[conv_node_id][neighbor]
            weight = edge_data.get("weight", 0.0)
            relationship = edge_data.get("relationship", "related")

            if target_id not in candidates:
                candidates[target_id] = LinkCandidate(
                    target_id=target_id,
                    target_title=target_conv.title,
                    score=weight,
                    relationship_types=[relationship],
                    shared_elements={},
                )
            else:
                candidates[target_id].score += weight
                if relationship not in candidates[target_id].relationship_types:
                    candidates[target_id].relationship_types.append(relationship)

            # Add shared elements metadata
            if "shared_concepts" in edge_data:
                candidates[target_id].shared_elements["concepts"] = edge_data["shared_concepts"]
            if "shared_tags" in edge_data:
                candidates[target_id].shared_elements["tags"] = edge_data["shared_tags"]
            if "shared_people" in edge_data:
                candidates[target_id].shared_elements["people"] = edge_data["shared_people"]

        # Also find indirect connections (conversations sharing the same concepts/tags)
        for neighbor in graph.graph.neighbors(conv_node_id):
            if neighbor.startswith("concept:") or neighbor.startswith("tag:"):
                # Find other conversations connected to this concept/tag
                for second_neighbor in graph.graph.neighbors(neighbor):
                    if not second_neighbor.startswith("conv:"):
                        continue

                    target_id = second_neighbor[5:]
                    if target_id == conversation.id or target_id not in all_conversations:
                        continue

                    target_conv = all_conversations[target_id]

                    # Calculate indirect weight (lower than direct connections)
                    edge1_weight = graph.graph[conv_node_id][neighbor].get("weight", 1.0)
                    edge2_weight = graph.graph[neighbor][second_neighbor].get("weight", 1.0)
                    indirect_weight = (edge1_weight * edge2_weight) * 0.3

                    element_type = "concepts" if neighbor.startswith("concept:") else "tags"
                    element_name = neighbor.split(":", 1)[1]

                    if target_id not in candidates:
                        candidates[target_id] = LinkCandidate(
                            target_id=target_id,
                            target_title=target_conv.title,
                            score=indirect_weight,
                            relationship_types=["indirect"],
                            shared_elements={element_type: [element_name]},
                        )
                    else:
                        candidates[target_id].score += indirect_weight
                        if element_type not in candidates[target_id].shared_elements:
                            candidates[target_id].shared_elements[element_type] = []
                        if element_name not in candidates[target_id].shared_elements[element_type]:
                            candidates[target_id].shared_elements[element_type].append(element_name)

        # Sort candidates by score
        sorted_candidates = sorted(
            candidates.values(),
            key=lambda c: c.score,
            reverse=True,
        )

        return sorted_candidates

    def _get_concept_links(
        self,
        conversation: EnrichedConversation,
        graph: NetworkXKnowledgeGraph,
    ) -> list[str]:
        """Get concepts that should be linked to concept pages.

        Args:
            conversation: The conversation to get concept links for.
            graph: The knowledge graph.

        Returns:
            List of concept names to link to.
        """
        if not self.link_to_concepts:
            return []

        # Get concepts sorted by their importance in the graph
        concept_scores: list[tuple[str, float]] = []

        for concept in conversation.concepts:
            normalized = concept.lower().strip()
            concept_node_id = f"concept:{normalized}"

            if concept_node_id in graph.nodes:
                score = graph.nodes[concept_node_id].importance_score
                # Also consider how many conversations use this concept
                occurrence = graph.nodes[concept_node_id].metadata.get("occurrence_count", 1)
                combined_score = score * (1 + 0.1 * occurrence)
                concept_scores.append((concept, combined_score))
            else:
                concept_scores.append((concept, 0.0))

        # Sort by score and return top concepts
        concept_scores.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in concept_scores[:self.max_concept_links]]

    def _calculate_backlinks(
        self,
        conversation_id: str,
        all_linked: dict[str, list[str]],
    ) -> list[str]:
        """Calculate which notes should have backlinks to this conversation.

        Args:
            conversation_id: The conversation ID to find backlinks for.
            all_linked: Dictionary mapping conversation IDs to their related notes.

        Returns:
            List of conversation titles that link to this one.
        """
        backlinks: list[str] = []

        for source_id, related_titles in all_linked.items():
            if source_id == conversation_id:
                continue

            # Check if any of the related titles match this conversation
            # This is a simplified check - in practice, you'd match by ID
            for title in related_titles:
                # The title being linked should be tracked for backlinks
                # Note: This builds backlinks based on the linking structure
                pass

        return backlinks

    def _get_chronological_links(
        self,
        conversation: EnrichedConversation,
        all_conversations: list[EnrichedConversation],
        same_category_only: bool = True,
    ) -> tuple[Optional[str], Optional[str]]:
        """Find previous and next conversations in chronological order.

        Args:
            conversation: The current conversation.
            all_conversations: All conversations sorted by date.
            same_category_only: If True, only link within same category.

        Returns:
            Tuple of (previous_title, next_title).
        """
        # Filter to same category if requested
        if same_category_only:
            relevant = [
                c for c in all_conversations
                if c.category == conversation.category
            ]
        else:
            relevant = all_conversations

        # Sort by created_at
        sorted_convs = sorted(relevant, key=lambda c: c.created_at)

        # Find current conversation index
        current_idx = None
        for i, c in enumerate(sorted_convs):
            if c.id == conversation.id:
                current_idx = i
                break

        if current_idx is None:
            return None, None

        prev_title = sorted_convs[current_idx - 1].title if current_idx > 0 else None
        next_title = sorted_convs[current_idx + 1].title if current_idx < len(sorted_convs) - 1 else None

        return prev_title, next_title

    async def process(
        self,
        conversations: list[EnrichedConversation],
        graph: NetworkXKnowledgeGraph,
    ) -> list[LinkedConversation]:
        """Process conversations and create bidirectional wikilinks.

        Args:
            conversations: List of enriched conversations.
            graph: The knowledge graph containing relationships.

        Returns:
            List of LinkedConversation with wikilink information.
        """
        if not conversations:
            console.print("[yellow]No conversations to process[/yellow]")
            return []

        console.print(f"\n[bold blue]Creating links for {len(conversations)} conversations[/bold blue]")

        # Create lookup dictionary
        conv_by_id: dict[str, EnrichedConversation] = {c.id: c for c in conversations}

        # Track all links for backlink calculation
        all_links: dict[str, list[str]] = defaultdict(list)

        results: list[LinkedConversation] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Analyzing connections...", total=len(conversations))

            for conv in conversations:
                # Calculate link candidates
                candidates = self._calculate_link_candidates(conv, conv_by_id, graph)

                # Filter by minimum weight and take top N
                filtered_candidates = [
                    c for c in candidates
                    if c.score >= self.min_connection_weight
                ][:self.max_related_notes]

                # Get related note titles
                related_notes = [c.target_title for c in filtered_candidates]
                all_links[conv.id] = related_notes

                # Get concept links
                concept_links = self._get_concept_links(conv, graph)

                # Get chronological links
                prev_title, next_title = self._get_chronological_links(conv, conversations)

                # Build link metadata
                link_metadata: dict[str, Any] = {
                    "link_scores": {c.target_title: c.score for c in filtered_candidates},
                    "relationship_types": {
                        c.target_title: c.relationship_types for c in filtered_candidates
                    },
                    "shared_elements": {
                        c.target_title: c.shared_elements for c in filtered_candidates
                    },
                }

                if prev_title:
                    link_metadata["previous_in_sequence"] = prev_title
                if next_title:
                    link_metadata["next_in_sequence"] = next_title

                # Create LinkedConversation
                linked = LinkedConversation(
                    **conv.model_dump(),
                    related_notes=related_notes,
                    concept_links=concept_links,
                    backlinks=[],  # Will be filled in second pass
                    link_metadata=link_metadata,
                )
                results.append(linked)
                progress.advance(task)

            # Second pass: calculate backlinks
            task = progress.add_task("[cyan]Building backlinks...", total=len(results))

            # Build reverse index: which conversations link to which
            backlink_index: dict[str, list[str]] = defaultdict(list)
            for conv_id, related_titles in all_links.items():
                source_title = conv_by_id[conv_id].title
                for target_title in related_titles:
                    # Find the conversation with this title
                    for target_conv in conversations:
                        if target_conv.title == target_title:
                            backlink_index[target_conv.id].append(source_title)
                            break

            # Update backlinks in results
            for linked in results:
                linked.backlinks = backlink_index.get(linked.id, [])
                progress.advance(task)

        # Display summary statistics
        self._display_link_stats(results)

        return results

    def _display_link_stats(self, results: list[LinkedConversation]) -> None:
        """Display statistics about the created links.

        Args:
            results: List of linked conversations.
        """
        total_related = sum(len(r.related_notes) for r in results)
        total_concepts = sum(len(r.concept_links) for r in results)
        total_backlinks = sum(len(r.backlinks) for r in results)

        avg_related = total_related / len(results) if results else 0
        avg_concepts = total_concepts / len(results) if results else 0
        avg_backlinks = total_backlinks / len(results) if results else 0

        # Find most connected conversations
        most_connected = sorted(
            results,
            key=lambda r: len(r.related_notes) + len(r.backlinks),
            reverse=True,
        )[:5]

        table = Table(title="Link Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Related Links", str(total_related))
        table.add_row("Total Concept Links", str(total_concepts))
        table.add_row("Total Backlinks", str(total_backlinks))
        table.add_row("", "")
        table.add_row("Avg Related per Note", f"{avg_related:.1f}")
        table.add_row("Avg Concepts per Note", f"{avg_concepts:.1f}")
        table.add_row("Avg Backlinks per Note", f"{avg_backlinks:.1f}")

        console.print(table)

        if most_connected:
            console.print("\n[bold]Most Connected Notes:[/bold]")
            for i, linked in enumerate(most_connected, 1):
                total_links = len(linked.related_notes) + len(linked.backlinks)
                console.print(f"  {i}. {linked.title[:50]} ({total_links} connections)")

        console.print("\n[bold green]Linking complete![/bold green]")

    def format_links_for_obsidian(
        self,
        linked_conv: LinkedConversation,
    ) -> dict[str, str]:
        """Format all links for embedding in an Obsidian note.

        Args:
            linked_conv: The linked conversation to format links for.

        Returns:
            Dictionary with formatted link sections.
        """
        sections: dict[str, str] = {}

        # Related Notes section
        if linked_conv.related_notes:
            links = [self._format_wikilink(title) for title in linked_conv.related_notes]
            sections["related_notes"] = "\n".join(f"- {link}" for link in links)

        # Concepts section
        if linked_conv.concept_links:
            # Concepts go in a concepts folder
            links = [
                self._format_wikilink(f"Concepts/{concept}", concept)
                for concept in linked_conv.concept_links
            ]
            sections["concepts"] = " ".join(links)

        # Backlinks section
        if linked_conv.backlinks:
            links = [self._format_wikilink(title) for title in linked_conv.backlinks]
            sections["backlinks"] = "\n".join(f"- {link}" for link in links)

        # Chronological navigation
        metadata = linked_conv.link_metadata
        nav_links = []
        if "previous_in_sequence" in metadata:
            prev_link = self._format_wikilink(metadata["previous_in_sequence"], "Previous")
            nav_links.append(prev_link)
        if "next_in_sequence" in metadata:
            next_link = self._format_wikilink(metadata["next_in_sequence"], "Next")
            nav_links.append(next_link)

        if nav_links:
            sections["navigation"] = " | ".join(nav_links)

        return sections
