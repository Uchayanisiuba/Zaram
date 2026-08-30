# backend/runtimes/models/engines/ollama_engine.py
import requests
import json
import logging
from collections.abc import Iterator
from typing import Callable, Optional
from .base_engine import ERROR_PREFIX, LLMEngine

logger = logging.getLogger(__name__)

#: How long Ollama holds the weights after a reply. See `stream_response`.
KEEP_ALIVE = "30m"

#: How long to wait for the socket. Loopback, so a slow one is a dead one.
CONNECT_TIMEOUT = 5.0

#: How long a request may go without a byte **once the weights are in memory**.
#: A model that has gone this quiet with everything already loaded is stuck,
#: not slow, and saying so is worth more than waiting longer.
IDLE_TIMEOUT = 120.0

#: The same wait, when the weights are *not* in memory yet.
#:
#: These were one number, and the number was measuring two different things.
#: Measured on this machine, 27 August 2026, `gemma4:26b-a4b-it-q4_K_M` —
#: 18.2 GB on disk against a 12 GB card, so Ollama put 9.3 GB on the GPU and
#: spilled the rest to system RAM:
#:
#:   * cold load, empty prompt, nothing generated: **109 s**
#:   * first token afterwards, on a five-word prompt: **28.8 s**
#:
#: 138 s of which the first 109 produced no bytes at all, against a 120 s read
#: timeout — so Ollama was loading correctly and Zaram hung up on it and
#: reported a read timeout. Exactly the failure already recorded for the
#: vision path below, which was patched with a second constant rather than by
#: separating the two questions, and so came back on the text path.
#:
#: **Ollama does not send response headers until the first token**, which is
#: what makes this a read timeout rather than a slow stream. Measured on the
#: same model: ``status=200`` and the first ``response`` chunk arrived in the
#: same 49.9 s, on a warm model with a five-word prompt. So `requests.post`
#: itself blocks for the whole load, and there is no earlier moment at which a
#: shorter budget could be applied.
#:
#: Ten minutes covers moving an oversized model off a slow disk. It is a
#: deliberate trade: for the request that pays it, a genuinely hung model is
#: not reported for ten minutes rather than two. That only applies while the
#: weights are still cold, which is the one case where a long silence is the
#: expected behaviour rather than a symptom.
COLD_START_TIMEOUT = 600.0

#: Given the id a model is catalogued under, return the name Ollama speaks.
#:
#: A callable rather than a `ProviderManager`, for the same reason
#: `CloudFanout` takes `ResolveCloud`: this module must not import `providers`,
#: and the mapping from an id to a provider-native name is knowledge that
#: belongs where the catalogue lives.
WireName = Callable[[str], str]


