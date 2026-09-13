"""`read_page`: fetch a page and hand back its prose, through the gate.

The same shape as the code pack's tools — a built-in MCP server in process,
so it inherits the policy gate, the injection scan on results, the tool
budget rules and the egress log without a second mechanism.
"""

from __future__ import annotations

import logging
import urllib.error
from typing import Any, Callable, Dict, List, Optional

from runtimes.internet.deep_read import MAX_CHARS, extract_text
from runtimes.mcp.client import ToolDescriptor

from .active import named_urls, normalise

logger = logging.getLogger(__name__)

__all__ = ["WebTools", "READ_PAGE", "SERVER_ID", "PAGE_TIMEOUT"]

SERVER_ID = "web"
READ_PAGE = "read_page"
#: A person is waiting; a page that takes longer than this is reported as
#: slow rather than held open. Longer than deep read's six seconds because
#: this page was asked for by name, and its absence is the whole answer.
PAGE_TIMEOUT = 15.0


class WebTools:
    """Zaram's built-in web server: one tool, `read_page`."""

    def __init__(self, fetch: Optional[Callable[..., bytes]] = None) -> None:
        # Injectable for tests; the real one is the gate's synchronous path.
        self._fetch = fetch

    # -- the built-in server surface ------------------------------------------ #

    def connect(self) -> None:
        """Nothing to start. Present because the runtime calls it."""

    def close(self) -> None:
        """Nothing to stop."""

    def granted_tools(self) -> set:
        """Always offered. The consent question is per page, inside the tool:
        a page the person named may be read; any other meets the per-host
        policy. Withholding the tool would not make either safer."""
        return {READ_PAGE}

    def list_tools(self) -> List[ToolDescriptor]:
        return [
            ToolDescriptor(
                server_id=SERVER_ID,
                name=READ_PAGE,
                description=(
                    "Open a web page and read its text. Use it when the person names a "
                    "page or site, or when a search result's snippet is not enough to "
                    "answer. Returns the page's readable prose, up to a few thousand "
                    "characters. A page the person did not name may be refused by their "
                    "privacy rules; if so, say so and do not guess its contents."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The page's address."},
                        "question": {
                            "type": "string",
                            "description": "What you are looking for on it, if anything in particular.",
                        },
                    },
                    "required": ["url"],
                },
            )
        ]

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        arguments = arguments or {}
        if name != READ_PAGE:
            return {"error": f"the web server has no tool called {name!r}"}
        return self.read_page(str(arguments.get("url") or ""), str(arguments.get("question") or ""))

    # -- the tool ------------------------------------------------------------- #

    def read_page(self, url: str, question: str = "") -> Dict[str, Any]:
        if not url.strip():
            return {"error": "no address was given"}
        try:
            target = normalise(url)
        except ValueError:
            return {"error": f"{url!r} is not an address Zaram can open"}

        # Rule 7j. A page the person named in their own message is a
        # destination they chose, and travels on a grant of that exact URL —
        # the same capability search results use. Anything else meets the
        # per-host policy: allowed, asked, or refused. The model cannot put a
        # URL on the named list; only the chat endpoint writes it.
        from core.egress import EgressDenied, get_gate
        from core.egress.gate import SearchReadGrant

        named = named_urls()
        grant = (
            SearchReadGrant.of([target], because="reading a page you named in your message")
            if target in named else None
        )
        fetch = self._fetch or (
            lambda u, g: get_gate().request(
                u,
                headers={"Accept": "text/html,application/xhtml+xml"},
                timeout=PAGE_TIMEOUT,
                source="web.read_page",
                grant=g,
            )
        )
        try:
            raw = fetch(target, grant)
        except EgressDenied as denied:
            return {
                "url": target,
                "refused": True,
                "error": (
                    f"Zaram did not open {target}: {denied}. The person can allow this "
                    "site in Settings or Activity, or name it in their message."
                ),
            }
        except urllib.error.HTTPError as http_error:
            return {"url": target, "error": f"the site answered {http_error.code}"}
        except Exception as exc:  # noqa: BLE001 - a failed fetch is an answer, not a crash
            logger.info("read_page could not fetch %s: %s", target, exc)
            return {"url": target, "error": f"could not load the page: {exc}"}

        html = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        text = extract_text(html, max_chars=MAX_CHARS)
        if not text:
            return {
                "url": target,
                "error": "the page loaded but had no readable text — it may need a browser to render",
            }
        result: Dict[str, Any] = {
            "url": target,
            "named_by_person": target in named,
            "chars": len(text),
            "truncated": len(text) >= MAX_CHARS,
            "text": text,
        }
        if question:
            result["question"] = question
        return result
