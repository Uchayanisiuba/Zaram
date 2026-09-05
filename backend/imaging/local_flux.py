"""FLUX.1 [schnell] on the user's own GPU, through diffusers.

Replaces the SDXL provider rather than sitting beside it — the maintainer's
decision on 4 September 2026, after the comparison in `docs/MILESTONES.md`.
What FLUX buys over SDXL is prompt adherence, legible text inside the picture,
and hands that have five fingers; what it costs is that it is a 12B model rather
than a 3.5B one, which is the whole reason the quantisation below matters.

Why diffusers and not ComfyUI
-----------------------------
Unchanged from the module this replaces, and worth keeping because the model
itself recommended otherwise when asked: ComfyUI would be a second application
to install, run and keep working, and CLAUDE.md names that class of thing *"a
permanent maintenance obligation that breaks on every host-app update"*. The
backend is already Python and already has torch.

Why NF4, and why the weights arrive already quantised
-----------------------------------------------------
FLUX.1 [schnell] is 23.8 GB in bf16 and does not fit a 12 GB card. Two ways to
make it fit, and the difference is entirely in what the user downloads:

* **Quantise on load** from the bf16 originals — 57.9 GB fetched to produce
  ~8 GB resident. It also needs `black-forest-labs/FLUX.1-schnell`, which is
  gated: the licence is Apache 2.0 but the repository still requires an account
  and a token to accept it, and asking a user for a token to make a local
  feature work is the opposite of what this feature is for.
* **Fetch weights that are already NF4** — 13.4 GB, ungated, in the standard
  diffusers layout.

The second, obviously. `magespace/FLUX.1-schnell-bnb-nf4` is what
`docs/RUNNING.md` names. Measured from the HuggingFace API before downloading
rather than after: transformer 6.69 GB, T5 text encoder 6.33 GB, CLIP 0.25 GB,
VAE 0.17 GB.

**A directory, not a single file, and that simplifies things.** SDXL arrived as
one `.safetensors` and needed a separate pipeline-configuration directory beside
it — `find_pipeline_config` existed so that a missing config *refused* instead of
letting diffusers fetch it. A diffusers-layout folder carries its own
`model_index.json` and every component config, so the folder is the
configuration. One fewer thing to find, one fewer way to be half-installed.

It also fixes a hazard the old discovery had here specifically: it globbed
`*.safetensors` and took the first, so a leftover `sd_xl_base_1.0.safetensors`
in the same directory would have been picked up and handed to a FLUX pipeline.
Looking for `model_index.json` cannot make that mistake.

Nothing is imported until something asks for a picture
------------------------------------------------------
``torch`` and ``diffusers`` are imported inside the functions that need them,
never at module scope. The backend must boot on a machine that has neither.
"""

from __future__ import annotations

import io
import logging
import os
import secrets
import threading
from pathlib import Path
from typing import Any, List, Optional

from .contracts import (
    AVAILABLE,
    Availability,
    GeneratedImage,
    ImageProgress,
    ImageRequest,
    ProgressCallback,
)

logger = logging.getLogger(__name__)

#: A directory naming the model outright.
MODEL_ENV = "ZARAM_IMAGE_MODEL"

#: A directory to scan for a diffusers layout when no model is named.
MODEL_DIR_ENV = "ZARAM_IMAGE_MODEL_DIR"

#: What diffusers reads first. Its presence is the honest test for "this
#: directory is a pipeline" — the same role `model_index.json` played in the
#: SDXL provider's config check, now doing the whole job.
PIPELINE_INDEX = "model_index.json"

#: The repository the weights come from, named here so the availability remedy
#: can print something the user can act on rather than "install a model".
SOURCE_REPO = "magespace/FLUX.1-schnell-bnb-nf4"
SOURCE_SIZE = "13.4 GB"

#: Resident VRAM, NF4 transformer plus the NF4 T5 encoder, with the pipeline
#: offloading components it is not currently using. Used to warn, never to
#: block — CLAUDE.md settles that VRAM routes a task and does not reject one.
APPROXIMATE_VRAM_BYTES = 8_400_000_000

#: Schnell is guidance-distilled: it is trained to produce its result in a few
#: steps with no classifier-free guidance at all. A guidance scale above zero
#: does not make it more faithful, it makes it worse, and there is no negative
#: prompt to weigh against — which is why `generate` ignores one and says so.
GUIDANCE = 0.0

#: T5 is trained here at 256 for schnell. Raising it costs memory and changes
#: nothing; lowering it truncates long prompts silently.
MAX_SEQUENCE_LENGTH = 256


