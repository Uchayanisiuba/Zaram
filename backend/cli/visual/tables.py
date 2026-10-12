"""Comparison tables using rich.table for feature comparisons."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from rich.table import Table as RichTable
from rich.console import Console


class FeatureStatus(Enum):
    """Status of a feature in a system."""
    PRESENT = "present"
    ABSENT = "absent"
    PARTIAL = "partial"
    PLANNED = "planned"


@dataclass
class FeatureRow:
    """A single row in the comparison table."""
    feature: str
    systems: Dict[str, FeatureStatus]
    notes: Optional[str] = None


class ComparisonTableRenderer:
    """Renders feature comparison tables using rich.table."""
    
    MARKERS = {
        FeatureStatus.PRESENT: ("[green]YES[/green]", "green"),      # YES
        FeatureStatus.ABSENT: ("[red]NO[/red]", "red"),              # NO
        FeatureStatus.PARTIAL: ("[yellow]PARTIAL[/yellow]", "yellow"),  # PARTIAL
        FeatureStatus.PLANNED: ("[blue]PLANNED[/blue]", "blue"),     # PLANNED
    }
    
    def __init__(self, show_notes: bool = True):
        self.show_notes = show_notes
    
    def _marker(self, status: FeatureStatus) -> str:
        """Get colored marker for a status."""
        marker, color = self.MARKERS.get(status, ("?", "white"))
        return f"[{color}]{marker}[/{color}]"
    
    def render_feature_comparison(
        self,
        features: List[FeatureRow],
        title: Optional[str] = None,
        system_order: Optional[List[str]] = None,
    ) -> str:
        """Render a feature comparison table."""
        if not features:
            return "No features to compare."
        
        # Determine system columns
        all_systems = set()
        for row in features:
            all_systems.update(row.systems.keys())
        
        if system_order:
            systems = [s for s in system_order if s in all_systems]
            systems += [s for s in all_systems if s not in system_order]
        else:
            systems = sorted(all_systems)
        
        # Build table
        table = RichTable(show_header=True, header_style="bold", box=None, pad_edge=False)
        table.add_column("Feature", style="bold", no_wrap=False)
        
        for system in systems:
            table.add_column(system, style="dim", no_wrap=True, justify="center")
        
        if self.show_notes:
            table.add_column("Notes", style="dim", no_wrap=False)
        
        for row in features:
            cells = [row.feature]
            for system in systems:
                status = row.systems.get(system, FeatureStatus.ABSENT)
                cells.append(self._marker(status))
            if self.show_notes:
                cells.append(row.notes or "")
            table.add_row(*cells)
        
        output = []
        if title:
            output.append(f"\n[bold]{title}[/bold]\n")
        
        console = Console(record=True, width=120)
        console.print(table)
        output.append(console.export_text())
        
        return "".join(output)
    
    def render_simple_comparison(
        self,
        features: List[str],
        systems: Dict[str, Dict[str, FeatureStatus]],
        title: Optional[str] = None,
    ) -> str:
        """Render a simple comparison from feature list and system dicts."""
        rows = []
        for feature in features:
            row_systems = {}
            for system, feature_map in systems.items():
                row_systems[system] = feature_map.get(feature, FeatureStatus.ABSENT)
            rows.append(FeatureRow(feature=feature, systems=row_systems))
        
        system_order = list(systems.keys())
        return self.render_feature_comparison(rows, title=title, system_order=system_order)


# Pre-defined comparison data for common topics
MEMORY_COMPARISON_FEATURES = [
    FeatureRow("Local-first (no cloud required)", {
        "mem0": FeatureStatus.PRESENT,
        "Zaram Spine": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
    FeatureRow("Provenance on every fact", {
        "mem0": FeatureStatus.PARTIAL,
        "Zaram Spine": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
    FeatureRow("Correction loop (rule 4)", {
        "mem0": FeatureStatus.ABSENT,
        "Zaram Spine": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
    FeatureRow("Project-scoped facts (rule 7i)", {
        "mem0": FeatureStatus.ABSENT,
        "Zaram Spine": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
    FeatureRow("Cross-provider recall", {
        "mem0": FeatureStatus.ABSENT,
        "Zaram Spine": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
    FeatureRow("Egress logging (rule 3)", {
        "mem0": FeatureStatus.ABSENT,
        "Zaram Spine": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
    FeatureRow("Per-source privacy policy (rule 5)", {
        "mem0": FeatureStatus.ABSENT,
        "Zaram Spine": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
    FeatureRow("Agent-scoped memory", {
        "mem0": FeatureStatus.PARTIAL,
        "Zaram Spine": FeatureStatus.PLANNED,
        "browser-use": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
    FeatureRow("MCP server exposure", {
        "mem0": FeatureStatus.ABSENT,
        "Zaram Spine": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
    FeatureRow("Auto fact extraction", {
        "mem0": FeatureStatus.PRESENT,
        "Zaram Spine": FeatureStatus.PLANNED,
        "browser-use": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
    FeatureRow("Export in open format (rule 7)", {
        "mem0": FeatureStatus.PARTIAL,
        "Zaram Spine": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.PARTIAL,
    }),
    FeatureRow("CLI access", {
        "mem0": FeatureStatus.ABSENT,
        "Zaram Spine": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.PRESENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
]

BROWSER_COMPARISON_FEATURES = [
    FeatureRow("Headless browser automation", {
        "Zaram (code pack)": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.PRESENT,
        "Playwright": FeatureStatus.PRESENT,
        "Selenium": FeatureStatus.PRESENT,
    }),
    FeatureRow("DevTools protocol (CDP)", {
        "Zaram (code pack)": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.PARTIAL,
        "Playwright": FeatureStatus.PRESENT,
        "Selenium": FeatureStatus.ABSENT,
    }),
    FeatureRow("Visual regression (screenshots)", {
        "Zaram (code pack)": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.PRESENT,
        "Playwright": FeatureStatus.PRESENT,
        "Selenium": FeatureStatus.PRESENT,
    }),
    FeatureRow("Console log capture", {
        "Zaram (code pack)": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.PARTIAL,
        "Playwright": FeatureStatus.PRESENT,
        "Selenium": FeatureStatus.PARTIAL,
    }),
    FeatureRow("Network request interception", {
        "Zaram (code pack)": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.ABSENT,
        "Playwright": FeatureStatus.PRESENT,
        "Selenium": FeatureStatus.PARTIAL,
    }),
    FeatureRow("MCP tool exposure", {
        "Zaram (code pack)": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.ABSENT,
        "Playwright": FeatureStatus.ABSENT,
        "Selenium": FeatureStatus.ABSENT,
    }),
    FeatureRow("Egress-gated network calls", {
        "Zaram (code pack)": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.ABSENT,
        "Playwright": FeatureStatus.ABSENT,
        "Selenium": FeatureStatus.ABSENT,
    }),
    FeatureRow("Local-only execution", {
        "Zaram (code pack)": FeatureStatus.PRESENT,
        "browser-use": FeatureStatus.PRESENT,
        "Playwright": FeatureStatus.PRESENT,
        "Selenium": FeatureStatus.PRESENT,
    }),
]

SEARCH_COMPARISON_FEATURES = [
    FeatureRow("Web search integration", {
        "Zaram (trio)": FeatureStatus.PRESENT,
        "Perplexity": FeatureStatus.PRESENT,
        "LangChain": FeatureStatus.PRESENT,
        "Open WebUI": FeatureStatus.PRESENT,
    }),
    FeatureRow("Egress-logged requests", {
        "Zaram (trio)": FeatureStatus.PRESENT,
        "Perplexity": FeatureStatus.ABSENT,
        "LangChain": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
    FeatureRow("Per-source policy", {
        "Zaram (trio)": FeatureStatus.PRESENT,
        "Perplexity": FeatureStatus.ABSENT,
        "LangChain": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
    FeatureRow("Self-hosted fallback (SearXNG)", {
        "Zaram (trio)": FeatureStatus.PRESENT,
        "Perplexity": FeatureStatus.ABSENT,
        "LangChain": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
    FeatureRow("Rate limiting per provider", {
        "Zaram (trio)": FeatureStatus.PRESENT,
        "Perplexity": FeatureStatus.ABSENT,
        "LangChain": FeatureStatus.PARTIAL,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
    FeatureRow("Byte tracking", {
        "Zaram (trio)": FeatureStatus.PRESENT,
        "Perplexity": FeatureStatus.ABSENT,
        "LangChain": FeatureStatus.ABSENT,
        "Open WebUI": FeatureStatus.ABSENT,
    }),
]

PIPELINE_COMPARISON_FEATURES = [
    FeatureRow("Inlet filters (pre-LLM)", {
        "Zaram": FeatureStatus.PRESENT,
        "LangChain": FeatureStatus.PARTIAL,
        "LlamaIndex": FeatureStatus.PARTIAL,
        "Custom": FeatureStatus.ABSENT,
    }),
    FeatureRow("Outlet filters (post-LLM)", {
        "Zaram": FeatureStatus.PRESENT,
        "LangChain": FeatureStatus.PARTIAL,
        "LlamaIndex": FeatureStatus.ABSENT,
        "Custom": FeatureStatus.ABSENT,
    }),
    FeatureRow("Egress enforcement", {
        "Zaram": FeatureStatus.PRESENT,
        "LangChain": FeatureStatus.ABSENT,
        "LlamaIndex": FeatureStatus.ABSENT,
        "Custom": FeatureStatus.ABSENT,
    }),
    FeatureRow("PII scrubbing", {
        "Zaram": FeatureStatus.PRESENT,
        "LangChain": FeatureStatus.ABSENT,
        "LlamaIndex": FeatureStatus.ABSENT,
        "Custom": FeatureStatus.ABSENT,
    }),
    FeatureRow("Token budget enforcement", {
        "Zaram": FeatureStatus.PRESENT,
        "LangChain": FeatureStatus.PARTIAL,
        "LlamaIndex": FeatureStatus.PARTIAL,
        "Custom": FeatureStatus.ABSENT,
    }),
    FeatureRow("Citation validation", {
        "Zaram": FeatureStatus.PRESENT,
        "LangChain": FeatureStatus.ABSENT,
        "LlamaIndex": FeatureStatus.ABSENT,
        "Custom": FeatureStatus.ABSENT,
    }),
    FeatureRow("Spine context injection", {
        "Zaram": FeatureStatus.PRESENT,
        "LangChain": FeatureStatus.ABSENT,
        "LlamaIndex": FeatureStatus.ABSENT,
        "Custom": FeatureStatus.ABSENT,
    }),
    FeatureRow("Priority-based ordering", {
        "Zaram": FeatureStatus.PRESENT,
        "LangChain": FeatureStatus.PARTIAL,
        "LlamaIndex": FeatureStatus.ABSENT,
        "Custom": FeatureStatus.ABSENT,
    }),
]


def get_comparison_data(topic: str) -> List[FeatureRow]:
    """Get pre-defined comparison data for a topic."""
    topic = topic.lower()
    if topic in ("memory", "mem"):
        return MEMORY_COMPARISON_FEATURES
    elif topic in ("browser", "browsers", "automation"):
        return BROWSER_COMPARISON_FEATURES
    elif topic in ("search", "web_search", "web"):
        return SEARCH_COMPARISON_FEATURES
    elif topic in ("pipeline", "pipes"):
        return PIPELINE_COMPARISON_FEATURES
    else:
        return []


def render_comparison(topic: str, as_json: bool = False) -> str:
    """Render a comparison table for a topic."""
    features = get_comparison_data(topic)
    if not features:
        return f"Unknown comparison topic: {topic}. Available: memory, browser, search, pipeline"
    
    renderer = ComparisonTableRenderer()
    
    if as_json:
        import json
        data = {
            "topic": topic,
            "features": [
                {
                    "feature": f.feature,
                    "systems": {k: v.value for k, v in f.systems.items()},
                    "notes": f.notes,
                }
                for f in features
            ]
        }
        return json.dumps(data, indent=2)
    
    return renderer.render_feature_comparison(features, title=f"Feature Comparison: {topic.title()}")