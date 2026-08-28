# backend/main.py
import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# --- KERNEL IMPORTS (Strict Boundary) ---
from core.bootstrapper import KernelBootstrapper
from core.chat_router import ChatRouter
from core.identity import compose_system_prompt, identity_preamble
# `SEARCH_MARKER` was imported here for `_format_search_results`, which has
# moved to `core/search_context.py` — the engine is its only consumer and the
# kernel boundary runs one way. It had a latent `NameError` before that, which
# only stayed latent because web search was off by default.
# Per-request, and set before the planner runs. See the call site in `chat`.
from core.planner import set_search_locality

# --- LEGACY IMPORTS (Isolated for Fallback) ---
from implementations.ollama_llm import OllamaLLM
from runtimes.memory.maintenance import SpineMaintenance
# One spelling of `project:<id>`, from the module that owns it. A scope string
# built by hand at a call site is rule 7i's privacy boundary written twice.
from runtimes.memory.contracts import project_scope
from services.conversation_manager import ConversationManager

# Which voice speaks by default, imported rather than spelled. `voice/config.py`
# owns the answer and carries the reasoning; six copies of the literal is what
# this replaces. Nothing heavy loads with it — the module is stdlib only, and
# Kokoro itself is still behind the optional extra.
from voice.config import DEFAULT_VOICE

#: The preset every request carries when the user has chosen none.
#:
#: Named so `_resolve_voice` can tell "the user picked this tone" from "nobody
#: picked anything", which is the distinction that decides whether a preset's
#: voice outranks the user's own setting.
DEFAULT_PERSONA = "zaram_prime"

print("Starting Zaram Backend...")
app = FastAPI()

# --------------------------------------------------------------------------- #
# Who may talk to this process.
#
# Binding to 127.0.0.1 stopped the API being published to the café network,
# which was the loud hole. **It does not stop a web page.** A site the user
# visits can point a hostname it controls at 127.0.0.1 and then reach port 8420
# with ordinary *same-origin* requests — DNS rebinding — and CORS is no defence
# because the browser considers those requests same-origin. From there,
# `GET /memory` is the entire Spine, `GET /egress` is every question ever asked,
# and `PUT /egress/policy` sets a destination to `allow`.
#
# The check is the `Host` header: a rebinding request carries the attacker's
# hostname, because that is what the browser was told to fetch. A real local
# client carries `127.0.0.1` or `localhost`. That one comparison closes the
# browser-borne half of the problem for the cost of a middleware.
#
# **The other half is `RequireApiSecret`, below.** This paragraph used to end
# "any process on this machine can still call the API, because there is no
# authentication anywhere ... until that exists, this middleware is the honest
# improvement rather than the complete one" — sitting four lines above the
# import of the module that closed it. Loopback is a network boundary, not an
# identity one, and a per-launch secret is what makes it an identity one: the
# desktop host mints 32 bytes at boot, hands them to this process in the spawn
# environment and to the renderer over IPC, and `core/api_secret.py` documents
# the development file fallback as weaker rather than glossing it.
#
# Left stale, a comment like that is the README defect this repository has
# already recorded once — the product understating itself, in the one direction
# where a reader acts on it. `X-Zaram-Client` is unchanged and is still a label
# enforced by nothing; `X-Zaram-Auth` is the credential.
# --------------------------------------------------------------------------- #
from fastapi.middleware.trustedhost import TrustedHostMiddleware  # noqa: E402
from core.api_secret import (  # noqa: E402
    HEADER as AUTH_HEADER,
    ensure_resolved as _resolve_api_secret,
    matches as _secret_matches,
)

# At import, not on first use. `matches()` never resolves the credential for a
# request that carries none, so a backend that only ever sees unauthenticated
# requests would never write the file the dev server reads — and could never
# then be authenticated against. See `ensure_resolved`.
_resolve_api_secret()


