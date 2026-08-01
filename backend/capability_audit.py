from __future__ import annotations

import time
from typing import Any


CAPABILITY_AUDIT = {
    "knowledge.search": {
        "planner": True,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "KnowledgeRuntime orchestrates InternetRuntime + MemoryRuntime",
    },
    "knowledge.search.internet": {
        "planner": False,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "InternetRuntime with DuckDuckGo, Wikipedia, GitHub, RSS connectors",
    },
    "knowledge.search.memory": {
        "planner": False,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "MemoryRuntime with hybrid search (vector + keyword + temporal)",
    },
    "memory.store": {
        "planner": True,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "MemoryRuntime.store() with InMemory/SQLite backends",
    },
    "memory.retrieve": {
        "planner": True,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "MemoryRuntime.retrieve() with hybrid strategy + ranking",
    },
    "memory.conversation.history": {
        "planner": False,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "ConversationHistory with session tracking",
    },
    "memory.episodic": {
        "planner": False,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "EpisodicMemory for event recording and recall",
    },
    "memory.semantic": {
        "planner": False,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "SemanticMemory for fact extraction and knowledge queries",
    },
    "memory.consolidate": {
        "planner": False,
        "runtime": True,
        "connector": False,
        "status": "placeholder",
        "details": "MemoryRuntime.consolidate() - basic stats only",
    },
    "memory.forget": {
        "planner": False,
        "runtime": True,
        "connector": False,
        "status": "working",
        "details": "MemoryRuntime.forget() - deletes from store and index",
    },
    "filesystem.search": {
        "planner": True,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "FilesystemRuntime.search() with hybrid fulltext + metadata",
    },
    "filesystem.open": {
        "planner": True,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "FilesystemRuntime.open_file() returns full record",
    },
    "filesystem.metadata": {
        "planner": True,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "FilesystemRuntime.get_metadata() for file info",
    },
    "filesystem.index": {
        "planner": True,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "FilesystemRuntime.index_file() + reindex()",
    },
    "internet.search": {
        "planner": False,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "InternetRuntime.search() with retries, caching, ranking",
    },
    "internet.connector.register": {
        "planner": False,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "InternetRuntime.register_connector() for dynamic connectors",
    },
    "internet.connector.health": {
        "planner": False,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "Individual connector health checks with latency/error tracking",
    },
    "tool.git": {
        "planner": True,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "GitConnector: status, diff, log, branch, add, commit, push, pull, clone",
    },
    "tool.vscode": {
        "planner": True,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "VSCodeConnector: open_file, open_folder, install_extension, list_extensions",
    },
    "tool.terminal": {
        "planner": True,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "TerminalConnector: run, cd, pwd with timeout support",
    },
    "tool.browser": {
        "planner": True,
        "runtime": True,
        "connector": True,
        "status": "placeholder",
        "details": "BrowserConnector: navigate, screenshot, extract, click, type - requires playwright",
    },
    "tool.filesystem": {
        "planner": True,
        "runtime": True,
        "connector": True,
        "status": "working",
        "details": "FilesystemToolConnector: search, read, metadata via FilesystemRuntime",
    },
    "tool.email": {
        "planner": True,
        "runtime": True,
        "connector": True,
        "status": "placeholder",
        "details": "EmailConnector: send, search, list - requires SMTP/IMAP config",
    },
    "tool.calendar": {
        "planner": True,
        "runtime": True,
        "connector": True,
        "status": "placeholder",
        "details": "CalendarConnector: create_event, list_events, search - requires CalDAV/Google API",
    },
    "reasoning.generate": {
        "planner": True,
        "runtime": True,
        "connector": False,
        "status": "working",
        "details": "ModelsRuntime handles generation via Ollama",
    },
    "vision.analyze": {
        "planner": True,
        "runtime": True,
        "connector": False,
        "status": "working",
        "details": "ModelsRuntime handles image analysis",
    },
    "speech.synthesize": {
        "planner": True,
        "runtime": False,
        "connector": False,
        "status": "missing",
        "details": "Speech Runtime not yet implemented",
    },
    "speech.recognize": {
        "planner": True,
        "runtime": False,
        "connector": False,
        "status": "missing",
        "details": "Speech Runtime not yet implemented",
    },
    "world.simulate": {
        "planner": True,
        "runtime": False,
        "connector": False,
        "status": "missing",
        "details": "World Runtime not yet implemented",
    },
}

# Summary counts
WORKING = sum(1 for v in CAPABILITY_AUDIT.values() if v["status"] == "working")
PLACEHOLDER = sum(1 for v in CAPABILITY_AUDIT.values() if v["status"] == "placeholder")
MISSING = sum(1 for v in CAPABILITY_AUDIT.values() if v["status"] == "missing")
TOTAL = len(CAPABILITY_AUDIT)

AUDIT_SUMMARY = {
    "total_capabilities": TOTAL,
    "working": WORKING,
    "placeholder": PLACEHOLDER,
    "missing": MISSING,
    "completion_pct": round((WORKING / TOTAL) * 100, 1),
    "runtime_coverage": {
        "knowledge": True,
        "memory": True,
        "filesystem": True,
        "internet": True,
        "tool": True,
        "models": True,
        "speech": False,
        "world": False,
    },
    "generated_at": time.time(),
}


def generate_capability_report() -> str:
    lines = [
        "# Capability Audit Report",
        f"Generated: {time.ctime()}",
        f"",
        f"## Summary",
        f"- Total Capabilities: {TOTAL}",
        f"- Working: {WORKING}",
        f"- Placeholder: {PLACEHOLDER}",
        f"- Missing: {MISSING}",
        f"- Completion: {AUDIT_SUMMARY['completion_pct']}%",
        f"",
        f"## Runtime Coverage",
        *[f"- {k}: {'OK' if v else 'MISSING'}" for k, v in AUDIT_SUMMARY["runtime_coverage"].items()],
        f"",
        f"## Detailed Capabilities",
    ]

    for cap_id, info in sorted(CAPABILITY_AUDIT.items()):
        status_icon = "OK" if info["status"] == "working" else "WARN" if info["status"] == "placeholder" else "MISSING"
        lines.append(f"### {cap_id} [{status_icon}]")
        lines.append(f"- Planner: {'OK' if info['planner'] else 'MISSING'}")
        lines.append(f"- Runtime: {'OK' if info['runtime'] else 'MISSING'}")
        lines.append(f"- Connector: {'OK' if info['connector'] else 'MISSING'}")
        lines.append(f"- Status: {info['status']}")
        lines.append(f"- Details: {info['details']}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    print(generate_capability_report())