from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from amicited import watermark
from amicited.errors import (
    MissingModelCredentialError,
    ModelCLIUnavailableError,
    ModelConfigurationError,
    ProtectedSpanError,
)
from amicited.watermark.layers import (
    SemanticProvider,
    SemanticRewriteLayer,
    TextWatermarkLayer,
)
from amicited.watermark.models import RiskLevel, VerificationStatus


@dataclass
class FakeMessage:
    content: str


class FakeChatModel:
    def __init__(self, *, replacement: tuple[str, str] | None = None) -> None:
        self.replacement = replacement
        self.requests: list[object] = []

    def invoke(self, messages: object) -> FakeMessage:
        self.requests.append(messages)
        prompt = str(messages)
        if self.replacement is None:
            return FakeMessage(prompt)
        before, after = self.replacement
        assert before in prompt
        protected_text = prompt[prompt.index("<TEXT>\n") + len("<TEXT>\n") :]
        protected_text = protected_text[: protected_text.index("\n</TEXT>")]
        return FakeMessage(protected_text.replace(before, after))


class FailingChatModel:
    def invoke(self, messages: object) -> object:
        raise RuntimeError("provider leaked secret-token and private input")


def test_semantic_layer_implements_the_layer_contract_and_is_unverifiable() -> None:
    layer = SemanticRewriteLayer(
        model="openai:test-model",
        chat_model=FakeChatModel(),
    )

    assert isinstance(layer, TextWatermarkLayer)
    assert layer.inspect("plain text").findings == ()
    verification = layer.verify("plain text")
    assert verification.status is VerificationStatus.UNVERIFIABLE
    assert verification.signal_type == "statistical_text_watermark"
    assert verification.provider == "openai"
    assert verification.detector is not None
    assert verification.detector.authority.value == "heuristic"

    capability = layer.capability()
    assert capability.network_required is True
    assert capability.deterministic is False
    assert capability.signal_type == "statistical_text_watermark"
    assert "model for API provider" in capability.requirements


def test_sdk_model_rewrite_uses_langchain_and_preserves_sensitive_spans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeChatModel(
        replacement=(
            "The original sentence has a predictable structure.",
            "A less predictable structure now carries the original point.",
        )
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic._init_chat_model",
        lambda **kwargs: fake,
    )
    original = (
        "---\ntitle: Test 2026\n---\n\n"
        'The original sentence has a predictable structure. "Keep this quote." '
        "See https://example.com/a?q=1 and citation [12].\n\n"
        "```python\nanswer = 42\n```\n"
    )

    report = watermark.rewrite(
        watermark.WatermarkInput.text(original),
        model="openai:test-model",
    )

    assert "A less predictable structure" in report.transformed_text
    assert '"Keep this quote."' in report.transformed_text
    assert "https://example.com/a?q=1" in report.transformed_text
    assert "[12]" in report.transformed_text
    assert "---\ntitle: Test 2026\n---" in report.transformed_text
    assert "```python\nanswer = 42\n```" in report.transformed_text
    assert report.results[-1].layer_id == "semantic_rewrite"
    assert report.results[-1].model == "openai:test-model"
    assert report.results[-1].provider == "openai"
    assert report.results[-1].execution_provider == "api"
    assert report.results[-1].external_processing is True
    assert report.results[-1].protected_spans_preserved is True
    assert report.results[-1].meaning_risk is RiskLevel.MEDIUM
    assert (
        report.after_verification.results[-1].status is VerificationStatus.UNVERIFIABLE
    )
    assert report.verification_status is VerificationStatus.UNVERIFIABLE
    assert fake.requests


def test_sdk_fails_before_reading_or_sending_content_when_api_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(MissingModelCredentialError) as error:
        watermark.rewrite(
            watermark.WatermarkInput.text("private input"),
            model="openai:test-model",
        )

    assert error.value.provider == "openai"
    assert error.value.environment_variable == "OPENAI_API_KEY"
    assert "private input" not in str(error.value)


def test_model_failure_is_structured_and_preserves_the_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic._init_chat_model",
        lambda **kwargs: FailingChatModel(),
    )

    report = watermark.rewrite(
        watermark.WatermarkInput.text("private input"),
        model="openai:test-model",
    )

    assert report.transformation_status == "failed"
    assert report.transformed_text == "private input"
    assert report.results[-1].errors == ("Layer failed during transformation.",)
    assert "secret-token" not in report.to_json()


