"""Zaram's own settings, as tools the model can use when the person asks.

"Switch to the avatar", "use the Michael voice", "turn web search off", "open
Settings": the person says it in the conversation and the model does it, through
the same gate as every other tool -- a change asks the first time and can be
allowed for good from the card; a few always ask.

Rewritten 10 October 2026. The first version was never reachable: its handlers
were `async`, the runtime ran them in a thread and got a coroutine back, and every
call returned ``success: True`` having changed nothing -- while `set_renderer`
reported success by design without changing anything either, and `list_voices`
imported a function that does not exist. A model told "done" by a tool that did
nothing tells the person "done", which is the exact failure the product exists to
refuse. So every handler here reads the value back after setting it and reports
what is now true, and anything this server cannot do itself says where it is done.

**What it will not touch, by design.** What may leave the computer -- the kill
switch, per-site rules, keys -- is the person's to change in Settings -> Privacy,
never a model's (rule 5). Turning web search *on* is the one egress setting here,
because "turn on web search" is an ordinary thing to ask; it always asks first,
whatever was allowed before. Granting a tool permission also always asks: a model
must never be able to widen its own permissions with one card the person allowed
once.

Things the window owns -- which indicator is showing, which place is open -- are
returned as an ``apply`` instruction the engine forwards (from this server only)
and the window carries out.
"""

from __future__ import annotations

from typing import Any, Dict, List

from core.user_settings import RoutingPreference, get_user_settings
from runtimes.mcp.client import ToolDescriptor as Tool
from runtimes.mcp.config import ServerStore

SELF_SERVER_ID = "zaram-self"

#: The six places, by the id the window navigates with.
PLACES = ("work", "project", "memory", "knowledge", "activity", "settings")

#: Tools whose every call asks, whatever the person allowed before. Read by
#: `policy.always_asks` so the card does not offer "always" for them.
ALWAYS_ASK = frozenset({"grant_tool", "set_web_search"})


def _schema(properties: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required}


def _switch(description: str) -> Dict[str, Any]:
    return _schema({"on": {"type": "boolean", "description": description}}, ["on"])