class RequireApiSecret:
    """The other half: who this process will talk to, not merely from where.

    The `Host` guard above closes the browser-borne route. It does nothing
    about a *process*, and there was no authentication of any kind — so
    anything running as this user could read the whole Spine, the whole egress
    log, or set a destination to allow. That is the half that was left open,
    and this is it.

    **Plain ASGI, not `BaseHTTPMiddleware`.** The decorator form wraps the
    response body, and `/chat` streams NDJSON token by token — the entire point
    of it being NDJSON. A middleware that buffers would hold every reply until
    the model finished and turn the product's most visible behaviour into a
    long pause. Nothing here touches the body.

    **Innermost, deliberately.** Middlewares added later run further out, so
    declaring this before `TrustedHostMiddleware` and CORS puts it last in the
    chain. Both orderings matter: a rebound host must still be refused with 400
    by the host guard rather than 401 by this, since the reason it was refused
    is the more useful thing to say; and a CORS preflight must be answered by
    `CORSMiddleware` before reaching here, because a browser cannot put a
    custom header on an `OPTIONS` preflight and this would reject every
    cross-origin request the product itself makes.

    **Nothing is exempt, including `/health`.** It was tempting to leave it
    open so the desktop host can poll for readiness without a credential, but
    it reports capabilities, configured providers, model names and speech
    state — a description of the user's setup, which is information. The host
    mints the secret, so it can present it, and default-deny is the rule.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        presented = None
        wanted = AUTH_HEADER.lower().encode()
        for name, value in scope.get("headers") or []:
            if name.lower() == wanted:
                presented = value.decode("latin-1")
                break

        if not _secret_matches(presented):
            body = (
                b'{"detail":"Zaram\'s API requires the credential this machine\'s '
                b'Zaram was started with. Loopback is a network boundary, not an '
                b'identity one."}'
            )
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)


app.add_middleware(RequireApiSecret)

#: `testserver` is what Starlette's TestClient sends. Included so the guard is
#: exercised by the suite rather than switched off in it — a check the tests
#: bypass is a check nobody runs.
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver", "127.0.0.1:8420", "localhost:8420"]

app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The provider layer's HTTP surface: which models exist, what hardware was
# found, and which cloud provider Zaram may call.
#
# **This line is the whole bug.** The router has existed, with tests, since the
# provider layer landed, and was never included here — so `/providers/models`,
# `/providers/hardware` and the rest answered 404 on the running product while
# `providers/tests/test_api.py` passed, because it builds its own app and
# mounts the router itself. Every route below is asserted against *this* object
# in `tests/test_routes_are_mounted.py`, which is the only place the claim can
# be true.
from core.context_budget import budget_for  # noqa: E402
from providers.api import router as providers_router  # noqa: E402

app.include_router(providers_router)

# The session store, per rule 7d's *"session state and long-term memory are
# separate stores"* -- the half that was never built. Mounted here and asserted
# in `tests/test_routes_are_mounted.py`, which is the only place the claim that
# these routes are reachable can be true.
from conversations import ConversationRecords, default_db_path as conversations_db_path  # noqa: E402
from conversations.api import router as conversations_router, set_records  # noqa: E402

set_records(ConversationRecords(conversations_db_path()))
app.include_router(conversations_router)

# --- KERNEL LIFECYCLE ---
kernel = KernelBootstrapper()
chat_router = None
spine_maintenance = None


@app.on_event("startup")
async def startup_event():
    global chat_router, spine_maintenance

    print("[Startup] Booting Zaram Kernel...")
    await kernel.boot()

    # The provider routes answer 503 until this runs, which is deliberate: an
    # empty model list during boot is indistinguishable from a machine with no
    # models, and the first-run screen acts on that difference.
    from providers.api import set_providers_runtime

    providers_runtime = getattr(kernel, "providers_runtime", None)
    if providers_runtime is not None:
        set_providers_runtime(providers_runtime)

    # Speech Runtime is now initialized via KernelBootstrapper
    speech_runtime = kernel.speech_runtime
    print("[Startup] Speech Runtime initialized via Kernel.")

    # Initialize the Chat Router with the new engine and the legacy fallback
    def legacy_gen(req_text: str, model: str, system_prompt: str = "", persona: str = "zaram_prime"):
        from core.streaming_events import StreamEvent, EventType
        llm = OllamaLLM()
        cm = ConversationManager(llm, kernel.event_bus, persona=persona)
        for event in cm.run_conversation(req_text, model, system_prompt):
            if isinstance(event, dict):
                etype = event.get("type")
                if etype == "token":
                    yield StreamEvent.token(event.get("content", "")).to_ipc() + "\n"
                elif etype == "error":
                    yield StreamEvent.error(event.get("content", "")).to_ipc() + "\n"
                elif etype == "llm_done":
                    yield StreamEvent.status("complete").to_ipc() + "\n"
                elif etype == "done":
                    pass
            elif isinstance(event, str):
                yield StreamEvent.token(event).to_ipc() + "\n"
        yield StreamEvent.done().to_ipc() + "\n"

    chat_router = ChatRouter(kernel.execution_engine, kernel.event_bus, legacy_gen)

    # Ingest can now reach the Spine, and the engine can say what it could not
    # read. `core/` keeps no import of `ingest/`; the dependency points inward
    # from here, which is what lets the engine be tested without either.
    ingest_service.attach_memory(kernel.memory_runtime)
    kernel.execution_engine.set_notice_source(ingest_service.notice_text)

    # Rule 7e stops being a document here. The decay rules and the promotion
    # evidence were written, tested and never once invoked by anything running
    # — see `runtimes/memory/maintenance.py` for why the schedule is "shortly
    # after boot, then daily" rather than a shorter interval.
    if kernel.memory_runtime is not None:
        spine_maintenance = SpineMaintenance(kernel.memory_runtime, kernel.event_bus)
        spine_maintenance.start()

    # Preload the local model, in the background, so the first message does not
    # pay for it. Fire-and-forget on purpose: the backend must answer /health
    # and /readiness while several gigabytes move onto the card, or the first
    # run screen sits on a spinner deciding the product is broken.
    async def _warm():
        try:
            runtime = kernel.registry.get_runtime("models")
            await runtime.warm_local_model()
        except Exception:
            # A preload is an optimisation. Never let it stop the app starting.
            pass

    asyncio.create_task(_warm())

    print("[Startup] Chat Router initialized. Kernel Online.")


@app.on_event("shutdown")
async def shutdown_event():
    print("[Shutdown] Powering down Zaram Kernel...")

    # First, and before anything that awaits. A thread parked inside the egress
    # gate is waiting on an event only a browser can set, and a browser that is
    # closing is not going to. Releasing them as denied is both the correct
    # answer while shutting down and the reason the process can exit at all.
    from core.egress import get_pending

    released = get_pending().cancel_all()
    if released:
        print(f"[Shutdown] Denied {released} unanswered egress confirmation(s).")

    if spine_maintenance is not None:
        await spine_maintenance.stop()
    # No-op unless somebody actually used the microphone this session; the
    # recogniser is built on first use, not at boot.
    from voice.stt.service import shutdown_recogniser
    await shutdown_recogniser()
    await kernel.shutdown()


def _stream_error(message: str):
    from core.streaming_events import StreamEvent
    async def _gen():
        yield StreamEvent.error(message).to_ipc() + "\n"
        yield StreamEvent.done().to_ipc() + "\n"
    return _gen()


# --- REQUEST MODELS ---
@dataclass(frozen=True)
class _ModelChoice:
    """Which model answers this message, and what decided that.

    One object rather than two functions, because the two used to be
    `_resolve_model` and `_who_chose` and each re-derived the other's
    precedence from scratch. That is the failure `_answering_event`'s docstring
    warns about, one level up: if they ever disagreed, the reply named a source
    that had not decided. They cannot disagree now.
    """

    model: str | None
    chosen_by: str


def _task_requirements(prompt: str) -> tuple[bool, str | None]:
    """``(requires_vision, specialisation)`` for ``prompt``, or nothing known.

    Asks the kernel's own planner, so this classifies by the same wired
    semantic router the plan will use. A fresh `IntentRouter` built here would
    have no router attached, fall back to keywords, and could route the message
    to one intent while the plan routed it to another.

    Every failure returns "nothing known", which selects exactly the behaviour
    that existed before this function: Zaram's untasked default. Classification
    decides *which* model answers and must never decide *whether* one does.
    """
    if not (prompt or "").strip():
        return False, None
    try:
        from core.planner import INTENT_SPECIALISATION

        classification = kernel.execution_engine.classify(prompt)
        return (
            bool(classification.requires_vision),
            INTENT_SPECIALISATION.get(classification.intent_type),
        )
    except Exception:
        logging.getLogger(__name__).debug(
            "Task classification unavailable; using the untasked default"
        )
        return False, None


def _task_model(requires_vision: bool, specialisation: str | None) -> str | None:
    """The provider layer's pick for a request with these requirements.

    Returns the **display name** — the provider-native one — because that is
    what `ModelsRuntime._choose_model` returns and what the chat path speaks.
    Returning the catalogue id here would send ``ollama:qwen2.5-coder:14b`` to
    `/api/generate`, which is a 400 this repository has already paid for once.
    """
    manager = getattr(getattr(kernel, "providers_runtime", None), "manager", None)
    if manager is None:
        return None
    try:
        model = manager.select_model_for_task(
            requires_vision=requires_vision, specialisation=specialisation
        )
    except Exception:
        logging.getLogger(__name__).debug(
            "Task-aware selection failed; using the untasked default"
        )
        return None
    return model.display_name if model is not None else None


def _resolve_model(
    requested: str | None, prompt: str = "", has_images: bool = False
) -> _ModelChoice:
    """Which model answers: the request, then Settings, then Zaram's own pick.

    ``model=None`` is a real answer and the best one when nobody has chosen and
    the task says nothing — it means "use the engine default", which is the
    provider layer's vetted selection with the residency and data-policy gates
    already applied. Substituting a hardcoded name here would defeat both,
    which is exactly what the frontend's ``gemma3:latest`` did from the other
    end.

    **The task decides only in the branch where nobody else did.** An explicit
    choice — this message, or Settings — is returned untouched even when the
    question looks like one another model would serve better. Overriding a
    person's stated preference because a classifier disagreed is a product that
    argues with its user, and the classifier is a similarity judgement rather
    than a fact.

    That leaves one case this deliberately does *not* handle yet: a chosen
    model that cannot see, asked to read an image. It is not reachable today —
    `ChatRequest` carries no image, so `requires_vision` is inferred from
    wording alone, and re-routing off the word "screenshot" would be worse than
    the gap. When image input lands, that becomes a refusal rather than a
    silent substitution, because answering blind is rule 9's failure.
    """
    named = (requested or "").strip()
    if named:
        return _ModelChoice(named, "request")

    try:
        from core.user_settings import get_user_settings

        settings_default = get_user_settings().default_model
    except Exception:
        # A preference file must never be able to stop chat working.
        settings_default = None

    if settings_default:
        return _ModelChoice(settings_default, "settings")

    requires_vision, specialisation = _task_requirements(prompt)
    # An attached image is not a guess. Wording-based inference stays for the
    # case where someone describes a picture they have not attached, but a
    # file that is actually here outranks it and can only ever add the
    # requirement, never remove one the classifier found.
    requires_vision = requires_vision or has_images

    # Nothing known about the task is not the same as a task with no
    # preference: only the second is worth a round trip through the provider
    # layer, and only it may report itself as a routing decision. Without this
    # guard every ordinary message would claim to have been routed.
    if requires_vision or specialisation is not None:
        routed = _task_model(requires_vision, specialisation)

        # **Only a pick that differs from the untasked one is a routing
        # decision.** On a machine with one general model installed, a coding
        # question resolves to that same model — nothing was routed, and
        # reporting `task` there would put "matched to this question" under a
        # reply that would have been identical either way. That is a rendered
        # value nobody measured, which the UI principles forbid, and it is the
        # more dangerous kind because it is true often enough to look right.
        if routed is not None and routed != _task_model(False, None):
            return _ModelChoice(routed, "task")

    return _ModelChoice(None, "zaram")


def _conversation_store():
    """The session store, or ``None`` if it could not be reached.

    Every caller below degrades to "the exchange is not recorded" rather than
    failing the reply. A transcript is bookkeeping; an answer is the product,
    and a bookkeeping fault must never cost the user their answer.
    """
    try:
        from conversations.api import _RECORDS

        return _RECORDS
    except Exception:  # pragma: no cover - import guard
        return None


def _open_conversation(request: "ChatRequest") -> tuple[str, bool]:
    """The transcript for this exchange, and whether it was just started.

    Records the user's message immediately, before any generation. A question
    that produced an error is still a question they asked, and losing it
    because the model failed is exactly the amnesia this store exists to end.

    Returns ``("", False)`` when the store is unavailable, which every caller
    treats as "do not record" rather than as an error.
    """
    records = _conversation_store()
    if records is None:
        return "", False

    from conversations import USER, UnknownConversation

    conversation_id = (request.conversation_id or "").strip()
    started = False
    try:
        if conversation_id:
            # A named conversation that does not exist is not silently
            # replaced. Opening a new one under a different id would leave the
            # client writing into a transcript it cannot find again.
            records.get(conversation_id)
        else:
            conversation_id = records.start(project_id=request.project_id or "").id
            started = True
        records.append(conversation_id, USER, request.text)
    except UnknownConversation:
        logging.getLogger(__name__).info(
            "Chat: conversation %s is not in the store; this exchange is not recorded",
            conversation_id,
        )
        return "", False
    except Exception as exc:
        logging.getLogger(__name__).warning("Chat: could not record the question: %s", exc)
        return "", False

    return conversation_id, started


def _seed_turns_from_transcript(
    conversation_id: str, session_id: str, budget
) -> None:
    """Give a resumed conversation the turns it had before the restart.

    **The engine's turn buffer is in-process and dies with it.** That is rule
    7d's ephemeral half and it is correct — false starts must not reach the
    Spine — but until transcripts were stored it also meant reopening a
    conversation handed the model nothing, so "write that up as a proposal"
    resolved against an empty buffer. Rule 9's referential failure, arriving
    after a restart instead of on a first message.

    Fitted to the *answering* model's real window rather than sent whole. A
    local model is loaded with 4,096 tokens and a cloud one has far more, so
    the same transcript has to arrive trimmed at one and complete at the other
    -- which is `core/transcript.fit`'s job, and it drops whole turns because
    half a message attributed to a person is a fabrication.

    Never raises. A conversation that could not be rehydrated is a weaker
    reply, not a failed one.
    """
    if not conversation_id or not session_id:
        return
    records = _conversation_store()
    engine = getattr(kernel, "execution_engine", None)
    if records is None or engine is None or not hasattr(engine, "seed_session_turns"):
        return

    try:
        from core.transcript import ASSISTANT, USER, fit, from_messages

        turns = from_messages(records.messages(conversation_id))
        # The message just recorded is this request's own question, and it is
        # not a prior turn. Left in, the buffer would answer "what is 'that'"
        # with the sentence containing "that".
        if turns and turns[-1].role == USER:
            turns = turns[:-1]

        kept, _dropped = fit(turns, budget.document_tokens)

        # Back into the (question, answer) pairs the buffer holds. A reply with
        # no question ahead of it is dropped rather than paired with whatever
        # preceded it -- see `fit`, which already refuses to start on one.
        pairs: list[tuple[str, str]] = []
        pending: str | None = None
        for turn in kept:
            if turn.role == USER:
                pending = turn.text
            elif pending is not None:
                pairs.append((pending, turn.text))
                pending = None

        engine.seed_session_turns(session_id, pairs)
    except Exception as exc:
        logging.getLogger(__name__).debug(
            "Chat: could not rehydrate %s: %s", conversation_id, exc
        )


def _conversation_title(conversation_id: str) -> str:
    """The title the store settled on, for the event that names it."""
    records = _conversation_store()
    if records is None or not conversation_id:
        return ""
    try:
        return records.get(conversation_id).title
    except Exception:
        return ""


def _collect_answer(chunk: str, answer: list[str]) -> None:
    """Accumulate the reply text out of one IPC frame.

    Reads the frames rather than teeing the engine, because by this point the
    reply has already been through reasoning-splitting and citation handling —
    the tokens here are the ones the user sees, which is what belongs in a
    transcript.
    """
    try:
        frame = json.loads(chunk)
    except Exception:
        # A frame this layer cannot parse is still a frame the client gets.
        # Never let bookkeeping interfere with the stream.
        return
    if isinstance(frame, dict) and frame.get("type") == "token":
        content = (frame.get("data") or {}).get("content")
        if isinstance(content, str):
            answer.append(content)


def _record_reply(conversation_id: str, text: str, choice: "_ModelChoice") -> None:
    """Store the assistant's reply, with what answered and where it ran.

    An empty reply is not recorded. A stream that produced no tokens — refused,
    aborted before the first one, or failed — has nothing a person would want
    to find later, and an empty assistant row in the transcript reads as Zaram
    having said nothing when in fact it never spoke.
    """
    if not conversation_id or not text.strip():
        return
    records = _conversation_store()
    if records is None:
        return

    from conversations import ASSISTANT

    try:
        inference = _current_inference(choice.model)
        # `locality_of` answers `None` for a model it cannot place, and that
        # travels as "" rather than as "local". CLAUDE.md: *"runs on this
        # machine" would be a confident false claim on the one thing the user
        # is most likely to check.*
        records.append(
            conversation_id,
            ASSISTANT,
            text,
            model=str(inference.get("model") or choice.model or ""),
            locality=str(inference.get("locality") or ""),
        )
    except Exception as exc:
        logging.getLogger(__name__).warning("Chat: could not record the reply: %s", exc)


async def _vision_refusal(model: str | None) -> str:
    """Why this request cannot be answered, or `""` if it can.

    Called only when an image is attached. Returns a sentence for the user,
    never a status code: the person needs to know whether to change model or
    to install one, and those are different actions.

    **Every uncertainty resolves to `""`.** A model Zaram cannot place, a
    provider layer that has not booted, a discovery that found nothing, a
    lookup that raised \u2014 all proceed. Refusing on any of them would report
    "your machine cannot read images" as a fact about the hardware when it is a
    statement about our own bookkeeping, and that is the failure this function
    was written with: it fired on the first request after a boot, before
    anything had scanned, on a machine with two vision-capable models
    installed.

    The one case that does refuse is the one Zaram positively knows: models
    were found, and none of them can see. Same shape as `vram_bytes` returning
    `None` rather than `0`, and `locality_of` returning `None` rather than
    guessing local \u2014 do not turn "unmeasured" into a claim.
    """
    manager = getattr(getattr(kernel, "providers_runtime", None), "manager", None)
    if manager is None:
        return ""

    try:
        # The same thing `/providers/models` does before reading the catalogue.
        # Without it the first request of a session asks an empty shelf.
        await manager.ensure_scanned()
        if model:
            # Matched on `display_name`, which is what the chat path speaks and
            # what `_task_model` returns. `catalog.get` keys on the catalogue
            # id (`ollama:gemma4:12b`) and would miss every time.
            found = next(
                (m for m in manager.catalog.all() if m.display_name == model), None
            )
            if found is not None and not found.supports_vision:
                return (
                    f"{model} cannot read images. Choose a model that can see "
                    "in Settings, or remove the picture to ask about the text."
                )
            if found is not None:
                return ""

        # No model named, or one that could not be placed: ask the gate
        # whether *anything* here can see.
        #
        # Guarded on the catalogue being populated at all. An empty one means
        # discovery has not run or failed, and answering "nothing here can
        # see" to that question is a claim about the user's machine built on
        # our own missing data.
        known = manager.catalog.all()
        if known and manager.select_model_for_task(requires_vision=True) is None:
            return (
                "No model on this machine can read images. Zaram will not "
                "answer about a picture it cannot see."
            )
    except Exception:
        # A lookup failure must not become a refusal. See the docstring.
        logging.getLogger(__name__).debug("Vision eligibility check failed")
    return ""


def _answering_event(choice: _ModelChoice):
    """The event that tells the user which model is about to speak.

    Built here rather than in `ChatRouter` because this is where the model is
    resolved, and rebuilding that resolution one layer down is how two places
    come to disagree about which model answered — the exact failure the
    hardcoded ``gemma3:latest`` in the transport was.

    Takes the whole `_ModelChoice` for the same reason: the name and the reason
    it was chosen are one decision, and passing them separately is how a reply
    comes to name a model beside an explanation of a different choice.

    Every field degrades to ``None`` independently. A name Zaram cannot place
    still gets reported *as a name*, with no locality and no provider beside
    it, because "qwen3 answered" is true and useful while "qwen3 answered on
    this machine" would be a claim from a lookup that failed.
    """
    from core.streaming_events import StreamEvent

    model = choice.model
    name: str | None = model
    locality: str | None = None
    provider: str | None = None

    try:
        runtime = kernel.registry.get_runtime("models")
    except Exception:
        runtime = None

    if runtime is not None:
        if not name:
            # Nobody chose, so the answering model is the runtime's own — the
            # provider layer's vetted pick, which it reports as a wire name.
            try:
                name = runtime.health_check().get("model") or None
            except Exception:
                name = None
        try:
            locality = runtime.locality_of(model or name)
        except Exception:
            locality = None
        try:
            provider = runtime.provider_of(model or name)
        except Exception:
            provider = None
        try:
            name = runtime.wire_name(name) if name else name
        except Exception:
            pass

    return StreamEvent.answering(
        name,
        locality,
        chosen_by=choice.chosen_by,
        provider=provider,
    )


def _locality_of_model(model: str | None) -> str | None:
    """``"local"``, ``"cloud"``, or ``None`` when it cannot be established.

    Asks the models runtime's `locality_of`, which is deliberately *not*
    `_is_remote_model`: that one answers "may this leave the machine?" and
    returns `False` for anything it cannot resolve, because guessing wrong
    there costs the user's documents. This question is "where does it run?",
    and for that an unresolved model is genuinely unknown. Same input, two
    questions, and the two must not be merged.
    """
    try:
        runtime = kernel.registry.get_runtime("models")
        return runtime.locality_of(model)
    except Exception:
        return None


class ChatRequest(BaseModel):
    text: str
    #: Empty means "no preference expressed by this request", which is not the
    #: same as "no model". See `_resolve_model`. It was ``"gemma3:latest"`` —
    #: a default that silently answered on behalf of a user who had chosen
    #: nothing, and overrode a Settings choice they had.
    model: str = ""
    # `personality: str = "af_heart"` stood here and is deleted. It was a
    # *personality* field defaulting to a **voice id**, read by nothing, sent
    # by nothing, and sitting one line above the `persona` field that actually
    # carries the preset. Left alone it is a trap for whoever reads this class
    # next and concludes that a voice belongs on a chat request.
    persona: str = DEFAULT_PERSONA
    session_id: str = "default"
    #: Which project this exchange belongs to, or "" for none (rule 7i).
    #:
    #: Empty is a real answer, not a missing one: a question asked outside any
    #: project genuinely is not about one, and facts captured from it stay
    #: `global`. Inventing a project here would be a value nobody entered.
    project_id: str = ""
    #: The knowledge domains this question is asked inside, or [] for all.
    #:
    #: A separate axis from `project_id`, and deliberately so: scope is about
    #: *whose work* a fact belongs to, a domain is about *which library* the
    #: user chose to read from, and a question can sit inside both at once.
    #: Empty means unrestricted — the ordinary case — which is not the same as
    #: a chosen domain that happens to hold nothing. See `_domain_scope`.
    domain_ids: list[str] = []
    #: Files attached to *this message*, by id from `POST /chat/attachments`.
    #:
    #: A third axis again, and the narrowest. A project says whose work this
    #: is, a domain says which library to read from, and this says "the
    #: document in front of us right now" — which is working state and never
    #: enters the Spine unless the user separately decides it should (rule 7d).
    #:
    #: Ids rather than text, so the decision about how much of a document fits
    #: is made where the model's budget is known. A frontend that inlined the
    #: text would be choosing on behalf of a context length it cannot see.
    attachment_ids: list[str] = []
    #: Which stored conversation this message belongs to, or "" to begin one.
    #:
    #: **Not `session_id`, and the two must not be merged.** A session is a
    #: page load -- the frontend mints one per mount, and `_session_turns`
    #: evicts them by the dozen. A conversation is a thing a person comes back
    #: to next week. Keying transcripts on the session id would file every
    #: reload as a new conversation and every restart as amnesia, which is the
    #: behaviour this store exists to end.
    #:
    #: Empty means "start one", answered with a `conversation` event before the
    #: first token so the client knows what to send next time.
    conversation_id: str = ""


def _domain_scope(domain_ids: list[str]) -> tuple[frozenset[str] | None, str]:
    """Turn the domains a question was asked inside into a recall filter.

    Returns ``(only_ids, notice)``. ``only_ids`` is ``None`` when no domain was
    chosen — unrestricted — and a ``frozenset`` otherwise, **including an empty
    one**. `frozenset()` is falsy, so anything testing truthiness along this
    chain would widen a domain holding nothing to the entire Spine; every hop
    from here to `retrieval.py` compares against ``None`` instead.

    The notice is the other half, and it is not decoration. A question answered
    inside one domain did not look at the rest, and *disabled capabilities are
    visible, not silent* — so the restriction is stated whether or not it
    happened to find anything. Stating it matters most in the case that looks
    like a failure: an empty domain otherwise produces a confident answer built
    on no files at all, with nothing on screen explaining why.

    Resolution lives here rather than in the engine because the engine has no
    knowledge stores and should not grow any. It is handed a resolved set,
    exactly as it is handed a resolved scope string.

    `knowledge_domains` and `ingest_service` are created further down this
    module. That is deliberate and not a latent bug: both names are looked up
    when a request arrives, long after import has finished.
    """
    from knowledge.domain_recall import describe, fact_ids_for

    chosen = [d for d in (domain_ids or []) if d]
    if not chosen:
        return None, ""

    # A domain that cannot be resolved must not quietly answer from everything.
    # That is the opposite of what was asked for, and the user has no way to
    # see that it happened — so the failure narrows to nothing and says so.
    unreadable = (
        frozenset(),
        "Zaram could not read the knowledge domain you chose, "
        "so this answer used no facts from your files.",
    )
    try:
        only_ids = fact_ids_for(knowledge_domains, ingest_service.records, chosen)
        phrase = describe(knowledge_domains.all(), chosen)
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Domain scope failed to resolve: %s: %s", type(exc).__name__, exc
        )
        return unreadable
    if not phrase:
        # Ids naming no domain that exists. Same reasoning, same answer.
        return unreadable

    if only_ids:
        count = len(only_ids)
        notice = (
            f"Answering inside {phrase} — {count} "
            f"{'fact' if count == 1 else 'facts'} in scope. "
            "Nothing else in your Spine was read."
        )
    else:
        notice = (
            f"Nothing is indexed in {phrase} yet, "
            "so this answer used no facts from your files."
        )
    return only_ids, notice


# --- API ENDPOINTS ---


@app.get("/readiness")
async def readiness():
    """Can Zaram answer yet, and if not, what should be offered.

    Separate from `/health`, which reports whether the process is alive. This
    answers a different question — whether the *product* can do its job — and
    the first-run screen is built on it.

    The Ollama probe is a loopback request to a process on this machine, so it
    is not egress and rule 7g does not apply. Nothing here reaches the network:
    the decision of whether to *fetch* anything stays with the user, which is
    why `core.readiness` has no HTTP client of its own and a test asserting so.
    """
    import os

    from core.readiness import diagnose
    from providers.discoverers.ollama import OllamaAdapter

    # Through the adapter, not a request of our own. The first version of this
    # opened its own `urllib` connection and `test_no_module_opens_its_own_
    # connection` failed it — correctly. The probe is loopback and genuinely not
    # egress, but the chokepoint is structural on purpose: a module that opens
    # its own socket is exactly how an unlogged path appears, and an exception
    # granted for a local call is an exception the next author generalises.
    chat_models: list[str] = []
    engine_installed = False
    try:
        # Short timeout. A machine without Ollama should reach the offer screen
        # quickly rather than sit on a spinner deciding it is broken.
        discovered = await OllamaAdapter().discover_models(timeout=1.5)
        engine_installed = bool(discovered)
        for model in discovered:
            name = model.id or model.display_name
            # Embedding models cannot hold a conversation. Counting bge-m3 as a
            # chat model is how someone with only embeddings installed is told
            # they are ready and then meets a composer that answers nothing.
            if name and "embed" not in name.lower() and "bge" not in name.lower():
                chat_models.append(name)
    except Exception:
        # Unreachable means not installed *as far as this matters*. The
        # distinction between "absent" and "installed but not running" is real
        # and is not actionable differently: both need the same offer.
        engine_installed = False

    result = diagnose(
        engine_installed=engine_installed,
        chat_models=chat_models,
        cloud_key_configured=bool((os.getenv("ZARAM_OPENAI_KEY") or "").strip()),
    )
    return result.to_dict()


@app.get("/health")
async def health():
    """Liveness/readiness probe used by the desktop runtime health check."""
    capabilities = []
    try:
        if kernel and getattr(kernel, "registry", None) is not None:
            capabilities = [c.id for c in kernel.registry.list_capabilities()]
    except Exception:
        capabilities = []
    
    # Check knowledge providers
    provider_health = {}
    try:
        from knowledge.knowledge_service import get_runtime
        runtime = get_runtime()
        for provider_info in runtime.list_providers():
            provider_health[provider_info['id']] = {
                "status": provider_info.get('status', 'unknown'),
                "latency_ms": provider_info.get('latency_ms', 0),
                "requests": provider_info.get('requests', 0),
                "failures": provider_info.get('failures', 0),
            }
    except Exception:
        provider_health = {}
    
    # Check speech runtime
    speech_health = {}
    try:
        if kernel.speech_runtime:
            speech_health = kernel.speech_runtime.health_check()
    except Exception:
        speech_health = {}
    
    # Which build is answering, and since when. Cheap, and it exists because a
    # backend from 06:32 served this port all day while two already-fixed bugs
    # were re-diagnosed against it. See core/build_stamp.py.
    from core.build_stamp import build_stamp

    # What the Orb reports. This is the product claim made continuously visible,
    # so it must describe what is actually true rather than what is intended.
    from core.planner import web_search_enabled

    # Which model is actually answering. The models runtime knows, because the
    # provider layer chose it at boot; nothing downstream could see it, so the
    # interface had no way to name the model without inventing one. Stays None
    # when unknown rather than falling back to a plausible-looking default —
    # the persistent bar omits the segment rather than claiming a model.
    active_model = None
    try:
        active_model = kernel.registry.get_runtime("models").health_check().get("model")
    except Exception:
        active_model = None

    inference_providers = []
    try:
        for cap in capabilities:
            if cap == "reasoning.generate":
                inference_providers.append(
                    {"id": "ollama", "locality": "local", "model": active_model}
                )
    except Exception:
        pass

    # Connected cloud providers, so the Orb stops under-reporting.
    #
    # This list was hardcoded to Ollama alone, with a comment saying a cloud
    # engine "must list it, or the Orb will under-report egress" — and that is
    # what happened the first time somebody connected one. `describeSystem`
    # reads this list to decide between "Cloud enabled" and "Local · can send",
    # so connecting OpenRouter changed nothing on screen and the indicator kept
    # saying inference was local while a cloud model was one dropdown away.
    #
    # Reported as *connected*, which is not the same as *answering*. Zaram still
    # answers locally until a cloud model is chosen, and rule 5 is why: nothing
    # routes off-device by default. "Cloud enabled" is the honest word for it —
    # a cloud model can answer, not that one did.
    try:
        from providers import cloud_config

        for connection in cloud_config.connections().values():
            if connection.is_loopback:
                # LM Studio and friends are another process on this machine.
                # Listing them as cloud would over-report egress, which is the
                # opposite error and just as much a lie.
                continue
            inference_providers.append(
                {
                    "id": connection.provider_id,
                    "locality": "cloud",
                    "model": None,
                }
            )
    except Exception:
        pass

    search_on = web_search_enabled()

    # Whether anything *can* leave is now a fact about the policy, not a guess.
    # A destination with no rule is denied, so an empty policy means no route
    # off this machine exists at all — which is the honest thing for the Orb to
    # report, and it is now measured rather than inferred from a feature flag.
    egress_summary = {"allowed_hosts": 0, "entries": 0, "bytes_today": 0}
    try:
        from core.egress import Mode, get_gate

        gate = get_gate()
        rules = gate.policy.rules()
        egress_summary = {
            "allowed_hosts": sum(
                1 for m in rules.values() if m in (Mode.ALLOW.value, Mode.ASK.value)
            ),
            "entries": gate.log.count(),
            "bytes_today": gate.log.bytes_since(time.time() - 86400),
        }
    except Exception:
        pass

    can_egress = egress_summary["allowed_hosts"] > 0 or search_on
    # Derived, not asserted. This was the literal string "local" with a comment
    # promising it would become "cloud" or "mixed" once a remote provider was
    # wired — and it stayed "local" after one was, which is the shape of every
    # invented value this codebase has had to go back and fix.
    localities = {p.get("locality") for p in inference_providers}
    if localities == {"cloud"}:
        mode = "cloud"
    elif "cloud" in localities:
        mode = "mixed"
    else:
        mode = "local"

    routing = {
        "mode": mode,
        "providers": inference_providers,
        "web_search": "enabled" if search_on else "disabled",
        # The honest summary: is there any route off this machine at all?
        "can_leave_device": can_egress,
        "egress": egress_summary,
    }

    return {
        "status": "ok",
        "kernel": "online" if chat_router is not None else "offline",
        "capabilities": capabilities,
        "knowledge_providers": provider_health,
        "speech": speech_health,
        "routing": routing,
        # `curl localhost:8420/health` now answers "which build is this?" —
        # the question that would have saved two rounds of re-fixing bugs that
        # were already fixed.
        "build": build_stamp(),
    }


def _current_inference(requested_model: str | None) -> dict[str, str | None]:
    """What is actually about to answer — model name and where it runs.

    Every failure returns ``None`` for the field it could not establish, and
    `identity_preamble` renders nothing for a ``None``. The alternative is a
    preamble that names a plausible model, which would be a confident false
    claim in the one place the user is most likely to check.

    The requested model wins over the runtime's default because that is what
    will answer this message; the default is only the fallback for a request
    that named nothing.
    """
    model: str | None = (requested_model or "").strip() or None
    locality: str | None = None

    try:
        runtime = kernel.registry.get_runtime("models")
    except Exception:
        return {"model": model, "locality": None}

    if model is None:
        try:
            model = runtime.health_check().get("model") or None
        except Exception:
            model = None

    # The name the *user* would recognise, not the id the catalogue invented.
    # Asked "what model is answering", Zaram replied "ollama:qwen2.5-coder:1.5b"
    # — a string that appears nowhere in the interface, prefixed with a word
    # that looks like part of the model's name. Locality below is still asked
    # about the id, because that is what the catalogue is keyed by.
    display = model
    try:
        display = runtime.wire_name(model) if model else model
    except Exception:
        display = model

    try:
        # Three-valued on purpose. `_is_remote_model` answers False for an
        # unresolved model because routing must fail safe; identity must not
        # inherit that, or an unknown model gets described as local.
        locality = runtime.locality_of(model)
    except Exception:
        locality = None

    return {"model": display, "locality": locality}


@app.post("/chat")
async def chat(request: ChatRequest):
    """Strangler Fig Endpoint: Routes via ChatRouter."""
    # Which model answers, in precedence order: what this request named, then
    # what the user chose in Settings, then whatever the provider layer vetted.
    #
    # The request used to be the only input, and the frontend hardcoded
    # `gemma3:latest` into every one of them — a name no interface control ever
    # changed. So the provider layer's selection, the residency gate and the
    # data-policy gate all ran and were then overridden by a string literal in
    # `chatClient.ts`, which is why no routing decision was ever observable.
    #
    # The question itself is the fourth input and the last one consulted: it
    # decides only when nobody else has, and only when its intent asks for a
    # model Zaram would not otherwise have picked.
    # Attachments are resolved before the model, because an image changes
    # which models are eligible and that is a *fact* about the request rather
    # than an inference from its wording. `_resolve_model` previously guessed
    # `requires_vision` from the text alone - the word "screenshot" - and its
    # own docstring recorded that as the gap to close when image input landed.
    attached, missing_attachments = attachment_store.resolve(
        request.session_id, request.attachment_ids
    )
    images = [a.data for a in attached if a.kind == "image" and a.data]

    choice = _resolve_model(request.model, request.text, has_images=bool(images))
    model = choice.model

    # The refusal the docstring promised. A model that cannot see, asked to
    # look at a picture, must say so rather than answer around it: answering
    # blind produces confident prose about an image nobody looked at, which is
    # rule 9's failure in a new medium.
    #
    # Two different causes, two different sentences. "You chose a model that
    # cannot see" is actionable; "nothing installed here can see" is a
    # different problem with a different fix, and collapsing them into one
    # message leaves the user unable to tell which they have.
    if images:
        refusal = await _vision_refusal(model)
        if refusal:
            return StreamingResponse(
                _stream_error(refusal), media_type="text/event-stream"
            )

    # Web search compensates for what the *answering* model does not know, so
    # whether to search depends on which model that is — and this is the first
    # point where it has been resolved. The planner runs downstream, reads the
    # gate in two places, and has no way to ask.
    #
    # Carried in a `ContextVar` rather than a module global or an environment
    # variable. Both of those are process-wide, and two chat requests with
    # different models are in flight at once the moment a second window exists:
    # one would silently decide the other's search policy. A `ContextVar` is
    # per-task under asyncio, so each request sees its own value and nothing
    # needs to be restored afterwards.
    set_search_locality(_locality_of_model(model))
    print(f"[STAGE-7][Python] POST /chat received: text='{request.text[:50]}...' model={model} persona={request.persona}")
    print(f"[STAGE-7][Python] Full request text length: {len(request.text)} chars")

    # Two `hasattr(request, "image")` guards stood here and are deleted.
    # `ChatRequest` has no `image` field and never had one, so both conditions
    # were constant `False` — a refusal that could not fire, reading as a
    # protection that was in place. The honest version of that check belongs on
    # the attachment path, where an image genuinely can arrive and is genuinely
    # refused with a sentence saying why: see `attachments/store.py`.

    persona_data = PERSONAS.get(request.persona, PERSONAS.get("zaram_prime", {}))
    persona_prompt = persona_data.get("system_prompt", "") if persona_data else ""

    # Identity first, voice second. A model cannot know what it is deployed as —
    # ask a local Qwen and it answers from training data, which is how "I am
    # Qwen, made by Alibaba" ends up being the product's answer to "what are
    # you". The true answer only exists here, so it is handed over rather than
    # left to the weights.
    # The character the user chose, carried into the preamble as *facts* — the
    # same kind of statement as the model name beside it. A name is additive
    # ("this person calls you Ada"), never substitutive ("you are Ada"), which
    # is the distinction the eight removed personas got wrong.
    try:
        from core.user_settings import get_user_settings

        _character = get_user_settings()
        _named, _manner = _character.assistant_name, _character.manner
    except Exception:
        # A settings file must never be able to stop chat working.
        _named, _manner = "", ""

    # The date, read here rather than inside the preamble, which is pure by
    # design. Local time and not UTC: "what happened today" means the user's
    # today, and on the wrong side of midnight UTC those are different days.
    # Spelled out in full — "17 August 2026" cannot be read as 8 May the way
    # 08/17/2026 and 17/08/2026 read as each other's dates.
    from datetime import datetime as _datetime

    _today = _datetime.now().strftime("%d %B %Y")

    system_prompt = compose_system_prompt(
        identity_preamble(
            **_current_inference(model),
            assistant_name=_named,
            manner=_manner,
            today=_today,
        ),
        persona_prompt,
    )

    # The Kernel owns planning, search, grounding, and response generation.
    # The API layer passes the raw prompt through without independent search.
    final_prompt = request.text

    # Files attached to this message, composed against the model's budget.
    #
    # Here rather than in the kernel because this is the layer that holds the
    # session stores, and *before* the stream starts because what was read has
    # to be sayable before the answer built on it — the same reasoning the
    # domain notice already follows.
    # **Sized against the window this model was actually loaded with.**
    #
    # `compose.py` has carried a constant since it was written, with the reason
    # in its own comment: Ollama serves a default `num_ctx` regardless of what a
    # model advertises -- `gemma4:12b` reports a 262,144-token maximum through
    # `/api/show` and loads with 4,096 -- so the declared figure is the wrong
    # number and the constant erred small on purpose. `/api/ps` reports the real
    # one, which turns the guess into a measurement.
    #
    # Unknown still falls back to the constant rather than to a guess. A model
    # that is not resident has no loaded context, and inventing one for it is
    # the false-zero bug in different clothes.
    _budget = budget_for(model)
    composition = compose_attachments(
        attached,
        request.text,
        missing=missing_attachments,
        budget_chars=_budget.document_chars,
    )
    if composition.block:
        final_prompt = f"{composition.block}\n\n{request.text}"

    # Who is answering, said before the first token rather than after the last.
    #
    # `CLAUDE.md` requires every reply to name the model that answered, and
    # nothing did — so a user who had connected a cloud provider had no way to
    # tell whether anything ever reached it, which is precisely the report that
    # sent me looking. Ahead of the stream for the reason `model_load` is ahead
    # of it: an attribution that arrives after the answer is a footnote, and
    # the question is asked while reading.
    # Which knowledge domains this question may read from, resolved to fact ids
    # here because this is the layer that holds the knowledge stores.
    from core.streaming_events import StreamEvent

    only_ids, domain_notice = _domain_scope(request.domain_ids)

    # The transcript this exchange belongs to, opened now if the request did
    # not name one. **Before the stream**, because the user's message is
    # recorded whether or not a reply ever arrives -- a question that produced
    # an error is still a question they asked, and losing it because
    # generation failed is the amnesia this store exists to end.
    conversation_id, conversation_started = _open_conversation(request)
    # A conversation picked up after a restart gets its recent turns back.
    # Only when it was not just created: a new one has nothing prior, and
    # asking the store for it would be a query with a known answer.
    if conversation_id and not conversation_started:
        _seed_turns_from_transcript(conversation_id, request.session_id, _budget)

    async def _stream_with_attribution():
        # Only when Zaram opened it: the client already knows the id it sent
        # and needs to be told the id it did not. Ahead of the first token, so
        # an interrupted stream still leaves a conversation that can be
        # reopened rather than a thread with no name.
        if conversation_started:
            yield StreamEvent.conversation(
                conversation_id, _conversation_title(conversation_id)
            ).to_ipc() + "\n"
        yield _answering_event(choice).to_ipc() + "\n"
        # Before the answer rather than after it, unlike the ingest notice.
        # This one is a *frame* for what follows rather than housekeeping: if
        # the domain turned out to be empty, that has to be readable before a
        # confident answer built on no files is, not underneath it afterwards.
        if domain_notice:
            yield StreamEvent.notice(
                domain_notice, kind="domain", action="knowledge"
            ).to_ipc() + "\n"
        # How much of each attached file the model actually saw.
        #
        # **Always, not only when something was left out.** "Read it in full"
        # and "searched it and used 3 of 41 sections" are different answers to
        # the same question, and a disclosure that appears only in the second
        # case teaches the user that silence means everything was read — which
        # makes the one time it is missing indistinguishable from the one time
        # it did not fire. LM Studio switches between these two modes and
        # documents neither; this is the whole of the difference.
        attachment_notice = composition.notice()
        if attachment_notice:
            yield StreamEvent.notice(
                attachment_notice, kind="attachment"
            ).to_ipc() + "\n"
        # Tokens are accumulated as they pass, so the reply can be stored
        # when the stream ends.
        #
        # **Only `token`.** `reasoning` is the model's working, which
        # `ReasoningSplitter` already keeps out of `streamingText` and out
        # of speech -- storing it would put a model's internal monologue in
        # the transcript as though it were the answer, and a later session
        # would read it back as what Zaram said.
        answer: list[str] = []
        async for chunk in chat_router.route(
            final_prompt, model, system_prompt, request.session_id,
            project_id=request.project_id or None,
            only_ids=only_ids,
            images=images or None,
        ):
            _collect_answer(chunk, answer)
            yield chunk

        # After the loop rather than in a `finally`. A stream the user
        # aborted has a partial answer, and storing half a reply as though
        # it were the whole one is worse than storing nothing.
        _record_reply(conversation_id, "".join(answer), choice)

    return StreamingResponse(
        _stream_with_attribution(),
        media_type="text/event-stream"
    )


class VisionRequest(BaseModel):
    prompt: str
    image: str


@app.post("/vision/analyze")
async def vision_analyze(request: VisionRequest):
    """Vision analysis endpoint using Ollama vision models."""
    print(f"[STAGE-7][Python] POST /vision/analyze received: prompt='{request.prompt[:50]}...'")
    from runtimes.models.engines.ollama_engine import OllamaEngine
    engine = OllamaEngine()
    full_prompt = request.prompt

    if not request.image or not request.image.strip():
        async def _empty():
            yield StreamEvent.error("No image was provided for vision analysis. Capture a screenshot or attach an image first.").to_ipc() + "\n"
            yield StreamEvent.done().to_ipc() + "\n"
        return StreamingResponse(_empty(), media_type="text/event-stream")

    image_data = request.image
    if isinstance(image_data, str) and image_data.startswith("data:"):
        image_data = image_data.split(",", 1)[1] if "," in image_data else image_data

    async def _vision_stream():
        from core.streaming_events import StreamEvent, EventType
        yield StreamEvent.start().to_ipc() + "\n"
        for chunk in engine.stream_vision_response(full_prompt, images=[image_data]):
            parsed = _parse_legacy_sse(chunk)
            if parsed and parsed.get("type") == "token":
                yield StreamEvent.token(parsed.get("content", "")).to_ipc() + "\n"
            elif parsed and parsed.get("type") == "error":
                yield StreamEvent.error(parsed.get("content", "Vision error")).to_ipc() + "\n"
        yield StreamEvent.status("complete").to_ipc() + "\n"
        yield StreamEvent.done().to_ipc() + "\n"

    return StreamingResponse(_vision_stream(), media_type="text/event-stream")


class KnowledgeRequest(BaseModel):
    query: str
    persona: str = "zaram_prime"


@app.post("/knowledge/search")
async def knowledge_search(request: KnowledgeRequest):
    """Internet search endpoint."""
    print(f"[STAGE-7][Python] POST /knowledge/search received: query='{request.query[:50]}...' persona={request.persona}")
    from knowledge.knowledge_service import search_knowledge
    return search_knowledge(request.query, request.persona)


@app.get("/memory")
async def list_memory(limit: int = 200, offset: int = 0, q: str = ""):
    """Everything in the Spine, newest first.

    Backs the Memory surface. Returns what is actually stored — if the Spine
    holds four records, this returns four records. There is no sample data
    anywhere behind this endpoint.
    """
    if not kernel.memory_runtime:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    # include_superseded: corrected facts are excluded from *recall* but must
    # still appear here. Showing the user where Zaram was wrong, struck through
    # and dated, is the point of supersession — a correction they cannot see is
    # indistinguishable from a deletion.
    records = await kernel.memory_runtime._store.all_records(include_superseded=True)
    records.sort(key=lambda r: r.created_at, reverse=True)

    if q:
        needle = q.lower()
        records = [r for r in records if needle in (r.content or "").lower()]

    total = len(records)
    page = records[offset : offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "records": [
            {
                "id": r.id,
                "content": r.content,
                "memory_type": getattr(r.memory_type, "value", str(r.memory_type)),
                "created_at": r.created_at,
                "last_accessed": r.last_accessed,
                "access_count": r.access_count,
                "importance": r.importance,
                "source": r.source,
                "tags": list(r.tags or []),
                "session_id": r.session_id,
                # Rule 7i: `global` or `project:<id>`. One field, sent as one
                # field — the surface derives the project id from it rather
                # than being handed a second spelling that can disagree.
                "scope": r.scope,
                "superseded_by": r.superseded_by,
                "superseded_at": r.superseded_at,
                "pinned": r.pinned,
                # Set when this record replaced another, so the surface can link
                # a correction back to what it corrected.
                "corrects": (r.metadata or {}).get("corrects"),
            }
            for r in page
        ],
    }


@app.get("/memory/maintenance")
async def memory_maintenance_status():
    """What the last decay pass did, and what promotion is now being offered.

    Exists so the maintenance pass is observable rather than merely running.
    A background job that silently deletes the user's facts is the wrong shape
    for this product even when the deletions are correct — rule 4 gives the
    user authority over stored facts, and authority without visibility is not
    authority.

    `last_result` is null when no pass has run yet, which is a different claim
    from a pass that ran and changed nothing.
    """
    if spine_maintenance is None:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    result = spine_maintenance.last_result
    candidate_ids = (result or {}).get("promotion_candidates", [])

    # Resolved to content here rather than in the pass: the pass runs
    # unattended and should hold ids, not copies of facts that a correction may
    # have since changed underneath it.
    candidates = []
    if kernel.memory_runtime and candidate_ids:
        for rid in candidate_ids:
            record = await kernel.memory_runtime._store.get(rid)
            if record is None:
                continue
            candidates.append({
                "id": record.id,
                "content": record.content,
                "scope": record.scope,
                "recalled_in": sorted(record.recalled_in or []),
                "access_count": record.access_count,
            })

    return {
        "last_result": result,
        # Proposals, never applied. Promotion moves a fact from project scope to
        # global, changing what is shareable, and rule 6 says that is the user's
        # to grant. The caller promotes with POST /memory/{id}/scope.
        "promotion_candidates": candidates,
    }


@app.get("/memory/traffic")
async def memory_traffic():
    """Records the Spine holds that today's door check would refuse.

    **Why this is needed at all.** The check that decides what enters the Spine
    was a blocklist — store unless it looks like a question — and it failed
    open, so instructions and false starts became durable facts. Read out of a
    real Spine: "Say the single word: ping", "Reply with exactly: OK", "WHars
    your name". The door is fixed; this is for what got through before it was.

    They are not harmless once stored. Recall reaches them, so they arrive as
    citations in new answers — measured on a live question about AI news, where
    three of the ten sources behind the reply were the user's own old prompts.

    **Read-only, and that is deliberate.** It proposes and never applies. Rule
    4 gives the user authority over stored facts, and a background job that
    quietly deleted them would be the wrong shape even when every deletion is
    correct — the same reasoning `/memory/maintenance` already states about
    promotion. Removal is `DELETE /memory/{id}`, one fact at a time, by them.

    The classification is `ExecutionEngine._carries_new_information`, the very
    predicate the door uses. Reusing it rather than re-describing it is what
    stops the sweep and the gate disagreeing — two answers to one question is
    the failure this codebase keeps paying for, and a second copy of this rule
    would be exactly that.
    """
    if kernel.memory_runtime is None:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    from core.execution_engine import ExecutionEngine

    # Everything the user can see, superseded rows included.
    #
    # `all_records()` hides superseded ones by default, and the sweep then
    # reported 12 records while `GET /memory` listed 14 — so two entries were
    # invisible to the only tool offering to clean them up, including a
    # "Write any simple python code" the predicate classifies as traffic. A
    # review surface that cannot see what the user sees is one that quietly
    # claims to be finished when it is not.
    records = await kernel.memory_runtime._store.all_records(include_superseded=True)
    traffic = []
    for record in records or []:
        content = (record.content or "").strip()
        if not content:
            continue
        # A parsed document is not conversation and is never judged by a check
        # built for prompts. An invoice's text would fail it comprehensively.
        origin = (getattr(record, "metadata", None) or {}).get("origin")
        if origin == "user_document":
            continue
        if ExecutionEngine._carries_new_information(ExecutionEngine, content):
            continue
        traffic.append({
            "id": record.id,
            "content": content[:300],
            "created_at": getattr(record, "created_at", None),
            "access_count": getattr(record, "access_count", 0),
        })

    return {
        "traffic": traffic,
        "total_records": len(records or []),
        # Said in words because a count alone invites a "delete all" button,
        # and that button is what rule 4 exists to prevent.
        "note": (
            "These look like instructions or false starts rather than facts. "
            "Nothing has been changed. Remove any of them with "
            "DELETE /memory/{id}."
        ),
    }


@app.get("/memory/stats")
async def memory_stats():
    """Counts for the Memory surface. Every number is measured, none estimated."""
    if not kernel.memory_runtime:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    stats = await kernel.memory_runtime._store.stats()
    records = await kernel.memory_runtime._store.all_records()

    sessions = {r.session_id for r in records if r.session_id}
    newest = max((r.created_at for r in records), default=None)

    return {
        "total_records": stats.total_records,
        "by_type": dict(stats.by_type or {}),
        "sessions": len(sessions),
        "newest_at": newest,
        "storage_bytes": stats.storage_size_bytes,
        # Measured from the egress log. A real zero now means zero — before the
        # log existed this returned null, because an absent measurement must
        # never read as a measured zero on a privacy claim.
        "bytes_left_device_today": _egress_bytes_today(),
    }


def _egress_bytes_today() -> int | None:
    """Bytes that left in the last 24 hours, or None if the log is unreachable."""
    try:
        from core.egress import get_gate

        return get_gate().log.bytes_since(time.time() - 86400)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Egress — what left this machine.
#
# Rule 3 says every byte that leaves is logged. A log nobody can read satisfies
# the letter of that and none of the point, so these endpoints exist to make it
# legible: what left, when, to whom, whether the record has been tampered with,
# and which destinations are permitted at all.
# --------------------------------------------------------------------------- #


@app.get("/egress")
async def egress_log(limit: int = 100, offset: int = 0):
    """The log itself, newest first.

    ``literal_text`` is the point of this endpoint. Showing that a request went
    to wikipedia.org tells the user almost nothing; showing the exact query
    string that left is the thing they cannot get anywhere else.
    """
    from core.egress import get_gate

    gate = get_gate()
    limit = max(1, min(limit, 500))
    entries = gate.log.entries(limit=limit, offset=max(0, offset))

    return {
        "total": gate.log.count(),
        "entries": [
            {
                "id": e.id,
                "at": e.at,
                "kind": e.kind,
                "host": e.host,
                "method": e.method,
                "url": e.url,
                "body": e.body,
                "literal_text": e.url if not e.body else f"{e.url}\n\n{e.body}",
                "bytes": e.byte_count,
                "decision": e.decision,
                "reason": e.reason,
                "source": e.source,
                "meta": e.meta,
            }
            for e in entries
        ],
    }


@app.get("/egress/verify")
async def egress_verify():
    """Check the hash chain.

    Reports what the check actually proves. The chain detects alteration by
    anything that did not go through the log's own append path; it does not
    prevent someone with write access from rebuilding it. Saying otherwise in
    the interface would be the kind of absolute security claim the contract
    forbids, so the wording here is what the UI should show.
    """
    from core.egress import TamperDetected, get_gate

    gate = get_gate()
    try:
        gate.log.verify()
        return {
            "intact": True,
            "entries": gate.log.count(),
            "detail": "Every entry still matches its hash and the chain is unbroken.",
            "caveat": (
                "This detects changes made outside Zaram — an edit, a deletion, "
                "a reordering, or file corruption. It cannot stop someone with "
                "access to this machine from rebuilding the record."
            ),
        }
    except TamperDetected as exc:
        return {
            "intact": False,
            "entries": gate.log.count(),
            "at_row": exc.at_row,
            "entry_id": exc.entry_id,
            "detail": str(exc),
        }


@app.get("/egress/policy")
async def egress_policy():
    """Per-source rules, and every host ever contacted.

    Returns hosts seen but unruled as well, so the privacy pane can offer a
    decision about a destination the user has actually encountered rather than
    asking them to type hostnames from memory.
    """
    from core.egress import get_gate

    gate = get_gate()
    rules = gate.policy.rules()
    seen = list(gate.log.hosts())

    return {
        "default": "deny",
        "rules": rules,
        "hosts_seen": seen,
        "hosts_without_a_rule": [h for h in seen if h not in rules and h != "-"],
    }


@app.get("/egress/killswitch")
async def egress_kill_switch():
    """Whether everything outbound is currently refused.

    Settings promised this control and nothing implemented it, so the row read
    "not built" — which was at least honest. It lives in `EgressPolicy.decide`
    rather than in this file, so it covers every caller of the gate: tool
    traffic, model discovery, an update check somebody adds next year. A kill
    switch enforced at one call site is a kill switch for that call site, and
    the whole value of the control is that the user does not have to know how
    many outbound paths exist.
    """
    from core.egress import get_gate

    return {"on": get_gate().policy.kill_switch()}


class KillSwitchUpdate(BaseModel):
    on: bool


@app.post("/egress/killswitch")
async def set_egress_kill_switch(update: KillSwitchUpdate):
    """Cut, or restore, all outbound traffic in one action.

    Turning it off restores the per-host rules exactly as they were. Loopback is
    never affected — a request to 127.0.0.1 cannot leave the machine, so there
    is nothing to cut, and sealing it would stop the local model answering.
    """
    from core.egress import get_gate

    return {"on": get_gate().policy.set_kill_switch(update.on)}


@app.get("/search/web")
async def web_search_setting():
    """Whether questions may reach a search engine, and what still stands in the way.

    Three fields rather than one boolean, because "on" alone would be a
    misleading answer. Search is `CLAUDE.md`'s *first governed source*: turning
    it on lets a search step be planned, and the per-host policy still decides
    whether the request may be sent. A screen that showed only the switch would
    have the user turn it on, ask a question, get a refusal, and conclude the
    feature is broken.

    * ``on`` — the gate itself.
    * ``forced_by_environment`` — ``ZARAM_WEB_SEARCH`` is set, so the toggle is
      not the authority and the screen must say so rather than showing a
      control that appears to do nothing.
    * ``host_policy`` — what would happen to a request to the search engine
      today, read from the same policy the gate enforces.
    """
    from core.egress import get_gate
    from core.planner import SEARCH_HOST, web_search_enabled
    from core.user_settings import get_user_settings

    raw = os.getenv("ZARAM_WEB_SEARCH")
    gate = get_gate()

    settings = get_user_settings()
    return {
        "on": web_search_enabled(),
        "stored": settings.web_search,
        "scope": settings.search_scope.value,
        "forced_by_environment": bool(raw is not None and raw.strip()),
        "host": SEARCH_HOST,
        "host_policy": gate.policy.rules().get(SEARCH_HOST, "deny"),
        "kill_switch": gate.policy.kill_switch(),
    }


class WebSearchUpdate(BaseModel):
    #: Absent leaves the switch alone, which is what lets `scope` be set on its
    #: own without a client having to resend a value it did not mean to change.
    on: bool | None = None
    #: `local_only` or `always`. Absent leaves it alone.
    scope: str | None = None


@app.post("/search/web")
async def set_web_search_setting(update: WebSearchUpdate):
    """Turn web search on or off, and say when it is worth running.

    Stores preferences and nothing else — no request is made, and no host
    policy is changed. Granting the search engine permission to be contacted is
    a separate, per-item decision, which is rule 5 and is the whole reason
    search was sequenced behind the policy rather than beside it.
    """
    from core.user_settings import SearchScope, get_user_settings

    settings = get_user_settings()

    if update.on is not None:
        settings.set_web_search(update.on)

    if update.scope is not None:
        try:
            settings.set_search_scope(update.scope)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"scope must be one of: {', '.join(s.value for s in SearchScope)}",
            )

    return await web_search_setting()


@app.get("/character")
async def get_character():
    """What this person calls it, how they want it to write, which voice speaks.

    **Three fields, one object, because it is one thing to the user.** A name, a
    manner and a voice are a character; splitting them across three endpoints
    would let an interface save two and fail on the third, leaving a
    half-applied character nobody chose.

    None of it can change what Zaram says it is. `identity_preamble` places the
    user's name and manner *before* the rules about self-description, so the
    last instruction a model reads is the true one — the guarantee is the
    ordering, and `tests/test_identity_stays_truthful.py` asserts it against
    hostile input rather than trusting it.
    """
    from core.user_settings import get_user_settings

    settings = get_user_settings()
    return {
        "assistant_name": settings.assistant_name,
        "manner": settings.manner,
        "voice": settings.voice,
        # What it is called when the user has not named it. Sent so the
        # interface never has to hardcode the product's own name to render a
        # placeholder — the same reason `default_model` of null is meaningful.
        "default_name": "Zaram",
    }


class CharacterUpdate(BaseModel):
    #: Absent leaves a field alone; empty string clears it back to the default.
    #: The two are different intentions and must stay distinguishable, which is
    #: why every field is `str | None` rather than `str`.
    assistant_name: str | None = None
    manner: str | None = None
    voice: str | None = None


@app.post("/character")
async def set_character(update: CharacterUpdate):
    from core.user_settings import get_user_settings

    return get_user_settings().set_character(
        assistant_name=update.assistant_name,
        manner=update.manner,
        voice=update.voice,
    )


@app.get("/routing/preference")
async def routing_preference():
    """The second of `CLAUDE.md`'s three tiers of control, and the chosen model.

    Tier one is Zaram deciding; this is the one control in plain language; tier
    three is per-task assignment behind Advanced. Served together because a
    screen showing one without the other cannot explain what either does.
    """
    from core.user_settings import RoutingPreference, get_user_settings

    settings = get_user_settings()
    return {
        **settings.to_dict(),
        "options": [p.value for p in RoutingPreference],
    }


class RoutingPreferenceUpdate(BaseModel):
    #: One of `RoutingPreference`. Absent leaves it unchanged.
    routing_preference: str | None = None
    #: The model to answer with, or "" to hand the choice back to Zaram.
    #: `None` leaves it unchanged, which is what lets one endpoint set either
    #: field without a client having to send both and risk clobbering the one
    #: it did not mean to touch.
    default_model: str | None = None


@app.post("/routing/preference")
async def set_routing_preference(update: RoutingPreferenceUpdate):
    from core.user_settings import RoutingPreference, get_user_settings

    settings = get_user_settings()

    if update.routing_preference is not None:
        try:
            settings.set_routing_preference(update.routing_preference)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=(
                    "routing_preference must be one of: "
                    + ", ".join(p.value for p in RoutingPreference)
                ),
            )

    if update.default_model is not None:
        settings.set_default_model(update.default_model)

    return settings.to_dict()


class EgressPolicyUpdate(BaseModel):
    host: str
    #: "allow", "ask" or "deny". Anything else is rejected.
    mode: str


@app.put("/egress/policy")
async def set_egress_policy(update: EgressPolicyUpdate):
    """Set one host's rule. Rule 5's 'explicit, per-item policy' in practice."""
    from core.egress import Mode, get_gate

    host = (update.host or "").strip().lower()
    if not host:
        raise HTTPException(status_code=400, detail="A host is required")
    try:
        mode = Mode(update.mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"mode must be one of: {', '.join(m.value for m in Mode)}",
        )

    get_gate().policy.set(host, mode)
    return {"host": host, "mode": mode.value}


@app.delete("/egress/policy/{host}")
async def forget_egress_policy(host: str):
    """Remove a rule. The host reverts to the default, which is deny."""
    from core.egress import get_gate

    get_gate().policy.forget(host)
    return {"host": host.lower(), "mode": "deny", "reverted_to_default": True}


class EgressRetentionUpdate(BaseModel):
    #: Days to keep. 0 means keep everything.
    days: int


@app.post("/egress/retention")
async def apply_egress_retention(update: EgressRetentionUpdate):
    """Prune the log, and record that the pruning happened.

    The contract requires retention to ship *with* the log rather than after it:
    a permanent record of every private question is itself a privacy problem.
    """
    from core.egress import get_gate

    if update.days < 0:
        raise HTTPException(status_code=400, detail="days cannot be negative")

    gate = get_gate()
    removed = gate.log.apply_retention(max_age_days=update.days or None)
    return {
        "removed": removed,
        "remaining": gate.log.count(),
        "days": update.days,
        "note": (
            "Pruning is itself recorded, so the log can always show that entries "
            "were removed even though it can no longer show what they were."
        ),
    }


# --------------------------------------------------------------------------- #
# Pending confirmations — the person answering the gate's question.
#
# `EgressGate.check` calls its confirm hook from the middle of a synchronous
# decision, before anything is logged or sent, and blocks there. These three
# endpoints are the other end of that block: what is waiting, and the decision
# that releases it. Rule 6 in practice — the confirmation is the moment autonomy
# is granted, and it is granted per request rather than once.
#
# Polled rather than pushed. The chat stream is exactly what stalls while a
# question waits, so the notification cannot arrive on it, and a second channel
# to carry one event would be more machinery than a poll the dialog runs only
# while a request is in flight.
# --------------------------------------------------------------------------- #


@app.get("/egress/pending")
async def egress_pending():
    """Everything waiting on an answer, oldest first.

    A list, because a chat reply and a tool call can be in flight together and
    an interface built on the assumption of one would silently drop the second.
    """
    from core.egress import get_pending

    waiting = get_pending().pending()
    return {"pending": waiting, "count": len(waiting)}


@app.get("/egress/pending/{confirmation_id}")
async def egress_pending_one(confirmation_id: str):
    """One waiting question, for a dialog that reopened and wants its subject.

    404 once it has been decided. That is not an error state to paper over —
    a question already answered is exactly what a second dialog must not be
    able to answer again.
    """
    from core.egress import get_pending

    found = get_pending().get(confirmation_id)
    if found is None:
        raise HTTPException(
            status_code=404,
            detail="That request is no longer waiting — it was answered, or it timed out.",
        )
    return found


class EgressDecision(BaseModel):
    approved: bool
    #: The edited outbound text, or omitted to send it unchanged. Ignored on a
    #: refusal: there is no such thing as editing something you are not sending.
    body: str | None = None


@app.post("/egress/pending/{confirmation_id}")
async def decide_egress_pending(confirmation_id: str, decision: EgressDecision):
    """Answer a waiting question, and release the thread holding it.

    ``body`` is what the user approved after editing — striking a recalled fact
    they did not want to send. The gate reads the body back after the hook
    returns and logs it before sending, so what is shown, what is logged and
    what goes on the wire are the same bytes. The frontend does not have to be
    careful about that; it only has to send what the user approved.
    """
    from core.egress import get_pending

    released = get_pending().decide(
        confirmation_id, approved=decision.approved, body=decision.body
    )
    if not released:
        # A double-click, a retry, or a dialog answering something that already
        # timed out. Never approve a second send of text that has already gone.
        raise HTTPException(
            status_code=404,
            detail="That request is no longer waiting — it was answered, or it timed out.",
        )
    return {
        "id": confirmation_id,
        "approved": decision.approved,
        "edited": decision.approved and decision.body is not None,
    }


@app.get("/memory/{record_id}")
async def get_memory(record_id: str):
    """Fetch one stored fact, so a citation can be inspected.

    Rule 2 says every recalled fact carries provenance. A citation the user
    cannot open is only half of that — this is what makes it inspectable.
    """
    if not kernel.memory_runtime:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    record = await kernel.memory_runtime.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No such memory")

    return {
        "id": record.id,
        "content": record.content,
        "memory_type": getattr(record.memory_type, "value", str(record.memory_type)),
        "created_at": record.created_at,
        "last_accessed": record.last_accessed,
        "access_count": record.access_count,
        "importance": record.importance,
        "source": record.source,
        "tags": list(record.tags or []),
        "session_id": record.session_id,
        # Where this fact belongs. Absent until 10 August, which meant a fact
        # could be scoped to a project and there was no way to see that it was
        # — rule 7i's field existed and was invisible from the outside.
        "scope": record.scope,
        "metadata": dict(record.metadata or {}),
    }


class MemoryCorrection(BaseModel):
    content: str


@app.post("/memory/{record_id}/correct")
async def correct_memory(record_id: str, body: MemoryCorrection):
    """Correct a fact. The original is kept, struck through, and never recalled.

    Rule 4 says the user can correct any stored fact and the affected answers
    must change. Deletion only ever satisfied half of that: it stops the wrong
    fact being recalled, but discards the record that Zaram had it wrong and the
    user said so. That record is the point — a system that shows you where it
    was mistaken is one you can believe when it says it is right.
    """
    if not kernel.memory_runtime:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    corrected = (body.content or "").strip()
    if not corrected:
        raise HTTPException(status_code=400, detail="A correction cannot be empty")

    try:
        result = await kernel.memory_runtime.correct(record_id, corrected)
    except KeyError:
        raise HTTPException(status_code=404, detail="No such memory")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return {
        **result,
        "note": (
            "The original is kept and shown struck through. It is excluded from "
            "recall, so answers that depended on it will change."
        ),
    }


class MemoryPin(BaseModel):
    pinned: bool


@app.post("/memory/{record_id}/pin")
async def pin_memory(record_id: str, body: MemoryPin):
    """Pin a fact so recall prefers it over merely-recent ones."""
    if not kernel.memory_runtime:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    if not await kernel.memory_runtime.set_pinned(record_id, body.pinned):
        raise HTTPException(status_code=404, detail="No such memory")
    return {"id": record_id, "pinned": body.pinned}


@app.delete("/memory/{record_id}")
async def delete_memory(record_id: str):
    """Forget one stored fact.

    Rule 4: the user can delete any stored fact, and the affected answers must
    change. Removal is from the Spine itself, so the next question genuinely
    cannot recall it — this is not a display filter.
    """
    if not kernel.memory_runtime:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    deleted = await kernel.memory_runtime.forget(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="No such memory")

    print(f"[Memory] Forgot record {record_id}")
    return {"deleted": True, "id": record_id}


# --- ARTIFACTS -------------------------------------------------------------
#
# Backs the Work surface and the in-conversation file cards. Both read the same
# records, because they are the same thing shown twice — Work is "everything I
# made", a file card is "the thing I just made", and letting them diverge is how
# a document appears in one and not the other.

from artifacts import export as artifact_export  # noqa: E402
from artifacts.records import ArtifactRecords, default_db_path  # noqa: E402
from artifacts.service import ArtifactService  # noqa: E402
from artifacts.store import ArtifactStore, default_output_root  # noqa: E402

artifact_service = ArtifactService(
    ArtifactRecords(default_db_path()),
    ArtifactStore(default_output_root()),
)


def _artifact_json(artifact, *, include_html: bool = False) -> Dict[str, Any]:
    """One artifact, shaped for the frontend.

    `html` is omitted by default. It is the re-export source and can be large,
    and a list of twenty documents would carry twenty full documents to draw
    twenty rows.
    """
    payload = artifact.to_dict()
    payload["exists"] = bool(artifact.path) and os.path.isfile(artifact.path)
    if include_html:
        payload["html"] = artifact.html
    return payload


@app.get("/artifacts")
async def list_artifacts(
    project_id: str = "",
    kind: str = "",
    conversation_id: str = "",
    limit: int = 200,
    offset: int = 0,
):
    """Everything the user has made, newest first.

    Returns what is actually stored. If nothing has been generated this returns
    an empty list, and Work says so — there is no sample data behind this
    endpoint, and the module that used to provide some is gone.
    """
    artifacts = artifact_service.records.list(
        project_id=project_id or None,
        kind=kind or None,
        conversation_id=conversation_id or None,
        limit=limit,
        offset=offset,
    )
    return {
        "total": artifact_service.records.count(
            project_id=project_id or None, kind=kind or None
        ),
        "offset": offset,
        "limit": limit,
        "artifacts": [_artifact_json(a) for a in artifacts],
    }


# Declared before `/artifacts/{artifact_id}`: FastAPI matches in declaration
# order, so a static segment registered after a path parameter is unreachable —
# "projects" would be read as an artifact id and 404.
@app.get("/artifacts/projects")
async def list_artifact_projects():
    """Projects that actually hold artifacts, with counts.

    A *view over artifacts*, and now explicitly only that. It is what Work uses
    to offer a filter that cannot lead to an empty list. The list of projects
    that **exist** is `/projects`, which is a different question and used to be
    conflated with this one — a project you had only talked about was invisible,
    and one made by a typo could never be removed.
    """
    return {"projects": artifact_service.records.projects()}


# --------------------------------------------------------------------------- #
# Projects
#
# A project is an object here, not a label derived from artifacts. It carries
# the type that activates a pack, and it exists before anything has been saved
# into it — which is what lets a user work *inside* a project and have their
# facts scoped to it, rather than only after they have generated a file.
# --------------------------------------------------------------------------- #

from projects import ProjectRecords, ProjectType, UnknownProject  # noqa: E402
from projects.records import default_db_path as projects_db_path  # noqa: E402

project_records = ProjectRecords(projects_db_path())


def _project_json(project) -> Dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "type": project.type.value,
        "created_at": project.created_at,
        "note": project.note,
        "scope": project.scope,
    }


class ProjectCreateRequest(BaseModel):
    name: str
    type: str = "general"
    note: str = ""


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    type: str | None = None
    note: str | None = None


@app.get("/projects")
async def list_projects():
    """Every project that exists, with what is in it.

    The counts come from the stores that own those things rather than from a
    column here, so they cannot drift. They are what the delete confirmation is
    built on: "this holds 3 files and 11 facts" is the difference between an
    informed decision and a surprise.
    """
    out = []
    for project in project_records.list():
        entry = _project_json(project)
        entry["artifacts"] = artifact_service.records.count_for_project(project.id)
        entry["facts"] = await _fact_count_for_scope(project.scope)
        out.append(entry)
    return {"projects": out}


async def _fact_count_for_scope(scope: str) -> int:
    """How many facts are scoped to this project, or ``-1`` when unknown.

    ``-1`` rather than ``0``: a memory runtime that cannot answer is not the
    same as a project with no facts, and showing "0 facts" on a delete
    confirmation that then destroys eleven of them is the exact failure this
    count exists to prevent.
    """
    try:
        runtime = kernel.memory_runtime
        if runtime is None:
            return -1
        return await runtime.count_by_scope(scope)
    except Exception:
        return -1


@app.post("/projects")
async def create_project(body: ProjectCreateRequest):
    try:
        project = project_records.create(
            body.name, type=ProjectType(body.type), note=body.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _project_json(project)


# Before `/projects/{project_id}` in declaration order. FastAPI matches in the
# order routes are registered, and while no `GET /projects/{id}` exists today,
# adding one later would silently shadow this and read "unclaimed" as an id.
@app.get("/projects/unclaimed")
async def list_unclaimed_projects():
    """Groups that exist on files and facts, but are not projects.

    A `project_id` reaches an artifact, and a `project:<id>` scope reaches the
    Spine, from whatever the request carried. Neither creation path checked that
    the project existed, so a stale selection or a typo produces a group Project
    cannot show, rename or delete — while Work happily groups files under it.

    **Assignment validates its destination, which is what turned this from
    untidiness into a one-way door.** A file can leave such a group and cannot
    return, because the destination is not a project. That validation is right;
    what was missing is a way back in, and this is the list that offers it.

    Counted from the stores that own the things, so the numbers are what
    adoption would actually claim rather than an estimate. A group is reported
    whether it holds files, facts, or both — a project whose only trace is a
    handful of facts is exactly the one that is hardest to find by hand.
    """
    counts: Dict[str, Dict[str, int]] = {}
    for entry in artifact_service.records.projects():
        counts.setdefault(entry["id"], {"artifacts": 0, "facts": 0})
        counts[entry["id"]]["artifacts"] = entry["count"]

    # -1 is not folded into 0 anywhere else this count is shown, and it is not
    # folded here: "no facts" and "the Spine could not say" lead to different
    # decisions, and adoption is about to act on the difference.
    facts_known = True
    try:
        runtime = kernel.memory_runtime
        if runtime is None:
            facts_known = False
        else:
            for project_id, n in (await runtime.project_fact_counts()).items():
                counts.setdefault(project_id, {"artifacts": 0, "facts": 0})
                counts[project_id]["facts"] = n
    except Exception:
        facts_known = False

    unclaimed = [
        {
            "id": project_id,
            "artifacts": n["artifacts"],
            "facts": n["facts"] if facts_known else -1,
        }
        for project_id, n in sorted(counts.items())
        if not project_records.exists(project_id)
    ]
    return {"unclaimed": unclaimed, "facts_counted": facts_known}


class ProjectAdoptRequest(BaseModel):
    """A name and a type for a group that already has contents.

    `name` defaults to the id, which is the honest default: the id is the only
    thing the user ever actually wrote for this group, and inventing a prettier
    name would be Zaram deciding what their work is called.
    """

    name: str = ""
    type: str = "general"


@app.post("/projects/{project_id}/adopt")
async def adopt_project(project_id: str, body: ProjectAdoptRequest):
    """Turn a group that exists only on its contents into a real project.

    **The id is kept exactly.** That is the whole operation — every artifact
    row and every `project:<id>` scope points at this string, and a project
    created under any other id would adopt nothing while looking like it had.
    `ProjectRecords.create` appends a numeric suffix on collision, which is
    right for a user typing a name twice and catastrophic here, so the
    collision is checked and refused rather than resolved.

    Adoption is the creation moment, so it is where the **type** is asked for —
    the one thing rule 7e says the system genuinely cannot infer from behaviour,
    and the choice that activates a pack. It is asked once, here, rather than
    guessed from the files that happen to be in the group.

    Nothing is moved, re-scoped or rewritten. The contents already carry this
    id; what was missing was the record they point at.
    """
    wanted = project_id.strip()
    if not wanted:
        raise HTTPException(status_code=400, detail="No project id given.")

    if project_records.exists(wanted):
        raise HTTPException(
            status_code=409,
            detail=f"{wanted!r} is already a project.",
        )

    # Refuse to adopt a group with nothing in it. Otherwise this is a second
    # create route that lets the caller choose its own id, and the ids it would
    # mint are precisely the ones `slugify` exists to keep readable.
    holds_artifacts = artifact_service.records.count_for_project(wanted) > 0
    holds_facts = False
    try:
        runtime = kernel.memory_runtime
        if runtime is not None:
            holds_facts = await runtime.count_by_scope(project_scope(wanted)) > 0
    except Exception:
        holds_facts = False

    if not (holds_artifacts or holds_facts):
        raise HTTPException(
            status_code=404,
            detail=(
                f"Nothing is grouped under {wanted!r}, so there is nothing to "
                "adopt. Create it as a new project instead."
            ),
        )

    try:
        project = project_records.create(
            body.name.strip() or wanted,
            type=ProjectType(body.type),
            project_id=wanted,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Asserted rather than assumed. If the id ever moved, the caller would get a
    # cheerful 200 for a project that adopted nothing, and the files would still
    # be stranded — the exact failure this route exists to end.
    if project.id != wanted:
        project_records.delete(project.id)
        raise HTTPException(
            status_code=500,
            detail=f"Adoption would have created {project.id!r}, not {wanted!r}.",
        )

    return _project_json(project)


@app.patch("/projects/{project_id}")
async def update_project(project_id: str, body: ProjectUpdateRequest):
    """Rename, retype or annotate. **The id never moves.**

    Facts carry `project:<id>` and artifacts carry `project_id`; re-slugging on
    rename would orphan every one of them.
    """
    try:
        project = project_records.get(project_id)
        if body.name is not None:
            project = project_records.rename(project_id, body.name)
        if body.type is not None:
            project = project_records.set_type(project_id, ProjectType(body.type))
        if body.note is not None:
            project = project_records.set_note(project_id, body.note)
    except UnknownProject:
        raise HTTPException(status_code=404, detail=f"No project called {project_id!r}.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _project_json(project)


@app.delete("/projects/{project_id}")
async def delete_project(project_id: str, contents: str = "keep"):
    """Remove a project. **The caller must say what happens to its contents.**

    `contents=keep` re-scopes the project's facts to global and leaves its files
    where they are, so nothing is lost — only the grouping. This is the default
    because it is the recoverable one.

    `contents=delete` removes the facts too. It is never implicit: a container
    quietly exercising rule 4 on the user's behalf is how someone loses a
    client's rates by tidying a sidebar.

    Files are never deleted by either path. Zaram has no capability to remove a
    file from disk and deliberately never has — that is the operating system's
    job, and a record claiming a file is gone while it sits in the output folder
    is worse than no record.
    """
    if contents not in ("keep", "delete"):
        raise HTTPException(
            status_code=400,
            detail="contents must be 'keep' (re-scope facts to global) or 'delete'.",
        )

    try:
        project = project_records.get(project_id)
    except UnknownProject:
        raise HTTPException(status_code=404, detail=f"No project called {project_id!r}.")

    moved = removed = 0
    try:
        runtime = kernel.memory_runtime
        if runtime is not None:
            if contents == "keep":
                moved = await runtime.rescope_to_global(project.scope)
            else:
                removed = await runtime.forget_scope(project.scope)
    except Exception as exc:
        # The facts are the irreplaceable half. If they cannot be dealt with,
        # the project stays — a half-completed delete that orphans facts under a
        # scope nothing points at is worse than a delete that did not happen.
        raise HTTPException(
            status_code=500,
            detail=f"The project was left in place: its facts could not be {contents}d ({exc}).",
        )

    project_records.delete(project_id)
    return {
        "deleted": project_id,
        "facts_moved_to_global": moved,
        "facts_deleted": removed,
        "files_untouched": artifact_service.records.count_for_project(project_id),
    }


class ArtifactUpdateRequest(BaseModel):
    """`None` means "not mentioned"; `""` means "no project".

    The same distinction the remember override draws, for the same reason: a
    field the caller left out and a field the caller cleared are different
    instructions, and collapsing them makes unassigning indistinguishable from
    forgetting to say.
    """

    project_id: str | None = None


@app.patch("/artifacts/{artifact_id}")
async def update_artifact(artifact_id: str, body: ArtifactUpdateRequest):
    """Move a file into a project, out of one, or between two.

    Assignment lives here rather than at generation time because the decision
    is usually made afterwards: a file exists, and *then* it becomes clear what
    it belongs to. Rule 7h — the offer belongs at the moment of doubt, not as a
    question asked in advance of the work.

    **The destination is checked before the move.** A typo would otherwise
    create a project that exists only as a string on one file: invisible in
    `/projects`, unnameable, undeletable, and carrying facts nothing points at.
    That is the bug `/artifacts/projects` and `/projects` were split to fix, and
    an unvalidated write here would put it straight back.

    Files are only ever re-labelled. Nothing moves on disk — the output
    directory is not a folder tree and a project is not a folder.
    """
    if body.project_id is None:
        raise HTTPException(
            status_code=400,
            detail="Nothing to change. Send project_id, or \"\" to remove it from its project.",
        )

    destination = body.project_id.strip()
    if destination:
        try:
            project_records.get(destination)
        except UnknownProject:
            raise HTTPException(
                status_code=400,
                detail=f"No project called {destination!r}. Create it first.",
            )

    if not artifact_service.records.set_project(artifact_id, destination):
        raise HTTPException(status_code=404, detail="No such artifact")

    return {"id": artifact_id, "project_id": destination}


# Declared here, among the project routes, rather than beside the other
# `/memory` ones: validating the destination needs `project_records`, which is
# imported at the top of this section. The alternative was hoisting that import
# above the whole artifacts block for one route's benefit.
class MemoryScope(BaseModel):
    """Where a fact belongs. `""` means global — about the user, not the work."""

    project_id: str


@app.post("/memory/{record_id}/scope")
async def set_memory_scope(record_id: str, body: MemoryScope):
    """Move a fact between global and a project, or between two projects.

    Rule 7i keeps scope as **one field on one store** precisely so this is a
    move rather than a copy between two stores. It is also the multiplayer
    boundary, which is what makes the direction matter: project memory is
    shareable and global memory never is, so moving a fact *into* a project
    widens who could eventually see it. That has to be the user's decision,
    which is why nothing here infers it.

    Promotion to global stays evidence-driven per rule 7e — a fact recalled
    across three projects is probably about the person, and that is when Zaram
    asks. This route is the answer to that question, and the manual override
    for when the system never asks.
    """
    if not kernel.memory_runtime:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    destination = (body.project_id or "").strip()
    if destination:
        try:
            project_records.get(destination)
        except UnknownProject:
            raise HTTPException(
                status_code=400,
                detail=f"No project called {destination!r}. Create it first.",
            )

    scope = project_scope(destination)
    if not await kernel.memory_runtime.set_scope(record_id, scope):
        raise HTTPException(status_code=404, detail="No such memory")

    return {
        "id": record_id,
        "scope": scope,
        "note": (
            "Facts about you stay global; facts about the work move with the "
            "project. Recall reads both."
        ),
    }


@app.get("/artifacts/formats")
async def list_artifact_formats():
    """Which export formats work on this machine, and why the others do not.

    CLAUDE.md: disabled capabilities are visible, not silent. PDF is expected to
    be unavailable on Windows until the installer carries the GTK runtime, and
    the UI is meant to show that reason rather than hide the option.
    """
    return {
        "formats": [
            {
                "extension": extension,
                "label": artifact_export.get(extension).label,
                "available": availability.ok,
                "reason": availability.reason,
                "remedy": availability.remedy,
            }
            for extension, availability in artifact_export.formats()
        ]
    }


@app.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str, include_html: bool = False):
    artifact = artifact_service.records.get(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="No such artifact")

    return _artifact_json(artifact, include_html=include_html)


@app.get("/artifacts/{artifact_id}/download")
async def download_artifact(artifact_id: str):
    """The file itself.

    The path comes from the record, not from the request, so there is nothing
    user-controlled in it — but it is still checked for containment before being
    served. The store confines every write to the output root; this asserts the
    same thing on the way out, because a record written by an older build is an
    input this endpoint does not control.
    """
    artifact = artifact_service.records.get(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="No such artifact")
    if not artifact.path:
        raise HTTPException(status_code=404, detail="No file was written")

    resolved = os.path.abspath(artifact.path)
    root = os.path.abspath(str(artifact_service.store.root))
    if os.path.commonpath([resolved, root]) != root:
        raise HTTPException(status_code=403, detail="Outside the output directory")
    if not os.path.isfile(resolved):
        # The record exists and the file does not. Say which, rather than a bare
        # 404 that reads as "no such document" — the user may have moved it, and
        # that is a different problem from Zaram having lost it.
        raise HTTPException(
            status_code=410,
            detail="The record is here but the file is not at the path it was written to",
        )

    exporter_media = {
        e: artifact_export.get(e).media_type for e in artifact_export.EXPORTERS
    }
    extension = os.path.splitext(resolved)[1].lstrip(".").lower()

    return FileResponse(
        resolved,
        media_type=exporter_media.get(extension, "application/octet-stream"),
        filename=artifact.filename,
    )


class GenerateClaim(BaseModel):
    id: str
    source_id: str
    excerpt: str
    source_excerpt: str = ""
    source_revision: str | None = None


class GenerateSource(BaseModel):
    kind: str
    url: str | None = None
    title: str | None = None


class GenerateLineItem(BaseModel):
    description: str
    #: Strings, so JSON's single double-precision number type cannot round the
    #: money before it reaches the Decimal that is supposed to protect it.
    quantity: str = "1"
    unit_price: str
    unit: str = ""


class GenerateAdjustment(BaseModel):
    """A named amount after the subtotal — tax, discount, deposit held.

    `label` is the user's word for it and is printed as given. Zaram does not
    know whether this is VAT or GST, does not decide whether it applies, and
    holds no table of rates: CLAUDE.md forbids computing tax liability. Summing
    what someone tells you is bookkeeping; deciding it is advice.
    """

    label: str
    rate: str | None = None
    amount: str | None = None


class GenerateSlide(BaseModel):
    """One slide: a heading and its bullets.

    A heading with no bullets is kept — it is a section marker, and dropping it
    loses the deck's structure.
    """

    heading: str
    bullets: list[str] = []


def _document_block(block: Any, by_id: dict[str, Any]) -> Any:
    """One request block as something `render_document` understands.

    The vocabulary is deliberately the one `export/_reader.py` already parses —
    `h2`/`h3`, `li`, `table` — so a structured document exports to .docx and
    .pptx through the readers that were built for it and were, until now, being
    fed nothing but paragraphs.

    Three shapes, and the order matters:

    * a **string** is a paragraph, unchanged, and is the common case;
    * an object carrying `claim_id` is a cited sentence, unchanged;
    * an object carrying `type` is structure.

    An unrecognised `type` is a 400 rather than a paragraph. Silently rendering
    a block the caller meant as a table into a line of prose produces a
    document that is wrong in a way its author cannot see — which is the
    failure rule 9 exists to prevent, arriving through the request body instead
    of through the model.
    """
    from artifacts.contracts import BulletList, Heading, PageBreak, TableBlock

    if not isinstance(block, dict):
        return str(block)

    kind = block.get("type")
    if kind is None:
        claim_id = block.get("claim_id") or block.get("id")
        if claim_id not in by_id:
            raise HTTPException(
                status_code=400,
                detail=f"block cites claim {claim_id!r}, which is not in claims",
            )
        return by_id[claim_id]

    if kind in ("paragraph", "p", "text"):
        return str(block.get("text", ""))

    if kind in ("heading", "h2", "h3"):
        level = block.get("level", 3 if kind == "h3" else 2)
        try:
            return Heading(text=str(block.get("text", "")), level=int(level))
        except (ValueError, TypeError) as exc:
            # `Heading` refuses level 1 by construction: h1 is the title. The
            # message it raises is written for a person and goes back unchanged.
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if kind in ("list", "ul", "ol"):
        items = [
            by_id[i["claim_id"]]
            if isinstance(i, dict) and i.get("claim_id") in by_id
            else str(i.get("text", "") if isinstance(i, dict) else i)
            for i in block.get("items", [])
        ]
        return BulletList(items=items, ordered=bool(block.get("ordered", kind == "ol")))

    if kind == "table":
        return TableBlock(
            header=[str(h) for h in block.get("header", [])],
            rows=[[str(c) for c in row] for row in block.get("rows", [])],
            caption=str(block.get("caption", "")),
            numeric_columns=[int(i) for i in block.get("numeric_columns", [])],
        )

    if kind in ("pagebreak", "page_break"):
        return PageBreak()

    raise HTTPException(
        status_code=400,
        detail=(
            f"unknown block type {kind!r}. Known types: paragraph, heading, "
            "list, table, pagebreak"
        ),
    )


class GenerateMeta(BaseModel):
    """One label/value pair in the scan-first block under the masthead.

    A list of pairs rather than named fields, for the reason `_meta_block`
    records: the fields differ by document and by country, and a schema written
    here would be wrong somewhere.
    """

    label: str = ""
    value: str = ""


class GenerateBody(BaseModel):
    title: str
    #: The document's content, in order.
    #:
    #: A string is a plain paragraph. An object with a matching claim id is a
    #: sentence traceable to a fact and gets an anchor. An object with a
    #: `type` is structure — see `_document_block` for the vocabulary.
    blocks: list[Any] = []
    #: The document body as markdown, which is what a model writes when asked
    #: for a proposal. Converted to the same blocks `blocks` carries, so this
    #: is a second *input* form and not a second document model.
    #:
    #: Mutually exclusive with `blocks`: supplying both is refused rather than
    #: resolved by precedence, because a caller that sent both had two
    #: intentions and picking one silently discards the other.
    markdown: str = ""
    #: Label/value pairs under the masthead: reference, dates, parties.
    meta: list[GenerateMeta] = []
    #: What kind of document this is, set small and uppercase opposite the
    #: letterhead: "Proposal", "Report", "Statement of Work".
    kind_label: str = ""
    #: Print the Sources section into the file itself. Off by default, because
    #: a document is written for its recipient and a client has no use for
    #: `memory:55b6` at the foot of it. On for the genres where citation is
    #: part of the form.
    include_provenance: bool = False
    kind: str = "document"
    fmt: str | None = None
    filename: str = ""
    project_id: str = ""
    conversation_id: str = ""
    conversation_title: str = ""
    sources: list[GenerateSource] = []
    claims: list[GenerateClaim] = []
    # Spreadsheet only.
    header: list[str] = []
    rows: list[list[Any]] = []
    caption: str = ""
    # Deck only. The outline: one heading per slide, bullets beneath it. Not a
    # second authoring path — the exporter splits any document on its headings,
    # and this is only how a caller says "I meant slides" so `.pptx` is the
    # default format and the preview is the outline.
    slides: list[GenerateSlide] = []
    # Invoice only.
    #
    # Amounts are strings, not floats. JSON has one number type and it is a
    # double, so `"unit_price": 0.1` arrives as 0.1000000000000000055…, and an
    # invoice built from that cannot be reconciled by hand. `invoice.py` refuses
    # a float rather than converting one; keeping the wire type a string is what
    # makes that refusal reachable instead of a 500 nobody can act on.
    items: list[GenerateLineItem] = []
    adjustments: list[GenerateAdjustment] = []
    number: str = ""
    #: ISO date. Defaults to today, which is what "make me an invoice" means.
    issued: str = ""
    #: Days from issue until payment is due. Produces both the printed terms
    #: sentence and the Due date, from one number, so they cannot disagree.
    terms_days: int | None = None
    currency: str = ""
    bill_to: list[str] = []
    notes: str = ""
    payment: list[str] = []
    #: The masthead — who the invoice is from. Optional: with nothing supplied
    #: the document is still titled and ruled rather than a bare heading, which
    #: is why the absence of branding does not read as a rendering failure.
    from_name: str = ""
    from_lines: list[str] = []


@app.post("/artifacts/generate")
async def generate_artifact(body: GenerateBody):
    """Make a document, spreadsheet or chart, and record it.

    The seam between "a model produced some prose" and "the user has a file".
    Generative tier: it creates new artifacts and changes nothing that already
    exists, so it needs no undo, no sandbox and no confirmation — the safety is
    structural. Files land in one output directory, the write path cannot
    overwrite or delete, and a name collision increments.

    Not yet reachable from natural language. Saying "write that up as a
    proposal" in chat does not trigger this — that needs a capability registered
    with the router, which is separate work. This endpoint is the thing that
    capability will call.
    """
    from datetime import date

    from artifacts import invoice as invoice_module
    from artifacts.contracts import ArtifactKind, ArtifactSource, Claim
    from artifacts.letterhead import Letterhead

    try:
        kind = ArtifactKind(body.kind)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown kind {body.kind!r}; use one of "
            f"{[k.value for k in ArtifactKind]}",
        ) from None

    if body.fmt:
        try:
            availability = artifact_export.get(body.fmt).availability()
        except KeyError:
            raise HTTPException(
                status_code=400, detail=f"No exporter for {body.fmt!r}"
            ) from None
        if not availability.ok:
            # 503, not 500: the request is fine and the machine cannot serve it.
            # The reason and the remedy go back so the UI can say which.
            raise HTTPException(
                status_code=503,
                detail={
                    "reason": availability.reason,
                    "remedy": availability.remedy,
                },
            )

    # The same check `PATCH /artifacts/{id}` makes, at the other end of the same
    # hole. Assignment validated its destination and creation did not, so a file
    # could be *born* into a project that does not exist while being forbidden
    # from moving into one — and the ghost groups on this machine, `harbour` and
    # `northwind`, arrived exactly this way. Refusing here costs a 400 before
    # anything is written; not refusing costs a file nothing can regroup.
    if body.project_id.strip() and not project_records.exists(body.project_id.strip()):
        raise HTTPException(
            status_code=400,
            detail=f"No project called {body.project_id.strip()!r}. Create it first.",
        )

    sources = [ArtifactSource(**s.model_dump()) for s in body.sources]
    claims = [Claim(**c.model_dump()) for c in body.claims]
    by_id = {c.id: c for c in claims}

    common = dict(
        title=body.title,
        filename=body.filename,
        project_id=body.project_id,
        conversation_id=body.conversation_id,
        conversation_title=body.conversation_title,
        sources=sources,
        claims=claims,
    )

    try:
        if kind == ArtifactKind.INVOICE:
            artifact = artifact_service.create_invoice(
                items=[
                    invoice_module.line_item(
                        description=i.description,
                        quantity=i.quantity,
                        unit_price=i.unit_price,
                        unit=i.unit,
                    )
                    for i in body.items
                ],
                adjustments=[
                    invoice_module.Adjustment(
                        label=a.label,
                        rate=invoice_module.to_decimal(a.rate, field_name=f"rate for {a.label!r}")
                        if a.rate is not None
                        else None,
                        amount=invoice_module.to_decimal(
                            a.amount, field_name=f"amount for {a.label!r}"
                        )
                        if a.amount is not None
                        else None,
                    )
                    for a in body.adjustments
                ],
                number=body.number,
                issued=date.fromisoformat(body.issued) if body.issued else None,
                terms_days=body.terms_days,
                currency=body.currency,
                bill_to=body.bill_to,
                notes=body.notes,
                payment=body.payment,
                # Supplied per request, not read from a store, because **where
                # branding is captured is an open decision** (see MILESTONES,
                # "Where branding is captured — decided, not yet built"). A
                # request field commits to nothing: when capture lands, this
                # becomes its default rather than a second source of truth.
                letterhead=(
                    Letterhead(name=body.from_name, lines=body.from_lines)
                    if (body.from_name or body.from_lines)
                    else None
                ),
                fmt=body.fmt,
                **common,
            )
        elif kind == ArtifactKind.DECK:
            artifact = artifact_service.create_deck(
                slides=[(s.heading, s.bullets) for s in body.slides],
                subtitle=body.caption,
                fmt=body.fmt,
                **common,
            )
        elif kind == ArtifactKind.SPREADSHEET:
            artifact = artifact_service.create_spreadsheet(
                header=body.header, rows=body.rows, caption=body.caption,
                fmt=body.fmt, **common
            )
        else:
            # A block naming a claim becomes that claim, so the anchor and the
            # Sources entry agree. A block naming one that was not supplied is
            # rejected rather than silently written as plain prose — an
            # unanchored sentence that was meant to be cited is the failure the
            # whole provenance chain exists to prevent.
            if body.markdown and body.blocks:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "send either `markdown` or `blocks`, not both — they "
                        "are two ways of saying the same thing"
                    ),
                )

            if body.markdown:
                from artifacts.markdown_blocks import blocks_from_markdown

                blocks: list[Any] = blocks_from_markdown(
                    body.markdown, title=body.title
                )
            else:
                blocks = [_document_block(b, by_id) for b in body.blocks]

            artifact = artifact_service.create_document(
                blocks=blocks,
                kind=kind,
                fmt=body.fmt,
                letterhead=(
                    Letterhead(name=body.from_name, lines=body.from_lines)
                    if (body.from_name or body.from_lines)
                    else None
                ),
                meta=[(m.label, m.value) for m in body.meta if m.label and m.value],
                kind_label=body.kind_label,
                include_provenance=body.include_provenance,
                **common,
            )
    except HTTPException:
        raise
    except invoice_module.InvoiceIncomplete as exc:
        # 400, not 500. Rule 9 refusals are the caller being told what is
        # missing — "an invoice needs at least one line" is actionable, and a
        # 500 would present a deliberate, correct refusal as a crash. The
        # message is written for a person and goes back unchanged.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        # Chiefly `date.fromisoformat` on a malformed `issued`. Same reasoning.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    print(f"[Artifacts] Wrote {artifact.filename} ({artifact.size_bytes} bytes)")
    return _artifact_json(artifact)


class RememberBody(BaseModel):
    remember: bool | None = None


@app.post("/artifacts/{artifact_id}/remember")
async def set_artifact_remember(artifact_id: str, body: RememberBody):
    """The "Don't remember this" override on a file card.

    `null` clears the override rather than setting it to false: "I have not
    decided" and "no" are different answers, and only the first is allowed to be
    changed later by a default.
    """
    if not artifact_service.records.set_remember_override(artifact_id, body.remember):
        raise HTTPException(status_code=404, detail="No such artifact")

    return {"id": artifact_id, "remember_override": body.remember}


# --------------------------------------------------------------------------- #
# Export — rule 7, which had been written and could not be reached.
#
# `core/export.py` builds the whole thing: facts as JSONL with their correction
# history, the egress log, obligations, a manifest naming what is absent and
# why. Twenty assertions cover it in `tests/test_export.py`. It had **no
# caller, no route, and no control in Settings** — the sixth complete, tested,
# unreachable feature this repo has found, and the one that mattered most,
# because rule 7 is the promise that leaving is cheap.
#
# A .zip rather than a directory: one file is a thing a person can move to a
# drive, and it is what `build/installer.nsh` hands back on uninstall. That
# uninstall path used to zip the raw SQLite files — technically an open format,
# and not what "in open formats you can read without Zaram installed" means to
# somebody who opens it and finds four databases.
# --------------------------------------------------------------------------- #


@app.get("/export")
async def export_everything():
    """Hand back everything Zaram holds, in formats that outlive it.

    Streams a .zip. Nothing is deleted and nothing changes — export is a read,
    and a user checking whether they *could* leave must not have to risk
    anything to find out.

    **A section that cannot be built is named, not omitted.** A missing file in
    an export reads as "Zaram has nothing of mine there", which on a memory
    product is the one wrong impression worth engineering against. Each store
    is asked separately and a failure adds a line to the manifest rather than
    failing the export — a Spine that exports without its egress log is far
    better than no export at all.
    """
    import io
    import zipfile

    from core.export import build_export

    facts: list[Any] = []
    egress_entries: list[Dict[str, Any]] = []
    obligations: list[Dict[str, Any]] = []
    generated_files: list[str] = []
    unavailable: list[str] = []

    try:
        if kernel.memory_runtime is None:
            raise RuntimeError("memory runtime not available")
        # include_superseded: the corrections are the point. An export of only
        # what Zaram currently believes discards the record of where it was
        # wrong and the user said so, which is rule 4's more interesting half.
        facts = await kernel.memory_runtime._store.all_records(include_superseded=True)
    except Exception:
        unavailable.append("Stored facts — the memory runtime could not be read")

    try:
        from core.egress import get_gate

        gate = get_gate()
        egress_entries = [
            {
                "at": e.at,
                "host": e.host,
                "method": e.method,
                "url": e.url,
                "bytes": e.byte_count,
                "decision": e.decision,
                "reason": e.reason,
                "source": e.source,
            }
            for e in gate.log.entries(limit=gate.log.count() or 1, offset=0)
        ]
    except Exception:
        unavailable.append("Egress log — the record of what left could not be read")

    try:
        generated_files = [
            a.path for a in artifact_service.records.list(limit=10_000) if a.path
        ]
    except Exception:
        unavailable.append("Generated documents — the artifact records could not be read")

    # Obligations have no store yet, so this is honest rather than empty: the
    # manifest says the section is absent and why, instead of shipping a CSV of
    # headers that reads as "you have no deadlines".
    unavailable.append(
        "Obligations — extracted per document, not yet persisted, so there is "
        "nothing to export"
    )

    documents = build_export(
        facts=facts,
        egress_entries=egress_entries,
        obligations=obligations,
        generated_files=generated_files,
        unavailable=unavailable,
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for document in documents:
            archive.writestr(document.name, document.content)
    buffer.seek(0)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="zaram-export-{stamp}.zip"',
        },
    )


@app.get("/export/manifest")
async def export_manifest():
    """What an export would contain, without building one.

    Settings shows this before the download so the button is not a leap. It is
    also what makes "obligations are not exportable yet" visible at the moment
    somebody is deciding whether they can leave, rather than after they have
    unzipped the file.
    """
    from core.export import EXPORT_FORMAT_VERSION

    facts = 0
    try:
        if kernel.memory_runtime is not None:
            records = await kernel.memory_runtime._store.all_records(include_superseded=True)
            facts = len(records)
    except Exception:
        facts = -1

    entries = 0
    try:
        from core.egress import get_gate

        entries = get_gate().log.count()
    except Exception:
        entries = -1

    documents = 0
    try:
        documents = artifact_service.records.count()
    except Exception:
        documents = -1

    return {
        "format_version": EXPORT_FORMAT_VERSION,
        # -1 means "could not be counted", which is not zero. A zero on this
        # screen is a claim that the user has nothing.
        "facts": facts,
        "egress_entries": entries,
        "generated_documents": documents,
        "formats": ["JSONL", "CSV", "JSON"],
        "note": (
            "Everything is written in open formats. JSONL and CSV open in any "
            "text editor or spreadsheet, with no Zaram installed."
        ),
    }


# --- Ingest -------------------------------------------------------------- #
#
# Knowledge reads these. The service already produced a reason and a remedy per
# file; without somewhere to read them from, "failures must be loud" reduces to
# whether anyone happened to be watching the response stream.

from ingest.records import IngestRecords  # noqa: E402
from ingest.service_api import IngestService, default_db_path as ingest_db_path  # noqa: E402

from obligations.records import (  # noqa: E402
    ObligationRecords,
    default_db_path as obligations_db_path,
)

from attachments import (  # noqa: E402
    AttachmentError,
    AttachmentStore,
    compose as compose_attachments,
)

#: Files attached to a conversation. Working state, cleared at startup.
#:
#: Deliberately not built from `IngestRecords` and deliberately not sharing a
#: store with the Spine. Rule 7d: entering long-term memory is a decision the
#: system makes, and dragging a file onto a message box is not that decision.
attachment_store = AttachmentStore()

#: Commitments read out of the documents the user ingests.
#:
#: Built here rather than inside `IngestService` so that a build without it
#: still indexes. Indexing a document and reading its deadlines are two
#: capabilities, and doing the half you can beats doing neither.
obligation_records = ObligationRecords(obligations_db_path())

ingest_service = IngestService(
    IngestRecords(ingest_db_path()), obligations=obligation_records
)


# --------------------------------------------------------------------------- #
# Attachments — the files one message is about.
#
# Separate from `/ingest` on purpose, and the separation is rule 7d rather than
# tidiness. `/ingest` adds a document to the Spine, where it is indexed,
# recalled and cited for as long as the user keeps it. These routes hold a file
# for the conversation it was dropped into and no longer: parsed, used, and
# then offered. Someone asking one question about a contract has not decided to
# add it to their knowledge base, and treating those as the same act fills the
# Spine with things people looked at once — which is the store that stops being
# worth searching.
#
# `POST /chat/attachments/{id}/keep` is where the two meet, and it is the only
# place they do: it hands the same bytes to the ordinary ingest path and
# produces an ordinary source, with the user having said so.
# --------------------------------------------------------------------------- #


@app.post("/chat/attachments")
async def add_chat_attachments(
    session_id: str = Form("default"),
    files: list[UploadFile] = File(...),
):
    """Parse files for this conversation and hold them.

    The bytes are read here rather than inside a streamed body, for the reason
    `/ingest/upload` records: a `StreamingResponse` runs after the endpoint
    returns, by which point the temporary files behind `UploadFile` may be
    gone. This one answers in a single response anyway — a composer chip needs
    the whole result before it can be drawn.

    Refusals are per file and do not fail the request. Dropping four files of
    which one is a screenshot should attach three and say why the fourth did
    not, rather than refusing all four and naming none of them.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files were sent.")

    attached: list[dict] = []
    refused: list[dict] = []
    evicted: list[dict] = []

    for upload in files:
        name = upload.filename or ""
        try:
            data = await _read_capped(upload)
        except HTTPException as exc:
            refused.append({"name": name, "reason": str(exc.detail)})
            continue
        try:
            item, dropped = attachment_store.add(session_id, name, data)
        except AttachmentError as exc:
            refused.append({"name": name, "reason": str(exc)})
            continue
        except OSError as exc:
            refused.append({"name": name, "reason": f"Could not keep that file: {exc}"})
            continue
        attached.append(item.to_dict())
        evicted.extend(d.to_dict() for d in dropped)

    return {
        "attached": attached,
        "refused": refused,
        # What was dropped to make room, named rather than silent. An
        # attachment that disappeared without being mentioned would leave the
        # user believing a document is in scope when it is not.
        "evicted": evicted,
    }


