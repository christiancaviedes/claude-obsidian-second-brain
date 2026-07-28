import json

from click.testing import CliRunner

from main import cli


def test_validate_accepts_sample_export() -> None:
    result = CliRunner().invoke(cli, ["validate", "examples/sample-export.json"])
    assert result.exit_code == 0
    assert "VALID" in result.output


def test_validate_rejects_missing_messages(tmp_path) -> None:
    invalid_export = tmp_path / "invalid.json"
    invalid_export.write_text(json.dumps([{"name": "Missing messages"}]), encoding="utf-8")
    result = CliRunner().invoke(cli, ["validate", str(invalid_export)])
    assert result.exit_code == 1
    assert "INVALID" in result.output


def test_stats_outputs_machine_readable_json(tmp_path) -> None:
    (tmp_path / "note.md").write_text(
        "# Note\n\n#ai\n\nSee [[Another Note]].", encoding="utf-8"
    )
    result = CliRunner().invoke(cli, ["stats", str(tmp_path), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["markdown_files"] == 1
    assert data["total_links"] == 1
    assert data["tags"] == {"ai": 1}
