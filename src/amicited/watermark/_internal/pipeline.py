"""Sequential execution engine for text watermark layers."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version

from amicited.errors import (
    InputFileReadError,
    ModelCLIExecutionError,
    ProtectedSpanError,
    UnsupportedEncodingError,
)
from amicited.watermark.input import InputKind, WatermarkInput
from amicited.watermark.layers import TextWatermarkLayer
from amicited.watermark.models import (
    AuthorityLevel,
    CapabilitiesReport,
    CapabilityDeclaration,
    DetectorDescriptor,
    InputSummary,
    InspectionReport,
    LayerInspectionResult,
    LayerRewriteResult,
    LayerVerificationResult,
    RiskLevel,
    TextFinding,
    TransformationReport,
    VerificationReport,
    VerificationStatus,
)

SCHEMA_VERSION = "1.0"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _tool_version() -> str:
    try:
        return version("amicited")
    except PackageNotFoundError:  # pragma: no cover - editable source fallback
        return "0.0.0"


def _summary(*, kind: InputKind, text: str, path: str | None = None) -> InputSummary:
    encoded = text.encode("utf-8")
    return InputSummary(
        kind=kind.value,
        content_included=False,
        character_count=len(text),
        byte_count=len(encoded),
        sha256=hashlib.sha256(encoded).hexdigest(),
        path=path,
    )


def _read_input(input_data: WatermarkInput) -> tuple[str, InputSummary]:
    if input_data.kind is InputKind.TEXT:
        if input_data.content is None:  # guarded by WatermarkInput
            raise ValueError("Text input has no content.")
        text = input_data.content
        return text, _summary(kind=InputKind.TEXT, text=text)

    if input_data.path is None:  # guarded by WatermarkInput
        raise ValueError("File input has no path.")
    try:
        with input_data.path.open("r", encoding="utf-8", newline="") as input_file:
            text = input_file.read()
    except UnicodeDecodeError as error:
        raise UnsupportedEncodingError(str(input_data.path)) from error
    except OSError as error:
        raise InputFileReadError(str(input_data.path)) from error
    return text, _summary(
        kind=InputKind.FILE,
        text=text,
        path=str(input_data.path),
    )


def _aggregate_status(
    results: Sequence[LayerVerificationResult],
) -> VerificationStatus:
    statuses = {result.status for result in results}
    for status in (
        VerificationStatus.FAILED,
        VerificationStatus.DETECTED,
        VerificationStatus.NOT_CONFIGURED,
        VerificationStatus.UNSUPPORTED,
        VerificationStatus.UNVERIFIABLE,
    ):
        if status in statuses:
            return status
    return VerificationStatus.NOT_DETECTED


def _deduplicate_findings(
    results: Sequence[LayerInspectionResult],
) -> tuple[TextFinding, ...]:
    findings: list[TextFinding] = []
    seen: set[tuple[int, str, str]] = set()
    for result in results:
        for finding in result.findings:
            key = (
                finding.position.code_point_index,
                finding.code_point,
                finding.type,
            )
            if key not in seen:
                findings.append(finding)
                seen.add(key)
    return tuple(findings)


class TextWatermarkPipeline:
    """Execute immutable text layers sequentially in their declared order."""

    def __init__(
        self,
        layers: Sequence[TextWatermarkLayer],
        *,
        additional_capabilities: Sequence[CapabilityDeclaration] = (),
    ) -> None:
        self.layers = tuple(layers)
        self.additional_capabilities = tuple(additional_capabilities)
        ids = [layer.id for layer in self.layers]
        if len(ids) != len(set(ids)):
            raise ValueError("Watermark layer IDs must be unique.")
        if any(layer.modality != "text" for layer in self.layers):
            raise ValueError("Version 1 accepts text watermark layers only.")

    def inspect(self, input_data: WatermarkInput) -> InspectionReport:
        started_at = _now()
        text, input_summary = _read_input(input_data)
        results: list[LayerInspectionResult] = []
        for layer in self.layers:
            try:
                results.append(layer.inspect(text))
            except Exception:  # layer boundary must return a structured failure
                results.append(
                    LayerInspectionResult(
                        layer_id=layer.id,
                        findings=(),
                        errors=("Layer failed during inspection.",),
                    )
                )
        result_tuple = tuple(results)
        return InspectionReport(
            schema_version=SCHEMA_VERSION,
            tool_version=_tool_version(),
            operation="inspect",
            started_at=started_at,
            completed_at=_now(),
            input=input_summary,
            capabilities_used=tuple(layer.id for layer in self.layers),
            results=result_tuple,
            findings=_deduplicate_findings(result_tuple),
            errors=tuple(error for result in result_tuple for error in result.errors),
        )

    def _verify_text(
        self, text: str, input_summary: InputSummary
    ) -> VerificationReport:
        started_at = _now()
        results: list[LayerVerificationResult] = []
        for layer in self.layers:
            try:
                results.append(layer.verify(text))
            except Exception:  # detector failures must never become not_detected
                results.append(
                    LayerVerificationResult(
                        layer_id=layer.id,
                        authority=AuthorityLevel.HEURISTIC,
                        status=VerificationStatus.FAILED,
                        findings=(),
                        detector=DetectorDescriptor(
                            id=layer.id,
                            version="1.0",
                            authority=AuthorityLevel.HEURISTIC,
                            interpretation="Layer execution failed.",
                        ),
                        errors=("Layer failed during verification.",),
                    )
                )
        result_tuple = tuple(results)
        return VerificationReport(
            schema_version=SCHEMA_VERSION,
            tool_version=_tool_version(),
            operation="verify",
            started_at=started_at,
            completed_at=_now(),
            input=input_summary,
            capabilities_used=tuple(layer.id for layer in self.layers),
            status=_aggregate_status(result_tuple),
            results=result_tuple,
            warnings=(
                "Only enumerated Unicode signals were verified; this is not proof "
                "of human authorship or absence of other watermark schemes.",
            ),
            errors=tuple(error for result in result_tuple for error in result.errors),
        )

    def verify(self, input_data: WatermarkInput) -> VerificationReport:
        text, input_summary = _read_input(input_data)
        return self._verify_text(text, input_summary)

    def transform(
        self, input_data: WatermarkInput, *, operation: str
    ) -> TransformationReport:
        if operation not in {"remove", "rewrite"}:
            raise ValueError(f"Unsupported transformation operation: {operation}")
        started_at = _now()
        original, input_summary = _read_input(input_data)
        before_verification = self._verify_text(original, input_summary)
        current = original
        results: list[LayerRewriteResult] = []
        for layer in self.layers:
            try:
                result = layer.rewrite(current)
            except Exception as error:  # preserve current text if a transformer fails
                safe_error = isinstance(
                    error, ModelCLIExecutionError | ProtectedSpanError
                )
                result = LayerRewriteResult(
                    layer_id=layer.id,
                    text=current,
                    changes=(),
                    deterministic=getattr(layer, "id", "") != "semantic_rewrite",
                    external_processing=getattr(layer, "id", "") == "semantic_rewrite",
                    model=getattr(layer, "model", None),
                    provider=getattr(layer, "provider", None),
                    execution_provider=getattr(layer, "execution_provider", None),
                    protected_spans_preserved=(
                        False if isinstance(error, ProtectedSpanError) else None
                    ),
                    protected_span_diagnostics=(
                        error.diagnostics
                        if isinstance(error, ProtectedSpanError)
                        else None
                    ),
                    chunk_count=getattr(layer, "chunk_count", None),
                    max_chunk_words=getattr(layer, "max_chunk_words", None),
                    max_concurrency=getattr(layer, "max_concurrency", None),
                    lexical_diversity=getattr(layer, "lexical_diversity", None),
                    order_diversity=getattr(layer, "order_diversity", None),
                    meaning_risk=(
                        RiskLevel.MEDIUM
                        if getattr(layer, "id", "") == "semantic_rewrite"
                        else None
                    ),
                    error_category=(
                        getattr(error, "category", None)
                        if safe_error
                        else "layer_failed"
                    ),
                    errors=(
                        getattr(error, "public_message")
                        if safe_error
                        else "Layer failed during transformation.",
                    ),
                )
            results.append(result)
            current = result.text

        after_summary = _summary(kind=InputKind.TEXT, text=current)
        after_verification = self._verify_text(current, after_summary)
        result_tuple = tuple(results)
        changes = tuple(change for result in result_tuple for change in result.changes)
        errors = tuple(error for result in result_tuple for error in result.errors)
        return TransformationReport(
            schema_version=SCHEMA_VERSION,
            tool_version=_tool_version(),
            operation=operation,
            started_at=started_at,
            completed_at=_now(),
            input=input_summary,
            capabilities_used=tuple(layer.id for layer in self.layers),
            transformation_status="failed" if errors else "completed",
            verification_status=after_verification.status,
            changed=current != original,
            transformed_text=current,
            results=result_tuple,
            changes=changes,
            before_verification=before_verification,
            after_verification=after_verification,
            warnings=(
                "Verification is capability-specific. A completed transformation "
                "does not prove universal watermark removal or human authorship.",
            ),
            errors=errors,
        )

    def capabilities(self) -> CapabilitiesReport:
        return CapabilitiesReport(
            schema_version=SCHEMA_VERSION,
            tool_version=_tool_version(),
            operation="capabilities",
            capabilities=(
                tuple(layer.capability() for layer in self.layers)
                + self.additional_capabilities
            ),
        )
