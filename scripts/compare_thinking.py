"""Does thinking help when the request is a page? Measure it.

Written 5 October 2026. The maintainer's resident 27B wrote a game with twenty-
three missing `++` while the composer said *Thinking off*, and the guess was that
thinking might have caught it. A guess is not a default: the same model once
spent 870 seconds thinking about a bouncing ball. This asks the question the
only way that answers it -- the same request, several times each, thinking on
and thinking off, through Zaram's own chat route (so the guidance, the model and
the settings are the product's) -- and runs every page it gets back through the
same check the product runs (`core/page_check.py`).

It prints, per mode: how many pages started cleanly, how long a reply took, and
how much of that was thinking. Nothing is changed and nothing is stored.

Run it when the GPU is free -- thinking runs take minutes and this makes
`runs x 2` of them::

    set ZARAM_API_SECRET=<the secret Zaram is running with>
    backend\\venv\\Scripts\\python scripts\\compare_thinking.py --runs 3

It lives in `scripts/`, not `backend/`, because the installer ships every `.py`
under `backend/` and a measuring tool is not part of the product.

The default request names no library, because the check runs offline and a page
that wants three.js cannot be judged here; pass `--prompt` for another.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# The backend's own modules (`core.page_check`), run from the repository.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

DEFAULT_PROMPT = (
    "Make a snake game in one HTML file. Canvas, arrow keys, score, game over screen. "
    "No libraries."
)


def read_stream(lines: Iterable[bytes | str]) -> Dict[str, Any]:
    """Fold a chat NDJSON stream into the reply, the thinking, and its errors."""
    reply: List[str] = []
    reasoning = 0
    errors: List[str] = []
    for raw in lines:
        text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
        text = text.strip()
        if not text:
            continue
        try:
            event = json.loads(text)
        except ValueError:
            continue
        kind = event.get("type")
        data = event.get("data") or {}
        if kind == "token":
            reply.append(str(data.get("content", "")))
        elif kind == "reasoning":
            reasoning += len(str(data.get("content", "")))
        elif kind == "error":
            errors.append(str(data.get("message") or data.get("content") or data))
    return {"reply": "".join(reply), "reasoning_chars": reasoning, "errors": errors}


def first_page(reply: str) -> Optional[str]:
    """The first ```html block in a reply, or `None`."""
    match = re.search(r"```[ \t]*html[^\n]*\n([\s\S]*?)(?:```|$)", reply, re.IGNORECASE)
    return match.group(1) if match and match.group(1).strip() else None


def summarise(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """One mode's rows reduced to the numbers worth comparing."""
    ran = [r for r in rows if r.get("checked")]
    return {
        "runs": len(rows),
        "wrote_a_page": sum(1 for r in rows if r.get("page")),
        "checked": len(ran),
        "clean": sum(1 for r in ran if r.get("ok")),
        "hung": sum(1 for r in ran if r.get("hung")),
        "median_seconds": round(statistics.median([r["seconds"] for r in rows]), 1) if rows else None,
        "median_thinking_chars": int(statistics.median([r["reasoning_chars"] for r in rows])) if rows else None,
    }


def ask(base: str, secret: str, prompt: str, thinking: bool, model: str, timeout: float) -> Dict[str, Any]:
    body = json.dumps(
        {"text": prompt, "thinking": thinking, "session_id": f"compare-{uuid.uuid4().hex[:8]}", "model": model}
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/chat",
        data=body,
        headers={"Content-Type": "application/json", "X-Zaram-Auth": secret},
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        folded = read_stream(response)
    folded["seconds"] = time.monotonic() - started
    return folded


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs", type=int, default=3, help="requests per mode")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--model", default="", help="a model id, or empty for Zaram's choice")
    parser.add_argument("--url", default="http://127.0.0.1:8420")
    parser.add_argument("--timeout", type=float, default=1800.0, help="seconds per request")
    args = parser.parse_args(argv)

    secret = os.environ.get("ZARAM_API_SECRET", "")
    if not secret:
        print("Set ZARAM_API_SECRET to the secret Zaram is running with.", file=sys.stderr)
        return 2

    from core.page_check import check_page

    results: Dict[str, List[Dict[str, Any]]] = {"thinking on": [], "thinking off": []}
    # Interleaved, so a model that warms up or a GPU that heats does not
    # favour whichever mode happened to go second.
    for n in range(args.runs):
        for label, flag in (("thinking on", True), ("thinking off", False)):
            print(f"[{n + 1}/{args.runs}] {label} ...", flush=True)
            row = ask(args.url, secret, args.prompt, flag, args.model, args.timeout)
            page = first_page(row["reply"])
            row["page"] = page is not None
            if page is not None:
                verdict = check_page(page)
                row.update(checked=verdict.checked, ok=verdict.ok, hung=verdict.hung, problems=verdict.problems())
            outcome = "no page" if page is None else ("clean" if row.get("ok") else "FAILED " + "; ".join(row.get("problems", []))[:120])
            print(f"    {row['seconds']:.0f}s, thinking {row['reasoning_chars']} chars, {outcome}", flush=True)
            results[label].append(row)

    print()
    for label, rows in results.items():
        print(label, json.dumps(summarise(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
