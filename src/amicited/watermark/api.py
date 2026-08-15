"""Stable operation facade for the watermark SDK."""

from collections.abc import Callable, Sequence
from typing import Never

from amicited.errors import ModelConfigurationError, WatermarkNotImplementedError
from amicited.watermark._internal.pipeline import TextWatermarkPipeline
from amicited.watermark.input import WatermarkInput
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
    CapabilitiesReport,
    InspectionReport,
    TransformationReport,
    VerificationReport,
)
from amicited.watermark.options import DeterministicOptions, SemanticProvider


def _not_implemented(operation: str) -> Never:
    raise WatermarkNotImplementedError(operation)


class Watermark:
    """Configurable facade for AmICited Watermark operations."""

    def __init__(
        self,
        layers: Sequence[TextWatermarkLayer] | None = None,
        *,
        options: DeterministicOptions | None = None,
    ) -> None:
        self._custom_layers = tuple(layers) if layers is not None else None
        self._options = options or DeterministicOptions()
        selected_layers = (
            self._custom_layers
            if self._custom_layers is not None
            else self._default_layers(self._options)
        )
        self._pipeline = TextWatermarkPipeline(
            selected_layers,
            additional_capabilities=(SemanticRewriteLayer.declaration(),),
        )

    @staticmethod
    def _default_layers(
        options: DeterministicOptions,
    ) -> tuple[TextWatermarkLayer, ...]:
        return (
            HiddenUnicodeLayer(strip_semantic_format=options.strip_semantic_format),
            BidiControlLayer(strip_semantic_format=options.strip_semantic_format),
            UnicodeTagLayer(strip_semantic_format=options.strip_semantic_format),
            ExoticSpaceLayer(normalize_spaces=options.normalize_spaces),
            ConfusableLayer(map_confusables=options.map_confusables),
            UnicodeNormalizationLayer(form=options.normalization),
            WhitespacePatternLayer(),
        )

    def _pipeline_for(
        self, options: DeterministicOptions | None
    ) -> TextWatermarkPipeline:
        if options is None:
            return self._pipeline
        if not isinstance(options, DeterministicOptions):
            raise TypeError("options must be DeterministicOptions or None")
        if self._custom_layers is not None:
            raise ValueError("Per-operation options cannot override custom layers.")
        return TextWatermarkPipeline(self._default_layers(options))

    def _transformation_pipeline(
        self,
        options: DeterministicOptions | None,
        *,
        provider: SemanticProvider,
        model: str | None,
        model_provider: str | None,
        base_url: str | None,
        cli_timeout: float,
        progress_callback: Callable[[str], None] | None,
    ) -> TextWatermarkPipeline:
        pipeline = self._pipeline_for(options)
        if not isinstance(provider, SemanticProvider):
            raise TypeError("provider must be a SemanticProvider")
        if provider is SemanticProvider.API and model is None:
            if model_provider is not None or base_url is not None:
                raise ModelConfigurationError(
                    "model_provider and base_url require model to be selected."
                )
            return pipeline
        semantic_layer = SemanticRewriteLayer(
            model=model,
            execution_provider=provider,
            model_provider=model_provider,
            base_url=base_url,
            cli_timeout=cli_timeout,
            progress_callback=progress_callback,
        )
        semantic_layer.validate_configuration()
        return TextWatermarkPipeline((*pipeline.layers, semantic_layer))

    def inspect(
        self,
        input_data: WatermarkInput,
        *,
        options: DeterministicOptions | None = None,
    ) -> InspectionReport:
        """Inspect input without modifying it."""
        return self._pipeline_for(options).inspect(input_data)

    def verify(
        self,
        input_data: WatermarkInput,
        *,
        options: DeterministicOptions | None = None,
    ) -> VerificationReport:
        """Run compatible, explicitly configured verification."""
        return self._pipeline_for(options).verify(input_data)

    def remove(
        self,
        input_data: WatermarkInput,
        *,
        options: DeterministicOptions | None = None,
        provider: SemanticProvider = SemanticProvider.API,
        model: str | None = None,
        model_provider: str | None = None,
        base_url: str | None = None,
        cli_timeout: float = 120.0,
        progress_callback: Callable[[str], None] | None = None,
    ) -> TransformationReport:
        """Apply selected removal strategies to a copy of the input."""
        return self._transformation_pipeline(
            options,
            provider=provider,
            model=model,
            model_provider=model_provider,
            base_url=base_url,
            cli_timeout=cli_timeout,
            progress_callback=progress_callback,
        ).transform(input_data, operation="remove")

    def rewrite(
        self,
        input_data: WatermarkInput,
        *,
        options: DeterministicOptions | None = None,
        provider: SemanticProvider = SemanticProvider.API,
        model: str | None = None,
        model_provider: str | None = None,
        base_url: str | None = None,
        cli_timeout: float = 120.0,
        progress_callback: Callable[[str], None] | None = None,
    ) -> TransformationReport:
        """Produce a reviewable rewrite candidate."""
        return self._transformation_pipeline(
            options,
            provider=provider,
            model=model,
            model_provider=model_provider,
            base_url=base_url,
            cli_timeout=cli_timeout,
            progress_callback=progress_callback,
        ).transform(input_data, operation="rewrite")

    def compare(
        self,
        original: WatermarkInput,
        transformed: WatermarkInput,
        *,
        options: object | None = None,
    ) -> object:
        """Compare original and transformed content."""
        _not_implemented("compare")

    def explain(self, report: object, *, options: object | None = None) -> str:
        """Explain a structured watermark report."""
        _not_implemented("explain")

    def capabilities(self) -> CapabilitiesReport:
        """List statically declared watermark capabilities."""
        return self._pipeline.capabilities()


