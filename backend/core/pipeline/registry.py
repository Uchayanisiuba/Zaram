"""Filter registry for managing pipeline filters."""

from __future__ import annotations

from typing import List, Callable, Awaitable, Dict, Any
from dataclasses import dataclass, field

from .types import (
    FilterPriority,
    InletFilter,
    OutletFilter,
    PipelineContext,
    FilterResult,
    InletFilterType,
    OutletFilterType,
)


@dataclass
class RegisteredInletFilter:
    """A registered inlet filter with metadata."""
    filter: InletFilter
    priority: FilterPriority
    name: str
    enabled: bool = True


@dataclass
class RegisteredOutletFilter:
    """A registered outlet filter with metadata."""
    filter: OutletFilter
    priority: FilterPriority
    name: str
    enabled: bool = True


class FilterRegistry:
    """Registry for pipeline filters with priority-based ordering."""
    
    def __init__(self):
        self._inlet_filters: List[RegisteredInletFilter] = []
        self._outlet_filters: List[RegisteredOutletFilter] = []
        self._filter_map: Dict[str, Any] = {}  # name -> filter for lookup
    
    def register_inlet(
        self,
        filter: InletFilter,
        priority: FilterPriority = FilterPriority.CONTEXT,
        name: Optional[str] = None,
    ) -> None:
        """Register an inlet filter."""
        filter_name = name or filter.__class__.__name__
        
        # Remove existing filter with same name
        self._inlet_filters = [f for f in self._inlet_filters if f.name != filter_name]
        
        registered = RegisteredInletFilter(
            filter=filter,
            priority=priority,
            name=filter_name,
        )
        self._inlet_filters.append(registered)
        self._inlet_filters.sort(key=lambda f: f.priority)
        self._filter_map[filter_name] = filter
    
    def register_outlet(
        self,
        filter: OutletFilter,
        priority: FilterPriority = FilterPriority.LOGGING,
        name: Optional[str] = None,
    ) -> None:
        """Register an outlet filter."""
        filter_name = name or filter.__class__.__name__
        
        # Remove existing filter with same name
        self._outlet_filters = [f for f in self._outlet_filters if f.name != filter_name]
        
        registered = RegisteredOutletFilter(
            filter=filter,
            priority=priority,
            name=filter_name,
        )
        self._outlet_filters.append(registered)
        self._outlet_filters.sort(key=lambda f: f.priority)
        self._filter_map[filter_name] = filter
    
    def register_inlet_func(
        self,
        func: InletFilterType,
        priority: FilterPriority = FilterPriority.CONTEXT,
        name: Optional[str] = None,
    ) -> None:
        """Register an inlet filter function."""
        filter_name = name or func.__name__
        
        class FuncInletFilter:
            def __init__(self, f, p):
                self._func = f
                self.priority = p
            
            async def process(self, request: Dict[str, Any], context: PipelineContext) -> FilterResult:
                return await self._func(request, context)
        
        self.register_inlet(FuncInletFilter(func, priority), priority, filter_name)
    
    def register_outlet_func(
        self,
        func: OutletFilterType,
        priority: FilterPriority = FilterPriority.LOGGING,
        name: Optional[str] = None,
    ) -> None:
        """Register an outlet filter function."""
        filter_name = name or func.__name__
        
        class FuncOutletFilter:
            def __init__(self, f, p):
                self._func = f
                self.priority = p
            
            async def process(self, response: Dict[str, Any], context: PipelineContext) -> FilterResult:
                return await self._func(response, context)
        
        self.register_outlet(FuncOutletFilter(func, priority), priority, filter_name)
    
    def unregister_inlet(self, name: str) -> bool:
        """Unregister an inlet filter by name."""
        for i, f in enumerate(self._inlet_filters):
            if f.name == name:
                self._inlet_filters.pop(i)
                self._filter_map.pop(name, None)
                return True
        return False
    
    def unregister_outlet(self, name: str) -> bool:
        """Unregister an outlet filter by name."""
        for i, f in enumerate(self._outlet_filters):
            if f.name == name:
                self._outlet_filters.pop(i)
                self._filter_map.pop(name, None)
                return True
        return False
    
    def get_inlet_filters(self) -> List[InletFilter]:
        """Get all enabled inlet filters in priority order."""
        return [f.filter for f in self._inlet_filters if f.enabled]
    
    def get_outlet_filters(self) -> List[OutletFilter]:
        """Get all enabled outlet filters in priority order."""
        return [f.filter for f in self._outlet_filters if f.enabled]
    
    def get_filter(self, name: str) -> Any:
        """Get a filter by name."""
        return self._filter_map.get(name)
    
    def set_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable a filter."""
        for f in self._inlet_filters:
            if f.name == name:
                f.enabled = enabled
                return True
        for f in self._outlet_filters:
            if f.name == name:
                f.enabled = enabled
                return True
        return False
    
    def list_filters(self) -> Dict[str, List[Dict[str, Any]]]:
        """List all registered filters with their status."""
        return {
            "inlet": [
                {
                    "name": f.name,
                    "priority": f.priority.value,
                    "enabled": f.enabled,
                    "class": f.filter.__class__.__name__,
                }
                for f in self._inlet_filters
            ],
            "outlet": [
                {
                    "name": f.name,
                    "priority": f.priority.value,
                    "enabled": f.enabled,
                    "class": f.filter.__class__.__name__,
                }
                for f in self._outlet_filters
            ],
        }
    
    def clear(self) -> None:
        """Clear all filters."""
        self._inlet_filters.clear()
        self._outlet_filters.clear()
        self._filter_map.clear()