@app.get("/chat/attachments")
async def list_chat_attachments(session_id: str = "default"):
    """What this conversation currently holds."""
    return {"attachments": [a.to_dict() for a in attachment_store.for_session(session_id)]}


@app.delete("/chat/attachments/{attachment_id}")
async def remove_chat_attachment(attachment_id: str):
    """Detach one. The bytes go with it — this was never storage."""
    if not attachment_store.remove(attachment_id):
        raise HTTPException(status_code=404, detail="That file is not attached.")
    return {"removed": attachment_id}


@app.post("/chat/attachments/{attachment_id}/keep")
async def keep_chat_attachment(attachment_id: str):
    """Add an attached file to Knowledge, because the user said so.

    Rule 7d's other half. The file goes through the ordinary ingest path and
    becomes an ordinary source — indexed, policied, correctable, removable —
    rather than being promoted by some second mechanism that would then need
    its own correction loop.

    It stays attached afterwards. The question being asked about it is not
    over, and detaching it as a side effect of keeping it would take the
    document out of the conversation at the moment the user said it mattered.
    """
    item = attachment_store.get(attachment_id)
    if item is None:
        raise HTTPException(status_code=404, detail="That file is not attached.")

    source = Path(item.path)
    if not source.exists():
        raise HTTPException(
            status_code=409,
            detail="The file is no longer on disk, so it cannot be kept. Attach it again.",
        )

    try:
        saved = ingest_service.save_upload(item.name, source.read_bytes())
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail=f"Could not keep that file: {exc.strerror or exc}"
        ) from exc

    return _stream_paths([saved])


