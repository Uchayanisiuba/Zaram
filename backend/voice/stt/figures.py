"""Whether a transcript contains something that must not be trusted.

**Measured, not hypothesised.** One sentence, one voice, one model, three runs
through the real route (``test_speech_roundtrip.py``):

    said:  My day rate for Harbour Lane is four hundred and twenty five thousand naira.
    heard: My day rate for Harbor Lane is 425,000 Nira.
    heard: My day rate for Harbor Lane is 400 and 25,000 Nira.
    heard: My day rate for Harbor Lane is $400,000 and $25,000.

Two failures, and the second is much the worse. The figure is unstable — "four
hundred and twenty five thousand" parses as one number or two depending on the
run. And **the currency is invented**: the audio says *naira*, the third
transcript says **$**, twice, unhedged. A Nigerian day rate rendered as dollars
is wrong by roughly fifteen hundred times, in the direction that looks
reasonable on an invoice, and nothing downstream can catch it because
``$400,000`` is a well-formed amount.

So the recorded decision is **speech is for prose; amounts get typed or get
confirmed**. This module is the "or get confirmed" half.

**It does not correct anything, and that is deliberate.** Rewriting ``$`` to
``₦`` would be guessing at the user's intent from audio that has already proven
unreliable, and a confident wrong correction is the failure rule 9 is about. The
only honest move is to say *this part is not trustworthy, look at it* and leave
the text exactly as heard.

**It errs toward flagging.** A false positive costs a glance at a warning; a
false negative puts an invented number in front of a client. The two are not
comparable, so the patterns are broad on purpose — a bare year, an address, a
phone number all trip it, and that is the right side to be wrong on.
"""

from __future__ import annotations

import re
from typing import NamedTuple

#: Symbols that assert a currency. `$` leads because it is the one Whisper
#: invented, and `₦` is here because the correct answer must also be flagged —
#: the point is not "the currency is wrong", it is "a machine chose a currency
#: from audio, and a machine cannot be trusted to".
_CURRENCY_SYMBOLS = "$€£₦¥₹₽₩"

#: Spelled-out currencies, so "four hundred thousand naira" trips this before it
#: ever becomes digits. Not exhaustive and does not need to be: any digit at all
#: also trips the check below, so this only has to catch the case where the
#: amount survived as words.
_CURRENCY_WORDS = (
    "naira|kobo|dollars?|cents?|pounds?|pence|euros?|cedis?|rand|shillings?"
    "|rupees?|yen|yuan|won|francs?|dinars?|dirhams?|pesos?"
)

#: Magnitude words. "four hundred and twenty five thousand" carries no digits
#: and is exactly the phrase that parsed three different ways.
_MAGNITUDE_WORDS = "hundred|thousand|million|billion|trillion"

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("currency symbol", re.compile(f"[{re.escape(_CURRENCY_SYMBOLS)}]\\s*[\\d,.]*\\d?")),
    ("currency word", re.compile(rf"\b(?:{_CURRENCY_WORDS})\b", re.IGNORECASE)),
    # Digits with separators first, so `425,000` is one finding rather than two.
    ("number", re.compile(r"\b\d[\d,.]*\b")),
    ("spelled-out amount", re.compile(rf"\b(?:{_MAGNITUDE_WORDS})\b", re.IGNORECASE)),
)


class Figure(NamedTuple):
    """One thing in the transcript that a human has to check."""

    kind: str
    text: str
    start: int
    end: int


def figures_in(text: str) -> list[Figure]:
    """Every span worth a second look, in the order they appear.

    Overlaps are kept rather than merged: ``$400,000`` yields both the currency
    symbol and the number, and they are different claims — one about *which
    currency* and one about *how much*. The measured failure got the first wrong
    while the second stayed plausible, so collapsing them would hide the worse
    of the two behind the better.
    """
    found: list[Figure] = []
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(text or ""):
            value = match.group().strip()
            if value:
                found.append(Figure(kind, value, match.start(), match.end()))
    return sorted(found, key=lambda f: (f.start, f.kind))


def needs_confirmation(text: str) -> bool:
    """Whether a dictated transcript contains anything a human must verify."""
    return bool(figures_in(text))


#: Shown to the user when it does. Names the observed failure rather than
#: warning in the abstract — "check the figures" is ignorable, "it heard naira
#: as dollars" is not, and the second is true and was measured.
CONFIRMATION_NOTICE = (
    "Check the figures — dictation heard “naira” as “$” in testing, "
    "and amounts can split differently between runs."
)
