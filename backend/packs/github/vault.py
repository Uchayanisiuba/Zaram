"""Where Zaram keeps the GitHub token, and how it is protected there.

**The decision this reverses, and why it is reversed on purpose.** `DataClass.REPO`
was written (4 October 2026) with a rule beside it: pushing goes through the
terminal and the operating system's credential helper, *so Zaram never holds a
credential*. That kept the product away from a token and it was right for a
terminal. It also meant Zaram could not open a pull request, file an issue or tell
a person which repositories it could reach -- everything a GitHub connection is
*for*. On 12 October 2026 the maintainer asked for the connection the other
assistants have, and this module is the cost of it: **a credential on this machine**.

So it is held as carefully as the platform allows, and described as it is:

* **Windows**: sealed with DPAPI (`CryptProtectData`), which ties the bytes to this
  Windows account. Another user on the machine, a copied file, a backup restored
  elsewhere: none can read it. A process running *as the same user* can, as with
  every secret an application keeps -- DPAPI is not a defence against that, and
  this does not claim it is.
* **Elsewhere**: a file readable by the owner only (0600), and marked as not
  sealed, so a surface can say so. Zaram ships for Windows; this is the honest
  fallback for a development checkout on another system.

Never written to the egress log, never returned by an API route, never put in a
command line (see `tools.py`: it travels in an environment variable, which other
programs cannot list the way they can list arguments).

Provider keys in `cloud-connections.json` are stored in plaintext and are weaker
than this; that is recorded in `docs/MILESTONES.md` rather than glossed.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

FILENAME = "github-connection.json"


@dataclass(frozen=True)
class Connection:
    """Who is connected. ``token`` exists only in memory and in the sealed file."""

    login: str
    user_id: int
    token: str
    connected_at: float
    #: When the token stops working, or ``None`` for one that does not expire. A
    #: GitHub App's user tokens expire after eight hours *unless* the app is set not
    #: to; Zaram cannot refresh one (that needs the app's secret, which it does not
    #: hold), so an expiring token is reported and the person reconnects.
    expires_at: Optional[float] = None

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and time.time() >= self.expires_at


# ----------------------------------------------------------------- sealing


def _dpapi(data: bytes, *, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    buffer = ctypes.create_string_buffer(data, len(data))
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    out = Blob()
    if protect:
        done = crypt32.CryptProtectData(ctypes.byref(source), "Zaram GitHub", None, None, None, 0, ctypes.byref(out))
    else:
        done = crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(out))
    if not done:
        raise OSError("Windows could not protect or unprotect the GitHub token")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def seals() -> bool:
    """Whether this platform can seal the token to the user."""
    return sys.platform == "win32"


def seal(data: bytes) -> bytes:
    return _dpapi(data, protect=True) if seals() else data


def unseal(data: bytes) -> bytes:
    return _dpapi(data, protect=False) if seals() else data


# ----------------------------------------------------------------- the file


def _path() -> Path:
    from core.paths import in_data_dir

    return Path(in_data_dir(FILENAME, "ZARAM_GITHUB_CONNECTION_FILE"))


def save(connection: Connection) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "login": connection.login,
        "user_id": connection.user_id,
        "connected_at": connection.connected_at,
        "expires_at": connection.expires_at,
        "sealed": seals(),
        "token": base64.b64encode(seal(connection.token.encode("utf-8"))).decode("ascii"),
    }
    # Write then replace, so a crash never leaves half a token on disk.
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document), encoding="utf-8")
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, path)


def load() -> Optional[Connection]:
    path = _path()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        token = unseal(base64.b64decode(document["token"])).decode("utf-8")
        return Connection(
            login=str(document["login"]),
            user_id=int(document["user_id"]),
            token=token,
            connected_at=float(document.get("connected_at") or 0),
            expires_at=(float(document["expires_at"]) if document.get("expires_at") else None),
        )
    except (OSError, ValueError, KeyError, TypeError):
        # Missing, corrupt, or sealed by another Windows account: not connected,
        # said once, rather than an error on every screen that asks.
        return None


def clear() -> None:
    try:
        _path().unlink()
    except FileNotFoundError:
        pass


def sealed_on_disk() -> Optional[bool]:
    """Whether the stored token is sealed, or ``None`` when nothing is stored."""
    try:
        return bool(json.loads(_path().read_text(encoding="utf-8")).get("sealed"))
    except (OSError, ValueError):
        return None