# --------------------------------------------------------------------------- #
# Obligations — commitments read out of the user's own documents.
#
# The extractor and its contracts had 28 green tests and no caller outside
# them. These routes plus the ingest seam are what make the package reachable;
# without them it is the eighteenth complete, tested, unreachable subsystem.
#
# Two rules shape every endpoint below, and both come from CLAUDE.md.
#
# **Never silently create a commitment.** A missed deadline is bad and an
# invented one is worse, because the user reorganises their week around it and
# only discovers it was never in the contract when they go looking for the
# clause. So every obligation returned carries its source clause, and a clause
# that could not be dated is returned as a *question* rather than anchored to
# a guess.
#
# **It is not a calendar.** These endpoints report and correct. Nothing here
# schedules, notifies, or writes to anything outside the obligations store.
# --------------------------------------------------------------------------- #


@app.get("/obligations")
async def list_obligations(scope: str = "", include_closed: bool = False):
    """Live commitments, soonest first, each with the clause it was read from.

    `include_closed` returns dismissed and met ones as well. That is not an
    administrative nicety: a product that claims to be correctable has to be
    able to show the user what they corrected, or "you can dismiss this" is a
    promise with no way to audit it.
    """
    records = (
        obligation_records.all_obligations()
        if include_closed
        else obligation_records.open_obligations(scope=scope)
    )
    return {
        "obligations": records,
        "questions": obligation_records.open_questions(),
    }


