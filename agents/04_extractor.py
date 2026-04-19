"""
ExtractorAgent - Extracts key insights, decisions, and concepts from conversations.

This agent processes tagged conversations using Claude API to extract structured
information including decisions, insights, action items, concepts, summaries,
and people mentioned.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

from anthropic import AsyncAnthropic, RateLimitError, APIError
from pydantic import BaseModel, Field
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from agents.models import TaggedConversation


console = Console()


class EnrichedConversation(TaggedConversation):
    """Conversation enriched with extracted insights and metadata.

    Extends TaggedConversation with detailed extraction from Claude API analysis.
    This is an intermediate model used by ExtractorAgent before final linking.

    Attributes:
        key_decisions: Important choices made during the conversation.
        insights: Valuable learnings and realizations discovered.
        action_items: Todos and next steps mentioned.
        concepts: Important terms and ideas discussed.
        summary: Brief 2-3 sentence summary of the conversation.
        people_mentioned: Names and roles referenced in the conversation.
    """
    key_decisions: list[str] = Field(
        default_factory=list,
        description="Important choices and decisions made"
    )
    insights: list[str] = Field(
        default_factory=list,
        description="Valuable learnings and realizations"
    )
    action_items: list[str] = Field(
        default_factory=list,
        description="Todos and next steps mentioned"
    )
    concepts: list[str] = Field(
        default_factory=list,
        description="Important terms and ideas discussed"
    )
    summary: str = Field(
        "",
        description="2-3 sentence summary of the conversation"
    )
    people_mentioned: list[str] = Field(
        default_factory=list,
        description="Names and roles referenced"
    )

    class Config:
        frozen = False
        extra = "ignore"

    def to_linked_conversation(self) -> "LinkedConversation":
        """Convert to LinkedConversation model for final output.

        Returns:
            LinkedConversation with extracted data mapped to model fields.
        """
        from agents.models import LinkedConversation as ModelLinkedConversation
        return ModelLinkedConversation(
            **{k: v for k, v in self.model_dump().items()
               if k in ModelLinkedConversation.model_fields},
            concepts=self.concepts,
            decisions=self.key_decisions,
            action_items=self.action_items,
            summary=self.summary,
        )


EXTRACTION_SYSTEM_PROMPT = """You are an expert at analyzing conversations and extracting structured information.

Given a conversation, extract the following in JSON format:
{
    "key_decisions": ["list of important choices or decisions made"],
    "insights": ["list of valuable learnings, realizations, or 'aha moments'"],
    "action_items": ["list of todos, next steps, or tasks mentioned"],
    "concepts": ["list of important terms, ideas, technologies, or frameworks discussed"],
    "summary": "A concise 2-3 sentence summary capturing the essence of the conversation",
    "people_mentioned": ["list of names, roles, or personas referenced (e.g., 'John', 'the manager', 'our CTO')"]
}

Guidelines:
- Be thorough but concise - capture the essence, not every detail
- For key_decisions: focus on actual choices made, not hypotheticals
- For insights: capture learnings that could be valuable later
- For action_items: include only clear, actionable items
- For concepts: include technologies, methodologies, frameworks, and domain terms
- For summary: focus on what the conversation achieved or discussed
- For people_mentioned: include both names and roles when mentioned

