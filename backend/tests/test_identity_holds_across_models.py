"""Every installed model gives the same account of what Zaram is.

`identity_preamble` is pure and `test_identity.py` asserts what it *says*. That
is not the same claim as *it works*, and the gap is where this product keeps
getting hurt: the preamble was correct, reached the model, and a 1.5B model
still answered "I am Zaram, a language model created by Alibaba Cloud" — taking
the name and keeping its training's account of who made it.

A prompt is only as good as the weakest model it is given to, and Zaram's whole
argument is that the model underneath changes. So the property has to be
measured against the models actually installed, not asserted against a string.

**Off by default, and that is not squeamishness.** Running it loads every chat
model on the machine in turn, evicting whatever is resident — minutes, and
several gigabytes moved across the bus. A suite that does that is a suite
nobody runs. Enable deliberately::

    $env:ZARAM_LIVE_MODELS='1'; .venv\\Scripts\\python.exe -m pytest \\
        backend/tests/test_identity_holds_across_models.py -v

It is a test rather than a scratch script because a probe that lives in a
scratchpad is a probe that runs once and is never run again — and this one has
to be re-run every time the preamble is touched.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

import pytest

from core.identity import LOCAL, identity_preamble

OLLAMA = "http://127.0.0.1:11434"

#: Labs whose name a model may recite as its own maker. The failure is not
#: mentioning them — a truthful "the model answering is Qwen, trained by
#: Alibaba" is exactly what routing legibility asks for — it is claiming they
#: made *Zaram*, so the assertion below is about the sentence, not the word.
_LABS = [
    "alibaba",
    "anthropic",
    "deepseek",
    "google",
    "meta",
    "microsoft",
    "mistral",
    "openai",
]

#: "created by Alibaba Cloud", "made by OpenAI", "developed by Google", and the
#: same three with an intervening word or two, which is how models phrase it.
_MAKER_CLAIM = re.compile(
    r"\b(created|made|developed|built|trained)\s+by\s+(\w+\s+){0,2}(" + "|".join(_LABS) + r")",
    re.IGNORECASE,
)

#: The other half of the measured failure: accepting "language model" as what
#: Zaram is. Only in the first person — a reply explaining that Zaram is not a
#: language model has to be able to use the phrase.
_SELF_AS_MODEL = re.compile(
    r"\bI(?:'m| am)\s+(a|an)\s+(large\s+|small\s+)?(language|ai)\s+model", re.IGNORECASE
)


def _installed_chat_models() -> list[str]:
    """Whatever this machine has, discovered at collection time.

    Nothing is hardcoded and no model is named: the property has to hold for
    the models the *user* installed, and a fixed list would quietly stop
    covering anything pulled after it was written.
    """
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=2) as response:
            payload = json.loads(response.read())
    except (urllib.error.URLError, OSError, ValueError):
        return []

    names = [m.get("name", "") for m in payload.get("models", [])]
    # Embedders and rerankers cannot hold a conversation, and asking one to
    # produces a 400 that says nothing about identity.
    return [n for n in names if n and "embed" not in n and "bge" not in n]


#: A question with no identity content, whose answer establishes only whether
#: this model can follow a plain instruction at all.
_CONTROL = "Reply with the single word: ok"


def _skip_unless_it_can_converse(model: str) -> None:
    """Skip models that cannot answer anything, with the evidence in the reason.

    `moondream` answers "Who are you?" with ``'urn'``. It is a 1.8B
    image-captioning model and no prompt makes it converse, so an identity
    assertion against it measures the model's competence rather than Zaram's
    prompt — and a permanently red test is a permanent invitation to stop
    reading the file.

    **Derived, never named.** The first version listed `moondream` by name,
    which made the suite a description of one machine: a model the user pulls
    tomorrow gets no such judgement, and the exclusion would silently stop
    matching if the tag changed. Ollama's own capability report cannot
    substitute — it says ``completion, vision`` for both `moondream` and
    `qwen2.5vl:7b`, and only one of those can hold a conversation, so the
    distinction is about quality and quality has to be measured.

    A control question is the honest instrument: it contains no identity
    content, so failing it says nothing about the preamble, and passing it
    earns the model a real assertion. A capable model wrongly skipped here is
    visible as a skip rather than as a pass, which is the safe direction.
    """
    try:
        answer = _ask(model, _CONTROL, "")
    except Exception as exc:  # a model that will not run cannot be measured
        pytest.skip(f"{model} could not be reached: {exc}")

    if "ok" not in answer.lower():
        pytest.skip(
            f"{model} cannot follow a plain instruction — asked {_CONTROL!r} it "
            f"answered {answer.strip()[:80]!r}. Identity is not measurable here, "
            f"and this model should probably not be offered as a chat model."
        )


#: Model families a reply might name. Used to catch a model answering the
#: identity question from its training rather than from what it was told.
_FAMILIES = ["llama", "qwen", "gemma", "gpt", "claude", "mistral", "deepseek", "phi"]


def _family(model: str) -> str:
    """`qwen2.5-coder:1.5b` → `qwen`. The name a model would call itself."""
    stem = model.split(":")[0].split("/")[-1]
    match = re.match(r"[a-z]+", stem, re.IGNORECASE)
    return match.group(0).lower() if match else stem.lower()


def _ask(model: str, question: str, system: str) -> str:
    body = json.dumps(
        {
            "model": model,
            "prompt": question,
            "system": system,
            "stream": False,
            "keep_alive": "30s",
        }
    ).encode()
    request = urllib.request.Request(
        f"{OLLAMA}/api/generate", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read()).get("response", "")


live_only = pytest.mark.skipif(
    os.environ.get("ZARAM_LIVE_MODELS") != "1",
    reason="loads every installed model; set ZARAM_LIVE_MODELS=1 to run",
)


@live_only
@pytest.mark.parametrize("model", _installed_chat_models() or ["none-installed"])
def test_the_model_does_not_hand_zaram_to_its_own_trainer(model: str):
    if model == "none-installed":
        pytest.skip("no Ollama chat models installed")
    _skip_unless_it_can_converse(model)

    answer = _ask(model, "Who are you?", identity_preamble(model=model, locality=LOCAL))

    assert "zaram" in answer.lower(), f"{model} did not identify as Zaram: {answer!r}"

    claim = _MAKER_CLAIM.search(answer)
    assert claim is None, f"{model} credited Zaram to {claim.group(0)!r}: {answer!r}"

    self_model = _SELF_AS_MODEL.search(answer)
    assert self_model is None, f"{model} called itself a language model: {answer!r}"


@live_only
@pytest.mark.parametrize("model", _installed_chat_models() or ["none-installed"])
def test_the_model_never_names_a_different_model(model: str):
    """Naming *itself* is the goal; naming *another* is the defect.

    The first version of this asserted the model must name itself, and
    `qwen2.5-coder:1.5b` failed it by declining: *"I cannot say which specific
    model is currently answering you."* That is a weak answer and it is not a
    false one, and the assertion was measuring capability rather than the
    contract.

    The contract is `identity.py`'s: do not answer this from training. A model
    that declines has obeyed it. A model that says "I am Qwen, made by
    Alibaba" while deployed as something else has not — that is the failure the
    whole module exists for, and it is what this catches.

    **Naming the model is guaranteed elsewhere, by construction rather than by
    prompt.** `StreamEvent.answering` carries it on every reply from what
    routing resolved, so `CLAUDE.md`'s "every reply names the model that
    answered" does not depend on a 1.5B model choosing to cooperate. Asking the
    prose to carry it too would make a hard requirement out of the least
    reliable path.
    """
    if model == "none-installed":
        pytest.skip("no Ollama chat models installed")
    _skip_unless_it_can_converse(model)

    answer = _ask(
        model,
        "Which model is answering right now?",
        identity_preamble(model=model, locality=LOCAL),
    )

    mine = _family(model)
    foreign = [f for f in _FAMILIES if f != mine and re.search(rf"\b{f}", answer, re.I)]

    assert not foreign, f"{model} named {foreign} as the answering model: {answer!r}"
