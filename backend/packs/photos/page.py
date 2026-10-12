"""The page side of photos: what the model is told, and how its references are read.

A page is written by one model turn with no tools and previewed in a sandbox
with no network, so the model cannot fetch a picture and must not guess a URL.
What it can do is *say what picture belongs where*. It writes
`<img src="photo:Lagos Lekki beach at sunset" alt="...">`; Zaram resolves those
descriptions afterwards (`finder.find_photos`) and substitutes the pictures.

Nothing here touches the network. `wants_photos` and `PHOTO_GUIDANCE` decide and
phrase what the model is asked; `photo_references` and `apply_photos` read and
rewrite the finished page.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import Mapping

from .guard import MAX_WORDS, description_key

#: The most pictures one page may ask for. The finder enforces the same number,
#: so a model that ignores the sentence below still cannot cause more requests.
MAX_REFERENCES = 8

#: The words the guidance below uses inside its own pattern. A small model
#: sometimes copies a template literally; a reference made of these is not a
#: description of anything, so it is not read as one.
_PLACEHOLDER_KEYS = frozenset({"short description of the photo"})

#: Added to the page instructions for a site-shaped request. Written for a small
#: local model: one pattern to copy, two examples, the limits stated as rules.
#: It tells the model what not to put in a description because a description is
#: sent to a photo search once the person agrees -- the instruction is a courtesy
#: and `guard.py` is the enforcement.
PHOTO_GUIDANCE = (
    "Real photographs: decide whether this page needs any. A site with a public "
    "face -- a resort, a restaurant, a portfolio, a business -- usually does; a "
    "game, a tool, a calculator or a dashboard usually does not, and then write "
    "none. Where a real photograph belongs (a hero banner, a gallery, "
    "a destination, room, dish or team card), write "
    '<img src="photo:short description of the photo" alt="what the photo shows"> '
    "and do not invent a picture, an emoji stand-in, a gradient block or any "
    "other image address. Describe the photo in 3 to 8 plain words: subject, "
    "place or setting, light. When the site is about one place, begin every "
    "description with that place's name, so the photos are of it. For example "
    "photo:Lagos Lekki beach at sunset, "
    "photo:street food market at night, photo:hotel room with sea view. A "
    "background picture is style=\"background-image:url('photo:mountain village at dawn')\". "
    f"Use at most {MAX_REFERENCES} photos on the whole page. A description is sent to a "
    "photo search, so never put a person's name, an email address, a price, a "
    "phone number or anything from the user's private notes in one. Zaram "
    "replaces each photo: reference with a real, credited picture after the "
    "page is written, so do not write photo credits yourself. Pictures in a "
    "page are found, never drawn: if the person asked for a generated or drawn "
    "picture in the page, use a photo: reference for it and say in one line that "
    "page pictures are real photos, and that they can ask separately for a "
    "picture to be drawn."
)

# --------------------------------------------------------------- when it applies

#: Words that name a thing with a public face. Alone they are not enough to ask
#: for photographs ("restaurant bill calculator"), so they need a page word too.
_SUBJECTS = re.compile(
    r"\b(tourism|tourist|travel|tours?|safari|lodge|resort|hotel|hostel|guest ?house|"
    r"airbnb|restaurant|caf[eé]|bakery|coffee|catering|food|chef|salon|spa|barber|"
    r"boutique|florist|wedding|photograph(?:y|er)|studio|gallery|museum|church|school|"
    r"academy|ngo|non-?profit|charity|farm|real ?estate|estate agent|property|"
    r"gym|fitness|yoga|dentist|clinic|agency|portfolio|blog|magazine|festival|event)\b",
    re.IGNORECASE,
)
#: A request that is plainly about a page or a site, whatever the subject.
_SITE_WORDS = re.compile(
    r"\b(web ?site|web ?page|landing ?page|home ?page|one[- ]page|brochure site|"
    r"storefront|microsite)\b",
    re.IGNORECASE,
)
#: Softer: enough only when a subject is present as well.
_BUILD_WORDS = re.compile(r"\b(page|site|build|make|create|design|write|generate)\b", re.IGNORECASE)
#: Things that are applications, not places with a public face. These veto only
#: when the request never says "website" or "landing page" -- "a website for my
#: game studio" is a site and still wants photographs.
_APP_WORDS = re.compile(
    r"\b(games?|calculators?|converters?|timers?|stopwatch|quiz|todo|to-do|"
    r"tic[- ]tac[- ]toe|snake|tetris|pong|chess|sudoku|clock|counter|"
    r"dashboard|spreadsheet|chart|simulator|simulation|animation|visuali[sz]er|"
    r"tool|utility|generator|checker|tracker|editor)\b",
    re.IGNORECASE,
)


def wants_photos(text: str | None) -> bool:
    """Whether a request is the kind of page that should carry real photographs.

    True for a website, landing page or portfolio, and for a business with a
    public face asked for as a page. False for a game, a calculator or a tool,
    where a stock photograph is noise and a search would be a pointless request
    to make. Deliberately a keyword test, not a model call: it runs on every
    page request, must cost nothing, and must give the same answer for any
    model. Wrong in the "yes" direction is cheap (the model may use no photos);
    wrong in the "no" direction costs only a page without photos.
    """
    if not text or not text.strip():
        return False
    strong = bool(_SITE_WORDS.search(text))
    if strong:
        return True
    if _APP_WORDS.search(text):
        return False
    return bool(_SUBJECTS.search(text) and _BUILD_WORDS.search(text))


# ------------------------------------------------------------- reading the page

_ATTR = re.compile(
    r"""(?P<head>\b(?:src|srcset|data-src|poster|content)\s*=\s*(?P<q>["']))"""
    r"""(?P<pre>\s*)photo:(?P<desc>.*?)(?P=q)""",
    re.IGNORECASE | re.DOTALL,
)
_CSS = re.compile(
    r"""(?P<head>url\(\s*(?P<q>["']?))(?P<pre>\s*)photo:(?P<desc>.*?)(?P=q)(?P<tail>\s*\))""",
    re.IGNORECASE | re.DOTALL,
)
#: `photo:beach 2x` -- a srcset density or width descriptor after the reference.
_SRCSET_TAIL = re.compile(r"\s+\d+(?:\.\d+)?[wx]\s*$", re.IGNORECASE)


def _decode(raw: str) -> str:
    return " ".join(html.unescape(urllib.parse.unquote(raw)).split())


def _split_descriptor(desc: str) -> tuple[str, str]:
    m = _SRCSET_TAIL.search(desc)
    return (desc[: m.start()], m.group(0)) if m else (desc, "")


def photo_references(page: str) -> list[str]:
    """Every distinct `photo:` description in the page, in order of appearance.

    Reads `src`, `srcset`, `data-src`, `poster` and `content` attributes and CSS
    `url(...)`, in HTML or in a stylesheet. Percent-encoding and entities are
    decoded, so `photo:Lagos%20beach` and `photo:Lagos beach` are one reference.
    Not capped here -- the caller decides what to do with the ninth.
    """
    # In page order across both kinds, because only the first eight are
    # fetched and a page's hero is often a CSS background: reading attributes
    # first put it last, past the limit, on a live tourism page.
    hits = sorted(
        [(m.start(), _split_descriptor(m.group("desc"))[0]) for m in _ATTR.finditer(page or "")]
        + [(m.start(), m.group("desc")) for m in _CSS.finditer(page or "")]
    )
    found: dict[str, str] = {}
    for _, raw in hits:
        text = _decode(raw)
        if text and description_key(text) not in _PLACEHOLDER_KEYS:
            found.setdefault(description_key(text), text)
    return list(found.values())


def apply_photos(page: str, replacements: Mapping[str, str]) -> str:
    """The page with each resolved `photo:` reference replaced by its address.

    ``replacements`` maps a description (any spelling; it is keyed through
    `description_key`) to the URL the page should use. A reference with no entry
    is left exactly as written, so the caller can see what was not resolved
    and put a labelled placeholder there instead -- this never invents a picture.
    """
    keyed = {description_key(k): v for k, v in replacements.items() if v}

    def sub_attr(m: re.Match[str]) -> str:
        desc, descriptor = _split_descriptor(m.group("desc"))
        url = keyed.get(description_key(_decode(desc)))
        if not url:
            return m.group(0)
        q = m.group("q")
        return f"{m.group('head')}{m.group('pre')}{html.escape(url, quote=True)}{descriptor}{q}"

    def sub_css(m: re.Match[str]) -> str:
        url = keyed.get(description_key(_decode(m.group("desc"))))
        if not url:
            return m.group(0)
        return f"{m.group('head')}{m.group('pre')}{html.escape(url, quote=True)}{m.group('q')}{m.group('tail')}"

    return _CSS.sub(sub_css, _ATTR.sub(sub_attr, page or ""))


__all__ = [
    "MAX_REFERENCES",
    "MAX_WORDS",
    "PHOTO_GUIDANCE",
    "apply_photos",
    "photo_references",
    "wants_photos",
]
