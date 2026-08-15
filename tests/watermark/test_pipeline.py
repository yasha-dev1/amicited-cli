from amicited.watermark import Watermark, WatermarkInput
from amicited.watermark.layers import TextWatermarkLayer
from amicited.watermark.models import (
    AuthorityLevel,
    CapabilityDeclaration,
    LayerInspectionResult,
    LayerRewriteResult,
    LayerVerificationResult,
    VerificationStatus,
)


class RecordingLayer(TextWatermarkLayer):
    modality = "text"

    def __init__(self, layer_id: str, suffix: str, calls: list[str]) -> None:
        self.id = layer_id
        self._suffix = suffix
        self._calls = calls

    def inspect(self, text: str) -> LayerInspectionResult:
        self._calls.append(f"inspect:{self.id}:{text}")
        return LayerInspectionResult(layer_id=self.id, findings=())

    def verify(self, text: str) -> LayerVerificationResult:
        self._calls.append(f"verify:{self.id}:{text}")
        return LayerVerificationResult(
            layer_id=self.id,
            authority=AuthorityLevel.HEURISTIC,
            status=VerificationStatus.NOT_DETECTED,
            findings=(),
        )

    def rewrite(self, text: str) -> LayerRewriteResult:
        self._calls.append(f"rewrite:{self.id}:{text}")
        return LayerRewriteResult(
            layer_id=self.id,
            text=f"{text}{self._suffix}",
            changes=(),
        )

    def capability(self) -> CapabilityDeclaration:
        return CapabilityDeclaration(
            id=self.id,
            type="detector_and_strategy",
            signal_type="hidden_unicode",
            modalities=("text",),
            schemes=(),
            providers=(),
            authority=AuthorityLevel.HEURISTIC,
            requirements=(),
            network_required=False,
            deterministic=True,
            operations=("inspect", "verify", "rewrite"),
            limitations=(),
        )


class FailingLayer(RecordingLayer):
    def verify(self, text: str) -> LayerVerificationResult:
        self._calls.append(f"verify:{self.id}:{text}")
        raise RuntimeError("private input must not be copied into the report")

    def rewrite(self, text: str) -> LayerRewriteResult:
        self._calls.append(f"rewrite:{self.id}:{text}")
        raise RuntimeError("private input must not be copied into the report")


def test_inspection_and_verification_execute_every_layer_in_order() -> None:
    calls: list[str] = []
    sdk = Watermark(
        layers=(
            RecordingLayer("first", "A", calls),
            RecordingLayer("second", "B", calls),
        )
    )

    inspection = sdk.inspect(WatermarkInput.text("x"))
    verification = sdk.verify(WatermarkInput.text("x"))

    assert [result.layer_id for result in inspection.results] == ["first", "second"]
    assert [result.layer_id for result in verification.results] == ["first", "second"]
    assert calls == [
        "inspect:first:x",
        "inspect:second:x",
        "verify:first:x",
        "verify:second:x",
    ]


def test_rewrite_feeds_each_layer_output_to_the_next_layer() -> None:
    calls: list[str] = []
    sdk = Watermark(
        layers=(
            RecordingLayer("first", "A", calls),
            RecordingLayer("second", "B", calls),
        )
    )

    report = sdk.rewrite(WatermarkInput.text("x"))

    assert report.transformed_text == "xAB"
    assert [result.layer_id for result in report.results] == ["first", "second"]
    assert "rewrite:first:x" in calls
    assert "rewrite:second:xA" in calls
    assert calls.index("rewrite:first:x") < calls.index("rewrite:second:xA")


def test_layer_failures_are_structured_and_do_not_stop_later_layers() -> None:
    calls: list[str] = []
    sdk = Watermark(
        layers=(
            FailingLayer("failing", "X", calls),
            RecordingLayer("later", "B", calls),
        )
    )

    verification = sdk.verify(WatermarkInput.text("secret"))
    rewrite = sdk.rewrite(WatermarkInput.text("secret"))

    assert verification.status is VerificationStatus.FAILED
    assert verification.results[0].status is VerificationStatus.FAILED
    assert verification.results[0].errors == ("Layer failed during verification.",)
    assert verification.results[1].status is VerificationStatus.NOT_DETECTED
    assert rewrite.transformation_status == "failed"
    assert rewrite.results[0].text == "secret"
    assert "rewrite:later:secret" in calls
    assert "private input" not in rewrite.to_json()
