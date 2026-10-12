"""Tests for Pipeline Orchestrator."""

import pytest
from backend.core.pipeline.pipeline import Pipeline, PipelineBlockedError, get_pipeline, set_pipeline
from backend.core.pipeline.registry import FilterRegistry
from backend.core.pipeline.types import PipelineContext, FilterResult, FilterPriority
from backend.core.pipeline.builtins.spine_injector import SpineInjector
from backend.core.pipeline.builtins.egress_guard import EgressGuard


class TestPipeline:
    """Test Pipeline class."""
    
    def test_pipeline_disabled_by_default(self):
        """Test pipeline is disabled by default (feature flag)."""
        import os
        os.environ["ZARAM_PIPELINE_ENABLED"] = "false"
        
        # Need to reimport to pick up env var
        import importlib
        import backend.core.pipeline.pipeline as pipeline_module
        importlib.reload(pipeline_module)
        
        registry = FilterRegistry()
        pipeline = Pipeline(registry=registry)
        assert pipeline.enabled is False
    
    def test_pipeline_process_inlet_when_disabled(self):
        """Test inlet processing returns request unchanged when disabled."""
        import os
        os.environ["ZARAM_PIPELINE_ENABLED"] = "false"
        
        import importlib
        import backend.core.pipeline.pipeline as pipeline_module
        importlib.reload(pipeline_module)
        
        registry = FilterRegistry()
        pipeline = Pipeline(registry=registry)
        
        import asyncio
        context = PipelineContext(request={"text": "test"}, session_id="test", user_id="user")
        result = asyncio.run(pipeline.process_inlet({"text": "test"}, context))
        
        assert result == {"text": "test"}
    
    def test_pipeline_process_outlet_when_disabled(self):
        """Test outlet processing returns response unchanged when disabled."""
        import os
        os.environ["ZARAM_PIPELINE_ENABLED"] = "false"
        
        import importlib
        import backend.core.pipeline.pipeline as pipeline_module
        importlib.reload(pipeline_module)
        
        registry = FilterRegistry()
        pipeline = Pipeline(registry=registry)
        
        import asyncio
        context = PipelineContext(request={}, session_id="test", user_id="user")
        result = asyncio.run(pipeline.process_outlet({"text": "response"}, context))
        
        assert result == {"text": "response"}
    
    def test_pipeline_run_when_disabled(self):
        """Test full pipeline run returns request when disabled."""
        import os
        os.environ["ZARAM_PIPELINE_ENABLED"] = "false"
        
        import importlib
        import backend.core.pipeline.pipeline as pipeline_module
        importlib.reload(pipeline_module)
        
        registry = FilterRegistry()
        pipeline = Pipeline(registry=registry)
        
        import asyncio
        context = PipelineContext(request={"text": "test"}, session_id="test", user_id="user")
        result = asyncio.run(pipeline.run({"text": "test"}, context))
        
        # When disabled and no LLM call, returns a default response dict
        assert result.get("pipeline_only") is True
        assert result.get("model") == "none"
    
    def test_pipeline_enable_disable(self):
        """Test enabling and disabling pipeline."""
        import os
        os.environ["ZARAM_PIPELINE_ENABLED"] = "false"
        
        import importlib
        import backend.core.pipeline.pipeline as pipeline_module
        importlib.reload(pipeline_module)
        
        registry = FilterRegistry()
        pipeline = Pipeline(registry=registry)
        
        assert pipeline.enabled is False
        pipeline.enable()
        assert pipeline.enabled is True
        pipeline.disable()
        assert pipeline.enabled is False
    
    def test_pipeline_get_status(self):
        """Test getting pipeline status."""
        registry = FilterRegistry()
        
        class TestInlet:
            priority = FilterPriority.CONTEXT
            async def process(self, request, context):
                return FilterResult()
        
        registry.register_inlet(TestInlet(), FilterPriority.CONTEXT, "test_inlet")
        
        pipeline = Pipeline(registry=registry)
        status = pipeline.get_status()
        
        assert "enabled" in status
        assert "filters" in status
        assert "inlet" in status["filters"]
        assert "outlet" in status["filters"]


class TestGlobalPipeline:
    """Test global pipeline functions."""
    
    def test_get_set_pipeline(self):
        """Test getting and setting global pipeline."""
        registry = FilterRegistry()
        pipeline = Pipeline(registry=registry)
        
        set_pipeline(pipeline)
        retrieved = get_pipeline()
        
        assert retrieved is pipeline
    
    def test_get_pipeline_none_when_not_set(self):
        """Test get_pipeline returns None when not set."""
        import backend.core.pipeline.pipeline as pipeline_module
        pipeline_module._pipeline = None
        
        retrieved = get_pipeline()
        assert retrieved is None