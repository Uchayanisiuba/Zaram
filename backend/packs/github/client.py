"""Talking to GitHub: sign-in, and the handful of calls Zaram makes.

Every request goes through `EgressGate`, so it is checked against the person's
rules and written to the egress log like everything else Zaram sends (rule 3). The
token is passed to the gate as a header, which the log does not record; the request
*body* (a pull request's title and description) is recorded, which is what rule 3
asks for.

**Sign-in is GitHub's device flow, and it needs nothing secret.** Zaram asks GitHub
for a short code, the person types it at github.com/login/device in their own
browser and approves, and Zaram -- polling meanwhile -- is handed a token. No
redirect, no local web server, no client secret. The cost: a token that expires
(GitHub's default for an app) cannot be refreshed without the secret, so it is
reported as expired and the person connects again; the app is set not to expire
user tokens, and this handles the case where it is not.

Base addresses are parameters so a test can point both at a server on this machine.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from . import app, vault

logger = logging.getLogger(__name__)

SOURCE = "github"

#: Dates the API contract, so a change on GitHub's side cannot change an answer
#: under a running copy.
API_VERSION = "2022-11-28"

#: A full name: owner/name, with the characters GitHub allows and nothing else, so
#: nothing a model writes can become a different path or a different host.
_FULL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}$")

#: How many repositories one listing returns. Enough for a person's own work; a
#: model's context does not need more, and GitHub pages at 100.
MAX_REPOSITORIES = 100


class GitHubError(RuntimeError):
    """A refusal from GitHub, in words a person can act on."""

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


def valid_full_name(name: str) -> bool:
    return bool(_FULL_NAME.match(name or "")) and ".." not in name


@dataclass(frozen=True)
class DeviceCode:
    user_code: str
    verification_uri: str
    device_code: str
    expires_in: int
    interval: int


def _explain(status: int, payload: Any, what: str) -> str:
    """GitHub's own sentence, plus what usually fixes it."""
    message = ""
    if isinstance(payload, dict):
        message = str(payload.get("message") or payload.get("error_description") or "")
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            detail = "; ".join(
                str(e.get("message") or e) if isinstance(e, dict) else str(e) for e in errors[:3]
            )
            message = f"{message} ({detail})" if message else detail
    if status == 401:
        return "GitHub no longer accepts Zaram's sign-in (it expired or was revoked). Connect GitHub again in Settings."
    if status == 403 and "rate limit" in message.lower():
        return "GitHub's rate limit was reached. Try again in a few minutes."
    if status in (403, 404):
        return (
            f"GitHub would not let Zaram {what}: {message or 'forbidden'}. The usual cause is that Zaram is not "
            f"installed on that repository -- choose it at {app.install_url()} -- or that the repository does "
            "not exist under that name."
        )
    return f"GitHub refused to {what} ({status}): {message or 'no reason given'}."


