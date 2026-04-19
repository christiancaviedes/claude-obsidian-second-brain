"""
ParserAgent - Parses Claude JSON/HTML export formats.

This agent handles the initial parsing of Claude conversation exports,
supporting both JSON and HTML formats.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiofiles
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from agents.models import Conversation, Message


class ParserAgent:
    """Parses Claude export files into structured Conversation objects.

    Supports both JSON export format (conversations array with messages)
    and HTML export format (parsed using BeautifulSoup).

    Attributes:
        console: Rich console for output.
        verbose: Whether to output detailed progress information.

    Example:
        ```python
        parser = ParserAgent(verbose=True)
        conversations = await parser.process(Path("export.json"))
        ```
    """

    def __init__(self, verbose: bool = True) -> None:
        """Initialize the ParserAgent.

        Args:
            verbose: If True, output progress information to console.
        """
        self.console = Console()
        self.verbose = verbose

    async def process(self, input_path: Path) -> list[Conversation]:
        """Parse a Claude export file into Conversation objects.

        Automatically detects the file format (JSON or HTML) based on
        extension and content, then delegates to the appropriate parser.

        Args:
            input_path: Path to the export file (JSON or HTML).

        Returns:
            List of parsed Conversation objects.

        Raises:
            FileNotFoundError: If the input file doesn't exist.
            ValueError: If the file format is unsupported or malformed.
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Export file not found: {input_path}")

        if self.verbose:
            self.console.print(f"[blue]Parsing:[/blue] {input_path.name}")

        suffix = input_path.suffix.lower()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            disable=not self.verbose,
        ) as progress:
            task = progress.add_task("Reading file...", total=None)

            async with aiofiles.open(input_path, "r", encoding="utf-8") as f:
                content = await f.read()

            progress.update(task, description="Detecting format...")

            if suffix == ".json" or self._looks_like_json(content):
                progress.update(task, description="Parsing JSON format...")
                conversations = await self._parse_json(content, input_path)
            elif suffix in (".html", ".htm") or self._looks_like_html(content):
                progress.update(task, description="Parsing HTML format...")
                conversations = await self._parse_html(content, input_path)
            else:
                raise ValueError(
                    f"Unsupported file format: {suffix}. "
                    "Expected .json or .html"
                )

            progress.update(task, description="Done!")

        if self.verbose:
            self.console.print(
                f"[green]Parsed {len(conversations)} conversations[/green]"
            )

        return conversations

    def _looks_like_json(self, content: str) -> bool:
        """Check if content appears to be JSON."""
        stripped = content.strip()
        return stripped.startswith("{") or stripped.startswith("[")

    def _looks_like_html(self, content: str) -> bool:
        """Check if content appears to be HTML."""
        stripped = content.strip().lower()
        return stripped.startswith("<!doctype") or stripped.startswith("<html")

    async def _parse_json(
        self, content: str, source_path: Path
    ) -> list[Conversation]:
        """Parse Claude JSON export format.

        Handles the standard Claude export format with a conversations array,
        where each conversation contains messages with roles and content.

        Args:
            content: Raw JSON content.
            source_path: Source file path for error reporting.

        Returns:
            List of parsed Conversation objects.

        Raises:
            ValueError: If the JSON is malformed or has unexpected structure.
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON in {source_path}: {e}")

        conversations: list[Conversation] = []

        # Handle different JSON structures
        if isinstance(data, list):
            # Array of conversations
            raw_conversations = data
        elif isinstance(data, dict):
            # Object with conversations array
            raw_conversations = data.get("conversations", data.get("data", [data]))
            if not isinstance(raw_conversations, list):
                raw_conversations = [raw_conversations]
        else:
            raise ValueError(f"Unexpected JSON structure in {source_path}")

        for idx, conv_data in enumerate(raw_conversations):
            try:
                conversation = self._parse_json_conversation(conv_data, idx)
                conversations.append(conversation)
            except Exception as e:
                if self.verbose:
                    self.console.print(
                        f"[yellow]Warning: Skipping malformed conversation {idx}: {e}[/yellow]"
                    )
                continue

        return conversations

    def _parse_json_conversation(
        self, data: dict[str, Any], index: int
    ) -> Conversation:
        """Parse a single conversation from JSON data.

        Args:
            data: Dictionary containing conversation data.
            index: Index for generating fallback ID.

        Returns:
            Parsed Conversation object.
        """
        # Extract ID
        conv_id = str(
            data.get("uuid")
            or data.get("id")
            or data.get("conversation_id")
            or str(uuid.uuid4())
        )

        # Extract title
        title = (
            data.get("name")
            or data.get("title")
            or data.get("subject")
            or f"Conversation {index + 1}"
        )

        # Extract created_at
        created_at = self._parse_timestamp(
            data.get("created_at")
            or data.get("create_time")
            or data.get("timestamp")
            or data.get("date")
        )

        # Extract source URL
        source_url = data.get("url") or data.get("source_url")

        # Parse messages
        messages = self._parse_json_messages(data)

        return Conversation(
            id=conv_id,
            title=title,
            created_at=created_at,
            messages=messages,
            source_url=source_url,
        )

    def _parse_json_messages(self, data: dict[str, Any]) -> list[Message]:
        """Extract and parse messages from conversation data.

        Args:
            data: Conversation dictionary.

        Returns:
            List of Message objects.
        """
        messages: list[Message] = []

        # Try different message array keys
        raw_messages = (
            data.get("chat_messages")
            or data.get("messages")
            or data.get("conversation")
            or []
        )

        if not isinstance(raw_messages, list):
            return messages

        for msg_data in raw_messages:
            if not isinstance(msg_data, dict):
                continue

            # Extract role
            role = self._normalize_role(
                msg_data.get("sender")
                or msg_data.get("role")
                or msg_data.get("author")
                or "unknown"
            )

            # Extract content
            content = self._extract_message_content(msg_data)
            if not content:
                continue

            # Extract timestamp
            timestamp = self._parse_timestamp(
                msg_data.get("created_at")
                or msg_data.get("timestamp")
                or msg_data.get("time")
            )

            messages.append(Message(
                role=role,
                content=content,
                timestamp=timestamp,
            ))

        return messages

    def _extract_message_content(self, msg_data: dict[str, Any]) -> str:
        """Extract text content from a message object.

        Handles various content formats including nested structures.

        Args:
            msg_data: Message dictionary.

        Returns:
            Extracted text content.
        """
        # Try direct content field
        content = msg_data.get("text") or msg_data.get("content")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            # Handle content blocks (Claude format)
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif "text" in block:
                        parts.append(block["text"])
            return "\n".join(parts)

        if isinstance(content, dict):
            return content.get("text", "") or content.get("value", "")

        return ""

    def _normalize_role(self, role: str) -> str:
        """Normalize role names to 'human' or 'assistant'.

        Args:
            role: Raw role string.

        Returns:
            Normalized role ('human' or 'assistant').
        """
        role_lower = str(role).lower()

        if role_lower in ("human", "user", "you", "me"):
            return "human"
        elif role_lower in ("assistant", "claude", "ai", "bot", "system"):
            return "assistant"
        else:
            return role_lower

    def _parse_timestamp(self, value: Any) -> datetime:
        """Parse a timestamp from various formats.

        Args:
            value: Timestamp value (string, int, float, or None).

        Returns:
            Parsed datetime, or current time if parsing fails.
        """
        if value is None:
            return datetime.now()

        if isinstance(value, datetime):
            return value

        if isinstance(value, (int, float)):
            # Unix timestamp
            try:
                # Handle milliseconds
                if value > 1e12:
                    value = value / 1000
                return datetime.fromtimestamp(value)
            except (ValueError, OSError):
                return datetime.now()

        if isinstance(value, str):
            try:
                return date_parser.parse(value)
            except (ValueError, date_parser.ParserError):
                return datetime.now()

        return datetime.now()

    async def _parse_html(
        self, content: str, source_path: Path
    ) -> list[Conversation]:
        """Parse Claude HTML export format.

        Extracts conversations from HTML structure using BeautifulSoup.

        Args:
            content: Raw HTML content.
            source_path: Source file path for error reporting.

        Returns:
            List of parsed Conversation objects.
        """
        soup = BeautifulSoup(content, "lxml")
        conversations: list[Conversation] = []

        # Try to find conversation containers
        conv_containers = (
            soup.find_all("div", class_="conversation")
            or soup.find_all("article", class_="conversation")
            or soup.find_all("section", class_="conversation")
            or soup.find_all("div", {"data-conversation": True})
        )

        if not conv_containers:
            # Treat entire document as single conversation
            conv_containers = [soup]

        for idx, container in enumerate(conv_containers):
            try:
                conversation = self._parse_html_conversation(
                    container, idx, source_path
                )
                if conversation.messages:
                    conversations.append(conversation)
            except Exception as e:
                if self.verbose:
                    self.console.print(
                        f"[yellow]Warning: Skipping HTML conversation {idx}: {e}[/yellow]"
                    )
                continue

        return conversations

    def _parse_html_conversation(
        self, container: Any, index: int, source_path: Path
    ) -> Conversation:
        """Parse a single conversation from HTML container.

        Args:
            container: BeautifulSoup element containing conversation.
            index: Index for generating fallback ID.
            source_path: Source file for context.

        Returns:
            Parsed Conversation object.
        """
        # Extract ID
        conv_id = (
            container.get("data-id")
            or container.get("id")
            or str(uuid.uuid4())
        )

        # Extract title
        title_elem = (
            container.find("h1")
            or container.find("h2")
            or container.find("title")
            or container.find(class_="title")
        )
        title = (
            title_elem.get_text(strip=True) if title_elem
            else f"Conversation {index + 1}"
        )

        # Extract timestamp
        time_elem = container.find("time") or container.find(class_="timestamp")
        created_at = self._parse_timestamp(
            time_elem.get("datetime") if time_elem else None
        )

        # Parse messages
        messages = self._parse_html_messages(container)

        return Conversation(
            id=conv_id,
            title=title,
            created_at=created_at,
            messages=messages,
            source_url=str(source_path),
        )

    def _parse_html_messages(self, container: Any) -> list[Message]:
        """Extract messages from HTML container.

        Args:
            container: BeautifulSoup element containing messages.

        Returns:
            List of Message objects.
        """
        messages: list[Message] = []

        # Try various message container patterns
        msg_elements = (
            container.find_all("div", class_="message")
            or container.find_all("div", class_="chat-message")
            or container.find_all(class_=lambda c: c and "message" in c.lower() if c else False)
            or container.find_all("p")
        )

        for elem in msg_elements:
            # Determine role from class or data attribute
            classes = " ".join(elem.get("class", []))
            role_attr = elem.get("data-role", "")

            if "human" in classes.lower() or "user" in classes.lower():
                role = "human"
            elif "assistant" in classes.lower() or "claude" in classes.lower():
                role = "assistant"
            elif role_attr:
                role = self._normalize_role(role_attr)
            else:
                # Try to infer from structure
                role = "human" if len(messages) % 2 == 0 else "assistant"

            content = elem.get_text(separator="\n", strip=True)
            if not content:
                continue

            # Try to find timestamp
            time_elem = elem.find("time") or elem.find(class_="timestamp")
            timestamp = self._parse_timestamp(
                time_elem.get("datetime") if time_elem else None
            )

            messages.append(Message(
                role=role,
                content=content,
                timestamp=timestamp,
            ))

        return messages