def test_semantic_layer_rejects_a_response_that_drops_protected_spans() -> None:
    class DropsProtectedSpan:
        def invoke(self, messages: object) -> FakeMessage:
            return FakeMessage("Rewritten without the protected URL.")

    layer = SemanticRewriteLayer(
        model="openai:test-model",
        chat_model=DropsProtectedSpan(),
    )

    with pytest.raises(ProtectedSpanError, match="protected spans") as error:
        layer.rewrite("Read https://example.com and keep 42.")

    assert error.value.diagnostics.expected_count == 2
    assert error.value.diagnostics.found_count == 0
    assert error.value.diagnostics.first_mismatch_index == 0
    assert error.value.diagnostics.missing_ids == ("0000", "0001")
    assert error.value.diagnostics.duplicate_ids == ()
    assert error.value.diagnostics.unexpected_ids == ()
    assert error.value.diagnostics.reordered is False
    assert error.value.diagnostics.malformed_placeholder_count == 0


def test_semantic_layer_rejects_reordered_protected_spans() -> None:
    class ReordersProtectedSpans:
        def invoke(self, messages: object) -> FakeMessage:
            return FakeMessage(
                "__AMICITED_PROTECTED_0001__ then __AMICITED_PROTECTED_0000__"
            )

    layer = SemanticRewriteLayer(
        model="openai:test-model",
        chat_model=ReordersProtectedSpans(),
    )

    with pytest.raises(ProtectedSpanError, match="protected spans") as error:
        layer.rewrite("Read https://example.com before 42.")

    assert error.value.diagnostics.expected_count == 2
    assert error.value.diagnostics.found_count == 2
    assert error.value.diagnostics.first_mismatch_index == 0
    assert error.value.diagnostics.missing_ids == ()
    assert error.value.diagnostics.duplicate_ids == ()
    assert error.value.diagnostics.unexpected_ids == ()
    assert error.value.diagnostics.reordered is True
    assert error.value.diagnostics.malformed_placeholder_count == 0


@pytest.mark.parametrize(
    ("response", "duplicate_ids", "unexpected_ids", "malformed_count"),
    [
        (
            "__AMICITED_PROTECTED_0000__ "
            "__AMICITED_PROTECTED_0000__ "
            "__AMICITED_PROTECTED_0001__",
            ("0000",),
            (),
            0,
        ),
        (
            "__AMICITED_PROTECTED_0000__ "
            "__AMICITED_PROTECTED_9999__ "
            "__AMICITED_PROTECTED_0001__",
            (),
            ("9999",),
            0,
        ),
        (
            "__AMICITED_PROTECTED_0000__ "
            "__AMICITED_PROTECTED_00X1__",
            (),
            (),
            1,
        ),
    ],
)
def test_semantic_layer_reports_sanitized_placeholder_mismatch_details(
    response: str,
    duplicate_ids: tuple[str, ...],
    unexpected_ids: tuple[str, ...],
    malformed_count: int,
) -> None:
    class InvalidProtectedSpans:
        def invoke(self, messages: object) -> FakeMessage:
            return FakeMessage(response)

    layer = SemanticRewriteLayer(
        model="openai:test-model",
        chat_model=InvalidProtectedSpans(),
    )

    with pytest.raises(ProtectedSpanError) as error:
        layer.rewrite("Read https://example.com before 42.")

    diagnostics = error.value.diagnostics
    assert diagnostics.expected_count == 2
    assert diagnostics.duplicate_ids == duplicate_ids
    assert diagnostics.unexpected_ids == unexpected_ids
    assert diagnostics.malformed_placeholder_count == malformed_count
    assert "https://example.com" not in str(error.value)


