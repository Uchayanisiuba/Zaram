"""Drawing pictures on the user's own machine.

The engine half of image generation, kept apart from the runtime that calls it
for the same reason `artifacts/` is kept apart from `runtimes/documents/`: what
draws is replaceable, and what records provenance is not.
"""

from .contracts import (
    AVAILABLE,
    DEFAULT_STEPS,
    MAX_IMAGES,
    Availability,
    GeneratedImage,
    ImageProgress,
    ImageProvider,
    ImageRequest,
    ProgressCallback,
)
from .local_sdxl import SdxlProvider, find_checkpoint

__all__ = [
    "AVAILABLE",
    "DEFAULT_STEPS",
    "MAX_IMAGES",
    "Availability",
    "GeneratedImage",
    "ImageProgress",
    "ImageProvider",
    "ImageRequest",
    "ProgressCallback",
    "SdxlProvider",
    "find_checkpoint",
]
