"""Explicit input references accepted by the watermark SDK."""

from dataclasses import dataclass
from enum import StrEnum
from os import PathLike
from pathlib import Path


class InputKind(StrEnum):
    """Source kinds supported by the public SDK boundary."""

    TEXT = "text"
    FILE = "file"


@dataclass(frozen=True, slots=True)
class WatermarkInput:
    """An unambiguous text value or file reference.

    The SDK never guesses whether a string is content or a path. Callers choose
    one of the two constructors explicitly.
    """

    kind: InputKind
    content: str | None = None
    path: Path | None = None

    def __post_init__(self) -> None:
        if self.kind is InputKind.TEXT and (
            self.content is None or self.path is not None
        ):
            raise ValueError("Text input requires content and cannot include a path.")
        if self.kind is InputKind.FILE and (
            self.path is None or self.content is not None
        ):
            raise ValueError("File input requires a path and cannot include content.")

    @classmethod
    def text(cls, content: str) -> "WatermarkInput":
        """Create an input containing text, including an empty string."""
        return cls(kind=InputKind.TEXT, content=content)

    @classmethod
    def file(cls, path: str | PathLike[str]) -> "WatermarkInput":
        """Create a file reference without reading or modifying the file."""
        return cls(kind=InputKind.FILE, path=Path(path))
