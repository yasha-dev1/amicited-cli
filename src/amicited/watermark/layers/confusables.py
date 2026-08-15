"""Inspection and explicit remediation of potential Latin confusables."""

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

_CYRILLIC_CONFUSABLES = {
    "А": "A",
    "В": "B",
    "Е": "E",
    "К": "K",
    "М": "M",
    "Н": "H",
    "О": "O",
    "Р": "P",
    "С": "C",
    "Т": "T",
    "Х": "X",
    "а": "a",
    "е": "e",
    "о": "o",
    "р": "p",
    "с": "c",
    "у": "y",
    "х": "x",
    "і": "i",
}
_FULLWIDTH_CONFUSABLES = {
    **{chr(value): chr(value - 0xFF21 + ord("A")) for value in range(0xFF21, 0xFF3B)},
    **{chr(value): chr(value - 0xFF41 + ord("a")) for value in range(0xFF41, 0xFF5B)},
}
_CONFUSABLES = {**_CYRILLIC_CONFUSABLES, **_FULLWIDTH_CONFUSABLES}


def _token_bounds(text: str, index: int) -> tuple[int, int]:
    start = index
    while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
        start -= 1
    end = index + 1
    while end < len(text) and (text[end].isalnum() or text[end] == "_"):
        end += 1
    return start, end


def _is_potentially_ambiguous(text: str, index: int) -> bool:
    character = text[index]
    if character in _FULLWIDTH_CONFUSABLES:
        return True
    if character not in _CYRILLIC_CONFUSABLES:
        return False
    start, end = _token_bounds(text, index)
    return any(
        ("A" <= candidate <= "Z") or ("a" <= candidate <= "z")
        for candidate in text[start:end]
    )


class ConfusableLayer(TextWatermarkLayer):
    """Flag mixed-script/fullwidth lookalikes and map only when requested."""

    id = "confusables"

    def __init__(self, *, map_confusables: bool = False) -> None:
        self.map_confusables = map_confusables

    def inspect(self, text: str) -> LayerInspectionResult:
        findings = tuple(
            finding(
                layer_id=self.id,
                text=text,
                index=index,
                category="potential_confusable",
                risk=RiskLevel.HIGH,
                legitimate_uses=("Cyrillic-language content and fullwidth typography",),
                action=RecommendedAction.REVIEW,
            )
            for index, character in enumerate(text)
            if character in _CONFUSABLES and _is_potentially_ambiguous(text, index)
        )
        return inspection(self.id, findings)

    def verify(self, text: str) -> LayerVerificationResult:
        return verification(
            layer_id=self.id,
            findings=self.inspect(text).findings,
            interpretation=(
                "Presence of enumerated fullwidth lookalikes or Cyrillic lookalikes "
                "inside mixed Latin-script tokens."
            ),
            limitations=(
                "Confusable detection is heuristic and does not prove malicious intent.",
                "Pure Cyrillic words are not flagged.",
            ),
        )

    def rewrite(self, text: str) -> LayerRewriteResult:
        selected = {
            finding.position.code_point_index for finding in self.inspect(text).findings
        }

        def replacement(index: int, character: str) -> str | None:
            if self.map_confusables and index in selected:
                return _CONFUSABLES[character]
            return None

        return rewrite_characters(
            layer_id=self.id,
            text=text,
            replacement=replacement,
            reason="Mapped an explicitly selected potential confusable to ASCII Latin.",
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
            limitations=("Mapping is disabled unless explicitly requested.",),
        )
