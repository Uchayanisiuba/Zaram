# backend/tests/test_alpha10c_acceptance.py
"""
Sprint Alpha.10C — Internet Search Acceptance Tests

Verifies:
- Exactly one search executes per request
- Search results are formatted with structured context block
- Planner does not duplicate search when marker is present
- Prompt formatting includes structured blocks
"""
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parents[1]
if str(backend_path) not in sys.path:
     sys.path.insert(0, str(backend_path))

from unittest.mock import patch, AsyncMock

from core.planner import IntentPlanner
from core.query_classifier import needs_search, SEARCH_MARKER


class FakeKnowledgeSearch:
    def __init__(self, results):
        self.results = results
        self.call_count = 0

    def search_knowledge(self, query, persona="zaram_prime"):
        self.call_count += 1
        return {
            "query": query,
            "persona": persona,
            "total_results": len(self.results),
            "results": self.results,
        }


class TestNoDuplicateSearch:
    def test_planner_skips_search_when_marker_present(self):
        planner = IntentPlanner()
        prompt_with_results = f"{SEARCH_MARKER}\nUser Question: What is the latest Unreal Engine version?\n"
        plan = planner.create_plan(prompt_with_results)
        assert len(plan.steps) == 1
        assert plan.steps[0].capability_id == "reasoning.generate"

    def test_planner_includes_search_when_no_marker(self, monkeypatch):
        # Web search is off by default; this test is about search *routing*, so
        # it states that precondition explicitly. See the sequencing commitments
        # in CLAUDE.md and test_outbound_query_invariant.py.
        monkeypatch.setenv("ZARAM_WEB_SEARCH", "1")
        planner = IntentPlanner()
        prompt = "What is the latest Unreal Engine version?"
        plan = planner.create_plan(prompt)
        assert len(plan.steps) == 2
        assert plan.steps[0].capability_id == "knowledge.search"
        assert plan.steps[1].capability_id == "reasoning.generate"

    def test_planner_skips_search_for_timeless_question(self):
        planner = IntentPlanner()
        prompt = "Explain recursion"
        plan = planner.create_plan(prompt)
        assert len(plan.steps) == 1
        assert plan.steps[0].capability_id == "reasoning.generate"


class TestClassifier:
    def test_time_sensitive_detection(self):
        assert needs_search("What is the latest AI news today?") is True
        assert needs_search("Current weather forecast") is True
        assert needs_search("Breaking news about the election") is True

    def test_factual_detection(self):
        assert needs_search("Who is the current US president?") is True
        assert needs_search("What was the stock price yesterday?") is True
        assert needs_search("When did Unreal Engine 5 release?") is True

    def test_topic_detection(self):
        assert needs_search("Latest OpenAI announcement") is True
        assert needs_search("Latest Gemini model update") is True
        assert needs_search("Latest Blender release notes") is True

    def test_timeless_detection(self):
        assert needs_search("Explain recursion") is False
        assert needs_search("How does Python work") is False
        assert needs_search("What is polymorphism") is False

    def test_short_input(self):
        assert needs_search("") is False
        assert needs_search("   ") is False

    def test_marker_prevents_search(self):
        prompt = f"{SEARCH_MARKER}\nSome context\nWhat is the latest AI news?"
        assert needs_search(prompt) is False


class TestPromptFormatting:
    def test_format_search_results_creates_structured_block(self):
        from main import _format_search_results
        search_result = {
            "query": "test query",
            "total_results": 2,
            "results": [
                {
                    "title": "Test Title",
                    "url": "https://example.com",
                    "snippet": "Test snippet content",
                    "published": "2026-07-22",
                },
                {
                    "title": "",
                    "url": "https://example.org",
                    "snippet": "Another snippet",
                    "published": "",
                },
            ],
        }
        formatted = _format_search_results("test query", search_result)
        assert SEARCH_MARKER in formatted
        assert "Source 1:" in formatted
        assert "Title: Test Title" in formatted
        assert "URL: https://example.com" in formatted
        assert "Published: 2026-07-22" in formatted
        assert "Snippet: Test snippet content" in formatted
        assert "User Question:" in formatted

    def test_format_empty_results(self):
        from main import _format_search_results
        formatted = _format_search_results("test query", {"total_results": 0, "results": []})
        assert formatted == "test query"


class TestEndToEndSearch:
    def test_chat_endpoint_triggers_single_search(self):
        from main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        fake_results = [
            {"title": "UE5.5 Released", "url": "https://unrealengine.com", "snippet": "Unreal Engine 5.5 is now available.", "published": "2026-07-22"},
        ]
        fake_search = FakeKnowledgeSearch(fake_results)

        import main as main_module
        original_search = main_module._format_search_results

        def fake_search_knowledge(query, persona="zaram_prime"):
            return fake_search.search_knowledge(query, persona)

        with patch("knowledge.knowledge_service.search_knowledge", fake_search_knowledge):
            with patch.object(main_module, "chat_router") as mock_router:
                async def fake_stream(text, model, system_prompt):
                    yield "data: {\"type\": \"token\", \"content\": \"test\"}\n\n"
                    yield "data: [DONE]\n\n"

                mock_router.route.return_value = fake_stream("text", "model", "prompt")

                response = client.post("/chat", json={
                    "text": "What is the latest Unreal Engine version?",
                    "model": "gemma3:latest",
                    "persona": "zaram_prime",
                })

                assert fake_search.call_count == 1
                assert response.status_code == 200