_default = Watermark()


def inspect(
    input_data: WatermarkInput, *, options: DeterministicOptions | None = None
) -> InspectionReport:
    """Inspect input using the default watermark facade."""
    return _default.inspect(input_data, options=options)


def verify(
    input_data: WatermarkInput, *, options: DeterministicOptions | None = None
) -> VerificationReport:
    """Verify input using the default watermark facade."""
    return _default.verify(input_data, options=options)


def remove(
    input_data: WatermarkInput,
    *,
    options: DeterministicOptions | None = None,
    provider: SemanticProvider = SemanticProvider.API,
    model: str | None = None,
    model_provider: str | None = None,
    base_url: str | None = None,
    cli_timeout: float = 120.0,
    progress_callback: Callable[[str], None] | None = None,
) -> TransformationReport:
    """Transform input using the default watermark facade."""
    return _default.remove(
        input_data,
        options=options,
        provider=provider,
        model=model,
        model_provider=model_provider,
        base_url=base_url,
        cli_timeout=cli_timeout,
        progress_callback=progress_callback,
    )


def rewrite(
    input_data: WatermarkInput,
    *,
    options: DeterministicOptions | None = None,
    provider: SemanticProvider = SemanticProvider.API,
    model: str | None = None,
    model_provider: str | None = None,
    base_url: str | None = None,
    cli_timeout: float = 120.0,
    progress_callback: Callable[[str], None] | None = None,
) -> TransformationReport:
    """Rewrite input using the default watermark facade."""
    return _default.rewrite(
        input_data,
        options=options,
        provider=provider,
        model=model,
        model_provider=model_provider,
        base_url=base_url,
        cli_timeout=cli_timeout,
        progress_callback=progress_callback,
    )


def compare(
    original: WatermarkInput,
    transformed: WatermarkInput,
    *,
    options: object | None = None,
) -> object:
    """Compare inputs using the default watermark facade."""
    return _default.compare(original, transformed, options=options)


def explain(report: object, *, options: object | None = None) -> str:
    """Explain a report using the default watermark facade."""
    return _default.explain(report, options=options)


def capabilities() -> CapabilitiesReport:
    """List capabilities using the default watermark facade."""
    return _default.capabilities()
