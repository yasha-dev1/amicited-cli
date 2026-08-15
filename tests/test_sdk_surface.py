from pathlib import Path

import pytest

from amicited import watermark
from amicited.errors import WatermarkNotImplementedError

EXPECTED_OPERATIONS = {
    "inspect",
    "verify",
    "remove",
    "rewrite",
    "compare",
    "explain",
    "capabilities",
}


def test_watermark_module_exposes_the_version_one_operations() -> None:
    assert EXPECTED_OPERATIONS <= set(watermark.__all__)
    for operation in EXPECTED_OPERATIONS:
        assert callable(getattr(watermark, operation))


def test_input_constructors_distinguish_text_from_files() -> None:
    text_input = watermark.WatermarkInput.text("article contents")
    file_input = watermark.WatermarkInput.file(Path("article.md"))

    assert text_input.kind is watermark.InputKind.TEXT
    assert text_input.content == "article contents"
    assert text_input.path is None

    assert file_input.kind is watermark.InputKind.FILE
    assert file_input.content is None
    assert file_input.path == Path("article.md")


@pytest.mark.parametrize(
    "arguments",
    [
        {
            "kind": watermark.InputKind.TEXT,
            "content": "",
            "path": Path("article.md"),
        },
        {
            "kind": watermark.InputKind.FILE,
            "content": "",
            "path": Path("article.md"),
        },
    ],
)
def test_input_rejects_ambiguous_sources(arguments: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="cannot include"):
        watermark.WatermarkInput(**arguments)


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        (
            "compare",
            lambda: (
                watermark.WatermarkInput.text("before"),
                watermark.WatermarkInput.text("after"),
            ),
        ),
        ("explain", lambda: ({"operation": "inspect"},)),
    ],
)
def test_unimplemented_operations_fail_explicitly(name: str, arguments: object) -> None:
    operation = getattr(watermark, name)

    with pytest.raises(WatermarkNotImplementedError) as raised:
        operation(*arguments())

    assert raised.value.operation == name
    assert "not implemented" in str(raised.value).lower()


def test_stateful_facade_exposes_the_same_operations() -> None:
    sdk = watermark.Watermark()

    for operation in EXPECTED_OPERATIONS:
        assert callable(getattr(sdk, operation))
