"""A dev server the model started opens in Zaram's own browser pane.

**The shape of the bug, 11 October 2026.** The maintainer: *"when Zaram is
building an app, instead of just giving the user a link to the localhost and
telling the user to open it in the browser, it actually opens the localhost."*
The pane already existed and already opened from a card's address. Two things
kept it from opening for a model-started app:

* `start_app_stack` answers with a list of processes and no `url` of its own,
  so the tool event carried no address and there was nothing to open;
* no process said what it was *for*, so choosing the frontend of several meant
  guessing from names.

These pin the half that lives in the backend: which address a started stack
reports, how a process reports its role, and what the model is told.
"""

from __future__ import annotations

from packs.code import apps
from packs.code.apps import OPENS_ITSELF, START_APP, START_APP_STACK, page_url, role_of
from packs.code.runners import Runner


def _proc(name: str, url: str | None, role: str | None = None, running: bool = True) -> dict:
    return {"name": name, "url": url, "role": role, "running": running, "runner": f"npm:{name}"}


def _stack(*procs: dict) -> dict:
    return {"stack": True, "processes": list(procs), "started": [p["name"] for p in procs]}


class TestTheAddressAStackReports:
    def test_a_single_app_reports_its_own_url(self):
        assert page_url(START_APP, {"url": "http://127.0.0.1:5173"}) == "http://127.0.0.1:5173"

    def test_a_single_app_with_no_url_yet_reports_nothing(self):
        assert page_url(START_APP, {"url": None}) == ""

    def test_the_frontend_is_chosen_by_its_role_whatever_it_is_called(self):
        stack = _stack(
            _proc("api", "http://127.0.0.1:8000", role="backend"),
            _proc("dev", "http://127.0.0.1:5173", role="frontend"),
        )
        assert page_url(START_APP_STACK, stack) == "http://127.0.0.1:5173"

    def test_a_name_that_says_frontend_does_not_outrank_a_role(self):
        # The role is the fact; a process called "frontend" that reports itself
        # a backend is not the page.
        stack = _stack(
            _proc("frontend", "http://127.0.0.1:8000", role="backend"),
            _proc("web", "http://127.0.0.1:3000", role="frontend"),
        )
        assert page_url(START_APP_STACK, stack) == "http://127.0.0.1:3000"

    def test_one_running_process_is_the_page_even_if_it_is_a_backend(self):
        stack = _stack(_proc("server", "http://127.0.0.1:8000", role="backend"))
        assert page_url(START_APP_STACK, stack) == "http://127.0.0.1:8000"

    def test_a_process_that_died_is_not_the_page(self):
        stack = _stack(
            _proc("dev", "http://127.0.0.1:5173", role="frontend", running=False),
            _proc("api", "http://127.0.0.1:8000", role="backend"),
        )
        assert page_url(START_APP_STACK, stack) == "http://127.0.0.1:8000"

    def test_the_one_process_not_known_to_be_something_else_is_the_page(self):
        stack = _stack(
            _proc("api", "http://127.0.0.1:8000", role="backend"),
            _proc("dev", "http://127.0.0.1:5173", role=None),
        )
        assert page_url(START_APP_STACK, stack) == "http://127.0.0.1:5173"

    def test_several_unplaced_processes_yield_nothing_rather_than_a_guess(self):
        stack = _stack(
            _proc("a", "http://127.0.0.1:3001"),
            _proc("b", "http://127.0.0.1:3002"),
        )
        assert page_url(START_APP_STACK, stack) == ""

    def test_a_stack_that_announced_no_address_yet_yields_nothing(self):
        assert page_url(START_APP_STACK, _stack(_proc("dev", None, role="frontend"))) == ""

    def test_something_that_is_not_a_result_yields_nothing(self):
        assert page_url(START_APP_STACK, "boom") == ""
        assert page_url(START_APP_STACK, None) == ""


class TestWhatAProcessIsFor:
    def test_a_vite_server_is_a_frontend(self):
        runner = Runner(name="npm:dev", argv=("npm", "run", "dev", "--", "vite"), description="")
        assert role_of(runner) == "frontend"

    def test_a_runserver_is_a_backend(self):
        runner = Runner(name="django", argv=("python", "manage.py", "runserver"), description="")
        assert role_of(runner) == "backend"

    def test_an_unrecognised_command_has_no_role_rather_than_a_wrong_one(self):
        runner = Runner(name="npm:serve", argv=("npm", "run", "serve"), description="")
        assert role_of(runner) is None


class TestWhatTheModelIsTold:
    def _descriptions(self) -> dict:
        tools = apps.AppTools()
        return {d.name: d.description for d in tools.descriptors("code", None)}

    def test_both_start_tools_say_zaram_opens_the_app_itself(self):
        described = self._descriptions()
        for name in (START_APP, START_APP_STACK):
            assert OPENS_ITSELF in described[name], name

    def test_the_sentence_forbids_the_instruction_it_replaces(self):
        assert "do not tell the person to open the link" in OPENS_ITSELF

    def test_it_names_no_model_or_provider(self):
        for word in ("qwen", "gemma", "llama", "gpt", "claude", "ollama"):
            assert word not in OPENS_ITSELF.lower()
