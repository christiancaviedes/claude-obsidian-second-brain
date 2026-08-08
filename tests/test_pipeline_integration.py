from pathlib import Path
from types import SimpleNamespace

import pytest

from agents import OrchestratorAgent


class FakeAgent:
    def __init__(self, output):
        self.output = output

    async def process(self, *args, **kwargs):
        return self.output


class FakeGraph:
    nodes = ["conversation-1"]
    edges = []

    def to_model(self):
        return self


@pytest.mark.integration
async def test_complete_pipeline_with_remote_ai_stages_mocked(tmp_path, monkeypatch):
    """Exercise every orchestration stage without sending private data to an API."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "mocked")
    monkeypatch.chdir(tmp_path)

    config = tmp_path / "settings.yaml"
    config.write_text(
        "paths:\n  cache_dir: .cache\n  logs_dir: logs\nlogging:\n  file_logging: false\n",
        encoding="utf-8",
    )
    export = tmp_path / "export.json"
    export.write_text("[]", encoding="utf-8")

    conversation = SimpleNamespace(id="conversation-1")
    graph = FakeGraph()
    orchestrator = OrchestratorAgent(config)
    orchestrator.agents = {
        "parser": FakeAgent([conversation]),
        "cleaner": FakeAgent([conversation]),
        "tagger": FakeAgent([conversation]),
        "extractor": FakeAgent([conversation]),
        "graph": FakeAgent(graph),
        "linker": FakeAgent([conversation]),
        "moc": FakeAgent([SimpleNamespace(title="Architecture")]),
        "formatter": FakeAgent(SimpleNamespace(notes_created=1, mocs_created=1)),
        "indexer": FakeAgent(SimpleNamespace(path="000 Index/README.md")),
    }

    result = await orchestrator.run(export, tmp_path / "vault")

    assert result.success is True
    assert result.stages_completed == [name for name, _ in orchestrator.STAGES]
    assert result.total_conversations == 1
    assert result.total_notes == 2
    assert result.total_mocs == 1
    assert not (tmp_path / ".cache" / "pipeline_checkpoint.json").exists()
