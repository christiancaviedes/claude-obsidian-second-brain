"""Stable import path for the cleaner agent."""
from importlib import import_module

CleanerAgent = import_module("agents.02_cleaner").CleanerAgent
__all__ = ["CleanerAgent"]
