"""Files attached to a conversation — working state, never the Spine.

Rule 7d in a package: a document dropped into a message is used for that
exchange and offered afterwards, rather than indexed because the user asked
about it. See `contracts.py` for why that shape, and `compose.py` for the half
that says out loud how much of it the model actually saw.
"""

from .compose import BUDGET_CHARS, GAP, Composition, DocumentRead, Mode, compose
from .contracts import Attachment, AttachmentError
from .store import (
    DIRNAME,
    IMAGE_SUFFIXES,
    MAX_BYTES,
    MAX_PER_SESSION,
    PREFIX,
    AttachmentStore,
    default_root,
)

__all__ = [
    "BUDGET_CHARS",
    "DIRNAME",
    "GAP",
    "IMAGE_SUFFIXES",
    "MAX_BYTES",
    "MAX_PER_SESSION",
    "PREFIX",
    "Attachment",
    "AttachmentError",
    "AttachmentStore",
    "Composition",
    "DocumentRead",
    "Mode",
    "compose",
    "default_root",
]
