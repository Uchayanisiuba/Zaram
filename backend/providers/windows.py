"""The window a cloud model is known to have, as a lower bound, dated.

**Why this exists.** `core.context_budget.budget_for` measures a *local*
model's window — `/api/ps`, `/api/show`, a local server's own route — and
none of those can say anything about a model that runs on somebody else's
machine. Until 14 September 2026 a cloud model therefore fell through to the
Ollama default, 4,096, and a 128,000-token GLM was shown one exchange of the
conversation and told the user, every session, that it "cannot hold" more.
The same wrong number sized attached documents, so a contract that would
have fitted whole was excerpted to a thirtieth of it. Seen on screen by the
maintainer on `nvidia_nim:z-ai/glm-5.3-flash`.

**Three readings, most trustworthy first.** What the provider's own listing
says (OpenRouter's `context_length`, Groq's `context_window`) is recorded
on `ModelInfo.context_length` by the discoverer and wins. Where the listing
carries nothing — NVIDIA NIM's does not — this table answers from the model's
name. Where neither speaks, `budget_for` assumes `CLOUD_FALLBACK_CONTEXT_TOKENS`,
which is smaller than every model any catalogued provider serves today.

**Every figure here is a floor, never a ceiling, and that is what makes a
dated table safe to ship.** A budget sized under the real window costs some
conversation the model could have seen; one sized over it is a request the
provider refuses. So a family whose members differ (Gemma 3's 1B is 32K and
its 27B 128K) is entered at the smallest, and a family this file is not sure
of is left out rather than guessed — the fallback is the guess, and it is
labelled as one in the budget's `source`.

Same posture as `models.manifest.json`: knowledge with a date on it, never
fetched (rule 7g), and never allowed to decide anything a measurement can.
"""

from __future__ import annotations

from typing import Optional, Tuple

#: When the table below was last checked against the providers' own pages.
GENERATED = "2026-09-14"

#: What to assume for a cloud model nothing can size. 8,192 is the smallest
#: window any model on a catalogued provider serves (NIM's `gemma-2-9b-it`
#: and `llama3-8b-instruct`); Ollama's 4,096 default was the wrong number for
#: a machine Zaram does not run.
CLOUD_FALLBACK_CONTEXT_TOKENS = 8192

#: (substring of the lowercased model name, window). First match wins, so the
#: explicit size suffixes come first and the broad family names last.
_KNOWN: Tuple[Tuple[str, int], ...] = (
    # A window spelled in the name is the name's own claim.
    ("-4k", 4096),
    ("-8k", 8192),
    ("-16k", 16384),
    ("-32k", 32768),
    ("-64k", 65536),
    ("-128k", 131072),
    ("-256k", 262144),
    ("-1m", 1000000),
    # Families whose smallest member is known.
    ("gemma-2", 8192),
    ("gemma2", 8192),
    ("llama3-", 8192),  # Llama 3.0 — `llama3-8b-instruct`; the point releases are 128K
    ("llama-3.1", 131072),
    ("llama-3.2", 131072),
    ("llama-3.3", 131072),
    ("llama3.1", 131072),
    ("llama3.2", 131072),
    ("llama3.3", 131072),
    ("llama-4", 131072),
    ("nemotron", 131072),
    ("glm-4", 131072),
    ("glm-5", 131072),
    ("glm-z1", 131072),
    ("kimi-k2", 131072),
    ("deepseek", 65536),
    ("qwen3-coder", 131072),
    ("qwen2.5-coder", 32768),
    ("qwen2.5", 32768),
    ("qwen3", 32768),
    ("qwq", 32768),
    ("mixtral", 32768),
    ("mistral", 32768),
    ("magistral", 32768),
    ("devstral", 131072),
    ("codestral", 32768),
    ("gemma-3", 32768),
    ("gemma3", 32768),
    ("phi-4", 16384),
    ("gpt-oss", 131072),
    ("gpt-4o", 128000),
    ("gpt-4.1", 128000),
    ("gpt-4-turbo", 128000),
    ("gpt-5", 128000),
    ("claude", 200000),
    ("gemini", 131072),
    ("grok", 131072),
    ("command-a", 131072),
    ("command-r", 131072),
    ("minimax", 131072),
    ("sonar", 128000),
)


def bare_name(model_id: str) -> str:
    """The model's own name: after the provider prefix and the vendor slash,
    lowercased. ``nvidia_nim:z-ai/glm-5.3-flash`` → ``glm-5.3-flash``."""
    name = model_id.strip().lower()
    if ":" in name and not name.startswith("http"):
        # A provider prefix, unless it is Ollama's tag (`qwen2.5:14b`).
        head, _, tail = name.partition(":")
        if "/" in tail or not tail[:1].isdigit():
            name = tail
    return name.rsplit("/", 1)[-1]


def known_window(model_id: str) -> Optional[int]:
    """The window this model is known to have at least, or ``None``."""
    name = bare_name(model_id)
    if not name:
        return None
    for needle, window in _KNOWN:
        if needle in name:
            return window
    return None
