"""Stable import path for the parser agent."""
from importlib import import_module

ParserAgent = import_module("agents.01_parser").ParserAgent
__all__ = ["ParserAgent"]
