"""Deterministic inspection and sanitation of hidden Unicode characters."""

from __future__ import annotations

import unicodedata

from amicited.watermark.layers._unicode import (
    finding,
    inspection,
    rewrite_characters,
    verification,
)
from amicited.watermark.layers.base import TextWatermarkLayer
from amicited.watermark.models import (
    AuthorityLevel,
    CapabilityDeclaration,
    LayerInspectionResult,
    LayerRewriteResult,
    LayerVerificationResult,
    RecommendedAction,
    RiskLevel,
)

_REMOVABLE = {
    0x00AD,  # soft hyphen
    0x200B,  # zero width space
}
_CONTEXT_SENSITIVE = {
    0x034F,  # combining grapheme joiner
    0x115F,  # Hangul choseong filler
    0x1160,  # Hangul jungseong filler
    0x17B4,  # Khmer vowel inherent AQ
    0x17B5,  # Khmer vowel inherent AA
    0x180B,  # Mongolian free variation selector one
    0x180C,
    0x180D,
    0x180E,  # Mongolian vowel separator (deprecated)
    0x200C,  # zero width non-joiner
    0x200D,  # zero width joiner
    0x2060,  # word joiner
    0x2061,  # function application
    0x2062,  # invisible times
    0x2063,  # invisible separator
    0x2064,  # invisible plus
    0xFFF9,  # interlinear annotation anchor
    0xFFFA,  # interlinear annotation separator
    0xFFFB,  # interlinear annotation terminator
}
_BIDI_CONTROLS = {
    0x061C,
    0x200E,
    0x200F,
    *range(0x202A, 0x202F),
    *range(0x2066, 0x2070),
}
_SCRIPT_CONTEXT = {
    0x115F: "HANGUL",
    0x1160: "HANGUL",
    0x17B4: "KHMER",
    0x17B5: "KHMER",
    0x180B: "MONGOLIAN",
    0x180C: "MONGOLIAN",
    0x180D: "MONGOLIAN",
    0x180E: "MONGOLIAN",
}
_JOINER_SCRIPTS = (
    "ARABIC",
    "BENGALI",
    "DEVANAGARI",
    "GUJARATI",
    "GURMUKHI",
    "KANNADA",
    "MALAYALAM",
    "ORIYA",
    "SINHALA",
    "TAMIL",
    "TELUGU",
)


def _is_variation_selector(value: int) -> bool:
    return 0xFE00 <= value <= 0xFE0F or 0xE0100 <= value <= 0xE01EF


def _is_relevant_control(value: int) -> bool:
    return (
        0x00 <= value <= 0x08
        or value in {0x0B, 0x0C}
        or 0x0E <= value <= 0x1F
        or (0x7F <= value <= 0x9F and value != 0x85)
    )


def _is_owned(value: int) -> bool:
    if value in _BIDI_CONTROLS or 0xE0000 <= value <= 0xE007F:
        return False
    return (
        value in _REMOVABLE
        or value in _CONTEXT_SENSITIVE
        or value == 0xFEFF
        or _is_variation_selector(value)
        or _is_relevant_control(value)
        or unicodedata.category(chr(value)) == "Cf"
    )


def _visible(character: str) -> bool:
    return (
        bool(character)
        and not character.isspace()
        and not unicodedata.category(character).startswith("C")
    )


def _has_named_neighbor(text: str, index: int, name: str) -> bool:
    neighbors = (
        text[index - 1] if index else "",
        text[index + 1] if index + 1 < len(text) else "",
    )
    return any(
        character and name in unicodedata.name(character, "") for character in neighbors
    )


def _balanced_interlinear_indices(text: str) -> set[int]:
    balanced: set[int] = set()
    anchor: int | None = None
    separator: int | None = None
    for index, character in enumerate(text):
        value = ord(character)
        if value == 0xFFF9:
            anchor = index
            separator = None
        elif value == 0xFFFA and anchor is not None:
            separator = index
        elif value == 0xFFFB and anchor is not None and separator is not None:
            balanced.update((anchor, separator, index))
            anchor = None
            separator = None
    return balanced


