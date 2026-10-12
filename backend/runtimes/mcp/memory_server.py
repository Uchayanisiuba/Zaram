"""MCP Memory Server - exposes Spine as MCP tools for other assistants."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from zaram_mcp import Spine, DEFAULT_API, CREDENTIAL_ENV, require_loopback


# Tool definitions for MCP
MEMORY_TOOLS = [
    {
        "name": "memory_add",
        "description": "Store a fact in the user's Spine for cross-assistant recall.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The fact to store"},
                "project_id": {"type": "string", "description": "Optional project scope"},
                "memory_type": {"type": "string", "enum": ["conversation", "episodic", "semantic", "working"], "default": "semantic"},
                "importance": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["content"],
        },
    },
    {
        "name": "memory_search",
        "description": "Search the Spine for facts relevant to a query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"},
                "project_id": {"type": "string", "description": "Optional project scope"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 6},
                "memory_types": {"type": "array", "items": {"type": "string", "enum": ["conversation", "episodic", "semantic", "working"]}},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_update",
        "description": "Update an existing fact's content or metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fact_id": {"type": "string", "description": "ID of the fact to update"},
                "content": {"type": "string", "description": "New content"},
                "importance": {"type": "number", "minimum": 0, "maximum": 1},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["fact_id"],
        },
    },
    {
        "name": "memory_delete",
        "description": "Delete a fact from the Spine (correction - keeps history).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fact_id": {"type": "string", "description": "ID of the fact to delete"},
                "reason": {"type": "string", "description": "Why this is being deleted"},
            },
            "required": ["fact_id", "reason"],
        },
    },
    {
        "name": "memory_list",
        "description": "List facts with optional filtering.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "memory_type": {"type": "string", "enum": ["conversation", "episodic", "semantic", "working"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
            },
        },
    },
]


class MemoryMCPServer:
    """MCP server exposing memory tools."""
    
    def __init__(self, credential: str, base_url: str = DEFAULT_API):
        self.spine = Spine(credential, base_url)
    
    def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "zaram-memory", "version": "0.1"},
        }
    
    def handle_tools_list(self) -> Dict[str, Any]:
        return {"tools": MEMORY_TOOLS}
    
    async def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if name == "memory_add":
                return await self._memory_add(arguments)
            elif name == "memory_search":
                return await self._memory_search(arguments)
            elif name == "memory_update":
                return await self._memory_update(arguments)
            elif name == "memory_delete":
                return await self._memory_delete(arguments)
            elif name == "memory_list":
                return await self._memory_list(arguments)
            else:
                return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "isError": True}
    
    async def _memory_add(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from runtimes.memory.contracts import MemoryType
        
        result = self.spine._call("POST", "/memory", {
            "text": args["content"],
            "project_id": args.get("project_id"),
            "memory_type": args.get("memory_type", "semantic"),
            "importance": args.get("importance", 0.5),
            "tags": args.get("tags", []),
            "origin": "conversation",
        })
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    
    async def _memory_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        result = self.spine.recall(
            args["query"],
            args.get("project_id"),
            args.get("limit", 6),
        )
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    
    async def _memory_update(self, args: Dict[str, Any]) -> Dict[str, Any]:
        fact_id = args["fact_id"]
        updates = {k: v for k, v in args.items() if k != "fact_id" and v is not None}
        
        result = self.spine._call("POST", f"/memory/{fact_id}/correct", {
            "content": updates.get("content", ""),
            "importance": updates.get("importance"),
            "tags": updates.get("tags"),
        })
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    
    async def _memory_delete(self, args: Dict[str, Any]) -> Dict[str, Any]:
        result = self.spine._call("POST", f"/memory/{args['fact_id']}/correct", {
            "content": f"[DELETED] {args['reason']}",
        })
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    
    async def _memory_list(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # Use recall with empty query to list
        result = self.spine.recall("", args.get("project_id"), args.get("limit", 20))
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def serve_stdio(credential: str, base_url: str = DEFAULT_API):
    """Run MCP server over stdio."""
    server = MemoryMCPServer(credential, base_url)
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            method = message.get("method")
            msg_id = message.get("id")
            params = message.get("params", {})
            
            def ok(result):
                return {"jsonrpc": "2.0", "id": msg_id, "result": result}
            
            def err(code, msg):
                return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": msg}}
            
            if method == "initialize":
                response = ok(server.handle_initialize(params))
            elif method == "tools/list":
                response = ok(server.handle_tools_list())
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                result = await server.handle_tool_call(tool_name, tool_args)
                response = ok(result)
            else:
                response = err(-32601, f"Method not found: {method}")
        
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


def main():
    """Entry point for MCP server."""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="Zaram Memory MCP Server")
    parser.add_argument("--credential", default=os.environ.get(CREDENTIAL_ENV), help="Paired client credential")
    parser.add_argument("--api", default=DEFAULT_API, help="Zaram API URL")
    args = parser.parse_args()
    
    if not args.credential:
        print(f"Error: No credential provided. Set {CREDENTIAL_ENV} or use --credential", file=sys.stderr)
        sys.exit(1)
    
    require_loopback(args.api)
    
    import asyncio
    asyncio.run(serve_stdio(args.credential, args.api))


if __name__ == "__main__":
    main()