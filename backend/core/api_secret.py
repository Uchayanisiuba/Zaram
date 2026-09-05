"""The credential that separates Zaram's own interface from everything else on
this machine.

**Loopback is a network boundary, not an identity one.** Binding to 127.0.0.1
stopped the API being published to the café network, and the `Host` guard in
`main.py` stopped a web page reaching it by pointing a hostname it controls at
127.0.0.1. Neither does anything about a *process*. Until this module existed
there was no authentication at all, so anything running as this user could
``GET /memory`` and read every fact Zaram has ever stored, ``GET /egress`` and
read every question ever asked, or ``PUT /egress/policy`` and set a destination
to allow. `X-Zaram-Client` is sent by the interface and enforced nowhere; it is
a label, and it was never a credential.

Two sources, and the difference between them is the difference between the
product and a checkout
----------------------------------------------------------------------------
**`ZARAM_API_SECRET` wins, and packaged builds use only that.** The desktop
host mints a value at boot and hands it to the backend as an environment
variable on the spawn. It exists in two process images and nowhere else — no
file to read, no value that outlives the run, nothing left behind by a crash.
That is what "per-launch secret" means and it is the posture that ships.

**A file under `data_dir()` is the development fallback**, because in a
checkout the backend and the Vite dev server are started independently by a
person and have no parent to hand either of them anything. Whichever starts
first creates it. This is **weaker** — a secret at rest is readable by anything
that can read the directory, which on a single-user machine is most things —
and it is stated here rather than glossed because a fallback nobody documents
becomes the thing everyone relies on. It is never used when
`ZARAM_API_SECRET` is set, so it is never used in a packaged build.

What this does and does not defend
----------------------------------
It stops another process on the machine, another user account, and anything
that finds port 8420 by scanning. It does **not** turn the file fallback into a
real secret against a same-user attacker, and it is not a substitute for
`core/pairing.py`, which is the credential a *second device* needs. This is the
first of the two and the one that had been missing entirely.
"""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path

from core.paths import data_dir

__all__ = ["SECRET_ENV", "HEADER", "SECRET_FILENAME", "api_secret", "matches", "reset_cache"]

#: How the desktop host hands the value to the backend it spawns.
SECRET_ENV = "ZARAM_API_SECRET"

#: The header the interface presents it in. Distinct from `X-Zaram-Client`,
#: which stays exactly what it always was — a label — so that reading either
#: name in a log or a proxy config says unambiguously which one is load-bearing.
HEADER = "X-Zaram-Auth"

#: Development only. Named so it is obvious in a directory listing what it is.
SECRET_FILENAME = "api-secret"

#: 32 bytes, for the reason `core/pairing.py` gives for the same choice: this is
#: a value nobody chose and nobody types, so entropy does the work a slow
#: password hash would otherwise have to.
_SECRET_BYTES = 32

_cached: str | None = None


def _read_or_create_file() -> str:
    """The development fallback. Created once, reused after."""
    path = Path(data_dir()) / SECRET_FILENAME
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except OSError:
        pass

    minted = secrets.token_urlsafe(_SECRET_BYTES)
    try:
        path.write_text(minted, encoding="utf-8")
        # Owner-only. A no-op on Windows, where the ACL inherited from the
        # user's own AppData directory is what actually restricts it — which is
        # why this is not the mechanism the packaged build relies on.
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # An unwritable data directory must not stop the process starting. The
        # secret still holds for this run; it simply will not be readable by a
        # dev server started afterwards, which fails loudly at the first
        # request rather than quietly letting anything through.
        pass
    return minted


def api_secret() -> str:
    """This process's credential, minted at most once per run."""
    global _cached
    if _cached is not None:
        return _cached

    from_env = (os.getenv(SECRET_ENV) or "").strip()
    _cached = from_env or _read_or_create_file()
    return _cached


def ensure_resolved() -> None:
    """Mint and persist the credential at startup, before anyone asks.

    **Not optional, and the reason is a deadlock.** `matches()` returns `False`
    immediately for an absent header — correctly, there is nothing to compare —
    which means it never calls `api_secret()`. So on a machine where every
    request arrives without a credential, the credential is never resolved and
    the development fallback file is never written. The dev server cannot
    present a secret until the file exists, and the file does not exist until
    something presents a secret.

    Observed exactly that way: the backend answered 401 to everything while
    `backend/api-secret` did not exist, and calling `api_secret()` by hand in
    another process created a *different* value — so a file that finally
    appeared would have disagreed with the running process anyway. Lazy
    resolution of a value two programs have to share is the bug.

    Called once at import in `main.py`. Costs a file write in development and
    nothing at all in a packaged build, where the environment supplies it.
    """
    api_secret()


def matches(presented: str | None) -> bool:
    """Whether a presented value is the credential.

    `compare_digest`, never `==`. Comparing secrets with equality leaks their
    contents through timing — slowly, but reliably, and against a local
    attacker who can issue as many requests as they like there is no rate limit
    making that impractical. `core/pairing.py` reaches for the same function
    for the same reason.
    """
    if not presented:
        return False
    return secrets.compare_digest(presented, api_secret())


def reset_cache() -> None:
    """Forget the cached value. For tests, which need to change the
    environment between cases and would otherwise measure the first one for
    the rest of the session."""
    global _cached
    _cached = None
