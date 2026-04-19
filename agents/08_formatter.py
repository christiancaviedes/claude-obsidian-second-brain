"""
Formatter Agent for Claude Obsidian Second Brain.

Outputs proper Obsidian markdown with YAML frontmatter,
wikilinks, and proper content formatting.
"""
from __future__ import annotations

import asyncio
import re
from collections import defaultdict
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

from agents.models import LinkedConversation, MOCPage, OutputStats

console = Console()


class FormatterAgent:
    """Agent that formats conversations and MOCs as Obsidian markdown.

    Creates properly formatted markdown files with YAML frontmatter,
    callouts for messages, and wikilinks for relationships.

    Attributes:
        output_path: Base path for output files.
        notes_dir: Directory name for conversation notes.
        mocs_dir: Directory name for MOC pages.
    """

    def __init__(
        self,
        notes_dir: str = "Conversations",
        mocs_dir: str = "MOCs",
        index_dir: str = "000 Index",
    ) -> None:
        """Initialize the Formatter Agent.

        Args:
            notes_dir: Directory name for conversation notes.
            mocs_dir: Directory name for MOC pages.
            index_dir: Directory name for index files.
        """
        self.notes_dir = notes_dir
        self.mocs_dir = mocs_dir
        self.index_dir = index_dir

    async def process(
        self,
        conversations: list[LinkedConversation],
        mocs: list[MOCPage],
        output_path: Path,
    ) -> OutputStats:
        """Format and write all conversations and MOCs to disk.

        Args:
            conversations: List of linked conversations to format.
            mocs: List of MOC pages to write.
            output_path: Base path for output files.

        Returns:
            OutputStats with counts of created files and links.
        """
        console.print(
            Panel(
                "[bold cyan]Formatter Agent[/bold cyan]\n"
                "Creating Obsidian-compatible markdown files",
                border_style="cyan",
            )
        )

        # Create directory structure
        notes_path = output_path / self.notes_dir
        mocs_path = output_path / self.mocs_dir
        index_path = output_path / self.index_dir

        await self._ensure_directories(notes_path, mocs_path, index_path)

        stats = OutputStats(output_path=output_path)
        total_links = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # Write conversation notes
            task1 = progress.add_task(
                "[cyan]Writing conversation notes...",
                total=len(conversations),
            )

            for conv in conversations:
                content, link_count = self._format_conversation(conv, conversations)
                filename = self._sanitize_filename(conv.title) + ".md"
                filepath = notes_path / conv.category / filename

                await self._ensure_directories(notes_path / conv.category)
                await self._write_file(filepath, content)

                stats.notes_created += 1
                total_links += link_count
                progress.update(task1, advance=1)

            # Write MOC pages
            task2 = progress.add_task(
                "[cyan]Writing MOC pages...",
                total=len(mocs),
            )

            for moc in mocs:
                content = self._format_moc(moc)
                filename = self._sanitize_filename(moc.title) + ".md"

                # Special handling for index MOC
                if moc.category == "Index":
                    filepath = index_path / filename
                else:
                    filepath = mocs_path / filename

                await self._write_file(filepath, content)
                stats.mocs_created += 1
                total_links += len(moc.linked_notes) + len(moc.sub_mocs)
                progress.update(task2, advance=1)

        stats.total_links = total_links

        # Display summary
        self._display_summary(stats)

        return stats

    async def _ensure_directories(self, *paths: Path) -> None:
        """Ensure directories exist.

        Args:
            *paths: Paths to create if they don't exist.
        """
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)

    async def _write_file(self, filepath: Path, content: str) -> None:
        """Write content to file asynchronously.

        Args:
            filepath: Path to write to.
            content: Content to write.
        """
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(content)

    def _format_conversation(
        self,
        conversation: LinkedConversation,
        all_conversations: list[LinkedConversation],
    ) -> tuple[str, int]:
        """Format a conversation as Obsidian markdown.

        Args:
            conversation: The conversation to format.
            all_conversations: All conversations for resolving links.

        Returns:
            Tuple of (formatted content, link count).
        """
        link_count = 0

        # Build frontmatter
        frontmatter = self._build_frontmatter(conversation)

        # Build content
        lines = [
            "---",
            frontmatter,
            "---",
            "",
            f"# {conversation.title}",
            "",
        ]

        # Add summary if available
        if conversation.summary:
            lines.extend([
                "## Summary",
                "",
                conversation.summary,
                "",
            ])

        # Add decisions if available
        if conversation.decisions:
            lines.extend([
                "## Decisions",
                "",
            ])
            for decision in conversation.decisions:
                lines.append(f"- {decision}")
            lines.append("")

        # Add action items if available
        if conversation.action_items:
            lines.extend([
                "## Action Items",
                "",
            ])
            for item in conversation.action_items:
                lines.append(f"- [ ] {item}")
            lines.append("")

        # Add conversation content
        lines.extend([
            "## Conversation",
            "",
        ])

        for message in conversation.messages:
            formatted_message = self._format_message(message.role, message.content)
            lines.append(formatted_message)
            lines.append("")

        # Add related notes section
        if conversation.related_conversations:
            lines.extend([
                "## Related Notes",
                "",
            ])
            conv_by_id = {c.id: c for c in all_conversations}
            for related_id in conversation.related_conversations:
                if related_id in conv_by_id:
                    related = conv_by_id[related_id]
                    strength = conversation.link_strength.get(related_id, 0.5)
                    strength_indicator = self._strength_to_indicator(strength)
                    lines.append(f"- [[{related.title}]] {strength_indicator}")
                    link_count += 1
            lines.append("")

        # Add see also section for concepts
        if conversation.concepts:
            lines.extend([
                "## See Also",
                "",
            ])
            for concept in conversation.concepts[:10]:
                lines.append(f"- [[{concept}]]")
                link_count += 1
            lines.append("")

        # Add tags section
        if conversation.tags:
            lines.extend([
                "## Tags",
                "",
                " ".join(f"#{tag}" for tag in conversation.tags),
                "",
            ])

        return "\n".join(lines), link_count

    def _build_frontmatter(self, conversation: LinkedConversation) -> str:
        """Build YAML frontmatter for a conversation.

        Args:
            conversation: The conversation to build frontmatter for.

        Returns:
            YAML frontmatter string (without delimiters).
        """
        lines = [
            f"title: \"{self._escape_yaml_string(conversation.title)}\"",
            f"date: {conversation.created_at.strftime('%Y-%m-%d')}",
            f"created: {conversation.created_at.isoformat()}",
            f"category: {conversation.category}",
        ]

        # Tags as list
        if conversation.tags:
            lines.append("tags:")
            for tag in conversation.tags:
                lines.append(f"  - {tag}")

        # Decisions as list
        if conversation.decisions:
            lines.append("decisions:")
            for decision in conversation.decisions:
                lines.append(f"  - \"{self._escape_yaml_string(decision)}\"")

        # Action items as list
        if conversation.action_items:
            lines.append("action_items:")
            for item in conversation.action_items:
                lines.append(f"  - \"{self._escape_yaml_string(item)}\"")

        # Related notes
        if conversation.related_conversations:
            lines.append("related:")
            for related_id in conversation.related_conversations:
                lines.append(f"  - \"{related_id}\"")

        # Source URL
        if conversation.source_url:
            lines.append(f"source_url: \"{conversation.source_url}\"")

        # Concepts
        if conversation.concepts:
            lines.append("concepts:")
            for concept in conversation.concepts[:10]:
                lines.append(f"  - {concept}")

        return "\n".join(lines)

    def _format_message(self, role: str, content: str) -> str:
        """Format a message as an Obsidian callout.

        Args:
            role: The role of the message sender.
            content: The message content.

        Returns:
            Formatted callout string.
        """
        if role == "human":
            callout_type = "question"
            title = "Human"
            icon = "user"
        else:
            callout_type = "info"
            title = "Assistant"
            icon = "bot"

        # Preserve code blocks
        content = self._preserve_code_blocks(content)

        # Indent content for callout
        indented_lines = []
        for line in content.split("\n"):
            indented_lines.append(f"> {line}" if line else ">")

        callout_header = f"> [!{callout_type}]+ {title}"
        return callout_header + "\n" + "\n".join(indented_lines)

    def _preserve_code_blocks(self, content: str) -> str:
        """Preserve code blocks in content.

        Args:
            content: Content that may contain code blocks.

        Returns:
            Content with code blocks preserved.
        """
        # Code blocks are already properly formatted in markdown
        # Just ensure they're not mangled by other processing
        return content

    def _format_moc(self, moc: MOCPage) -> str:
        """Format a MOC page as Obsidian markdown.

        Args:
            moc: The MOC page to format.

        Returns:
            Formatted markdown string.
        """
        # Build frontmatter
        frontmatter_lines = [
            f"title: \"{self._escape_yaml_string(moc.title)}\"",
            f"type: moc",
            f"category: {moc.category}",
        ]

        if moc.key_concepts:
            frontmatter_lines.append("key_concepts:")
            for concept in moc.key_concepts[:10]:
                frontmatter_lines.append(f"  - {concept}")

        if moc.sub_mocs:
            frontmatter_lines.append("sub_mocs:")
            for sub_moc in moc.sub_mocs:
                frontmatter_lines.append(f"  - \"{self._escape_yaml_string(sub_moc)}\"")

        frontmatter = "\n".join(frontmatter_lines)

        lines = [
            "---",
            frontmatter,
            "---",
            "",
            moc.content,
        ]

        return "\n".join(lines)

    def _sanitize_filename(self, title: str) -> str:
        """Sanitize a title for use as a filename.

        Args:
            title: The title to sanitize.

        Returns:
            Sanitized filename (without extension).
        """
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        sanitized = title
        for char in invalid_chars:
            sanitized = sanitized.replace(char, "-")

        # Remove leading/trailing whitespace and dots
        sanitized = sanitized.strip(". ")

        # Truncate if too long
        if len(sanitized) > 200:
            sanitized = sanitized[:200].rsplit(" ", 1)[0]

        # Ensure not empty
        if not sanitized:
            sanitized = "Untitled"

        return sanitized

    def _escape_yaml_string(self, value: str) -> str:
        """Escape a string for use in YAML.

        Args:
            value: The string to escape.

        Returns:
            Escaped string.
        """
        # Escape backslashes and quotes
        value = value.replace("\\", "\\\\")
        value = value.replace('"', '\\"')
        # Remove newlines
        value = value.replace("\n", " ").replace("\r", "")
        return value

    def _strength_to_indicator(self, strength: float) -> str:
        """Convert link strength to a visual indicator.

        Args:
            strength: Link strength from 0.0 to 1.0.

        Returns:
            Visual indicator string.
        """
        if strength >= 0.8:
            return "(strong)"
        elif strength >= 0.5:
            return "(moderate)"
        else:
            return "(weak)"

    def _display_summary(self, stats: OutputStats) -> None:
        """Display summary of formatting results.

        Args:
            stats: Output statistics.
        """
        table = Table(title="Formatting Summary", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Notes Created", str(stats.notes_created))
        table.add_row("MOCs Created", str(stats.mocs_created))
        table.add_row("Total Links", str(stats.total_links))
        table.add_row("Output Path", str(stats.output_path))

        console.print(table)
        console.print(
            f"\n[bold green]Successfully wrote {stats.notes_created + stats.mocs_created} files[/bold green]"
        )
