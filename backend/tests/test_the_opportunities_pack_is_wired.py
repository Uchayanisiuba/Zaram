"""The eligibility gate exists in the running product, not only in its own test.

`test_the_opportunity_gate_filters.py` builds `OpportunityTools` by hand and
proves its rules. That is necessary and it is not sufficient — the same was
true of the MCP runtime for a fortnight while nothing could name `mcp.call`, of
the library tools that shipped measured and unregistered, and of fifteen other
subsystems here. `CLAUDE.md`: *assume unreachable until the caller is seen.*

So this asserts the two links that turn a module into a feature. The
bootstrapper registers the server, against the real boot path rather than a
fixture that repeats it — delete the registration line and this fails while
every other opportunities test still passes. And the project types that
activate the pack exist and round-trip through the store, because a pack whose
type cannot be chosen is a pack nobody reaches.

It also asserts an absence, which is the unusual one: **there is no submission
tool, and the boot must never offer one.** That is not a limitation to be
lifted later. Grants.gov's own API documentation says applications cannot be
submitted through it and the EU portal has no submission endpoint, so a tool
promising otherwise would be describing a capability that does not exist to a
model that would then narrate having used it.
"""

from __future__ import annotations

import pytest

from packs.opportunities import CHECK_ELIGIBILITY, READ_CRITERIA, SERVER_ID


async def _offered_by_a_real_boot() -> set:
    from core.bootstrapper import KernelBootstrapper

    kernel = KernelBootstrapper()
    await kernel.boot()
    try:
        listed = await kernel.mcp_runtime.execute(
            "mcp.list_tools", {"query": "am I eligible to apply for this grant"}
        )
        assert listed["success"] is True
        return {t["name"] for t in listed["tools"] if t["server"] == SERVER_ID}
    finally:
        await kernel.shutdown()


@pytest.mark.asyncio
async def test_the_bootstrapper_offers_the_gate_to_the_model() -> None:
    offered = await _offered_by_a_real_boot()

    assert CHECK_ELIGIBILITY in offered, (
        "the model is never handed a way to ask whether the person can actually "
        "apply, so it will answer from the posting's prose instead — which is a "
        "stranger's text deciding who is eligible"
    )
    assert READ_CRITERIA in offered


@pytest.mark.asyncio
async def test_the_boot_offers_no_way_to_submit_an_application() -> None:
    """An absence asserted on purpose.

    Rules 6, 9 and the mutative tier all land on this line independently, and
    so do the funders: neither Grants.gov nor the EU portal exposes a
    submission endpoint at all. A tool named for it would promise something
    that does not exist.
    """
    offered = await _offered_by_a_real_boot()

    forbidden = {n for n in offered if any(w in n for w in ("apply", "submit", "send"))}
    assert not forbidden, f"the pack grew a way to send an application: {forbidden}"


def test_both_project_types_exist_and_round_trip(tmp_path) -> None:
    """A pack whose project type cannot be chosen is a pack nobody reaches.

    Two types rather than one because the weighting has to live somewhere —
    for jobs the bottleneck is the draft, for grants it is eligibility — and
    one pack rather than two because the pipeline is shared and a copy of it
    would have drifted within a month.
    """
    from projects.records import ProjectRecords, ProjectType

    assert ProjectType("jobs") is ProjectType.JOBS
    assert ProjectType("grants") is ProjectType.GRANTS

    records = ProjectRecords(str(tmp_path / "projects.db"))
    made = records.create("Funding 2026", type=ProjectType.GRANTS)
    assert records.get(made.id).type is ProjectType.GRANTS

    switched = records.set_type(made.id, ProjectType.JOBS)
    assert switched.type is ProjectType.JOBS
