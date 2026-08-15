"""Deterministic inspection and sanitation of Unicode tag characters."""

from __future__ import annotations

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

_BLACK_FLAG = 0x1F3F4
_TAG_START = 0xE0020
_TAG_END = 0xE007E
_CANCEL_TAG = 0xE007F


def _is_tag(value: int) -> bool:
    return 0xE0000 <= value <= 0xE007F


def _valid_emoji_tag_indices(text: str) -> set[int]:
    valid: set[int] = set()
    index = 0
    while index < len(text):
        if ord(text[index]) != _BLACK_FLAG:
            index += 1
            continue
        cursor = index + 1
        first_tag = cursor
        while cursor < len(text) and _TAG_START <= ord(text[cursor]) <= _TAG_END:
            cursor += 1
        if (
            cursor > first_tag
            and cursor < len(text)
            and ord(text[cursor]) == _CANCEL_TAG
        ):
            valid.update(range(first_tag, cursor + 1))
            index = cursor + 1
        else:
            index += 1
    return valid


class UnicodeTagLayer(TextWatermarkLayer):
    """Remove standalone tags while preserving valid emoji tag sequences."""

    id = "unicode_tags"

    def __init__(self, *, strip_semantic_format: bool = False) -> None:
        self.strip_semantic_format = strip_semantic_format

    def inspect(self, text: str) -> LayerInspectionResult:
        valid_indices = _valid_emoji_tag_indices(text)
        findings = tuple(
            finding(
                layer_id=self.id,
                text=text,
                index=index,
                category="unicode_tag",
                risk=RiskLevel.MEDIUM,
                legitimate_uses=("emoji subdivision flag sequences",),
                action=(
                    RecommendedAction.PRESERVE
                    if index in valid_indices and not self.strip_semantic_format
                    else RecommendedAction.REMOVE
                ),
            )
            for index, character in enumerate(text)
            if _is_tag(ord(character))
        )
        return inspection(self.id, findings)

    def verify(self, text: str) -> LayerVerificationResult:
        return verification(
            layer_id=self.id,
            findings=self.inspect(text).findings,
            interpretation="Exact presence of Unicode tag code points.",
            limitations=(
                "Valid emoji subdivision sequences are detected but preserved.",
                "Presence does not establish watermark intent.",
            ),
        )

    def rewrite(self, text: str) -> LayerRewriteResult:
        valid_indices = _valid_emoji_tag_indices(text)

        def replacement(index: int, character: str) -> str | None:
            if _is_tag(ord(character)) and (
                self.strip_semantic_format or index not in valid_indices
            ):
                return ""
            return None

        return rewrite_characters(
            layer_id=self.id,
            text=text,
            replacement=replacement,
            reason="Removed a Unicode tag outside a valid emoji tag sequence.",
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
            limitations=("Valid emoji tag sequences are preserved by default.",),
        )
