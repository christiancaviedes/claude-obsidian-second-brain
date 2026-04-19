"""
TaggerAgent - Uses Claude API to generate smart tags.

This agent analyzes conversations and generates relevant tags,
categories, and confidence scores using the Anthropic API.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
from typing import Any, Optional

import anthropic
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from agents.models import Conversation, Message, TaggedConversation


class TaggerAgent:
    """Generates smart tags for conversations using Claude API.

    Uses the Anthropic SDK to analyze conversation content and generate
    relevant tags based on a provided taxonomy. Handles batching,
    rate limits, and confidence scoring.

    Attributes:
        console: Rich console for output.
        verbose: Whether to output detailed progress information.
        client: Anthropic API client.
        model: Claude model to use for tagging.
        max_retries: Maximum retry attempts for API calls.
        batch_size: Number of conversations per API batch.

    Example:
        ```python
        tagger = TaggerAgent(verbose=True)
        taxonomy = {
            "categories": ["programming", "writing", "research"],
            "tags": ["python", "javascript", "api", "debugging"]
        }
        tagged = await tagger.process(conversations, taxonomy)
        ```
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        verbose: bool = True,
        max_retries: int = 5,
        batch_size: int = 5,
    ) -> None:
        """Initialize the TaggerAgent.

        Args:
            api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.
            model: Claude model to use for tagging.
            verbose: If True, output progress information to console.
            max_retries: Maximum retry attempts for rate-limited requests.
            batch_size: Number of conversations to process per API call.
        """
        self.console = Console()
        self.verbose = verbose
        self.model = model
        self.max_retries = max_retries
        self.batch_size = batch_size

        # Initialize Anthropic client
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Please set it or pass api_key parameter."
            )
        self.client = anthropic.Anthropic(api_key=key)

    async def process(
        self,
        conversations: list[Conversation],
        taxonomy: dict[str, Any],
    ) -> list[TaggedConversation]:
        """Generate tags for a list of conversations.

        Batches conversations efficiently to minimize API calls while
        staying within rate limits.

        Args:
            conversations: List of Conversation objects to tag.
            taxonomy: Dictionary containing:
                - categories: List of valid category names
                - tags: List of valid tag names
                - Optional: descriptions for categories/tags

        Returns:
            List of TaggedConversation objects with tags and categories.
        """
        if not conversations:
            return []

        if self.verbose:
            self.console.print(
                f"[blue]Tagging {len(conversations)} conversations...[/blue]"
            )

        tagged: list[TaggedConversation] = []

        # Prepare batches
        batches = [
            conversations[i:i + self.batch_size]
            for i in range(0, len(conversations), self.batch_size)
        ]

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.console,
            disable=not self.verbose,
        ) as progress:
            task = progress.add_task(
                "Tagging conversations...",
                total=len(conversations)
            )

            for batch in batches:
                results = await self._tag_batch(batch, taxonomy)
                tagged.extend(results)
                progress.update(task, advance=len(batch))

        if self.verbose:
            self.console.print(
                f"[green]Tagged {len(tagged)} conversations[/green]"
            )

        return tagged

    async def _tag_batch(
        self,
        batch: list[Conversation],
        taxonomy: dict[str, Any],
    ) -> list[TaggedConversation]:
        """Tag a batch of conversations with a single API call.

        Args:
            batch: List of conversations to tag.
            taxonomy: Taxonomy dictionary.

        Returns:
            List of TaggedConversation objects.
        """
        # Build prompt for batch tagging
        prompt = self._build_batch_prompt(batch, taxonomy)

        # Call API with retry
        response = await self._call_api_with_retry(prompt)

        # Parse response
        tags_data = self._parse_response(response, len(batch))

        # Build TaggedConversation objects
        results: list[TaggedConversation] = []
        for i, conv in enumerate(batch):
            tag_info = tags_data[i] if i < len(tags_data) else {}

            tagged = TaggedConversation(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                messages=conv.messages,
                source_url=conv.source_url,
                tags=tag_info.get("tags", [])[:7],  # Max 7 tags
                category=tag_info.get("category", "uncategorized"),
                tag_confidence=tag_info.get("confidence", {}),
            )
            results.append(tagged)

        return results

    def _build_batch_prompt(
        self,
        batch: list[Conversation],
        taxonomy: dict[str, Any],
    ) -> str:
        """Build the prompt for batch tagging.

        Args:
            batch: List of conversations.
            taxonomy: Taxonomy dictionary.

        Returns:
            Formatted prompt string.
        """
        categories = taxonomy.get("categories", [])
        available_tags = taxonomy.get("tags", [])
        category_descriptions = taxonomy.get("category_descriptions", {})

        # Build taxonomy description
        tax_desc = "## Available Categories\n"
        for cat in categories:
            desc = category_descriptions.get(cat, "")
            tax_desc += f"- {cat}"
            if desc:
                tax_desc += f": {desc}"
            tax_desc += "\n"

        if available_tags:
            tax_desc += "\n## Suggested Tags\n"
            tax_desc += ", ".join(available_tags)
            tax_desc += "\n\nYou may also create relevant tags not in this list."

        # Build conversation summaries
        conv_summaries = []
        for i, conv in enumerate(batch):
            # Create a summary of the conversation
            summary = self._summarize_conversation(conv)
            conv_summaries.append(f"### Conversation {i + 1}\n{summary}")

        convs_text = "\n\n".join(conv_summaries)

        prompt = f"""Analyze the following conversations and assign relevant tags and a primary category to each.

{tax_desc}

## Instructions
- Assign 3-7 relevant tags per conversation
- Assign exactly one primary category from the available categories
- Provide confidence scores (0.0 to 1.0) for each tag
- Return valid JSON

## Conversations

{convs_text}

## Response Format
Return a JSON array with one object per conversation:
```json
[
  {{
    "conversation_index": 1,
    "category": "category_name",
    "tags": ["tag1", "tag2", "tag3"],
    "confidence": {{
      "tag1": 0.95,
      "tag2": 0.87,
      "tag3": 0.72
    }}
  }}
]
```

Respond with ONLY the JSON array, no other text."""

        return prompt

    def _summarize_conversation(self, conv: Conversation) -> str:
        """Create a summary of a conversation for tagging.

        Args:
            conv: The conversation to summarize.

        Returns:
            Summary string.
        """
        parts = [f"**Title:** {conv.title}"]

        # Include first few and last few messages
        messages = conv.messages
        max_messages = 6

        if len(messages) <= max_messages:
            selected = messages
        else:
            # First 3 and last 3
            selected = messages[:3] + messages[-3:]

        for msg in selected:
            role = msg.role.capitalize()
            # Truncate long messages
            content = msg.content[:500]
            if len(msg.content) > 500:
                content += "..."
            parts.append(f"**{role}:** {content}")

        if len(messages) > max_messages:
            parts.insert(4, f"*[... {len(messages) - max_messages} more messages ...]*")

        return "\n\n".join(parts)

    async def _call_api_with_retry(self, prompt: str) -> str:
        """Call Claude API with exponential backoff retry.

        Args:
            prompt: The prompt to send.

        Returns:
            Response text from Claude.

        Raises:
            Exception: If all retries fail.
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                # Run sync client in thread pool
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.messages.create(
                        model=self.model,
                        max_tokens=4096,
                        messages=[
                            {"role": "user", "content": prompt}
                        ],
                    )
                )

                # Extract text content
                text_content = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text_content += block.text

                return text_content

            except anthropic.RateLimitError as e:
                last_error = e
                # Exponential backoff with jitter
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                if self.verbose:
                    self.console.print(
                        f"[yellow]Rate limited, waiting {wait_time:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})[/yellow]"
                    )
                await asyncio.sleep(wait_time)

            except anthropic.APIError as e:
                last_error = e
                if self.verbose:
                    self.console.print(
                        f"[yellow]API error: {e}, retrying...[/yellow]"
                    )
                await asyncio.sleep(1)

        raise Exception(f"API call failed after {self.max_retries} retries: {last_error}")

    def _parse_response(
        self, response: str, expected_count: int
    ) -> list[dict[str, Any]]:
        """Parse the JSON response from Claude.

        Args:
            response: Raw response text.
            expected_count: Expected number of results.

        Returns:
            List of tag dictionaries.
        """
        # Extract JSON from response
        response = response.strip()

        # Try to find JSON array in response
        start_idx = response.find("[")
        end_idx = response.rfind("]") + 1

        if start_idx != -1 and end_idx > start_idx:
            json_str = response[start_idx:end_idx]
        else:
            json_str = response

        try:
            data = json.loads(json_str)

            if not isinstance(data, list):
                data = [data]

            # Normalize the data
            results: list[dict[str, Any]] = []
            for item in data:
                result = {
                    "tags": item.get("tags", []),
                    "category": item.get("category", "uncategorized"),
                    "confidence": item.get("confidence", {}),
                }

                # Ensure confidence has all tags
                for tag in result["tags"]:
                    if tag not in result["confidence"]:
                        result["confidence"][tag] = 0.5

                results.append(result)

            # Pad with defaults if we got fewer results
            while len(results) < expected_count:
                results.append({
                    "tags": [],
                    "category": "uncategorized",
                    "confidence": {},
                })

            return results

        except json.JSONDecodeError as e:
            if self.verbose:
                self.console.print(
                    f"[yellow]Warning: Failed to parse tagging response: {e}[/yellow]"
                )
            # Return defaults
            return [
                {"tags": [], "category": "uncategorized", "confidence": {}}
                for _ in range(expected_count)
            ]
