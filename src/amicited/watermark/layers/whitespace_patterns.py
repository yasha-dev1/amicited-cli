"""Read-only inspection of repeated, mixed, and nonstandard whitespace."""

from __future__ import annotations

from amicited.watermark.layers._unicode import finding, inspection, verification
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

_LINE_SEPARATORS = {0x0085, 0x2028, 0x2029}


def _horizontal_whitespace(character: str) -> bool:
    return character.isspace() and character not in {"\r", "\n", "\v", "\f"}


class WhitespacePatternLayer(TextWatermarkLayer):
    """Report whitespace patterns without changing or collapsing them."""

    id = "whitespace_patterns"

    def inspect(self, text: str) -> LayerInspectionResult:
        findings = []
        for index, character in enumerate(text):
            if ord(character) in _LINE_SEPARATORS:
                findings.append(
                    finding(
                        layer_id=self.id,
                        text=text,
                        index=index,
                        category="nonstandard_line_separator",
                        risk=RiskLevel.LOW,
                        legitimate_uses=(
                            "line and paragraph boundaries in formatting systems",
                        ),
                        action=RecommendedAction.PRESERVE,
                    )
                )

        index = 0
        while index < len(text):
            if not _horizontal_whitespace(text[index]):
                index += 1
                continue
            end = index + 1
            while end < len(text) and _horizontal_whitespace(text[end]):
                end += 1
            run = text[index:end]
            if len(run) > 1:
                findings.append(
                    finding(
                        layer_id=self.id,
                        text=text,
                        index=index + 1,
                        category=(
                            "mixed_whitespace"
                            if len(set(run)) > 1
                            else "repeated_whitespace"
                        ),
                        risk=RiskLevel.LOW,
                        legitimate_uses=(
                            "indentation, tables, code, poetry, and visual alignment",
                        ),
                        action=RecommendedAction.REVIEW,
                    )
                )
            index = end
        findings.sort(key=lambda item: item.position.code_point_index)
        return inspection(self.id, tuple(findings))

    def verify(self, text: str) -> LayerVerificationResult:
        return verification(
            layer_id=self.id,
            findings=self.inspect(text).findings,
            interpretation=(
                "Presence of repeated/mixed horizontal whitespace or Unicode line separators."
            ),
            limitations=(
                "Whitespace patterns are frequently legitimate and are never modified.",
            ),
        )

    def rewrite(self, text: str) -> LayerRewriteResult:
        return LayerRewriteResult(layer_id=self.id, text=text, changes=())

    def capability(self) -> CapabilityDeclaration:
        return CapabilityDeclaration(
            id=self.id,
            type="detector",
            signal_type=self.signal_type,
            modalities=(self.modality,),
            schemes=(),
            providers=(),
            authority=AuthorityLevel.HEURISTIC,
            requirements=(),
            network_required=False,
            deterministic=True,
            operations=("inspect", "verify", "remove", "rewrite"),
            limitations=("Inspection only; whitespace is never collapsed.",),
        )
