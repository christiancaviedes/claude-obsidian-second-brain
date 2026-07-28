"""Stable import path for the graph-builder agent."""
from importlib import import_module

_module = import_module("agents.05_graph_builder")
GraphBuilderAgent = _module.GraphBuilderAgent
NetworkXKnowledgeGraph = _module.NetworkXKnowledgeGraph
NodeInfo = _module.NodeInfo
EdgeInfo = _module.EdgeInfo
__all__ = ["EdgeInfo", "GraphBuilderAgent", "NetworkXKnowledgeGraph", "NodeInfo"]
