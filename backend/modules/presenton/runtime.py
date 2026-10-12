"""Presenton Runtime — Registers presentation.generate capability and executes generation.

Follows the same pattern as DocumentsRuntime and MotionRuntime:
- Generative tier: creates new artifacts, changes nothing existing
- Calls ArtifactService.create_presentation() for persistence
- Returns artifact card for conversation display
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from artifacts.contracts import Artifact, ArtifactKind, ArtifactSource, Claim
from artifacts.service import ArtifactService
from core.contracts import (
    Capability,
    CapabilityLocality,
    Runtime,
    RuntimeMetadata,
    RuntimeState,
)
from core.event_bus import EventBus

from .contracts import PresentationScript, PresentationMeta, PresentationSlide, PresentationElement, PresentationTheme
from .compiler import compile_presentation, CompilationError
from .renderer import render_to_pptx, render_to_pdf, RenderError, PresentonNotFoundError

logger = logging.getLogger(__name__)

RUNTIME_ID = "presenton"
RUNTIME_VERSION = "1.0.0"
GENERATE = "presentation.generate"

# Feature flag
_PRESENTON_ENABLED = True  # Could be env var controlled like motion


class GenerationUnavailable(RuntimeError):
    """The model could not be asked, or did not answer. Nothing was made up instead."""


class PresentonRuntime(Runtime):
    """Turns a presentation description into a PPTX/PDF file via Presenton engine."""

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
        self._presenton_checked = False

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
                    category="presentation",
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
        if not _PRESENTON_ENABLED:
            logger.info("Presenton Runtime ready (disabled)")
            return

        if not self._check_presenton_available():
            logger.warning(
                "Presenton Runtime ready but Presenton CLI unavailable — "
                "rendering will fail. Install: pip install presenton"
            )
        else:
            logger.info("Presenton Runtime ready; Presenton CLI available")

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        self._state = RuntimeState.STOPPED

    async def health_check(self) -> Dict[str, Any]:
        presenton_ok = self._check_presenton_available()
        return {
            "status": "healthy" if self._state == RuntimeState.READY and presenton_ok else "degraded",
            "runtime_id": RUNTIME_ID,
            "generated": self._generated,
            "enabled": _PRESENTON_ENABLED,
            "presenton_available": presenton_ok,
            "can_render": _PRESENTON_ENABLED and presenton_ok,
        }

    def _check_presenton_available(self) -> bool:
        """Check Presenton CLI availability (cached)."""
        if not self._presenton_checked:
            try:
                subprocess.run(
                    ["presenton", "--version"],
                    check=True,
                    capture_output=True,
                    timeout=5,
                )
                self._presenton_checked = True
            except Exception:
                return False
        return True

    # ------------------------------------------------------------- execute

    async def execute(
        self, capability_id: str, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if capability_id != GENERATE:
            return {"success": False, "error": f"unknown capability {capability_id}"}

        if not _PRESENTON_ENABLED:
            return {
                "success": False,
                "error": "Presentation generation is disabled.",
                "unavailable": True,
            }

        if not self._check_presenton_available():
            return {
                "success": False,
                "error": (
                    "Presenton CLI not available for rendering. "
                    "Install with: pip install presenton"
                ),
                "unavailable": True,
            }

        prompt = (input_data.get("prompt") or "").strip()
        answer = (input_data.get("answer") or "").strip()

        # Use answer if available (referential: "design that"), else prompt
        request_text = answer or prompt
        if not request_text:
            return {
                "success": False,
                "error": "There was nothing to present — describe what you want presented.",
            }

        try:
            # 1. Generate PresentationScript via LLM
            script = await self._generate_script(request_text, input_data)

            # 2. Compile to Presenton IR
            ir = compile_presentation(script)

            # 3. Render to PPTX
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
                output_path = Path(f.name)

            render_to_pptx(ir, output_path)

            # 4. Read bytes and create artifact
            pptx_bytes = output_path.read_bytes()
            output_path.unlink()

            artifact = self._service.create_presentation(
                title=script.meta.title,
                script=script,
                pptx_bytes=pptx_bytes,
                project_id=input_data.get("project_id", ""),
                conversation_id=input_data.get("session_id", ""),
                conversation_title=input_data.get("conversation_title", "") or script.meta.title,
            )

            self._generated += 1
            logger.info("Generated presentation: %s (%d bytes)", artifact.filename, artifact.size_bytes)

            return {"success": True, "artifact": _card(artifact)}

        except CompilationError as e:
            logger.exception("Presentation compilation failed")
            return {"success": False, "error": f"Compilation failed: {e}"}
        except RenderError as e:
            logger.exception("Presentation rendering failed")
            return {"success": False, "error": f"Rendering failed: {e}"}
        except PresentonNotFoundError as e:
            logger.exception("Presenton CLI not found")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.exception("Presentation generation failed")
            return {"success": False, "error": f"Presentation generation failed: {e}"}

    async def _generate_script(
        self,
        request_text: str,
        input_data: Dict[str, Any],
    ) -> PresentationScript:
        """Ask the model for a PresentationScript, or fail. Never invent one.

        Same history and same fix as `MotionRuntime._generate_script`: a method
        that does not exist, a raw HTTP post outside the egress gate, a model name
        in the code, and a mock presentation when it all failed.
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(request_text, input_data)
        if self._complete is None:
            raise GenerationUnavailable(
                "Presentation generation has no model to ask: it is not connected to the routed engine."
            )
        model = None
        if self._model_resolver:
            try:
                model = await self._model_resolver("presentation.generate")
            except Exception:  # noqa: BLE001 - the engine's own default is the fallback
                model = None
        try:
            response = await self._complete(user_prompt, system_prompt, model)
        except Exception as exc:  # noqa: BLE001
            raise GenerationUnavailable(f"The model could not write the presentation: {exc}") from exc
        return self._parse_script_response(response)

    def _build_system_prompt(self) -> str:
        """Build system prompt with Presenton design vocabulary."""
        return """You are Zaram's presentation designer. You output ONLY valid JSON matching the PresentationScript schema.

DESIGN VOCABULARY — Use only these slide layouts and element types:

SLIDE LAYOUTS:
- "title": Hero title slide — centered title + subtitle
- "content": Standard content slide — title + body elements  
- "two_column": Two-column layout — left/right element groups
- "metric_focus": Metrics dashboard — grid of metric elements
- "quote": Quote/testimonial slide — large quote + attribution
- "section": Section divider — large text, full-slide background

ELEMENT TYPES (with content structure):
- "title": {"text": "string"}
- "subtitle": {"text": "string"}
- "body": {"text": "string"}
- "bullet_list": {"items": ["string"], "ordered": false}
- "metric": {"value": "string", "label": "string"}
- "chart": {"data": {}, "type": "bar|line|pie", "title": "string"}
- "image": {"src": "string", "alt": "string"}
- "table": {"header": ["string"], "rows": [["string"]]}
- "divider": {"text": "string"}

STYLE TOKENS (Tailwind-style, parsed not eval'd):
- text-white, text-slate-400, text-4xl, text-2xl, font-bold, font-semibold
- bg-slate-900, bg-slate-800, p-8, px-6, py-4

OUTPUT SCHEMA (must match exactly):
{
  "meta": {"title": "string", "aspect_ratio": "16:9", "template_id": "corporate_dark_v1"},
  "theme": {
    "colors": {"primary": "#1e293b", "secondary": "#334155", "accent": "#22d3ee", "background": "#0f172a", "text": "#f8fafc", "muted": "#94a3b8"},
    "fonts": {"heading": "Inter", "body": "Inter", "mono": "JetBrains Mono"},
    "spacing": {"base": 24, "lg": 32, "xl": 48}
  },
  "slides": [
    {
      "layout": "content",
      "background": "",
      "elements": [
        {"type": "title", "content": {"text": "Slide Title"}, "style": "text-white text-4xl font-bold"},
        {"type": "bullet_list", "content": {"items": ["Point 1", "Point 2"], "ordered": false}, "style": "text-slate-400"}
      ],
      "speaker_notes": "Speaker notes here"
    }
  ],
  "claims": []
}

RULES:
1. Output ONLY the JSON object — no markdown, no explanation
2. Every slide must have at least one element
3. Use metric elements for KPIs/numbers — they render as designed metric cards
4. Use two_column for comparisons, metric_focus for dashboards
5. Include speaker_notes for each slide
6. Reference facts via claims array (handled by caller)"""

    def _build_user_prompt(self, request: str, input_data: Dict) -> str:
        """Build user prompt with context."""
        context_parts = []
        
        if input_data.get("conversation_summary"):
            context_parts.append(f"Conversation context: {input_data['conversation_summary']}")
        
        if input_data.get("project_style"):
            context_parts.append(f"Project style: {input_data['project_style']}")
        
        if input_data.get("brand_colors"):
            context_parts.append(f"Brand colors: {input_data['brand_colors']}")
        
        context = "\n\n".join(context_parts) if context_parts else "No additional context."
        
        return f"""Request: {request}

{context}

Generate a complete PresentationScript JSON for this presentation. Include appropriate slides, layouts, and speaker notes."""

    def _parse_script_response(self, response: str) -> PresentationScript:
        """Parse LLM JSON response into PresentationScript."""
        import json
        data = json.loads(response)
        
        # Parse meta
        meta = PresentationMeta(
            title=data["meta"].get("title", "Presentation"),
            aspect_ratio=data["meta"].get("aspect_ratio", "16:9"),
            template_id=data["meta"].get("template_id", "corporate_dark_v1"),
        )
        
        # Parse theme
        theme_data = data.get("theme", {})
        theme = PresentationTheme(
            colors=theme_data.get("colors", {}),
            fonts=theme_data.get("fonts", {}),
            spacing=theme_data.get("spacing", {}),
        )
        
        # Parse slides
        slides = []
        for s in data["slides"]:
            elements = [
                PresentationElement(
                    type=e["type"],
                    content=e["content"],
                    style=e.get("style", ""),
                    position=e.get("position"),
                )
                for e in s["elements"]
            ]
            slides.append(PresentationSlide(
                layout=s["layout"],
                background=s.get("background", ""),
                elements=elements,
                speaker_notes=s.get("speaker_notes", ""),
            ))
        
        # Claims are handled by caller
        claims = data.get("claims", [])
        
        return PresentationScript(meta=meta, slides=slides, theme=theme, claims=claims)


def _card(artifact: Artifact) -> Dict[str, Any]:
    """Artifact card for conversation display."""
    import os
    payload = artifact.to_dict()
    payload["exists"] = bool(artifact.path) and os.path.isfile(artifact.path)
    payload["download_url"] = f"/artifacts/{artifact.id}/download"
    payload["deliberate"] = True
    return payload