def default_model_dir() -> Path:
    """Where a model is looked for when nobody said.

    Under the data directory, which is where every other store already lives
    and what the uninstaller already promises to hand back. Overridable,
    because 13 GB is exactly the kind of thing somebody already has somewhere
    else and must not be asked to download twice.
    """
    override = os.getenv(MODEL_DIR_ENV)
    if override:
        return Path(override).expanduser()

    from core.paths import data_dir

    return data_dir() / "models" / "image"


def find_model() -> Optional[Path]:
    """The pipeline directory to draw with, or ``None``.

    ``None`` is a real answer and not a failure: no image model installed is
    the state most machines are in, and the caller's job is to say so and offer
    rather than to raise.
    """
    named = os.getenv(MODEL_ENV)
    if named:
        candidate = Path(named).expanduser()
        return candidate if _looks_installed(candidate) else None

    directory = default_model_dir()
    if not directory.is_dir():
        return None

    # The directory may itself be a pipeline, or may contain them. Both are
    # reasonable things for a user to have arranged and neither is worth
    # refusing over.
    if _looks_installed(directory):
        return directory

    # Sorted so the choice is stable across runs. A directory with two
    # pipelines in it must not draw with a different one each launch.
    for candidate in sorted(p for p in directory.iterdir() if p.is_dir()):
        if _looks_installed(candidate):
            return candidate
    return None


def _looks_installed(candidate: Path) -> bool:
    """An index *and* the weights it names. See `_is_complete`."""
    return (candidate / PIPELINE_INDEX).is_file() and _is_complete(candidate)


#: Component classes that ship configuration and no weights.
#:
#: **Not every component in a pipeline has a `.safetensors` beside it**, and
#: the first version of `_is_complete` assumed they all did. FLUX's index names
#: seven components; three of them — the scheduler and both tokenisers — are
#: config-only by design, so a fully downloaded 13.4 GB model reported itself as
#: *"only partly downloaded"*. Found by the real thing the moment the download
#: finished, which is the argument for testing against a real artifact rather
#: than only against a fixture this file wrote itself.
#:
#: Matched on the class name rather than on a list of component names, so it
#: holds for a pipeline whose components are arranged differently. A name that
#: is not recognised is treated as needing weights: the failure that matters is
#: calling a half-download complete, and this is the direction that errs safely.
_CONFIG_ONLY_SUFFIXES = (
    "Tokenizer",
    "TokenizerFast",
    "Scheduler",
    "Processor",
    "FeatureExtractor",
)


