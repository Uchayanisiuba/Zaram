"""`core/pairing.py` gets its caller: the clients this machine has paired.

**The credential a second client needs.** `core/api_secret.py` is the
credential Zaram's *own* interface holds — per-launch, IPC-only, gone when
the process is. That is right for the desktop host and useless for anything
else: Claude Code, Cline, a script — any process that wants Zaram's memory
has to hold something that outlives one launch and that the person can
revoke without restarting Zaram. `DeviceRegistry` has had the rules for that
since it was written — single-use tokens, a minute's expiry, hashed storage,
constant-time comparison — and no caller. `docs/AGENT-UX.md` is exact about
why the MCP server could not be built first: *"a stdio MCP server that read
the development fallback file would work on a checkout and be a secret at
rest on an install"*. So this comes first, and the server is small.

**What this adds to the registry is persistence and nothing else.** The
rules stay in `pairing.py`, tested without a database; this stores the
outcome — `Device` rows in SQLite under `data_dir()` — so a client paired
on Monday still authenticates on Tuesday. Pending tokens are deliberately
*not* persisted: they live a minute, and a token that survived a restart
would be a token that survived longer than its own rule says.

**"Client", not "device", at this layer.** The registry was written for a
phone; what pairs today is another program on this machine. Same
credential, same rules, same revocation — the word changes because what
the person sees in Settings is *Claude Code*, not *Pixel 8*, and the
column is named for what it holds.

**Every call a paired client makes is egress to that client.** Rule 3 says
every byte that leaves is logged, and recalled facts handed to another
process have left this one. `RequireApiSecret` in `main.py` writes the
entry; this module only says which client it was.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import List, Optional

from core.pairing import Device, DeviceRegistry, PairingError, TOKEN_TTL_SECONDS
from core.paths import data_dir

__all__ = ["PairedClients", "PairingError", "TOKEN_TTL_SECONDS", "DB_FILENAME"]

DB_FILENAME = "paired-clients.db"


class PairedClients:
    """`DeviceRegistry` with its devices written through to SQLite.

    Thread-safe around the connection, because the middleware verifies from
    the event loop and Settings issues tokens from a route on the same loop
    — and `sqlite3` refuses a connection shared across threads by default.
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path is not None else Path(data_dir()) / DB_FILENAME
        self._lock = threading.Lock()
        self._registry = DeviceRegistry()
        self._init_schema()
        self._load()

    # -- storage ------------------------------------------------------------ #

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS paired_clients (
                    id              TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    credential_hash TEXT NOT NULL,
                    linked_at       REAL NOT NULL,
                    last_seen       REAL,
                    revoked_at      REAL
                )
                """
            )

    def _load(self) -> None:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM paired_clients").fetchall()
        for row in rows:
            device = Device(
                id=row["id"],
                name=row["name"],
                credential_hash=row["credential_hash"],
                linked_at=row["linked_at"],
                last_seen=row["last_seen"],
                revoked_at=row["revoked_at"],
            )
            self._registry._devices[device.id] = device

    def _write(self, device: Device) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO paired_clients
                    (id, name, credential_hash, linked_at, last_seen, revoked_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    last_seen = excluded.last_seen,
                    revoked_at = excluded.revoked_at
                """,
                (
                    device.id, device.name, device.credential_hash,
                    device.linked_at, device.last_seen, device.revoked_at,
                ),
            )

    # -- the registry's verbs, persisted ------------------------------------ #

    def issue_token(self) -> str:
        """A one-time code, in clear, exactly once. Shown in Settings."""
        self._registry.purge_expired_tokens()
        return self._registry.issue_token()

    def redeem(self, token: str, *, name: str = "") -> tuple[Device, str]:
        """The token becomes a client and its credential — returned once."""
        device, credential = self._registry.redeem(token, device_name=name)
        self._write(device)
        return device, credential

    def verify(self, credential: str) -> Optional[Device]:
        """The active client behind a credential, or None. Records the sighting.

        `last_seen` is written on every verified call. That is one small write
        per request from a paired client, which is cheap; what it buys is a
        Settings row that can say *"last used two minutes ago"* rather than
        *"paired in March"*, and that is the line a person revokes on.
        """
        device = self._registry.verify(credential)
        if device is not None:
            self._write(device)
        return device

    def revoke(self, client_id: str) -> bool:
        """Immediate. The row is kept, marked, and never verifies again."""
        if not self._registry.revoke(client_id):
            return False
        self._write(self._registry._devices[client_id])
        return True

    def clients(self, *, include_revoked: bool = True) -> List[Device]:
        return self._registry.devices(include_revoked=include_revoked)

    def get(self, client_id: str) -> Optional[Device]:
        return self._registry._devices.get(client_id)
