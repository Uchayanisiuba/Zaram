"""A picture the person attached, as something Zaram builds *with*.

Until now an attached picture could be looked at -- a vision model sees it --
and nothing more. "Make me a portfolio site from these photos" produced a page
of grey boxes, and "put my passport photo on this form" produced a form without
one. This is the missing half: the picture becomes content in what is built.

**The model is given a name, never the bytes.** A 2 MB photograph is ~2.7 MB of
base64, which would overflow the window of a local model several times over and
cost a cloud one real money to be told something it cannot use. So every
picture gets a short name that is safe to write into markup, the model is told
"these pictures exist, by these names", and it writes `<img src="photo-1.jpg">`
or `![passport photo](photo-1.jpg)`. The bytes are put in afterwards, on this
machine: by the window for a page (`frontend/src/lib/pagePictures.ts`), by the
documents runtime for a document (`artifacts/markdown_blocks.py`).

**The name is assigned once, here, and read everywhere else.** It is stored on
the attachment and sent to the window with it, so the prompt, the page and the
document cannot disagree about which name means which picture -- there is no
second copy of the rule to drift.

**What each destination can carry.** A browser shows png, jpeg, gif, webp and
bmp; it does not show tiff or heic. A document is made through Pillow and can
carry whatever Pillow opens, converted to png when it is not already png or
jpeg. A format neither can use gets no name at all, and the model is told so in
words, so it can tell the person rather than write a reference that shows
nothing.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence

from .contracts import Attachment, AttachmentKind

#: What a browser will draw. A page that names anything else shows nothing.
PAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"})

#: What a document can carry once Pillow has read it. Wider than the page's
#: list by tiff; heic is absent because Pillow does not open it without a
#: plug-in Zaram does not ship.
DOCUMENT_SUFFIXES = PAGE_SUFFIXES | {".tif", ".tiff"}

#: A file name is kept when it is already made only of these and short enough
#: to read. Anything else (spaces, accents, brackets) is replaced rather than
#: repaired: a repaired name is a name the person did not give, and the
#: generic one at least says plainly that it is generic.
_SAFE_STEM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")

#: A picture's name may be written into markup, CSS and prose, so nothing
#: outside this set ever reaches a prompt.
_NOT_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def page_name_for(original: str, suffix: str, taken: Iterable[str]) -> str:
    """The short name a picture goes by in what Zaram builds, or ``""``.

    ``""`` means no destination can use this format. Otherwise the person's own
    file name when it is already safe -- `portrait.jpg` stays `portrait.jpg`,
    which is what they will recognise in the page -- and `photo-N.ext` when it
    is not or when it would repeat a name already in use. Compared without
    regard to case, because the page may be saved to a filesystem that does not
    distinguish it.
    """
    suffix = suffix.lower()
    if suffix not in DOCUMENT_SUFFIXES:
        return ""
    used = {t.lower() for t in taken if t}
    stem = Path(original or "").stem
    if _SAFE_STEM.match(stem) and f"{stem}{suffix}".lower() not in used:
        return f"{stem}{suffix}"
    number = 1
    while f"photo-{number}{suffix}".lower() in used:
        number += 1
    return f"photo-{number}{suffix}"


@dataclass(frozen=True)
class PictureRef:
    """One attached picture as the prompt describes it. No bytes."""

    name: str
    #: What the person called the file, cleaned so it can sit in a prompt.
    original: str
    suffix: str
    attachment_id: str

    @property
    def for_pages(self) -> bool:
        return self.suffix in PAGE_SUFFIXES

    @property
    def for_documents(self) -> bool:
        return self.suffix in DOCUMENT_SUFFIXES


def _clean(original: str) -> str:
    """A file name as text that is safe to put in front of a model."""
    return _NOT_NAME.sub("-", original or "").strip("-.")[:60] or "picture"


def refs_for(attached: Iterable[Attachment]) -> List[PictureRef]:
    """The pictures among ``attached``, in the order they were attached."""
    return [
        PictureRef(
            name=a.page_name,
            original=_clean(a.name),
            suffix=a.suffix.lower(),
            attachment_id=a.id,
        )
        for a in attached
        if a.kind == AttachmentKind.IMAGE.value
    ]


def _unusable(refs: Sequence[PictureRef], usable: Callable[[PictureRef], bool]) -> List[str]:
    return [r.original for r in refs if not (r.name and usable(r))]


def page_guidance(refs: Sequence[PictureRef], *, seen: bool) -> str:
    """What to tell the model about the pictures, for a page. ``""`` for none.

    ``seen`` is whether the model was actually shown them. When it was not --
    nothing installed here can see -- it is told so, because a model that is
    handed names and no pictures will otherwise invent captions for them.
    """
    usable = [r for r in refs if r.name and r.for_pages]
    lines: List[str] = []
    if usable:
        lines.append(
            "The person attached these pictures to this conversation. Use them in the "
            "page by these exact file names as image sources, in the order attached, "
            "and do not write the pictures themselves out as data: URLs -- Zaram puts "
            "the pictures in when it runs or saves the page:"
        )
        lines.extend(f"- {r.name}" for r in usable)
        lines.append(
            "Write them as ordinary relative references, for example "
            '<img src="' + usable[0].name + '" alt="…"> or '
            "background-image: url(" + usable[0].name + "). Do not add a path in front "
            "of the name, do not invent other picture files, and give every picture an "
            "alt text that says what it shows."
        )
        if not seen:
            # Measured 11 October 2026: "ask rather than guess" made a model that
            # cannot see stop and ask what a hero photo showed instead of building
            # the page. Placing a picture by name needs no description of it, so
            # the model places it and keeps its words to what it was told.
            lines.append(
                "You were not shown the pictures themselves. Use them anyway, where the "
                "person asked: their contents are not needed to place them. Describe a "
                "picture only from what the person said about it; otherwise give it a "
                "plain alt text such as \"Hero image\" or \"Photo\". Do not stop to ask "
                "what a picture shows."
            )
    skipped = _unusable(refs, lambda r: r.for_pages)
    if skipped and refs:
        lines.append(
            "These attached pictures are in a format a browser cannot show, so they "
            "cannot go in a page: " + ", ".join(skipped) + ". Say so in one line "
            "instead of referring to them."
        )
    return "\n".join(lines)


#: What an invoice, a CV and a deck are told, by the field the picture goes in.
#: Those three are made of fields read out of the answer, not of markdown, so
#: the model is asked to name the picture in the answer where the field will
#: pick it up; the extraction step (`artifacts/extract.py`) is offered the same
#: names and only accepts one of them.
_FIELD_GUIDANCE = {
    "logo": (
        "An invoice or quote carries one picture, its logo, printed at the top. If "
        "the person asked for a logo or a picture on it, write the exact file name "
        "of that one picture on a line of its own as `Logo: <file name>`, for "
        "example Logo: {first}. "
    ),
    "photo": (
        "A CV carries one picture, the person's photo, printed at the top. If the "
        "person asked for a photo on it, write the exact file name of that one "
        "picture on a line of its own as `Photo: <file name>`, for example "
        "Photo: {first}. "
    ),
    "slide": (
        "A slide can carry one picture. If the person asked for a picture on a "
        "slide, write the exact file name on a line of its own directly under "
        "that slide's heading as `Slide image: <file name>`, for example "
        "Slide image: {first}. "
    ),
}


def document_guidance(refs: Sequence[PictureRef], *, seen: bool, slot: str = "") -> str:
    """The same, for a document. ``""`` for none.

    ``slot`` is the field the picture goes in for the kinds made of fields --
    ``"logo"`` (invoice, quote), ``"photo"`` (CV) or ``"slide"`` (deck) -- and
    ``""`` for a document written as markdown, where it is an image on a line of
    its own. An unknown slot is treated as markdown rather than invented.
    """
    usable = [r for r in refs if r.name and r.for_documents]
    if not usable:
        return ""
    if slot in _FIELD_GUIDANCE:
        lines = [
            "The person attached these pictures to this conversation. "
            + _FIELD_GUIDANCE[slot].format(first=usable[0].name)
            + "The picture is put in when the file is made; never write its "
            "contents, a path or a web address, and name no picture the person did "
            "not ask for:"
        ]
    else:
        lines = [
            "The person attached these pictures to this conversation. To place one in the "
            "document, put it on a line of its own as a markdown image using its exact "
            "file name, for example ![passport photo](" + usable[0].name + "). The "
            "picture is put in when the file is made; never write its contents. Place "
            "only the pictures the person asked for, and only where they belong:"
        ]
    lines.extend(f"- {r.name}" for r in usable)
    if not seen:
        lines.append(
            "You were not shown the pictures themselves, so describe them only if the "
            "person told you what they are."
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# The bytes, for a document. Read here, on this machine, at the moment the file
# is made -- never copied into a prompt.
# --------------------------------------------------------------------------- #

#: The largest picture a document will carry, matching `main._MAX_IMAGE_BYTES`
#: for the same reason: a file people email must stay below what bounces.
MAX_DOCUMENT_PICTURE_BYTES = 12 * 1024 * 1024


@dataclass(frozen=True)
class DocumentPicture:
    """A picture ready to become an `ImageBlock`."""

    name: str
    original: str
    attachment_id: str
    data: bytes
    media_type: str


def _sniff(data: bytes) -> Optional[str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def as_document_picture(ref: PictureRef, raw: bytes) -> Optional[DocumentPicture]:
    """``raw`` as bytes a document can carry, or ``None`` when it cannot.

    png and jpeg go through untouched. Anything else Pillow can open is
    converted to png, which is a change of container and not of picture.
    """
    if not raw or len(raw) > MAX_DOCUMENT_PICTURE_BYTES:
        return None
    media = _sniff(raw)
    if media is None:
        try:
            from PIL import Image

            with Image.open(io.BytesIO(raw)) as opened:
                opened.load()
                converted = opened.convert("RGBA" if "A" in opened.getbands() else "RGB")
                out = io.BytesIO()
                converted.save(out, format="PNG")
            raw, media = out.getvalue(), "image/png"
        except Exception:  # noqa: BLE001 - a picture that will not open is left out, not fatal
            return None
    return DocumentPicture(
        name=ref.name,
        original=ref.original,
        attachment_id=ref.attachment_id,
        data=raw,
        media_type=media,
    )


_store = None


def use_store(store) -> None:
    """Tell this module which attachment store the running app holds.

    A module-level hand-off rather than an import of `main`, which would be a
    cycle; set once where the store is made.
    """
    global _store
    _store = store


def refs_for_session(session_id: str) -> List[PictureRef]:
    """Pictures held for ``session_id``, named. Empty when no store is set."""
    if _store is None:
        return []
    return refs_for(_store.for_session(session_id))


def document_pictures_for_session(session_id: str) -> List[DocumentPicture]:
    """Every picture held for ``session_id`` that a document can carry."""
    if _store is None:
        return []
    found: List[DocumentPicture] = []
    for attachment in _store.for_session(session_id):
        if attachment.kind != AttachmentKind.IMAGE.value or not attachment.page_name:
            continue
        ref = refs_for([attachment])[0]
        if not ref.for_documents:
            continue
        try:
            raw = Path(attachment.path).read_bytes()
        except OSError:
            continue
        picture = as_document_picture(ref, raw)
        if picture is not None:
            found.append(picture)
    return found