def _contextually_meaningful(text: str, index: int, interlinear: set[int]) -> bool:
    value = ord(text[index])
    previous = text[index - 1] if index else ""
    following = text[index + 1] if index + 1 < len(text) else ""
    if value in _SCRIPT_CONTEXT:
        return _has_named_neighbor(text, index, _SCRIPT_CONTEXT[value])
    if value in {0xFFF9, 0xFFFA, 0xFFFB}:
        return index in interlinear
    if value == 0x034F:
        return any(
            character and unicodedata.category(character).startswith("M")
            for character in (previous, following)
        )
    if value in {0x200C, 0x200D}:
        if not (_visible(previous) and _visible(following)):
            return False
        names = (
            unicodedata.name(previous, ""),
            unicodedata.name(following, ""),
        )
        language_context = any(
            script in name for script in _JOINER_SCRIPTS for name in names
        )
        emoji_context = any(
            unicodedata.category(character) in {"So", "Sk"}
            for character in (previous, following)
        )
        return language_context or emoji_context
    if value in {0x2060, 0x2061, 0x2062, 0x2063, 0x2064}:
        return _visible(previous) and _visible(following)
    if _is_variation_selector(value):
        return _visible(previous)
    return False


class HiddenUnicodeLayer(TextWatermarkLayer):
    """Find exact hidden characters and remove only context-safe artifacts."""

    id = "hidden_unicode"

    def __init__(self, *, strip_semantic_format: bool = False) -> None:
        self.strip_semantic_format = strip_semantic_format

    def _should_remove(self, text: str, index: int, interlinear: set[int]) -> bool:
        value = ord(text[index])
        if value in _REMOVABLE or _is_relevant_control(value):
            return True
        if value == 0xFEFF:
            return index != 0 or self.strip_semantic_format
        if value in _CONTEXT_SENSITIVE or _is_variation_selector(value):
            return self.strip_semantic_format or not _contextually_meaningful(
                text, index, interlinear
            )
        if unicodedata.category(text[index]) == "Cf":
            return self.strip_semantic_format
        return False

    def inspect(self, text: str) -> LayerInspectionResult:
        findings = []
        interlinear = _balanced_interlinear_indices(text)
        for index, character in enumerate(text):
            value = ord(character)
            if not _is_owned(value):
                continue
            removable = self._should_remove(text, index, interlinear)
            legitimate: tuple[str, ...]
            if value in {0x200C, 0x200D}:
                legitimate = (
                    "Arabic, Persian, and Indic shaping",
                    "emoji composition",
                )
            elif _is_variation_selector(value):
                legitimate = ("emoji and standardized glyph presentation",)
            elif value == 0xFEFF:
                legitimate = ("byte-order marker at the beginning of text",)
            elif value in {0x2061, 0x2062, 0x2063, 0x2064}:
                legitimate = ("mathematical notation",)
            elif value in _SCRIPT_CONTEXT:
                legitimate = (f"{_SCRIPT_CONTEXT[value].title()} script formatting",)
            elif value in {0xFFF9, 0xFFFA, 0xFFFB}:
                legitimate = ("balanced interlinear annotation formatting",)
            else:
                legitimate = ("formatting and language-specific text",)
            findings.append(
                finding(
                    layer_id=self.id,
                    text=text,
                    index=index,
                    category=(
                        "variation_selector"
                        if _is_variation_selector(value)
                        else "control"
                        if _is_relevant_control(value)
                        else "format"
                    ),
                    risk=RiskLevel.MEDIUM,
                    legitimate_uses=legitimate,
                    action=(
                        RecommendedAction.REMOVE
                        if removable
                        else RecommendedAction.PRESERVE
                    ),
                )
            )
        return inspection(self.id, tuple(findings))

    def verify(self, text: str) -> LayerVerificationResult:
        return verification(
            layer_id=self.id,
            findings=self.inspect(text).findings,
            interpretation="Exact presence of enumerated hidden Unicode characters.",
            limitations=(
                "Presence does not establish watermark intent or provider origin.",
                "Context-sensitive joiners and variation selectors are preserved.",
            ),
        )

    def rewrite(self, text: str) -> LayerRewriteResult:
        interlinear = _balanced_interlinear_indices(text)

        def replacement(index: int, character: str) -> str | None:
            if self._should_remove(text, index, interlinear):
                return ""
            return None

        return rewrite_characters(
            layer_id=self.id,
            text=text,
            replacement=replacement,
            reason="Removed an enumerated hidden Unicode artifact.",
        )

    def capability(self) -> CapabilityDeclaration:
        return CapabilityDeclaration(
            id=self.id,
            type="detector_and_strategy",
            signal_type=self.signal_type,
            modalities=(self.modality,),
            schemes=(),
            providers=(),
            authority=AuthorityLevel.HEURISTIC,
            requirements=(),
            network_required=False,
            deterministic=True,
            operations=("inspect", "verify", "remove", "rewrite"),
            limitations=(
                "Detects enumerated characters, not statistical text watermarks.",
                "Context-sensitive and unknown format characters are preserved by default.",
            ),
        )
