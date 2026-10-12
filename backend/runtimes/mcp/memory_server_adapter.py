"""MCP Memory Server Adapter - wraps memory operations as an in-process MCP server."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from runtimes.mcp.client import McpServer, ToolDescriptor
from runtimes.mcp.config import ServerConfig, WriteMode
from zaram_mcp import Spine, DEFAULT_API, CREDENTIAL_ENV, require_loopback


class MemoryMCPServer:
    """In-process MCP server exposing memory tools."""
    
    def __init__(self, credential: str, base_url: str = DEFAULT_API):
        self.spine = Spine(credential, base_url)
    
    @property
    def server_id(self) -> str:
        return "zaram-memory"
    
    @property
    def grant_scope(self) -> str:
        return "memory operations"
    
    def list_tools(self) -> List[ToolDescriptor]:
        """List available memory tools."""
        return [
            ToolDescriptor(
                name="memory_add",
                description="Store a fact in the user's Spine for cross-assistant recall.",
                inputSchema={
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
            ),
            ToolDescriptor(
                name="memory_search",
                description="Search the Spine for facts relevant to a query.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "What to search for"},
                        "project_id": {"type": "string", "description": "Optional project scope"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 6},
                        "memory_types": {"type": "array", "items": {"type": "string", "enum": ["conversation", "episodic", "semantic", "working"]}},
                    },
                    "required": ["query"],
                },
            ),
            ToolDescriptor(
                name="memory_update",
                description="Update an existing fact's content or metadata.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "fact_id": {"type": "string", "description": "ID of the fact to update"},
                        "content": {"type": "string", "description": "New content"},
                        "importance": {"type": "number", "minimum": 0, "maximum": 1},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["fact_id"],
                },
            ),
            ToolDescriptor(
                name="memory_delete",
                description="Delete a fact from the Spine (correction - keeps history).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "fact_id": {"type": "string", "description": "ID of the fact to delete"},
                        "reason": {"type": "string", "description": "Why this is being deleted"},
                    },
                    "required": ["fact_id", "reason"],
                },
            ),
            ToolDescriptor(
                name="memory_list",
                description="List facts with optional filtering.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "memory_type": {"type": "string", "enum": ["conversation", "episodic", "semantic", "working"]},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                        "offset": {"type": "integer", "minimum": 0, "default": 0},
                    },
                },
            ),
        ]
    
    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a memory tool."""
        try:
            if tool_name == "memory_add":
                return await self._memory_add(arguments)
            elif tool_name == "memory_search":
                return await self._memory_search(arguments)
            elif tool_name == "memory_update":
                return await self._memory_update(arguments)
            elif tool_name == "memory_delete":
                return await self._memory_delete(arguments)
            elif tool_name == "memory_list":
                return await self._memory_list(arguments)
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
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
        return {"success": True, "result": result}
    
    async def _memory_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        result = self.spine.recall(
            args["query"],
            args.get("project_id"),
            args.get("limit", 6),
        )
        return {"success": True, "result": result}
    
    async def _memory_update(self, args: Dict[str, Any]) -> Dict[str, Any]:
        fact_id = args["fact_id"]
        updates = {k: v for k, v in args.items() if k != "fact_id" and v is not None}
        
        result = self.spine._call("POST", f"/memory/{fact_id}/correct", {
            "content": updates.get("content", ""),
            "importance": updates.get("importance"),
            "tags": updates.get("tags"),
        })
        return {"success": True, "result": result}
    
    async def _memory_delete(self, args: Dict[str, Any]) -> Dict[str, Any]:
        result = self.spine._call("POST", f"/memory/{args['fact_id']}/correct", {
            "content": f"[DELETED] {args['reason']}",
        })
        return {"success": True, "result": result}
    
    async def _memory_list(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # Use recall with empty query to list
        result = self.spine.recall("", args.get("project_id"), args.get("limit", 20))
        return {"success": True, "result": result}


def create_memory_mcp_server(credential: str, base_url: str = DEFAULT_API) -> MemoryMCPServer:
    """Factory function to create a MemoryMCPServer."""
    return MemoryMCPServer(credential, base_url)