@app.get("/obligations/{obligation_id}")
async def get_obligation(obligation_id: str):
    record = obligation_records.get(obligation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No such obligation")
    return record


class ObligationCorrection(BaseModel):
    """What the user is changing. Absent fields are left alone.

    The source clause is deliberately not among them. A correction says Zaram
    read the sentence wrongly, not that the sentence was different, and letting
    a caller rewrite the clause would break the one guarantee this package
    makes.
    """

    #: ISO date.
    due: str | None = None
    summary: str | None = None
    #: A string, not a float. JSON has one number type and it is a double, so
    #: `0.1` arrives as 0.1000000000000000055 — the same reasoning the invoice
    #: line items already follow.
    amount: str | None = None
    currency: str | None = None
    #: `owed_by_user` or `owed_to_user`. This is the field the extractor
    #: deliberately refuses to guess, so it is the one a user most often sets.
    direction: str | None = None


@app.post("/obligations/{obligation_id}/correct")
async def correct_obligation(obligation_id: str, body: ObligationCorrection):
    """Replace an obligation with a corrected one. Rule 4.

    The original is superseded rather than deleted and stays readable, so "what
    did Zaram think last week" remains answerable and the correction is a
    visible event rather than a field changing underneath the interface.
    """
    from datetime import date as _date
    from decimal import Decimal, InvalidOperation

    from obligations.contracts import Direction

    parsed_due = None
    if body.due:
        try:
            parsed_due = _date.fromisoformat(body.due)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"due must be an ISO date: {exc}"
            ) from exc

    parsed_amount = None
    if body.amount:
        try:
            parsed_amount = Decimal(body.amount)
        except (InvalidOperation, ValueError) as exc:
            raise HTTPException(
                status_code=400, detail=f"amount is not a number: {body.amount!r}"
            ) from exc

    parsed_direction = None
    if body.direction:
        try:
            parsed_direction = Direction(body.direction)
        except ValueError as exc:
            allowed = ", ".join(d.value for d in Direction)
            raise HTTPException(
                status_code=400, detail=f"direction must be one of: {allowed}"
            ) from exc

    corrected = obligation_records.correct(
        obligation_id,
        due=parsed_due,
        summary=body.summary,
        amount=parsed_amount,
        currency=body.currency,
        direction=parsed_direction,
    )
    if corrected is None:
        raise HTTPException(
            status_code=404, detail="No such obligation, or it was already superseded"
        )
    return corrected


