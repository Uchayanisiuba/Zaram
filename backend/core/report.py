"""What a person sends when Zaram misbehaves — assembled here, sent by them.

**Zaram never phones home, so feedback has to travel with the person.**
Telemetry is prohibited (rule 7g) and a thumbs button is refused (rule 7f),
which leaves the honest channel: a report the person reads, copies and
pastes wherever they talk to the maintainer — a reply to the tester email,
a GitHub issue. This module writes that report. Nothing here opens a
socket; the interface puts the text on the clipboard.

**What is in it is what a maintainer needs to reproduce a fault and nothing
that would embarrass the person to paste.** Version, platform, the card and
its memory, which models were found and where they run, the routing
choices, the image setting, which providers are connected — *by id, never a
key* — and the last few egress decisions as host, class, decision and
reason, **never the body**. No conversation text, no file names from
Knowledge, no facts from the Spine. The report says so at the top, so the
person can check the claim against the text below it.
"""

from __future__ import annotations

import platform
import sys
import time
from typing import Any, Iterable, List, Optional

VERSION = "0.1.0"


def _gb(n: Optional[int]) -> str:
    return "unknown" if not isinstance(n, (int, float)) or n <= 0 else f"{n / 1e9:.1f} GB"


def build_report(
    *,
    manager: Any = None,
    settings: Any = None,
    connections: Iterable[Any] = (),
    egress_entries: Iterable[Any] = (),
    images: Optional[dict] = None,
    version: str = VERSION,
) -> str:
    """The report as plain text. Every argument is optional; a part that
    cannot be read is written as unknown rather than left out, so the person
    can see that Zaram could not read it."""
    lines: List[str] = [
        f"Zaram {version} — problem report, {time.strftime('%Y-%m-%d %H:%M')}",
        "Contains: version, platform, hardware, models found, routing choices, "
        "connected providers by id, and the last egress decisions without their contents.",
        "Contains no conversation text, no document names, no remembered facts, no keys.",
        "",
        f"Platform: {platform.system()} {platform.release()} · Python {sys.version.split()[0]}",
    ]

    hw = getattr(manager, "hardware_profile", None)
    profile = hw() if callable(hw) else None
    if profile is not None:
        lines.append(
            f"Hardware: {getattr(profile, 'cpu_model', 'unknown')} · "
            f"RAM {_gb(getattr(profile, 'total_ram_bytes', None))} · "
            f"GPU {getattr(profile, 'gpu_name', 'unknown')} · VRAM {_gb(getattr(profile, 'vram_bytes', None))}"
        )
    else:
        lines.append("Hardware: unknown")

    lines.append("")
    lines.append("Models found:")
    catalog = getattr(manager, "catalog", None)
    models = list(catalog.all()) if catalog is not None and hasattr(catalog, "all") else []
    if not models:
        lines.append("  none, or the catalogue could not be read")
    for m in sorted(models, key=lambda x: str(getattr(x, "id", ""))):
        where = getattr(getattr(m, "locality", None), "value", "unknown")
        window = getattr(m, "context_length", None)
        lines.append(
            f"  {getattr(m, 'id', '?')} · {where}"
            + (f" · window {window:,}" if isinstance(window, int) else "")
            + ("" if getattr(m, "available", True) else " · unavailable")
        )

    lines.append("")
    if settings is not None:
        pref = getattr(getattr(settings, "routing_preference", None), "value", "unknown")
        default = getattr(settings, "default_model", None) or "Zaram's pick"
        slots = getattr(settings, "task_models", {}) or {}
        lines.append(f"Routing: {pref} · default {default}")
        lines.append("Per task: " + (", ".join(f"{k}={v}" for k, v in slots.items()) if slots else "nothing assigned"))
        lines.append(f"Pictures: prefer {getattr(getattr(settings, 'image_locality', None), 'value', 'unknown')}")
    else:
        lines.append("Routing: settings could not be read")
    if images:
        lines.append(
            "Can draw: "
            + (f"yes — {images.get('answers')}" if images.get("answers") else "no")
            + (f" · local ok: {images.get('local_ok')}" if "local_ok" in images else "")
        )

    lines.append("")
    ids = [str(getattr(c, "provider_id", None) or (c.get("provider_id") if isinstance(c, dict) else c)) for c in connections]
    lines.append("Connected providers: " + (", ".join(ids) if ids else "none"))

    lines.append("")
    lines.append("Last egress decisions (newest first):")
    shown = 0
    for e in egress_entries:
        at = getattr(e, "at", None)
        when = time.strftime("%H:%M:%S", time.localtime(at)) if isinstance(at, (int, float)) else "?"
        cls = getattr(getattr(e, "data_class", None), "value", getattr(e, "data_class", "prompt"))
        lines.append(
            f"  {when} {getattr(e, 'host', '?')} · {cls} · {getattr(e, 'decision', '?')} — {getattr(e, 'reason', '')}"
        )
        shown += 1
        if shown >= 12:
            break
    if not shown:
        lines.append("  none")

    return "\n".join(lines) + "\n"