class GitHub:
    def __init__(self, *, web: Optional[str] = None, api: Optional[str] = None, gate=None) -> None:
        self._web = (web or app.WEB_BASE).rstrip("/")
        self._api = (api or app.API_BASE).rstrip("/")
        self._gate = gate

    # ------------------------------------------------------------ plumbing

    def _send(self, method: str, url: str, body: Optional[Dict[str, Any]], token: Optional[str], what: str) -> Any:
        from core.egress import DataClass, get_gate

        gate = self._gate if self._gate is not None else get_gate()
        headers = {
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "Zaram",
            "X-GitHub-Api-Version": API_VERSION,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            raw = gate.request(
                url,
                method=method,
                body=json.dumps(body) if body is not None else None,
                headers=headers,
                timeout=30.0,
                source=SOURCE,
                data_class=DataClass.PROMPT,
            )
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8", "replace"))
            except Exception:  # noqa: BLE001
                payload = None
            raise GitHubError(_explain(exc.code, payload, what), exc.code) from exc
        except urllib.error.URLError as exc:
            raise GitHubError(f"Zaram could not reach GitHub ({exc.reason}). Check the connection and try again.") from exc
        text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw or "")
        if not text.strip():
            return {}
        try:
            return json.loads(text)
        except ValueError as exc:
            raise GitHubError("GitHub answered with something Zaram could not read.") from exc

    # ------------------------------------------------------------ signing in

    def start_device_flow(self) -> DeviceCode:
        if not app.configured():
            raise GitHubError("The Zaram GitHub app has not been registered on this build, so there is nothing to sign in to.")
        payload = self._send("POST", f"{self._web}/login/device/code", {"client_id": app.client_id()}, None, "start signing in")
        if isinstance(payload, dict) and payload.get("error"):
            if payload["error"] == "device_flow_disabled":
                raise GitHubError(
                    "Device sign-in is switched off for the Zaram app on GitHub. In the app's settings, "
                    "tick 'Enable Device Flow'."
                )
            raise GitHubError(f"GitHub would not start sign-in: {payload.get('error_description') or payload['error']}")
        try:
            return DeviceCode(
                user_code=str(payload["user_code"]),
                verification_uri=str(payload["verification_uri"]),
                device_code=str(payload["device_code"]),
                expires_in=int(payload.get("expires_in") or 900),
                interval=max(5, int(payload.get("interval") or 5)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise GitHubError("GitHub's sign-in answer was missing something Zaram needs.") from exc

    def poll_device_flow(self, device_code: str) -> Dict[str, Any]:
        """One poll. ``state`` is pending, slow_down, done, expired, denied or error."""
        payload = self._send(
            "POST",
            f"{self._web}/login/oauth/access_token",
            {
                "client_id": app.client_id(),
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            None,
            "finish signing in",
        )
        error = payload.get("error") if isinstance(payload, dict) else "unreadable"
        if not error and payload.get("access_token"):
            lifetime = payload.get("expires_in")
            return {
                "state": "done",
                "token": str(payload["access_token"]),
                "expires_at": (time.time() + float(lifetime)) if lifetime else None,
            }
        states = {
            "authorization_pending": "pending",
            "slow_down": "slow_down",
            "expired_token": "expired",
            "access_denied": "denied",
        }
        return {"state": states.get(str(error), "error"), "detail": str((payload or {}).get("error_description") or error)}

    # ------------------------------------------------------------ reading

    def whoami(self, token: str) -> Dict[str, Any]:
        user = self._send("GET", f"{self._api}/user", None, token, "read who is signed in")
        return {"login": str(user.get("login") or ""), "id": int(user.get("id") or 0)}

    def repositories(self, token: str) -> List[Dict[str, Any]]:
        """Every repository Zaram has been installed on, for this person."""
        found: List[Dict[str, Any]] = []
        installs = self._send("GET", f"{self._api}/user/installations?per_page=100", None, token, "list where Zaram is installed")
        for install in (installs.get("installations") or []):
            if str((install.get("app_slug") or "")).lower() != app.slug().lower() and app.slug():
                # An installation of some other app on the same token cannot happen
                # with a GitHub App user token; skipped rather than trusted.
                continue
            listing = self._send(
                "GET",
                f"{self._api}/user/installations/{int(install['id'])}/repositories?per_page={MAX_REPOSITORIES}",
                None,
                token,
                "list the repositories Zaram can reach",
            )
            for repo in listing.get("repositories") or []:
                permissions = repo.get("permissions") or {}
                found.append(
                    {
                        "full_name": str(repo.get("full_name") or ""),
                        "private": bool(repo.get("private")),
                        "default_branch": str(repo.get("default_branch") or "main"),
                        "can_push": bool(permissions.get("push") or permissions.get("admin")),
                    }
                )
        return found[:MAX_REPOSITORIES]

    # ------------------------------------------------------------ writing

    def open_pull_request(
        self, token: str, repo: str, *, title: str, head: str, base: str, body: str = "", draft: bool = False
    ) -> Dict[str, Any]:
        made = self._send(
            "POST",
            f"{self._api}/repos/{repo}/pulls",
            {"title": title, "head": head, "base": base, "body": body, "draft": bool(draft)},
            token,
            "open that pull request",
        )
        return {"number": made.get("number"), "url": made.get("html_url"), "state": made.get("state")}

    def create_issue(self, token: str, repo: str, *, title: str, body: str = "") -> Dict[str, Any]:
        made = self._send(
            "POST", f"{self._api}/repos/{repo}/issues", {"title": title, "body": body}, token, "file that issue"
        )
        return {"number": made.get("number"), "url": made.get("html_url")}

    def create_repository(self, token: str, name: str, *, private: bool = True, description: str = "") -> Dict[str, Any]:
        made = self._send(
            "POST",
            f"{self._api}/user/repos",
            {"name": name, "private": bool(private), "description": description, "auto_init": False},
            token,
            "create that repository",
        )
        return {"full_name": made.get("full_name"), "url": made.get("html_url"), "private": bool(made.get("private"))}

    def default_branch(self, token: str, repo: str) -> str:
        info = self._send("GET", f"{self._api}/repos/{repo}", None, token, "read that repository")
        return str(info.get("default_branch") or "main")


def current(connection: Optional[vault.Connection] = None) -> Optional[vault.Connection]:
    """The stored connection, or ``None`` -- including when it has expired."""
    found = connection if connection is not None else vault.load()
    if found is None or found.expired:
        return None
    return found
