"""Presenton Contracts — Declarative presentation state (the sacred artifact).

The LLM writes this structured JSON; Presenton compiles it to PPTX/PDF.
Never let the LLM write raw binary data or PPTX XML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class PresentationMeta:
    """Presentation-level metadata."""
    title: str
    aspect_ratio: str = "16:9"  # "16:9", "4:3", "1:1"
    template_id: str = "corporate_dark_v1"
    author: str = ""
    date: str = ""


@dataclass(frozen=True)
class PresentationTheme:
    """Design tokens — maps to Presenton theme specification."""
    colors: Dict[str, str] = field(default_factory=lambda: {
        "primary": "#1e293b",
        "secondary": "#334155",
        "accent": "#22d3ee",
        "background": "#0f172a",
        "text": "#f8fafc",
        "muted": "#94a3b8",
    })
    fonts: Dict[str, str] = field(default_factory=lambda: {
        "heading": "Inter",
        "body": "Inter",
        "mono": "JetBrains Mono",
    })
    spacing: Dict[str, int] = field(default_factory=lambda: {
        "base": 24,
        "lg": 32,
        "xl": 48,
    })


@dataclass(frozen=True)
class PresentationElement:
    """One visual element on a slide.
    
    Types are allowlisted — no arbitrary types permitted.
    """
    # Allowlisted types only
    type: str  # "title" | "subtitle" | "body" | "bullet_list" | "metric" | "chart" | "image" | "table" | "divider"
    content: Any  # Structured per type
    style: str = ""  # Tailwind-style tokens, parsed not eval'd
    position: Optional[Dict[str, Any]] = None  # For absolute positioning if needed

    def __post_init__(self) -> None:
        allowed = {"title", "subtitle", "body", "bullet_list", "metric", "chart", "image", "table", "divider"}
        if self.type not in allowed:
            raise ValueError(f"Element type '{self.type}' not allowed. Must be one of: {allowed}")


@dataclass(frozen=True)
class PresentationSlide:
    """One slide in the presentation."""
    layout: str  # "title" | "content" | "two_column" | "metric_focus" | "quote" | "section"
    background: str = ""
    elements: Sequence[PresentationElement] = field(default_factory=list)
    speaker_notes: str = ""

    def __post_init__(self) -> None:
        allowed = {"title", "content", "two_column", "metric_focus", "quote", "section"}
        if self.layout not in allowed:
            raise ValueError(f"Slide layout '{self.layout}' not allowed. Must be one of: {allowed}")


@dataclass(frozen=True)
class PresentationScript:
    """The sacred artifact — declarative presentation state.
    
    This is what the LLM produces. It is stored as JSON and never modified.
    The binary PPTX/PDF is a disposable render artifact.
    """
    meta: PresentationMeta
    slides: Sequence[PresentationSlide]
    theme: PresentationTheme
    # Provenance: which facts/sources informed each slide
    claims: Sequence[Any] = field(default_factory=list)  # ArtifactClaim from artifacts.contracts

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "meta": self.meta.__dict__,
            "slides": [
                {
                    "layout": s.layout,
                    "background": s.background,
                    "elements": [
                        {
                            "type": e.type,
                            "content": e.content,
                            "style": e.style,
                            "position": e.position,
                        }
                        for e in s.elements
                    ],
                    "speaker_notes": s.speaker_notes,
                }
                for s in self.slides
            ],
            "theme": self.theme.__dict__,
            "claims": [c.to_dict() if hasattr(c, 'to_dict') else str(c) for c in self.claims],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PresentationScript":
        """Deserialize from JSON dict."""
        meta = PresentationMeta(**data["meta"])
        theme = PresentationTheme(**data["theme"])
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
        # Claims are opaque here — resolved at runtime
        claims = data.get("claims", [])
        return cls(meta=meta, slides=slides, theme=theme, claims=claims)


# --- Element content schemas (for LLM guidance) ---

ELEMENT_CONTENT_SCHEMAS = {
    "title": {"text": "string"},
    "subtitle": {"text": "string"},
    "body": {"text": "string"},
    "bullet_list": {"items": ["string"], "ordered": "boolean"},
    "metric": {"value": "string", "label": "string"},
    "chart": {"data": "object", "type": "bar|line|pie", "title": "string"},
    "image": {"src": "string (data URI or path)", "alt": "string"},
    "table": {"header": ["string"], "rows": [["string"]]},
    "divider": {"text": "string"},
}

SLIDE_LAYOUTS = {
    "title": "Hero title slide — centered title + subtitle",
    "content": "Standard content slide — title + body elements",
    "two_column": "Two-column layout — left/right element groups",
    "metric_focus": "Metrics dashboard — grid of metric elements",
    "quote": "Quote/testimonial slide — large quote + attribution",
    "section": "Section divider — large text, full-slide background",
}