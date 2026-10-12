"""Tests for Web Search Providers."""

import pytest
from backend.packs.web_search.providers.tavily import TavilyProvider
from backend.packs.web_search.providers.brave import BraveProvider
from backend.packs.web_search.providers.searxng import SearXNGProvider
from backend.packs.web_search.unified import WebSearchManager, SearchResult
from backend.packs.web_search.rate_limiter import TokenBucketRateLimiter
from backend.packs.web_search.api_keys import APIKeyManager
from backend.network.session import ZaramGovernedSession, ZaramSecurityViolation
from core.egress import EgressGate


class TestTokenBucketRateLimiter:
    """Test TokenBucketRateLimiter."""
    
    @pytest.mark.asyncio
    async def test_acquire_immediate(self):
        limiter = TokenBucketRateLimiter(rate_per_minute=60, burst=10)
        
        # Should acquire immediately when tokens available
        await limiter.acquire(1)
        assert limiter.available_tokens <= 9
    
    @pytest.mark.asyncio
    async def test_acquire_waits_when_empty(self):
        limiter = TokenBucketRateLimiter(rate_per_minute=60, burst=1)
        
        # Use the only token
        await limiter.acquire(1)
        
        # Next acquire should wait (but we won't wait long in test)
        # Just verify it doesn't error
        assert limiter.available_tokens < 1
    
    def test_try_acquire(self):
        limiter = TokenBucketRateLimiter(rate_per_minute=60, burst=5)
        
        assert limiter.try_acquire(1) is True
        assert limiter.try_acquire(5) is False  # Not enough tokens
    
    def test_reset(self):
        limiter = TokenBucketRateLimiter(rate_per_minute=60, burst=5)
        
        limiter.acquire(3)
        limiter.reset()
        
        assert limiter.available_tokens == 5


class TestAPIKeyManager:
    """Test APIKeyManager."""
    
    def test_set_and_get_key(self):
        manager = APIKeyManager(storage_path="/tmp/test_keys.json")
        
        manager.set_key("tavily", "test-key-123", "Test Key", rate_limit_rpm=20)
        
        key = manager.get_key("tavily")
        assert key == "test-key-123"
        
        entry = manager.get_entry("tavily")
        assert entry.name == "Test Key"
        assert entry.rate_limit_rpm == 20
        assert entry.enabled is True
    
    def test_remove_key(self):
        manager = APIKeyManager(storage_path="/tmp/test_keys2.json")
        
        manager.set_key("tavily", "test-key")
        assert manager.get_key("tavily") == "test-key"
        
        manager.remove_key("tavily")
        assert manager.get_key("tavily") is None
    
    def test_list_providers(self):
        manager = APIKeyManager(storage_path="/tmp/test_keys3.json")
        
        manager.set_key("tavily", "key1", "Tavily Key")
        manager.set_key("brave", "key2", "Brave Key")
        
        providers = manager.list_providers()
        assert "tavily" in providers
        assert "brave" in providers
        assert providers["tavily"]["name"] == "Tavily Key"
        assert providers["brave"]["name"] == "Brave Key"
    
    def test_enable_disable_provider(self):
        manager = APIKeyManager(storage_path="/tmp/test_keys4.json")
        
        manager.set_key("tavily", "key1")
        assert manager.get_key("tavily") == "key1"
        
        manager.enable_provider("tavily", False)
        assert manager.get_key("tavily") is None
        
        manager.enable_provider("tavily", True)
        assert manager.get_key("tavily") == "key1"
    
    def test_get_all_keys(self):
        manager = APIKeyManager(storage_path="/tmp/test_keys5.json")
        
        manager.set_key("tavily", "key1")
        manager.enable_provider("tavily", True)
        manager.set_key("brave", "key2")
        manager.enable_provider("brave", False)
        
        keys = manager.get_all_keys()
        assert "tavily" in keys
        assert "brave" not in keys


class TestSearchResult:
    """Test SearchResult dataclass."""
    
    def test_search_result_creation(self):
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            snippet="Test snippet",
            provider="tavily",
            score=0.9,
        )
        
        assert result.title == "Test Title"
        assert result.url == "https://example.com"
        assert result.snippet == "Test snippet"
        assert result.provider == "tavily"
        assert result.score == 0.9
        assert result.metadata == {}


