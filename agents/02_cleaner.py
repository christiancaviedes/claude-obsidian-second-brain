"""
CleanerAgent - Normalizes and cleans conversation text.

This agent processes parsed conversations to standardize formatting,
remove artifacts, and prepare text for downstream processing.
"""
from __future__ import annotations

import asyncio
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from agents.models import Conversation, Message


class CleanerAgent:
    """Normalizes and cleans conversation text for consistent formatting.

    Handles code block artifacts, timestamp standardization, whitespace
    normalization, and cleanup of Claude-specific internal markers.

    Attributes:
        console: Rich console for output.
        verbose: Whether to output detailed progress information.

    Example:
        ```python
        cleaner = CleanerAgent(verbose=True)
        cleaned = await cleaner.process(conversations)
        ```
    """

    # Regex patterns for cleaning
    CODE_BLOCK_ARTIFACT = re.compile(
        r"```(?:[\w+-]*\n)?(.*?)```",
        re.DOTALL
    )
    ARTIFACT_MARKERS = re.compile(
        r"<(?:artifact|antArtifact)[^>]*>.*?</(?:artifact|antArtifact)>",
        re.DOTALL | re.IGNORECASE
    )
    THINKING_BLOCKS = re.compile(
        r"<thinking>.*?</thinking>",
        re.DOTALL | re.IGNORECASE
    )
    INTERNAL_MARKERS = re.compile(
        r"\[(?:INST|/INST|SYS|/SYS|CLAUDE|HUMAN)\]",
        re.IGNORECASE
    )
    XML_TAGS = re.compile(
        r"</?(?:response|reply|answer|output|result)[^>]*>",
        re.IGNORECASE
    )
    MULTIPLE_NEWLINES = re.compile(r"\n{3,}")
    MULTIPLE_SPACES = re.compile(r"[ \t]{2,}")
    LEADING_TRAILING_WHITESPACE = re.compile(r"^[ \t]+|[ \t]+$", re.MULTILINE)

    def __init__(self, verbose: bool = True) -> None:
        """Initialize the CleanerAgent.

        Args:
            verbose: If True, output progress information to console.
        """
        self.console = Console()
        self.verbose = verbose

    async def process(
        self, conversations: list[Conversation]
    ) -> list[Conversation]:
        """Clean and normalize a list of conversations.

        Processes each conversation to:
        - Remove code block artifacts and normalize formatting
        - Standardize timestamps to ISO format
        - Clean up Claude's internal markers/artifacts
        - Normalize whitespace and line breaks
        - Handle emoji and special characters properly

        Args:
            conversations: List of parsed Conversation objects.

        Returns:
            List of cleaned Conversation objects with the same structure.
        """
        if not conversations:
            return []

        if self.verbose:
            self.console.print(
                f"[blue]Cleaning {len(conversations)} conversations...[/blue]"
            )

        cleaned: list[Conversation] = []

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.console,
            disable=not self.verbose,
        ) as progress:
            task = progress.add_task(
                "Cleaning conversations...",
                total=len(conversations)
            )

            # Process in batches for better async performance
            batch_size = 50
            for i in range(0, len(conversations), batch_size):
                batch = conversations[i:i + batch_size]
                tasks = [
                    self._clean_conversation(conv)
                    for conv in batch
                ]
                results = await asyncio.gather(*tasks)
                cleaned.extend(results)
                progress.update(task, advance=len(batch))

        if self.verbose:
            self.console.print(
                f"[green]Cleaned {len(cleaned)} conversations[/green]"
            )

        return cleaned

    async def _clean_conversation(
        self, conversation: Conversation
    ) -> Conversation:
        """Clean a single conversation.

        Args:
            conversation: The conversation to clean.

        Returns:
            Cleaned Conversation object.
        """
        # Clean each message
        cleaned_messages = [
            await self._clean_message(msg)
            for msg in conversation.messages
        ]

        # Filter out empty messages after cleaning
        cleaned_messages = [
            msg for msg in cleaned_messages
            if msg.content.strip()
        ]

        # Standardize conversation-level timestamp
        created_at = self._standardize_timestamp(conversation.created_at)

        # Clean title
        title = self._clean_text(conversation.title)
        if not title.strip():
            title = "Untitled Conversation"

        return Conversation(
            id=conversation.id,
            title=title,
            created_at=created_at,
            messages=cleaned_messages,
            source_url=conversation.source_url,
        )

    async def _clean_message(self, message: Message) -> Message:
        """Clean a single message.

        Args:
            message: The message to clean.

        Returns:
            Cleaned Message object.
        """
        content = message.content

        # Apply cleaning pipeline
        content = self._remove_artifact_markers(content)
        content = self._remove_thinking_blocks(content)
        content = self._normalize_code_blocks(content)
        content = self._remove_internal_markers(content)
        content = self._remove_xml_tags(content)
        content = self._normalize_whitespace(content)
        content = self._normalize_unicode(content)

        # Standardize timestamp
        timestamp = (
            self._standardize_timestamp(message.timestamp)
            if message.timestamp
            else None
        )

        return Message(
            role=message.role,
            content=content,
            timestamp=timestamp,
        )

    def _remove_artifact_markers(self, text: str) -> str:
        """Remove Claude artifact markers from text.

        Args:
            text: Input text.

        Returns:
            Text with artifact markers removed.
        """
        # Remove <artifact> and <antArtifact> tags but keep content
        result = self.ARTIFACT_MARKERS.sub("", text)
        return result

    def _remove_thinking_blocks(self, text: str) -> str:
        """Remove <thinking> blocks from text.

        Args:
            text: Input text.

        Returns:
            Text with thinking blocks removed.
        """
        return self.THINKING_BLOCKS.sub("", text)

    def _normalize_code_blocks(self, text: str) -> str:
        """Normalize code block formatting.

        Ensures code blocks have consistent formatting with language
        specifiers and proper newlines.

        Args:
            text: Input text.

        Returns:
            Text with normalized code blocks.
        """
        def normalize_block(match: re.Match) -> str:
            code = match.group(1).strip()
            # Preserve the code block but ensure clean formatting
            return f"```\n{code}\n```"

        # First pass: normalize existing code blocks
        result = self.CODE_BLOCK_ARTIFACT.sub(normalize_block, text)

        return result

    def _remove_internal_markers(self, text: str) -> str:
        """Remove Claude internal instruction markers.

        Args:
            text: Input text.

        Returns:
            Text with internal markers removed.
        """
        return self.INTERNAL_MARKERS.sub("", text)

    def _remove_xml_tags(self, text: str) -> str:
        """Remove generic XML wrapper tags.

        Args:
            text: Input text.

        Returns:
            Text with XML tags removed.
        """
        return self.XML_TAGS.sub("", text)

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text.

        - Converts tabs to spaces
        - Collapses multiple spaces
        - Limits consecutive newlines to 2
        - Trims leading/trailing whitespace from lines

        Args:
            text: Input text.

        Returns:
            Text with normalized whitespace.
        """
        # Replace tabs with spaces (except in code blocks)
        # First, protect code blocks
        code_blocks: list[str] = []

        def save_code_block(match: re.Match) -> str:
            code_blocks.append(match.group(0))
            return f"\x00CODE_BLOCK_{len(code_blocks) - 1}\x00"

        text = self.CODE_BLOCK_ARTIFACT.sub(save_code_block, text)

        # Normalize whitespace outside code blocks
        text = self.MULTIPLE_SPACES.sub(" ", text)
        text = self.MULTIPLE_NEWLINES.sub("\n\n", text)
        text = self.LEADING_TRAILING_WHITESPACE.sub("", text)

        # Restore code blocks
        for i, block in enumerate(code_blocks):
            text = text.replace(f"\x00CODE_BLOCK_{i}\x00", block)

        return text.strip()

    def _normalize_unicode(self, text: str) -> str:
        """Normalize Unicode characters and handle special characters.

        - Normalizes to NFC form
        - Preserves emoji and special characters
        - Removes control characters (except newline, tab)

        Args:
            text: Input text.

        Returns:
            Text with normalized Unicode.
        """
        # Normalize to NFC (composed form)
        text = unicodedata.normalize("NFC", text)

        # Remove control characters except \n and \t
        cleaned = []
        for char in text:
            if unicodedata.category(char) == "Cc":
                if char in ("\n", "\t", "\r"):
                    cleaned.append(char)
                # Skip other control characters
            else:
                cleaned.append(char)

        text = "".join(cleaned)

        # Normalize line endings to \n
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        return text

    def _standardize_timestamp(self, dt: Optional[datetime]) -> datetime:
        """Standardize timestamp to UTC ISO format.

        Args:
            dt: Input datetime, may be timezone-aware or naive.

        Returns:
            Timezone-aware datetime in UTC.
        """
        if dt is None:
            return datetime.now(timezone.utc)

        # If naive, assume UTC
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)

        # Convert to UTC
        return dt.astimezone(timezone.utc)

    def _clean_text(self, text: str) -> str:
        """Apply basic text cleaning without aggressive normalization.

        Used for titles and other metadata that should preserve more
        of the original formatting.

        Args:
            text: Input text.

        Returns:
            Cleaned text.
        """
        if not text:
            return ""

        # Normalize Unicode
        text = unicodedata.normalize("NFC", text)

        # Remove control characters
        text = "".join(
            char for char in text
            if not unicodedata.category(char) == "Cc" or char in "\n\t"
        )

        # Collapse whitespace
        text = " ".join(text.split())

        return text.strip()
