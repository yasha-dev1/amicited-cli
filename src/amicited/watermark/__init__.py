"""Public SDK interface for AmICited Watermark.

Only names re-exported by this module are part of the stable SDK surface.
"""

from amicited.watermark.api import (
    Watermark,
    capabilities,
    compare,
    explain,
    inspect,
    remove,
    rewrite,
    verify,
)
from amicited.watermark.input import InputKind, WatermarkInput
from amicited.watermark.layers import (
    BidiControlLayer,
    ConfusableLayer,
    ExoticSpaceLayer,
    HiddenUnicodeLayer,
    SemanticRewriteLayer,
    TextWatermarkLayer,
    UnicodeNormalizationLayer,
    UnicodeTagLayer,
    WhitespacePatternLayer,
)
from amicited.watermark.models import (
    AuthorityLevel,
    CapabilitiesReport,
    CapabilityDeclaration,
    InspectionReport,
    OutputSummary,
    ProtectedSpanDiagnostics,
    RecommendedAction,
    RiskLevel,
    TransformationReport,
    VerificationReport,
    VerificationStatus,
)
from amicited.watermark.options import (
    DeterministicOptions,
    NormalizationForm,
    SemanticProvider,
)

__all__ = [
    "AuthorityLevel",
    "BidiControlLayer",
    "CapabilitiesReport",
    "CapabilityDeclaration",
    "ConfusableLayer",
    "DeterministicOptions",
    "ExoticSpaceLayer",
    "HiddenUnicodeLayer",
    "InputKind",
    "InspectionReport",
    "NormalizationForm",
    "OutputSummary",
    "ProtectedSpanDiagnostics",
    "RecommendedAction",
    "RiskLevel",
    "SemanticProvider",
    "SemanticRewriteLayer",
    "TextWatermarkLayer",
    "TransformationReport",
    "UnicodeTagLayer",
    "UnicodeNormalizationLayer",
    "VerificationReport",
    "VerificationStatus",
    "Watermark",
    "WatermarkInput",
    "WhitespacePatternLayer",
    "capabilities",
    "compare",
    "explain",
    "inspect",
    "remove",
    "rewrite",
    "verify",
]
