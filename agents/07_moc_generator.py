"""
MOC Generator Agent for Claude Obsidian Second Brain.

Generates Maps of Content (MOC) hub pages that organize conversations
into navigable topic hierarchies for Obsidian.
"""
from __future__ import annotations

import asyncio
import os
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from agents.models import KnowledgeGraph, LinkedConversation, MOCPage

console = Console()


class MOCGeneratorAgent:
    """Agent that generates Maps of Content (MOC) hub pages.

    MOCs are organizational hub pages that link related conversations
    together, providing navigation through the knowledge base.

    Attributes:
        client: Anthropic API client for generating descriptions.
        model: Model to use for generation.
        min_notes_for_moc: Minimum notes required to create a MOC.
        high_connectivity_threshold: Node degree to consider high connectivity.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        min_notes_for_moc: int = 3,
        high_connectivity_threshold: int = 5,
    ) -> None:
        """Initialize the MOC Generator Agent.

        Args:
            api_key: Anthropic API key. Uses ANTHROPIC_API_KEY env var if not provided.
            model: Model to use for generating MOC descriptions.
            min_notes_for_moc: Minimum number of notes required to create a MOC.
            high_connectivity_threshold: Minimum connections to be considered high connectivity.
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = model
        self.min_notes_for_moc = min_notes_for_moc
        self.high_connectivity_threshold = high_connectivity_threshold

    async def process(
        self,
        conversations: list[LinkedConversation],
        graph: KnowledgeGraph,
    ) -> list[MOCPage]:
        """Generate MOC pages from conversations and knowledge graph.

        Creates MOCs for:
        - Each major category from taxonomy
        - High-connectivity topics (nodes with many connections)
        - Temporal groupings (monthly/quarterly reviews)

        Args:
            conversations: List of linked conversations to organize.
            graph: Knowledge graph with relationships.

        Returns:
            List of generated MOCPage objects.
        """
        console.print(
            Panel(
                "[bold cyan]MOC Generator Agent[/bold cyan]\n"
                "Generating Maps of Content for knowledge organization",
                border_style="cyan",
            )
        )

        mocs: list[MOCPage] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # Generate category MOCs
            task1 = progress.add_task(
                "[cyan]Generating category MOCs...", total=None
            )
            category_mocs = await self._generate_category_mocs(conversations)
            mocs.extend(category_mocs)
            progress.update(task1, completed=True, total=1)

            # Generate high-connectivity topic MOCs
            task2 = progress.add_task(
                "[cyan]Generating topic MOCs...", total=None
            )
            topic_mocs = await self._generate_topic_mocs(conversations, graph)
            mocs.extend(topic_mocs)
            progress.update(task2, completed=True, total=1)

            # Generate temporal MOCs
            task3 = progress.add_task(
                "[cyan]Generating temporal MOCs...", total=None
            )
            temporal_mocs = await self._generate_temporal_mocs(conversations)
            mocs.extend(temporal_mocs)
            progress.update(task3, completed=True, total=1)

            # Generate master MOC
            task4 = progress.add_task(
                "[cyan]Generating master MOC...", total=None
            )
            master_moc = await self._generate_master_moc(mocs, conversations)
            mocs.insert(0, master_moc)
            progress.update(task4, completed=True, total=1)

        # Display summary
        self._display_summary(mocs)

        return mocs

    async def _generate_category_mocs(
        self,
        conversations: list[LinkedConversation],
    ) -> list[MOCPage]:
        """Generate MOCs for each major category.

        Args:
            conversations: List of linked conversations.

        Returns:
            List of category MOCPage objects.
        """
        # Group conversations by category
        category_groups: dict[str, list[LinkedConversation]] = defaultdict(list)
        for conv in conversations:
            category_groups[conv.category].append(conv)

        mocs: list[MOCPage] = []

        for category, convs in category_groups.items():
            if len(convs) < self.min_notes_for_moc:
                continue

            # Extract key concepts from conversations in this category
            concepts = self._extract_concepts(convs)

            # Generate description using Claude API
            description = await self._generate_moc_description(
                category,
                [c.title for c in convs[:10]],
                concepts[:10],
            )

            # Build content
            content = self._build_moc_content(
                title=f"{category} MOC",
                description=description,
                conversations=convs,
                concepts=concepts,
            )

            moc = MOCPage(
                title=f"{category} MOC",
                category=category,
                description=description,
                linked_notes=[c.title for c in convs],
                sub_mocs=[],
                key_concepts=concepts[:15],
                content=content,
            )
            mocs.append(moc)

        return mocs

    async def _generate_topic_mocs(
        self,
        conversations: list[LinkedConversation],
        graph: KnowledgeGraph,
    ) -> list[MOCPage]:
        """Generate MOCs for high-connectivity topics.

        Args:
            conversations: List of linked conversations.
            graph: Knowledge graph with node connections.

        Returns:
            List of topic MOCPage objects.
        """
        mocs: list[MOCPage] = []

        # Find high-connectivity concept nodes
        high_connectivity_nodes: list[tuple[str, int]] = []
        for node_id, node in graph.nodes.items():
            if node.node_type == "concept":
                degree = graph.get_node_degree(node_id)
                if degree >= self.high_connectivity_threshold:
                    high_connectivity_nodes.append((node_id, degree))

        # Sort by degree
        high_connectivity_nodes.sort(key=lambda x: x[1], reverse=True)

        # Create MOC for top topics
        conv_by_id = {c.id: c for c in conversations}

        for node_id, degree in high_connectivity_nodes[:20]:
            node = graph.nodes[node_id]
            topic = node.label

            # Find conversations connected to this topic
            connected_conv_ids = graph.get_node_connections(node_id)
            connected_convs = [
                conv_by_id[cid]
                for cid in connected_conv_ids
                if cid in conv_by_id
            ]

            if len(connected_convs) < self.min_notes_for_moc:
                continue

            # Extract related concepts
            related_concepts = self._extract_concepts(connected_convs)
            related_concepts = [c for c in related_concepts if c != topic]

            # Generate description
            description = await self._generate_moc_description(
                topic,
                [c.title for c in connected_convs[:10]],
                related_concepts[:10],
            )

            content = self._build_moc_content(
                title=f"{topic} MOC",
                description=description,
                conversations=connected_convs,
                concepts=related_concepts,
            )

            moc = MOCPage(
                title=f"{topic} MOC",
                category="Topics",
                description=description,
                linked_notes=[c.title for c in connected_convs],
                sub_mocs=[],
                key_concepts=related_concepts[:15],
                content=content,
            )
            mocs.append(moc)

        return mocs

    async def _generate_temporal_mocs(
        self,
        conversations: list[LinkedConversation],
    ) -> list[MOCPage]:
        """Generate MOCs for temporal groupings (monthly/quarterly).

        Args:
            conversations: List of linked conversations.

        Returns:
            List of temporal MOCPage objects.
        """
        mocs: list[MOCPage] = []

        # Group by month
        monthly_groups: dict[str, list[LinkedConversation]] = defaultdict(list)
        for conv in conversations:
            month_key = conv.created_at.strftime("%Y-%m")
            monthly_groups[month_key].append(conv)

        # Create monthly MOCs
        for month_key, convs in sorted(monthly_groups.items()):
            if len(convs) < self.min_notes_for_moc:
                continue

            date_obj = datetime.strptime(month_key, "%Y-%m")
            month_name = date_obj.strftime("%B %Y")

            concepts = self._extract_concepts(convs)
            categories = list(set(c.category for c in convs))

            description = (
                f"Conversations from {month_name}. "
                f"Covers {len(convs)} discussions across categories: "
                f"{', '.join(categories[:5])}."
            )

            content = self._build_temporal_moc_content(
                title=f"{month_name} Review",
                description=description,
                conversations=convs,
                concepts=concepts,
            )

            moc = MOCPage(
                title=f"{month_name} Review",
                category="Timeline",
                description=description,
                linked_notes=[c.title for c in convs],
                sub_mocs=[],
                key_concepts=concepts[:15],
                content=content,
            )
            mocs.append(moc)

        # Create quarterly MOCs if enough data
        quarterly_groups: dict[str, list[LinkedConversation]] = defaultdict(list)
        for conv in conversations:
            quarter = (conv.created_at.month - 1) // 3 + 1
            quarter_key = f"{conv.created_at.year}-Q{quarter}"
            quarterly_groups[quarter_key].append(conv)

        for quarter_key, convs in sorted(quarterly_groups.items()):
            if len(convs) < self.min_notes_for_moc * 2:
                continue

            year, quarter = quarter_key.split("-")
            quarter_name = f"{quarter} {year}"

            concepts = self._extract_concepts(convs)
            categories = Counter(c.category for c in convs)
            top_categories = [cat for cat, _ in categories.most_common(5)]

            description = (
                f"Quarterly review for {quarter_name}. "
                f"Contains {len(convs)} conversations. "
                f"Primary focus areas: {', '.join(top_categories)}."
            )

            # Link to monthly MOCs
            monthly_moc_titles = []
            for conv in convs:
                month_name = conv.created_at.strftime("%B %Y")
                moc_title = f"{month_name} Review"
                if moc_title not in monthly_moc_titles:
                    monthly_moc_titles.append(moc_title)

            content = self._build_quarterly_moc_content(
                title=f"{quarter_name} Review",
                description=description,
                monthly_mocs=monthly_moc_titles,
                concepts=concepts,
                top_categories=top_categories,
            )

            moc = MOCPage(
                title=f"{quarter_name} Review",
                category="Timeline",
                description=description,
                linked_notes=[c.title for c in convs],
                sub_mocs=monthly_moc_titles,
                key_concepts=concepts[:15],
                content=content,
            )
            mocs.append(moc)

        return mocs

    async def _generate_master_moc(
        self,
        mocs: list[MOCPage],
        conversations: list[LinkedConversation],
    ) -> MOCPage:
        """Generate the master MOC linking all other MOCs.

        Args:
            mocs: List of all generated MOCs.
            conversations: All conversations for statistics.

        Returns:
            Master MOCPage object.
        """
        # Group MOCs by category
        mocs_by_category: dict[str, list[MOCPage]] = defaultdict(list)
        for moc in mocs:
            mocs_by_category[moc.category].append(moc)

        # Get all unique concepts
        all_concepts: list[str] = []
        for moc in mocs:
            all_concepts.extend(moc.key_concepts)
        concept_counts = Counter(all_concepts)
        top_concepts = [c for c, _ in concept_counts.most_common(20)]

        description = (
            f"Master index for the Second Brain knowledge base. "
            f"Contains {len(conversations)} conversations organized into "
            f"{len(mocs)} Maps of Content across {len(mocs_by_category)} categories."
        )

        content = self._build_master_moc_content(
            mocs_by_category=mocs_by_category,
            total_conversations=len(conversations),
            top_concepts=top_concepts,
        )

        return MOCPage(
            title="Second Brain Index",
            category="Index",
            description=description,
            linked_notes=[],
            sub_mocs=[moc.title for moc in mocs],
            key_concepts=top_concepts,
            content=content,
        )

    async def _generate_moc_description(
        self,
        topic: str,
        note_titles: list[str],
        concepts: list[str],
    ) -> str:
        """Generate a compelling MOC description using Claude API.

        Args:
            topic: The topic/category of the MOC.
            note_titles: Titles of notes in this MOC.
            concepts: Key concepts in this MOC.

        Returns:
            Generated description string.
        """
        prompt = f"""Generate a concise, compelling description (2-3 sentences) for a Map of Content page about "{topic}".

This MOC contains notes about:
{chr(10).join(f'- {title}' for title in note_titles[:10])}

Key concepts covered:
{', '.join(concepts[:10])}

The description should:
1. Explain what this topic covers
2. Highlight the value of the collected knowledge
3. Be written in second person (you/your)

Respond with ONLY the description, no other text."""

        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            console.print(f"[yellow]Warning: Could not generate description: {e}[/yellow]")
            return f"A collection of notes and insights about {topic}."

    def _extract_concepts(
        self,
        conversations: list[LinkedConversation],
    ) -> list[str]:
        """Extract and rank concepts from conversations.

        Args:
            conversations: List of conversations to analyze.

        Returns:
            List of concepts sorted by frequency.
        """
        concept_counts: Counter[str] = Counter()
        for conv in conversations:
            concept_counts.update(conv.concepts)
            concept_counts.update(conv.tags)

        return [concept for concept, _ in concept_counts.most_common(50)]

    def _build_moc_content(
        self,
        title: str,
        description: str,
        conversations: list[LinkedConversation],
        concepts: list[str],
    ) -> str:
        """Build markdown content for a MOC page.

        Args:
            title: MOC title.
            description: MOC description.
            conversations: Conversations in this MOC.
            concepts: Key concepts.

        Returns:
            Complete markdown content string.
        """
        lines = [
            f"# {title}",
            "",
            description,
            "",
            "## Overview",
            "",
            f"This Map of Content organizes **{len(conversations)}** related conversations.",
            "",
        ]

        # Key concepts section
        if concepts:
            lines.extend([
                "## Key Concepts",
                "",
            ])
            for concept in concepts[:10]:
                lines.append(f"- [[{concept}]]")
            lines.append("")

        # Notes section grouped by category or date
        lines.extend([
            "## Notes",
            "",
        ])

        # Group by category
        by_category: dict[str, list[LinkedConversation]] = defaultdict(list)
        for conv in conversations:
            by_category[conv.category].append(conv)

        for category, convs in sorted(by_category.items()):
            lines.append(f"### {category}")
            lines.append("")
            for conv in sorted(convs, key=lambda c: c.created_at, reverse=True):
                date_str = conv.created_at.strftime("%Y-%m-%d")
                lines.append(f"- [[{conv.title}]] ({date_str})")
            lines.append("")

        # Related tags
        all_tags = set()
        for conv in conversations:
            all_tags.update(conv.tags)

        if all_tags:
            lines.extend([
                "## Related Tags",
                "",
                " ".join(f"#{tag}" for tag in sorted(all_tags)[:20]),
                "",
            ])

        return "\n".join(lines)

    def _build_temporal_moc_content(
        self,
        title: str,
        description: str,
        conversations: list[LinkedConversation],
        concepts: list[str],
    ) -> str:
        """Build markdown content for a temporal MOC page.

        Args:
            title: MOC title.
            description: MOC description.
            conversations: Conversations in this period.
            concepts: Key concepts.

        Returns:
            Complete markdown content string.
        """
        lines = [
            f"# {title}",
            "",
            description,
            "",
            "## Statistics",
            "",
            f"- **Total Conversations**: {len(conversations)}",
        ]

        # Category breakdown
        categories = Counter(c.category for c in conversations)
        lines.append(f"- **Categories**: {len(categories)}")
        lines.append("")

        # Category breakdown
        lines.extend([
            "## By Category",
            "",
        ])
        for category, count in categories.most_common():
            lines.append(f"- **{category}**: {count} conversations")
        lines.append("")

        # Key concepts
        if concepts:
            lines.extend([
                "## Key Concepts",
                "",
            ])
            for concept in concepts[:10]:
                lines.append(f"- [[{concept}]]")
            lines.append("")

        # Chronological list
        lines.extend([
            "## Conversations",
            "",
        ])
        for conv in sorted(conversations, key=lambda c: c.created_at):
            date_str = conv.created_at.strftime("%Y-%m-%d")
            lines.append(f"- [[{conv.title}]] ({date_str})")
        lines.append("")

        return "\n".join(lines)

    def _build_quarterly_moc_content(
        self,
        title: str,
        description: str,
        monthly_mocs: list[str],
        concepts: list[str],
        top_categories: list[str],
    ) -> str:
        """Build markdown content for a quarterly MOC page.

        Args:
            title: MOC title.
            description: MOC description.
            monthly_mocs: List of monthly MOC titles.
            concepts: Key concepts.
            top_categories: Top category names.

        Returns:
            Complete markdown content string.
        """
        lines = [
            f"# {title}",
            "",
            description,
            "",
            "## Monthly Reviews",
            "",
        ]

        for monthly in monthly_mocs:
            lines.append(f"- [[{monthly}]]")
        lines.append("")

        lines.extend([
            "## Focus Areas",
            "",
        ])
        for category in top_categories:
            lines.append(f"- [[{category} MOC|{category}]]")
        lines.append("")

        if concepts:
            lines.extend([
                "## Key Concepts",
                "",
            ])
            for concept in concepts[:15]:
                lines.append(f"- [[{concept}]]")
            lines.append("")

        return "\n".join(lines)

    def _build_master_moc_content(
        self,
        mocs_by_category: dict[str, list[MOCPage]],
        total_conversations: int,
        top_concepts: list[str],
    ) -> str:
        """Build markdown content for the master MOC page.

        Args:
            mocs_by_category: MOCs grouped by category.
            total_conversations: Total number of conversations.
            top_concepts: Top concepts across all MOCs.

        Returns:
            Complete markdown content string.
        """
        lines = [
            "# Second Brain Index",
            "",
            "Welcome to your Second Brain knowledge base.",
            "",
            "## Quick Stats",
            "",
            f"- **Total Conversations**: {total_conversations}",
            f"- **Maps of Content**: {sum(len(m) for m in mocs_by_category.values())}",
            f"- **Categories**: {len(mocs_by_category)}",
            "",
            "## Browse by Category",
            "",
        ]

        for category, category_mocs in sorted(mocs_by_category.items()):
            lines.append(f"### {category}")
            lines.append("")
            for moc in category_mocs:
                lines.append(f"- [[{moc.title}]]")
            lines.append("")

        lines.extend([
            "## Top Concepts",
            "",
        ])
        for concept in top_concepts[:20]:
            lines.append(f"- [[{concept}]]")
        lines.append("")

        lines.extend([
            "## Getting Started",
            "",
            "1. Browse by category to find topics of interest",
            "2. Use the Timeline MOCs for chronological exploration",
            "3. Follow wikilinks to discover connected ideas",
            "4. Use Obsidian's graph view to visualize connections",
            "",
        ])

        return "\n".join(lines)

    def _display_summary(self, mocs: list[MOCPage]) -> None:
        """Display summary of generated MOCs.

        Args:
            mocs: List of generated MOCs.
        """
        table = Table(title="Generated MOCs", show_header=True)
        table.add_column("Title", style="cyan")
        table.add_column("Category", style="green")
        table.add_column("Notes", style="yellow", justify="right")
        table.add_column("Concepts", style="magenta", justify="right")

        for moc in mocs[:20]:
            table.add_row(
                moc.title[:40],
                moc.category,
                str(len(moc.linked_notes)),
                str(len(moc.key_concepts)),
            )

        if len(mocs) > 20:
            table.add_row("...", "...", "...", "...")
            table.add_row(
                f"[dim]+{len(mocs) - 20} more[/dim]",
                "",
                "",
                "",
            )

        console.print(table)
        console.print(
            f"\n[bold green]Generated {len(mocs)} MOC pages[/bold green]"
        )
