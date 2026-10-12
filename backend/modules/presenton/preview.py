"""Presenton Preview — Lightweight HTML preview for conversation cards.

Renders slide thumbnails from PresentationScript without Presenton CLI.
Used for in-conversation artifact preview.
"""

from __future__ import annotations

from .contracts import PresentationScript, PresentationSlide, PresentationElement


def render_preview_html(script: PresentationScript) -> str:
    """Generate lightweight HTML preview of the presentation."""
    slides_html = []
    for i, slide in enumerate(script.slides):
        elements_html = []
        for el in slide.elements:
            elements_html.append(_render_element_preview(el))
        
        slides_html.append(f"""
        <div class="slide-preview" data-layout="{slide.layout}">
            <div class="slide-thumbnail">
                {''.join(elements_html)}
            </div>
            <div class="slide-meta">
                <span class="slide-number">Slide {i+1}</span>
                <span class="slide-layout">{slide.layout}</span>
            </div>
        </div>
        """)
    
    theme = script.theme
    colors = theme.colors
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{script.meta.title}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: {theme.fonts.get('body', 'Inter')}, sans-serif;
            background: {colors.get('background', '#0f172a')};
            color: {colors.get('text', '#f8fafc')};
            margin: 0;
            padding: 16px;
        }}
        .presentation-title {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 16px;
            color: {colors.get('text', '#f8fafc')};
        }}
        .slides-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 12px;
        }}
        .slide-preview {{
            background: {colors.get('secondary', '#334155')};
            border: 1px solid {colors.get('primary', '#1e293b')};
            border-radius: 8px;
            overflow: hidden;
        }}
        .slide-thumbnail {{
            aspect-ratio: 16/9;
            padding: 12px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            overflow: hidden;
        }}
        .slide-meta {{
            padding: 8px 12px;
            background: {colors.get('primary', '#1e293b')};
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: {colors.get('muted', '#94a3b8')};
        }}
        .slide-layout {{
            text-transform: capitalize;
        }}
        /* Element previews */
        .el-title {{ font-size: 18px; font-weight: 700; }}
        .el-subtitle {{ font-size: 14px; opacity: 0.7; }}
        .el-body {{ font-size: 12px; opacity: 0.8; }}
        .el-bullet_list {{ font-size: 11px; display: flex; flex-direction: column; gap: 4px; }}
        .el-bullet_list::before {{ content: "• "; }}
        .el-metric {{ font-size: 12px; background: {colors.get('accent', '#22d3ee')}; color: {colors.get('background', '#0f172a')}; padding: 4px 8px; border-radius: 4px; font-weight: 600; }}
        .el-chart {{ font-size: 11px; opacity: 0.6; }}
        .el-table {{ font-size: 10px; opacity: 0.6; }}
        .el-divider {{ font-size: 16px; font-weight: 600; text-align: center; }}
    </style>
</head>
<body>
    <div class="presentation-title">{script.meta.title}</div>
    <div class="slides-grid">
        {''.join(slides_html)}
    </div>
</body>
</html>"""


def _render_element_preview(el: PresentationElement) -> str:
    """Render a single element for preview."""
    css_class = f"el-{el.type.replace('_', '-')}"
    content = el.content
    
    if el.type == "title":
        text = content.get("text", "") if isinstance(content, dict) else str(content)
        return f'<div class="{css_class}">{text}</div>'
    
    elif el.type == "subtitle":
        text = content.get("text", "") if isinstance(content, dict) else str(content)
        return f'<div class="{css_class}">{text}</div>'
    
    elif el.type == "body":
        text = content.get("text", "") if isinstance(content, dict) else str(content)
        return f'<div class="{css_class}">{text[:80]}{"..." if len(text) > 80 else ""}</div>'
    
    elif el.type == "bullet_list":
        items = content.get("items", []) if isinstance(content, dict) else []
        items_html = "".join(f'<div>{item[:40]}{"..." if len(item) > 40 else ""}</div>' for item in items[:3])
        return f'<div class="{css_class}">{items_html}</div>'
    
    elif el.type == "metric":
        value = content.get("value", "") if isinstance(content, dict) else str(content)
        label = content.get("label", "") if isinstance(content, dict) else ""
        return f'<div class="{css_class}">{value} <span style="font-weight:400;font-size:10px;opacity:0.8">{label}</span></div>'
    
    elif el.type == "chart":
        title = content.get("title", "Chart") if isinstance(content, dict) else "Chart"
        return f'<div class="{css_class}">[Chart: {title}]</div>'
    
    elif el.type == "table":
        return f'<div class="{css_class}">[Table]</div>'
    
    elif el.type == "divider":
        text = content.get("text", "") if isinstance(content, dict) else str(content)
        return f'<div class="{css_class}">{text}</div>'
    
    elif el.type == "image":
        return f'<div class="{css_class}">[Image]</div>'
    
    return f'<div class="{css_class}">[{el.type}]</div>'