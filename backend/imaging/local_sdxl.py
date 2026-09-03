"""SDXL on the user's own GPU, through diffusers.

Why diffusers and not ComfyUI
-----------------------------
ComfyUI would have been a second application to install, run and keep working,
and CLAUDE.md names that class of thing *"a permanent maintenance obligation
that breaks on every host-app update"*. Zaram's backend is already Python and
already had torch; SDXL has a mature diffusers pipeline and ``from_single_file``
loads exactly the one self-contained checkpoint a user downloads. So the second
app buys nothing here.

Nothing is imported until something asks for a picture
------------------------------------------------------
``torch`` and ``diffusers`` are imported inside the functions that need them,
never at module scope. The backend must boot on a machine that has neither —
CUDA torch alone is 2.6 GB — and an import at the top would make image
generation a *requirement* rather than a capability. The same reason the OCR
parsers sit behind an extra.

Offline is asserted, and the first attempt at asserting it did not work
-----------------------------------------------------------------------
``from_single_file`` loads the *weights* from the file it is given and resolves
the pipeline's **component configuration** separately — the scheduler settings,
the two CLIP tokenizers, the UNet and VAE shapes. Left alone it fetches those
from the Hugging Face Hub. That is a network call made by a feature whose
entire claim on screen is "on your machine, nothing left the device", which is
rule 7g with the worst possible cargo.

The first version of this module set ``HF_HUB_OFFLINE=1`` around the load and
passed ``local_files_only=True``, and **measured 3 September 2026 it did not
work**: 3.2 MB of tokenizer and config files were written into
``~/.cache/huggingface`` during the run. ``huggingface_hub`` reads that
environment variable **once, at import**, into ``constants.HF_HUB_OFFLINE`` —
and ``import diffusers`` has already imported it by the time this function
runs. So the variable was being set after the only moment it was read, and the
guard was decorative.

It was found by looking at the cache directory rather than by the test, because
the test asserted that the environment had been *restored* — which is true of a
guard that never applied. That is the assertion-free test this repository has
been bitten by before, and the replacement blocks sockets instead.

Two changes follow, and the second is the one that matters:

* the constant is set directly, not only the variable it was read from;
* the configuration is resolved from **a directory on this machine**, passed as
  ``config=``, so there is nothing to fetch even if the guard were lifted. A
  missing config is a refusal that names the 3 MB, in the same shape as the OCR
  extra — an honestly unavailable feature beats one that quietly reaches the
  network in order to become available.
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

#: A single file naming the checkpoint outright.
CHECKPOINT_ENV = "ZARAM_IMAGE_CHECKPOINT"

#: A directory to scan for ``*.safetensors`` when no file is named.
MODEL_DIR_ENV = "ZARAM_IMAGE_MODEL_DIR"

#: The pipeline configuration directory — see the header. Overridable for the
#: same reason the checkpoint is: somebody may already have it.
CONFIG_DIR_ENV = "ZARAM_IMAGE_PIPELINE_CONFIG"

#: What that directory is named when nobody says, and the file that proves it
#: is one. ``model_index.json`` is what diffusers reads first, so its absence
#: is the honest test for "this is not a pipeline config".
CONFIG_DIRNAME = "sdxl-config"
CONFIG_INDEX = "model_index.json"

#: Roughly what SDXL base claims in fp16, measured rather than quoted: 6.94 GB
#: of weights load to about 7 GB resident with the UNet, both text encoders and
#: the VAE on the card. Used to warn, never to block — CLAUDE.md settles that
#: VRAM routes a task and does not reject one.
APPROXIMATE_VRAM_BYTES = 7_400_000_000


def default_model_dir() -> Path:
    """Where a checkpoint is looked for when nobody said.

    Under the data directory, which is where every other store already lives
    and what the uninstaller already promises to hand back. Overridable,
    because a 6.94 GB file is exactly the kind of thing somebody already has
    somewhere else and must not be asked to download twice.
    """
    override = os.getenv(MODEL_DIR_ENV)
    if override:
        return Path(override).expanduser()

    from core.paths import data_dir

    return data_dir() / "models" / "image"


def find_checkpoint() -> Optional[Path]:
    """The checkpoint to draw with, or ``None``.

    ``None`` is a real answer and not a failure: no image model installed is
    the state most machines are in, and the caller's job is to say so and offer
    rather than to raise.
    """
    named = os.getenv(CHECKPOINT_ENV)
    if named:
        candidate = Path(named).expanduser()
        return candidate if candidate.is_file() else None

    directory = default_model_dir()
    if not directory.is_dir():
        return None

    # Sorted so the choice is stable across runs. A directory with two
    # checkpoints in it must not draw with a different one each launch.
    for candidate in sorted(directory.glob("*.safetensors")):
        if candidate.is_file():
            return candidate
    return None


def find_pipeline_config() -> Optional[Path]:
    """The component configuration, on this machine, or ``None``.

    ``None`` is what makes the refusal possible. Without this the loader falls
    back to whatever diffusers would do on its own, which is to go and get it —
    and a feature that repairs itself over the network is exactly the failure
    this function exists to make impossible.
    """
    named = os.getenv(CONFIG_DIR_ENV)
    directory = (
        Path(named).expanduser() if named else default_model_dir() / CONFIG_DIRNAME
    )
    return directory if (directory / CONFIG_INDEX).is_file() else None


def _force_hub_offline() -> None:
    """Make ``huggingface_hub`` refuse the network, for real this time.

    The environment variable alone does nothing here, because the library reads
    it into a module constant at import and ``diffusers`` has already imported
    it. Both are set: the constant is what the library actually consults, and
    the variable is what a subprocess or a late import would read.

    Never restored. This process has no legitimate reason to fetch from the
    Hub — every model Zaram uses arrives through Ollama, a connected provider,
    or a file the user put on disk — so scoping it to the load would only
    create a window in which some other import could reach out.
    """
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        import huggingface_hub.constants as constants

        constants.HF_HUB_OFFLINE = True
    except Exception:  # pragma: no cover - hub absent means nothing to force
        logger.debug("huggingface_hub not importable; nothing to force offline")


def _module_present(name: str) -> bool:
    from importlib.util import find_spec

    try:
        return find_spec(name) is not None
    except (ImportError, ValueError):
        return False


class SdxlProvider:
    """Draws with a Stable Diffusion XL checkpoint on the local GPU.

    One pipeline is held and reused. Loading costs tens of seconds and ~7 GB,
    so reloading per request would make the second image as slow as the first
    for no reason — and would evict whatever chat model is resident twice
    instead of once.
    """

    name = "sdxl"

    def __init__(self, checkpoint: Optional[Path] = None) -> None:
        self._checkpoint = checkpoint
        self._pipeline: Any = None
        # Generation is not re-entrant: two threads sampling on one pipeline
        # interleave their latents and both get noise. The API serialises here
        # rather than at the route, so every caller inherits it.
        self._lock = threading.Lock()

    # ------------------------------------------------------------ discovery

    @property
    def checkpoint(self) -> Optional[Path]:
        if self._checkpoint is None:
            self._checkpoint = find_checkpoint()
        return self._checkpoint

    def availability(self) -> Availability:
        """Whether a picture could be drawn here right now.

        Three separate reasons it might not be, each with its own remedy and
        its own size, because "images are unavailable" is not something a user
        can act on and "install a 2.6 GB dependency" is.
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
        if self.checkpoint is None:
            return Availability(
                ok=False,
                reason="No image model is installed on this machine.",
                remedy=(
                    f"Put a Stable Diffusion XL checkpoint in {default_model_dir()}, "
                    f"or set {CHECKPOINT_ENV} to one you already have "
                    "(SDXL base is 6.9 GB, one time)"
                ),
            )

        if find_pipeline_config() is None:
            return Availability(
                ok=False,
                reason=(
                    "The checkpoint is here but the pipeline configuration is not, "
                    "and Zaram will not fetch it — a local feature that reaches the "
                    "network to repair itself is not a local feature."
                ),
                remedy=(
                    f"Put the SDXL pipeline config in "
                    f"{default_model_dir() / CONFIG_DIRNAME}, or set "
                    f"{CONFIG_DIR_ENV} to it (3 MB, one time)"
                ),
            )

        import torch

        if not torch.cuda.is_available():
            # Not a refusal. CPU sampling works and takes minutes per image
            # rather than seconds, which is a warning the caller must pass on.
            return Availability(
                ok=True,
                reason="No CUDA GPU was found, so images are drawn on the CPU and "
                "will take minutes rather than seconds.",
            )

        return AVAILABLE

    def describe(self) -> str:
        """What to show the user as the thing that drew the picture."""
        checkpoint = self.checkpoint
        return checkpoint.stem if checkpoint else "sdxl"

    # ------------------------------------------------------------- sampling

    def _load(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline

        checkpoint = self.checkpoint
        if checkpoint is None:
            raise RuntimeError("no image checkpoint installed")

        config = find_pipeline_config()
        if config is None:
            raise RuntimeError(
                "The image pipeline configuration is not on this machine. "
                f"Put it in {default_model_dir() / CONFIG_DIRNAME} or set "
                f"{CONFIG_DIR_ENV}. Zaram will not fetch it."
            )

        import torch
        from diffusers import StableDiffusionXLPipeline

        cuda = torch.cuda.is_available()
        logger.info("Loading %s (%s)", checkpoint.name, "cuda" if cuda else "cpu")

        # Belt and braces, in that order. `config=` means there is nothing to
        # fetch; the offline switch means a fetch would fail rather than
        # succeed quietly if some future diffusers decides it needs one more
        # file. The second exists because the first is a claim about a library
        # we do not maintain.
        _force_hub_offline()
        pipeline = StableDiffusionXLPipeline.from_single_file(
            str(checkpoint),
            config=str(config),
            torch_dtype=torch.float16 if cuda else torch.float32,
            use_safetensors=True,
            local_files_only=True,
        )

        pipeline.to("cuda" if cuda else "cpu")
        # The progress bars diffusers prints go to stderr and end up in the
        # backend log as thousands of carriage returns. The progress the user
        # sees comes from the callback below.
        pipeline.set_progress_bar_config(disable=True)

        self._pipeline = pipeline
        return pipeline

    def unload(self) -> None:
        """Give the VRAM back.

        Present because a resident 7 GB pipeline is most of a 12 GB card, and
        the chat model has to live somewhere. The orb reports `swapping` while
        this happens; an invisible swap reads as a broken product.
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

        One at a time rather than as a batch, deliberately. A batch of four
        holds four sets of latents on a card that is already carrying seven
        gigabytes of weights, and the failure when it does not fit is an
        out-of-memory error after the user has waited — where drawing them in
        sequence simply takes four times as long and always finishes. It also
        gives each image its own seed, which is what makes one of the four
        reproducible on its own.
        """
        import torch

        with self._lock:
            pipeline = self._load()
            device = "cuda" if torch.cuda.is_available() else "cpu"
            results: List[GeneratedImage] = []

            for index in range(request.count):
                # A seed is chosen here rather than left to the global RNG so
                # that it can be *reported*. `secrets` rather than `random`
                # only because it needs no seeding of its own.
                seed = (
                    request.seed + index
                    if request.seed is not None
                    else secrets.randbelow(2**31)
                )
                generator = torch.Generator(device=device).manual_seed(seed)

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
                                    # `step` is 0-based on entry; report the
                                    # step that has just finished.
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
                    negative_prompt=request.negative_prompt or None,
                    width=request.width,
                    height=request.height,
                    num_inference_steps=request.steps,
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
