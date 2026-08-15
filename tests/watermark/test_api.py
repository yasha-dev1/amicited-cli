import json
from pathlib import Path

from amicited import watermark
from amicited.watermark.models import VerificationStatus


def test_default_sdk_inspects_verifies_and_rewrites_deterministic_signals() -> None:
    input_data = watermark.WatermarkInput.text("hello\u200bworld\u00a0")

    inspection = watermark.inspect(input_data)
    verification = watermark.verify(input_data)
    rewrite = watermark.rewrite(input_data)

    assert [finding.code_point for finding in inspection.findings] == [
        "U+200B",
        "U+00A0",
    ]
    assert verification.status is VerificationStatus.DETECTED
    assert rewrite.transformed_text == "helloworld "
    assert rewrite.changed is True
    assert rewrite.after_verification.status is VerificationStatus.NOT_DETECTED
    assert input_data.content == "hello\u200bworld\u00a0"


def test_remove_uses_the_same_deterministic_pipeline_but_reports_its_operation() -> (
    None
):
    report = watermark.remove(watermark.WatermarkInput.text("a\u200bb"))

    assert report.operation == "remove"
    assert report.transformed_text == "ab"
    assert report.changed is True


def test_file_input_is_read_as_utf8_without_modifying_the_original(
    tmp_path: Path,
) -> None:
    source = tmp_path / "article.txt"
    source.write_bytes("a\u3000b\r\n".encode())

    report = watermark.rewrite(watermark.WatermarkInput.file(source))

    assert report.transformed_text == "a b\r\n"
    assert source.read_bytes() == "a\u3000b\r\n".encode()
    assert report.input.path == str(source)


def test_reports_have_a_versioned_machine_readable_shape() -> None:
    report = watermark.inspect(watermark.WatermarkInput.text("a\u200bb"))

    serialized = json.loads(report.to_json())

    assert serialized["schema_version"] == "1.0"
    assert serialized["operation"] == "inspect"
    assert serialized["input"]["content_included"] is False
    assert serialized["results"][0]["layer_id"] == "hidden_unicode"
    assert serialized["findings"][0]["position"]["code_point_index"] == 1


def test_capabilities_are_static_and_text_only() -> None:
    report = watermark.capabilities()

    assert [capability.id for capability in report.capabilities] == [
        "hidden_unicode",
        "bidi_controls",
        "unicode_tags",
        "exotic_spaces",
        "confusables",
        "unicode_normalization",
        "whitespace_patterns",
        "semantic_rewrite",
    ]
    assert all(capability.modalities == ("text",) for capability in report.capabilities)
    assert report.capabilities[-1].network_required is True
    assert report.capabilities[-1].deterministic is False
    assert report.capabilities[-1].execution_providers == (
        "api",
        "codex",
        "claude",
    )
