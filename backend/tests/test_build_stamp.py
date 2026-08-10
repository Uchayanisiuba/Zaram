"""`/health` says which build is answering.

Written after a backend started at 06:32 served `127.0.0.1:8420` for the rest of
the day. Two bugs that had already been fixed were diagnosed as live and
re-investigated against it, because nothing in the running system could answer
"which code is this?".

The guard is small and the point is narrow: the field exists, it is honest when
it cannot know, and it is reachable from the endpoint people already curl.
"""

from __future__ import annotations

import re

from core.build_stamp import STARTED_AT, build_stamp, commit_sha

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class TestTheStamp:
    def test_it_reports_a_real_commit_in_a_checkout(self):
        sha = commit_sha()
        assert sha is not None, "running inside a git checkout but found no commit"
        assert SHA_RE.match(sha), f"{sha!r} is not a 40-character sha"

    def test_unknown_is_none_rather_than_a_plausible_string(self, monkeypatch):
        """The `vram_bytes` rule, applied to a build id.

        A caller can check for `None`. It cannot check a SHA that is merely
        well-formed and wrong — and a wrong build id is worse than no build id,
        because it ends an investigation instead of starting one.
        """
        import core.build_stamp as module

        commit_sha.cache_clear()
        monkeypatch.setattr(module, "_REPO_ROOT", module.Path("/definitely/not/here"))
        try:
            assert module.commit_sha() is None
        finally:
            commit_sha.cache_clear()

    def test_the_payload_carries_what_a_human_compares(self):
        stamp = build_stamp()

        assert set(stamp) == {"commit", "commit_short", "started_at", "uptime_s"}
        # Uptime is the field that actually catches a stale process: a SHA only
        # helps if you know which SHA you expected, and "started 3 hours ago"
        # needs no reference at all.
        assert stamp["uptime_s"] >= 0
        assert stamp["started_at"] == STARTED_AT
        if stamp["commit"]:
            assert stamp["commit_short"] == stamp["commit"][:9]

    def test_health_exposes_it(self):
        """Reachable from the endpoint people already curl.

        A stamp behind a route nobody calls would not have helped: the whole
        value is that the first thing anyone already does — hit `/health` —
        answers the question.
        """
        from fastapi.testclient import TestClient

        import main

        with TestClient(main.app) as client:
            payload = client.get("/health").json()

        assert "build" in payload, "/health does not report which build is running"
        assert "uptime_s" in payload["build"]
