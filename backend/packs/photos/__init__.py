"""Web photos: real, credited pictures for the pages Zaram writes.

A page is written with `photo:<description>` references; this pack resolves
them afterwards from an openly licensed source, through the egress gate, once
the person has agreed to the destination. See `finder.py` for the consent and
retention story, `guard.py` for what may be sent, `page.py` for the model-facing
sentence, `source.py` for the sources (Openverse, then Wikimedia Commons as a
fallback), `pacing.py` for staying under their rate limits and `index.py` for
remembering what a description resolved to.
"""

from .finder import MAX_PHOTOS, find_photos, photos_dir
from .page import PHOTO_GUIDANCE, apply_photos, photo_references, wants_photos

__all__ = [
    "MAX_PHOTOS",
    "PHOTO_GUIDANCE",
    "apply_photos",
    "find_photos",
    "photo_references",
    "photos_dir",
    "wants_photos",
]