@app.post("/obligations/{obligation_id}/dismiss")
async def dismiss_obligation(obligation_id: str):
    """Say this was never an obligation.

    Stored, not deleted. Deleting would mean the next ingest of the same
    document extracts the same clause and asks again, which teaches the user
    that correcting Zaram does not stick.
    """
    if not obligation_records.dismiss(obligation_id):
        raise HTTPException(
            status_code=404, detail="No such obligation, or it was already superseded"
        )
    return obligation_records.get(obligation_id)


@app.post("/obligations/{obligation_id}/met")
async def complete_obligation(obligation_id: str):
    """Mark it done. Distinct from dismissing: it was real, and it happened."""
    if not obligation_records.mark_met(obligation_id):
        raise HTTPException(
            status_code=404, detail="No such obligation, or it was already superseded"
        )
    return obligation_records.get(obligation_id)


class QuestionAnswer(BaseModel):
    #: The date the relative term counts from — an invoice's issue date, a
    #: contract's signature date. ISO.
    anchor: str


@app.post("/obligations/questions/{question_id}/answer")
async def answer_obligation_question(question_id: str, body: QuestionAnswer):
    """Supply what was missing, and turn a clause into a dated commitment.

    This is the shape of rule 9 in this feature. Extraction that cannot pin a
    date down neither drops the clause nor guesses at it — it asks, and this is
    where the answer arrives. A 409 means the anchor was accepted and still did
    not settle it, so the question stays open rather than being closed on a
    date nobody could produce.
    """
    from datetime import date as _date

    try:
        anchor = _date.fromisoformat(body.anchor)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"anchor must be an ISO date: {exc}"
        ) from exc

    created = obligation_records.answer_question(question_id, anchor=anchor)
    if created is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "That date did not resolve the clause, so it has been left as a "
                "question rather than closed on a guess."
            ),
        )
    return created