def test_protected_span_failure_is_fail_closed_and_content_safe_by_default() -> None:
    sentinel = "SENTINEL-private-article-body"

    class DropsLastProtectedSpan:
        def invoke(self, messages: object) -> FakeMessage:
            return FakeMessage(
                f"{sentinel} rewritten __AMICITED_PROTECTED_0000__"
            )

    sdk = watermark.Watermark(
        layers=(
            SemanticRewriteLayer(
                model="openai:test-model",
                chat_model=DropsLastProtectedSpan(),
            ),
        )
    )
    original = f"{sentinel} https://example.com 42"

    report = sdk.rewrite(watermark.WatermarkInput.text(original))

    assert report.transformation_status == "failed"
    assert report.changed is False
    assert report.transformed_text == original
    assert report.results[0].protected_spans_preserved is False
    assert report.results[0].protected_span_diagnostics is not None
    assert report.results[0].protected_span_diagnostics.missing_ids == ("0001",)

    serialized = report.to_json()
    payload = json.loads(serialized)
    assert sentinel not in serialized
    assert payload["content_included"] is False
    assert payload["input"]["content_included"] is False
    assert payload["transformed_text"] is None
    assert all(result["text"] is None for result in payload["results"])

    included = report.to_dict(include_content=True)
    assert included["content_included"] is True
    assert included["input"]["content_included"] is True
    assert included["transformed_text"] == original


def test_large_markdown_prompt_declares_and_preserves_all_protected_spans() -> None:
    fake = FakeChatModel(replacement=("Original prose", "Rewritten prose"))
    layer = SemanticRewriteLayer(
        model="openai:test-model",
        chat_model=fake,
    )
    original = "\n".join(
        f"## Section\n\nOriginal prose with value {index}."
        for index in range(100)
    )

    result = layer.rewrite(original)

    assert result.protected_spans_preserved is True
    assert result.text.count("Rewritten prose") == 100
    assert result.text.count("value") == 100
    assert "exactly 100 protected placeholders" in str(fake.requests[0])


@pytest.mark.parametrize(
    ("model", "provider", "environment_variable"),
    [
        ("openai:gpt-test", "openai", "OPENAI_API_KEY"),
        ("anthropic:claude-test", "anthropic", "ANTHROPIC_API_KEY"),
        ("google_genai:gemini-test", "google_genai", "GOOGLE_API_KEY"),
    ],
)
def test_known_provider_credentials_are_validated(
    monkeypatch: pytest.MonkeyPatch,
    model: str,
    provider: str,
    environment_variable: str,
) -> None:
    monkeypatch.delenv(environment_variable, raising=False)
    layer = SemanticRewriteLayer(model=model, chat_model=FakeChatModel())

    with pytest.raises(MissingModelCredentialError) as error:
        layer.validate_configuration()

    assert error.value.provider == provider
    assert error.value.environment_variable == environment_variable


def test_langchain_model_receives_public_configuration_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    fake = FakeChatModel(replacement=("Original.", "Rewritten."))

    def factory(**kwargs: Any) -> FakeChatModel:
        captured.update(kwargs)
        return fake

    monkeypatch.setenv("OPENAI_API_KEY", "secret-key")
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic._init_chat_model",
        factory,
    )

    report = watermark.rewrite(
        watermark.WatermarkInput.text("Original."),
        model="test-model",
        model_provider="openai",
        base_url="https://models.example/v1",
    )

    assert report.transformed_text == "Rewritten."
    assert captured == {
        "model": "test-model",
        "model_provider": "openai",
        "temperature": 0.7,
        "base_url": "https://models.example/v1",
    }
    assert "secret-key" not in report.to_json()


def test_semantic_provider_options_require_a_model() -> None:
    with pytest.raises(ModelConfigurationError, match="require model"):
        watermark.rewrite(
            watermark.WatermarkInput.text("text"),
            model_provider="openai",
        )


def test_ambiguous_model_name_is_a_typed_configuration_failure() -> None:
    with pytest.raises(ModelConfigurationError, match="ambiguous"):
        watermark.rewrite(
            watermark.WatermarkInput.text("text"),
            model="custom-model",
        )


@pytest.mark.parametrize("provider", (SemanticProvider.CODEX, SemanticProvider.CLAUDE))
def test_cli_provider_fails_before_reading_input_when_binary_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    provider: SemanticProvider,
) -> None:
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic.shutil.which",
        lambda executable: None,
    )
    missing_input = tmp_path / "also-missing.txt"

    with pytest.raises(ModelCLIUnavailableError) as error:
        watermark.rewrite(
            watermark.WatermarkInput.file(missing_input),
            provider=provider,
        )

    assert error.value.provider == provider.value
    assert str(missing_input) not in str(error.value)