Return ONLY valid JSON, no markdown formatting or explanation."""


class ExtractorAgent:
    """Agent that extracts structured insights from tagged conversations.

    Uses Claude API to analyze conversation content and extract key information
    including decisions, insights, action items, concepts, summaries, and people.

    Attributes:
        client: Anthropic async client for API calls.
        model: Claude model to use for extraction.
        max_concurrent: Maximum concurrent API calls.
        batch_size: Number of conversations to process in parallel.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_concurrent: int = 5,
        batch_size: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize the ExtractorAgent.

        Args:
            api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.
            model: Claude model to use for extraction.
            max_concurrent: Maximum number of concurrent API calls.
            batch_size: Number of conversations to process in each batch.
            max_retries: Maximum retry attempts for rate-limited requests.
            retry_delay: Base delay between retries in seconds.
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable or api_key parameter required")

        self.client = AsyncAnthropic(api_key=self.api_key)
        self.model = model
        self.max_concurrent = max_concurrent
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._semaphore: Optional[asyncio.Semaphore] = None

    def _format_conversation_for_extraction(self, conversation: TaggedConversation) -> str:
        """Format a conversation for the extraction prompt.

        Args:
            conversation: The tagged conversation to format.

        Returns:
            Formatted string representation of the conversation.
        """
        lines = [
            f"Title: {conversation.title}",
            f"Date: {conversation.created_at.isoformat()}",
            f"Tags: {', '.join(conversation.tags)}",
            f"Category: {conversation.category}",
            "",
            "Messages:",
        ]

        for msg in conversation.messages:
            role_label = "Human" if msg.role == "human" else "Assistant"
            # Truncate very long messages to avoid token limits
            content = msg.content
            if len(content) > 2000:
                content = content[:2000] + "... [truncated]"
            lines.append(f"\n[{role_label}]:\n{content}")

        return "\n".join(lines)

    async def _extract_with_retry(
        self,
        conversation: TaggedConversation,
        semaphore: asyncio.Semaphore,
    ) -> EnrichedConversation:
        """Extract insights from a conversation with retry logic.

        Args:
            conversation: The tagged conversation to process.
            semaphore: Semaphore for rate limiting.

        Returns:
            EnrichedConversation with extracted data.

        Raises:
            APIError: If extraction fails after all retries.
        """
        async with semaphore:
            last_error: Optional[Exception] = None

            for attempt in range(self.max_retries):
                try:
                    return await self._extract_single(conversation)
                except RateLimitError as e:
                    last_error = e
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    console.print(
                        f"[yellow]Rate limited on '{conversation.title[:30]}...', "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.max_retries})[/yellow]"
                    )
                    await asyncio.sleep(delay)
                except APIError as e:
                    last_error = e
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay * (2 ** attempt)
                        console.print(
                            f"[yellow]API error on '{conversation.title[:30]}...', "
                            f"retrying in {delay:.1f}s[/yellow]"
                        )
                        await asyncio.sleep(delay)

            # If all retries failed, return conversation with empty extractions
            console.print(
                f"[red]Failed to extract from '{conversation.title[:30]}...' "
                f"after {self.max_retries} attempts: {last_error}[/red]"
            )
            return EnrichedConversation(
                **conversation.model_dump(),
                key_decisions=[],
                insights=[],
                action_items=[],
                concepts=[],
                summary=f"Extraction failed: {str(last_error)[:100]}",
                people_mentioned=[],
            )

    async def _extract_single(self, conversation: TaggedConversation) -> EnrichedConversation:
        """Extract insights from a single conversation.

        Args:
            conversation: The tagged conversation to process.

        Returns:
            EnrichedConversation with extracted data.
        """
        formatted_content = self._format_conversation_for_extraction(conversation)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Please analyze this conversation and extract the requested information:\n\n{formatted_content}",
                }
            ],
        )

        # Parse the JSON response
        response_text = response.content[0].text.strip()

        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first and last lines (```json and ```)
            response_text = "\n".join(lines[1:-1])

        try:
            extracted = json.loads(response_text)
        except json.JSONDecodeError as e:
            console.print(
                f"[yellow]JSON parse error for '{conversation.title[:30]}...': {e}[/yellow]"
            )
            extracted = {
                "key_decisions": [],
                "insights": [],
                "action_items": [],
                "concepts": [],
                "summary": "Failed to parse extraction response",
                "people_mentioned": [],
            }

        return EnrichedConversation(
            **conversation.model_dump(),
            key_decisions=extracted.get("key_decisions", []),
            insights=extracted.get("insights", []),
            action_items=extracted.get("action_items", []),
            concepts=extracted.get("concepts", []),
            summary=extracted.get("summary", ""),
            people_mentioned=extracted.get("people_mentioned", []),
        )

    async def process(
        self,
        conversations: list[TaggedConversation],
    ) -> list[EnrichedConversation]:
        """Process multiple conversations and extract insights from each.

        Args:
            conversations: List of tagged conversations to process.

        Returns:
            List of enriched conversations with extracted data.
        """
        if not conversations:
            console.print("[yellow]No conversations to process[/yellow]")
            return []

        console.print(f"\n[bold blue]Extracting insights from {len(conversations)} conversations[/bold blue]")

        results: list[EnrichedConversation] = []
        semaphore = asyncio.Semaphore(self.max_concurrent)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "[cyan]Extracting insights...",
                total=len(conversations),
            )

            # Process in batches
            for batch_start in range(0, len(conversations), self.batch_size):
                batch = conversations[batch_start : batch_start + self.batch_size]

                # Create tasks for this batch
                tasks = [
                    self._extract_with_retry(conv, semaphore)
                    for conv in batch
                ]

                # Process batch concurrently
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                for i, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        console.print(f"[red]Error processing conversation: {result}[/red]")
                        # Create a fallback enriched conversation
                        conv = batch[i]
                        result = EnrichedConversation(
                            **conv.model_dump(),
                            key_decisions=[],
                            insights=[],
                            action_items=[],
                            concepts=[],
                            summary=f"Error during extraction: {str(result)[:100]}",
                            people_mentioned=[],
                        )
                    results.append(result)
                    progress.advance(task)

        # Print summary statistics
        total_decisions = sum(len(r.key_decisions) for r in results)
        total_insights = sum(len(r.insights) for r in results)
        total_actions = sum(len(r.action_items) for r in results)
        total_concepts = sum(len(r.concepts) for r in results)
        total_people = sum(len(r.people_mentioned) for r in results)

        console.print("\n[bold green]Extraction complete![/bold green]")
        console.print(f"  [dim]Decisions:[/dim] {total_decisions}")
        console.print(f"  [dim]Insights:[/dim] {total_insights}")
        console.print(f"  [dim]Action items:[/dim] {total_actions}")
        console.print(f"  [dim]Concepts:[/dim] {total_concepts}")
        console.print(f"  [dim]People mentioned:[/dim] {total_people}")

        return results

    async def close(self) -> None:
        """Close the API client and release resources."""
        await self.client.close()
