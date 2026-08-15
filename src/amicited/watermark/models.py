"""Versioned result models shared by the CLI and Python SDK."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
from typing import cast


class VerificationStatus(StrEnum):
    """All states a detector may return."""

    DETECTED = "detected"
    NOT_DETECTED = "not_detected"
    NOT_CONFIGURED = "not_configured"
    UNSUPPORTED = "unsupported"
    UNVERIFIABLE = "unverifiable"
    FAILED = "failed"


class AuthorityLevel(StrEnum):
    """How authoritative a detector result is."""

    OFFICIAL = "official"
    KNOWN_SCHEME = "known_scheme"
    RESEARCH = "research"
    HEURISTIC = "heuristic"
    UNOFFICIAL = "unofficial"


class RiskLevel(StrEnum):
    """Review risk associated with a finding."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendedAction(StrEnum):
    """Conservative action recommended for a finding."""

    PRESERVE = "preserve"
    REMOVE = "remove"
    REVIEW = "review"


def _serialize(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _serialize(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, tuple | list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value


class Serializable:
    """JSON serialization shared by every public result model."""

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible dictionary."""
        value = _serialize(self)
        return cast(dict[str, object], value)

    def to_json(self, *, indent: int | None = 2) -> str:
        """Return stable UTF-8 JSON without terminal styling."""
        return json.dumps(
            self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True
        )


@dataclass(frozen=True, slots=True)
class TextPosition(Serializable):
    """A position expressed in Unicode code points and UTF-8 bytes."""

    code_point_index: int
    byte_offset: int


@dataclass(frozen=True, slots=True)
class TextFinding(Serializable):
    """One exact text signal found by a layer."""

    layer_id: str
    type: str
    code_point: str
    unicode_name: str
    category: str
    position: TextPosition
    context: str
    risk: RiskLevel
    legitimate_uses: tuple[str, ...]
    recommended_action: RecommendedAction


@dataclass(frozen=True, slots=True)
class TextChange(Serializable):
    """One deterministic modification made by a layer."""

    layer_id: str
    position: TextPosition
    before: str
    after: str
    reason: str


@dataclass(frozen=True, slots=True)
class DetectorDescriptor(Serializable):
    """Identity and interpretation of one detector."""

    id: str
    version: str
    authority: AuthorityLevel
    interpretation: str
    calibration: str | None = None
    supported_scope: str = "enumerated Unicode code points in text"


@dataclass(frozen=True, slots=True)
class LayerInspectionResult(Serializable):
    """Findings returned by one inspection layer."""

    layer_id: str
    findings: tuple[TextFinding, ...]
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LayerVerificationResult(Serializable):
    """Verification status returned by one exact detector layer."""

    layer_id: str
    authority: AuthorityLevel
    status: VerificationStatus
    findings: tuple[TextFinding, ...]
    detector: DetectorDescriptor | None = None
    signal_type: str = "hidden_unicode"
    modality: str = "text"
    scheme: str | None = None
    provider: str | None = None
    execution_provider: str | None = None
    score: float | None = None
    threshold: float | None = None
    confidence: float | None = None
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LayerRewriteResult(Serializable):
    """Output and changes returned by one transformation layer."""

    layer_id: str
    text: str
    changes: tuple[TextChange, ...]
    strategy_category: str | None = None
    deterministic: bool = True
    external_processing: bool = False
    model: str | None = None
    provider: str | None = None
    execution_provider: str | None = None
    protected_spans_preserved: bool | None = None
    meaning_risk: RiskLevel | None = None
    error_category: str | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InputSummary(Serializable):
    """Privacy-preserving description of an operation input."""

    kind: str
    content_included: bool
    character_count: int
    byte_count: int
    sha256: str
    path: str | None = None


@dataclass(frozen=True, slots=True)
class OutputSummary(Serializable):
    """Description and checksum of a transformed file written by the CLI."""

    path: str
    character_count: int
    byte_count: int
    sha256: str


@dataclass(frozen=True, slots=True)
class InspectionReport(Serializable):
    """Versioned result of the inspect operation."""

    schema_version: str
    tool_version: str
    operation: str
    started_at: str
    completed_at: str
    input: InputSummary
    capabilities_used: tuple[str, ...]
    results: tuple[LayerInspectionResult, ...]
    findings: tuple[TextFinding, ...]
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VerificationReport(Serializable):
    """Versioned aggregate of independent detector results."""

    schema_version: str
    tool_version: str
    operation: str
    started_at: str
    completed_at: str
    input: InputSummary
    capabilities_used: tuple[str, ...]
    status: VerificationStatus
    results: tuple[LayerVerificationResult, ...]
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TransformationReport(Serializable):
    """Versioned rewrite/remove result with before and after verification."""

    schema_version: str
    tool_version: str
    operation: str
    started_at: str
    completed_at: str
    input: InputSummary
    capabilities_used: tuple[str, ...]
    transformation_status: str
    verification_status: VerificationStatus
    changed: bool
    transformed_text: str
    results: tuple[LayerRewriteResult, ...]
    changes: tuple[TextChange, ...]
    before_verification: VerificationReport
    after_verification: VerificationReport
    output: OutputSummary | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityDeclaration(Serializable):
    """Static declaration for one text layer."""

    id: str
    type: str
    signal_type: str
    modalities: tuple[str, ...]
    schemes: tuple[str, ...]
    providers: tuple[str, ...]
    authority: AuthorityLevel
    requirements: tuple[str, ...]
    network_required: bool
    deterministic: bool
    operations: tuple[str, ...]
    limitations: tuple[str, ...]
    execution_providers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilitiesReport(Serializable):
    """Static list of installed text capabilities."""

    schema_version: str
    tool_version: str
    operation: str
    capabilities: tuple[CapabilityDeclaration, ...]
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
