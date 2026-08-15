"""Inspection and explicit application of Unicode normalization."""

from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher
from typing import Literal

from amicited.watermark.layers._unicode import (
    finding,
    inspection,
    rewrite_text_diff,
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
from amicited.watermark.options import NormalizationForm


def _first_changed_original_index(original: str, normalized: str) -> int | None:
    for tag, start, end, _new_start, _new_end in SequenceMatcher(
        a=original, b=normalized, autojunk=False
    ).get_opcodes():
        if tag != "equal":
            return min(start, max(0, len(original) - 1)) if original else None
    return None


class UnicodeNormalizationLayer(TextWatermarkLayer):
    """Report normalization differences and apply them only when configured."""

    id = "unicode_normalization"

    def __init__(self, *, form: NormalizationForm | None = None) -> None:
        self.form = form

    def inspect(self, text: str) -> LayerInspectionResult:
        findings = []
        canonical_index = _first_changed_original_index(
            text, unicodedata.normalize("NFC", text)
        )
        if canonical_index is not None:
            findings.append(
                finding(
                    layer_id=self.id,
                    text=text,
                    index=canonical_index,
                    category="canonical_normalization_difference",
                    risk=RiskLevel.MEDIUM,
                    legitimate_uses=("decomposed Unicode and legacy text encodings",),
                    action=RecommendedAction.REVIEW,
                )
            )

        compatibility_indices = {
            index
            for index, character in enumerate(text)
            if unicodedata.normalize("NFKC", character) != character
        }
        if not compatibility_indices and canonical_index is None:
            compatibility_index = _first_changed_original_index(
                text, unicodedata.normalize("NFKC", text)
            )
            if compatibility_index is not None:
                compatibility_indices.add(compatibility_index)
        for index in sorted(compatibility_indices):
            if index == canonical_index:
                continue
            findings.append(
                finding(
                    layer_id=self.id,
                    text=text,
                    index=index,
                    category="compatibility_normalization_difference",
                    risk=RiskLevel.MEDIUM,
                    legitimate_uses=(
                        "fullwidth typography, mathematical notation, and compatibility forms",
                    ),
                    action=RecommendedAction.REVIEW,
                )
            )
        return inspection(self.id, tuple(findings))

    def verify(self, text: str) -> LayerVerificationResult:
        return verification(
            layer_id=self.id,
            findings=self.inspect(text).findings,
            interpretation="Difference from Unicode NFC or NFKC normalization.",
            limitations=(
                "Normalization differences are not evidence of watermark intent.",
                "NFKC can alter typography and mathematical meaning.",
            ),
        )

    def rewrite(self, text: str) -> LayerRewriteResult:
        if self.form is None:
            return LayerRewriteResult(layer_id=self.id, text=text, changes=())
        form: Literal["NFC", "NFKC"] = (
            "NFC" if self.form is NormalizationForm.NFC else "NFKC"
        )
        transformed = unicodedata.normalize(form, text)
        return rewrite_text_diff(
            layer_id=self.id,
            text=text,
            transformed=transformed,
            reason=f"Applied explicitly selected Unicode {form} normalization.",
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
            limitations=("Normalization is disabled unless explicitly requested.",),
        )