def _is_complete(pipeline: Path) -> bool:
    """Whether every component the index names has weights on disk.

    **`model_index.json` arrives first and weighs nothing.** It is one of the
    small files, so an interrupted 13.4 GB download leaves it sitting in a
    directory with no transformer beside it — and a check that looked only for
    the index would report the model as installed, tell the user `can_draw`,
    and fail at the moment they asked for a picture. Found on 4 September 2026
    by running the tests against a download that was 78% done.

    Read from the index rather than by looking for known folder names, so this
    stays true of any diffusers pipeline rather than of this one repository's
    layout. The index maps a component to a ``[library, class]`` pair; the
    component name is the subdirectory.

    A malformed index means "not complete" rather than an exception. The
    caller's job at this point is to decide whether to offer, and a directory
    nobody can parse is not something to offer.
    """
    import json

    try:
        index = json.loads((pipeline / PIPELINE_INDEX).read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(index, dict):
        return False

    # **Staging files are deliberately not consulted**, though they look like
    # the obvious signal. `huggingface_hub` writes into
    # `.cache/huggingface/download/…incomplete` and moves the result into place
    # only on success, so a half-fetched weight is already an *absent* weight
    # and the loop below catches it. Treating a leftover `.incomplete` as
    # evidence adds nothing and gets the live case wrong: an interrupted
    # attempt leaves one behind, a later attempt completes the same file by
    # another route, and the orphan would then block a model that is entirely
    # present. Measured here — that is exactly what happened on the first run.
    for name, value in index.items():
        # Keys beginning with an underscore are metadata (`_class_name`,
        # `_diffusers_version`), and a null value is a component the pipeline
        # declares and does not ship — a safety checker, usually.
        if name.startswith("_") or not isinstance(value, list):
            continue
        folder = pipeline / name
        if not folder.is_dir():
            return False

        # The class the index names decides whether weights are expected. A
        # tokeniser folder holds a vocabulary and no tensors, and demanding a
        # `.safetensors` from it fails a model that is completely installed.
        klass = value[1] if len(value) > 1 and isinstance(value[1], str) else ""
        if klass.endswith(_CONFIG_ONLY_SUFFIXES):
            continue

        if not any(folder.glob("*.safetensors")) and not any(folder.glob("*.bin")):
            return False
    return True


def _module_present(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _force_hub_offline() -> None:
    """Make ``huggingface_hub`` refuse the network, for real this time.

    **The environment variable alone does nothing here**, and that is measured
    rather than assumed: the library reads it into a module constant at import,
    and ``import diffusers`` has already imported it by the time this runs. On
    3 September 2026, with only the variable set, 3.2 MB of tokeniser and config
    files were written into ``~/.cache/huggingface`` during a run the suite
    reported as passing. Both are set — the constant is what the library
    actually consults, the variable is what a subprocess or a late import would
    read.

    Carried over from the SDXL provider unchanged, deliberately. It is the one
    piece of that module that was got wrong once and fixed against a
    measurement, and `test_egress_chokepoint.py` asserts the *effective* form
    rather than the form that reads correctly — a test that accepted the
    environment variable would be the test that let the original bug through.

    Never restored. This process has no legitimate reason to fetch from the
    Hub, so scoping it to the load would only create a window in which some
    other import could reach out.
    """
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        import huggingface_hub.constants as constants

        constants.HF_HUB_OFFLINE = True
    except Exception:  # pragma: no cover - hub absent means nothing to force
        logger.debug("huggingface_hub not importable; nothing to force offline")


class FluxProvider:
    """Draws with FLUX.1 [schnell] on the local GPU.

    One pipeline is held and reused. Loading costs tens of seconds and most of
    the card, so reloading per request would make the second image as slow as
    the first for no reason.
    """

    name = "flux-schnell"

    def __init__(self, model: Optional[Path] = None) -> None:
        self._model = model
        self._pipeline: Any = None
        # Generation is not re-entrant: two threads sampling on one pipeline
        # interleave their latents and both get noise. The API serialises here
        # rather than at the route, so every caller inherits it.
        self._lock = threading.Lock()

    # ------------------------------------------------------------ discovery

    @property
    def model(self) -> Optional[Path]:
        if self._model is None:
            self._model = find_model()
        return self._model

    def availability(self) -> Availability:
        """Whether a picture could be drawn here right now.

        Each reason has its own remedy and its own size, because "images are
        unavailable" is not something a user can act on and "download 13.4 GB"
        is.
        """
        if not _module_present("torch"):
            return Availability(
                ok=False,
                reason="Drawing images needs PyTorch, which is not installed.",
                remedy="pip install zaram[image] (2.6 GB, one time)",
            )
        if not _module_present("diffusers"):
            return Availability(
                ok=False,
                reason="Drawing images needs diffusers, which is not installed.",
                remedy="pip install zaram[image]",
            )
        if not _module_present("bitsandbytes"):
            # Its own reason rather than being folded into the one above. The
            # weights are stored NF4, so this is what actually reads them, and
            # a user told only "install diffusers" would install it and still
            # not be able to draw.
            return Availability(
                ok=False,
                reason=(
                    "The image model is stored in 4-bit, and bitsandbytes — "
                    "which reads that format — is not installed."
                ),
                remedy="pip install bitsandbytes",
            )
        if self.model is None:
            # **Half-installed says so.** An interrupted download leaves the
            # index and the small configs behind, and "no image model is
            # installed" would send a user to start a 13.4 GB fetch they have
            # mostly already done — where resuming costs them the remainder.
            partial = default_model_dir()
            half = partial.is_dir() and any(
                (child / PIPELINE_INDEX).is_file()
                for child in [partial, *(p for p in partial.iterdir() if p.is_dir())]
            )
            if half:
                return Availability(
                    ok=False,
                    reason=(
                        "The image model is only partly downloaded — its index is "
                        "here but some of its weights are not."
                    ),
                    remedy=(
                        f"Finish the download of {SOURCE_REPO} into "
                        f"{default_model_dir()}. It resumes where it stopped."
                    ),
                )
            return Availability(
                ok=False,
                reason="No image model is installed on this machine.",
                remedy=(
                    f"Put a FLUX.1 [schnell] pipeline in {default_model_dir()}, "
                    f"or set {MODEL_ENV} to one you already have "
                    f"(from {SOURCE_REPO}, {SOURCE_SIZE}, one time)"
                ),
            )

        import torch

        if not torch.cuda.is_available():
            # Not a refusal, but a much stronger warning than SDXL needed: a
            # 12B transformer on a CPU is tens of minutes per image, not the
            # couple of minutes SDXL took.
            return Availability(
                ok=True,
                reason=(
                    "No CUDA GPU was found. FLUX can be drawn on the CPU, but a "
                    "single image will take tens of minutes."
                ),
            )

        return AVAILABLE

    def describe(self) -> str:
        """What to show the user as the thing that drew the picture."""
        model = self.model
        return model.name if model else self.name

    # ------------------------------------------------------------- sampling

    def _load(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline

        model = self.model
        if model is None:
            raise RuntimeError("no image model installed")

        import torch
        from diffusers import FluxPipeline

        cuda = torch.cuda.is_available()
        logger.info("Loading %s (%s)", model.name, "cuda" if cuda else "cpu")

        _force_hub_offline()
        pipeline = FluxPipeline.from_pretrained(
            str(model),
            # bfloat16 for the parts that are not quantised — the VAE and the
            # unquantised layers. fp16 overflows in FLUX's attention and comes
            # out as black images, which is a failure that looks like a bug in
            # everything except the dtype.
            torch_dtype=torch.bfloat16,
            local_files_only=True,
        )

        if cuda:
            # **Offload rather than `.to("cuda")`.** T5 and the transformer are
            # about 13 GB between them and the card is 12; moving everything on
            # at once is an out-of-memory error before the first step. This
            # keeps each component on the GPU only while it is running — T5
            # encodes the prompt, leaves, then the transformer denoises — at
            # the cost of a few seconds of transfer per image.
            #
            # **Two granularities, and the coarser one is tried first.** Model
            # offload moves whole components; sequential offload moves
            # individual submodules and is much slower, but needs less headroom.
            # 4-bit weights are also restricted in how bitsandbytes lets them
            # move between devices, so the coarse call is the one that might
            # refuse — and a refusal here should cost seconds per image rather
            # than the whole feature.
            try:
                pipeline.enable_model_cpu_offload()
            except Exception as coarse:
                logger.info(
                    "Model offload unavailable (%s); falling back to sequential "
                    "offload, which is slower per image",
                    coarse,
                )
                pipeline.enable_sequential_cpu_offload()
        else:
            pipeline.to("cpu")

        # The progress bars diffusers prints go to stderr and end up in the
        # backend log as thousands of carriage returns. The progress the user
        # sees comes from the callback in `generate`.
        pipeline.set_progress_bar_config(disable=True)

        self._pipeline = pipeline
        return pipeline

    def unload(self) -> None:
        """Give the VRAM back.

        Present because the pipeline is most of a 12 GB card and the chat model
        has to live somewhere. The orb reports `swapping` while this happens; an
        invisible swap reads as a broken product.
        """
        if self._pipeline is None:
            return
        self._pipeline = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:  # pragma: no cover - torch absent or already gone
            logger.debug("Could not empty the CUDA cache", exc_info=True)

    def generate(
        self,
        request: ImageRequest,
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[GeneratedImage]:
        """Draw ``request.count`` images, reporting each step as it lands.

        One at a time rather than as a batch, for the reason the SDXL provider
        gave and which is sharper here: a batch holds several sets of latents on
        a card that is already offloading to fit one model, and the failure when
        it does not fit is an out-of-memory error *after* the user has waited.
        Drawing in sequence simply takes longer and always finishes.

        **A negative prompt is ignored, and that is said out loud.** Schnell is
        guidance-distilled and has nothing to weigh a negative against;
        `FluxPipeline` does not accept the argument at all. Passing it silently
        would leave a user believing they had excluded something.
        """
        import torch

        if request.negative_prompt:
            logger.info(
                "Negative prompt ignored: FLUX schnell is guidance-distilled and "
                "has no negative channel"
            )

        with self._lock:
            pipeline = self._load()
            # The generator stays on the CPU. With model offloading the
            # transformer's device moves during the call, and a generator bound
            # to `cuda` then seeds from a device the pipeline is not on — which
            # makes the same seed produce different pictures.
            results: List[GeneratedImage] = []

            for index in range(request.count):
                seed = (
                    request.seed + index
                    if request.seed is not None
                    else secrets.randbelow(2**31)
                )
                generator = torch.Generator(device="cpu").manual_seed(seed)

                def step_callback(
                    _pipe: Any,
                    step: int,
                    _timestep: Any,
                    callback_kwargs: dict,
                    _index: int = index,
                ) -> dict:
                    if on_progress is not None:
                        try:
                            on_progress(
                                ImageProgress(
                                    step=step + 1,
                                    total_steps=request.steps,
                                    index=_index + 1,
                                    count=request.count,
                                )
                            )
                        except Exception:
                            # A reporting failure must never abort a generation
                            # that is working.
                            logger.debug("Progress callback raised", exc_info=True)
                    return callback_kwargs

                output = pipeline(
                    prompt=request.prompt,
                    width=request.width,
                    height=request.height,
                    num_inference_steps=request.steps,
                    guidance_scale=GUIDANCE,
                    max_sequence_length=MAX_SEQUENCE_LENGTH,
                    generator=generator,
                    callback_on_step_end=step_callback,
                )

                image = output.images[0]
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                results.append(
                    GeneratedImage(
                        png=buffer.getvalue(),
                        width=image.width,
                        height=image.height,
                        seed=seed,
                    )
                )

            return results
