"""Which code is actually running, and since when.

**Written because not knowing cost two debugging rounds on 10 August 2026.** A
backend started at 06:32 kept serving `127.0.0.1:8420` for the rest of the day.
Windows let a second uvicorn bind `0.0.0.0:8420` alongside it without an error,
and the older process won for loopback — so every request went to code from
before the day's fixes. Two separate bugs were diagnosed as live and re-fixed
before anyone thought to ask *which build is answering*:

* the audio 404, "fixed" and still 404ing in the app;
* recall on a greeting, gated in the code and still citing in the app.

Both fixes were correct. The evidence said otherwise because the evidence came
from a different build. `CLAUDE.md`'s working agreement is "verify by seeing it
work", and that check is worth nothing if you cannot tell what you are looking
at.

**Read from `.git` directly, never from a subprocess.** Spawning `git` costs
tens of milliseconds on Windows, needs git on PATH, and fails inside a packaged
build that has no repository at all — where this is most useful, because a
packaged backend is exactly the one nobody can inspect.

**Unknown is a value, and a wrong SHA would be worse than none.** Every failure
returns ``None``, the same rule `vram_bytes` follows: a caller can check for
absence and cannot check a plausible lie.
"""

from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path

#: When this process started, as a wall-clock epoch. Captured at import, which
#: is close enough to process start for the question being asked — "is this
#: older than the fix I just made" is a question about minutes, not milliseconds.
STARTED_AT = time.time()

_REPO_ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def commit_sha() -> str | None:
    """The commit this process was started from, or ``None``.

    Cached: the answer cannot change while the process lives, and that is the
    whole point of it — a stale process keeps reporting the stale SHA, which is
    precisely the signal wanted.
    """
    head = _REPO_ROOT / ".git" / "HEAD"
    try:
        content = head.read_text(encoding="utf-8").strip()
    except OSError:
        return None

    if content.startswith("ref:"):
        ref = content.partition(" ")[2].strip()
        try:
            return (_REPO_ROOT / ".git" / ref).read_text(encoding="utf-8").strip() or None
        except OSError:
            # A packed ref, or a ref that does not resolve. Fall through to
            # packed-refs rather than guessing.
            pass
        try:
            packed = (_REPO_ROOT / ".git" / "packed-refs").read_text(encoding="utf-8")
        except OSError:
            return None
        for line in packed.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            sha, _, name = line.partition(" ")
            if name.strip() == ref:
                return sha.strip() or None
        return None

    # Detached HEAD holds the SHA itself.
    return content or None


def build_stamp() -> dict[str, object]:
    """What is running, for `/health`.

    ``uptime_s`` is included rather than left to the caller because the
    comparison that matters — "did this process start before the change I am
    testing?" — needs a clock both sides agree on, and the client's clock is not
    it.
    """
    sha = commit_sha()
    return {
        # Short form: this is read by a human comparing it to `git log`, not
        # parsed. The full SHA is available in `commit` for anything that is.
        "commit": sha,
        "commit_short": sha[:9] if sha else None,
        "started_at": STARTED_AT,
        "uptime_s": round(time.time() - STARTED_AT, 1),
    }
