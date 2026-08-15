"""Typed options for deterministic text cleanup."""

from dataclasses import dataclass
from enum import StrEnum


class NormalizationForm(StrEnum):
    """Unicode normalization forms available as explicit strategies."""

    NFC = "nfc"
    NFKC = "nfkc"


class SemanticProvider(StrEnum):
    """Execution provider for model-driven semantic rewriting."""

    API = "api"
    CODEX = "codex"
    CLAUDE = "claude"


@dataclass(frozen=True, slots=True)
class DeterministicOptions:
    """Configuration for local deterministic inspection and transformation."""

    strip_semantic_format: bool = False
    map_confusables: bool = False
    normalize_spaces: bool = True
    normalization: NormalizationForm | None = None

    def __post_init__(self) -> None:
        for name in (
            "strip_semantic_format",
            "map_confusables",
            "normalize_spaces",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        if self.normalization is not None and not isinstance(
            self.normalization, NormalizationForm
        ):
            raise TypeError("normalization must be a NormalizationForm or None")
