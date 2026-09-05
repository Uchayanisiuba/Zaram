"""Linking a phone to the machine that holds the Spine.

The pattern is the one people already learned from WhatsApp and Signal: the
computer shows a QR, the phone scans it, and from then on the phone is a linked
device that the computer can revoke. No account, no email, no password, no
reset flow — the machine holding the data is the authority, which is the only
arrangement consistent with a product whose whole claim is that the data stays
on that machine.

**This is the authentication the API has never had.** Until now the only thing
standing between a stranger and the whole Spine was that the server binds to
loopback and nothing else. That is a good boundary and it stays — the phone
reaches in through a tunnel that connects to loopback locally, so the bind is
never widened. But a second device is by definition not this process, so it
needs credentials, and this is where they come from.

Four properties do the work, and each exists because its absence is a specific
attack:

* **Tokens are single-use.** A QR photographed over someone's shoulder is
  worthless once the real phone has used it.
* **Tokens expire in a minute.** A QR left on screen during a meeting, or
  photographed and used later, is worthless too.
* **Credentials are stored hashed.** A stolen `spine.db` must not yield working
  credentials for someone's devices. This is the same reasoning as never
  storing a password, applied to a secret that grants exactly as much.
* **Comparison is constant-time.** Comparing secrets with `==` leaks their
  contents through timing, slowly but reliably.

The credential is returned exactly once, at redemption. Nothing in this module
can recover it afterwards, which is what makes the hashed storage meaningful
rather than decorative.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "PairingError",
    "Device",
    "DeviceRegistry",
    "TOKEN_TTL_SECONDS",
]

#: How long a QR stays valid. Short enough that a photographed code is
#: near-useless, long enough that someone can find their phone, unlock it and
#: open the camera. WhatsApp and Signal both sit in this range.
TOKEN_TTL_SECONDS = 60.0

#: Bytes of entropy in a credential. 32 bytes is 256 bits — far past guessing,
#: and high enough that a single SHA-256 is the right way to store it. Password
#: hashes are slow to defend *low*-entropy secrets; that reasoning does not
#: apply to a value nobody chose and nobody types.
_CREDENTIAL_BYTES = 32
_TOKEN_BYTES = 24


class PairingError(Exception):
    """A pairing attempt failed, with a reason written for a person."""


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


@dataclass
class Device:
    """A phone or tablet that has been linked, and may be unlinked.

    `credential_hash` rather than the credential. Nothing here can reconstruct
    what the device holds — the registry can only confirm that a presented
    value hashes to the same thing.
    """

    id: str
    name: str
    credential_hash: str
    linked_at: float
    last_seen: Optional[float] = None
    revoked_at: Optional[float] = None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def to_dict(self) -> Dict[str, Any]:
        """Safe to send anywhere. Deliberately has no credential field at all —
        not an empty one, not a redacted one. A field that sometimes holds a
        secret is a field that will eventually be logged."""
        return {
            "id": self.id,
            "name": self.name,
            "linked_at": self.linked_at,
            "last_seen": self.last_seen,
            "revoked_at": self.revoked_at,
            "is_active": self.is_active,
        }


@dataclass
class _PendingToken:
    token_hash: str
    created_at: float
    expires_at: float
    used_at: Optional[float] = None


@dataclass
class DeviceRegistry:
    """Issues pairing tokens, redeems them, and verifies linked devices.

    In-memory by design at this layer: persistence is the caller's, and keeping
    it out means the security properties are testable without a database and
    the storage choice can change without touching the rules.
    """

    _pending: Dict[str, _PendingToken] = field(default_factory=dict)
    _devices: Dict[str, Device] = field(default_factory=dict)

    # -- issuing ---------------------------------------------------------- #

    def issue_token(self, *, now: Optional[float] = None) -> str:
        """A one-time code to put in a QR. Returned in clear exactly once.

        Only its hash is retained, for the same reason the credential's is: a
        pending token is a live grant of access to everything.
        """
        moment = now if now is not None else time.time()
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        self._pending[_hash(token)] = _PendingToken(
            token_hash=_hash(token),
            created_at=moment,
            expires_at=moment + TOKEN_TTL_SECONDS,
        )
        return token

    def redeem(
        self, token: str, *, device_name: str = "", now: Optional[float] = None
    ) -> tuple[Device, str]:
        """Turn a scanned token into a linked device and its credential.

        Returns the device and the credential **once**. The registry keeps only
        a hash, so a caller that discards this value cannot ask for it again —
        the phone must be re-paired, which is the correct and cheap recovery.
        """
        moment = now if now is not None else time.time()
        pending = self._pending.get(_hash(token))

        # Same message for "no such token" and "already used". Distinguishing
        # them tells an attacker which guesses were once real.
        if pending is None or pending.used_at is not None:
            raise PairingError(
                "That code is not valid. Show a new QR on your computer and try again."
            )
        if moment > pending.expires_at:
            raise PairingError(
                "That code has expired. Show a new QR on your computer — they "
                "last about a minute on purpose."
            )

        pending.used_at = moment
        credential = secrets.token_urlsafe(_CREDENTIAL_BYTES)
        device = Device(
            id=secrets.token_hex(8),
            name=(device_name or "").strip() or "Unnamed device",
            credential_hash=_hash(credential),
            linked_at=moment,
            last_seen=moment,
        )
        self._devices[device.id] = device
        return device, credential

    # -- using ------------------------------------------------------------ #

    def verify(self, credential: str, *, now: Optional[float] = None) -> Optional[Device]:
        """The device behind a credential, or None.

        None for unknown *and* for revoked, so a revoked phone is refused by
        the same path as a forged one and no caller has to remember to check
        `is_active` separately. Forgetting that check is how a revoked device
        keeps working.
        """
        if not credential:
            return None
        presented = _hash(credential)
        for device in self._devices.values():
            # Constant-time even though both sides are hex digests of fixed
            # length: the habit is what survives a later change to the format.
            if secrets.compare_digest(device.credential_hash, presented):
                if not device.is_active:
                    return None
                device.last_seen = now if now is not None else time.time()
                return device
        return None

    # -- managing --------------------------------------------------------- #

    def revoke(self, device_id: str, *, now: Optional[float] = None) -> bool:
        """Unlink a device. Immediate, and the record is kept.

        Kept rather than deleted so "which devices have ever had access, and
        when did that stop" stays answerable — the same reasoning that makes a
        corrected fact stay visible struck through.
        """
        device = self._devices.get(device_id)
        if device is None or not device.is_active:
            return False
        device.revoked_at = now if now is not None else time.time()
        return True

    def devices(self, *, include_revoked: bool = True) -> List[Device]:
        """Everything ever linked, newest first."""
        found = [
            device
            for device in self._devices.values()
            if include_revoked or device.is_active
        ]
        return sorted(found, key=lambda device: device.linked_at, reverse=True)

    def purge_expired_tokens(self, *, now: Optional[float] = None) -> int:
        """Drop tokens that can no longer be redeemed.

        Housekeeping rather than security — an expired token is already
        refused. Without it a long-running process accumulates one dead entry
        per QR ever shown.
        """
        moment = now if now is not None else time.time()
        dead = [
            key
            for key, pending in self._pending.items()
            if pending.used_at is not None or moment > pending.expires_at
        ]
        for key in dead:
            del self._pending[key]
        return len(dead)