class OllamaEngine(LLMEngine):
    """Text generation against a local Ollama server.

    Every request carries `keep_alive`, and `warm()` loads the model without
    asking it to say anything — together they are why "Warming up" should be a
    once-per-session state rather than a once-per-message one.

    **The id a model is catalogued under is not the name Ollama answers to, and
    conflating them broke every model the user chose deliberately.** The
    provider layer records each discovered model as ``<provider_id>:<model>``,
    because two providers can offer the same name and the ids have to be
    distinct; Settings stores what the user picked, which is that id. This
    engine put whatever it was handed straight into the request body, so
    choosing a model sent ``ollama:qwen2.5-coder:1.5b`` to `/api/generate` and
    got back `400 Bad Request` — measured, against the bare name returning 200
    seconds later on the same server.

    `CloudFanout` already fixed this on the cloud side and the local side never
    learned it, which is the tell: the conversion belongs at the one place a
    name goes on the wire, on *both* paths, or the next engine repeats it.

    The resolution is a lookup, never a string operation. Stripping a leading
    ``ollama:`` by hand would be the same guess-from-the-name mistake
    `RoutedEngine` refuses for locality, and it would mangle a model whose own
    name carries a prefix — `qllama/bge-reranker-v2-m3:latest` is installed on
    this machine today. An id the catalogue cannot place passes through
    unchanged, because a hand-typed `qwen3` is a name Ollama resolves itself.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        wire_name: Optional[WireName] = None,
    ):
        self.base_url = base_url
        #: The model used when a caller names none. ``None`` is the only
        #: honest value, and it is assigned from outside by
        #: `ModelsRuntime.initialize` once the provider layer has picked one.
        #:
        #: **This was ``"gemma3:latest"``, and it was the fourth instance of a
        #: class this codebase had already fixed three times.** The identical
        #: note sits on `implementations/ollama_llm.py`, which was fixed while
        #: the engine actually on the chat path was not — so the literal
        #: survived where it did the most damage.
        #:
        #: It reaches a user because the assignment above it is guarded:
        #: ``if self._selected_model: engine.default_model = ...``. That guard
        #: is right — it must not overwrite a real pick with ``None`` — but it
        #: means a selection that yields *nothing* leaves whatever was here.
        #: Measured 30 August 2026 on a clean data dir: the first message of
        #: the session came back ``Ollama refused the request for
        #: gemma3:latest: model 'gemma3:latest' not found``, naming a model
        #: uninstalled months earlier that no control had ever offered.
        #:
        #: The branch is the one `CLAUDE.md` warns about by name — it runs
        #: "never with Ollama up, always on a stranger's machine" — because an
        #: empty candidate set is the ordinary outcome when every installed
        #: model is too large to select, which is exactly the first-run state
        #: this product is blocked on.
        #:
        #: Naming a different model here would repeat the mistake with a
        #: fresher name.
        self.default_model: Optional[str] = None
        self._wire_name = wire_name

    def _wire(self, model: Optional[str]) -> Optional[str]:
        """The name to put in the request body for `model`.

        Never raises. A resolver that fails must cost the request nothing more
        than the name it already had — the alternative is a lookup taking chat
        down, which is the failure this whole layer is arranged to avoid.
        """
        if not model or self._wire_name is None:
            return model
        try:
            resolved = self._wire_name(model)
        except Exception as exc:
            logger.debug("wire-name lookup failed for %r: %s", model, exc)
            return model
        return resolved or model

    def _is_resident(self, model: Optional[str]) -> Optional[bool]:
        """Whether Ollama already holds `model`'s weights. Never raises.

        Asked so the read timeout can be sized to what the request is actually
        waiting for — a load, or a token. `ProviderManager.swap_preflight`
        asks the same question for the orb's sake and cannot answer this one:
        this module must not import `providers`, and `/api/ps` is a loopback
        call to the server we are about to post to anyway.

        ``None`` means the question could not be answered — Ollama unreachable,
        or a reply we do not understand. It is not promoted to ``True``: a
        request that is about to fail for another reason must not also be
        given the short timeout, and guessing "already loaded" is the guess
        that produced the bug this exists to fix.
        """
        if not model:
            return None
        try:
            response = requests.get(f"{self.base_url}/api/ps", timeout=1.0)
            response.raise_for_status()
            loaded = response.json().get("models")
        except Exception as exc:
            logger.debug("residency check failed for %r: %s", model, exc)
            return None
        if not isinstance(loaded, list):
            return None
        # Ollama answers `/api/ps` with the name it resolved, which may carry a
        # `:latest` the request did not. Normalised rather than compared
        # directly, for the same reason `_same_model` is in the provider
        # layer: treating those as different models would put every reply on
        # the cold budget and give back the hang detection.
        #
        # Duplicated rather than imported, because this module must not depend
        # on `providers` — the constraint the whole `wire_name` callable exists
        # to satisfy. Narrower than that one on purpose: only Ollama's own
        # spellings reach here.
        #
        # **The tag is part of the name and must not be dropped.** Comparing
        # only up to the first colon would read a resident `gemma4:12b` as
        # covering a cold `gemma4:26b-a4b-it-q4_K_M` — the short budget handed
        # to the exact request that cannot meet it, which is this bug again by
        # a shorter route.
        def norm(name: str) -> str:
            name = (name or "").strip().lower()
            if name.startswith("ollama:"):
                name = name[len("ollama:"):]
            return name[: -len(":latest")] if name.endswith(":latest") else name

        wanted = norm(model)
        for entry in loaded:
            name = str((entry or {}).get("name") or (entry or {}).get("model") or "")
            if name and norm(name) == wanted:
                return True
        return False

    def _read_timeout(self, model: Optional[str], *, attached: bool) -> float:
        """How long this request may go without a byte.

        A vision request is treated as cold whatever `/api/ps` says. The
        projector loads separately from the weights and does not appear there,
        so a resident model answering its first question about an image is a
        cold start that reports as a warm one — measured at 158.9 s against a
        120 s timeout, 26 August 2026.
        """
        if attached:
            return COLD_START_TIMEOUT
        return IDLE_TIMEOUT if self._is_resident(model) is True else COLD_START_TIMEOUT

    def warm(self, model: str | None = None, *, timeout: float = COLD_START_TIMEOUT) -> bool:
        """Load the model into memory without generating anything.

        An empty prompt with `keep_alive` set is Ollama's documented way to
        preload: it resolves the model, pulls the weights into VRAM and returns
        without producing a token. So this costs the load it was always going to
        cost, moved from the user's first message to the seconds after launch
        when nobody is waiting.

        Loopback only, so it is not egress and rule 7g does not apply — this is
        a request to a process on the same machine, the same class as the
        readiness probe.

        Returns whether the model is now resident. Never raises: Ollama not
        running is the ordinary state on a machine that has not installed it,
        and the first-run screen already handles that. A failure here must cost
        a slower first reply and nothing else.
        """
        target = self._wire(model or self.default_model)
        if not target:
            return False
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": target, "prompt": "", "stream": False, "keep_alive": KEEP_ALIVE},
                timeout=timeout,
            )
            response.raise_for_status()
            logger.info("[OllamaEngine] %s is resident", target)
            return True
        except Exception as exc:
            logger.info("[OllamaEngine] could not preload %s: %s", target, exc)
            return False

    def read_structured(
        self, prompt: str, system_prompt: str = "", model: str | None = None
    ) -> str:
        """One JSON reply, sampled as little as Ollama allows.

        Extraction is a *reading* of text that already exists, not a
        composition, so everything that makes generation good makes this worse.
        Three settings, each earning its place:

        - ``format: "json"`` constrains decoding to syntactically valid JSON.
          Without it a small model wraps the object in prose or a code fence
          however firmly the prompt forbids it, and `_json_from` is left
          fishing for braces.
        - ``temperature: 0`` — there is no creativity wanted in "what was the
          rate", and sampling is what made this flaky rather than wrong.
          Measured: 7 of 8 installed models extracted an invoice correctly at
          temperature 0 in the suite, while the same model refused through the
          chat path, which samples.
        - ``stream: False`` because the caller wants the whole object and
          nothing can be done with half of one.

        Not part of `LLMEngine`. The protocol is about answering a person, and
        callers reach this through `getattr` so an engine without it degrades
        to ordinary generation rather than breaking.
        """
        chosen = model or self.default_model
        if not chosen:
            # Raised rather than posted. Extraction callers already treat an
            # exception as "no draft" and say what was missing, and asking
            # Ollama for `None` would produce a 404 that reads as the server
            # being unreachable — sending whoever debugs it to the wrong layer.
            raise RuntimeError(
                "No model was selected for this request. Choose one in Settings."
            )
        payload = {
            "model": self._wire(chosen),
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
            "keep_alive": KEEP_ALIVE,
        }
        # Not streaming, so this one number really is the whole wait — the
        # load and the reading of the document together. Sized to the load for
        # the same reason `stream_response` is: extraction is the path a
        # freshly-chosen model is most likely to meet cold.
        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=(CONNECT_TIMEOUT, COLD_START_TIMEOUT),
        )
        response.raise_for_status()
        return str(response.json().get("response", ""))

    def stream_response(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        images: list[str] | None = None,
    ) -> Iterator[str]:
        """Stream plain text tokens, per `LLMEngine`.

        This used to yield SSE frames that `ModelsService` immediately parsed
        back into tokens — transport framing invented by the engine and undone
        one call up the stack.

        ``images`` ride in the same `/api/generate` call as the prompt, on
        **whichever model was routed here**. Whether a model can see is decided
        before this point, by the gate in
        `ProviderManager.select_model_for_task`.

        There used to be a second one. `stream_vision_response` posted to the
        same Ollama against a hardcoded `qwen2.5vl:7b` — not installed on the
        machine it was written on — from `POST /vision/analyze`, and its own
        docstring said it bypassed routing and the egress gate. It was deleted
        on 28 August 2026 rather than repaired: a second entrance to inference
        that the egress log cannot see is rule 3, and there is no version of it
        that is better than the one path above.
        """
        url = f"{self.base_url}/api/generate"
        attached = [i for i in (images or []) if i and i.strip()]
        # An image *embedded in the prompt text* is refused rather than
        # read. A data URI in a prompt is not an attachment: nothing parsed
        # it, nothing sized it, and nothing logged it leaving. The refusal
        # used to point the user at `/vision/analyze`; that route is gone, so
        # it points at the paperclip, which is the only way in.
        if not attached and ("<image>" in prompt or "data:image" in prompt or "[IMAGE:" in prompt):
            yield ERROR_PREFIX + (
                "That looks like an image pasted into the message text. "
                "Attach it with the paperclip instead, so Zaram can read it "
                "and tell you what it did with it."
            )
            return
        chosen = model or self.default_model
        if not chosen:
            # Said plainly, and never guessed. A guessed name produces a 404
            # from Ollama that reads as "the local model is unreachable",
            # which is a claim about the server rather than about the caller
            # that passed nothing — the same sentence `ollama_llm` settled on.
            yield (
                f"{ERROR_PREFIX}No model was selected for this request. "
                "Choose one in Settings."
            )
            return
        payload = {
            "model": self._wire(chosen),
            "prompt": prompt,
            "system": system_prompt,
            "stream": True,
            # How long Ollama keeps the weights resident after answering.
            #
            # Nothing set this, so the default of **5 minutes** applied and the
            # model unloaded during any ordinary pause — reading a reply,
            # answering the door. The next message then paid a full cold start,
            # which is why "Warming up" appeared on almost every message rather
            # than once a session. The state was reported correctly; the model
            # really was loading again.
            #
            # 30 minutes rather than `-1` (forever). Zaram's whole VRAM argument
            # is that a chat model shares the card with the embedder and with
            # whatever else the user runs, and pinning weights indefinitely
            # would make a background app the reason a game or a render will not
            # start. Half an hour covers a working session; walking away still
            # gives the memory back.
            "keep_alive": KEEP_ALIVE,
        }
        # Only when there are some. Ollama reads the presence of the key as a
        # vision request on some builds, and a text-only model handed an empty
        # list answers oddly rather than failing, which is the worst of both.
        if attached:
            payload["images"] = attached
        logger.debug(
            "OllamaEngine.stream_response: model=%s images=%d prompt='%s...'",
            payload["model"],
            len(attached),
            prompt[:50],
        )
        try:
            # **The wait before the first token and the wait between tokens are
            # different questions, and one number was answering both.**
            #
            # `requests` applies a read timeout per socket read, so with
            # `stream=True` this is an *inter-byte* budget: once tokens flow at
            # an ordinary rate, a large value costs nothing. The only stretch it
            # actually buys is the silence before the first one — which for a
            # cold model is the load, and for a model that does not fit the card
            # is the load plus the spill to system RAM. See `COLD_START_TIMEOUT`
            # for what that measured.
            #
            # So the budget is chosen by whether the weights are already there,
            # not by whether an image is attached. The image case is a cold
            # start too — of the projector — which is why it kept needing a
            # constant of its own.
            timeout = (CONNECT_TIMEOUT, self._read_timeout(payload["model"], attached=bool(attached)))
            response = requests.post(url, json=payload, stream=True, timeout=timeout)
            response.raise_for_status()
            token_count = 0
            for line in response.iter_lines():
                if line:
                    json_data = json.loads(line)
                    if "response" in json_data:
                        text = json_data["response"]
                        if "does not support image input" in text or "doesn't support image input" in text:
                            # Names no model, deliberately. This read
                            # "(qwen2.5vl:7b)" and pointed at something the
                            # user did not have — advice naming a model nobody
                            # installed is worse than advice naming none, and
                            # `CLAUDE.md` keeps model filenames out of the
                            # primary path in any case.
                            #
                            # `implementations/ollama_llm.py` carries the same
                            # sentence and was fixed on 19 August 2026. This
                            # copy was missed, which is what two copies of one
                            # message are for. What is vision-capable here is a
                            # question the provider layer answers, through
                            # `select_model_for_task(requires_vision=True)`,
                            # and this engine cannot.
                            yield ERROR_PREFIX + "The selected model does not support image input. Switch to a vision-capable model for image analysis, or remove the image and try again."
                            return
                        token_count += 1
                        yield text
                    if "done" in json_data and json_data["done"]:
                        break
                    if "error" in json_data:
                        yield ERROR_PREFIX + str(json_data["error"])
                        break
            logger.debug("OllamaEngine.stream_response: done, %d tokens", token_count)
        except Exception as e:
            logger.warning("OllamaEngine.stream_response failed: %s: %s", type(e).__name__, e)
            yield ERROR_PREFIX + self._explain(e, payload["model"])

    @staticmethod
    def _explain(exc: Exception, model: Optional[str]) -> str:
        """What went wrong, in terms that name the model and Ollama's reason.

        `requests` renders a refusal as "400 Client Error: Bad Request for url:
        http://127.0.0.1:11434/api/generate", which names neither the model nor
        the cause — the user sees a URL and an HTTP code for what is usually
        "that model is not installed" or "this model cannot generate text".
        Ollama itself says which in the response body, and it was being thrown
        away.

        The body is quoted rather than translated. Guessing at a friendlier
        phrasing would mean inventing a diagnosis for a failure this layer did
        not make, and the honest sentence is the server's own.
        """
        detail = ""
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                body = response.json()
                detail = str(body.get("error") or "").strip()
            except Exception:
                detail = (getattr(response, "text", "") or "").strip()[:300]

        named = model or "the selected model"
        if detail:
            return f"Ollama refused the request for {named}: {detail}"
        return f"Ollama could not answer with {named}: {exc}"

