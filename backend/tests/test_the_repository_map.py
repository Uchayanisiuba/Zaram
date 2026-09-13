"""The model is shown the shape of the repository before it acts.

Aider's repo map, taken 12 September 2026 without its dependencies: files and
the definitions in them, ranked by lexical overlap with the question, trimmed
to a budget, and honest about what was trimmed.
"""

from __future__ import annotations

import json

import pytest

from core.context_budget import estimate_tokens
from packs.code import SERVER_ID, CodeTools, CodeWriter, repo_map
from packs.code.tools import MAP_TOKENS
from runtimes.mcp.config import ServerConfig, ServerStore, WriteMode
from runtimes.mcp.runtime import LIST_TOOLS, McpRuntime


@pytest.fixture
def project(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "billing.py").write_text(
        "class Invoice:\n    pass\n\n\ndef total_due(items):\n    return 0\n", encoding="utf-8"
    )
    (tmp_path / "src" / "users.py").write_text("def find_user(uid):\n    return None\n", encoding="utf-8")
    (tmp_path / "src" / "deep").mkdir()
    (tmp_path / "src" / "deep" / "helpers.ts").write_text(
        "export function formatMoney(n: number) { return '' }\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("# not code\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("function hidden() {}\n", encoding="utf-8")
    repo_map.forget()
    return tmp_path


class TestTheMap:
    def test_it_names_files_and_their_definitions(self, project):
        text = repo_map.repo_map(project, "anything", budget_tokens=2000)
        assert "src/billing.py" in text
        assert "Invoice, total_due" in text
        assert "src/deep/helpers.ts" in text and "formatMoney" in text

    def test_it_skips_what_ingestion_skips_and_what_is_not_code(self, project):
        text = repo_map.repo_map(project, "anything", budget_tokens=2000)
        assert "node_modules" not in text and "hidden" not in text
        assert "README.md" not in text

    def test_the_question_ranks_the_file_it_names_first(self, project):
        text = repo_map.repo_map(project, "why is the invoice total wrong", budget_tokens=2000)
        body = text.split("first.")[1]
        assert body.index("src/billing.py") < body.index("src/users.py")

        text = repo_map.repo_map(project, "how do we find a user", budget_tokens=2000)
        body = text.split("first.")[1]
        assert body.index("src/users.py") < body.index("src/billing.py")

    def test_camel_case_matches_its_parts(self, project):
        text = repo_map.repo_map(project, "where is money formatted", budget_tokens=2000)
        body = text.split("first.")[1]
        assert body.index("src/deep/helpers.ts") < body.index("src/users.py")

    def test_the_budget_trims_and_says_so(self, project):
        text = repo_map.repo_map(project, "anything", budget_tokens=1)
        # One file always survives, and the rest are counted, never silently gone.
        assert "2 more files not shown" in text
        assert estimate_tokens(text) < 200

    def test_an_empty_folder_is_no_map(self, tmp_path):
        assert repo_map.repo_map(tmp_path, "x", budget_tokens=100) == ""

    def test_the_walk_is_cached_and_a_write_forgets_it(self, project):
        repo_map.repo_map(project, "x", budget_tokens=2000)
        (project / "src" / "late.py").write_text("def arrived():\n    pass\n", encoding="utf-8")
        assert "late.py" not in repo_map.repo_map(project, "x", budget_tokens=2000)
        repo_map.forget(project)
        assert "late.py" in repo_map.repo_map(project, "x", budget_tokens=2000)


class TestItReachesThePrompt:
    def test_the_listing_carries_the_briefing(self, project):
        runtime = McpRuntime(store=ServerStore(str(project / "servers.json")))
        runtime.register_builtin(
            ServerConfig(server_id=SERVER_ID, writes=WriteMode.HOST_UNDO),
            CodeTools(lambda: project, writer=CodeWriter()),
        )
        import asyncio

        listed = asyncio.run(runtime.execute(LIST_TOOLS, {"query": "invoice"}))
        assert "## The open project" in listed["briefing"]
        assert "src/billing.py" in listed["briefing"]
        assert estimate_tokens(listed["briefing"]) <= MAP_TOKENS + 60

    def test_no_project_means_no_briefing(self, tmp_path):
        runtime = McpRuntime(store=ServerStore(str(tmp_path / "servers.json")))
        runtime.register_builtin(
            ServerConfig(server_id=SERVER_ID, writes=WriteMode.HOST_UNDO),
            CodeTools(lambda: None),
        )
        import asyncio

        assert asyncio.run(runtime.execute(LIST_TOOLS, {"query": "x"}))["briefing"] == ""

    def test_the_engine_places_it_before_the_tool_rules(self):
        """Rules last — the ordering `tool_instructions` and `identity_preamble`
        keep against text that arrived from outside."""
        from core.execution_engine import ExecutionEngine
        from core.tool_loop import tool_instructions

        payload = json.dumps({
            "success": True,
            "tools": [{"server": "code", "name": "read_lines", "description": "read"}],
            "briefing": "\n## The open project\n\nsrc/app.py\n",
        })
        engine = ExecutionEngine.__new__(ExecutionEngine)
        briefing = engine._parse_briefing(payload)
        assert "src/app.py" in briefing
        composed = briefing + tool_instructions(engine._parse_tool_list(payload))
        assert composed.index("src/app.py") < composed.index("## Tools attached")
