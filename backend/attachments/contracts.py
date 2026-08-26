"""What a file dropped into a conversation is, and what it is not.

**Rule 7d is the whole design.** Conversation is ephemeral, and entering the
Spine is a decision the system makes rather than a side effect of the user
dragging something onto a message box. A person attaching a contract to ask one
question about it has not decided to add it to their knowledge base — and
indexing it because they asked about it would fill the Spine with things they
looked at once, which is exactly the store that stops being worth searching.

So an attachment is **working state**: parsed, used for the exchange it was
attached to, and offered afterwards. `Attachment` deliberately carries no
`fact_ids` and no scope, because it is not in the Spine and the type should
make that impossible to forget. Keeping one is a separate act that goes through
the ordinary ingest path, and produces an ordinary source.

The second thing this module exists for is honesty about **what was read**.
`Attachment.text` is the whole document; whether the whole of it reached the
model is a different question, answered per request against that model's
budget, and reported to the user in words. A file that was attached and then
silently summarised is worse than one that was refused, because the answer
looks complete.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class AttachmentKind(str, Enum):
    """What sort of thing was attached, and therefore how it reaches a model.

    The distinction is load-bearing rather than descriptive. A document becomes
    *text in the prompt*, sized against a character budget and excerpted when
    it does not fit. An image becomes *a separate field on the request*, is
    never excerpted, and can only go to a model that can see. Treating them
    alike is how a picture ends up base64-encoded inside a prompt, or how a
    contract gets sent to a vision endpoint.
    """

    DOCUMENT = "document"
    IMAGE = "image"


@dataclass(frozen=True)
class Attachment:
    """One file, parsed, held for the conversation it was attached to.

    Frozen, because nothing about a parsed file changes after it is read. A
    correction to an attachment is a different file.
    """

    id: str
    #: Which conversation it belongs to. Attachments never cross sessions —
    #: a document you showed Zaram yesterday is not silently in scope today.
    session_id: str
    #: What the user called it. Shown as it arrived; never prettified into a
    #: title, which would be a value nobody entered.
    name: str
    #: Lowercase, with the dot. `""` when the file had none.
    suffix: str
    #: Where the bytes are, so keeping it in Knowledge later is a move rather
    #: than a re-upload. Under the data directory, never in the Spine.
    path: str
    #: The extracted text, whole. What the *model* sees is decided per request.
    #: Empty for an image, which has no text and must not pretend to.
    text: str
    #: Which parser read it, so "how do you know that" has an answer.
    parser: str
    kind: str = AttachmentKind.DOCUMENT.value
    #: Base64 for an image, without a data-URI prefix. Empty for a document.
    #:
    #: Held in memory rather than re-read from disk on every request because a
    #: conversation asks several questions about the same picture, and because
    #: the encoding is what the engine wants either way.
    data: str = ""
    #: Pages, where the format has them. 0 where it does not — not a guess.
    pages: int = 0
    created_at: float = field(default_factory=time.time)

    @property
    def chars(self) -> int:
        """Characters extracted. Measured, not estimated."""
        return len(self.text)

    def to_dict(self) -> Dict[str, Any]:
        """What the interface is told. **Never the text.**

        A chip in a composer needs a name, a size and a reason to trust that
        the file was read. It does not need the document, and sending one
        would put the whole of a contract into every listing response.
        """
        return {
            "id": self.id,
            "name": self.name,
            "suffix": self.suffix,
            "chars": self.chars,
            "pages": self.pages,
            "parser": self.parser,
            "kind": self.kind,
            "created_at": self.created_at,
        }


class AttachmentError(Exception):
    """A file that could not become an attachment, and why, in a sentence.

    The message is written for the person who dropped the file, not for a log.
    "That is a .heic, and Zaram cannot read images yet" is something they can
    act on; "unsupported suffix" is not.
    """
