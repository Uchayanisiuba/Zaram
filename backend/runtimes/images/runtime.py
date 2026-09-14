"""Images Runtime — the second generative tool, and the first that refuses.

Modelled on `DocumentsRuntime` line for line, because that is the path in this
codebase that demonstrably reaches a user: a runtime registered at boot, calling
`ArtifactService`, writing into one output directory that cannot be overwritten,
and handing back a card. An image that arrived by any other route would be a
file Work has never heard of and a download the egress log cannot account for.

Generative tier, and the safety is structural
---------------------------------------------
CLAUDE.md's risk table: a generative tool creates new artifacts and changes
nothing that already exists, so it needs no undo, no sandbox and no
confirmation dialog. None of that safety is promised here — it lives underneath
in `ArtifactStore`, which has no capability to delete or overwrite and confines
every path to the output root before opening anything.

The refusal is the feature
--------------------------
This runtime's most important behaviour is the one where it produces nothing.

"Draw me a logo" reaching an ordinary chat model produces a confident paragraph
about a picture that was never made — rule 9 in a new medium, and the silent
version of it, because nothing on screen says the image does not exist. So when
no provider can draw, this returns ``success: False`` with a reason and a
remedy, and the chat path is responsible for showing that instead of an answer.

That ordering is deliberate and it is the handoff's: **the refusal path first,
the offer second.** An offer is the nice part; the refusal is the part that
stops the product lying.

The card is asked before it is spent
------------------------------------
On 12 September 2026 the maintainer used a local chat model, asked for a
picture, and the machine froze. FLUX needs about 8.4 GB of the card; the chat
model that had just answered held 10 GB of a 12 GB card; the provider's only
preflight was "does CUDA exist". Twenty gigabytes were asked of twelve, the
driver paged GPU memory through system RAM for every process on the machine,
and the offload hook then moved whole components across that bus on every
denoising step.

So before anything loads, `_make_room` reads what is free, releases what
Zaram's own servers hold when that is short, reads again, and only then lets
the provider load. A card that is still held — TabbyAPI has no unload route;
a game or an editor is not Zaram's to close — is refused **by name**, with
where to free it, and nothing falls through to CPU offload on a full card,
because that is the freeze. The card's three questions live in `card.py`.

And the picture given, the model is unloaded. Eight gigabytes held resident
for something used once an hour is the thirty-minute keep-alive mistake in a
bigger tenant, and it is what put the chat model and FLUX on the card at the
same time in the first place. Requests in flight together share one load.

Progress is published, not predicted
------------------------------------
A diffusion pipeline emits a callback per denoising step, so the events carry a
step count and a percentage derived from it. There is no time remaining
anywhere in this file, and `ImageProgress` has no field that could hold one —
see `imaging/contracts.py`. With code you watch it being written and the wait
explains itself; an image is silent for its whole duration unless something
reports it, and a wrong number is worse than none.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from artifacts.contracts import Artifact
from artifacts.service import ArtifactService
from core.contracts import (
    Capability,
    CapabilityLocality,
    Runtime,
    RuntimeMetadata,
    RuntimeState,
)
from core.event_bus import EventBus
from imaging.contracts import (
    DEFAULT_STEPS,
    MAX_IMAGES,
    GeneratedImage,
    ImageProgress,
    ImageProvider,
    ImageRequest,
)
from runtimes.images.card import Card

logger = logging.getLogger(__name__)

#: What a notice from this runtime is tagged as on the stream. The interface
#: routes `action: settings` to the screen where providers and models live,
#: which is where a held card or a missing image provider is dealt with.
NOTICE_KIND = "images"

RUNTIME_ID = "images"
RUNTIME_VERSION = "1.0.0"

#: The capability the planner routes an `image` intent to.
GENERATE = "image.generate"

#: What the user is told when nothing on the machine can draw and no reason was
#: supplied. A fallback for a state that should not occur — the provider always
#: gives a reason — kept because a bare "failed" is the one message a user
#: cannot act on.
_UNAVAILABLE = "Zaram cannot draw images on this machine yet."


class ImagesRuntime(Runtime):
    """Turns a description into a picture, and records where it came from."""

    def __init__(
        self,
        service: ArtifactService,
        provider: Optional[ImageProvider] = None,
        event_bus: Optional[EventBus] = None,
        card: Optional[Card] = None,
    ):
        self._service = service
        # Injected, and `None` is a supported state rather than a broken one:
        # most machines have no image model, and that is a thing to say rather
        # than a thing to crash on.
        self._provider = provider
        self._event_bus = event_bus
        # The graphics card's three questions — free, held by whom, release.
        # `None` means nobody can answer them, and then the runtime draws as
        # it always did: unknown is not a reason to refuse, it is a reason
        # not to know, and the log says which.
        self._card = card
        self._state = RuntimeState.UNINITIALIZED
        self._start_time = time.time()
        self._generated = 0
        # Requests between preflight and their picture. The model is unloaded
        # when this reaches zero, so pictures asked for together share a load.
        self._in_flight = 0
        # What the last preflight found, for `/health`. Reported as *last*,
        # with its time, rather than re-probed on every poll: the probe is a
        # subprocess and a round trip to each local server, and `/health` is
        # asked every ten seconds by two pollers.
        self._last_preflight: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------- lifecycle

    def get_runtime_id(self) -> str:
        return RUNTIME_ID

    def get_version(self) -> str:
        return RUNTIME_VERSION

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id=RUNTIME_ID,
            version=RUNTIME_VERSION,
            priority="normal",
            capabilities=[
                Capability(
                    id=GENERATE,
                    runtime_id=RUNTIME_ID,
                    category="image",
                    # Local without qualification, because the only provider
                    # that exists is. When a cloud one is added this becomes a
                    # property of the provider rather than a constant here, and
                    # the egress gate is what governs it — not this field.
                    locality=CapabilityLocality.LOCAL,
                )
            ],
            dependencies=[],
            auto_start=True,
        )

    def get_state(self) -> RuntimeState:
        return self._state

    async def initialize(self) -> None:
        self._state = RuntimeState.READY
        availability = self.availability()
        if availability.ok:
            logger.info("Images Runtime ready; %s", self.describe_provider())
        else:
            # Info, not a warning. No image model installed is the ordinary
            # state of a machine, not a fault, and logging it as one trains
            # people to ignore warnings.
            logger.info("Images Runtime ready; nothing can draw: %s", availability.reason)

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        unload = getattr(self._provider, "unload", None)
        if callable(unload):
            try:
                unload()
            except Exception:
                logger.debug("Image provider did not unload cleanly", exc_info=True)
        self._state = RuntimeState.STOPPED

    async def health_check(self) -> Dict[str, Any]:
        availability = self.availability()
        return {
            "status": "healthy" if self._state == RuntimeState.READY else "degraded",
            "runtime_id": RUNTIME_ID,
            "generated": self._generated,
            # Disabled capabilities are visible, not silent — and the remedy
            # carries its size, because naming a fix without naming its cost is
            # not a choice a user on metered data can make.
            "can_draw": availability.ok,
            "reason": availability.reason,
            "remedy": availability.remedy,
            "provider": self.describe_provider(),
            # What drawing takes from the card, whether the model is on it
            # right now, and what the last request found there. `loaded` is
            # live and cheap; `last_preflight` is stamped with when it was
            # read, because a verdict from an hour ago presented as current
            # would be a rendered value nobody measured.
            "vram_needed_bytes": self._vram_needed(),
            "loaded": bool(getattr(self._provider, "loaded", False)),
            "last_preflight": self._last_preflight,
        }

    def _vram_needed(self) -> Optional[int]:
        try:
            needed = getattr(self._provider, "vram_needed_bytes", None)
        except Exception:  # noqa: BLE001 - a provider probe never fails health
            return None
        return int(needed) if isinstance(needed, (int, float)) and needed > 0 else None

    # ------------------------------------------------------------- capability

    def availability(self):
        """Whether a picture can be drawn right now, and if not, why."""
        from imaging.contracts import Availability

        if self._provider is None:
            return Availability(
                ok=False,
                reason=_UNAVAILABLE,
                remedy="Install an image model, or connect a provider that can draw.",
            )
        return self._provider.availability()

    def describe_provider(self) -> str:
        if self._provider is None:
            return "none"
        describe = getattr(self._provider, "describe", None)
        return describe() if callable(describe) else self._provider.name

    # --------------------------------------------------------------- execute

    async def execute(
        self, capability_id: str, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if capability_id != GENERATE:
            return {"success": False, "error": f"unknown capability {capability_id}"}

        prompt = (input_data.get("prompt") or "").strip()
        if not prompt:
            return {
                "success": False,
                "error": "There was nothing to draw — say what the picture should be of.",
            }

        # The refusal, before anything else and before any model is asked
        # anything. This is the branch that stops a text model being handed a
        # request it will answer in prose.
        availability = self.availability()
        if not availability.ok:
            return {
                "success": False,
                "error": availability.reason or _UNAVAILABLE,
                "remedy": availability.remedy,
                # Named so the caller can tell "cannot" from "went wrong", and
                # offer rather than apologise.
                "unavailable": True,
            }

        try:
            request = ImageRequest(
                prompt=prompt,
                negative_prompt=(input_data.get("negative_prompt") or "").strip(),
                width=int(input_data.get("width") or 1024),
                height=int(input_data.get("height") or 1024),
                steps=int(input_data.get("steps") or DEFAULT_STEPS),
                seed=input_data.get("seed"),
                count=max(1, min(MAX_IMAGES, int(input_data.get("count") or 1))),
            )
        except (TypeError, ValueError) as error:
            return {"success": False, "error": f"I can't draw that: {error}"}

        # Where each step's progress goes, supplied by whoever is going to
        # show it. A plain callable on `input_data` rather than an event on
        # the bus, and that choice was made the other way round first.
        #
        # The bus version published `image.progress` and **nothing subscribed
        # to it** — the dispatcher blocks on this coroutine, so the one place
        # that could have forwarded it was not running while the events were
        # being sent. That is a complete, tested, unreachable channel, which is
        # the shape `CLAUDE.md` says has been found fifteen times here. A
        # callback cannot be in that state: if nobody passes one, nothing is
        # reported and no code exists pretending otherwise.
        sink = input_data.get("progress_sink")
        on_progress = None
        if callable(sink):

            def on_progress(progress: ImageProgress) -> None:  # noqa: F811
                # Called from the sampling thread. The sink is responsible for
                # being safe to call from one — the dispatcher's is a queue.
                sink(
                    {
                        "step": progress.step,
                        "total_steps": progress.total_steps,
                        "index": progress.index,
                        "count": progress.count,
                        "percent": progress.percent,
                    }
                )

        # Where what the runtime has to *say* goes — "drawing this unloads
        # qwen3-14b first", or the refusal naming who holds the card. Same
        # shape as the progress sink and for the same reason: a callable that
        # nobody passes reports to nobody, and no code exists pretending
        # otherwise.
        say = _speaker(input_data.get("notice_sink"))

        self._in_flight += 1
        try:
            # The card, before the load. This is the whole fix — see the
            # module docstring for the afternoon it cost.
            # Who draws if the card turns out to be full and cannot be
            # freed: a connected cloud provider, when there is one. Decided
            # before the preflight so the refusal knows whether to speak.
            elsewhere = getattr(self._provider, "instead_of_the_card", None)
            fallback = elsewhere() if callable(elsewhere) else None
            refused = await self._make_room(say, quiet=fallback is not None)
            draw_with = self._provider
            if refused is not None:
                # The card is full and cannot be freed. A connected cloud
                # provider draws this one instead, and that is said in one
                # line rather than the refusal's three — the person asked
                # for a picture, not for a report on their graphics card.
                if fallback is None:
                    return refused
                say(
                    f"The graphics card is full, so {fallback.name} is drawing this one.",
                    action="",
                )
                draw_with = fallback

            try:
                # Off the event loop. Sampling holds the GIL in short bursts
                # and runs for tens of seconds; on the loop it would stall
                # every other request in the backend, including the stream
                # carrying its own progress events.
                drawn: List[GeneratedImage] = await asyncio.to_thread(
                    draw_with.generate, request, on_progress
                )
            except Exception as error:
                logger.exception("Image generation failed")
                return {"success": False, "error": f"could not draw that: {error}"}
        finally:
            self._in_flight -= 1
            if self._in_flight == 0:
                # Give the card back. Whether the picture landed or not: a
                # failed load is the case most likely to have left something
                # half-resident, and the chat model needs the room either way.
                # Off the loop like the load: dropping eight gigabytes of
                # tensors and emptying the CUDA cache is not instant.
                await asyncio.to_thread(self._unload)

        if not drawn:
            return {"success": False, "error": "the image model produced nothing"}

        locality = input_data.get("locality") or "on your machine — nothing left the device"
        model = self.describe_provider()
        title = input_data.get("title") or _title_from(prompt)

        artifacts: List[Artifact] = []
        for index, image in enumerate(drawn):
            try:
                artifacts.append(
                    self._service.create_image(
                        title=title if len(drawn) == 1 else f"{title} ({index + 1})",
                        png=image.png,
                        prompt=prompt,
                        model=model,
                        locality=locality,
                        seed=image.seed,
                        project_id=input_data.get("project_id", ""),
                        conversation_id=input_data.get("session_id", ""),
                        conversation_title=input_data.get("conversation_title", "")
                        or title,
                    )
                )
            except Exception as error:
                logger.exception("Wrote the image but could not record it")
                return {"success": False, "error": f"could not save the image: {error}"}

        self._generated += len(artifacts)
        logger.info("Drew %d image(s) with %s", len(artifacts), model)

        return {
            "success": True,
            # A list even when there is one, because the card that draws these
            # is the same card either way — one request is one card, and a
            # batch is one card with a grid in it rather than four cards.
            "artifacts": [_card(a) for a in artifacts],
            "artifact": _card(artifacts[0]),
        }

    # ------------------------------------------------------------- the card

    async def _make_room(self, say, *, quiet: bool = False) -> Optional[Dict[str, Any]]:
        # ``quiet``: the caller has somewhere else to draw, so a card that
        # cannot take the load is reported back rather than emptied or
        # complained about.
        """Read the card, free it if Zaram can, and refuse if it cannot.

        Returns ``None`` when the load may go ahead and a refusal result
        otherwise. Every probe runs off the loop: the free-memory read is a
        subprocess and the release is a round trip to each local server.

        Three things it deliberately does not do. It does not guess when the
        card cannot be read — `None` from the probe means no NVIDIA driver,
        and refusing every AMD and Apple machine on a probe that cannot run
        there is a wrong number with the sign flipped. It does not trust a
        release: the card is read *again* afterwards, because Ollama saying
        "released" tells you nothing about what TabbyAPI or a game still
        holds. And it never lowers the bar — no CPU fallback, no offload on
        a full card, no force flag — because every one of those is the freeze
        wearing a different name.
        """
        needed = self._vram_needed()
        if self._card is None or needed is None:
            return None
        if getattr(self._provider, "loaded", False):
            # Already on the card, so the memory is already spent — another
            # request in flight loaded it, and this one shares the load.
            return None

        free = await asyncio.to_thread(self._card.free_bytes)
        if free is None:
            logger.info("Images: free VRAM unreadable; loading without a preflight")
            self._note_preflight(free_bytes=None, needed_bytes=needed, fits=None)
            return None
        if free >= needed:
            self._note_preflight(free_bytes=free, needed_bytes=needed, fits=True)
            return None

        # **A card that would have to be emptied is not emptied when a cloud
        # provider can draw — 14 September 2026.** Evicting the chat model
        # costs its reload (106 s measured for the maintainer's 26B) twice:
        # once to draw, once to answer the next question. With NVIDIA one
        # request away that is the wrong trade for one picture, so the
        # caller's fallback draws instead and the chat model stays warm.
        # Nothing is announced here; the caller says its one line.
        if quiet:
            self._note_preflight(free_bytes=free, needed_bytes=needed, fits=False, released={})
            logger.info("Images: the card is full; drawing elsewhere rather than unloading")
            return {"success": False, "error": "the card is full", "unavailable": True, "said": False}

        # Short. Say what is about to happen, then make it happen. An empty
        # residency map means Zaram's servers hold nothing and a release
        # would free nothing — whatever has the card is not ours to close.
        # An *unknown* map (None) is not the same thing, and the release is
        # still tried, because a probe that failed is no evidence the card
        # is somebody else's.
        resident = await asyncio.to_thread(self._card.resident)
        # Only what is actually *on the card*. Measured on the first live run
        # of this path: Ollama reported bge-m3 resident with `size_vram: 0` —
        # loaded, but on the CPU — and the announcement named it, the release
        # unloaded it, the card gained nothing and recall lost its embedder.
        # A size of None is unknown and is kept; zero is known and is not.
        on_card = {
            name: size
            for name, size in (resident or {}).items()
            if size is None or size > 0
        }
        held = ", ".join(_short(name) for name in on_card)
        if resident is None or held:
            say(
                (
                    f"Drawing this unloads {held} first"
                    if held
                    else "Drawing this frees the card of Zaram's chat model first"
                )
                + f" — the card has {_gb(free)} GB free and the picture needs "
                f"about {_gb(needed)} GB. The next question reloads it.",
                action="",
            )
            outcome = await asyncio.to_thread(self._card.release)
            free = await asyncio.to_thread(self._card.free_bytes)
            if free is None or free >= needed:
                self._note_preflight(
                    free_bytes=free, needed_bytes=needed, fits=True, released=outcome
                )
                return None
        else:
            outcome = {}

        # Still short. Name what is in the way, and stop.
        holders = {
            name: why for name, why in outcome.items() if not why.startswith("released")
        }
        if holders:
            named = "; ".join(
                f"{_short(name)} is held by {_app_from(why)}" for name, why in holders.items()
            )
            error = (
                f"Drawing needs about {_gb(needed)} GB of the graphics card and "
                f"only {_gb(free)} GB is free. {named}, and Zaram cannot unload "
                "it."
            )
            remedy = (
                "Unload it from that app, or connect an image provider, and "
                "ask again."
            )
        else:
            error = (
                f"Drawing needs about {_gb(needed)} GB of the graphics card and "
                f"only {_gb(free)} GB is free — something else on this machine "
                "is using the rest."
            )
            remedy = (
                "Close what is using the card, or connect an image provider, "
                "and ask again."
            )
        self._note_preflight(
            free_bytes=free,
            needed_bytes=needed,
            fits=False,
            released=outcome,
            held_by=holders,
        )
        logger.info("Images: refused to load — %s", error)
        # `quiet`: the caller will draw elsewhere and say so itself; the
        # refusal is then a log line, not a notice.
        said = False if quiet else say(f"{error} {remedy}", action="settings")
        return {
            "success": False,
            "error": error,
            "remedy": remedy,
            # Named so the dispatcher refuses rather than falling back to
            # prose — a text model describing a picture it never drew is the
            # failure this runtime exists to prevent, in either direction.
            "unavailable": True,
            # Already on the stream, so the dispatcher does not repeat it.
            "said": said,
            "held_by": holders,
        }

    def _note_preflight(self, **verdict: Any) -> None:
        self._last_preflight = {"checked_at": time.time(), **verdict}

    def _unload(self) -> None:
        if not getattr(self._provider, "loaded", True):
            return
        unload = getattr(self._provider, "unload", None)
        if not callable(unload):
            return
        try:
            unload()
        except Exception:  # noqa: BLE001
            logger.debug("Image provider did not unload cleanly", exc_info=True)


def _speaker(sink: Any):
    """Wrap an optional notice sink so callers can just `say(...)`."""

    def say(content: str, *, action: str = "") -> bool:
        """True when somebody heard it — so a refusal can tell the
        dispatcher not to say the same sentence a second time."""
        if not callable(sink):
            return False
        try:
            sink({"content": content, "kind": NOTICE_KIND, "action": action})
            return True
        except Exception:  # noqa: BLE001 - reporting must never abort a draw
            logger.debug("Notice sink raised", exc_info=True)
            return False

    return say


def _gb(n: Optional[int]) -> str:
    return "?" if n is None else f"{n / 1_000_000_000:.1f}"


def _short(model_name: str) -> str:
    """`qwen3-14b-16k:latest` reads as `qwen3-14b-16k` to a person."""
    return model_name.rsplit(":", 1)[0] if model_name.endswith(":latest") else model_name


def _app_from(outcome: str) -> str:
    """Pull the app's name out of `release_resident`'s "not released:
    <app> has no unload route; ..." so the refusal can say *TabbyAPI* rather
    than quote a status string at the user."""
    body = outcome.split(":", 1)[1].strip() if ":" in outcome else outcome
    for marker in (" has no unload route", " could not", ";"):
        if marker in body:
            return body.split(marker, 1)[0].strip() or "another app"
    return body.split(" ", 1)[0] or "another app"


def _card(artifact: Artifact) -> Dict[str, Any]:
    """What the conversation shows. The same shape a document card uses.

    Deliberately identical, including the `exists` read rather than an
    assumption that the write succeeded — see `runtimes/documents/runtime.py`,
    where an absent field made a card for a file written one second earlier
    render "file not found where it was written".
    """
    import os

    payload = artifact.to_dict()
    payload["exists"] = bool(artifact.path) and os.path.isfile(artifact.path)
    payload["download_url"] = f"/artifacts/{artifact.id}/download"
    # The picture *was* the request — this capability only runs when somebody
    # asked for an image — so the preview may open itself. Transport only: not
    # a property of the file, never stored, and absent from `/artifacts`,
    # because "did the user ask for this" is a fact about one exchange rather
    # than about a document that outlives it.
    payload["deliberate"] = True
    return payload


def _title_from(prompt: str) -> str:
    """A short name for the file, from what was asked for.

    The prompt itself, trimmed. Not a model call: naming a picture is not worth
    a round trip, and a generated title would be a second thing that can be
    wrong about an image nobody has looked at yet.
    """
    cleaned = " ".join(prompt.split())
    for opener in (
        "draw me a picture of ",
        "draw me an image of ",
        "draw me ",
        "draw a picture of ",
        "draw an image of ",
        "generate an image of ",
        "generate a picture of ",
        "create an image of ",
        "create a picture of ",
        "make me an image of ",
        "make me a picture of ",
        "an illustration of ",
        "a picture of ",
    ):
        if cleaned.lower().startswith(opener):
            cleaned = cleaned[len(opener) :]
            break
    cleaned = cleaned.strip(" .,")
    return (cleaned[:60] or "image").strip()
