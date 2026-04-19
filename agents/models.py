"""
Data models for Claude Obsidian Second Brain.

Contains Pydantic models for Conversation, Message, TaggedConversation,
LinkedConversation, KnowledgeGraph, MOCPage, and OutputStats.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Represents a single message in a conversation.

    Attributes:
        role: The role of the message sender (human/assistant).
        content: The text content of the message.
        timestamp: Optional timestamp when the message was sent.
    """
    role: str = Field(..., description="Role of sender: 'human' or 'assistant'")
    content: str = Field(..., description="Text content of the message")
    timestamp: Optional[datetime] = Field(None, description="When the message was sent")

    class Config:
        frozen = False
        extra = "ignore"


class Conversation(BaseModel):
    """Represents a complete conversation from Claude exports.

    Attributes:
        id: Unique identifier for the conversation.
        title: Title or subject of the conversation.
        created_at: When the conversation was created.
        messages: List of messages in the conversation.
        source_url: Optional URL where the conversation originated.
    """
    id: str = Field(..., description="Unique conversation identifier")
    title: str = Field(..., description="Conversation title or subject")
    created_at: datetime = Field(..., description="Creation timestamp")
    messages: list[Message] = Field(default_factory=list, description="Messages in order")
    source_url: Optional[str] = Field(None, description="Original source URL if available")

    class Config:
        frozen = False
        extra = "ignore"


class TaggedConversation(Conversation):
    """Conversation with AI-generated tags and categorization.

    Extends Conversation with tagging metadata from Claude API analysis.

    Attributes:
        tags: List of relevant tags for the conversation.
        category: Primary category classification.
        tag_confidence: Confidence scores for each tag (0.0 to 1.0).
    """
    tags: list[str] = Field(default_factory=list, description="Generated tags")
    category: str = Field("uncategorized", description="Primary category")
    tag_confidence: dict[str, float] = Field(
        default_factory=dict,
        description="Confidence score per tag"
    )

    class Config:
        frozen = False
        extra = "ignore"


class LinkedConversation(TaggedConversation):
    """Conversation with linked relationships to other conversations.

    Extends TaggedConversation with graph-based linking information.

    Attributes:
        related_conversations: List of related conversation IDs.
        concepts: List of extracted concepts from the conversation.
        decisions: List of decisions made in the conversation.
        action_items: List of action items extracted.
        summary: AI-generated summary of the conversation.
        link_strength: Strength scores for each linked conversation (0.0 to 1.0).
    """
    related_conversations: list[str] = Field(
        default_factory=list,
        description="IDs of related conversations"
    )
    concepts: list[str] = Field(
        default_factory=list,
        description="Extracted concepts/topics"
    )
    decisions: list[str] = Field(
        default_factory=list,
        description="Decisions made in conversation"
    )
    action_items: list[str] = Field(
        default_factory=list,
        description="Action items to follow up"
    )
    summary: str = Field("", description="AI-generated summary")
    link_strength: dict[str, float] = Field(
        default_factory=dict,
        description="Strength of link to each related conversation"
    )

    class Config:
        frozen = False
        extra = "ignore"


@dataclass
class KnowledgeNode:
    """Represents a node in the knowledge graph.

    Attributes:
        id: Unique identifier for the node.
        node_type: Type of node (conversation, concept, tag, category).
        label: Display label for the node.
        metadata: Additional metadata about the node.
        connections: List of connected node IDs.
    """
    id: str
    node_type: str
    label: str
    metadata: dict[str, Any] = field(default_factory=dict)
    connections: list[str] = field(default_factory=list)


@dataclass
class KnowledgeEdge:
    """Represents an edge in the knowledge graph.

    Attributes:
        source: Source node ID.
        target: Target node ID.
        edge_type: Type of relationship.
        weight: Strength of the connection (0.0 to 1.0).
        metadata: Additional metadata about the edge.
    """
    source: str
    target: str
    edge_type: str
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeGraph:
    """Represents the entire knowledge graph structure.

    Attributes:
        nodes: Dictionary of node ID to KnowledgeNode.
        edges: List of KnowledgeEdge connections.
        clusters: Dictionary of cluster ID to list of node IDs.
        metadata: Graph-level metadata.
    """
    nodes: dict[str, KnowledgeNode] = field(default_factory=dict)
    edges: list[KnowledgeEdge] = field(default_factory=list)
    clusters: dict[str, list[str]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_node_connections(self, node_id: str) -> list[str]:
        """Get all nodes connected to a given node."""
        connections = []
        for edge in self.edges:
            if edge.source == node_id:
                connections.append(edge.target)
            elif edge.target == node_id:
                connections.append(edge.source)
        return connections

    def get_node_degree(self, node_id: str) -> int:
        """Get the number of connections for a node."""
        return len(self.get_node_connections(node_id))


@dataclass
class MOCPage:
    """Represents a Map of Content (MOC) page for Obsidian.

    Attributes:
        title: Title of the MOC.
        category: Category this MOC belongs to.
        description: Description of what this MOC covers.
        linked_notes: List of conversation IDs/titles in this MOC.
        sub_mocs: List of child MOC titles for deeper organization.
        key_concepts: Key concepts covered in this MOC.
        content: Full markdown content of the MOC.
    """
    title: str
    category: str
    description: str
    linked_notes: list[str] = field(default_factory=list)
    sub_mocs: list[str] = field(default_factory=list)
    key_concepts: list[str] = field(default_factory=list)
    content: str = ""


@dataclass
class OutputStats:
    """Statistics about the output generation process.

    Attributes:
        notes_created: Number of conversation notes created.
        mocs_created: Number of MOC pages created.
        total_links: Total number of wikilinks generated.
        output_path: Path where output was written.
    """
    notes_created: int = 0
    mocs_created: int = 0
    total_links: int = 0
    output_path: Path = field(default_factory=lambda: Path("."))