def test_codex_cli_provider_uses_isolated_file_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], str, str]] = []
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic.shutil.which",
        lambda executable: "/test/bin/codex" if executable == "codex" else None,
    )

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        prompt = kwargs["input"]
        calls.append((command, prompt, kwargs["cwd"]))
        workspace = Path(kwargs["cwd"])
        protected_text = (workspace / "amicited-protected-input.md").read_text(
            encoding="utf-8"
        )
        (workspace / "amicited-rewritten-output.md").write_text(
            protected_text.replace("Original sentence.", "Codex rewrite."),
            encoding="utf-8",
        )
        Path(command[command.index("--output-last-message") + 1]).write_text(
            "Rewrite file created.", encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0, stdout="progress", stderr="")

    monkeypatch.setattr("amicited.watermark.layers.semantic.subprocess.run", run)

    report = watermark.rewrite(
        watermark.WatermarkInput.text("Original sentence."),
        provider=SemanticProvider.CODEX,
        model="gpt-test",
    )

    assert report.transformed_text == "Codex rewrite."
    assert report.results[-1].execution_provider == "codex"
    assert report.results[-1].provider == "codex"
    command, prompt, cwd = calls[0]
    assert command[:2] == ["/test/bin/codex", "exec"]
    assert "--ephemeral" in command
    assert command[command.index("--sandbox") + 1] == "workspace-write"
    assert "--skip-git-repo-check" in command
    assert command[command.index("--model") + 1] == "gpt-test"
    assert command[-1] == "-"
    assert "amicited-protected-input.md" in prompt
    assert "amicited-rewritten-output.md" in prompt
    assert "Original sentence." not in prompt
    assert "Original sentence." not in command
    assert Path(cwd).is_absolute()


def test_claude_cli_provider_uses_restricted_file_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], str, str]] = []
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic.shutil.which",
        lambda executable: "/test/bin/claude" if executable == "claude" else None,
    )

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        prompt = kwargs["input"]
        calls.append((command, prompt, kwargs["cwd"]))
        workspace = Path(kwargs["cwd"])
        protected_text = (workspace / "amicited-protected-input.md").read_text(
            encoding="utf-8"
        )
        (workspace / "amicited-rewritten-output.md").write_text(
            protected_text.replace("Original sentence.", "Claude rewrite."),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {"type": "result", "is_error": False, "result": "File written."}
            ),
            stderr="",
        )

    monkeypatch.setattr("amicited.watermark.layers.semantic.subprocess.run", run)

    report = watermark.rewrite(
        watermark.WatermarkInput.text("Original sentence."),
        provider=SemanticProvider.CLAUDE,
        model="sonnet",
    )

    assert report.transformed_text == "Claude rewrite."
    assert report.results[-1].execution_provider == "claude"
    assert report.results[-1].provider == "claude"
    command, prompt, cwd = calls[0]
    assert command[:2] == ["/test/bin/claude", "-p"]
    assert "--safe-mode" in command
    assert "--no-session-persistence" in command
    assert command[command.index("--output-format") + 1] == "json"
    assert command[command.index("--tools") + 1] == "Read,Write"
    assert command[command.index("--allowedTools") + 1] == "Read,Write"
    assert command[command.index("--model") + 1] == "sonnet"
    assert "amicited-protected-input.md" in prompt
    assert "amicited-rewritten-output.md" in prompt
    assert "Original sentence." not in prompt
    assert "Original sentence." not in command
    assert Path(cwd).is_absolute()


@pytest.mark.parametrize(
    ("stderr", "category"),
    [
        ("You've hit your usage limit · resets 8pm", "usage_exhausted"),
        ("You've hit your weekly limit · resets Friday", "usage_exhausted"),
        ("Credit balance is too low", "usage_exhausted"),
        ("Not logged in. Please run claude auth login", "authentication_failed"),
        ("Unexpected provider crash with private details", "cli_failed"),
    ],
)
def test_cli_provider_classifies_failures_without_leaking_output(
    monkeypatch: pytest.MonkeyPatch,
    stderr: str,
    category: str,
) -> None:
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic.shutil.which",
        lambda executable: "/test/bin/claude",
    )
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 1, stdout="", stderr=stderr
        ),
    )

    report = watermark.rewrite(
        watermark.WatermarkInput.text("private input"),
        provider=SemanticProvider.CLAUDE,
    )

    assert report.transformation_status == "failed"
    assert report.transformed_text == "private input"
    assert report.results[-1].error_category == category
    assert stderr not in report.to_json()
    assert "private input" not in report.results[-1].errors[0]


