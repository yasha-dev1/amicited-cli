"""Deterministic inspection and replacement of exotic space characters."""

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

_EXOTIC_SPACES = {
    0x00A0,
    0x1680,
    *range(0x2000, 0x200B),
    0x202F,
    0x205F,
    0x3000,
}


class ExoticSpaceLayer(TextWatermarkLayer):
    """Map selected Unicode spaces one-for-one to ASCII space."""

    id = "exotic_spaces"

    def __init__(self, *, normalize_spaces: bool = True) -> None:
        self.normalize_spaces = normalize_spaces

    def inspect(self, text: str) -> LayerInspectionResult:
        findings = tuple(
            finding(
                layer_id=self.id,
                text=text,
                index=index,
                category="space_separator",
                risk=RiskLevel.MEDIUM,
                legitimate_uses=(
                    "typography, non-breaking layout, and language-specific spacing",
                ),
                action=RecommendedAction.REMOVE,
            )
            for index, character in enumerate(text)
            if ord(character) in _EXOTIC_SPACES
        )
        return inspection(self.id, findings)

    def verify(self, text: str) -> LayerVerificationResult:
        return verification(
            layer_id=self.id,
            findings=self.inspect(text).findings,
            interpretation="Exact presence of enumerated non-ASCII space characters.",
            limitations=(
                "Replacing non-breaking spaces can change line wrapping.",
                "Presence does not establish watermark intent.",
            ),
        )

    def rewrite(self, text: str) -> LayerRewriteResult:
        def replacement(_index: int, character: str) -> str | None:
            if self.normalize_spaces and ord(character) in _EXOTIC_SPACES:
                return " "
            return None

        return rewrite_characters(
            layer_id=self.id,
            text=text,
            replacement=replacement,
            reason="Mapped an exotic Unicode space to one ASCII space.",
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
                "Maps characters one-for-one and never collapses whitespace.",
                "Non-breaking behavior is not preserved.",
            ),
        )
