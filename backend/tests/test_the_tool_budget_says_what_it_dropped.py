"""A server shut out by the context budget says so, and can be overridden.

Found 3 October 2026 by grepping the interface for `offered`, which the
backend has reported per server since 20 September. **There was no caller.**

So attaching a server with 39 tools — Comfy Org's `comfy-mcp` is one — put 8
in front of the model and dropped 31 in silence. The model then truthfully
answered that it could not run the thing, while the card showed a server that
was attached, reachable and healthy. Three correct components and a product
that appeared broken.

`CLAUDE.md` names both halves of the failure:

* *"Disabled capabilities are visible, not silent. If a question would have
  used search and search is off, say so rather than answering quietly without
  it."* The counts exist precisely so the interface can say it.
* And the shape this file is really about — *"assume unreachable until the
  caller is seen"*, with fifteen complete, tested, unreachable subsystems
  already found. The counts were measured, reported and tested. Nothing asked
  for them.

**Saying it is only half.** A product that reports *"31 tools omitted"* and
offers no way to choose which is a complaint rather than a control — the same
way a refusal that does not name the switch reads as a broken product. So a
person may **pin** a tool, and a pin survives the budget.

**A pin is a membership decision, and it is the only one allowed to be.**
`CLAUDE.md` is emphatic that a blend may order candidates and must never
decide what is in the running, and that error has cost this codebase three
times. A pin is not a score: it is the user naming a tool, the same kind of
act as granting one. The tests below assert that it cannot become permission
— being seen by the model and being allowed to act are different questions,
and the grant is a different field.
"""

from __future__ import annotations

import asyncio

import pytest

from runtimes.mcp.client import ToolDescriptor
from runtimes.mcp.config import ServerConfig, ServerStore, WriteMode
from runtimes.mcp.runtime import CALL, LIST_TOOLS, McpRuntime


