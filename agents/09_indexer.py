"""
Indexer Agent for Claude Obsidian Second Brain.

Creates master index files and topic analysis for the Obsidian vault.
"""
from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles
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


class IndexerAgent:
    """Agent that creates master index and topic analysis files.

    Generates comprehensive index files for navigating the vault,
    including topic analysis, timeline views, and statistics.

    Attributes:
        index_dir: Directory name for index files.
    """

    def __init__(self, index_dir: str = "000 Index") -> None:
        """Initialize the Indexer Agent.

        Args:
            index_dir: Directory name for index files.
        """
        self.index_dir = index_dir

    async def process(
        self,
        conversations: list[LinkedConversation],
        mocs: list[MOCPage],
        graph: KnowledgeGraph,
        output_path: Path,
    ) -> None:
        """Generate all index files for the vault.

        Creates:
        - README.md - Master vault index
        - Topics MOC.md - All topics with counts
        - Timeline.md - Chronological view
        - Clusters.md - Knowledge cluster visualization
        - Statistics.md - Vault statistics

        Args:
            conversations: List of linked conversations.
            mocs: List of MOC pages.
            graph: Knowledge graph.
            output_path: Base output path.
        """
        console.print(
            Panel(
                "[bold cyan]Indexer Agent[/bold cyan]\n"
                "Creating master index and analysis files",
                border_style="cyan",
            )
        )

        index_path = output_path / self.index_dir
        index_path.mkdir(parents=True, exist_ok=True)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "[cyan]Generating index files...",
                total=5,
            )

            # Generate README (master index)
            readme_content = self._generate_readme(conversations, mocs, graph)
            await self._write_file(index_path / "README.md", readme_content)
            progress.update(task, advance=1)

            # Generate Topics MOC
            topics_content = self._generate_topics_moc(conversations, graph)
            await self._write_file(index_path / "Topics MOC.md", topics_content)
            progress.update(task, advance=1)

            # Generate Timeline
            timeline_content = self._generate_timeline(conversations)
            await self._write_file(index_path / "Timeline.md", timeline_content)
            progress.update(task, advance=1)

            # Generate Clusters
            clusters_content = self._generate_clusters(conversations, graph)
            await self._write_file(index_path / "Clusters.md", clusters_content)
            progress.update(task, advance=1)

            # Generate Statistics
            stats_content = self._generate_statistics(conversations, mocs, graph)
            await self._write_file(index_path / "Statistics.md", stats_content)
            progress.update(task, advance=1)

        # Display final statistics
        self._display_final_stats(conversations, mocs, graph)

    async def _write_file(self, filepath: Path, content: str) -> None:
        """Write content to file asynchronously.

        Args:
            filepath: Path to write to.
            content: Content to write.
        """
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(content)

    def _generate_readme(
        self,
        conversations: list[LinkedConversation],
        mocs: list[MOCPage],
        graph: KnowledgeGraph,
    ) -> str:
        """Generate the master vault index README.

        Args:
            conversations: All conversations.
            mocs: All MOC pages.
            graph: Knowledge graph.

        Returns:
            README markdown content.
        """
        # Calculate statistics
        date_range = self._get_date_range(conversations)
        categories = Counter(c.category for c in conversations)
        total_concepts = len([n for n in graph.nodes.values() if n.node_type == "concept"])

        lines = [
            "# Second Brain Vault Index",
            "",
            "Welcome to your Claude conversation archive, transformed into a connected knowledge base.",
            "",
            "## Quick Stats",
            "",
            f"- **Total Conversations**: {len(conversations)}",
            f"- **Maps of Content**: {len(mocs)}",
            f"- **Categories**: {len(categories)}",
            f"- **Concepts Extracted**: {total_concepts}",
            f"- **Date Range**: {date_range}",
            "",
            "## Navigation",
            "",
            "### By Category",
            "",
        ]

        for category, count in categories.most_common():
            lines.append(f"- [[{category} MOC|{category}]] ({count} conversations)")
        lines.append("")

        lines.extend([
            "### Index Files",
            "",
            "- [[Topics MOC]] - Browse all topics with frequency counts",
            "- [[Timeline]] - Chronological view of all conversations",
            "- [[Clusters]] - Visual representation of knowledge clusters",
            "- [[Statistics]] - Detailed vault statistics and analysis",
            "",
            "## Recent Conversations",
            "",
        ])

        # Show 10 most recent
        recent = sorted(conversations, key=lambda c: c.created_at, reverse=True)[:10]
        for conv in recent:
            date_str = conv.created_at.strftime("%Y-%m-%d")
            lines.append(f"- [[{conv.title}]] ({date_str})")
        lines.append("")

        lines.extend([
            "## Top Concepts",
            "",
        ])

        # Get top concepts by connection count
        concept_degrees: list[tuple[str, int]] = []
        for node_id, node in graph.nodes.items():
            if node.node_type == "concept":
                degree = graph.get_node_degree(node_id)
                concept_degrees.append((node.label, degree))
        concept_degrees.sort(key=lambda x: x[1], reverse=True)

        for concept, degree in concept_degrees[:15]:
            lines.append(f"- [[{concept}]] ({degree} connections)")
        lines.append("")

        lines.extend([
            "---",
            "",
            "*Generated by Claude Obsidian Second Brain*",
            "",
        ])

        return "\n".join(lines)

    def _generate_topics_moc(
        self,
        conversations: list[LinkedConversation],
        graph: KnowledgeGraph,
    ) -> str:
        """Generate the Topics MOC with all topics and counts.

        Args:
            conversations: All conversations.
            graph: Knowledge graph.

        Returns:
            Topics MOC markdown content.
        """
        lines = [
            "# Topics MOC",
            "",
            "All topics and concepts extracted from conversations, organized by frequency.",
            "",
            "## Topics by Frequency",
            "",
        ]

        # Count topic/concept occurrences
        topic_counts: Counter[str] = Counter()
        for conv in conversations:
            topic_counts.update(conv.concepts)
            topic_counts.update(conv.tags)

        # Group by frequency ranges
        high_freq = [(t, c) for t, c in topic_counts.most_common() if c >= 10]
        med_freq = [(t, c) for t, c in topic_counts.most_common() if 5 <= c < 10]
        low_freq = [(t, c) for t, c in topic_counts.most_common() if 2 <= c < 5]
        rare = [(t, c) for t, c in topic_counts.most_common() if c == 1]

        if high_freq:
            lines.extend([
                "### High Frequency (10+ mentions)",
                "",
            ])
            for topic, count in high_freq:
                lines.append(f"- [[{topic}]] ({count})")
            lines.append("")

        if med_freq:
            lines.extend([
                "### Medium Frequency (5-9 mentions)",
                "",
            ])
            for topic, count in med_freq:
                lines.append(f"- [[{topic}]] ({count})")
            lines.append("")

        if low_freq:
            lines.extend([
                "### Low Frequency (2-4 mentions)",
                "",
            ])
            for topic, count in low_freq[:50]:  # Limit to 50
                lines.append(f"- [[{topic}]] ({count})")
            if len(low_freq) > 50:
                lines.append(f"- *... and {len(low_freq) - 50} more*")
            lines.append("")

        if rare:
            lines.extend([
                "### Single Mentions",
                "",
                f"*{len(rare)} topics mentioned only once*",
                "",
            ])
            # Just list first 20
            for topic, count in rare[:20]:
                lines.append(f"- [[{topic}]]")
            if len(rare) > 20:
                lines.append(f"- *... and {len(rare) - 20} more*")
            lines.append("")

        # Tag usage section
        lines.extend([
            "## Tag Usage",
            "",
        ])

        tag_counts: Counter[str] = Counter()
        for conv in conversations:
            tag_counts.update(conv.tags)

        for tag, count in tag_counts.most_common(30):
            lines.append(f"- #{tag} ({count})")
        lines.append("")

        return "\n".join(lines)

    def _generate_timeline(
        self,
        conversations: list[LinkedConversation],
    ) -> str:
        """Generate chronological timeline view.

        Args:
            conversations: All conversations.

        Returns:
            Timeline markdown content.
        """
        lines = [
            "# Timeline",
            "",
            "Chronological view of all conversations.",
            "",
        ]

        # Group by year and month
        by_year_month: dict[str, dict[str, list[LinkedConversation]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for conv in conversations:
            year = str(conv.created_at.year)
            month = conv.created_at.strftime("%B")
            by_year_month[year][month].append(conv)

        # Sort years descending
        for year in sorted(by_year_month.keys(), reverse=True):
            lines.append(f"## {year}")
            lines.append("")

            months = by_year_month[year]
            # Sort months by date
            month_order = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]

            for month in reversed(month_order):
                if month not in months:
                    continue

                convs = months[month]
                lines.append(f"### {month} ({len(convs)} conversations)")
                lines.append("")

                # Sort by date descending
                for conv in sorted(convs, key=lambda c: c.created_at, reverse=True):
                    date_str = conv.created_at.strftime("%Y-%m-%d")
                    lines.append(f"- {date_str}: [[{conv.title}]]")
                lines.append("")

        return "\n".join(lines)

    def _generate_clusters(
        self,
        conversations: list[LinkedConversation],
        graph: KnowledgeGraph,
    ) -> str:
        """Generate knowledge cluster visualization.

        Args:
            conversations: All conversations.
            graph: Knowledge graph with clusters.

        Returns:
            Clusters markdown content.
        """
        lines = [
            "# Knowledge Clusters",
            "",
            "Visual representation of how topics and conversations cluster together.",
            "",
            "## Cluster Overview",
            "",
        ]

        # Use graph clusters if available
        if graph.clusters:
            for cluster_id, node_ids in graph.clusters.items():
                lines.append(f"### Cluster: {cluster_id}")
                lines.append("")
                for node_id in node_ids[:20]:
                    if node_id in graph.nodes:
                        node = graph.nodes[node_id]
                        lines.append(f"- [[{node.label}]] ({node.node_type})")
                if len(node_ids) > 20:
                    lines.append(f"- *... and {len(node_ids) - 20} more*")
                lines.append("")
        else:
            # Generate clusters from categories
            lines.append("*Clusters generated from category groupings*")
            lines.append("")

            by_category: dict[str, list[LinkedConversation]] = defaultdict(list)
            for conv in conversations:
                by_category[conv.category].append(conv)

            for category, convs in sorted(by_category.items(), key=lambda x: -len(x[1])):
                # Get top concepts for this category
                concepts: Counter[str] = Counter()
                for conv in convs:
                    concepts.update(conv.concepts)

                lines.append(f"### {category} Cluster")
                lines.append("")
                lines.append(f"**{len(convs)} conversations**")
                lines.append("")

                # ASCII visualization
                cluster_ascii = self._generate_cluster_ascii(category, concepts.most_common(10))
                lines.append("```")
                lines.extend(cluster_ascii)
                lines.append("```")
                lines.append("")

                # List top concepts
                lines.append("**Top concepts:**")
                for concept, count in concepts.most_common(10):
                    lines.append(f"- [[{concept}]] ({count})")
                lines.append("")

        return "\n".join(lines)

    def _generate_cluster_ascii(
        self,
        center: str,
        connections: list[tuple[str, int]],
    ) -> list[str]:
        """Generate ASCII visualization of a cluster.

        Args:
            center: Center node label.
            connections: List of (label, weight) tuples for connected nodes.

        Returns:
            List of ASCII art lines.
        """
        if not connections:
            return [f"  [{center}]"]

        lines = []
        center_padded = f"[{center}]"
        center_len = len(center_padded)

        # Top connections
        top_conns = connections[:3]
        top_labels = [f"({c[0][:15]})" for c in top_conns]

        if top_labels:
            # Top row
            top_line = "    ".join(top_labels)
            padding = " " * max(0, (center_len - len(top_line)) // 2 + 10)
            lines.append(padding + top_line)

            # Connectors
            connector_line = "      \\".ljust(15) + "|".center(10) + "/".rjust(5)
            lines.append(connector_line)

        # Center
        lines.append(" " * 10 + center_padded)

        # Bottom connectors
        if len(connections) > 3:
            bottom_conns = connections[3:6]
            connector_line = "      /".ljust(15) + "|".center(10) + "\\".rjust(5)
            lines.append(connector_line)

            bottom_labels = [f"({c[0][:15]})" for c in bottom_conns]
            bottom_line = "    ".join(bottom_labels)
            padding = " " * max(0, (center_len - len(bottom_line)) // 2 + 10)
            lines.append(padding + bottom_line)

        return lines

    def _generate_statistics(
        self,
        conversations: list[LinkedConversation],
        mocs: list[MOCPage],
        graph: KnowledgeGraph,
    ) -> str:
        """Generate comprehensive vault statistics.

        Args:
            conversations: All conversations.
            mocs: All MOC pages.
            graph: Knowledge graph.

        Returns:
            Statistics markdown content.
        """
        lines = [
            "# Vault Statistics",
            "",
            "Comprehensive statistics and analysis of the knowledge base.",
            "",
            "## Overview",
            "",
        ]

        # Basic stats
        date_range = self._get_date_range(conversations)
        total_messages = sum(len(c.messages) for c in conversations)
        avg_messages = total_messages / len(conversations) if conversations else 0

        lines.extend([
            f"- **Total Conversations**: {len(conversations)}",
            f"- **Total Messages**: {total_messages}",
            f"- **Average Messages per Conversation**: {avg_messages:.1f}",
            f"- **Date Range**: {date_range}",
            f"- **Maps of Content**: {len(mocs)}",
            f"- **Graph Nodes**: {len(graph.nodes)}",
            f"- **Graph Edges**: {len(graph.edges)}",
            "",
        ])

        # Category distribution
        lines.extend([
            "## Category Distribution",
            "",
        ])

        categories = Counter(c.category for c in conversations)
        max_count = max(categories.values()) if categories else 1

        for category, count in categories.most_common():
            bar_len = int((count / max_count) * 30)
            bar = "#" * bar_len
            lines.append(f"- **{category}**: {count} {bar}")
        lines.append("")

        # Most active periods
        lines.extend([
            "## Most Active Periods",
            "",
        ])

        monthly_counts: Counter[str] = Counter()
        for conv in conversations:
            month_key = conv.created_at.strftime("%Y-%m")
            monthly_counts[month_key] += 1

        lines.append("### Top Months")
        lines.append("")
        for month, count in monthly_counts.most_common(10):
            date_obj = datetime.strptime(month, "%Y-%m")
            month_name = date_obj.strftime("%B %Y")
            lines.append(f"- **{month_name}**: {count} conversations")
        lines.append("")

        # Day of week distribution
        day_counts: Counter[str] = Counter()
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for conv in conversations:
            day_name = day_names[conv.created_at.weekday()]
            day_counts[day_name] += 1

        lines.extend([
            "### Activity by Day of Week",
            "",
        ])
        for day in day_names:
            count = day_counts[day]
            bar_len = int((count / max(day_counts.values())) * 20) if day_counts else 0
            bar = "#" * bar_len
            lines.append(f"- **{day}**: {count} {bar}")
        lines.append("")

        # Top concepts
        lines.extend([
            "## Top Concepts",
            "",
        ])

        concept_counts: Counter[str] = Counter()
        for conv in conversations:
            concept_counts.update(conv.concepts)

        for concept, count in concept_counts.most_common(20):
            lines.append(f"- **{concept}**: {count} mentions")
        lines.append("")

        # Top tags
        lines.extend([
            "## Top Tags",
            "",
        ])

        tag_counts: Counter[str] = Counter()
        for conv in conversations:
            tag_counts.update(conv.tags)

        for tag, count in tag_counts.most_common(20):
            lines.append(f"- #{tag}: {count}")
        lines.append("")

        # Graph statistics
        lines.extend([
            "## Knowledge Graph Statistics",
            "",
        ])

        node_types: Counter[str] = Counter()
        for node in graph.nodes.values():
            node_types[node.node_type] += 1

        lines.append("### Node Types")
        lines.append("")
        for node_type, count in node_types.most_common():
            lines.append(f"- **{node_type}**: {count}")
        lines.append("")

        # Most connected nodes
        node_degrees: list[tuple[str, str, int]] = []
        for node_id, node in graph.nodes.items():
            degree = graph.get_node_degree(node_id)
            node_degrees.append((node.label, node.node_type, degree))
        node_degrees.sort(key=lambda x: x[2], reverse=True)

        lines.extend([
            "### Most Connected Nodes",
            "",
        ])
        for label, node_type, degree in node_degrees[:15]:
            lines.append(f"- **{label}** ({node_type}): {degree} connections")
        lines.append("")

        lines.extend([
            "---",
            "",
            f"*Statistics generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
        ])

        return "\n".join(lines)

    def _get_date_range(self, conversations: list[LinkedConversation]) -> str:
        """Get the date range string for conversations.

        Args:
            conversations: List of conversations.

        Returns:
            Formatted date range string.
        """
        if not conversations:
            return "N/A"

        dates = [c.created_at for c in conversations]
        min_date = min(dates).strftime("%Y-%m-%d")
        max_date = max(dates).strftime("%Y-%m-%d")

        return f"{min_date} to {max_date}"

    def _display_final_stats(
        self,
        conversations: list[LinkedConversation],
        mocs: list[MOCPage],
        graph: KnowledgeGraph,
    ) -> None:
        """Display final statistics to console.

        Args:
            conversations: All conversations.
            mocs: All MOC pages.
            graph: Knowledge graph.
        """
        table = Table(title="Vault Statistics", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        # Basic counts
        table.add_row("Total Conversations", str(len(conversations)))
        table.add_row("Total MOCs", str(len(mocs)))
        table.add_row("Graph Nodes", str(len(graph.nodes)))
        table.add_row("Graph Edges", str(len(graph.edges)))

        # Date range
        date_range = self._get_date_range(conversations)
        table.add_row("Date Range", date_range)

        # Categories
        categories = set(c.category for c in conversations)
        table.add_row("Categories", str(len(categories)))

        # Concepts
        all_concepts = set()
        for conv in conversations:
            all_concepts.update(conv.concepts)
        table.add_row("Unique Concepts", str(len(all_concepts)))

        # Tags
        all_tags = set()
        for conv in conversations:
            all_tags.update(conv.tags)
        table.add_row("Unique Tags", str(len(all_tags)))

        console.print(table)

        # Most active category
        if conversations:
            categories_count = Counter(c.category for c in conversations)
            top_category, top_count = categories_count.most_common(1)[0]
            console.print(
                f"\n[bold]Most Active Category:[/bold] {top_category} ({top_count} conversations)"
            )

        console.print(
            "\n[bold green]Index files generated successfully![/bold green]"
        )
