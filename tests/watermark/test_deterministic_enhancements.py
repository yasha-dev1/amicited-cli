import pytest

from amicited import watermark
from amicited.watermark.layers import (
    BidiControlLayer,
    ConfusableLayer,
    HiddenUnicodeLayer,
    UnicodeNormalizationLayer,
    WhitespacePatternLayer,
)
from amicited.watermark.models import RecommendedAction, VerificationStatus


@pytest.mark.parametrize(
    "character",
    (
        "\u115f",
        "\u1160",
        "\u17b4",
        "\u17b5",
        "\u180b",
        "\u180c",
        "\u180d",
        "\ufff9",
        "\ufffa",
        "\ufffb",
    ),
)
def test_additional_format_characters_are_inspected(character: str) -> None:
    report = HiddenUnicodeLayer().inspect(f"a{character}b")

    assert len(report.findings) == 1
    assert report.findings[0].code_point == f"U+{ord(character):04X}"


def test_orphan_semantic_controls_are_removed_but_real_context_is_preserved() -> None:
    layer = HiddenUnicodeLayer()
    orphaned = "a\u034fb a\u200cb \ufe0f \u180b"
    legitimate = "a\u0301\u034f\u0300 می\u200cخواهم ❤\ufe0f ᠠ\u180bᠡ"

    orphan_result = layer.rewrite(orphaned)
    legitimate_result = layer.rewrite(legitimate)

    assert orphan_result.text == "ab ab  "
    assert legitimate_result.text == legitimate
    assert legitimate_result.changes == ()


def test_script_fillers_and_interlinear_annotations_use_context() -> None:
    layer = HiddenUnicodeLayer()
    legitimate = "ᄀ\u115fᅡ ក\u17b4ខ \ufff9term\ufffagloss\ufffb"

    assert layer.rewrite(legitimate).text == legitimate
    assert layer.rewrite("x\u115fy\u17b4z\ufff9").text == "xyz"


def test_aggressive_hidden_cleanup_strips_even_semantic_formatting() -> None:
    text = "می\u200cخواهم ❤\ufe0f ᠠ\u180bᠡ"

    result = HiddenUnicodeLayer(strip_semantic_format=True).rewrite(text)

    assert result.text == "میخواهم ❤ ᠠᠡ"
    assert len(result.changes) == 3


def test_balanced_bidi_pairs_are_preserved_and_orphans_are_removed() -> None:
    layer = BidiControlLayer()
    balanced = "prefix \u2067مرحبا\u2069 suffix"
    unbalanced = "prefix \u2067مرحبا suffix"

    assert layer.rewrite(balanced).text == balanced
    assert layer.rewrite(unbalanced).text == "prefix مرحبا suffix"


def test_directional_marks_require_a_real_ltr_rtl_transition() -> None:
    layer = BidiControlLayer()

    assert layer.rewrite("English\u200fعربي").text == "English\u200fعربي"
    assert layer.rewrite("عربي text\u200f end").text == "عربي text end"


@pytest.mark.parametrize("value", range(0x206A, 0x2070))
def test_deprecated_bidi_controls_are_detected_and_removed(value: int) -> None:
    layer = BidiControlLayer()
    character = chr(value)

    assert layer.verify(character).status is VerificationStatus.DETECTED
    assert layer.rewrite(character).text == ""


def test_confusables_are_reported_only_when_potentially_ambiguous() -> None:
    layer = ConfusableLayer()

    mixed = layer.inspect("pаypal ＡBC")
    cyrillic = layer.inspect("мама")

    assert [finding.code_point for finding in mixed.findings] == [
        "U+0430",
        "U+FF21",
    ]
    assert all(
        finding.recommended_action is RecommendedAction.REVIEW
        for finding in mixed.findings
    )
    assert cyrillic.findings == ()


def test_confusable_mapping_requires_explicit_configuration() -> None:
    text = "pаypal ＡBC"

    assert ConfusableLayer().rewrite(text).text == text
    assert ConfusableLayer(map_confusables=True).rewrite(text).text == "paypal ABC"


def test_normalization_differences_are_inspected_but_not_changed_by_default() -> None:
    text = "Cafe\u0301 and Ａ"
    layer = UnicodeNormalizationLayer()

    inspection = layer.inspect(text)
    rewrite = layer.rewrite(text)

    assert {finding.category for finding in inspection.findings} == {
        "canonical_normalization_difference",
        "compatibility_normalization_difference",
    }
    assert rewrite.text == text
    assert rewrite.changes == ()


@pytest.mark.parametrize(
    ("form", "expected"),
    [
        (watermark.NormalizationForm.NFC, "Café and Ａ"),
        (watermark.NormalizationForm.NFKC, "Café and A"),
    ],
)
def test_normalization_can_be_selected_explicitly(
    form: watermark.NormalizationForm, expected: str
) -> None:
    options = watermark.DeterministicOptions(normalization=form)

    report = watermark.rewrite(
        watermark.WatermarkInput.text("Cafe\u0301 and Ａ"),
        options=options,
    )

    assert report.transformed_text == expected
    assert any(change.layer_id == "unicode_normalization" for change in report.changes)


def test_sdk_options_control_all_aggressive_deterministic_strategies() -> None:
    text = "a\u200cb pаypal Ａ\u00a0B"
    options = watermark.DeterministicOptions(
        strip_semantic_format=True,
        map_confusables=True,
        normalize_spaces=False,
    )

    report = watermark.remove(watermark.WatermarkInput.text(text), options=options)

    assert report.transformed_text == "ab paypal A\u00a0B"
    assert [result.layer_id for result in report.results] == [
        "hidden_unicode",
        "bidi_controls",
        "unicode_tags",
        "exotic_spaces",
        "confusables",
        "unicode_normalization",
        "whitespace_patterns",
    ]


def test_whitespace_patterns_are_reported_but_never_collapsed() -> None:
    text = "aligned  text\t value\u2028next"
    layer = WhitespacePatternLayer()

    inspection = layer.inspect(text)
    rewrite = layer.rewrite(text)

    assert [finding.category for finding in inspection.findings] == [
        "repeated_whitespace",
        "mixed_whitespace",
        "nonstandard_line_separator",
    ]
    assert rewrite.text == text
    assert rewrite.changes == ()
