"""Tests for Pipeline Infrastructure - Types and Registry."""

import pytest
from backend.core.pipeline.types import (
    FilterPhase,
    FilterPriority,
    PipelineContext,
    FilterResult,
    InletFilter,
    OutletFilter,
)
from backend.core.pipeline.registry import FilterRegistry


class TestFilterPhase:
    """Test FilterPhase enum."""
    
    def test_filter_phase_values(self):
        assert FilterPhase.INLET.value == "inlet"
        assert FilterPhase.OUTLET.value == "outlet"


class TestFilterPriority:
    """Test FilterPriority enum."""
    
    def test_priority_order(self):
        assert FilterPriority.SECURITY < FilterPriority.CONTEXT
        assert FilterPriority.CONTEXT < FilterPriority.TRANSFORM
        assert FilterPriority.TRANSFORM < FilterPriority.LOGGING
    
    def test_priority_values(self):
        assert FilterPriority.SECURITY == 10
        assert FilterPriority.CONTEXT == 20
        assert FilterPriority.TRANSFORM == 30
        assert FilterPriority.LOGGING == 90


class TestPipelineContext:
    """Test PipelineContext dataclass."""
    
    def test_default_context(self):
        context = PipelineContext(request={"text": "test"})
        assert context.request == {"text": "test"}
        assert context.response is None
        assert context.session_id == "default"
        assert context.user_id == "user"
        assert context.project_id is None
        assert context.metadata == {}
    
    def test_custom_context(self):
        context = PipelineContext(
            request={"text": "test"},
            session_id="session1",
            user_id="user1",
            project_id="project1",
            metadata={"key": "value"},
        )
        assert context.session_id == "session1"
        assert context.user_id == "user1"
        assert context.project_id == "project1"
        assert context.metadata == {"key": "value"}


class TestFilterResult:
    """Test FilterResult dataclass."""
    
    def test_default_result(self):
        result = FilterResult()
        assert result.modified_request is None
        assert result.modified_response is None
        assert result.blocked is False
        assert result.block_reason is None
        assert result.metadata == {}
        assert result.has_modifications is False
    
    def test_result_with_modifications(self):
        result = FilterResult(modified_request={"text": "modified"})
        assert result.has_modifications is True
    
    def test_result_with_block(self):
        result = FilterResult(blocked=True, block_reason="Policy violation")
        assert result.blocked is True
        assert result.block_reason == "Policy violation"


