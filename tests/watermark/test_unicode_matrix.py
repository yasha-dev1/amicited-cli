import pytest

from amicited import watermark
from amicited.watermark.layers import (
    BidiControlLayer,
    ExoticSpaceLayer,
    HiddenUnicodeLayer,
    UnicodeTagLayer,
)
from amicited.watermark.models import RecommendedAction, VerificationStatus

REMOVABLE_HIDDEN = (
    "\u0000",
    "\u0007",
    "\u000b",
    "\u001f",
    "\u007f",
    "\u009f",
    "\u00ad",
    "\u034f",
    "\u180e",
    "\u200b",
    "\u200c",
    "\u200d",
)

PRESERVED_HIDDEN = (
    "\u2060",
    "\u2061",
    "\u2062",
    "\u2063",
    "\u2064",
    "\ufe0e",
    "\ufe0f",
    "\U000e0100",
)

BIDI_CONTROLS = (
    "\u061c",
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
)

EXOTIC_SPACES = (
    "\u00a0",
    "\u1680",
    "\u2000",
    "\u2001",
    "\u2002",
    "\u2003",
    "\u2004",
    "\u2005",
    "\u2006",
    "\u2007",
    "\u2008",
    "\u2009",
    "\u200a",
    "\u202f",
    "\u205f",
    "\u3000",
)


@pytest.mark.parametrize("character", REMOVABLE_HIDDEN)
def test_every_declared_removable_hidden_character_is_detected_and_removed(
    character: str,
) -> None:
    layer = HiddenUnicodeLayer()
    text = f"a{character}b"

    assert layer.verify(text).status is VerificationStatus.DETECTED
    assert layer.rewrite(text).text == "ab"


@pytest.mark.parametrize("character", PRESERVED_HIDDEN)
def test_context_sensitive_hidden_characters_are_detected_but_preserved(
    character: str,
) -> None:
    layer = HiddenUnicodeLayer()
    text = f"a{character}b"

    inspection = layer.inspect(text)

    assert inspection.findings[0].recommended_action is RecommendedAction.PRESERVE
    assert layer.verify(text).status is VerificationStatus.DETECTED
    assert layer.rewrite(text).text == text


@pytest.mark.parametrize("character", BIDI_CONTROLS)
def test_every_supported_bidi_control_is_removed_from_ltr_text(
    character: str,
) -> None:
    layer = BidiControlLayer()
    text = f"left{character}right"

    assert layer.verify(text).status is VerificationStatus.DETECTED
    assert layer.rewrite(text).text == "leftright"


@pytest.mark.parametrize("character", EXOTIC_SPACES)
def test_every_supported_exotic_space_maps_one_for_one(character: str) -> None:
    layer = ExoticSpaceLayer()

    result = layer.rewrite(f"a{character}{character}b")

    assert result.text == "a  b"
    assert len(result.changes) == 2


@pytest.mark.parametrize("value", (0xE0000, 0xE0001, 0xE0020, 0xE007E, 0xE007F))
def test_standalone_unicode_tag_boundaries_are_detected_and_removed(
    value: int,
) -> None:
    layer = UnicodeTagLayer()
    character = chr(value)

    assert layer.verify(character).status is VerificationStatus.DETECTED
    assert layer.rewrite(character).text == ""


def test_rewrite_is_deterministic_and_idempotent_for_sanitizable_input() -> None:
    original = "a\u200b\u202eb\u00a0\U000e0063c"

    first = watermark.rewrite(watermark.WatermarkInput.text(original))
    repeated = watermark.rewrite(watermark.WatermarkInput.text(original))
    second_pass = watermark.rewrite(
        watermark.WatermarkInput.text(first.transformed_text)
    )

    assert first.transformed_text == "ab c"
    assert repeated.transformed_text == first.transformed_text
    assert [change.to_dict() for change in repeated.changes] == [
        change.to_dict() for change in first.changes
    ]
    assert second_pass.changed is False
    assert second_pass.changes == ()
    assert second_pass.after_verification.status is VerificationStatus.NOT_DETECTED


def test_rewrite_preserves_markdown_code_frontmatter_and_crlf() -> None:
    original = (
        "---\r\ntitle: A\u00a0Title\r\n---\r\n"
        "# Heading\r\n\r\n`x\u200by` and [link](https://example.com/a_b)\r\n"
        "```python\r\nvalue = 'a  b'\r\n```\r\n"
    )

    report = watermark.rewrite(watermark.WatermarkInput.text(original))

    assert report.transformed_text == (
        "---\r\ntitle: A Title\r\n---\r\n"
        "# Heading\r\n\r\n`xy` and [link](https://example.com/a_b)\r\n"
        "```python\r\nvalue = 'a  b'\r\n```\r\n"
    )
    assert report.transformed_text.count("\r\n") == original.count("\r\n")
    assert "a  b" in report.transformed_text


def test_unicode_normalization_is_never_applied_implicitly() -> None:
    decomposed = "Cafe\u0301"

    report = watermark.rewrite(watermark.WatermarkInput.text(decomposed))

    assert report.transformed_text == decomposed
    assert report.changed is False