class ZaramSelfServer:
    """In-process MCP server for Zaram's own settings."""

    def __init__(self, store_factory=ServerStore, settings=get_user_settings):
        self._store = store_factory
        self._settings = settings
        self._tools = self._build_tools()

    def _build_tools(self) -> List[Tool]:
        def tool(name: str, description: str, schema: Dict[str, Any]) -> Tool:
            return Tool(server_id=SELF_SERVER_ID, name=name, description=description, input_schema=schema)

        return [
            tool("get_settings", "Read Zaram's current settings: voice, routing, name, manner, thinking, web search, computer use.", _schema({}, [])),
            tool("list_voices", "List the voices on this machine, and the ones that need downloading first.", _schema({}, [])),
            tool("list_servers", "List the attached tool servers, whether each is on, and what is allowed.", _schema({}, [])),
            tool(
                "open_place",
                "Open one of Zaram's six places in the window: work, project, memory, knowledge, activity or settings.",
                _schema({"place": {"type": "string", "enum": list(PLACES)}}, ["place"]),
            ),
            tool(
                "set_indicator",
                "Show the orb or the avatar. The avatar also speaks replies aloud.",
                _schema({"renderer": {"type": "string", "enum": ["orb", "avatar"]}}, ["renderer"]),
            ),
            tool(
                "set_voice",
                "Choose the voice that speaks replies, by id from list_voices (e.g. am_michael). It must already be on this machine.",
                _schema({"voice_id": {"type": "string"}}, ["voice_id"]),
            ),
            tool(
                "set_routing",
                "How Zaram chooses between local and cloud models when nobody named one: prefer_local, auto, or prefer_cloud.",
                _schema({"mode": {"type": "string", "enum": [p.value for p in RoutingPreference]}}, ["mode"]),
            ),
            tool(
                "set_assistant_name",
                "What the person calls the assistant. Underneath it is still Zaram. Empty restores the default.",
                _schema({"name": {"type": "string", "maxLength": 48}}, ["name"]),
            ),
            tool(
                "set_manner",
                "How the assistant writes: tone, length, formality. Empty restores the default.",
                _schema({"manner": {"type": "string", "maxLength": 600}}, ["manner"]),
            ),
            tool("set_thinking", "Whether a model that can think step by step is asked to, before answering.", _switch("true to think first")),
            tool("set_web_search", "Turn searching the web for current information on or off. Always asks the person first.", _switch("true to allow web search")),
            tool("set_computer_use", "Turn computer use (Zaram working the desktop) on or off. Nothing is uninstalled.", _switch("true to turn it on")),
            tool(
                "grant_tool",
                "Allow one tool on one server for good, so it stops asking. Always asks the person first.",
                _schema({"server_id": {"type": "string"}, "tool_name": {"type": "string"}}, ["server_id", "tool_name"]),
            ),
            tool(
                "revoke_tool",
                "Withdraw a tool's standing permission, so it asks again.",
                _schema({"server_id": {"type": "string"}, "tool_name": {"type": "string"}}, ["server_id", "tool_name"]),
            ),
        ]

    def list_tools(self) -> List[Tool]:
        return self._tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        handler = getattr(self, f"_handle_{name}", None)
        if handler is None:
            raise ValueError(f"Unknown tool: {name}")
        return await handler(arguments or {})

    # ------------------------------------------------------------------ reads

    async def _handle_get_settings(self, args: Dict[str, Any]) -> Dict[str, Any]:
        s = self._settings()
        return {
            "voice": s.voice or "(the default voice)",
            "routing": s.routing_preference.value,
            "assistant_name": s.assistant_name or "(none: Zaram)",
            "manner": s.manner or "(the default)",
            "thinking": s.thinking,
            "web_search": s.web_search,
            "computer_use": self._computer_use_state(),
            "indicator": "held by the window; set it with set_indicator",
        }

    async def _handle_list_voices(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from voice.voice_manifest import catalogue

        rows = catalogue().get("voices") or []
        chosen = (self._settings().voice or "").strip()
        on_machine = [f"{r['id']} ({r['name']}, {r['language']})" + (" - speaking now" if r["id"] == chosen else "") for r in rows if r.get("installed")]
        to_download = [r["id"] for r in rows if not r.get("installed")]
        return {
            "on_this_machine": on_machine,
            "need_downloading": to_download,
            "note": "A voice that needs downloading is fetched by pressing Download in Settings -> Character -> Voice.",
        }

    async def _handle_list_servers(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "servers": [
                {
                    "id": sid,
                    "on": cfg.enabled,
                    "writes": cfg.writes.value,
                    "allowed_for_good": sorted(cfg.granted_tools),
                    "kept_for_the_model": sorted(cfg.pinned_tools),
                }
                for sid, cfg in self._store().load().items()
            ]
        }

    # ------------------------------------------------------------ the window

    async def _handle_open_place(self, args: Dict[str, Any]) -> Dict[str, Any]:
        place = str(args.get("place") or "").strip().lower()
        if place not in PLACES:
            return {"success": False, "error": f"there is no place called {place!r}; the six are {', '.join(PLACES)}"}
        return {"success": True, "opened": place, "apply": {"open": place}}

    async def _handle_set_indicator(self, args: Dict[str, Any]) -> Dict[str, Any]:
        renderer = str(args.get("renderer") or "").strip().lower()
        if renderer not in ("orb", "avatar"):
            return {"success": False, "error": "the indicator is either orb or avatar"}
        return {"success": True, "indicator": renderer, "apply": {"renderer": renderer}}

    # --------------------------------------------------------------- settings

    async def _handle_set_voice(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from voice.voice_manifest import catalogue

        voice_id = str(args.get("voice_id") or "").strip()
        row = next((r for r in catalogue().get("voices") or [] if r["id"] == voice_id), None)
        if row is None:
            return {"success": False, "error": f"there is no voice called {voice_id!r}; list_voices names them"}
        if not row.get("installed"):
            return {
                "success": False,
                "error": f"{voice_id} is not on this machine yet. The person downloads it by pressing Download "
                "beside it in Settings -> Character -> Voice; then it can be chosen.",
            }
        now = self._settings().set_character(voice=voice_id).get("voice")
        return {"success": now == voice_id, "voice": now}

    async def _handle_set_routing(self, args: Dict[str, Any]) -> Dict[str, Any]:
        mode = str(args.get("mode") or "").strip().lower()
        try:
            now = self._settings().set_routing_preference(mode)
        except ValueError:
            return {"success": False, "error": "routing is prefer_local, auto or prefer_cloud"}
        return {"success": True, "routing": now.value}

    async def _handle_set_assistant_name(self, args: Dict[str, Any]) -> Dict[str, Any]:
        now = self._settings().set_character(assistant_name=str(args.get("name") or ""))
        return {"success": True, "assistant_name": now.get("assistant_name") or "(none: Zaram)"}

    async def _handle_set_manner(self, args: Dict[str, Any]) -> Dict[str, Any]:
        now = self._settings().set_character(manner=str(args.get("manner") or ""))
        return {"success": True, "manner": now.get("manner") or "(the default)"}

    async def _handle_set_thinking(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": True, "thinking": self._settings().set_thinking(bool(args.get("on")))}

    async def _handle_set_web_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        now = self._settings().set_web_search(bool(args.get("on")))
        return {"success": now == bool(args.get("on")), "web_search": now}

    async def _handle_set_computer_use(self, args: Dict[str, Any]) -> Dict[str, Any]:
        on = bool(args.get("on"))
        store = self._store()
        desktops = [sid for sid in store.load() if "cua" in sid.lower()]
        if not desktops:
            return {
                "success": False,
                "error": "computer use is not installed. The person installs it with Install cua-driver in Settings -> Computer Use.",
            }
        for sid in desktops:
            store.set_enabled(sid, on)
        return {"success": True, "computer_use": self._computer_use_state()}

    async def _handle_grant_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        server_id, tool_name = str(args.get("server_id") or ""), str(args.get("tool_name") or "")
        store = self._store()
        if server_id not in store.load():
            return {"success": False, "error": f"there is no attached server called {server_id!r}"}
        store.grant(server_id, tool_name)
        return {"success": tool_name in store.load()[server_id].granted_tools, "server": server_id, "allowed_for_good": tool_name}

    async def _handle_revoke_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        server_id, tool_name = str(args.get("server_id") or ""), str(args.get("tool_name") or "")
        store = self._store()
        servers = store.load()
        if server_id not in servers:
            return {"success": False, "error": f"there is no attached server called {server_id!r}"}
        servers[server_id].granted_tools.discard(tool_name)
        store.save(servers)
        return {"success": True, "server": server_id, "asks_again": tool_name}

    # ---------------------------------------------------------------- helpers

    def _computer_use_state(self) -> str:
        desktops = [cfg for sid, cfg in self._store().load().items() if "cua" in sid.lower()]
        if not desktops:
            return "not installed"
        return "on" if any(cfg.enabled for cfg in desktops) else "off"


def create_self_server() -> ZaramSelfServer:
    """Factory for bootstrapper."""
    return ZaramSelfServer()
