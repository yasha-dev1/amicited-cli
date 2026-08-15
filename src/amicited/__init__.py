"""Public package for the AmICited CLI and Python SDK."""

from importlib.metadata import PackageNotFoundError, version

from amicited import watermark

try:
    __version__ = version("amicited")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0"

__all__ = ["__version__", "watermark"]