class Fake:
    """A server offering as many tools as it is told to."""

    def __init__(self, server_id: str, count: int):
        self.server_id = server_id
        self._count = count
        self.closed = False

    def connect(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    def list_tools(self):
        return [
            ToolDescriptor(
                server_id=self.server_id,
                name=f"edit_thing_{n:02d}",
                description=f"changes thing {n}",
            )
            for n in range(self._count)
        ]

    def call_tool(self, name, arguments):
        return {"did": name}


@pytest.fixture
def store(tmp_path):
    store = ServerStore(tmp_path / "servers.json")
    store.save(
        {
            "comfy": ServerConfig(
                server_id="comfy", command=["node", "comfy.js"], writes=WriteMode.HOST_UNDO
            )
        }
    )
    return store


@pytest.fixture
def runtime(store):
    runtime = McpRuntime(store=store)
    # Attached the way a stranger's server is: through `_connections`, so the
    # budget applies. A `register_builtin` server is never trimmed, which is
    # the case the row must *not* warn about — asserted separately below.
    runtime._connections["comfy"] = Fake("comfy", 39)
    return runtime


def ask(runtime, query: str = ""):
    return asyncio.run(runtime.execute(LIST_TOOLS, {"query": query}))


class TestTheNumbersAreReported:
    def test_before_a_question_neither_count_is_invented(self, runtime):
        """`None`, not 0 — and that distinction is the point.

        *"Nothing has been asked yet"* and *"this server was shut out"* are
        different answers, and a status indicator over hardcoded data is
        worse than no indicator. Same split `vram_bytes` makes by returning
        `None` rather than a confident zero.
        """
        health = asyncio.run(runtime.health_check())
        assert health["servers"]["comfy"]["tools"] is None
        assert health["servers"]["comfy"]["offered"] is None

    def test_after_a_question_both_are_real(self, runtime):
        ask(runtime)
        health = asyncio.run(runtime.health_check())
        assert health["servers"]["comfy"]["tools"] == 39
        assert health["servers"]["comfy"]["offered"] == runtime._budget
        assert health["tool_budget"] == runtime._budget

    def test_the_shortfall_is_the_difference(self, runtime):
        ask(runtime)
        server = asyncio.run(runtime.health_check())["servers"]["comfy"]
        assert server["tools"] - server["offered"] == 39 - runtime._budget


class TestTheListingCarriesThem:
    """On `/tools/servers`, which is the endpoint the interface calls.

    Left only on `/tools/health` they would still be unreachable — which is
    what they were. The surface that renders the server is the surface that
    has to say it.
    """

    @pytest.fixture
    def client(self, runtime, store, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from runtimes.mcp import api

        monkeypatch.setattr(api, "_store", lambda: store)
        api.set_mcp_runtime(runtime)
        app = FastAPI()
        # `api.router` already carries `prefix="/tools"`; main.py mounts it
        # bare. Adding the prefix here produced `/tools/tools/servers` and a
        # 404 whose body has no `servers` key, which is how this was found.
        app.include_router(api.router)
        try:
            yield TestClient(app)
        finally:
            api.set_mcp_runtime(None)

    def test_the_row_can_say_what_was_dropped(self, client, runtime):
        ask(runtime)
        body = client.get("/tools/servers").json()["servers"][0]
        assert body["tools"] == 39
        assert body["offered"] == runtime._budget
        assert body["toolBudget"] == runtime._budget

    def test_it_answers_before_the_kernel_is_up(self, client, store, monkeypatch):
        """The store-backed listing must keep working with no runtime.

        The interface shows what is configured while the backend is still
        starting, and the counts are absent rather than zero.
        """
        from runtimes.mcp import api

        api.set_mcp_runtime(None)
        body = client.get("/tools/servers").json()["servers"][0]
        assert body["tools"] is None
        assert body["offered"] is None
        assert body["builtin"] is False

    def test_the_names_are_listed_unranked_and_uncut(self, client, runtime):
        """A person cannot choose from a count.

        And the list must not be the shortlist: they are here precisely
        because the shortlist is smaller than the server.
        """
        body = client.get("/tools/servers/comfy/tools").json()
        assert len(body["tools"]) == 39
        assert body["tools"][0]["name"] == "edit_thing_00"

    def test_an_unknown_server_is_a_404_not_an_empty_list(self, client):
        assert client.get("/tools/servers/nobody/tools").status_code == 404
        assert client.put("/tools/servers/nobody/pins", json={"tools": ["x"]}).status_code == 404


class TestAPinSurvivesTheBudget:
    def test_unpinned_the_last_tools_never_arrive(self, runtime):
        offered = {t["name"] for t in ask(runtime)["tools"]}
        assert "edit_thing_38" not in offered

    def test_pinned_it_does(self, runtime, store):
        store.pin("comfy", {"edit_thing_38"})
        offered = {t["name"] for t in ask(runtime)["tools"]}
        assert "edit_thing_38" in offered

    def test_the_budget_still_holds_overall(self, runtime, store):
        store.pin("comfy", {"edit_thing_38"})
        assert len(ask(runtime)["tools"]) == runtime._budget

    def test_pinning_more_than_the_budget_is_honoured(self, runtime, store):
        """Their call, and a stronger signal than a cap chosen by measurement.

        Each one was named. The alternative — silently dropping some of what
        somebody explicitly pinned — is the original defect with an extra step.
        """
        wanted = {f"edit_thing_{n:02d}" for n in range(30, 39)}
        store.pin("comfy", wanted)
        offered = {t["name"] for t in ask(runtime)["tools"]}
        assert wanted <= offered

    def test_a_pin_is_not_ranked_away(self, runtime, store):
        """With a ranker attached and a query that matches nothing it pinned."""
        runtime.set_ranker(lambda query, tools, budget: list(tools)[:budget])
        store.pin("comfy", {"edit_thing_38"})
        offered = {t["name"] for t in ask(runtime, "something about invoices")["tools"]}
        assert "edit_thing_38" in offered

    def test_unpinning_the_last_one_means_none(self, runtime, store):
        """Which an add-only endpoint could not express."""
        store.pin("comfy", {"edit_thing_38"})
        store.pin("comfy", set())
        assert store.load()["comfy"].pinned_tools == set()
        assert "edit_thing_38" not in {t["name"] for t in ask(runtime)["tools"]}

    def test_it_survives_a_reload_from_disk(self, runtime, store):
        store.pin("comfy", {"edit_thing_38"})
        fresh = ServerStore(store.path)
        assert fresh.load()["comfy"].pinned_tools == {"edit_thing_38"}


class TestAPinIsVisibilityNotPermission:
    """The one thing this control must never do.

    Being seen by the model and being allowed to act are different questions.
    A control that quietly granted what it revealed would make the context
    budget a permission surface, which the risk tiers forbid for a separate
    reason — and it would do it through the one field a person would read as
    cosmetic.
    """

    def test_pinning_grants_nothing(self, runtime, store):
        store.pin("comfy", {"edit_thing_38"})
        cfg = store.load()["comfy"]
        assert cfg.pinned_tools == {"edit_thing_38"}
        assert cfg.granted_tools == set()

    def test_a_pinned_tool_still_asks(self, runtime, store):
        store.pin("comfy", {"edit_thing_38"})
        result = asyncio.run(
            runtime.execute(
                CALL, {"server": "comfy", "tool": "edit_thing_38", "arguments": {}}
            )
        )
        assert result["needs_confirmation"] is True

    def test_granting_does_not_pin(self, store):
        """And the reverse, because the fields must not drift into one.

        Somebody allowing a tool has said what it may do, not that it should
        displace another from a limited window.
        """
        store.grant("comfy", "edit_thing_01")
        cfg = store.load()["comfy"]
        assert cfg.granted_tools == {"edit_thing_01"}
        assert cfg.pinned_tools == set()


class TestZaramsOwnPacksAreNotTrimmed:
    """So a built-in must never carry a shortfall warning.

    The budget exists for strangers' servers. Dropping `write_file` because a
    ranker judged `look_at_app` closer to the question breaks the task rather
    than trimming the prompt — found 13 September, when the pack reached
    fourteen tools and the interface said *"7 attached"*.
    """

    def test_every_builtin_tool_is_offered(self, store):
        runtime = McpRuntime(store=store)
        runtime.register_builtin(ServerConfig(server_id="code"), Fake("code", 14))
        offered = ask(runtime)["tools"]
        assert len([t for t in offered if t["server"] == "code"]) == 14

    def test_a_builtin_is_not_in_the_listing_at_all(self, store):
        """And that is why it cannot carry a shortfall warning.

        `register_builtin` deliberately does not write to `mcp-servers.json`
        — that file is the servers the *user* attached, and a built-in in it
        could be deleted and would come back on the next launch. Both
        `health_check` and `/tools/servers` read the store, so Zaram's own
        packs never appear on the surface the budget warning lives on.

        Worth asserting rather than assuming: it is the reason the `builtin`
        flag is almost always `False`, and somebody reading that flag could
        otherwise conclude it is broken.
        """
        runtime = McpRuntime(store=store)
        runtime.register_builtin(ServerConfig(server_id="code"), Fake("code", 14))
        ask(runtime)
        assert "code" not in asyncio.run(runtime.health_check())["servers"]

    def test_the_flag_is_for_the_name_collision(self, tmp_path):
        """The one case it does fire, and the case it was written for.

        `_configs` puts built-ins last so a user attaching a server under a
        built-in's name cannot shadow it. The *store* then holds that name, so
        it does reach the listing — and it must not be warned about, because
        the tools being counted are Zaram's own and were never trimmed.
        """
        store = ServerStore(tmp_path / "servers.json")
        store.save({"code": ServerConfig(server_id="code", command=["node", "x.js"])})
        runtime = McpRuntime(store=store)
        runtime.register_builtin(ServerConfig(server_id="code"), Fake("code", 14))
        ask(runtime)
        assert asyncio.run(runtime.health_check())["servers"]["code"]["builtin"] is True
