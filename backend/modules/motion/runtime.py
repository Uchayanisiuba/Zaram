"""Motion Runtime — Registers motion.generate capability and executes generation.

Follows the same pattern as DocumentsRuntime and ImagesRuntime:
- Generative tier: creates new artifacts, changes nothing existing
- Calls ArtifactService.create_video() for persistence
- Returns artifact card for conversation display
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

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

class GenerationUnavailable(RuntimeError):
    """The model could not be asked, or did not answer. Nothing was made up instead."""


from .contracts import MotionScript, MAX_DURATION, DEFAULT_ASPECT_RATIO, ASPECT_RATIOS
from .generator import (
    build_system_prompt,
    build_user_prompt,
    parse_response,
    validate_script,
    MotionScriptParseError,
    MotionScriptValidationError,
)
from .compiler import compile_script, CompilationError
from .renderer import render_to_video, RenderError, check_playwright_available

logger = logging.getLogger(__name__)

RUNTIME_ID = "motion"
RUNTIME_VERSION = "1.0.0"
GENERATE = "motion.generate"

# Feature flag
_MOTION_ENABLED = os.getenv("ZARAM_MOTION_ENABLED", "0") == "1"

# Configurable max duration via env var
_MAX_DURATION = int(os.getenv("ZARAM_MOTION_MAX_DURATION", str(MAX_DURATION)))


class MotionRuntime(Runtime):
    """Turns a motion description into a video file via Code-to-Frame pipeline."""

    def __init__(
        self,
        service: ArtifactService,
        event_bus: Optional[EventBus] = None,
        model_resolver: Optional[Callable[[str], Awaitable[str]]] = None,
        provider_manager: Optional[Any] = None,
        complete: Optional[Callable[..., Awaitable[str]]] = None,
    ):
        self._complete = complete  # the routed engine's one-shot answer; see ModelsRuntime.complete
        self._service = service
        self._event_bus = event_bus
        self._model_resolver = model_resolver  # Resolves model name for generation
        self._provider_manager = provider_manager  # For ModelsRuntime integration
        self._state = RuntimeState.UNINITIALIZED
        self._start_time = time.time()
        self._generated = 0
        self._playwright_checked = False

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
                    category="motion",
                    locality=CapabilityLocality.LOCAL,  # Always local rendering
                )
            ],
            dependencies=[],
            auto_start=True,
        )

    def get_state(self) -> RuntimeState:
        return self._state

    async def initialize(self) -> None:
        self._state = RuntimeState.READY
        if not _MOTION_ENABLED:
            logger.info("Motion Runtime ready (disabled via ZARAM_MOTION_ENABLED=0)")
            return

        if not check_playwright_available():
            logger.warning(
                "Motion Runtime ready but Playwright unavailable — "
                "rendering will fail. Install: pip install playwright && playwright install chromium"
            )
        else:
            logger.info("Motion Runtime ready; Playwright available")

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        self._state = RuntimeState.STOPPED

    async def health_check(self) -> Dict[str, Any]:
        playwright_ok = check_playwright_available()
        return {
            "status": "healthy" if self._state == RuntimeState.READY else "degraded",
            "runtime_id": RUNTIME_ID,
            "generated": self._generated,
            "enabled": _MOTION_ENABLED,
            "playwright_available": playwright_ok,
            "can_render": _MOTION_ENABLED and playwright_ok,
        }

    # ------------------------------------------------------------- execute

    async def execute(
        self, capability_id: str, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if capability_id != GENERATE:
            return {"success": False, "error": f"unknown capability {capability_id}"}

        if not _MOTION_ENABLED:
            return {
                "success": False,
                "error": "Motion generation is disabled. Set ZARAM_MOTION_ENABLED=1 to enable.",
                "unavailable": True,
            }

        if not check_playwright_available():
            return {
                "success": False,
                "error": (
                    "Playwright not available for rendering. "
                    "Install with: pip install playwright && playwright install chromium"
                ),
                "unavailable": True,
            }

        prompt = (input_data.get("prompt") or "").strip()
        answer = (input_data.get("answer") or "").strip()

        # Use answer if available (referential: "animate that"), else prompt
        request_text = answer or prompt
        if not request_text:
            return {
                "success": False,
                "error": "There was nothing to animate — describe what you want animated.",
            }

        try:
            # 1. Get duration from input or use project default
            duration = input_data.get("duration")
            if duration is None:
                # Check project for default
                project_id = input_data.get("project_id", "")
                if project_id and self._provider_manager:
                    # Try to get project defaults
                    from projects.records import ProjectRecords, default_db_path
                    try:
                        project_records = ProjectRecords(default_db_path())
                        project = project_records.get(project_id)
                        if project and project.motion_default_duration:
                            duration = float(project.motion_default_duration)
                    except Exception:
                        pass
            if duration is None:
                duration = 10.0  # global default
            duration = float(duration)
            if duration > _MAX_DURATION:
                duration = _MAX_DURATION

            # 2. Get aspect ratio from input or use project default
            aspect_ratio = input_data.get("aspect_ratio")
            if aspect_ratio is None:
                project_id = input_data.get("project_id", "")
                if project_id and self._provider_manager:
                    from projects.records import ProjectRecords, default_db_path
                    try:
                        project_records = ProjectRecords(default_db_path())
                        project = project_records.get(project_id)
                        if project and project.motion_default_aspect_ratio:
                            aspect_ratio = project.motion_default_aspect_ratio
                    except Exception:
                        pass
            if aspect_ratio is None:
                aspect_ratio = DEFAULT_ASPECT_RATIO
            if aspect_ratio not in ASPECT_RATIOS:
                aspect_ratio = DEFAULT_ASPECT_RATIO

            # 3. Generate MotionScript via LLM (real integration)
            script = await self._generate_script(
                request_text, input_data, duration, aspect_ratio
            )

            # 4. Validate script (additional warnings)
            warnings = validate_script(script)
            for w in warnings:
                logger.warning("MotionScript warning: %s", w)

            # 5. Compile to HTML5 timeline
            asset = compile_script(script)

            # 6. VRAM preflight check
            if self._provider_manager:
                try:
                    swap_plan = self._provider_manager.swap_preflight("motion.generate")
                    if swap_plan and swap_plan.requires_swap:
                        logger.warning(
                            "Motion generation will trigger model swap: %s (evicts: %s)",
                            swap_plan.kind, swap_plan.evicts
                        )
                        if self._event_bus:
                            from core.event_bus import ZaramEvent
                            self._event_bus.publish(ZaramEvent(
                                source_runtime="motion",
                                event_type="model_swap",
                                data={"plan": swap_plan.to_dict(), "reason": "motion_generation"}
                            ))
                except Exception:
                    pass

            # 7. Render to video with progress sink
            progress_sink = input_data.get("progress_sink")
            video_path = await self._render_video(asset, progress_sink)

            # 8. Create artifact with MotionScript provenance
            artifact = self._create_artifact(asset, video_path, input_data)

            self._generated += 1
            logger.info("Generated motion video: %s (%d bytes)", artifact.filename, artifact.size_bytes)

            return {"success": True, "artifact": _card(artifact)}

        except MotionScriptParseError as e:
            logger.exception("MotionScript parse failed")
            return {"success": False, "error": f"Failed to parse motion script: {e}"}
        except MotionScriptValidationError as e:
            logger.exception("MotionScript validation failed")
            return {"success": False, "error": f"Invalid motion script: {e}"}
        except CompilationError as e:
            logger.exception("Compilation failed")
            return {"success": False, "error": f"Compilation failed: {e}"}
        except RenderError as e:
            logger.exception("Rendering failed")
            return {"success": False, "error": f"Rendering failed: {e}"}
        except Exception as e:
            logger.exception("Motion generation failed")
            return {"success": False, "error": f"Motion generation failed: {e}"}

    async def _generate_script(
        self,
        request_text: str,
        input_data: Dict[str, Any],
        duration: float,
        aspect_ratio: str,
    ) -> MotionScript:
        """Ask the model for a MotionScript, or fail. Never invent one.

        This used to try a method the models runtime does not have, then post
        the prompt to the first catalogue provider that had a ``base_url`` with a
        raw HTTP client -- outside the egress gate, rule 3 -- naming one model
        in the code, and finally return a *mock script* when all of that failed.
        A video of something nobody asked for is rule 9's failure in a new
        medium. The prompt now goes through the same routed engine as a chat
        turn, and when that cannot answer the request says so.
        """
        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(request_text, {
            "conversation_summary": input_data.get("conversation_summary", ""),
            "project_style": input_data.get("project_style", ""),
            "brand_colors": input_data.get("brand_colors", {}),
            "aspect_ratio": aspect_ratio,
            "duration": duration,
        })
        if self._complete is None:
            raise GenerationUnavailable(
                "Motion generation has no model to ask: it is not connected to the routed engine."
            )
        model = None
        if self._model_resolver:
            try:
                model = await self._model_resolver("motion.generate")
            except Exception:  # noqa: BLE001 - the engine's own default is the fallback
                model = None
        try:
            response = await self._complete(user_prompt, system_prompt, model)
        except Exception as exc:  # noqa: BLE001
            raise GenerationUnavailable(f"The model could not write the script: {exc}") from exc
        return parse_response(response)

    async def _render_video(
        self, asset: MotionAsset, progress_sink: Optional[Callable[[dict], None]]
    ) -> Path:
        """Render compiled asset to video file."""
        import tempfile

        output_dir = Path(tempfile.gettempdir()) / "zaram_motion"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"motion_{int(time.time()*1000)}.webm"

        return await render_to_video(
            html=asset.html_timeline,
            output_path=output_path,
            duration_ms=asset.duration_ms,
            fps=asset.fps,
            width=asset.width,
            height=asset.height,
            progress_sink=progress_sink,
        )

    def _create_artifact(
        self, asset: MotionAsset, video_path: Path, input_data: Dict[str, Any]
    ) -> Artifact:
        """Create artifact record via ArtifactService with MotionScript provenance."""
        # Read video bytes
        video_bytes = video_path.read_bytes()

        # Don't embed video in HTML — use download URL for preview (Task 13)
        # The HTML stored is the original timeline for re-export
        title = asset.script.metadata.get("title", "Motion Animation")
        filename = f"{title[:50].replace(' ', '_')}.webm"

        artifact = self._service.create_video(
            title=title,
            video_bytes=video_bytes,
            duration_ms=asset.duration_ms,
            width=asset.width,
            height=asset.height,
            fps=asset.fps,
            script=asset.script,  # Store MotionScript for provenance
            filename=filename,
            project_id=input_data.get("project_id", ""),
            conversation_id=input_data.get("session_id", ""),
            conversation_title=input_data.get("conversation_title", "") or title,
        )

        # Don't overwrite artifact.html with video preview
        # Keep the original HTML timeline as artifact.html for re-export
        # Frontend will use download_url for video playback
        return artifact


def _card(artifact: Artifact) -> Dict[str, Any]:
    """Artifact card for conversation display."""
    import os
    payload = artifact.to_dict()
    payload["exists"] = bool(artifact.path) and os.path.isfile(artifact.path)
    payload["download_url"] = f"/artifacts/{artifact.id}/download"
    payload["deliberate"] = True
    return payload