class IngestBody(BaseModel):
    path: str


class PasteBody(BaseModel):
    text: str
    name: str = ""


class PolicyBody(BaseModel):
    policy: str


#: The largest single file a drop or upload will accept, per file.
#:
#: A cap rather than a truncation. Reading the first 100 MB of a 400 MB file
#: and indexing it would produce a source that answers confidently from half a
#: document, which is rule 9's failure arriving by the back door — the document
#: is *there*, so nothing looks missing. Refusing names the problem instead.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


@app.post("/ingest")
async def start_ingest(body: IngestBody):
    """Index a folder, streaming one event per file as it is read.

    NDJSON on the same pattern as `/chat`, because the frontend already parses
    it and a second streaming format would be a second set of split-chunk bugs.

    Progress is per *file*, not a percentage: a bar that stops at 90% says
    nothing about which document is missing, and the name plus what happened to
    it is the only part the user can act on.
    """
    ingest_service.attach_memory(getattr(kernel, "memory_runtime", None))

    def _stream():
        for event in ingest_service.stream_scan(body.path):
            yield json.dumps(event) + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


async def _read_capped(upload: UploadFile) -> bytes:
    """Read one uploaded file, refusing rather than buffering without a bound.

    Chunked so that the cap is enforced on the way in. `await upload.read()`
    with no argument would hold the whole body in memory *before* anything got
    to check how big it was, which makes the limit decorative.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1 << 20)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"{upload.filename or 'That file'} is larger than "
                    f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB. Point Zaram at the "
                    "folder it lives in instead."
                ),
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _stream_paths(paths: list[Path]):
    """The NDJSON body for a drop, a paste or an upload.

    One shape for all three, and the same shape `/ingest` already emits, so the
    interface parses one stream format rather than three.
    """
    ingest_service.attach_memory(getattr(kernel, "memory_runtime", None))

    def _generate():
        for event in ingest_service.stream_ingest_paths(paths):
            yield json.dumps(event) + "\n"

    return StreamingResponse(_generate(), media_type="application/x-ndjson")


@app.post("/ingest/upload")
async def ingest_upload(files: list[UploadFile] = File(...)):
    """Dropped or chosen files, kept and indexed.

    **The bytes are written before a single event is streamed.** A
    `StreamingResponse` body runs after the endpoint returns, by which point
    the request — and the temporary files behind `UploadFile` — may be gone.
    Reading inside the generator would work on a small local test and lose
    files under any real load, which is the class of bug this codebase keeps
    paying for.

    They land in one uploads directory rather than beside wherever they came
    from, because a source row is a *place* and rule 5 asks about a place once.
    See `UPLOADS_DIRNAME`.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files were sent.")

    saved: list[Path] = []
    try:
        for upload in files:
            data = await _read_capped(upload)
            try:
                saved.append(ingest_service.save_upload(upload.filename or "", data))
            except OSError as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Could not keep {upload.filename or 'the file'}: {exc.strerror or exc}",
                ) from exc
    except HTTPException:
        # **All or none.** The tenth file being too large would otherwise leave
        # the first nine on disk with nothing recording them — bytes in the
        # uploads directory that no source row mentions, no answer can cite and
        # no "delete this source" can reach, and a re-drop would land beside
        # them as "invoice (2).pdf". Only this request's own writes are undone.
        for path in saved:
            try:
                path.unlink()
            except OSError:
                logging.warning("Ingest: could not clean up %s", path)
        raise

    return _stream_paths(saved)


@app.post("/ingest/text")
async def ingest_text(body: PasteBody):
    """Pasted text, written as a file and read by the same parser as any other.

    It could go straight into the Spine without touching the disk. It does not,
    because that would be a second ingest path with its own chunking and its
    own way of going wrong — and because a fact whose provenance is "something
    pasted once" cannot be shown, corrected at source, or removed with its
    source under rule 4.
    """
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="There was nothing in that.")

    try:
        path = ingest_service.save_text(body.text, body.name)
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail=f"Could not keep that text: {exc.strerror or exc}"
        ) from exc

    return _stream_paths([path])


@app.get("/ingest/sources")
async def list_ingest_sources():
    """Every folder the user has pointed at, with its counts.

    `staged` says whether this source is Zaram's own uploads directory, so the
    interface can warn that withdrawing it deletes documents. Answered here
    rather than inferred from the folder's name in the frontend — a source
    called "uploads" somewhere on the user's disk is not this one.
    """
    sources = ingest_service.records.sources()
    for source in sources:
        source["staged"] = ingest_service.is_staged_source(source["root"])
    return {"sources": sources}


@app.get("/ingest/outcomes")
async def list_ingest_outcomes(source_id: str = "", problems_only: bool = False):
    """What happened to each file. The list Knowledge shows."""
    return {
        "outcomes": ingest_service.records.outcomes(
            source_id=source_id or None, problems_only=problems_only
        )
    }


@app.post("/ingest/outcomes/{outcome_id}/retry")
async def retry_ingest_outcome(outcome_id: str):
    """Re-read one file.

    Offered on every visible problem, because the commonest reason a file
    failed is that it was open in Word at the time — and a failure the user
    cannot act on is just bad news.
    """
    ingest_service.attach_memory(getattr(kernel, "memory_runtime", None))
    outcome = ingest_service.retry(outcome_id)
    if outcome is None:
        raise HTTPException(status_code=404, detail="No such outcome")
    return outcome


@app.post("/ingest/sources/{source_id}/policy")
async def set_ingest_policy(source_id: str, body: PolicyBody):
    """Rule 5: per-source, default deny."""
    try:
        changed = ingest_service.records.set_policy(source_id, body.policy)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not changed:
        raise HTTPException(status_code=404, detail="No such source")
    return {"id": source_id, "policy": body.policy}


@app.delete("/ingest/sources/{source_id}")
async def remove_ingest_source(source_id: str):
    """Withdraw a folder: its facts out of the Spine, and Zaram's own copies off
    the disk.

    Rule 4: the user can delete any stored fact and the affected answers
    change. Removing the folder while leaving its facts recallable would be the
    rule failing quietly, which is worse than not offering removal at all.

    **`files_deleted` counts only copies Zaram made.** A dropped or pasted
    document is staged under the uploads directory, and that copy is Zaram's —
    the user's original is wherever they dragged it from. A scanned folder holds
    their originals and nothing there is ever touched. `IngestService.withdraw`
    is where that distinction lives and why.
    """
    outcome = ingest_service.withdraw(source_id)
    if outcome is None:
        raise HTTPException(status_code=404, detail="No such source")

    # A withdrawn source leaves every domain that held it. Without this a
    # domain keeps pointing at something that no longer exists, and the count
    # beside its name counts a source that is gone.
    knowledge_domains.forget_source(source_id)

    fact_ids = outcome["fact_ids"]
    forgotten = 0
    runtime = getattr(kernel, "memory_runtime", None)
    if runtime is not None:
        for fact_id in fact_ids:
            try:
                if await runtime.forget(fact_id):
                    forgotten += 1
            except Exception:
                print(f"[Ingest] could not forget {fact_id}")
    return {
        "id": source_id,
        "facts_removed": forgotten,
        "facts_recorded": len(fact_ids),
        "files_deleted": outcome["files_deleted"],
    }


