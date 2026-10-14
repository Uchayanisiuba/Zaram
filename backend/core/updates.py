"""Updates: find out a newer Zaram exists, fetch it, and hand it to the installer.

Asked for 14 October 2026, after a tester on one build could not be moved to the
next without someone sending them a link. Every build so far has been a download
from the website, run by hand over the last one.

**What it is, in the order the rules put it.**

*Rule 7g, as amended 16 August 2026:* update checks are asked for once and
default to yes. `checks` is `None` until the person answers, `True` or `False`
after, and nothing is fetched while it is `None` or `False` unless the person
presses *Check for updates* themselves, which is the question being answered
again by an act. *Rule 3:* every request here goes through `EgressGate`, the
asset's redirect hops included (`download_to_file`), so each one is in the egress
log. *Rule 5, by 7j:* answering yes is the person's decision about the four hosts
below, and it sets a rule for each unless they have blocked it.

**What the check sends.** An anonymous GET for the list of releases. It carries
no version, no identifier and nothing about the machine; GitHub sees an address,
as any website does. That is smaller than the 7g amendment allows, because the
comparison is made here, against the answer.

**It fetches; it does not install.** The installer is saved under the data
directory, checked against the SHA-256 that sits beside it in the release, and
left there. Running it is the desktop shell's job and happens only when the
person presses *Restart and install* (`electron/native/updateInstaller.js`).
This module never starts a program.

**Where the trust stops.** The checksum file and the installer come from the same
release, so this catches a corrupted or truncated download and not a release
published by somebody with write access to the repository. The builds are not
signed (`docs/MILESTONES.md`); Windows' own warning at first install is the
honest statement of that, and a signature is the fix. The file name must be the
one the build produces and the address must be under the repository's own release
path -- what the API returns is third-party text, so neither is taken as given.

**Retention** (CLAUDE.md: no new store without an answer). `updates.json` holds a
flag, a timestamp, the last answer and the name of the file downloaded. The
installer is deleted as soon as the running build is that version or newer, and a
new download removes the previous one. Deleting the data folder deletes all of it.

**An unversioned build cannot update.** Every alpha is `0.1.0` to Windows, so the
release tag is the version; the desktop host puts it in `ZARAM_RELEASE_TAG` from
what the build was stamped with. A checkout has none, and says so rather than
guessing it is old.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
import urllib.error
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SOURCE = "updates"
REPO = "Uchayanisiuba/Zaram"
API_BASE = "https://api.github.com"
WEB_BASE = "https://github.com"

#: The hosts a check and a download touch, by name: the API that lists releases,
#: the page that serves an asset, and the two storage hosts GitHub redirects an
#: asset to. Answering yes to "check for updates" is the decision about these.
HOSTS = (
    "api.github.com",
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
)

RELEASE_ENV = "ZARAM_RELEASE_TAG"
FILENAME = "updates.json"
FOLDER = "updates"

#: What the build names its installer. The portable build is `Zaram-Portable-…`
#: and cannot replace itself, so it does not match.
INSTALLER_NAME = re.compile(r"^Zaram-\d+\.\d+\.\d+-x64\.exe$")
SUMS_NAME = "SHA256SUMS.txt"

#: How long a launch-time check trusts the last answer. GitHub allows an
#: unauthenticated address sixty calls an hour, and nothing here is urgent.
CHECK_EVERY_SECONDS = 3600

#: Larger than any installer this has produced by a wide margin, and a stop for a
#: response that does not end.
MAX_INSTALLER_BYTES = 1 << 30

_TAG = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([A-Za-z]+)\.(\d+))?$")
_STAGES = {"alpha": 0, "beta": 1, "rc": 2}
_RELEASE = 3


def parse_tag(tag: Optional[str]) -> Optional[Tuple[int, int, int, int, int]]:
    """A tag as something that orders, or ``None`` when it is not a version.

    ``v0.1.0-alpha.7`` before ``v0.1.0-alpha.10`` before ``v0.1.0-beta.1`` before
    ``v0.1.0``. A stage this does not know is ``None`` -- not guessed to be older
    or newer -- so an unfamiliar tag is ignored rather than ranked.
    """
    match = _TAG.match((tag or "").strip())
    if not match:
        return None
    major, minor, patch, stage, number = match.groups()
    if stage is None:
        rank, n = _RELEASE, 0
    else:
        rank = _STAGES.get(stage.lower(), -1)
        if rank < 0:
            return None
        n = int(number)
    return (int(major), int(minor), int(patch), rank, n)


def is_newer(candidate: Optional[str], current: Optional[str]) -> bool:
    a, b = parse_tag(candidate), parse_tag(current)
    return a is not None and b is not None and a > b


def current_tag() -> Optional[str]:
    """The release this process is, or ``None`` for a build that was never stamped."""
    tag = (os.environ.get(RELEASE_ENV) or "").strip()
    return tag if parse_tag(tag) else None


def parse_sums(text: str) -> Dict[str, str]:
    """``sha256sum`` output as ``{file name: lower-case hex}``."""
    found: Dict[str, str] = {}
    for line in (text or "").splitlines():
        match = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$", line)
        if match:
            found[match.group(2)] = match.group(1).lower()
    return found


class UpdateError(RuntimeError):
    """Something went wrong that the person can be told in words."""


def allow_hosts(gate: Any = None) -> Optional[str]:
    """Allow the update hosts, or say why that cannot be done.

    The kill switch and a block the person set are both respected and neither is
    overridden: a refusal comes back as a sentence. A host with no rule yet gets
    one, which is what answering yes means.
    """
    from core.egress import Mode, get_gate

    policy = (gate or get_gate()).policy
    if policy.kill_switch():
        return "The kill switch is on, so nothing can be fetched. Turn it off in Activity first."
    for host in HOSTS:
        if policy.has_rule(host) and policy.decide(host).mode is Mode.DENY:
            return f"{host} is blocked in Activity. Allow it there first; Zaram will not override a block you set."
    for host in HOSTS:
        if not policy.has_rule(host):
            policy.set(host, Mode.ALLOW)
    return None


class Updates:
    def __init__(
        self,
        *,
        gate: Any = None,
        directory: Optional[Path] = None,
        current: Optional[str] = None,
        api_base: str = API_BASE,
        web_base: str = WEB_BASE,
        repo: str = REPO,
        now: Callable[[], float] = time.time,
        platform: str = sys.platform,
        portable: Optional[bool] = None,
        packaged: Optional[bool] = None,
    ) -> None:
        self._gate = gate
        self._directory = Path(directory) if directory else None
        self._current = current if current is not None else current_tag()
        self._api = api_base.rstrip("/")
        self._web = web_base.rstrip("/")
        self._repo = repo
        self._now = now
        self._platform = platform
        self._portable = bool(os.environ.get("PORTABLE_EXECUTABLE_FILE")) if portable is None else portable
        if packaged is None:
            from core.paths import is_packaged

            packaged = is_packaged()
        self._packaged = bool(packaged)
        self._lock = threading.RLock()
        self._phase = "idle"
        self._progress = (0, 0)
        self._error = ""
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------- storage

    def _root(self) -> Path:
        if self._directory is None:
            from core.paths import data_dir

            self._directory = Path(data_dir())
        self._directory.mkdir(parents=True, exist_ok=True)
        return self._directory

    def _file(self) -> Path:
        return self._root() / FILENAME

    def _folder(self) -> Path:
        folder = self._root() / FOLDER
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _load(self) -> Dict[str, Any]:
        try:
            data = json.loads(self._file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: Dict[str, Any]) -> None:
        tmp = self._file().with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, self._file())

    def _update(self, **fields: Any) -> Dict[str, Any]:
        with self._lock:
            data = self._load()
            data.update(fields)
            self._save(data)
            return data

    # ------------------------------------------------------------ settings

    def checks(self) -> Optional[bool]:
        """Whether the person has said yes (``True``), no (``False``) or not been asked (``None``)."""
        value = self._load().get("checks")
        return value if isinstance(value, bool) else None

    def set_checks(self, on: bool) -> bool:
        self._update(checks=bool(on))
        return bool(on)

    # -------------------------------------------------------------- reading

    @property
    def current(self) -> Optional[str]:
        return self._current

    def _can_install(self) -> Tuple[bool, str]:
        if self._platform != "win32":
            return False, "Installing an update from inside Zaram is only built for Windows."
        if self._portable:
            return False, "This is the portable build, which cannot replace itself. Download the new one from the release page."
        if not self._packaged:
            return False, "This is not an installed copy of Zaram, so there is nothing to replace."
        return True, ""

    def status(self) -> Dict[str, Any]:
        self._tidy()
        data = self._load()
        can, why = self._can_install()
        latest = data.get("latest") if isinstance(data.get("latest"), dict) else None
        available = bool(latest) and is_newer(latest.get("tag"), self._current)
        with self._lock:
            phase, progress, error = self._phase, self._progress, self._error
        downloaded = self._downloaded_record(data)
        ready = bool(downloaded) and bool(latest) and downloaded.get("tag") == latest.get("tag") and available
        if phase == "idle" and ready:
            phase = "ready"
        elif phase == "idle" and latest and not available:
            phase = "up_to_date"
        elif phase == "idle" and available:
            phase = "available"
        return {
            "current": self._current,
            "known": self._current is not None,
            "checks": self.checks(),
            "last_checked": data.get("last_checked"),
            "phase": phase,
            "latest": latest if available else None,
            "progress": {"done": progress[0], "total": progress[1]},
            "error": error,
            "ready": ready,
            "can_install": can and self._current is not None,
            "manual_reason": "" if can else why,
            "release_page": f"{self._web}/{self._repo}/releases",
        }

    # ------------------------------------------------------------ the check

    def _send(self, url: str, what: str) -> bytes:
        from core.egress import DataClass, EgressDenied, get_gate

        gate = self._gate if self._gate is not None else get_gate()
        try:
            return gate.request(
                url,
                headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
                timeout=30.0,
                source=SOURCE,
                data_class=DataClass.PROMPT,
            )
        except EgressDenied as denied:
            raise UpdateError(f"{denied} Nothing was fetched.") from denied
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                raise UpdateError("GitHub's rate limit was reached. Try again in a little while.") from exc
            raise UpdateError(f"GitHub refused to {what} ({exc.code}).") from exc
        except urllib.error.URLError as exc:
            raise UpdateError(f"Zaram could not reach GitHub to {what} ({exc.reason}). Check the connection and try again.") from exc

    def _release_from(self, releases: Any) -> Optional[Dict[str, Any]]:
        """The newest published release that carries an installer this build can use."""
        if not isinstance(releases, list):
            raise UpdateError("GitHub answered with something Zaram could not read.")
        best: Optional[Tuple[Tuple[int, int, int, int, int], Dict[str, Any]]] = None
        prefix_for = lambda tag: f"{self._web}/{self._repo}/releases/download/{tag}/"  # noqa: E731
        for release in releases:
            if not isinstance(release, dict) or release.get("draft"):
                continue
            tag = str(release.get("tag_name") or "")
            key = parse_tag(tag)
            if key is None:
                continue
            installer = sums = None
            for asset in release.get("assets") or []:
                if not isinstance(asset, dict):
                    continue
                name = str(asset.get("name") or "")
                url = str(asset.get("browser_download_url") or "")
                if not url.startswith(prefix_for(tag)) or url != prefix_for(tag) + name:
                    continue
                if INSTALLER_NAME.match(name):
                    installer = {"name": name, "url": url, "size": int(asset.get("size") or 0)}
                elif name == SUMS_NAME:
                    sums = {"name": name, "url": url}
            if not installer or not sums:
                continue
            page = str(release.get("html_url") or "")
            if not page.startswith(f"{self._web}/{self._repo}/releases/"):
                page = f"{self._web}/{self._repo}/releases/tag/{tag}"
            candidate = {"tag": tag, "installer": installer, "sums": sums, "page": page}
            if best is None or key > best[0]:
                best = (key, candidate)
        return best[1] if best else None

    def check(self, *, force: bool = False) -> Dict[str, Any]:
        """Ask for the release list and record the newest one. Blocking."""
        if self._current is None:
            return self.status()
        data = self._load()
        last = data.get("last_checked")
        if not force and isinstance(last, (int, float)) and self._now() - last < CHECK_EVERY_SECONDS:
            return self.status()
        with self._lock:
            if self._phase in ("checking", "downloading"):
                return self.status()
            self._phase, self._error = "checking", ""
        try:
            raw = self._send(f"{self._api}/repos/{self._repo}/releases?per_page=15", "list the releases")
            try:
                listing = json.loads(raw.decode("utf-8", "replace"))
            except ValueError as exc:
                raise UpdateError("GitHub answered with something Zaram could not read.") from exc
            latest = self._release_from(listing)
            self._update(last_checked=self._now(), latest=latest)
            with self._lock:
                self._phase = "idle"
        except UpdateError as error:
            with self._lock:
                self._phase, self._error = "idle", str(error)
            logger.info("update check failed: %s", error)
        return self.status()

    # --------------------------------------------------------- the download

    def _downloaded_record(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        record = data.get("downloaded")
        if not isinstance(record, dict):
            return None
        name = str(record.get("name") or "")
        if not INSTALLER_NAME.match(name) or not (self._folder() / name).is_file():
            return None
        return record

    def _tidy(self) -> None:
        """Delete an installer the running build has already caught up with, and strays."""
        with self._lock:
            if self._phase == "downloading":
                # The half-written file is not a stray, and status is polled
                # while it grows.
                return
        data = self._load()
        record = data.get("downloaded") if isinstance(data.get("downloaded"), dict) else None
        keep = None
        if record:
            stale = self._current is not None and not is_newer(record.get("tag"), self._current)
            if stale or not INSTALLER_NAME.match(str(record.get("name") or "")):
                record = None
            else:
                keep = str(record["name"])
        folder = self._root() / FOLDER
        if folder.is_dir():
            for entry in folder.iterdir():
                if entry.is_file() and entry.name != keep:
                    try:
                        entry.unlink()
                    except OSError:
                        pass
        if (data.get("downloaded") or None) != (record or None):
            self._update(downloaded=record)

    def download(self) -> Dict[str, Any]:
        """Start fetching the newest release's installer in the background."""
        if self._current is None:
            raise UpdateError("This build has no release number, so it cannot tell what is newer.")
        data = self._load()
        latest = data.get("latest") if isinstance(data.get("latest"), dict) else None
        if not latest or not is_newer(latest.get("tag"), self._current):
            raise UpdateError("There is no newer release to download. Check for updates first.")
        with self._lock:
            if self._phase in ("checking", "downloading"):
                return self.status()
            self._phase, self._error, self._progress = "downloading", "", (0, 0)
            self._thread = threading.Thread(target=self._download, args=(latest,), name="zaram-update", daemon=True)
            self._thread.start()
        return self.status()

    def wait(self, timeout: float = 30.0) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _download(self, latest: Dict[str, Any]) -> None:
        from core.egress import DataClass, EgressDenied, get_gate

        installer, sums = latest["installer"], latest["sums"]
        part = None
        try:
            gate = self._gate if self._gate is not None else get_gate()
            wanted = parse_sums(self._send(sums["url"], "read the checksums").decode("utf-8", "replace")).get(installer["name"])
            if not wanted:
                raise UpdateError("The release has no checksum for its installer, so Zaram will not use it.")
            folder = self._folder()
            for entry in folder.iterdir():
                if entry.is_file():
                    entry.unlink()
            part = folder / (installer["name"] + ".part")
            digest = hashlib.sha256()

            def progress(done: int, total: int) -> None:
                with self._lock:
                    self._progress = (done, total or installer.get("size") or 0)

            try:
                gate.download_to_file(
                    installer["url"], part, source=SOURCE, data_class=DataClass.PROMPT,
                    timeout=60.0, max_bytes=MAX_INSTALLER_BYTES, progress=progress, digest=digest,
                )
            except EgressDenied as denied:
                raise UpdateError(f"{denied} Nothing was fetched.") from denied
            except urllib.error.HTTPError as exc:
                raise UpdateError(f"GitHub refused to send the installer ({exc.code}).") from exc
            except urllib.error.URLError as exc:
                raise UpdateError(f"The download stopped ({exc.reason}). Nothing was installed; try again.") from exc
            if digest.hexdigest() != wanted:
                raise UpdateError("The download does not match its checksum, so it was thrown away. Try again.")
            final = folder / installer["name"]
            os.replace(part, final)
            part = None
            self._update(downloaded={"tag": latest["tag"], "name": installer["name"], "sha256": wanted})
            with self._lock:
                self._phase = "idle"
        except UpdateError as error:
            with self._lock:
                self._phase, self._error = "idle", str(error)
            logger.info("update download failed: %s", error)
        except Exception as exc:  # noqa: BLE001 - a thread must report, not die silently
            logger.exception("update download crashed")
            with self._lock:
                self._phase, self._error = "idle", f"The download failed: {exc}"
        finally:
            if part is not None:
                try:
                    part.unlink()
                except OSError:
                    pass

    # ----------------------------------------------------------- installing

    def pending(self) -> Optional[Dict[str, Any]]:
        """The downloaded installer, re-hashed, or ``None`` when there is not one to run.

        Read by the desktop shell, which runs it. The file is hashed again here
        rather than trusted from the earlier check, because it has sat on disk
        since and the cost is a second.
        """
        self._tidy()
        data = self._load()
        record = self._downloaded_record(data)
        latest = data.get("latest") if isinstance(data.get("latest"), dict) else None
        if not record or not latest or record.get("tag") != latest.get("tag") or not is_newer(record["tag"], self._current):
            return None
        can, _ = self._can_install()
        if not can:
            return None
        path = self._folder() / record["name"]
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        if digest.hexdigest() != record.get("sha256"):
            return None
        return {"path": str(path), "name": record["name"], "sha256": record["sha256"], "tag": record["tag"]}


_SHARED: Optional[Updates] = None


def shared() -> Updates:
    global _SHARED
    if _SHARED is None:
        _SHARED = Updates()
    return _SHARED


def reset_shared() -> None:
    global _SHARED
    _SHARED = None
