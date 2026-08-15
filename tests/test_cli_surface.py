import json
import re

import pytest
from typer.testing import CliRunner

from amicited.cli.app import app

runner = CliRunner()

EXPECTED_COMMANDS = {
    "inspect",
    "verify",
    "remove",
    "rewrite",
    "compare",
    "explain",
    "capabilities",
    "skills",
}


def _plain(value: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", value)


def test_root_help_exposes_only_the_watermark_feature_namespace() -> None:
    result = runner.invoke(app, ["--help"], color=False)

    assert result.exit_code == 0
    output = _plain(result.stdout)
    assert "watermark" in output


def test_watermark_help_exposes_every_version_one_operation() -> None:
    result = runner.invoke(app, ["watermark", "--help"], color=False)

    assert result.exit_code == 0
    output = _plain(result.stdout)
    for command in EXPECTED_COMMANDS:
        assert command in output


@pytest.mark.parametrize(
    "arguments",
    [
        ["watermark", "compare", "-", "-"],
        ["watermark", "explain", "report.json"],
    ],
)
def test_unimplemented_commands_fail_with_a_stable_exit_code(
    arguments: list[str],
) -> None:
    result = runner.invoke(app, arguments, input="text")

    assert result.exit_code == 5
    assert "not implemented" in _plain(result.output).lower()


@pytest.mark.parametrize(
    ("arguments", "operation"),
    [
        (["watermark", "inspect", "-"], "inspect"),
        (["watermark", "verify", "-"], "verify"),
        (["watermark", "remove", "-"], "remove"),
        (["watermark", "rewrite", "-"], "rewrite"),
        (["watermark", "capabilities"], "capabilities"),
    ],
)
def test_implemented_commands_emit_structured_results(
    arguments: list[str], operation: str
) -> None:
    result = runner.invoke(app, arguments, input="a\u200bb")

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["schema_version"] == "1.0"
    assert report["operation"] == operation


def test_rewrite_help_exposes_semantic_model_configuration() -> None:
    result = runner.invoke(app, ["watermark", "rewrite", "--help"], color=False)

    assert result.exit_code == 0
    output = _plain(result.stdout)
    assert "--model" in output
    assert "--provider" in output
    assert "default: api" in output
    assert "--model-provider" in output
    assert "--base-url" in output
    assert "--temperature" in output
    assert "--cli-timeout" in output
    assert "--max-chunk-words" in output
    assert "--max-concurrency" in output
    assert "--lexical-diversity" in output
    assert "--order-diversity" in output
    assert "--output" in output
    assert "-o" in output
    assert "--overwrite" in output
    assert "--include-conte" in output


def test_skills_help_exposes_provider_and_safe_update_options() -> None:
    result = runner.invoke(app, ["watermark", "skills", "--help"], color=False)

    assert result.exit_code == 0
    output = _plain(result.stdout)
    assert "--provider" in output
    assert "-p" in output
    assert "codex" in output
    assert "claude" in output
    assert "--force" in output