@app.delete("/ingest/outcomes/{outcome_id}")
async def remove_ingest_file(outcome_id: str):
    """Remove one file from Knowledge, rather than the source that holds it.

    Rule 4 says the user can delete any stored thing. Until this existed the
    only unit of removal was a whole source, and every dropped or pasted file
    shares one uploads source -- so getting rid of a single image meant
    withdrawing everything ever pasted. That is not the rule being satisfied.

    Same guarantees as withdrawing a source, because they are the same
    machinery: the file's facts leave the Spine, and only a copy *Zaram* made
    is deleted from disk. A scanned folder's file is the user's original and is
    never unlinked -- its row and its facts go, which is what removing it from
    Knowledge honestly means.

    A file that produced no facts is still removable, and that is not a
    no-op worth optimising away: an unsupported PNG has a row, a reason and a
    staged copy on disk, and the user asking for it to be gone means all
    three.
    """
    outcome = ingest_service.withdraw_file(outcome_id)
    if outcome is None:
        raise HTTPException(status_code=404, detail="No such file")

    fact_ids = outcome["fact_ids"]
    forgotten = 0
    runtime = getattr(kernel, "memory_runtime", None)
    if runtime is not None:
        for fact_id in fact_ids:
            try:
                if await runtime.forget(fact_id):
                    forgotten += 1
            except Exception:
                print(f"[Ingest] could not forget {fact_id}")
    return {
        "id": outcome_id,
        "name": outcome["name"],
        "source_id": outcome["source_id"],
        "facts_removed": forgotten,
        "facts_recorded": len(fact_ids),
        "files_deleted": outcome["files_deleted"],
    }


# --- Knowledge domains ---------------------------------------------------- #
#
# A named retrieval scope over the user's own sources. Not a folder: `CLAUDE.md`
# is explicit that if it only groups files it is a filter, and it has to change
# answers. `knowledge/domain_recall.py` is where that happens.
#
# No seventh node. Sources already live inside Knowledge and a domain is how
# Knowledge organises them.

from knowledge.domains import (  # noqa: E402
    DomainError,
    KnowledgeDomains,
    default_db_path as domains_db_path,
)

knowledge_domains = KnowledgeDomains(domains_db_path())


class DomainBody(BaseModel):
    name: str
    description: str = ""


@app.get("/knowledge/domains")
async def list_domains():
    """Every domain, with the sources in each."""
    return {"domains": knowledge_domains.all()}


@app.post("/knowledge/domains")
async def create_domain(body: DomainBody):
    try:
        return knowledge_domains.create(body.name, body.description)
    except DomainError as exc:
        # The store's message is written for a person and names what to fix.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/knowledge/domains/{domain_id}")
async def rename_domain(domain_id: str, body: DomainBody):
    try:
        changed = knowledge_domains.rename(domain_id, body.name, body.description)
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not changed:
        raise HTTPException(status_code=404, detail="No such domain")
    return knowledge_domains.get(domain_id)


@app.delete("/knowledge/domains/{domain_id}")
async def remove_domain(domain_id: str):
    """Delete a domain. **Its sources and their facts stay exactly where they are.**

    One memory, many domains. A domain is a way of looking at what is already
    there, so removing one removes a lens — the opposite of withdrawing a
    source, which does take facts with it. The two sit on the same screen, so
    the difference is worth being explicit about in both places.
    """
    if not knowledge_domains.remove(domain_id):
        raise HTTPException(status_code=404, detail="No such domain")
    return {"id": domain_id, "facts_removed": 0, "sources_removed": 0}


@app.post("/knowledge/domains/{domain_id}/sources/{source_id}")
async def add_source_to_domain(domain_id: str, source_id: str):
    """Put a source in a domain. A source may be in any number at once."""
    if not knowledge_domains.link(domain_id, source_id):
        raise HTTPException(status_code=404, detail="No such domain")
    return knowledge_domains.get(domain_id)


@app.delete("/knowledge/domains/{domain_id}/sources/{source_id}")
async def remove_source_from_domain(domain_id: str, source_id: str):
    knowledge_domains.unlink(domain_id, source_id)
    domain = knowledge_domains.get(domain_id)
    if domain is None:
        raise HTTPException(status_code=404, detail="No such domain")
    return domain


AUDIO_CACHE_DIR = os.path.abspath("audio_cache")


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Serve a generated audio file from the audio cache.

    ``filename`` is user-controlled, so it is confined to the cache directory:
    a bare name only, resolved and checked for containment before any read.
    """
    # Reject anything that is not a plain filename. Starlette decodes %2F, so
    # separators and traversal segments must be rejected explicitly.
    if (
        not filename
        or filename in (".", "..")
        or "/" in filename
        or "\\" in filename
        or "\x00" in filename
        or os.path.isabs(filename)
        or filename != os.path.basename(filename)
    ):
        raise HTTPException(status_code=400, detail="Invalid audio filename")

    file_path = os.path.abspath(os.path.join(AUDIO_CACHE_DIR, filename))

    # Belt and braces: confirm the resolved path is still inside the cache.
    if os.path.commonpath([AUDIO_CACHE_DIR, file_path]) != AUDIO_CACHE_DIR:
        raise HTTPException(status_code=400, detail="Invalid audio filename")

    if os.path.isfile(file_path):
        return FileResponse(file_path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="Audio file not found")


class VoiceSynthesizeRequest(BaseModel):
    text: str
    voice: str = ""
    #: `DEFAULT_PERSONA` rather than the literal, because `_resolve_voice`
    #: compares against it. Spelled here, the two could drift — and the day
    #: they did, every request that named no preset would look like a preset
    #: the user deliberately chose, so its voice would outrank the one they
    #: actually set. The coupling is asserted in `test_voice_resolution.py`.
    persona: str = DEFAULT_PERSONA


class VoiceStreamRequest(BaseModel):
    text: str
    voice: str = ""
    #: Same coupling as above.
    persona: str = DEFAULT_PERSONA


def _resolve_voice(requested: str, persona: str) -> str:
    """Which voice speaks, in the order the user would expect.

    **The user's chosen voice was stored and then ignored — found 19 August
    2026.** `user_settings.voice` is written by the character pane and read
    back by `GET /character`, and nothing else in the product ever consulted
    it: this resolution was `request.voice or PERSONAS[...] or` a hardcoded
    default, and both frontend callers speak with no voice argument at all.
    So a setting the interface offers, stores, and renders back had no effect
    on any sound the user heard.

    That is this repository's signature failure wearing a settings control
    rather than a module, and it is why the order below is written out rather
    than left implicit:

    1. What this request asked for. A per-utterance override still wins.
    2. What the user chose in Settings. Their standing answer.
    3. The tone preset's voice, if this request named a preset that is not
       the default one — a preset the user picked is also a choice.
    4. `DEFAULT_VOICE`, which is the only place a literal lives.

    Step 3 is deliberately narrow. Taking the preset before the user's setting
    would mean the default preset — which every request carries when nobody
    chose one — silently outranked the only voice the user actually picked.
    """
    from core.user_settings import get_user_settings

    if requested:
        return requested

    try:
        chosen = (get_user_settings().voice or "").strip()
    except Exception:
        # Settings failing to load must not take speech down with it; the
        # default below is always a real voice.
        chosen = ""
    if chosen:
        return chosen

    if persona and persona != DEFAULT_PERSONA:
        preset = PERSONAS.get(persona, {}).get("voice", "")
        if preset:
            return preset

    return DEFAULT_VOICE


@app.post("/voice/synthesize")
async def voice_synthesize(request: VoiceSynthesizeRequest):
    """Synthesize speech for a single utterance."""
    if not kernel.speech_runtime:
        raise HTTPException(status_code=503, detail="Speech runtime not available")

    voice = _resolve_voice(request.voice, request.persona)

    result = await kernel.speech_runtime.execute("speech.tts", {
        "text": request.text,
        "voice": voice,
        "persona": request.persona,
    })
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Synthesis failed"))
    
    return result


@app.post("/voice/stream")
async def voice_stream(request: VoiceStreamRequest):
    """Stream speech synthesis as Server-Sent Events."""
    if not kernel.speech_runtime:
        raise HTTPException(status_code=503, detail="Speech runtime not available")

    voice = _resolve_voice(request.voice, request.persona)

    async def event_generator():
        try:
            result = await kernel.speech_runtime.execute("speech.stream", {
                "text": request.text,
                "voice": voice,
                "persona": request.persona,
            })
            
            stream = result.get("stream")
            if not stream:
                yield f"data: {json.dumps({'type': 'error', 'content': 'No stream returned'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return
            
            async for chunk in stream:
                # Convert AudioChunk to event format
                # KNOWN WRONG, and unused: this builds the URL from the request
                # id, which is the defect that made /voice/synthesize return a
                # 404 for every utterance — AudioCache names files
                # `{voice}_{hash}.wav`. Fixed there by carrying
                # `SynthesisResult.audio_filename`; fixing it here needs the
                # same field on AudioChunk. Nothing in the frontend calls
                # /voice/stream, so it is marked rather than migrated — but it
                # must not be wired up in this state.
                audio_url = f"/audio/{chunk.audio_id}.wav" if chunk.audio_id else ""
                event = {
                    "type": "audio",
                    "audio_id": chunk.audio_id,
                    "url": audio_url,
                    "sequence": chunk.index,
                    "final": chunk.final,
                    "voice": chunk.voice_id,
                    "timestamp": chunk.timestamp_ms,
                    "duration": chunk.duration_ms,
                }
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/voice/voices")
async def voice_list():
    """List available voices."""
    if not kernel.speech_runtime:
        return {"voices": {}}
    result = await kernel.speech_runtime.execute("speech.voices", {})
    return result


@app.get("/voice/health")
async def voice_health():
    """Speech runtime health check."""
    if not kernel.speech_runtime:
        return {"status": "unavailable", "reason": "Speech runtime not initialized"}
    health = kernel.speech_runtime.health_check()
    return health


# --------------------------------------------------------------------------- #
# Listening
#
# The audio arrives as a raw body rather than a multipart form: it is one blob
# with one content type, and a form would add a filename and a field name that
# nothing reads. It is transcribed in this process, on this machine, and is
# never written to disk — a microphone recording is the most sensitive input
# Zaram takes, and a temp file would outlive the request that needed it.
# --------------------------------------------------------------------------- #

#: A push-to-talk clip is seconds long. The cap is not about disk — nothing is
#: written — but about not reading an unbounded body into memory because a
#: caller said so.
MAX_TRANSCRIBE_BYTES = 25 * 1024 * 1024


@app.get("/voice/stt/health")
async def stt_health():
    """Whether Zaram can listen, and when it cannot, why.

    Called by the UI to decide whether the microphone button is offered.
    CLAUDE.md: disabled capabilities are visible, not silent — a mic button that
    is simply absent tells the user nothing, and one that fails on press tells
    them something worse.
    """
    from voice.stt.service import get_recogniser

    recogniser = await get_recogniser()
    return await recogniser.health_check()


@app.post("/voice/transcribe")
async def voice_transcribe(request: Request, language: str | None = None):
    """Turn a recording into text. Local only."""
    from voice.stt.service import get_recogniser

    audio = await request.body()
    if len(audio) > MAX_TRANSCRIBE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"That recording is larger than the {MAX_TRANSCRIBE_BYTES // (1024 * 1024)} MB limit.",
        )

    recogniser = await get_recogniser()
    if not recogniser.is_available():
        report = await recogniser.health_check()
        # 503 with the recogniser's own reason. It is written for a user — it
        # names the install and its size, or the blocked download and its size —
        # so it is passed through rather than replaced with "unavailable".
        raise HTTPException(status_code=503, detail=report.get("reason", "Speech recognition is unavailable."))

    try:
        transcript = await recogniser.transcribe(audio, language=language)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")

    # Measured: the same sentence transcribed three ways, and one of them turned
    # *naira* into **$** — wrong by ~1500x, in the direction that looks
    # reasonable on an invoice. Nothing downstream can catch that, because
    # `$400,000` is a well-formed amount. So the transcript says so itself
    # rather than arriving looking like ordinary prose.
    #
    # Reported, never corrected. Rewriting `$` to `₦` would be guessing intent
    # from audio that has already proven unreliable, which is the failure rule 9
    # is about.
    from voice.stt.figures import CONFIRMATION_NOTICE, figures_in

    figures = figures_in(transcript.text)

    return {
        "text": transcript.text,
        "language": transcript.language,
        "duration_s": transcript.duration_s,
        "segments": [
            {"text": s.text, "start_s": s.start_s, "end_s": s.end_s}
            for s in transcript.segments
        ],
        "figures": [
            {"kind": f.kind, "text": f.text, "start": f.start, "end": f.end}
            for f in figures
        ],
        "needs_confirmation": bool(figures),
        # Sent rather than duplicated in the frontend, so the wording tracks the
        # measurement that justifies it.
        "confirmation_notice": CONFIRMATION_NOTICE if figures else None,
    }


# Voices, not characters — rewritten 13 August 2026.
#
# These were eight named personalities, each opening "You are Baba, a wise and
# analytical AI assistant" or "You are Nova, fast-paced and technical". Three
# things were wrong with that and they compounded.
#
# **They competed with the product's own identity.** Every entry made an
# identity claim, so the assistant was told it was Nova, by a system whose
# entire pitch is that it is Zaram. Asked what it was, it had three candidate
# answers — the persona's, the model's training ("I am Qwen, made by Alibaba"),
# and the truth — and no reason to prefer the last.
#
# **They were the personality the embodiment rule already refuses.** "A wise
# elder voice", "patient teacher": a *someone* to form a relationship with, on
# a product whose indicator is meant to report system state rather than perform.
# The avatar had that removed on the same day; leaving it in the prompt would
# have kept the projection and merely moved it.
#
# **Only one of the eight ever said anything about behaviour that mattered** —
# `zaram_prime`'s instruction to prefer recalled facts over training and to name
# which it used. That has moved into `core/identity.py`, where it applies to
# every request instead of one preset.
#
# What survives is what these were genuinely carrying: a **tone** and a Kokoro
# **voice**. The `/personalities` endpoint keeps its shape, the speech path
# keeps its voice selection, and no entry claims to be anybody.
PERSONAS = {
    "zaram_prime": {
        "name": "Default",
        "gender": "neutral",
        "description": "Calm and precise. The default voice.",
        # Deliberately empty. Identity and the recall instructions come from
        # `core/identity.py` on every request; a default that added tone on top
        # would make the plain case the only one nobody chose.
        "system_prompt": "",
        # The default preset takes the default voice, by reference. Spelling it
        # here is how the two drifted apart before: this entry and
        # `voice/config.py` are the same decision, and only one of them may
        # hold the answer.
        "voice": DEFAULT_VOICE,
    },
    "baba": {
        "name": "Considered",
        "gender": "neutral",
        "description": "Unhurried. Works through the reasoning before the answer.",
        "system_prompt": "Write unhurriedly. Set out the reasoning before the conclusion, and prefer understanding the whole shape of a problem to answering the narrow question.",
        "voice": "am_michael",
    },
    "nova": {
        "name": "Technical",
        "gender": "neutral",
        "description": "Sharp and efficient. Built for code and technical detail.",
        "system_prompt": "Write tersely and technically. Lead with the answer, use precise terms rather than approximations, and prefer a code example to a description of one.",
        "voice": "af_nicole",
    },
    "mentor": {
        "name": "Explanatory",
        "gender": "neutral",
        "description": "Explains rather than asserts. Good for unfamiliar ground.",
        "system_prompt": "Explain rather than assert. Define a term the first time it appears, build from what the reader is likely to already know, and say when something is a simplification.",
        "voice": "am_adam",
    },
    "creator": {
        "name": "Expressive",
        "gender": "neutral",
        "description": "For writing and design work.",
        "system_prompt": "Write with attention to rhythm and word choice. Offer alternatives where a choice is genuinely open, and say what each one costs.",
        "voice": "af_bella",
    },
    "analyst": {
        "name": "Evidential",
        "gender": "neutral",
        "description": "Figures and sources first.",
        "system_prompt": "Lead with figures and sources. Separate what is measured from what is inferred, and say plainly when a number is an estimate.",
        "voice": "am_michael",
    },
    "researcher": {
        "name": "Thorough",
        "gender": "neutral",
        "description": "Covers the ground, including what disagrees.",
        "system_prompt": "Cover the ground. Include what disagrees with the conclusion rather than only what supports it, and name what was not checked.",
        "voice": "af_heart",
    },
    "minimal": {
        "name": "Brief",
        "gender": "neutral",
        "description": "Short answers, no preamble.",
        "system_prompt": "Answer in as few words as the question genuinely needs. No preamble, no summary of what you are about to say, no offer of further help.",
        "voice": "af_nicole",
    },
}


@app.get("/personalities")
def get_personalities():
    """Personality Endpoint (Preserved)."""
    return {
        "personalities": {
            pid: {
                "name": p["name"],
                "gender": p["gender"],
                "description": p["description"],
                "system_prompt": p["system_prompt"],
                "voice": p["voice"]
            }
            for pid, p in PERSONAS.items()
        }
    }


@app.get("/personalities/{persona_id}")
def get_personality(persona_id: str):
    """Get a specific personality."""
    if persona_id not in PERSONAS:
        raise HTTPException(status_code=404, detail="Personality not found")
    p = PERSONAS[persona_id]
    return {
        "id": persona_id,
        "name": p["name"],
        "gender": p["gender"],
        "description": p["description"],
        "system_prompt": p["system_prompt"],
        "voice": p["voice"]
    }


#: The address the API listens on. **Loopback, and not configurable.**
#:
#: This was `0.0.0.0` — every network interface — and `backendLauncher.js`
#: starts the packaged app through exactly this path, so the shipped product
#: would have published its API to whatever network the user was on. There is
#: no authentication on any endpoint, so anyone able to reach port 8420 in a
#: café, a hotel or a shared office could read the whole Spine through
#: `/memory`, read the egress log, flip a host to `allow` through
#: `/egress/policy`, and approve a pending confirmation. For a product whose
#: claim is that your documents stay on your machine, that is the worst
#: available bug.
#:
#: Not an environment variable, deliberately. A setting that re-opens this
#: would be set once by someone debugging on a second device and then never
#: unset — and the failure is silent, because everything keeps working.
#: Someone who genuinely needs LAN access can change this line and own the
#: decision. `test_backend_binds_loopback_only.py` asserts it.
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8420


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=LISTEN_HOST, port=LISTEN_PORT)
