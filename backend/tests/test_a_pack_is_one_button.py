"""The optional packs are got from inside Zaram, the cost named, the download
recorded before the first byte — and never asked about on the first run.

`extras/__init__.py`. Three contracts: the catalogue says what each pack
turns on and what it costs, with the measurement dated; installing records
the download on the egress log *before* running anything and streams the
installer's own lines; a failure is a sentence, not a trace, and success is
only claimed when the probe module can actually be imported.
"""

from __future__ import annotations

import sys

from extras import EXTRAS, catalogue, describe, install, installed


class _Log:
    def __init__(self) -> None:
        self.entries = []

    def append(self, **entry):
        self.entries.append(entry)


class TestTheCatalogue:
    def test_every_pack_says_what_it_turns_on_and_what_it_costs(self):
        for extra in EXTRAS.values():
            assert extra.enables and all(len(e.split()) >= 4 for e in extra.enables), extra.id
            assert extra.size_mb > 0 and extra.measured, extra.id
            assert extra.commands and extra.probe, extra.id

    def test_the_three_packs_are_the_three_pip_lines_settings_used_to_show(self):
        assert set(EXTRAS) == {"voice", "mic", "ingest"}

    def test_speaking_says_it_needs_a_restart_and_the_others_do_not(self):
        assert EXTRAS["voice"].restart is True
        assert EXTRAS["mic"].restart is False
        assert EXTRAS["ingest"].restart is False

    def test_installed_is_answered_without_importing(self):
        """`find_spec`, not `import` — a probe that loaded torch to say yes
        would cost seconds on every Settings open."""
        before = set(sys.modules)
        for extra in EXTRAS.values():
            installed(extra)
        assert not ({"kokoro", "docling", "faster_whisper"} & (set(sys.modules) - before))

    def test_the_description_carries_the_interpreter_it_installs_into(self):
        row = describe(EXTRAS["mic"])
        assert row["python"] == sys.executable
        assert row["size_mb"] == 81
        assert isinstance(row["installed"], bool)
        assert len(catalogue()) == 3


class TestInstalling:
    def test_the_download_is_recorded_before_anything_runs(self, monkeypatch):
        order = []
        log = _Log()

        def fake_run(argv):
            order.append(("run", argv[:3]))
            yield "Collecting faster-whisper"
            yield "Successfully installed faster-whisper-1.2.1"

        original_append = log.append

        def recording_append(**entry):
            order.append(("log", entry["host"]))
            original_append(**entry)

        log.append = recording_append
        monkeypatch.setattr("extras.installed", lambda extra: True)

        events = list(install(EXTRAS["mic"], log=log, run=fake_run))

        assert order[0] == ("log", "files.pythonhosted.org")
        assert order[1][0] == "run"
        assert log.entries[0]["decision"] == "allowed"
        assert "Get it" in log.entries[0]["reason"] and "81 MB" in log.entries[0]["reason"]
        assert log.entries[0]["meta"]["direction"] == "download"
        assert events[0]["stage"].startswith("Getting the Listening pack")
        assert {"line": "Collecting faster-whisper"} in events
        assert events[-1]["done"] is True and events[-1]["restart"] is False

    def test_a_failed_installer_is_a_sentence_and_no_success_is_claimed(self):
        def failing(argv):
            yield "Collecting docling"
            raise RuntimeError("exited with 1")

        events = list(install(EXTRAS["ingest"], log=None, run=failing))
        assert events[-1]["error"].startswith("The Reading scans pack did not install")
        assert not any("done" in e for e in events)

    def test_an_installer_that_finishes_without_the_module_is_not_a_success(self, monkeypatch):
        monkeypatch.setattr("extras.installed", lambda extra: False)
        events = list(install(EXTRAS["ingest"], log=None, run=lambda argv: iter(["ok"])))
        assert "still cannot be imported" in events[-1]["error"]

    def test_every_command_runs_in_zarams_own_interpreter(self):
        """The pack must land where Zaram imports from, which in a packaged
        install is the bundled runtime and nowhere else."""
        import extras

        seen = []

        class _Proc:
            stdout = iter([])

            def wait(self):
                return 0

        def fake_popen(argv, **kw):
            seen.append(argv[0])
            return _Proc()

        original = extras.subprocess.Popen
        extras.subprocess.Popen = fake_popen
        try:
            list(extras._run(["-m", "pip", "--version"]))
        finally:
            extras.subprocess.Popen = original
        assert seen == [sys.executable]
