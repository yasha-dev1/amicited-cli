"""Public layer interface and built-in text-only implementations."""

from amicited.watermark.layers.base import TextWatermarkLayer
from amicited.watermark.layers.bidi_controls import BidiControlLayer
from amicited.watermark.layers.confusables import ConfusableLayer
from amicited.watermark.layers.exotic_spaces import ExoticSpaceLayer
from amicited.watermark.layers.hidden_unicode import HiddenUnicodeLayer
from amicited.watermark.layers.normalization import UnicodeNormalizationLayer
from amicited.watermark.layers.semantic import ChatModel, SemanticRewriteLayer
from amicited.watermark.layers.unicode_tags import UnicodeTagLayer
from amicited.watermark.layers.whitespace_patterns import WhitespacePatternLayer
from amicited.watermark.options import SemanticProvider

__all__ = [
    "BidiControlLayer",
    "ChatModel",
    "ConfusableLayer",
    "ExoticSpaceLayer",
    "HiddenUnicodeLayer",
    "SemanticRewriteLayer",
    "SemanticProvider",
    "TextWatermarkLayer",
    "UnicodeTagLayer",
    "UnicodeNormalizationLayer",
    "WhitespacePatternLayer",
]
