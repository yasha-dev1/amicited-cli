from amicited.watermark.layers import (
    BidiControlLayer,
    ExoticSpaceLayer,
    HiddenUnicodeLayer,
    TextWatermarkLayer,
    UnicodeTagLayer,
)
from amicited.watermark.models import RecommendedAction, VerificationStatus


def test_all_builtin_layers_implement_the_public_layer_interface() -> None:
    for layer_type in (
        HiddenUnicodeLayer,
        BidiControlLayer,
        UnicodeTagLayer,
        ExoticSpaceLayer,
    ):
        assert issubclass(layer_type, TextWatermarkLayer)
        assert layer_type().modality == "text"


def test_hidden_unicode_reports_exact_utf8_and_code_point_positions() -> None:
    result = HiddenUnicodeLayer().inspect("éA\u200bB")

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.code_point == "U+200B"
    assert finding.unicode_name == "ZERO WIDTH SPACE"
    assert finding.position.code_point_index == 2
    assert finding.position.byte_offset == 3
    assert "⟦U+200B⟧" in finding.context
    assert finding.recommended_action is RecommendedAction.REMOVE


def test_hidden_unicode_rewrite_is_conservative_and_reviewable() -> None:
    text = "\ufeffA\u200bB\u00adC\u200cD\u200dE\ufeff"

    result = HiddenUnicodeLayer().rewrite(text)

    assert result.text == "\ufeffABCDE"
    assert [change.before for change in result.changes] == [
        "\u200b",
        "\u00ad",
        "\u200c",
        "\u200d",
        "\ufeff",
    ]
    assert all(change.after == "" for change in result.changes)


def test_joiners_are_detected_but_preserved_for_language_and_emoji_safety() -> None:
    text = "می\u200cخواهم 👩\u200d💻"
    layer = HiddenUnicodeLayer()

    inspection = layer.inspect(text)
    rewrite = layer.rewrite(text)

    assert {finding.code_point for finding in inspection.findings} == {
        "U+200C",
        "U+200D",
    }
    assert all(
        finding.recommended_action is RecommendedAction.PRESERVE
        for finding in inspection.findings
    )
    assert rewrite.text == text
    assert rewrite.changes == ()


def test_bidi_controls_are_removed_from_ltr_text_but_preserved_in_rtl_text() -> None:
    layer = BidiControlLayer()

    unsafe = layer.rewrite("invoice\u202egnp.exe")
    legitimate = layer.rewrite("مرحبا\u200fEnglish")

    assert unsafe.text == "invoicegnp.exe"
    assert len(unsafe.changes) == 1
    assert legitimate.text == "مرحبا\u200fEnglish"
    assert legitimate.changes == ()


def test_unicode_tags_are_removed_unless_they_form_an_emoji_tag_sequence() -> None:
    layer = UnicodeTagLayer()
    unattached = "a\U000e0062b"
    subdivision_flag = (
        "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f"
    )

    unattached_inspection = layer.inspect(unattached)
    assert layer.rewrite(unattached).text == "ab"
    assert unattached_inspection.findings[0].code_point == "U+E0062"
    preserved = layer.rewrite(subdivision_flag)
    assert preserved.text == subdivision_flag
    assert preserved.changes == ()
    assert all(
        finding.recommended_action is RecommendedAction.PRESERVE
        for finding in layer.inspect(subdivision_flag).findings
    )


def test_exotic_spaces_are_mapped_without_collapsing_or_changing_line_endings() -> None:
    text = "a\u00a0\u2007b\r\nc\u3000d"

    result = ExoticSpaceLayer().rewrite(text)

    assert result.text == "a  b\r\nc d"
    assert len(result.changes) == 3


def test_each_layer_verifies_only_the_signal_it_owns() -> None:
    assert (
        HiddenUnicodeLayer().verify("plain text").status
        is VerificationStatus.NOT_DETECTED
    )
    assert ExoticSpaceLayer().verify("a\u00a0b").status is VerificationStatus.DETECTED
