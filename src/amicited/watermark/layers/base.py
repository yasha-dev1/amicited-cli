"""Public extension interface for text watermark layers."""

from abc import ABC, abstractmethod

from amicited.watermark.models import (
    AuthorityLevel,
    CapabilityDeclaration,
    LayerInspectionResult,
    LayerRewriteResult,
    LayerVerificationResult,
)


class TextWatermarkLayer(ABC):
    """A sequential, local-only text inspection and transformation layer."""

    id: str
    modality: str = "text"
    signal_type: str = "hidden_unicode"
    authority: AuthorityLevel = AuthorityLevel.HEURISTIC

    @abstractmethod
    def inspect(self, text: str) -> LayerInspectionResult:
        """Find this layer's signals without changing text."""

    @abstractmethod
    def verify(self, text: str) -> LayerVerificationResult:
        """Return an exact status for this layer's supported signals."""

    @abstractmethod
    def rewrite(self, text: str) -> LayerRewriteResult:
        """Transform a copy of text and record every modification."""

    @abstractmethod
    def capability(self) -> CapabilityDeclaration:
        """Return static metadata without running detection or transformation."""
