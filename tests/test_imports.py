from pathlib import Path

from agents import OrchestratorAgent, ParserAgent


def test_public_agent_imports_resolve() -> None:
    assert ParserAgent.__name__ == "ParserAgent"
    assert OrchestratorAgent.__name__ == "OrchestratorAgent"


def test_orchestrator_loads_taxonomy_and_agent_configuration(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    orchestrator = OrchestratorAgent(Path("config/settings.yaml"))

    taxonomy = orchestrator._load_taxonomy()
    assert "technical" in taxonomy["categories"]
    assert "ai-ml" in taxonomy["tags"]
    assert orchestrator._get_agent("parser").verbose is True
    assert orchestrator._get_agent("tagger").model == "claude-sonnet-4-20250514"
