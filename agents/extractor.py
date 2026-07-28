"""Stable import path for the extractor agent."""
from importlib import import_module

_module = import_module("agents.04_extractor")
ExtractorAgent = _module.ExtractorAgent
EnrichedConversation = _module.EnrichedConversation
__all__ = ["EnrichedConversation", "ExtractorAgent"]
