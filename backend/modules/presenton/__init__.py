"""Presenton Module — Presentation generation via Presenton engine."""

from .contracts import (
    PresentationScript,
    PresentationMeta,
    PresentationSlide,
    PresentationElement,
    PresentationTheme,
    ELEMENT_CONTENT_SCHEMAS,
    SLIDE_LAYOUTS,
)
from .compiler import compile_presentation, PresentonIR, CompilationError
from .renderer import render_to_pptx, render_to_pdf, RenderError, PresentonNotFoundError
from .runtime import PresentonRuntime, GENERATE as PRESENTON_GENERATE
from .preview import render_preview_html

__all__ = [
    "PresentationScript",
    "PresentationMeta", 
    "PresentationSlide",
    "PresentationElement",
    "PresentationTheme",
    "ELEMENT_CONTENT_SCHEMAS",
    "SLIDE_LAYOUTS",
    "compile_presentation",
    "PresentonIR",
    "CompilationError",
    "render_to_pptx",
    "render_to_pdf",
    "RenderError",
    "PresentonNotFoundError",
    "PresentonRuntime",
    "PRESENTON_GENERATE",
    "render_preview_html",
]