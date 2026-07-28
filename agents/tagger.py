"""Stable import path for the tagger agent."""
from importlib import import_module

TaggerAgent = import_module("agents.03_tagger").TaggerAgent
__all__ = ["TaggerAgent"]
