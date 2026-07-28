"""Stable import path for the linker agent."""
from importlib import import_module

_module = import_module("agents.06_linker")
LinkerAgent = _module.LinkerAgent
LinkedConversation = _module.LinkedConversation
LinkCandidate = _module.LinkCandidate
__all__ = ["LinkCandidate", "LinkedConversation", "LinkerAgent"]
