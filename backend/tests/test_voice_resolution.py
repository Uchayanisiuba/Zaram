"""Which voice speaks, and whether the user's choice reaches the sound.

**The defect this is written against.** `user_settings.voice` was written by
the character pane, read back by `GET /character`, rendered in Settings — and
consulted by nothing. `/voice/synthesize` resolved its voice as
``request.voice or PERSONAS[persona]["voice"] or "af_heart"``, and both
frontend callers speak with no voice argument at all. So the control existed,
stored, round-tripped, and had no effect on any sound the user heard.

That is this repository's signature failure wearing a settings control instead
of a module, and it is invisible to `check:reachability` — the route *is*
called, the setting *is* read somewhere. What is missing is the one hop
between them. It needed a test that asks what the user would ask: I chose a
voice; is that the voice that speaks?

**Why the assertions are about order rather than about one value.** A test that
only checked "the default is male" would pass against the broken code the
moment the default literal changed, because the broken code also returns a
default. The property that matters is precedence, so each step is asserted
against the step it must beat.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.user_settings import get_user_settings, set_user_settings_path
from voice.config import DEFAULT_VOICE


@pytest.fixture
def settings(tmp_path, monkeypatch):
    """A settings singleton pointed at a scratch file, restored afterwards."""
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    set_user_settings_path(str(tmp_path / "settings.json"))
    yield get_user_settings()
    set_user_settings_path(str(tmp_path / "settings.json"))


@pytest.fixture
def resolve():
    """`main._resolve_voice`, imported here rather than at module scope.

    `main` builds the kernel on import, which is expensive and not needed by
    every test in this file's neighbourhood.
    """
    main = importlib.import_module("main")
    return main._resolve_voice, main


class TestTheUsersChoiceIsHonoured:
    def test_a_chosen_voice_is_the_voice_that_speaks(self, settings, resolve):
        """The whole point. This failed before the fix and is the regression."""
        resolve_voice, main = resolve
        settings.set_character(voice="bm_george")

        assert resolve_voice("", main.DEFAULT_PERSONA) == "bm_george"

    def test_the_chosen_voice_beats_the_shipped_default(self, settings, resolve):
        resolve_voice, main = resolve
        settings.set_character(voice="af_bella")

        spoken = resolve_voice("", main.DEFAULT_PERSONA)
        assert spoken == "af_bella"
        assert spoken != DEFAULT_VOICE, "the default silently won"

    def test_clearing_the_choice_returns_to_the_default(self, settings, resolve):
        """Empty means "no preference", which is a different claim from a value.

        `set_character` distinguishes absent from empty deliberately, and the
        empty case has to fall through rather than be sent to Kokoro as a
        voice id of "".
        """
        resolve_voice, main = resolve
        settings.set_character(voice="am_fenrir")
        settings.set_character(voice="")

        assert resolve_voice("", main.DEFAULT_PERSONA) == DEFAULT_VOICE

    def test_whitespace_is_not_a_choice(self, settings, resolve):
        resolve_voice, main = resolve
        settings.set_character(voice="   ")

        assert resolve_voice("", main.DEFAULT_PERSONA) == DEFAULT_VOICE


class TestPrecedence:
    def test_this_request_beats_the_standing_choice(self, settings, resolve):
        """A per-utterance override still wins, which is what it is for."""
        resolve_voice, main = resolve
        settings.set_character(voice="af_bella")

        assert resolve_voice("am_puck", main.DEFAULT_PERSONA) == "am_puck"

    def test_the_default_preset_does_not_outrank_the_users_choice(self, settings, resolve):
        """The trap in the obvious implementation.

        Every request carries `persona="zaram_prime"` whether or not anybody
        chose it — the frontend hardcodes it. So resolving the preset before
        the setting would mean the preset nobody picked always beat the voice
        the user did pick, which is the broken behaviour wearing new code.
        """
        resolve_voice, main = resolve
        settings.set_character(voice="bm_lewis")

        assert main.PERSONAS[main.DEFAULT_PERSONA]["voice"] == DEFAULT_VOICE
        assert resolve_voice("", main.DEFAULT_PERSONA) == "bm_lewis"

    def test_the_request_models_default_to_the_preset_that_means_nobody_chose(self, resolve):
        """The coupling that makes the test above mean anything.

        `_resolve_voice` tells "nobody picked a preset" from "the user picked
        this one" by comparing against `DEFAULT_PERSONA`. Both voice routes
        supply that default themselves, so if either one ever spells its own
        literal instead, every request naming no preset starts looking like a
        deliberate choice — and the preset's voice quietly outranks the voice
        the user set, which is the defect this file was written against
        arriving by a second route.
        """
        _resolve_voice, main = resolve

        # Built the way the frontend builds them: text only, no preset named.
        assert main.VoiceSynthesizeRequest(text="hello").persona == main.DEFAULT_PERSONA
        assert main.VoiceStreamRequest(text="hello").persona == main.DEFAULT_PERSONA

    def test_a_deliberately_chosen_preset_still_supplies_its_voice(self, settings, resolve):
        """A preset the user selected is also a choice, so it is honoured.

        Only for a preset that is *not* the default one — that is the whole
        distinction `DEFAULT_PERSONA` exists to draw.
        """
        resolve_voice, main = resolve
        named = next(p for p in main.PERSONAS if p != main.DEFAULT_PERSONA)

        assert resolve_voice("", named) == main.PERSONAS[named]["voice"]


class TestItAlwaysReturnsARealVoice:
    def test_an_unknown_preset_falls_back_rather_than_returning_nothing(self, settings, resolve):
        """A voice id of "" reaches Kokoro as a missing file, not as a default."""
        resolve_voice, _ = resolve

        assert resolve_voice("", "a_preset_that_does_not_exist") == DEFAULT_VOICE

    def test_settings_failing_to_load_does_not_take_speech_down(self, resolve, monkeypatch):
        """Speech degrades to the default rather than raising.

        The same posture `models_runtime` had to be given after an
        `AttributeError` in a logging branch stopped the backend booting: a
        helper that cannot fail is only true if the failure is caught.
        """
        resolve_voice, main = resolve

        def explode():
            raise RuntimeError("settings file is unreadable")

        monkeypatch.setattr("core.user_settings.get_user_settings", explode)

        assert resolve_voice("", main.DEFAULT_PERSONA) == DEFAULT_VOICE


class TestOneSpelling:
    def test_the_default_voice_is_male(self):
        """Asked for by the maintainer on 19 August 2026.

        Asserted on the id's own convention rather than on the literal, so
        swapping `am_michael` for another male voice keeps this green and
        swapping it for a female one does not. Kokoro voice ids are
        `<language><gender>_<name>`, so the second character is the claim.
        """
        assert DEFAULT_VOICE[1] == "m", f"{DEFAULT_VOICE} is not a male voice id"

    def test_no_live_module_spells_the_old_default(self):
        """Six places held the literal, and that is how they drifted apart.

        A scan rather than a comment, because the comment saying "one place
        owns this" is exactly what was true of the TTS text cleaner and the
        two rankers while a second copy sat next to each of them.
        """
        backend = Path(__file__).resolve().parent.parent
        skip = {"venv", "__pycache__", "tests", "legacy"}

        offenders: list[str] = []
        for path in backend.rglob("*.py"):
            if any(part in skip for part in path.parts):
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                stripped = line.strip()
                # Prose about the change is fine; a value is not.
                if stripped.startswith("#") or stripped.startswith("*"):
                    continue
                if '"af_heart"' not in line and "'af_heart'" not in line:
                    continue
                # A tone preset may name any voice it likes: `researcher` keeps
                # a female one on purpose, because it is a selectable
                # alternative rather than the voice anybody gets by default.
                #
                # Matched on the exact shape of a preset entry, not on the file
                # it lives in. Excluding "anything in main.py" would also have
                # excused a new `.get("voice", "af_heart")` fallback — which is
                # precisely the line this test exists to catch, and it lives in
                # main.py too.
                if stripped == '"voice": "af_heart",':
                    continue
                offenders.append(f"{path.relative_to(backend)}:{number}")

        assert not offenders, (
            "These spell a default voice instead of importing `voice.config.DEFAULT_VOICE`:\n  "
            + "\n  ".join(offenders)
        )
