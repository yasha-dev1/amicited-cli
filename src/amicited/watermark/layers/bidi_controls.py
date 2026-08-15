"""Deterministic handling of bidirectional control characters."""

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

_BIDI_CONTROLS = {
    0x061C,
    0x200E,
    0x200F,
    0x202A,
    0x202B,
    0x202C,
    0x202D,
    0x202E,
    0x2066,
    0x2067,
    0x2068,
    0x2069,
    0x206A,
    0x206B,
    0x206C,
    0x206D,
    0x206E,
    0x206F,
}
_EMBED_OPEN = {0x202A, 0x202B, 0x202D, 0x202E}
_ISOLATE_OPEN = {0x2066, 0x2067, 0x2068}
_DEPRECATED = set(range(0x206A, 0x2070))


def _balanced_indices(text: str) -> set[int]:
    stack: list[tuple[str, int]] = []
    balanced: set[int] = set()
    for index, character in enumerate(text):
        value = ord(character)
        if value in _EMBED_OPEN:
            stack.append(("embed", index))
        elif value in _ISOLATE_OPEN:
            stack.append(("isolate", index))
        elif value == 0x202C and stack and stack[-1][0] == "embed":
            _, start = stack.pop()
            balanced.update((start, index))
        elif value == 0x2069 and stack and stack[-1][0] == "isolate":
            _, start = stack.pop()
            balanced.update((start, index))
    return balanced


def _is_direction_transition(text: str, index: int) -> bool:
    previous = text[index - 1] if index else ""
    following = text[index + 1] if index + 1 < len(text) else ""
    if not previous or not following or previous.isspace() or following.isspace():
        return False
    left = unicodedata.bidirectional(previous)
    right = unicodedata.bidirectional(following)
    rtl = {"R", "AL", "AN"}
    ltr = {"L", "EN"}
    return (left in rtl and right in ltr) or (left in ltr and right in rtl)


class BidiControlLayer(TextWatermarkLayer):
    """Remove bidi controls from LTR-only paragraphs and preserve RTL text."""

    id = "bidi_controls"

    def __init__(self, *, strip_semantic_format: bool = False) -> None:
        self.strip_semantic_format = strip_semantic_format

    def _should_remove(self, text: str, index: int, balanced: set[int]) -> bool:
        value = ord(text[index])
        if self.strip_semantic_format or value in _DEPRECATED:
            return True
        if value in {0x061C, 0x200E, 0x200F}:
            return not _is_direction_transition(text, index)
        return index not in balanced

    def inspect(self, text: str) -> LayerInspectionResult:
        balanced = _balanced_indices(text)
        findings = tuple(
            finding(
                layer_id=self.id,
                text=text,
                index=index,
                category="bidirectional_control",
                risk=RiskLevel.HIGH,
                legitimate_uses=("bidirectional and right-to-left text",),
                action=(
                    RecommendedAction.REMOVE
                    if self._should_remove(text, index, balanced)
                    else RecommendedAction.PRESERVE
                ),
            )
            for index, character in enumerate(text)
            if ord(character) in _BIDI_CONTROLS
        )
        return inspection(self.id, findings)

    def verify(self, text: str) -> LayerVerificationResult:
        return verification(
            layer_id=self.id,
            findings=self.inspect(text).findings,
            interpretation="Exact presence of Unicode bidirectional controls.",
            limitations=(
                "Bidi controls can be essential in legitimate RTL text.",
                "Presence does not establish watermark intent.",
            ),
        )

    def rewrite(self, text: str) -> LayerRewriteResult:
        balanced = _balanced_indices(text)

        def replacement(index: int, character: str) -> str | None:
            if ord(character) in _BIDI_CONTROLS and self._should_remove(
                text, index, balanced
            ):
                return ""
            return None

        return rewrite_characters(
            layer_id=self.id,
            text=text,
            replacement=replacement,
            reason="Removed a bidi control from a paragraph with no strong RTL text.",
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
                "Balanced embeddings/isolates and directional transitions are preserved.",
            ),
        )
