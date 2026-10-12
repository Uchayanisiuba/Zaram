"""Tests for MCP Memory Server."""

import pytest
import json
from backend.runtimes.mcp.memory_server import MemoryMCPServer


class TestMemoryMCPServer:
    """Test MemoryMCPServer class."""
    
    def test_initialization(self):
        server = MemoryMCPServer(credential="test-cred", base_url="http://localhost:8420")
        assert server.spine is not None
    
    def test_handle_initialize(self):
        server = MemoryMCPServer(credential="test-cred")
        result = server.handle_initialize({})
        
        assert result["protocolVersion"] == "2025-06-18"
        assert result["capabilities"] == {"tools": {}}
        assert result["serverInfo"]["name"] == "zaram-memory"
    
    def test_handle_tools_list(self):
        server = MemoryMCPServer(credential="test-cred")
        result = server.handle_tools_list()
        
        assert "tools" in result
        assert len(result["tools"]) == 5
        
        tool_names = {t["name"] for t in result["tools"]}
        expected = {"memory_add", "memory_search", "memory_update", "memory_delete", "memory_list"}
        assert tool_names == expected
    
    @pytest.mark.asyncio
    async def test_handle_tool_call_memory_add(self):
        server = MemoryMCPServer(credential="test-cred")
        
        # Mock spine._call
        server.spine._call = lambda method, path, data: {"id": "test-fact-id", "content": data["text"]}
        
        result = await server.handle_tool_call("memory_add", {"content": "Test fact"})
        
        assert "content" in result
        content = json.loads(result["content"][0]["text"])
        assert content["id"] == "test-fact-id"
    
    @pytest.mark.asyncio
    async def test_handle_tool_call_memory_search(self):
        server = MemoryMCPServer(credential="test-cred")
        
        # Mock spine.recall
        server.spine.recall = lambda query, project_id, limit: {"facts": [{"id": "1", "content": "Test"}]}
        
        result = await server.handle_tool_call("memory_search", {"query": "test"})
        
        assert "content" in result
        content = json.loads(result["content"][0]["text"])
        assert "facts" in content
    
    @pytest.mark.asyncio
    async def test_handle_tool_call_memory_update(self):
        server = MemoryMCPServer(credential="test-cred")
        
        server.spine._call = lambda method, path, data: {"success": True}
        
        result = await server.handle_tool_call("memory_update", {"fact_id": "123", "content": "Updated"})
        
        assert "content" in result
        content = json.loads(result["content"][0]["text"])
        assert content["success"] is True
    
    @pytest.mark.asyncio
    async def test_handle_tool_call_memory_delete(self):
        server = MemoryMCPServer(credential="test-cred")
        
        server.spine._call = lambda method, path, data: {"success": True}
        
        result = await server.handle_tool_call("memory_delete", {"fact_id": "123", "reason": "Obsolete"})
        
        assert "content" in result
        content = json.loads(result["content"][0]["text"])
        assert content["success"] is True
    
    @pytest.mark.asyncio
    async def test_handle_tool_call_memory_list(self):
        server = MemoryMCPServer(credential="test-cred")
        
        server.spine.recall = lambda query, project_id, limit: {"facts": [{"id": "1", "content": "Test"}]}
        
        result = await server.handle_tool_call("memory_list", {"limit": 10})
        
        assert "content" in result
        content = json.loads(result["content"][0]["text"])
        assert "facts" in content
    
    @pytest.mark.asyncio
    async def test_handle_tool_call_unknown(self):
        server = MemoryMCPServer(credential="test-cred")
        
        result = await server.handle_tool_call("unknown_tool", {})
        
        assert result["isError"] is True
        assert "Unknown tool" in result["content"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_handle_tool_call_error_handling(self):
        server = MemoryMCPServer(credential="test-cred")
        
        # Make spine._call raise an exception
        server.spine._call = lambda *args, **kwargs: (_ for _ in ()).throw(Exception("Test error"))
        
        result = await server.handle_tool_call("memory_add", {"content": "Test"})
        
        assert result["isError"] is True
        assert "Error: Test error" in result["content"][0]["text"]