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
from typing import Any, Dict


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
    text: str
    #: Which parser read it, so "how do you know that" has an answer.
    parser: str
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
            "created_at": self.created_at,
        }


class AttachmentError(Exception):
    """A file that could not become an attachment, and why, in a sentence.

    The message is written for the person who dropped the file, not for a log.
    "That is a .heic, and Zaram cannot read images yet" is something they can
    act on; "unsupported suffix" is not.
    """
