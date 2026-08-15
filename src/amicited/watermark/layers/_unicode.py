"""Shared helpers for deterministic Unicode layers."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from difflib import SequenceMatcher

from amicited.watermark.models import (
    AuthorityLevel,
    DetectorDescriptor,
    LayerInspectionResult,
    LayerRewriteResult,
    LayerVerificationResult,
    RecommendedAction,
    RiskLevel,
    TextChange,
    TextFinding,
    TextPosition,
    VerificationStatus,
)


def position(text: str, index: int) -> TextPosition:
    """Calculate a stable Unicode and UTF-8 position."""
    return TextPosition(
        code_point_index=index,
        byte_offset=len(text[:index].encode("utf-8")),
    )


def code_point(character: str) -> str:
    """Format a character as a Unicode code point."""
    return f"U+{ord(character):04X}"


def visible_context(text: str, index: int, *, radius: int = 12) -> str:
    """Show nearby text while making the target character visible."""
    start = max(0, index - radius)
    end = min(len(text), index + radius + 1)
    return f"{text[start:index]}⟦{code_point(text[index])}⟧{text[index + 1 : end]}"


def finding(
    *,
    layer_id: str,
    text: str,
    index: int,
    category: str,
    risk: RiskLevel,
    legitimate_uses: tuple[str, ...],
    action: RecommendedAction,
) -> TextFinding:
    """Build a complete finding for one code point."""
    character = text[index]
    return TextFinding(
        layer_id=layer_id,
        type="hidden_unicode",
        code_point=code_point(character),
        unicode_name=unicodedata.name(character, "UNNAMED CONTROL CHARACTER"),
        category=category,
        position=position(text, index),
        context=visible_context(text, index),
        risk=risk,
        legitimate_uses=legitimate_uses,
        recommended_action=action,
    )


def verification(
    *,
    layer_id: str,
    findings: tuple[TextFinding, ...],
    interpretation: str,
    limitations: tuple[str, ...],
) -> LayerVerificationResult:
    """Create a truthful presence/absence result for an exact scan."""
    return LayerVerificationResult(
        layer_id=layer_id,
        authority=AuthorityLevel.HEURISTIC,
        status=(
            VerificationStatus.DETECTED if findings else VerificationStatus.NOT_DETECTED
        ),
        findings=findings,
        detector=DetectorDescriptor(
            id=layer_id,
            version="1.0",
            authority=AuthorityLevel.HEURISTIC,
            interpretation=interpretation,
        ),
        warnings=(
            "Detected characters can have legitimate uses and do not prove a watermark.",
        )
        if findings
        else (),
        limitations=limitations,
    )


def rewrite_characters(
    *,
    layer_id: str,
    text: str,
    replacement: Callable[[int, str], str | None],
    reason: str,
) -> LayerRewriteResult:
    """Apply per-character replacements without normalizing other text."""
    output: list[str] = []
    changes: list[TextChange] = []
    for index, character in enumerate(text):
        replacement_value = replacement(index, character)
        if replacement_value is None:
            output.append(character)
            continue
        output.append(replacement_value)
        if replacement_value != character:
            changes.append(
                TextChange(
                    layer_id=layer_id,
                    position=position(text, index),
                    before=character,
                    after=replacement_value,
                    reason=reason,
                )
            )
    return LayerRewriteResult(
        layer_id=layer_id,
        text="".join(output),
        changes=tuple(changes),
    )


def rewrite_text_diff(
    *, layer_id: str, text: str, transformed: str, reason: str
) -> LayerRewriteResult:
    """Record deterministic whole-text changes as reviewable edit spans."""
    changes = tuple(
        TextChange(
            layer_id=layer_id,
            position=position(text, original_start),
            before=text[original_start:original_end],
            after=transformed[transformed_start:transformed_end],
            reason=reason,
        )
        for tag, original_start, original_end, transformed_start, transformed_end in (
            SequenceMatcher(a=text, b=transformed, autojunk=False).get_opcodes()
        )
        if tag != "equal"
    )
    return LayerRewriteResult(
        layer_id=layer_id,
        text=transformed,
        changes=changes,
    )


def inspection(
    layer_id: str, findings: tuple[TextFinding, ...]
) -> LayerInspectionResult:
    """Create a layer inspection result."""
    return LayerInspectionResult(layer_id=layer_id, findings=findings)
