"""Drawing pictures on the user's own machine.

The engine half of image generation, kept apart from the runtime that calls it
for the same reason `artifacts/` is kept apart from `runtimes/documents/`: what
draws is replaceable, and what records provenance is not.
"""

from .contracts import (
    MAX_REFERENCES,
    TEXT_TO_IMAGE_ONLY,
    ImageCapabilities,
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
from .local_flux import FluxProvider, find_model

__all__ = [
    "AVAILABLE",
    "DEFAULT_STEPS",
    "MAX_IMAGES",
    "MAX_REFERENCES",
    "TEXT_TO_IMAGE_ONLY",
    "Availability",
    "ImageCapabilities",
    "GeneratedImage",
    "ImageProgress",
    "ImageProvider",
    "ImageRequest",
    "ProgressCallback",
    "FluxProvider",
    "find_model",
]
