"""Stable import path for the formatter agent."""
from importlib import import_module

FormatterAgent = import_module("agents.08_formatter").FormatterAgent
__all__ = ["FormatterAgent"]
