"""Tests for Pipeline Inlet Filters."""

import pytest
from backend.core.pipeline.builtins.spine_injector import SpineInjector
from backend.core.pipeline.builtins.token_budget import TokenBudgetEnforcer
from backend.core.pipeline.builtins.model_param_normalizer import ModelParamNormalizer
from backend.core.pipeline.types import PipelineContext, FilterResult


class TestSpineInjector:
    """Test SpineInjector inlet filter."""
    
    def test_spine_injector_skips_when_no_runtime(self):
        """Test filter skips when no memory runtime."""
        injector = SpineInjector(memory_runtime=None)
        
        import asyncio
        context = PipelineContext(request={"text": "test query"}, session_id="test", user_id="user")
        result = asyncio.run(injector.process({"text": "test query"}, context))
        
        assert result.metadata.get("skipped") == "no_memory_runtime"
    
    def test_spine_injector_skips_when_no_query(self):
        """Test filter skips when no query in request."""
        class MockMemoryRuntime:
            pass
        
        injector = SpineInjector(memory_runtime=MockMemoryRuntime())
        
        import asyncio
        context = PipelineContext(request={}, session_id="test", user_id="user")
        result = asyncio.run(injector.process({}, context))
        
        assert result.metadata.get("skipped") == "no_query"
    
    def test_spine_injector_priority(self):
        """Test SpineInjector has correct priority."""
        from backend.core.pipeline.types import FilterPriority
        injector = SpineInjector(memory_runtime=None)
        assert injector.priority == FilterPriority.CONTEXT


class TestTokenBudgetEnforcer:
    """Test TokenBudgetEnforcer inlet filter."""
    
    def test_token_budget_skips_when_no_budget_or_model(self):
        """Test filter skips when no budget or model."""
        enforcer = TokenBudgetEnforcer()
        
        import asyncio
        context = PipelineContext(request={"text": "test"}, session_id="test", user_id="user")
        result = asyncio.run(enforcer.process({"text": "test"}, context))
        
        assert result.metadata.get("skipped") == "no_budget_or_model"
    
    def test_token_budget_with_context_budget(self):
        """Test token budget with ContextBudget."""
        from backend.core.context_budget import ContextBudget
        
        budget = ContextBudget(total_tokens=4096, measured=True, reply_reserve_tokens=2048)
        enforcer = TokenBudgetEnforcer(context_budget=budget)
        
        import asyncio
        context = PipelineContext(request={"text": "short prompt"}, session_id="test", user_id="user")
        result = asyncio.run(enforcer.process({"text": "short prompt"}, context))
        
        assert result.metadata.get("within_budget") is True
        assert result.metadata.get("total_input", 0) <= budget.input_tokens - 1000
    
    def test_token_budget_priority(self):
        """Test TokenBudgetEnforcer has correct priority."""
        from backend.core.pipeline.types import FilterPriority
        enforcer = TokenBudgetEnforcer()
        assert enforcer.priority == FilterPriority.CONTEXT


class TestModelParamNormalizer:
    """Test ModelParamNormalizer inlet filter."""
    
    def test_model_param_normalizer_ollama(self):
        """Test normalizing params for Ollama model."""
        normalizer = ModelParamNormalizer()
        
        import asyncio
        request = {
            "text": "test",
            "model": "qwen2.5:14b",
            "temperature": 0.7,
            "max_tokens": 1000,
        }
        context = PipelineContext(request=request, session_id="test", user_id="user")
        result = asyncio.run(normalizer.process(request, context))
        
        assert result.modified_request is not None
        assert "normalized_params" in result.modified_request
        assert result.modified_request["resolved_provider"] == "ollama"
        # Check Ollama-specific param names
        params = result.modified_request["normalized_params"]
        assert "num_predict" in params  # Ollama uses num_predict for max_tokens
    
    def test_model_param_normalizer_openai(self):
        """Test normalizing params for OpenAI model."""
        normalizer = ModelParamNormalizer()
        
        import asyncio
        request = {
            "text": "test",
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 1000,
        }
        context = PipelineContext(request=request, session_id="test", user_id="user")
        result = asyncio.run(normalizer.process(request, context))
        
        assert result.modified_request is not None
        params = result.modified_request["normalized_params"]
        assert params["max_tokens"] == 1000  # OpenAI uses max_tokens
        assert result.modified_request["resolved_provider"] == "openai"
    
    def test_model_param_normalizer_priority(self):
        """Test ModelParamNormalizer has correct priority."""
        from backend.core.pipeline.types import FilterPriority
        normalizer = ModelParamNormalizer()
        assert normalizer.priority == FilterPriority.TRANSFORM