class TestFilterRegistry:
    """Test FilterRegistry class."""
    
    def test_register_inlet(self):
        """Test registering an inlet filter."""
        registry = FilterRegistry()
        
        class TestInletFilter:
            priority = FilterPriority.CONTEXT
            async def process(self, request, context):
                return FilterResult()
        
        registry.register_inlet(TestInletFilter(), FilterPriority.CONTEXT, "test_filter")
        filters = registry.get_inlet_filters()
        assert len(filters) == 1
        assert filters[0].__class__.__name__ == "TestInletFilter"
    
    def test_register_outlet(self):
        """Test registering an outlet filter."""
        registry = FilterRegistry()
        
        class TestOutletFilter:
            priority = FilterPriority.SECURITY
            async def process(self, response, context):
                return FilterResult()
        
        registry.register_outlet(TestOutletFilter(), FilterPriority.SECURITY, "test_filter")
        filters = registry.get_outlet_filters()
        assert len(filters) == 1
    
    def test_priority_ordering(self):
        """Test filters are ordered by priority."""
        registry = FilterRegistry()
        
        class LowPriorityFilter:
            priority = FilterPriority.LOGGING
            async def process(self, request, context):
                return FilterResult()
        
        class HighPriorityFilter:
            priority = FilterPriority.SECURITY
            async def process(self, request, context):
                return FilterResult()
        
        registry.register_inlet(LowPriorityFilter(), FilterPriority.LOGGING, "low")
        registry.register_inlet(HighPriorityFilter(), FilterPriority.SECURITY, "high")
        
        filters = registry.get_inlet_filters()
        assert filters[0].__class__.__name__ == "HighPriorityFilter"
        assert filters[1].__class__.__name__ == "LowPriorityFilter"
    
    def test_unregister_inlet(self):
        """Test unregistering an inlet filter."""
        registry = FilterRegistry()
        
        class TestFilter:
            priority = FilterPriority.CONTEXT
            async def process(self, request, context):
                return FilterResult()
        
        registry.register_inlet(TestFilter(), FilterPriority.CONTEXT, "test")
        assert len(registry.get_inlet_filters()) == 1
        
        registry.unregister_inlet("test")
        assert len(registry.get_inlet_filters()) == 0
    
    def test_unregister_outlet(self):
        """Test unregistering an outlet filter."""
        registry = FilterRegistry()
        
        class TestFilter:
            priority = FilterPriority.SECURITY
            async def process(self, response, context):
                return FilterResult()
        
        registry.register_outlet(TestFilter(), FilterPriority.SECURITY, "test")
        assert len(registry.get_outlet_filters()) == 1
        
        registry.unregister_outlet("test")
        assert len(registry.get_outlet_filters()) == 0
    
    def test_register_inlet_function(self):
        """Test registering inlet filter function."""
        registry = FilterRegistry()
        
        async def inlet_func(request, context):
            return FilterResult()
        
        registry.register_inlet_func(inlet_func, FilterPriority.CONTEXT, "func_filter")
        filters = registry.get_inlet_filters()
        assert len(filters) == 1
    
    def test_register_outlet_function(self):
        """Test registering outlet filter function."""
        registry = FilterRegistry()
        
        async def outlet_func(response, context):
            return FilterResult()
        
        registry.register_outlet_func(outlet_func, FilterPriority.SECURITY, "func_filter")
        filters = registry.get_outlet_filters()
        assert len(filters) == 1
    
    def test_set_enabled(self):
        """Test enabling/disabling filters."""
        registry = FilterRegistry()
        
        class TestFilter:
            priority = FilterPriority.CONTEXT
            async def process(self, request, context):
                return FilterResult()
        
        registry.register_inlet(TestFilter(), FilterPriority.CONTEXT, "test")
        assert len(registry.get_inlet_filters()) == 1
        
        registry.set_enabled("test", False)
        assert len(registry.get_inlet_filters()) == 0
        
        registry.set_enabled("test", True)
        assert len(registry.get_inlet_filters()) == 1
    
    def test_list_filters(self):
        """Test listing filters."""
        registry = FilterRegistry()
        
        class InletF:
            priority = FilterPriority.CONTEXT
            async def process(self, request, context):
                return FilterResult()
        
        class OutletF:
            priority = FilterPriority.SECURITY
            async def process(self, response, context):
                return FilterResult()
        
        registry.register_inlet(InletF(), FilterPriority.CONTEXT, "inlet_test")
        registry.register_outlet(OutletF(), FilterPriority.SECURITY, "outlet_test")
        
        listed = registry.list_filters()
        assert len(listed["inlet"]) == 1
        assert len(listed["outlet"]) == 1
        assert listed["inlet"][0]["name"] == "inlet_test"
        assert listed["outlet"][0]["name"] == "outlet_test"
    
    def test_clear(self):
        """Test clearing all filters."""
        registry = FilterRegistry()
        
        class TestFilter:
            priority = FilterPriority.CONTEXT
            async def process(self, request, context):
                return FilterResult()
        
        registry.register_inlet(TestFilter(), FilterPriority.CONTEXT, "test")
        registry.register_outlet(TestFilter(), FilterPriority.SECURITY, "test2")
        
        registry.clear()
        assert len(registry.get_inlet_filters()) == 0
        assert len(registry.get_outlet_filters()) == 0