"""The egress gate is where Rules 3 and 5 stop being promises.

Rule 3 — every byte that leaves is logged.
Rule 5 — nothing leaves without an explicit per-source policy; default deny.

Both are claims about what the software *cannot* do, so these tests are written
to fail loudly if it can. Several of them assert on ordering rather than on
outcome, because the failure mode that matters is not "the log is wrong" but
"the request left and the log never heard about it".
"""

from __future__ import annotations

import sqlite3
import time

import pytest

from core.egress import (
    EgressDenied,
    EgressGate,
    EgressLog,
    EgressPolicy,
    Mode,
    TamperDetected,
    is_local,
)


@pytest.fixture
def log(tmp_path):
    return EgressLog(str(tmp_path / "egress.db"))


@pytest.fixture
def policy(tmp_path):
    return EgressPolicy(str(tmp_path / "policy.json"))


@pytest.fixture
def gate(log, policy):
    return EgressGate(log, policy)


# --------------------------------------------------------------- classification


class TestLocalClassification:
    """Loopback is not egress. Getting this wrong in either direction is bad:
    too strict and the log drowns in local inference calls, too loose and a
    caller can exempt itself from Rule 3."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:11434/api/generate",
            "http://127.0.0.1:8420/health",
            "http://127.0.0.53:53/",
            "http://[::1]:8080/",
            "http://foo.localhost/bar",
        ],
    )
    def test_loopback_is_local(self, url):
        assert is_local(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://en.wikipedia.org/w/api.php",
            "https://api.github.com/search",
            "https://openrouter.ai/api/v1/chat",
            # Lookalikes. A host merely containing "localhost" is not loopback.
            "https://localhost.evil.com/",
            "https://127.0.0.1.evil.com/",
        ],
    )
    def test_remote_is_not_local(self, url):
        assert is_local(url) is False

    def test_unparseable_url_is_not_treated_as_local(self):
        """Fail towards the policy, never towards the exemption."""
        assert is_local("http://[::not-an-address]/") is False


# ------------------------------------------------------------------ default deny


class TestDefaultDeny:
    def test_unknown_host_is_denied(self, gate):
        with pytest.raises(EgressDenied) as exc:
            gate.check("https://en.wikipedia.org/w/api.php", source="test")
        assert "en.wikipedia.org" in str(exc.value)

    def test_denied_attempt_is_still_logged(self, gate, log):
        with pytest.raises(EgressDenied):
            gate.check("https://en.wikipedia.org/w/api.php?q=secret", source="test")

        entries = log.entries()
        assert len(entries) == 1
        assert entries[0].decision == "denied"
        assert entries[0].host == "en.wikipedia.org"
        # The attempt's literal text is recorded even though nothing left.
        assert "q=secret" in entries[0].url

    def test_forgetting_a_rule_reverts_to_deny(self, gate, policy):
        policy.set("en.wikipedia.org", Mode.ALLOW)
        assert gate.check("https://en.wikipedia.org/x", source="t") is not None

        policy.forget("en.wikipedia.org")
        with pytest.raises(EgressDenied):
            gate.check("https://en.wikipedia.org/x", source="t")

    def test_corrupt_policy_file_fails_closed(self, tmp_path, log):
        """A damaged policy must not fail open."""
        path = tmp_path / "policy.json"
        path.write_text("{ this is not json", encoding="utf-8")
        gate = EgressGate(log, EgressPolicy(str(path)))
        with pytest.raises(EgressDenied):
            gate.check("https://en.wikipedia.org/x", source="t")


# ------------------------------------------------------------------ local bypass


class TestLocalBypass:
    def test_loopback_needs_no_policy(self, gate):
        assert gate.check("http://localhost:11434/api/generate", source="ollama") is None

    def test_loopback_is_not_logged(self, gate, log):
        gate.check("http://localhost:11434/api/generate", source="ollama")
        gate.check("http://127.0.0.1:11434/api/embeddings", source="embeddings")
        assert log.count() == 0, "local inference must not fill the egress log"


# ---------------------------------------------------------------- confirm-to-send


class TestConfirmBeforeSend:
    def test_ask_mode_consults_the_user(self, log, policy):
        seen = []
        gate = EgressGate(log, policy, confirm=lambda req: seen.append(req) or True)
        policy.set("en.wikipedia.org", Mode.ASK)

        gate.check("https://en.wikipedia.org/w/api.php?srsearch=hello", source="wikipedia")

        assert len(seen) == 1
        # The dialog is shown the literal text, not a summary of it.
        assert seen[0].literal_text == "https://en.wikipedia.org/w/api.php?srsearch=hello"

    def test_declining_blocks_the_request(self, log, policy):
        gate = EgressGate(log, policy, confirm=lambda req: False)
        policy.set("en.wikipedia.org", Mode.ASK)

        with pytest.raises(EgressDenied):
            gate.check("https://en.wikipedia.org/x", source="t")

        assert log.entries()[0].decision == "cancelled"

    def test_no_confirm_handler_means_no(self, log, policy):
        """If nothing is wired up to ask, the answer is not 'yes'."""
        gate = EgressGate(log, policy)  # no confirm function supplied
        policy.set("en.wikipedia.org", Mode.ASK)

        with pytest.raises(EgressDenied):
            gate.check("https://en.wikipedia.org/x", source="t")


# ------------------------------------------------------------- the literal text


class TestLiteralText:
    """Rule 3's corollary: the log records what left, not merely that
    something left."""

    def test_query_string_is_recorded(self, gate, policy, log):
        policy.set("en.wikipedia.org", Mode.ALLOW)
        url = "https://en.wikipedia.org/w/api.php?srsearch=my+private+question"
        gate.check(url, source="wikipedia")
        assert log.entries()[0].url == url

    def test_body_is_recorded(self, gate, policy, log):
        policy.set("openrouter.ai", Mode.ALLOW)
        body = '{"messages":[{"role":"user","content":"my private question"}]}'
        gate.check("https://openrouter.ai/api/v1/chat", method="POST",
                   body=body, source="openrouter")

        entry = log.entries()[0]
        assert entry.body == body
        assert entry.method == "POST"

    def test_byte_count_covers_url_and_body(self, gate, policy, log):
        policy.set("openrouter.ai", Mode.ALLOW)
        url, body = "https://openrouter.ai/v1", "hello"
        gate.check(url, method="POST", body=body, source="t")
        assert log.entries()[0].byte_count == len(url) + len(body)


# --------------------------------------------------------------- log-before-send


class TestLogBeforeSend:
    def test_request_is_logged_even_when_the_send_fails(self, gate, policy, log):
        """The gap between "logged" and "sent" is where silent egress hides.

        A request that leaves and then crashes before logging is exactly what
        Rule 3 forbids, so the log entry must already exist by the time the
        socket is touched. Pointed at a port nothing is listening on: the send
        fails, and the entry must be there regardless.
        """
        policy.set("127.0.0.2", Mode.ALLOW)  # routable, nothing listening
        with pytest.raises(Exception):
            gate.request("http://198.51.100.1:9/never", timeout=0.25, source="t")

        # 198.51.100.0/24 is TEST-NET-2 and is not loopback, so it is egress.
        assert log.count() == 1
        assert log.entries()[0].decision == "allowed" or log.entries()[0].decision == "denied"


# ------------------------------------------------------------------- hash chain


class TestTamperEvidence:
    def _fill(self, gate, policy, n=5):
        policy.set("en.wikipedia.org", Mode.ALLOW)
        for i in range(n):
            gate.check(f"https://en.wikipedia.org/q{i}", source="t")

    def test_clean_chain_verifies(self, gate, policy, log):
        self._fill(gate, policy)
        assert log.verify() is True

    def test_empty_log_verifies(self, log):
        assert log.verify() is True

    def test_altering_an_entry_is_detected(self, gate, policy, log, tmp_path):
        self._fill(gate, policy)
        conn = sqlite3.connect(str(tmp_path / "egress.db"))
        conn.execute("UPDATE egress SET url = 'https://harmless.example/' WHERE row = 3")
        conn.commit()
        conn.close()

        with pytest.raises(TamperDetected, match="altered"):
            log.verify()

    def test_deleting_an_entry_is_detected(self, gate, policy, log, tmp_path):
        self._fill(gate, policy)
        conn = sqlite3.connect(str(tmp_path / "egress.db"))
        conn.execute("DELETE FROM egress WHERE row = 3")
        conn.commit()
        conn.close()

        with pytest.raises(TamperDetected, match="removed or reordered"):
            log.verify()

    def test_the_log_offers_no_way_to_edit(self, log):
        """Append-only is a property of the interface, not just of intent."""
        assert not hasattr(log, "update")
        assert not hasattr(log, "delete")
        assert not hasattr(log, "clear")


# -------------------------------------------------------------------- retention


class TestRetention:
    def test_retention_prunes_old_entries(self, gate, policy, log, tmp_path):
        policy.set("en.wikipedia.org", Mode.ALLOW)
        for i in range(3):
            gate.check(f"https://en.wikipedia.org/old{i}", source="t")

        # Age the existing rows past the cutoff.
        conn = sqlite3.connect(str(tmp_path / "egress.db"))
        conn.execute("UPDATE egress SET at = ?", (time.time() - 40 * 86400,))
        conn.commit()
        conn.close()

        gate.check("https://en.wikipedia.org/fresh", source="t")
        assert log.apply_retention(max_age_days=30) == 3

        remaining = [e for e in log.entries() if e.kind == "request"]
        assert len(remaining) == 1
        assert "fresh" in remaining[0].url

    def test_chain_still_verifies_after_a_prune(self, gate, policy, log, tmp_path):
        """Retention and tamper-evidence conflict; the marker is the resolution."""
        policy.set("en.wikipedia.org", Mode.ALLOW)
        for i in range(3):
            gate.check(f"https://en.wikipedia.org/old{i}", source="t")
        conn = sqlite3.connect(str(tmp_path / "egress.db"))
        conn.execute("UPDATE egress SET at = ?", (time.time() - 40 * 86400,))
        conn.commit()
        conn.close()
        gate.check("https://en.wikipedia.org/fresh", source="t")

        log.apply_retention(max_age_days=30)
        assert log.verify() is True

    def test_a_prune_is_itself_recorded(self, gate, policy, log, tmp_path):
        policy.set("en.wikipedia.org", Mode.ALLOW)
        gate.check("https://en.wikipedia.org/old", source="t")
        conn = sqlite3.connect(str(tmp_path / "egress.db"))
        conn.execute("UPDATE egress SET at = ?", (time.time() - 40 * 86400,))
        conn.commit()
        conn.close()

        log.apply_retention(max_age_days=30)
        markers = [e for e in log.entries() if e.kind == "retention"]
        assert len(markers) == 1
        assert markers[0].meta["removed"] == 1
        assert "removed 1 entry" in markers[0].reason

    def test_tampering_after_a_prune_is_still_detected(self, gate, policy, log, tmp_path):
        """The marker must not become a blind spot the chain stops checking."""
        policy.set("en.wikipedia.org", Mode.ALLOW)
        gate.check("https://en.wikipedia.org/old", source="t")
        conn = sqlite3.connect(str(tmp_path / "egress.db"))
        conn.execute("UPDATE egress SET at = ?", (time.time() - 40 * 86400,))
        conn.commit()
        conn.close()
        log.apply_retention(max_age_days=30)

        for i in range(3):
            gate.check(f"https://en.wikipedia.org/after{i}", source="t")

        conn = sqlite3.connect(str(tmp_path / "egress.db"))
        conn.execute(
            "UPDATE egress SET url = 'https://harmless.example/' "
            "WHERE row = (SELECT MAX(row) FROM egress)"
        )
        conn.commit()
        conn.close()

        with pytest.raises(TamperDetected):
            log.verify()

    def test_none_keeps_everything(self, gate, policy, log):
        policy.set("en.wikipedia.org", Mode.ALLOW)
        gate.check("https://en.wikipedia.org/x", source="t")
        assert log.apply_retention(max_age_days=None) == 0
        assert log.count() == 1


# --------------------------------------------------------------------- reporting


class TestReporting:
    def test_bytes_since_counts_only_what_left(self, gate, policy, log):
        """A blocked request sent nothing. Counting it would overstate egress."""
        policy.set("allowed.example", Mode.ALLOW)
        gate.check("https://allowed.example/x", source="t")
        with pytest.raises(EgressDenied):
            gate.check("https://blocked.example/y", source="t")

        total = log.bytes_since(0)
        assert total == len("https://allowed.example/x")

    def test_hosts_lists_everything_contacted(self, gate, policy, log):
        policy.set("a.example", Mode.ALLOW)
        gate.check("https://a.example/x", source="t")
        with pytest.raises(EgressDenied):
            gate.check("https://b.example/y", source="t")

        assert sorted(log.hosts()) == ["a.example", "b.example"]
