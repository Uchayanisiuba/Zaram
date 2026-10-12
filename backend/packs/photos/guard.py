"""What may be written into a photo search, and what may not.

A photo description is **model-written text that leaves the machine**. That is
the one property that makes it different from the web-search query, which is
the user's own raw prompt and therefore carries nothing the user did not type
(`tests/test_outbound_query_invariant.py` holds that structurally). Here the
page was written by a model that had recall in its context, so rule 8 -- *nothing
derived from the Spine may appear in an outbound query* -- cannot be satisfied
by construction. It is satisfied by checking, and by making the check
impossible to forget: `find_photos` takes the Spine's text as a required
argument rather than an optional one, so the caller that skips it is the one
that fails to call.

What the check is, said accurately
----------------------------------
Two cheap tests against the text of what the Spine holds, each with the user's
own request as the exemption (their words are theirs, not recalled):

* **A verbatim run.** Any three consecutive words of the description that also
  appear, in that order, inside a stored fact or passage. This is the shape a
  copied sentence takes, and it is what a marker string planted in the Spine
  looks like when it leaks.
* **A proper name from memory.** A capitalised word the Spine contains and the
  request does not. Names, clients and places are where private detail lives,
  and a model that writes "Adaeze Okafor's office" for a picture has leaked one
  whether or not three words matched.

It does not catch a lowercase single word lifted from a note, and it cannot
prove a negative. It is a floor, not a proof, and two things stand behind it:
the description is capped to a handful of words (there is little room to
smuggle anything), and the first time it reaches the photo source the person is
shown every description exactly as it will be sent and may strike any of them.

Everything here is structural text handling; no model is consulted, so the
check works the same for any model that wrote the page.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Sequence

#: A description is a few words about a picture. More than this is a sentence,
#: and a sentence is where a recalled fact fits.
MAX_WORDS = 8
MAX_CHARS = 80
#: Three consecutive words is long enough that an ordinary phrase ("beach at
#: sunset") rarely matches a note by chance and short enough that a copied
#: clause cannot dodge it by changing one word in the middle.
RUN_LENGTH = 3

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_STRIP = re.compile(r"[^\w\s'\-.,]", re.UNICODE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+", re.UNICODE)
_URLISH = re.compile(
    r"(?:://|\bwww\.|\b[\w-]+\.(?:com|org|net|io|ng|co|uk|app|dev|me|info)\b)",
    re.IGNORECASE,
)
#: Phone numbers, account numbers, invoice references: a long run of digits
#: with only the separators people put in them.
_LONG_DIGITS = re.compile(r"\d[\d\s().\-]{6,}\d|\d{5,}")


class DescriptionRefused(ValueError):
    """A description that will not be sent, with a sentence saying why."""

    def __init__(self, reason: str, code: str = "refused_description"):
        super().__init__(reason)
        self.reason = reason
        self.code = code


def description_key(text: str) -> str:
    """The identity of a description: what two spellings of one picture share.

    Used to dedupe and to match a page's `photo:` reference to a result, so a
    stray space or a different case cannot make one picture two requests.
    """
    return " ".join(_TOKEN.findall(unicodedata.normalize("NFKC", text or "").lower()))


def clean_description(raw: object) -> str:
    """The text that would be sent for ``raw``, or `DescriptionRefused`.

    Structure only: nothing here knows what the Spine holds (that is
    `check_against_spine`). Removes everything that is not a word, caps the
    length, and refuses outright what no picture description needs -- an
    address, a link, a phone or account number -- rather than trimming it,
    because a trimmed email is still a half-sent email.
    """
    if not isinstance(raw, str):
        raise DescriptionRefused("The description was not text.")
    text = unicodedata.normalize("NFKC", raw)
    text = "".join(ch for ch in text if ch.isprintable() or ch in "\t ")

    if _EMAIL.search(text):
        raise DescriptionRefused("The description contained an email address, so it was not sent.")
    if _URLISH.search(text):
        raise DescriptionRefused("The description contained a web address, so it was not sent.")
    if _LONG_DIGITS.search(text):
        raise DescriptionRefused("The description contained a long number, so it was not sent.")

    text = _STRIP.sub(" ", text).replace("_", " ")
    words = text.split()
    words = words[:MAX_WORDS]
    text = " ".join(words)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rsplit(" ", 1)[0]
    text = text.strip(" .,-'")
    if len(text) < 3 or not any(ch.isalpha() for ch in text):
        raise DescriptionRefused("The description was too short to search for.", code="empty_description")
    return text


def _norm(text: str) -> str:
    return " ".join(_TOKEN.findall(unicodedata.normalize("NFKC", text or "").lower()))


def _capitalised_names(cleaned: str) -> list[str]:
    """Words that read as names: capitalised, and not just a sentence opening.

    The first word of a description is capitalised by habit ("Busy market"),
    so it only counts when the word after it is capitalised too ("Adaeze
    Okafor"), which is the shape of a name rather than of a sentence.
    """
    tokens = _TOKEN.findall(cleaned)
    names: list[str] = []
    for i, tok in enumerate(tokens):
        if len(tok) < 3 or not tok[0].isupper():
            continue
        if i == 0 and not (len(tokens) > 1 and tokens[1][0].isupper()):
            continue
        names.append(tok.lower())
    return names


def check_against_spine(
    cleaned: str,
    spine_texts: Sequence[str],
    request_text: str = "",
) -> None:
    """Raise `DescriptionRefused` if ``cleaned`` looks lifted from the Spine.

    ``spine_texts`` is the text of every stored fact and passage the caller can
    read; ``request_text`` is the person's own request for the page, whose
    words are exempt because they are not recalled -- the same reason the
    search query is allowed to be exactly the user's prompt.
    """
    if not spine_texts:
        return
    # One string, records separated by a character no token contains, so a run
    # of words can never be matched across the end of one fact and the start of
    # the next.
    padded = " " + " \n ".join(_norm(t) for t in spine_texts) + " "
    request = " " + _norm(request_text) + " "

    tokens = _norm(cleaned).split()
    for i in range(0, max(0, len(tokens) - RUN_LENGTH + 1)):
        run = f" {' '.join(tokens[i : i + RUN_LENGTH])} "
        if run in padded and run not in request:
            raise DescriptionRefused(
                "The description repeated wording from your memory, so it was not sent.",
                code="spine_derived",
            )

    for name in _capitalised_names(cleaned):
        if f" {name} " in padded and f" {name} " not in request:
            raise DescriptionRefused(
                f"The description named “{name}”, which comes from your memory "
                "rather than your request, so it was not sent.",
                code="spine_derived",
            )


def prepare(
    raw: object,
    spine_texts: Sequence[str] | None,
    request_text: str = "",
) -> str:
    """Clean a description and check it, or raise `DescriptionRefused`.

    ``spine_texts=None`` means *the Spine could not be read*, and that fails
    closed: a guard that cannot look refuses, because "I could not check" is not
    "nothing was there".
    """
    cleaned = clean_description(raw)
    if spine_texts is None:
        raise DescriptionRefused(
            "Zaram could not check this description against your memory, so it was not sent.",
            code="spine_unreadable",
        )
    check_against_spine(cleaned, spine_texts, request_text)
    return cleaned


def lines_to_queries(body: str | None) -> list[str]:
    """The descriptions in a confirmation body, one per line."""
    return [line.strip() for line in (body or "").splitlines() if line.strip()]


def content_words(text: str, stop: Iterable[str]) -> list[str]:
    """Words of ``text`` with the filler removed, for a shorter retry query."""
    stopset = set(stop)
    return [w for w in _TOKEN.findall(text) if w.lower() not in stopset and len(w) > 1]