def test_claude_structured_error_with_zero_exit_is_still_classified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic.shutil.which",
        lambda executable: "/test/bin/claude",
    )
    output = json.dumps(
        {
            "type": "result",
            "is_error": True,
            "result": "You've hit your weekly limit · resets later",
        }
    )
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout=output, stderr=""
        ),
    )

    report = watermark.rewrite(
        watermark.WatermarkInput.text("private input"),
        provider=SemanticProvider.CLAUDE,
    )

    assert report.transformation_status == "failed"
    assert report.results[-1].error_category == "usage_exhausted"
    assert "weekly limit" not in report.to_json()


def test_cli_provider_timeout_is_structured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic.shutil.which",
        lambda executable: "/test/bin/codex",
    )

    def timeout(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr("amicited.watermark.layers.semantic.subprocess.run", timeout)

    report = watermark.rewrite(
        watermark.WatermarkInput.text("private input"),
        provider=SemanticProvider.CODEX,
        cli_timeout=0.1,
    )

    assert report.transformation_status == "failed"
    assert report.results[-1].error_category == "timeout"
    assert report.transformed_text == "private input"


@pytest.mark.parametrize("provider", (SemanticProvider.CODEX, SemanticProvider.CLAUDE))
def test_cli_provider_empty_output_is_a_failure(
    monkeypatch: pytest.MonkeyPatch,
    provider: SemanticProvider,
) -> None:
    executable = provider.value
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic.shutil.which",
        lambda name: f"/test/bin/{executable}",
    )

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        workspace = Path(kwargs["cwd"])
        (workspace / "amicited-rewritten-output.md").write_text("", encoding="utf-8")
        if provider is SemanticProvider.CODEX:
            message_path = Path(
                command[command.index("--output-last-message") + 1]
            )
            message_path.write_text("File written.", encoding="utf-8")
            output = ""
        else:
            output = json.dumps(
                {"type": "result", "is_error": False, "result": "File written."}
            )
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    monkeypatch.setattr("amicited.watermark.layers.semantic.subprocess.run", run)

    report = watermark.rewrite(
        watermark.WatermarkInput.text("private input"),
        provider=provider,
    )

    assert report.transformation_status == "failed"
    assert report.results[-1].error_category == "empty_output"
    assert report.transformed_text == "private input"


@pytest.mark.parametrize("provider", (SemanticProvider.CODEX, SemanticProvider.CLAUDE))
def test_cli_provider_missing_rewrite_file_is_a_failure(
    monkeypatch: pytest.MonkeyPatch,
    provider: SemanticProvider,
) -> None:
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic.shutil.which",
        lambda name: f"/test/bin/{provider.value}",
    )

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if provider is SemanticProvider.CODEX:
            output = ""
        else:
            output = json.dumps(
                {"type": "result", "is_error": False, "result": "File written."}
            )
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    monkeypatch.setattr("amicited.watermark.layers.semantic.subprocess.run", run)

    report = watermark.rewrite(
        watermark.WatermarkInput.text("private input"),
        provider=provider,
    )

    assert report.transformation_status == "failed"
    assert report.results[-1].error_category == "invalid_output"
    assert "required rewrite output file" in report.results[-1].errors[0]
    assert "private input" not in report.to_json()


def test_claude_cli_malformed_json_is_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic.shutil.which",
        lambda name: "/test/bin/claude",
    )
    monkeypatch.setattr(
        "amicited.watermark.layers.semantic.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout="not-json", stderr=""
        ),
    )

    report = watermark.rewrite(
        watermark.WatermarkInput.text("private input"),
        provider=SemanticProvider.CLAUDE,
    )

    assert report.transformation_status == "failed"
    assert report.results[-1].error_category == "invalid_output"
    assert "not-json" not in report.to_json()


def test_api_only_options_are_rejected_for_cli_providers() -> None:
    with pytest.raises(ModelConfigurationError, match="API provider"):
        watermark.rewrite(
            watermark.WatermarkInput.text("text"),
            provider=SemanticProvider.CODEX,
            model_provider="openai",
        )
