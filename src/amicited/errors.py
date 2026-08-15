"""Public exception hierarchy for AmICited."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from amicited.watermark.models import ProtectedSpanDiagnostics


class AmICitedError(Exception):
    """Base class for errors raised by the AmICited SDK."""


class WatermarkInputError(AmICitedError):
    """Raised when watermark input cannot be read safely."""


class WatermarkOutputError(WatermarkInputError):
    """Raised when transformed output cannot be written safely."""


class OutputFileExistsError(WatermarkOutputError):
    """Raised when output would overwrite an existing path."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(
            f"Output file already exists: {path}. Use --overwrite to replace it."
        )


class OutputFileWriteError(WatermarkOutputError):
    """Raised when a transformed output file cannot be written."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Unable to write output file safely: {path}")


class WatermarkConfigurationError(AmICitedError):
    """Raised when a requested operation is not safely configured."""


class ModelConfigurationError(WatermarkConfigurationError):
    """Raised when semantic model selection is invalid or incomplete."""


class MissingModelCredentialError(WatermarkConfigurationError):
    """Raised before external processing when provider credentials are absent."""

    def __init__(self, provider: str, environment_variable: str) -> None:
        self.provider = provider
        self.environment_variable = environment_variable
        super().__init__(
            f"Model provider '{provider}' requires {environment_variable} "
            "in the environment."
        )


class ModelIntegrationError(WatermarkConfigurationError):
    """Raised when LangChain cannot initialize the selected model integration."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(
            f"The LangChain integration for model provider '{provider}' "
            "is not installed or could not be initialized."
        )


class ModelCLIUnavailableError(WatermarkConfigurationError):
    """Raised before input is read when a selected model CLI is unavailable."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(
            f"The '{provider}' CLI is not installed or is not available on PATH."
        )


class ModelCLIExecutionError(AmICitedError):
    """Sanitized model CLI failure safe to include in structured reports."""

    def __init__(self, provider: str, category: str, message: str) -> None:
        self.provider = provider
        self.category = category
        self.public_message = message
        super().__init__(message)


class ProtectedSpanError(ValueError):
    """Raised when a model changes the semantic rewrite's protected spans."""

    category = "protected_span_violation"

    def __init__(
        self,
        message: str,
        *,
        diagnostics: ProtectedSpanDiagnostics | None = None,
    ) -> None:
        self.public_message = message
        self.diagnostics = diagnostics
        super().__init__(message)


class UnsupportedEncodingError(WatermarkInputError):
    """Raised when a text file is not valid UTF-8."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Input file is not valid UTF-8: {path}")


class InputFileReadError(WatermarkInputError):
    """Raised when an input file cannot be opened or read."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Unable to read input file: {path}")


class WatermarkNotImplementedError(AmICitedError):
    """Raised while a scaffolded watermark operation has no implementation."""

    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(
            f"AmICited Watermark operation '{operation}' is not implemented yet."
        )
