"""Stable import path for the MOC generator agent."""
from importlib import import_module

MOCGeneratorAgent = import_module("agents.07_moc_generator").MOCGeneratorAgent
__all__ = ["MOCGeneratorAgent"]
