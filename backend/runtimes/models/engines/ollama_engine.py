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
        self.default_model = "gemma3:latest"
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

    def warm(self, model: str | None = None, *, timeout: float = 180.0) -> bool:
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

    def stream_response(self, prompt: str, system_prompt: str = "", model: str | None = None) -> Iterator[str]:
        """Stream plain text tokens, per `LLMEngine`.

        This used to yield SSE frames that `ModelsService` immediately parsed
        back into tokens — transport framing invented by the engine and undone
        one call up the stack. `stream_vision_response` below still speaks SSE
        because its caller in `main.py` reads the frames directly; collapsing
        that is a separate change to a separate endpoint.
        """
        url = f"{self.base_url}/api/generate"
        if "<image>" in prompt or "data:image" in prompt or "[IMAGE:" in prompt:
            yield ERROR_PREFIX + "Image input is not supported for text chat. Use /vision/analyze for image analysis, or remove the image and try again."
            return
        payload = {
            "model": self._wire(model or self.default_model),
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
        logger.debug("OllamaEngine.stream_response: model=%s prompt='%s...'", payload["model"], prompt[:50])
        try:
            response = requests.post(url, json=payload, stream=True, timeout=120)
            response.raise_for_status()
            token_count = 0
            for line in response.iter_lines():
                if line:
                    json_data = json.loads(line)
                    if "response" in json_data:
                        text = json_data["response"]
                        if "does not support image input" in text or "doesn't support image input" in text:
                            yield ERROR_PREFIX + "The selected model does not support image input. Switch to a vision-capable model (qwen2.5vl:7b) for image analysis, or remove the image and try again."
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

    def stream_vision_response(self, prompt: str, images: list[str], system_prompt: str = "") -> Iterator[str]:
        url = f"{self.base_url}/api/generate"
        clean_images = [img for img in (images or []) if img and img.strip()]
        if not clean_images:
            yield f"data: {json.dumps({'type': 'error', 'content': 'No valid image provided for vision analysis. Attach or capture an image before analyzing.'})}\n\n"
            yield "data: [DONE]\n\n"
            return
        payload = {
            "model": "qwen2.5vl:7b",
            "prompt": prompt,
            "images": clean_images,
            "system": system_prompt,
            "stream": True
        }
        print(f"[STAGE-9][Vision] OllamaEngine.stream_vision_response called: model=qwen2.5vl:7b, prompt='{prompt[:50]}...', images={len(clean_images)}")
        try:
            response = requests.post(url, json=payload, stream=True, timeout=120)
            response.raise_for_status()
            print(f"[STAGE-9][Vision] Ollama responded, streaming tokens...")
            token_count = 0
            accumulated = ""
            for line in response.iter_lines():
                if line:
                    json_data = json.loads(line)
                    if "response" in json_data:
                        text = json_data["response"]
                        accumulated += text
                        token_count += 1
                        if "does not support image input" in accumulated or "doesn't support image input" in accumulated or "Cannot read" in accumulated:
                            yield f"data: {json.dumps({'type': 'error', 'content': 'The vision model rejected the image input. Ensure the image is a valid PNG/JPEG and that the qwen2.5vl:7b model is pulled (run: ollama pull qwen2.5vl:7b).'})}\n\n"
                            yield "data: [DONE]\n\n"
                            return
                        yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"
                    if "done" in json_data and json_data["done"]:
                        yield "data: [DONE]\n\n"
                        break
                    if "error" in json_data:
                        yield f"data: {json.dumps({'type': 'error', 'content': json_data['error']})}\n\n"
                        yield "data: [DONE]\n\n"
                        break
            print(f"[STAGE-9][Vision] Done streaming. Total tokens: {token_count}")
        except Exception as e:
            print(f"[STAGE-9][Vision] Error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield "data: [DONE]\n\n"