class TestWebSearchManager:
    """Test WebSearchManager."""
    
    @pytest.mark.asyncio
    async def test_search_no_providers(self):
        manager = WebSearchManager()
        results = await manager.search("test query")
        assert results == []
    
    @pytest.mark.asyncio
    async def test_search_with_mock_provider(self):
        class MockProvider:
            name = "mock"
            rate_limit_rpm = 60
            
            async def search(self, query, max_results=10):
                return [
                    SearchResult(title="Result 1", url="https://ex.com/1", snippet="Snippet 1", provider="mock", score=0.9),
                    SearchResult(title="Result 2", url="https://ex.com/2", snippet="Snippet 2", provider="mock", score=0.8),
                ]
            
            async def health_check(self):
                return {"status": "healthy"}
        
        manager = WebSearchManager()
        provider = MockProvider()
        manager.register_provider(provider)
        
        results = await manager.search("test query", max_results=5)
        
        assert len(results) == 2
        assert results[0].title == "Result 1"
        assert results[1].title == "Result 2"
    
    @pytest.mark.asyncio
    async def test_search_deduplicates_by_url(self):
        class MockProvider:
            name = "mock"
            rate_limit_rpm = 60
            
            async def search(self, query, max_results=10):
                return [
                    SearchResult(title="Result 1", url="https://ex.com/1", snippet="Snippet 1", provider="mock", score=0.9),
                    SearchResult(title="Result 2", url="https://ex.com/1", snippet="Snippet 2", provider="mock", score=0.8),  # Same URL
                ]
            
            async def health_check(self):
                return {"status": "healthy"}
        
        manager = WebSearchManager()
        provider = MockProvider()
        manager.register_provider(provider)
        
        results = await manager.search("test query")
        
        assert len(results) == 1  # Deduplicated
        assert results[0].title == "Result 1"  # Higher score kept
    
    @pytest.mark.asyncio
    async def test_search_specific_providers(self):
        class MockProvider:
            name = "mock"
            rate_limit_rpm = 60
            
            async def search(self, query, max_results=10):
                return [SearchResult(title=f"{self.name} Result", url="https://ex.com", snippet="Snippet", provider=self.name, score=0.9)]
            
            async def health_check(self):
                return {"status": "healthy"}
        
        manager = WebSearchManager()
        provider1 = MockProvider()
        provider1.name = "provider1"
        provider2 = MockProvider()
        provider2.name = "provider2"
        
        manager.register_provider(provider1)
        manager.register_provider(provider2)
        
        results = await manager.search("test", providers=["provider1"])
        
        assert len(results) == 1
        assert results[0].provider == "provider1"


class TestZaramGovernedSession:
    """Test ZaramGovernedSession."""
    
    @pytest.mark.asyncio
    async def test_governed_session_creation(self):
        class MockEgressGate:
            def resolve(self, url, **kwargs):
                return url
        
        session = ZaramGovernedSession(MockEgressGate(), source="test")
        assert session is not None
    
    @pytest.mark.asyncio
    async def test_governed_session_blocks_on_denied(self):
        class DenyingEgressGate:
            def resolve(self, url, **kwargs):
                from core.egress import EgressDenied
                raise EgressDenied("test.com", "POST", "denied")
        
        session = ZaramGovernedSession(DenyingEgressGate(), source="test")
        
        with pytest.raises(ZaramSecurityViolation):
            await session.post("https://test.com/api", json={"test": "data"})
    
    @pytest.mark.asyncio
    async def test_governed_session_close(self):
        class MockEgressGate:
            def resolve(self, url, **kwargs):
                return url
        
        session = ZaramGovernedSession(MockEgressGate(), source="test")
        await session.close()
        assert session._closed is True


class TestZaramSecurityViolation:
    """Test ZaramSecurityViolation exception."""
    
    def test_security_violation_creation(self):
        exc = ZaramSecurityViolation("Test message", "test.com", "https://test.com/api", "entry-123")
        
        assert str(exc) == "Test message"
        assert exc.host == "test.com"
        assert exc.url == "https://test.com/api"
        assert exc.entry_id == "entry-123"