"""Presenton Compiler — Compiles PresentationScript to Presenton Intermediate Representation.

The IR is a pure Python dict structure that the renderer passes to Presenton CLI.
No external dependencies in compilation — just data transformation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from .contracts import PresentationScript, PresentationSlide, PresentationElement, PresentationTheme


class PresentonIR:
    """Presenton's internal representation — what the renderer consumes via CLI."""
    
    def __init__(self, script: PresentationScript):
        self.meta = script.meta
        self.theme = self._compile_theme(script.theme)
        self.slides = [self._compile_slide(s) for s in script.slides]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": self.meta.__dict__,
            "theme": self.theme,
            "slides": self.slides,
        }
    
    def _compile_theme(self, theme: PresentationTheme) -> Dict[str, Any]:
        """Map Zaram theme tokens to Presenton theme spec."""
        return {
            "colors": theme.colors,
            "fonts": theme.fonts,
            "spacing": theme.spacing,
        }
    
    def _compile_slide(self, slide: PresentationSlide) -> Dict[str, Any]:
        """Compile a slide to Presenton IR slide dict."""
        return {
            "layout": slide.layout,
            "background": slide.background,
            "elements": [self._compile_element(e) for e in slide.elements],
            "speaker_notes": slide.speaker_notes,
        }
    
    def _compile_element(self, el: PresentationElement) -> Dict[str, Any]:
        """Compile element to Presenton IR — maps Zaram types to Presenton types."""
        type_map = {
            "title": "heading",
            "subtitle": "subheading",
            "body": "paragraph",
            "bullet_list": "list",
            "metric": "metric",
            "chart": "chart",
            "image": "image",
            "table": "table",
            "divider": "divider",
        }
        
        return {
            "type": type_map.get(el.type, el.type),
            "content": self._compile_content(el.type, el.content),
            "style": self._parse_tailwind_style(el.style),
            "position": el.position,
        }
    
    def _compile_content(self, el_type: str, content: Any) -> Dict[str, Any]:
        """Structure content per element type for Presenton."""
        if el_type == "bullet_list" and isinstance(content, dict):
            return {
                "items": content.get("items", []),
                "ordered": content.get("ordered", False),
            }
        elif el_type == "metric" and isinstance(content, dict):
            return {
                "value": content.get("value", ""),
                "label": content.get("label", ""),
            }
        elif el_type == "chart" and isinstance(content, dict):
            return {
                "data": content.get("data", {}),
                "chart_type": content.get("type", "bar"),
                "title": content.get("title", ""),
            }
        elif el_type == "image" and isinstance(content, dict):
            return {
                "src": content.get("src", ""),
                "alt": content.get("alt", ""),
            }
        elif el_type == "table" and isinstance(content, dict):
            return {
                "header": content.get("header", []),
                "rows": content.get("rows", []),
            }
        elif el_type in ("title", "subtitle", "body", "divider"):
            return {"text": str(content)}
        return {"raw": content}
    
    def _parse_tailwind_style(self, style: str) -> Dict[str, Any]:
        """Parse Tailwind-style tokens to structured style dict.
        
        Examples:
            "text-white text-4xl font-bold" → {"color": "white", "size": "4xl", "weight": "bold"}
            "bg-slate-900 p-8" → {"background": "slate-900", "padding": 8}
        """
        if not style:
            return {}
        
        result = {}
        tokens = style.split()
        
        for token in tokens:
            # text-{color}
            m = re.match(r"text-(.+)", token)
            if m:
                result["color"] = m.group(1)
                continue
            
            # text-{size}
            m = re.match(r"text-(xs|sm|base|lg|xl|2xl|3xl|4xl|5xl|6xl|7xl|8xl|9xl)", token)
            if m:
                result["size"] = m.group(1)
                continue
            
            # font-{weight}
            m = re.match(r"font-(thin|extralight|light|normal|medium|semibold|bold|extrabold|black)", token)
            if m:
                result["weight"] = m.group(1)
                continue
            
            # bg-{color}
            m = re.match(r"bg-(.+)", token)
            if m:
                result["background"] = m.group(1)
                continue
            
            # p-{size} / px-{size} / py-{size}
            m = re.match(r"p[xy]?-(\d+)", token)
            if m:
                result["padding"] = int(m.group(1)) * 4  # Tailwind units = 4px
                continue
            
            # m-{size} / mx-{size} / my-{size}
            m = re.match(r"m[xy]?-(\d+)", token)
            if m:
                result["margin"] = int(m.group(1)) * 4
                continue
        
        return result


class CompilationError(ValueError):
    """Raised when compilation fails."""
    pass


def compile_presentation(script: PresentationScript) -> PresentonIR:
    """Main entry point: PresentationScript → PresentonIR.
    
    Validates the script structure and produces the IR for rendering.
    """
    # Verify slide structure
    for i, slide in enumerate(script.slides):
        if not slide.elements:
            # Empty slides are allowed (e.g., section dividers with just background)
            pass
    
    return PresentonIR(script)