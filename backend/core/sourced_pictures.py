"""The person asked for pictures *from the web*, in words.

**Asked for 12 October 2026, after a resort site was drawn instead of built:**
*"If users say source images or get images online, as part of a prompt for a
website, an app or a document, it should source the images from the web, not
try to generate them."*

So this is a statement about what the person said, and it settles one thing
before anything else is decided: **such a request is never a drawing.** Where
the pictures then come from depends on what is being made:

* a page (a website, an app) -- the photo pack's `photo:` references, which the
  window resolves after the page is written (`packs/photos`);
* a document -- the same references written as markdown images, which the
  documents runtime resolves when it makes the file (`DOCUMENT_PHOTO_GUIDANCE`).

Deliberately a word test, like `wants_photos`: it runs on every message, costs
nothing, and gives every model the same answer. Wrong in the "yes" direction
costs a photo search the person is still asked about first (the consent dialog
names every description); wrong in the "no" direction is today's behaviour.

In `core` rather than in the photo pack because the planner reads it, and
`core` does not import `packs` at module scope.
"""

from __future__ import annotations

import re

_PICTURES = r"(?:images?|photos?|photographs?|pictures?|pics?|imagery)"
_THE_WEB = (
    r"(?:online|(?:from|on|off|via)\s+(?:the\s+)?(?:web|internet|net)|the\s+(?:web|internet)|"
    r"google|unsplash|pexels|openverse|wikimedia|stock)"
)
#: "source" spelled the ways people type it: source, sorce, sourcing, sourced.
_SOURCE = r"sou?rc(?:e|es|ed|ing)"

_SOURCES_PICTURES = re.compile(
    # "get images online", "find photos from the web", "use pictures off the internet"
    rf"\b(?:{_SOURCE}|find|get|grab|fetch|pull|download|search(?:\s+for)?|look\s+for|look\s+up|use|"
    rf"include|add|with)\b(?:\W+\w+){{0,6}}?\W+{_PICTURES}\b(?:\W+\w+){{0,5}}?\W+{_THE_WEB}\b"
    # "source images" -- sourcing is getting them from somewhere else by definition
    rf"|\b{_SOURCE}\b(?:\W+\w+){{0,3}}?\W+{_PICTURES}\b"
    # "source the internet for images", "search the web for photos"
    rf"|\b(?:{_SOURCE}|search|scour|scrape|browse)\s+(?:the\s+)?(?:web|internet|net)\s+for\b"
    rf"(?:\W+\w+){{0,4}}?\W+{_PICTURES}\b"
    # "online images", "stock photos", "real photos"
    rf"|\b(?:online|web|internet|stock|real)\s+{_PICTURES}\b",
    re.IGNORECASE,
)


def asks_to_source_pictures(text: str) -> bool:
    """Whether the person asked, in words, for pictures found on the web."""
    return bool(_SOURCES_PICTURES.search(text or ""))


def document_photo_guidance() -> str:
    """What a document's body step is told when the person asked for web photos.

    The same contract as a page's `PHOTO_GUIDANCE`, in the document's own
    syntax: a markdown image whose address is ``photo:`` and a short
    description. The documents runtime finds each one when it makes the file,
    places it, and credits it -- the person is asked once per photo source
    first, by the same dialog a page uses.
    """
    try:
        from packs.photos.page import MAX_REFERENCES
    except Exception:  # noqa: BLE001 - a number in a sentence is not worth failing over
        MAX_REFERENCES = 8
    return (
        "\n\nPhotographs: the person asked for real photos from the web. Where a "
        "photograph belongs, put it on a line of its own as a markdown image whose "
        "address is photo: followed by a short description, for example\n"
        "![Lekki beach at sunset](photo:Lagos Lekki beach at sunset)\n"
        "Describe each photo in 3 to 8 plain words: subject, place or setting, light. "
        "When the document is about one place, begin every description with that "
        f"place's name. Use at most {MAX_REFERENCES} photos. A description is sent to "
        "a photo search, so never put a person's name, an email address, a price, a "
        "phone number or anything from the user's private notes in one. Zaram finds "
        "each photo and puts it, with its credit, into the file: never draw or invent "
        "a picture, and do not write photo credits yourself."
    )
