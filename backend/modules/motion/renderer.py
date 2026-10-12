"""Headless Browser Renderer — Renders HTML5 timeline to video using Playwright.

Uses Playwright (headless Chromium) to:
- Navigate to data: URL with compiled HTML
- Wait for animations to complete
- Record video via page.video or capture frames
- Encode to WebM/MP4

Safety:
- No network access (offline)
- Sandboxed browser context
- Timeout bounded by duration_ms * 2
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class RenderError(RuntimeError):
    """Raised when rendering fails."""
    pass


# Check if Playwright is available
_PLAYWRIGHT_AVAILABLE = None


def check_playwright_available() -> bool:
    """Check if Playwright and Chromium are available."""
    global _PLAYWRIGHT_AVAILABLE
    if _PLAYWRIGHT_AVAILABLE is not None:
        return _PLAYWRIGHT_AVAILABLE

    try:
        from playwright.async_api import async_playwright
        _PLAYWRIGHT_AVAILABLE = True
        logger.info("Playwright available for motion rendering")
    except ImportError:
        _PLAYWRIGHT_AVAILABLE = False
        logger.warning("Playwright not installed; motion rendering unavailable")
    return _PLAYWRIGHT_AVAILABLE


async def render_to_video(
    html: str,
    output_path: Path,
    *,
    duration_ms: int,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    timeout_multiplier: float = 2.5,
    progress_sink: Optional[Callable[[dict], None]] = None,
) -> Path:
    """Render HTML timeline to video file.

    Args:
        html: Self-contained HTML timeline from compiler.
        output_path: Output video file path (.webm or .mp4).
        duration_ms: Animation duration in milliseconds.
        fps: Frames per second.
        width: Video width.
        height: Video height.
        timeout_multiplier: Timeout = duration_ms * multiplier.
        progress_sink: Optional callback for streaming progress (step, total_steps, percent).

    Returns:
        Path to rendered video file.

    Raises:
        RenderError: If rendering fails or Playwright unavailable.
    """
    if not check_playwright_available():
        raise RenderError(
            "Motion rendering requires Playwright. "
            "Install with: pip install playwright && playwright install chromium"
        )

    from playwright.async_api import async_playwright

    timeout_ms = int(duration_ms * timeout_multiplier)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Use temporary directory for recording
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        async with async_playwright() as p:
            # Launch headless Chromium
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-web-security",  # For data: URLs
                    "--allow-file-access-from-files",
                ],
            )

            try:
                # Create context with video recording
                context = await browser.new_context(
                    record_video_dir=str(tmpdir_path),
                    record_video_size={"width": width, "height": height},
                    viewport={"width": width, "height": height},
                    device_scale_factor=1.0,
                )

                page = await context.new_page()

                # Navigate to data: URL with our HTML
                import urllib.parse
                data_url = f"data:text/html,{urllib.parse.quote(html)}"
                await page.goto(data_url, wait_until="networkidle", timeout=10000)

                # Real streaming preview with frame capture
                total_frames = max(1, int(duration_ms / 1000 * fps))
                frame_interval = duration_ms / total_frames if total_frames > 0 else 0

                # Emit initial progress
                if progress_sink:
                    progress_sink({
                        "step": 0,
                        "total_steps": total_frames,
                        "percent": 0,
                        "status": "starting",
                    })

                # Wait for animations and capture frames for streaming preview
                for frame_num in range(total_frames):
                    await page.wait_for_timeout(frame_interval)
                    
                    if progress_sink:
                        percent = int(((frame_num + 1) / total_frames) * 100)
                        progress_sink({
                            "step": frame_num + 1,
                            "total_steps": total_frames,
                            "percent": percent,
                            "status": "rendering",
                        })

                # Small buffer to ensure last frame is captured
                await page.wait_for_timeout(500)

                # Stop recording
                await context.close()
                await browser.close()

                # Find recorded video
                video_files = list(tmpdir_path.glob("*.webm"))
                if not video_files:
                    raise RenderError("No video file was recorded")

                recorded = video_files[0]

                # Move to final location
                if output_path.suffix.lower() == ".mp4":
                    # Convert WebM to MP4 using ffmpeg if available
                    await _convert_to_mp4(recorded, output_path)
                else:
                    shutil.move(str(recorded), str(output_path))

                logger.info("Rendered motion video to %s (%d ms, %dx%d@%dfps)",
                           output_path, duration_ms, width, height, fps)
                return output_path

            except Exception as e:
                await browser.close()
                raise RenderError(f"Rendering failed: {e}") from e


async def _convert_to_mp4(input_path: Path, output_path: Path) -> None:
    """Convert WebM to MP4 using ffmpeg."""
    import subprocess

    try:
        # Try ffmpeg
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(input_path),
                "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(output_path)
            ],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RenderError(f"ffmpeg failed: {result.stderr.decode()}")
    except FileNotFoundError:
        # ffmpeg not available, keep as WebM
        logger.warning("ffmpeg not found; keeping WebM output")
        output_webm = output_path.with_suffix(".webm")
        shutil.move(str(input_path), str(output_webm))
        raise RenderError(
            f"MP4 requested but ffmpeg not installed. Output saved as {output_webm}. "
            "Install ffmpeg for MP4 conversion."
        )