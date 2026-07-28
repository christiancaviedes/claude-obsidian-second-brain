"""Stable import path for the indexer agent."""
from importlib import import_module

IndexerAgent = import_module("agents.09_indexer").IndexerAgent
__all__ = ["IndexerAgent"]
