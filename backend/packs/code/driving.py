"""Driving the app, not only looking at it — slice 9 of the code pack.

`look_at_app` takes one screenshot of one URL. That is enough to check a
layout and not enough to check a *behaviour*, because the interesting states
are three interactions deep: open the panel, choose a type, fill the folder,
press Create. There is no URL you can screenshot to get there, so a defect
living in that state is invisible to a tool that can only look.

Asked for on 3 October 2026, after watching a bug get found exactly that way.

**The same browser, the same rule, no new dependency.** `apps.py` already
states the posture — *"the browser the person already has, Chrome or Edge, no
Playwright, no bundled Chromium: the same posture as bring-your-own model"* —
and this does not weaken it. Chrome's DevTools Protocol is spoken over a
WebSocket to the browser already found by `find_browser()`, and `aiohttp` is
already pinned, so nothing is downloaded and the installer does not move.
Playwright would have cost several hundred megabytes to do what the installed
browser does for free, against a product whose blocker is that a stranger
cannot install it.

**Loopback only, and that is the boundary not a setting.** `_LOOPBACK`
already refuses anything else for screenshots and it refuses it here. The
moment this can drive a page on the open web it stops being "look at your own
app" and becomes a browser agent — a different product, with an egress story
this one does not have.

**A profile of its own, every time.** The browser is launched with a fresh
`--user-data-dir`, so it carries none of the person's cookies, sessions or
history. Zaram's browser is not the person's browser. That is worth more than
convenience here: driving a dev app that happens to share a domain with
something they are signed into should not be able to act as them.

**Structure, not pixels.** `read_app_page` returns the interactive elements
as a short list with refs, not a screenshot. Three reasons and the last is
the one that matters. It is cheap, so a long session fits in a small context
window. It is exact, so "this button is disabled" is a fact rather than
something a vision model reads off a greyed rectangle. And it needs no vision
model at all, which means the capability works on a machine that has none —
`look_at_app` has to say *"no local vision model is available"* and this does
not.

**Real input events.** A click is `Input.dispatchMouseEvent` at the element's
own centre, not `element.click()`. The synthetic version skips the browser's
own event path and will happily "click" something covered by a modal, which
is the failure that teaches you to distrust the whole tool.

A ref is only valid until the page changes under it. The refs are stamped as
`data-zaram-ref` by the read, and a framework re-render drops them — so a
click against a stale ref fails loudly and says to read the page again,
rather than resolving to whatever is at those coordinates now.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtimes.mcp.client import ToolDescriptor

from .apps import _LOOPBACK, find_browser

logger = logging.getLogger(__name__)

OPEN_IN_BROWSER = "open_in_browser"
READ_APP_PAGE = "read_app_page"
CLICK_IN_APP = "click_in_app"
TYPE_IN_APP = "type_in_app"
READ_APP_CONSOLE = "read_app_console"
CLOSE_BROWSER = "close_browser"

TOOL_NAMES = frozenset(
    {OPEN_IN_BROWSER, READ_APP_PAGE, CLICK_IN_APP, TYPE_IN_APP, READ_APP_CONSOLE, CLOSE_BROWSER}
)

#: The tools that change something. Reading a loopback page Zaram started is
#: the same act `look_at_app` already performs; pressing a button in it is
#: not, and the tier table says so.
MUTATIVE = frozenset({CLICK_IN_APP, TYPE_IN_APP})

#: How long to wait for the debugging port after launching the browser.
PORT_WAIT_SECONDS = 15.0

#: How long any one protocol call may take. A page that never settles must
#: not hang the conversation.
CALL_TIMEOUT_SECONDS = 20.0

#: Interactive elements returned at most. A page with more than this is not
#: one a model should be reading element by element, and an unbounded list is
#: how a context window disappears in one tool call.
MAX_ELEMENTS = 120

#: Console lines kept. Enough for a stack trace, bounded so a page in a
#: render loop cannot fill the reply.
MAX_CONSOLE = 100

#: Stamped on each element by the reader so a later click can find the same
#: one. Dropped by a re-render, deliberately — see the module docstring.
REF_ATTRIBUTE = "data-zaram-ref"

NOT_LOOPBACK = (
    "{url} is not on this machine. Zaram drives only localhost — anything else "
    "is browsing, which has its own rules and its own consent."
)

STALE_REF = (
    "No element {ref} is on the page now. It has re-rendered since you read it. "
    "Read the page again and use a ref from that reading."
)

NO_BROWSER = "No Chrome or Edge is installed, so there is no browser to drive."

#: How much of an element's own label may appear in the phrase on the row.
ACTED_LABEL_CHARS = 60


def _said(label: str) -> str:
    """One element's name, safe to put on a row.

    **Page content is third-party text.** `call_target` bounds the model's
    arguments for the same reason and states it: a newline in a label breaks
    one row into two and lets a single call appear to be two. Rendered as
    text by the surface, never as markup, exactly like every other target.
    """
    clean = "".join(ch for ch in (label or "") if ch.isprintable()).strip()
    if len(clean) > ACTED_LABEL_CHARS:
        clean = clean[: ACTED_LABEL_CHARS - 1].rstrip() + "\u2026"
    return clean

NOT_OPEN = f"No page is open. Use `{OPEN_IN_BROWSER}` with a localhost URL first."

#: Recorded in the page itself rather than collected over a held-open
#: connection: each tool call opens its own, so an event stream would miss
#: everything between calls. This runs before the page's own scripts.
CONSOLE_RECORDER = """
(() => {
  if (window.__zaramConsole) return;
  window.__zaramConsole = [];
  const keep = (level, args) => {
    try {
      window.__zaramConsole.push({
        level,
        text: Array.from(args).map((a) => {
          if (a instanceof Error) return a.stack || String(a);
          if (typeof a === 'object') { try { return JSON.stringify(a); } catch { return String(a); } }
          return String(a);
        }).join(' '),
      });
      if (window.__zaramConsole.length > 400) window.__zaramConsole.shift();
    } catch (e) { /* never let recording break the page */ }
  };
  for (const level of ['log', 'info', 'warn', 'error', 'debug']) {
    const original = console[level].bind(console);
    console[level] = (...args) => { keep(level, args); original(...args); };
  }
  window.addEventListener('error', (e) => keep('error', [e.message]));
  window.addEventListener('unhandledrejection', (e) => keep('error', ['unhandled rejection: ' + e.reason]));
})()
"""

#: Returns the interactive elements, each stamped with its ref. Written here
#: rather than built from `Accessibility.getFullAXTree` because the full tree
#: on a real page is tens of thousands of tokens and most of it is layout.
READ_PAGE_JS = """
(() => {
  const SELECTOR = 'a,button,input,select,textarea,summary,[role=button],[role=link],[role=tab],[role=checkbox],[role=menuitem],[onclick],[contenteditable=true]';
  const out = [];
  let n = 0;
  for (const el of document.querySelectorAll(SELECTOR)) {
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) continue;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none' || style.opacity === '0') continue;
    n += 1;
    if (n > %(max)d) break;
    const ref = 'e' + n;
    el.setAttribute('%(attr)s', ref);
    const label = (
      el.getAttribute('aria-label') ||
      (el.innerText || '').trim() ||
      el.value ||
      el.getAttribute('placeholder') ||
      el.getAttribute('title') ||
      ''
    );
    out.push({
      ref,
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || '',
      type: el.getAttribute('type') || '',
      name: String(label).replace(/\\s+/g, ' ').trim().slice(0, 100),
      // Reported because it is the fact a screenshot cannot give you, and
      // the one that explains a button doing nothing.
      disabled: !!(el.disabled || el.getAttribute('aria-disabled') === 'true'),
      checked: el.checked === undefined ? null : !!el.checked,
      value: (el.value === undefined || el.type === 'password') ? null : String(el.value).slice(0, 100),
    });
  }
  const text = (document.body ? document.body.innerText : '').replace(/\\s+/g, ' ').trim().slice(0, 1500);
  return JSON.stringify({ url: location.href, title: document.title, elements: out, text });
})()
""" % {"max": MAX_ELEMENTS, "attr": REF_ATTRIBUTE}


def _centre_js(ref: str) -> str:
    """Where to click for `ref`, or `null` if it is no longer there."""
    return (
        "(() => { const el = document.querySelector('[%s=\"%s\"]');"
        " if (!el) return 'null';"
        " el.scrollIntoView({block: 'center', inline: 'center'});"
        " const r = el.getBoundingClientRect();"
        " const label = el.getAttribute('aria-label') || (el.innerText || '').trim()"
        " || el.getAttribute('placeholder') || el.value || el.tagName.toLowerCase();"
        " return JSON.stringify({x: Math.round(r.left + r.width / 2),"
        " y: Math.round(r.top + r.height / 2),"
        " name: String(label).replace(/\\s+/g, ' ').trim().slice(0, 120),"
        " disabled: !!(el.disabled || el.getAttribute('aria-disabled') === 'true')}); })()"
        % (REF_ATTRIBUTE, ref)
    )


def _select_js(ref: str) -> str:
    """Select what is in the field, so an insert replaces rather than appends."""
    return (
        "(() => { const el = document.querySelector('[%s=\"%s\"]');"
        " if (el && el.select) el.select(); })()" % (REF_ATTRIBUTE, ref)
    )


@dataclass
class BrowserSession:
    """One headless browser, for one project."""

    process: subprocess.Popen
    port: int
    profile: str
    url: str = ""
    started_at: float = field(default_factory=time.time)

    def alive(self) -> bool:
        return self.process.poll() is None


class _Protocol:
    """One DevTools conversation, opened and closed per tool call.

    Stateless by choice. A held-open socket would need reconnect handling, a
    background task and a lifetime tied to neither the app nor the request —
    three things to get wrong for a saving that does not matter at human
    speed. The browser process holds the page state, which is the part that
    has to persist.
    """

    def __init__(self, ws: Any) -> None:
        self._ws = ws
        self._next = 0

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._next += 1
        mine = self._next
        await self._ws.send_json({"id": mine, "method": method, "params": params or {}})
        deadline = time.monotonic() + CALL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            raw = await asyncio.wait_for(self._ws.receive_str(), timeout=CALL_TIMEOUT_SECONDS)
            message = json.loads(raw)
            # Events arrive on the same socket and are not answers. Skipping
            # anything without our id is what keeps a chatty page from being
            # mistaken for a reply.
            if message.get("id") != mine:
                continue
            if "error" in message:
                raise RuntimeError(str(message["error"].get("message", message["error"])))
            return message.get("result", {})
        raise TimeoutError(f"{method} did not answer in {CALL_TIMEOUT_SECONDS:.0f}s")

    async def evaluate(self, expression: str) -> Any:
        result = await self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        if "exceptionDetails" in result:
            detail = result["exceptionDetails"]
            raise RuntimeError(detail.get("text") or "the page threw while being read")
        return result.get("result", {}).get("value")


class DrivingTools:
    """One driven browser per project, and the verbs that use it."""

    def __init__(self, *, browser: Optional[str] = None) -> None:
        #: root -> the browser driving that project's app. One at a time, for
        #: the reason `AppTools` keeps one app: two is a state nobody can
        #: reason about from a transcript.
        self._sessions: Dict[str, BrowserSession] = {}
        self._lock = threading.Lock()
        self._browser = browser
        #: The label of the element the last click or type resolved to,
        #: for the phrase on the row. Set inside the protocol call and
        #: read immediately after it, on the same thread.
        self._last_name = ""
        import atexit

        atexit.register(self.close_all)

    # ------------------------------------------------------------ lifecycle

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            self._shut(session)

    def _shut(self, session: BrowserSession) -> None:
        try:
            session.process.terminate()
            session.process.wait(timeout=5)
        except Exception:
            try:
                session.process.kill()
            except Exception:
                pass
        # A temporary profile of this session's own making, holding whatever
        # the dev app wrote to storage. Nothing else is in it, because
        # nothing else was ever signed in.
        #
        # Retried, because Windows releases a process's file handles slightly
        # after the process itself is gone: a single rmtree immediately after
        # `wait()` leaves the profile on disk about half the time, and with
        # `ignore_errors` it leaves it *silently*. The point of the fresh
        # profile is that it does not outlive the session, so this is worth
        # a second or so of patience.
        for attempt in range(10):
            shutil.rmtree(session.profile, ignore_errors=attempt < 9)
            if not Path(session.profile).exists():
                return
            time.sleep(0.1)
        logger.debug("driving profile %s could not be removed", session.profile)

    def _free_port(self) -> int:
        import socket

        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            return int(probe.getsockname()[1])

    def _launch(self, url: str) -> BrowserSession:
        browser = self._browser or find_browser()
        if not browser:
            raise RuntimeError(NO_BROWSER)
        port = self._free_port()
        profile = tempfile.mkdtemp(prefix="zaram-driving-")
        process = subprocess.Popen(
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                # No extensions, no restored tabs, no sign-ins. See the module
                # docstring: Zaram's browser is not the person's browser.
                "--disable-extensions",
                "--window-size=1280,900",
                "--remote-debugging-port=%d" % port,
                "--user-data-dir=%s" % profile,
                url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return BrowserSession(process=process, port=port, profile=profile, url=url)

    def _page_socket(self, session: BrowserSession) -> str:
        """The debugging URL of the page target, once the browser offers one."""
        import requests

        deadline = time.monotonic() + PORT_WAIT_SECONDS
        while time.monotonic() < deadline:
            if not session.alive():
                raise RuntimeError("the browser exited before it opened a debugging port")
            try:
                listed = requests.get(
                    "http://127.0.0.1:%d/json/list" % session.port, timeout=1
                ).json()
                for target in listed:
                    if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                        return str(target["webSocketDebuggerUrl"])
            except Exception:
                pass
            time.sleep(0.2)
        raise TimeoutError(
            "the browser did not open a debugging port in %.0fs" % PORT_WAIT_SECONDS
        )

    # ------------------------------------------------------------- protocol

    def _run(self, session: BrowserSession, work) -> Any:
        """Open a conversation, do one thing, close it. See `_Protocol`."""
        ws_url = self._page_socket(session)

        async def go() -> Any:
            import aiohttp

            async with aiohttp.ClientSession() as http:
                async with http.ws_connect(ws_url, max_msg_size=32 * 1024 * 1024) as ws:
                    return await work(_Protocol(ws))

        return asyncio.run(go())

    async def _settle(self, cdp: "_Protocol") -> None:
        """Wait for the document, so a read does not race the load.

        An empty element list from a page still loading is indistinguishable
        from a page with nothing on it, and the model cannot tell which it
        got. Found in the spike for this slice, where exactly that happened.
        """
        for _ in range(60):
            if await cdp.evaluate("document.readyState") == "complete":
                return
            await asyncio.sleep(0.1)

    # ---------------------------------------------------------------- tools

    def call(self, name: str, arguments: Dict[str, Any], root: Path) -> Dict[str, Any]:
        key = str(root)
        try:
            if name == OPEN_IN_BROWSER:
                return self._open(key, str(arguments.get("url") or ""))
            if name == CLOSE_BROWSER:
                return self._close(key)
            session = self._sessions.get(key)
            if session is None or not session.alive():
                return {"error": NOT_OPEN}
            if name == READ_APP_PAGE:
                return self._read(session)
            if name == CLICK_IN_APP:
                return self._click(session, str(arguments.get("ref") or ""))
            if name == TYPE_IN_APP:
                return self._type(
                    session, str(arguments.get("ref") or ""), str(arguments.get("text") or "")
                )
            if name == READ_APP_CONSOLE:
                return self._console(session)
            return {"error": "no tool called %r" % name}
        except (RuntimeError, TimeoutError, OSError) as exc:
            # Reported rather than raised, like every refusal in this pack: a
            # failed call the model can read is one it can recover from.
            return {"error": str(exc)}

    def _open(self, key: str, url: str) -> Dict[str, Any]:
        target = url.strip()
        if not target:
            return {"error": "name the localhost URL to open."}
        if not _LOOPBACK.match(target):
            return {"error": NOT_LOOPBACK.format(url=target)}

        existing = self._sessions.get(key)
        if existing is not None and existing.alive():
            # Reuse the browser and navigate it, so a session keeps whatever
            # the app put in storage. A second browser per project is the
            # state nobody can reason about.
            def navigate(cdp):
                async def work():
                    await cdp.call("Page.enable")
                    await cdp.call(
                        "Page.addScriptToEvaluateOnNewDocument", {"source": CONSOLE_RECORDER}
                    )
                    await cdp.call("Page.navigate", {"url": target})
                    await self._settle(cdp)
                    await cdp.evaluate(CONSOLE_RECORDER)
                    return await cdp.evaluate(READ_PAGE_JS)

                return work()

            raw = self._run(existing, navigate)
            existing.url = target
            return self._summarise(raw, opened=target)

        session = self._launch(target)
        with self._lock:
            self._sessions[key] = session

        def first(cdp):
            async def work():
                await cdp.call("Page.enable")
                # Registered for every later navigation, and run once now for
                # the document that has already loaded.
                await cdp.call(
                    "Page.addScriptToEvaluateOnNewDocument", {"source": CONSOLE_RECORDER}
                )
                await self._settle(cdp)
                await cdp.evaluate(CONSOLE_RECORDER)
                return await cdp.evaluate(READ_PAGE_JS)

            return work()

        raw = self._run(session, first)
        return self._summarise(raw, opened=target)

    def _close(self, key: str) -> Dict[str, Any]:
        with self._lock:
            session = self._sessions.pop(key, None)
        if session is None:
            return {"closed": False, "note": "no page was open"}
        self._shut(session)
        return {"closed": True}

    def _read(self, session: BrowserSession) -> Dict[str, Any]:
        def work(cdp):
            async def go():
                await self._settle(cdp)
                return await cdp.evaluate(READ_PAGE_JS)

            return go()

        return self._summarise(self._run(session, work))

    def _summarise(self, raw: Any, opened: str = "") -> Dict[str, Any]:
        try:
            page = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (TypeError, ValueError):
            return {"error": "the page could not be read"}
        result: Dict[str, Any] = {
            "url": page.get("url", ""),
            "title": page.get("title", ""),
            "elements": page.get("elements", []),
            "text": page.get("text", ""),
        }
        if opened:
            result["opened"] = opened
            result["acted"] = f"opened {opened}"
        if len(result["elements"]) >= MAX_ELEMENTS:
            result["note"] = (
                "only the first %d interactive elements are listed; narrow what you "
                "are looking at before acting" % MAX_ELEMENTS
            )
        return result

    def _click(self, session: BrowserSession, ref: str) -> Dict[str, Any]:
        if not ref:
            return {"error": "name the ref to click, from a reading of the page."}

        def work(cdp):
            async def go():
                where = await cdp.evaluate(_centre_js(ref))
                if where in (None, "null"):
                    return {"error": STALE_REF.format(ref=ref)}
                spot = json.loads(where)
                self._last_name = str(spot.get("name") or "")
                if spot.get("disabled"):
                    # Said rather than clicked into the void. A disabled
                    # control swallows the event, and the model would read the
                    # unchanged page as "the click did nothing" — which is the
                    # same symptom as a real defect and sends it hunting.
                    return {"error": "%s is disabled, so clicking it does nothing." % ref}
                for kind in ("mousePressed", "mouseReleased"):
                    await cdp.call(
                        "Input.dispatchMouseEvent",
                        {
                            "type": kind,
                            "x": spot["x"],
                            "y": spot["y"],
                            "button": "left",
                            "clickCount": 1,
                        },
                    )
                # A click usually changes the page, so the page afterwards is
                # the answer. Returning "ok" would cost a second call every
                # single time.
                await asyncio.sleep(0.25)
                await self._settle(cdp)
                return await cdp.evaluate(READ_PAGE_JS)

            return go()

        out = self._run(session, work)
        if isinstance(out, dict) and "error" in out:
            return out
        page = self._summarise(out)
        page["clicked"] = ref
        # What a person watching needs. "clicked e5" is Zaram's own
        # bookkeeping and tells a reader nothing about what was pressed.
        named = _said(self._last_name)
        page["acted"] = f"clicked {named}" if named else f"clicked {ref}"
        return page

    def _type(self, session: BrowserSession, ref: str, text: str) -> Dict[str, Any]:
        if not ref:
            return {"error": "name the ref to type into, from a reading of the page."}

        def work(cdp):
            async def go():
                where = await cdp.evaluate(_centre_js(ref))
                if where in (None, "null"):
                    return {"error": STALE_REF.format(ref=ref)}
                spot = json.loads(where)
                self._last_name = str(spot.get("name") or "")
                for kind in ("mousePressed", "mouseReleased"):
                    await cdp.call(
                        "Input.dispatchMouseEvent",
                        {
                            "type": kind,
                            "x": spot["x"],
                            "y": spot["y"],
                            "button": "left",
                            "clickCount": 1,
                        },
                    )
                # Select-all, then insert, so typing into a filled field
                # replaces rather than appends — which is what a person means
                # by "type the folder in", and the opposite of what appending
                # would produce on a retry.
                await cdp.evaluate(_select_js(ref))
                await cdp.call("Input.insertText", {"text": text})
                await asyncio.sleep(0.15)
                return await cdp.evaluate(READ_PAGE_JS)

            return go()

        out = self._run(session, work)
        if isinstance(out, dict) and "error" in out:
            return out
        page = self._summarise(out)
        page["typed_into"] = ref
        named = _said(self._last_name)
        shown = _said(text)
        page["acted"] = (
            f"typed {shown!r} into {named}" if named else f"typed {shown!r} into {ref}"
        )
        return page

    def _console(self, session: BrowserSession) -> Dict[str, Any]:
        def work(cdp):
            async def go():
                return await cdp.evaluate(
                    "JSON.stringify((window.__zaramConsole || []).slice(-%d))" % MAX_CONSOLE
                )

            return go()

        raw = self._run(session, work)
        try:
            lines = json.loads(raw) if isinstance(raw, str) else []
        except (TypeError, ValueError):
            lines = []
        errors = [line for line in lines if line.get("level") == "error"]
        return {
            "lines": lines,
            "errors": len(errors),
            # Said explicitly, because an empty console and a recorder that
            # never ran look identical from here.
            "note": "" if lines else "nothing has been logged since the page loaded",
        }

    # ---------------------------------------------------------- descriptors

    def descriptors(self, server_id: str) -> List[ToolDescriptor]:
        return [
            ToolDescriptor(
                server_id=server_id,
                name=OPEN_IN_BROWSER,
                description=(
                    "Open the running app in a browser Zaram drives, and return what is on "
                    "the page. Only localhost. Use this before clicking or typing. The "
                    "browser carries none of the person's sign-ins: it starts with an empty "
                    "profile every time."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string", "description": "A localhost URL."}},
                    "required": ["url"],
                },
            ),
            ToolDescriptor(
                server_id=server_id,
                name=READ_APP_PAGE,
                description=(
                    "Read the open page as a list of interactive elements with refs, plus its "
                    "visible text. Each element says whether it is disabled, what it contains "
                    "and what it is called. Read before acting: a ref is valid only until the "
                    "page changes."
                ),
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDescriptor(
                server_id=server_id,
                name=CLICK_IN_APP,
                description=(
                    "Click one element by its ref and return the page as it is afterwards. "
                    "Refuses a disabled element rather than clicking into the void."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "ref": {"type": "string", "description": "A ref from reading the page."}
                    },
                    "required": ["ref"],
                },
            ),
            ToolDescriptor(
                server_id=server_id,
                name=TYPE_IN_APP,
                description=(
                    "Type into one field by its ref, replacing what is in it, and return the "
                    "page afterwards."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "ref": {"type": "string", "description": "A ref from reading the page."},
                        "text": {"type": "string", "description": "What to type."},
                    },
                    "required": ["ref", "text"],
                },
            ),
            ToolDescriptor(
                server_id=server_id,
                name=READ_APP_CONSOLE,
                description=(
                    "What the page logged since it loaded — errors, warnings, unhandled "
                    "rejections. The browser's console, not the server's log."
                ),
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDescriptor(
                server_id=server_id,
                name=CLOSE_BROWSER,
                description="Close the browser Zaram opened for this project.",
                input_schema={"type": "object", "properties": {}},
            ),
        ]
