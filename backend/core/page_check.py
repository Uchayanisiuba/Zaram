"""Run a page before the person does, and say whether it worked.

Written 5 October 2026, from one page. A Minecraft-style game the resident model
wrote froze the window the moment it started -- twenty-three loops with no
`++` -- and the person was the first to find out, an hour into the work. Someone
using an agent harness with the same model did not hit it, and the likeliest
difference is not the model: a harness runs what it writes, sees the freeze or
the error, and fixes it before showing anything. Zaram showed the first draft.

This is the half of that which has to live in the backend: **run the page
somewhere it can be killed, and report what happened.** The renderer cannot
do it safely, because a page that never ends freezes the process it runs in.

**The page runs exactly as the preview runs it.** The caller sends the frame
document it would put in the preview (policy, shims, vendored libraries and
all) and it is loaded here inside the same kind of sealed frame --
`sandbox="allow-scripts allow-pointer-lock"`, an opaque origin. A check run
under a looser setup would pass pages the preview then breaks.

**Nothing leaves.** The browser is launched with name resolution switched off
(`--host-resolver-rules`), so even a page that got past its own policy could
not reach a host. This is a check run on the person's machine on text from a
model; rule 3 applies to it as to anything.

**Hangs are found by heartbeat, not by timeout on one call.** A small script
is placed ahead of the page and posts a beat every 250 ms. A page stuck in a
loop stops the beats, and so does one stuck in a long but finite start-up; they
are told apart by the end: still no beat after `HANG_BUDGET_SECONDS` is a hang,
a gap that closed is a *slow start*, reported with its length because a page
that holds the window still for seven seconds reads as broken whether or not
it ever recovers. Whichever process the frame ends up in, the beat is the
frame's own, so the check does not depend on that.

**Unverified is a verdict.** No Chrome or Edge, a browser that would not start,
a page too large -- each returns `checked: false` with the reason, never `ok`.
A page nobody could run is not a page that passed, and the interface says so.

**What it does not do:** it does not play the game. It proves the page starts,
stays alive for a few seconds and throws nothing; whether the floor holds is
for the person, or for a later check that can press keys.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from packs.code.driving import NO_BROWSER, DrivingTools, _Protocol  # noqa: F401 - _Protocol typed below
from packs.code.apps import find_browser

logger = logging.getLogger(__name__)

#: Seconds the page must stay alive for, from load, before it is called fine.
SETTLE_SECONDS = 3.0

#: Seconds to wait for a first sign of life before calling it a hang. Software
#: rendering on a machine with no GPU builds a large world slowly, so this is
#: generous; an endless loop does not recover however long it is given.
HANG_BUDGET_SECONDS = 14.0

#: A start-up gap longer than this is reported even when the page recovers.
SLOW_START_SECONDS = 3.0

#: How long one read of the page's state may take before the page is treated
#: as not answering.
PROBE_TIMEOUT_SECONDS = 3.0

#: The largest frame document that will be run. A page this large is not a
#: reply from a model, and the request is refused rather than loaded.
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024

#: Errors that describe this machine rather than the page. Software GL may be
#: unavailable to a headless browser while the person's own window has a GPU;
#: reporting that as the page's fault would send a model to fix nothing.
_ENVIRONMENT = re.compile(
    r"webgl|web gl|getContext|gl context|swiftshader|graphics|gpu|"
    r"pointer ?lock|requestPointerLock|fullscreen|user gesture|"
    r"audiocontext|autoplay|ResizeObserver loop",
    re.IGNORECASE,
)

#: Placed ahead of the page, inside the frame. Beats, and reports what the
#: frame's own reporter does not: where an error was, and a `console.error`.
PROBE = (
    "<script>(function(){var p=window.parent;"
    "function s(m){try{p.postMessage(m,'*')}catch(e){}}"
    "s({__zaramCheck:'beat'});"
    "setInterval(function(){s({__zaramCheck:'beat'})},250);"
    "window.addEventListener('error',function(e){"
    "s({__zaramCheck:'error',text:String(e.message||'script error')+(e.lineno?' (line '+e.lineno+')':'')})});"
    "window.addEventListener('unhandledrejection',function(e){"
    "s({__zaramCheck:'error',text:'unhandled rejection: '+String((e.reason&&e.reason.message)||e.reason)})});"
    "var ce=console.error;console.error=function(){"
    "try{s({__zaramCheck:'error',text:'console.error: '+Array.prototype.map.call(arguments,String).join(' ').slice(0,300)})}catch(x){}"
    "return ce.apply(console,arguments)};"
    "})();</script>"
)

#: The page the frame is put in. Collects the frame's beats and errors.
WRAPPER = """
(function (doc) {
  var st = window.__zaramCheck = { beats: 0, last: 0, maxGap: 0, start: performance.now(), errors: [], blocked: [] };
  window.addEventListener('message', function (e) {
    var d = e.data;
    if (!d) return;
    if (d.__zaramCheck === 'beat') {
      var n = performance.now();
      var gap = n - (st.last || st.start);
      if (gap > st.maxGap) st.maxGap = gap;
      st.last = n; st.beats++;
    } else if (d.__zaramCheck === 'error') {
      if (st.errors.length < 12) st.errors.push(String(d.text));
    } else if (d.__zaramPreview && d.kind === 'blocked') {
      if (st.blocked.length < 12) st.blocked.push(String(d.uri || d.detail));
    }
  });
  var f = document.createElement('iframe');
  f.setAttribute('sandbox', 'allow-scripts allow-pointer-lock');
  f.style.cssText = 'position:fixed;left:0;top:0;width:1280px;height:800px;border:0';
  f.srcdoc = doc;
  document.body.appendChild(f);
  return true;
})(%s)
"""

READ_STATE = """JSON.stringify((function(){var s=window.__zaramCheck;if(!s)return null;var n=performance.now();
return {beats:s.beats,ago:n-(s.last||s.start),maxGap:s.maxGap,elapsed:n-s.start,errors:s.errors,blocked:s.blocked};})())"""

#: Software GL, so a three.js page can make a context in a headless browser,
#: and no route to any host at all, so nothing can leave.
BROWSER_ARGS = (
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    "--ignore-gpu-blocklist",
    "--autoplay-policy=no-user-gesture-required",
    "--host-resolver-rules=MAP * ~NOTFOUND",
    # Name resolution does not stop an address written as numbers, and Chrome
    # bypasses its proxy for loopback unless told not to. Every request is sent
    # to a port nothing listens on, loopback and numeric addresses included.
    "--proxy-server=http://127.0.0.1:9",
    "--proxy-bypass-list=<-loopback>",
)


@dataclass
class PageVerdict:
    #: Whether the page was run at all. ``False`` is "could not check", never "fine".
    checked: bool
    #: ``True`` only when it was run, stayed alive and threw nothing. ``None``
    #: when it was not checked.
    ok: Optional[bool] = None
    hung: bool = False
    #: What the page threw or logged as an error, in the order it happened.
    errors: List[str] = field(default_factory=list)
    #: Hosts the page asked for that the seal refused.
    blocked: List[str] = field(default_factory=list)
    #: The longest stretch the page did not answer at start-up.
    blocked_seconds: float = 0.0
    #: Environment-only messages that were set aside, so nothing is hidden.
    ignored: List[str] = field(default_factory=list)
    #: Why it was not checked, or one plain line about a slow start.
    note: str = ""

    def problems(self) -> List[str]:
        """What to tell a model, one plain sentence each."""
        out: List[str] = []
        if self.hung:
            out.append(
                "The page stopped responding while it started and never recovered. "
                "Look for a loop that never ends (a `for` or `while` whose counter or "
                "condition never changes) or work that runs without a limit at start-up."
            )
        for text in self.errors:
            out.append(f"The page reported an error: {text}")
        for host in self.blocked:
            out.append(
                f"The page asked for {host}, which is not available offline in the preview. "
                "Use only what is written in the page, or the libraries named in the guidance."
            )
        return out

    def as_dict(self) -> Dict[str, Any]:
        return {
            "checked": self.checked,
            "ok": self.ok,
            "hung": self.hung,
            "errors": self.errors,
            "blocked": self.blocked,
            "blocked_seconds": round(self.blocked_seconds, 1),
            "ignored": self.ignored,
            "note": self.note,
            "problems": self.problems(),
        }


_lock = threading.Lock()
_tools: Optional[DrivingTools] = None


def _driver(browser: Optional[str]) -> DrivingTools:
    global _tools
    if browser:
        return DrivingTools(browser=browser)
    if _tools is None:
        _tools = DrivingTools()
    return _tools


def _unchecked(reason: str) -> PageVerdict:
    return PageVerdict(checked=False, ok=None, note=reason)


def check_page(
    document: str,
    *,
    browser: Optional[str] = None,
    settle_seconds: float = SETTLE_SECONDS,
    hang_budget_seconds: float = HANG_BUDGET_SECONDS,
) -> PageVerdict:
    """Load ``document`` in a sealed frame in a throwaway browser and report.

    One check at a time: each starts a browser, and a reply that wrote three
    pages must not start three. Never raises; every failure is a verdict that
    says it did not check.
    """
    if not (document or "").strip():
        return _unchecked("there was no page to run")
    if len(document.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        return _unchecked("the page is too large to check")
    if not (browser or find_browser()):
        return _unchecked(NO_BROWSER)

    with _lock:
        driver = _driver(browser)
        session = None
        try:
            session = driver._launch("about:blank", extra_args=BROWSER_ARGS, software_gl=True)
            return _run(driver, session, document, settle_seconds, hang_budget_seconds)
        except Exception as exc:  # noqa: BLE001 - a check that cannot run says so
            logger.info("page check could not run: %s", exc)
            return _unchecked(f"the check could not run ({exc})")
        finally:
            if session is not None:
                # Never allowed to replace the verdict with its own failure.
                try:
                    driver._shut(session)
                except Exception:  # noqa: BLE001
                    logger.warning("page check: the browser was not cleaned up", exc_info=True)


def _run(driver: DrivingTools, session: Any, document: str, settle: float, budget: float) -> PageVerdict:
    framed = PROBE + document

    def work(cdp: "_Protocol"):
        async def go() -> PageVerdict:
            await cdp.call("Page.enable")
            await cdp.evaluate(WRAPPER % json.dumps(framed))
            deadline = time.monotonic() + budget
            alive = False
            state: Optional[Dict[str, Any]] = None
            while True:
                await asyncio.sleep(0.5)
                try:
                    raw = await asyncio.wait_for(cdp.evaluate(READ_STATE), PROBE_TIMEOUT_SECONDS)
                    state = json.loads(raw) if isinstance(raw, str) else None
                except (asyncio.TimeoutError, TimeoutError):
                    state = None
                except (RuntimeError, ValueError):
                    state = None
                if state and state["beats"] > 0 and state["elapsed"] >= settle * 1000 and state["ago"] < 1500:
                    alive = True
                    break
                if time.monotonic() > deadline:
                    break
            if state is None:
                # The last read timed out. Try once for what was seen before it.
                try:
                    raw = await asyncio.wait_for(cdp.evaluate(READ_STATE), PROBE_TIMEOUT_SECONDS)
                    state = json.loads(raw) if isinstance(raw, str) else None
                except Exception:  # noqa: BLE001
                    state = None
            return _verdict(alive, state)

        return go()

    return driver._run(session, work)


def _verdict(alive: bool, state: Optional[Dict[str, Any]]) -> PageVerdict:
    errors: List[str] = []
    ignored: List[str] = []
    blocked: List[str] = []
    seconds = 0.0
    if state:
        seconds = float(state.get("maxGap", 0.0)) / 1000.0
        for text in state.get("errors", []):
            bucket = ignored if _ENVIRONMENT.search(text) else errors
            if text not in bucket:
                bucket.append(text)
        for host in state.get("blocked", []):
            if host and host not in blocked and re.match(r"^https?:", host):
                blocked.append(host)
    hung = not alive
    note = ""
    if hung:
        seconds = max(seconds, HANG_BUDGET_SECONDS)
        note = f"the page did not respond for {HANG_BUDGET_SECONDS:.0f} seconds"
    elif seconds >= SLOW_START_SECONDS:
        note = f"the page held still for {seconds:.1f} seconds while it started"
    return PageVerdict(
        checked=True,
        ok=(not hung and not errors),
        hung=hung,
        errors=errors[:5],
        blocked=blocked[:5],
        blocked_seconds=seconds,
        ignored=ignored[:5],
        note=note,
    )
