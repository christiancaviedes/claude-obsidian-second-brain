"""
Claude Obsidian Second Brain - Agent Classes

This module exports all agent classes for the conversation processing pipeline.

Agents:
    1. ParserAgent - Parse Claude export files
    2. CleanerAgent - Clean and normalize conversations
    3. TaggerAgent - Apply taxonomy-based tagging
    4. ExtractorAgent - Extract insights and decisions
    5. GraphBuilderAgent - Build knowledge graph
    6. LinkerAgent - Create wikilinks between notes
    7. MOCGeneratorAgent - Generate Maps of Content
    8. FormatterAgent - Write Obsidian-formatted files
    9. IndexerAgent - Create master index
    10. OrchestratorAgent - Coordinate all agents
"""
from __future__ import annotations

from agents.models import (
    Conversation,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    LinkedConversation,
    Message,
    MOCPage,
    OutputStats,
    TaggedConversation,
)

# Import agents with graceful fallbacks for missing implementations
import importlib

try:
    _parser_module = importlib.import_module("agents.01_parser")
    ParserAgent = _parser_module.ParserAgent
except (ImportError, ModuleNotFoundError):
    ParserAgent = None  # type: ignore

try:
    _cleaner_module = importlib.import_module("agents.02_cleaner")
    CleanerAgent = _cleaner_module.CleanerAgent
except (ImportError, ModuleNotFoundError):
    CleanerAgent = None  # type: ignore

try:
    _tagger_module = importlib.import_module("agents.03_tagger")
    TaggerAgent = _tagger_module.TaggerAgent
except (ImportError, ModuleNotFoundError):
    TaggerAgent = None  # type: ignore

try:
    import importlib
    _extractor_module = importlib.import_module("agents.04_extractor")
    ExtractorAgent = _extractor_module.ExtractorAgent
    EnrichedConversation = _extractor_module.EnrichedConversation
except (ImportError, ModuleNotFoundError):
    try:
        from agents.extractor import ExtractorAgent, EnrichedConversation
    except ImportError:
        ExtractorAgent = None  # type: ignore
        EnrichedConversation = None  # type: ignore

try:
    import importlib
    _graph_builder_module = importlib.import_module("agents.05_graph_builder")
    GraphBuilderAgent = _graph_builder_module.GraphBuilderAgent
    NetworkXKnowledgeGraph = _graph_builder_module.NetworkXKnowledgeGraph
    NodeInfo = _graph_builder_module.NodeInfo
    EdgeInfo = _graph_builder_module.EdgeInfo
except (ImportError, ModuleNotFoundError):
    try:
        from agents.graph_builder import GraphBuilderAgent, NetworkXKnowledgeGraph, NodeInfo, EdgeInfo
    except ImportError:
        GraphBuilderAgent = None  # type: ignore
        NetworkXKnowledgeGraph = None  # type: ignore
        NodeInfo = None  # type: ignore
        EdgeInfo = None  # type: ignore

try:
    import importlib
    _linker_module = importlib.import_module("agents.06_linker")
    LinkerAgent = _linker_module.LinkerAgent
    LinkerLinkedConversation = _linker_module.LinkedConversation
    LinkCandidate = _linker_module.LinkCandidate
except (ImportError, ModuleNotFoundError):
    try:
        from agents.linker import LinkerAgent, LinkedConversation as LinkerLinkedConversation, LinkCandidate
    except ImportError:
        LinkerAgent = None  # type: ignore
        LinkerLinkedConversation = None  # type: ignore
        LinkCandidate = None  # type: ignore

try:
    import importlib
    _moc_gen_module = importlib.import_module("agents.07_moc_generator")
    MOCGeneratorAgent = _moc_gen_module.MOCGeneratorAgent
except (ImportError, ModuleNotFoundError):
    try:
        from agents.moc_generator import MOCGeneratorAgent
    except ImportError:
        MOCGeneratorAgent = None  # type: ignore

try:
    import importlib
    _formatter_module = importlib.import_module("agents.08_formatter")
    FormatterAgent = _formatter_module.FormatterAgent
except (ImportError, ModuleNotFoundError):
    try:
        from agents.formatter import FormatterAgent
    except ImportError:
        FormatterAgent = None  # type: ignore

try:
    import importlib
    _indexer_module = importlib.import_module("agents.09_indexer")
    IndexerAgent = _indexer_module.IndexerAgent
except (ImportError, ModuleNotFoundError):
    try:
        from agents.indexer import IndexerAgent
    except ImportError:
        IndexerAgent = None  # type: ignore

# Orchestrator is always available
from agents.orchestrator import (
    OrchestratorAgent,
    PipelineResult,
    StageResult,
    run_pipeline,
)

__all__ = [
    # Models from models.py
    "Conversation",
    "KnowledgeEdge",
    "KnowledgeGraph",
    "KnowledgeNode",
    "LinkedConversation",
    "Message",
    "MOCPage",
    "OutputStats",
    "TaggedConversation",
    # Models from agent modules
    "EnrichedConversation",
    "NetworkXKnowledgeGraph",
    "NodeInfo",
    "EdgeInfo",
    "LinkerLinkedConversation",
    "LinkCandidate",
    # Pipeline result types
    "PipelineResult",
    "StageResult",
    # Agents
    "ParserAgent",
    "CleanerAgent",
    "TaggerAgent",
    "ExtractorAgent",
    "GraphBuilderAgent",
    "LinkerAgent",
    "MOCGeneratorAgent",
    "FormatterAgent",
    "IndexerAgent",
    "OrchestratorAgent",
    # Convenience functions
    "run_pipeline",
]
