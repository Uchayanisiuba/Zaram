"""A document about an open repository is written from the repository.

The second layer of the 3 October 2026 report. After the briefing and the
recall block were taught to say which project is open, *"do an audit on this
project"* stopped inventing — it replied *"I'll need to review the files in
the repository at E:\\Keyline"* — and then did not review them. The tail of
the reply said why:

    Wrote the document · did not run
    · [FALLBACK] document.generate failed: I'd be guessing.

**"Audit" reads as a document request**, and the DOCUMENT branch is first in
the planner's chain. It built `reasoning.generate` → `document.generate` with
no listing step at all, so the turn had **no tools and no repository map** —
both arrive on `mcp.list_tools`. The body was written from recalled memory,
and on a referential five-word question the only memory anywhere near it was
about other work.

Rule 9 is what makes this urgent rather than untidy: *"a document produced
from unresolved context is confident, plausible and wrong — and unlike a chat
reply, it leaves the building."* A wrong reply is corrected on the next turn;
a wrong audit reads as finished work and gets sent to somebody.

The refusal path did fire, which is the rule working as designed and is the
only reason this was a visible failure rather than a plausible document. The
fix is to stop reaching it: give the body step what every other coding turn
already gets.
"""

from __future__ import annotations

import pytest

from core.planner import IntentPlanner, IntentType


def _planner(repo_open: bool) -> IntentPlanner:
    """A planner that classifies as DOCUMENT, with the repository probe set.

    **The classification is forced, and that is deliberate.** `IntentRouter`
    decides DOCUMENT by embedding the prompt against exemplars, so a bare
    router with no embedder answers `conversation` for everything — every
    phrasing tried here included. A test that went through it would skip or,
    worse, pass while exercising a different branch.

    What is under test is the *planner's* response to a document request with
    a repository open, so that is what is handed to it. The router has its own
    tests; `CLAUDE.md`'s rule about checking the instrument cuts both ways —
    a test must not quietly measure something other than its subject.
    """
    planner = IntentPlanner()
    planner.set_code_project_open(lambda: repo_open)
    original = planner._router.classify

    def as_document(prompt: str):
        verdict = original(prompt)
        return type(verdict)(
            **{**verdict.__dict__, "intent_type": IntentType.DOCUMENT}
        )

    planner._router.classify = as_document
    return planner


def plan_for(prompt: str, *, repo_open: bool):
    return [s.capability_id for s in _planner(repo_open).create_plan(prompt).steps]


def steps_of(prompt: str, *, repo_open: bool):
    return _planner(repo_open).create_plan(prompt).steps


@pytest.fixture
def document_prompt():
    return "write up an audit of this project as a document"


class TestWithARepositoryOpen:
    def test_the_tools_are_listed_first(self, document_prompt):
        steps = plan_for(document_prompt, repo_open=True)
        assert steps[0] == "mcp.list_tools", steps

    def test_the_body_is_written_after_the_listing(self, document_prompt):
        steps = steps_of(document_prompt, repo_open=True)
        body = next(s for s in steps if s.capability_id == "reasoning.generate")
        assert body.depends_on == [0]

    def test_the_document_is_made_from_the_body_not_the_request(self, document_prompt):
        """Unchanged, and worth holding: generating straight from the prompt
        would write up the user's own question."""
        steps = steps_of(document_prompt, repo_open=True)
        document = next(s for s in steps if s.capability_id == "document.generate")
        body_index = next(
            i for i, s in enumerate(steps) if s.capability_id == "reasoning.generate"
        )
        assert document.depends_on == [body_index]

    def test_the_document_step_still_gets_the_users_own_words(self, document_prompt):
        """The runtime reads them to decide whether a spreadsheet or an
        invoice was asked for, and the rewritten body instruction matches
        none of them."""
        steps = steps_of(document_prompt, repo_open=True)
        document = next(s for s in steps if s.capability_id == "document.generate")
        assert document.input_data["prompt"] == document_prompt


class TestWithNoRepositoryOpen:
    """The far more common case, and it must not pay for this.

    A letter, an invoice, a summary of a conversation — none of them wants a
    tool listing, and adding one would put the tool rules in every document
    prompt on the machine.
    """

    def test_the_plan_is_unchanged(self, document_prompt):
        assert plan_for(document_prompt, repo_open=False) == [
            "reasoning.generate",
            "document.generate",
        ]

    def test_the_body_depends_on_nothing(self, document_prompt):
        steps = steps_of(document_prompt, repo_open=False)
        assert steps[0].depends_on == []
        assert steps[1].depends_on == [0]


class TestTheProbeIsReachable:
    """`_coding_project_is_open` decides whether any of the above happens.

    It is wired in `bootstrapper.py` to `active_root() is not None`. Asserted
    because an unwired probe answers `False` forever and every test above
    would still pass while the product did nothing — which is this codebase's
    documented base rate, and the reason the wiring is checked rather than
    assumed.
    """

    def test_the_bootstrapper_wires_it(self):
        from pathlib import Path

        boot = (Path(__file__).resolve().parents[1] / "core" / "bootstrapper.py").read_text(
            encoding="utf-8"
        )
        assert "set_code_project_open(lambda: active_root() is not None)" in boot

    def test_an_unset_probe_does_not_add_the_listing(self, document_prompt):
        """Nobody told the planner, so it must not guess a repository is open."""
        planner = _planner(repo_open=False)
        planner.set_code_project_open(None)
        steps = [s.capability_id for s in planner.create_plan(document_prompt).steps]
        assert steps == ["reasoning.generate", "document.generate"]

    def test_a_probe_that_raises_does_not_take_the_reply_with_it(self, document_prompt):
        def boom() -> bool:
            raise RuntimeError("the project store is unreachable")

        planner = _planner(repo_open=False)
        planner.set_code_project_open(boom)
        steps = [s.capability_id for s in planner.create_plan(document_prompt).steps]
        assert "document.generate" in steps
