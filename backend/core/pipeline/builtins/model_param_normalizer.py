"""ModelParamNormalizer - Inlet filter that normalizes model parameters to provider-specific format."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..types import BaseInletFilter, FilterPriority, PipelineContext, FilterResult


class ModelParamNormalizer(BaseInletFilter):
    """Inlet filter that maps Zaram parameters to provider-specific format."""

    priority = FilterPriority.TRANSFORM

    # Provider-specific parameter mappings
    PROVIDER_PARAM_MAP = {
        "ollama": {
            "temperature": "temperature",
            "max_tokens": "num_predict",
            "top_p": "top_p",
            "top_k": "top_k",
            "stop": "stop",
        },
        "openai": {
            "temperature": "temperature",
            "max_tokens": "max_tokens",
            "top_p": "top_p",
            "stop": "stop",
        },
        "anthropic": {
            "temperature": "temperature",
            "max_tokens": "max_tokens",
            "top_p": "top_p",
            "stop_sequences": "stop",
        },
        "google": {
            "temperature": "temperature",
            "max_tokens": "max_output_tokens",
            "top_p": "top_p",
            "top_k": "top_k",
            "stop": "stop_sequences",
        },
    }

    # Default parameter values per provider
    PROVIDER_DEFAULTS = {
        "ollama": {
            "temperature": 0.7,
            "num_predict": 2048,
            "top_p": 0.9,
            "top_k": 40,
        },
        "openai": {
            "temperature": 1.0,
            "max_tokens": 2048,
            "top_p": 1.0,
        },
        "anthropic": {
            "temperature": 1.0,
            "max_tokens": 2048,
            "top_p": 1.0,
        },
        "google": {
            "temperature": 0.9,
            "max_output_tokens": 2048,
            "top_p": 1.0,
            "top_k": 40,
        },
    }

    def __init__(
        self,
        model_registry: Optional[Any] = None,
    ):
        self.model_registry = model_registry

    async def process(self, request: Dict[str, Any], context: PipelineContext) -> FilterResult:
        """Normalize model parameters for the target provider."""
        model = request.get("model")
        if not model:
            return FilterResult(metadata={"skipped": "no_model"})

        # Determine provider from model name or registry
        provider = self._resolve_provider(model)
        if not provider:
            return FilterResult(metadata={"skipped": "unknown_provider", "model": model})

        # Get parameter mapping for provider
        param_map = self.PROVIDER_PARAM_MAP.get(provider, {})
        defaults = self.PROVIDER_DEFAULTS.get(provider, {})

        # Build normalized parameters
        normalized = {}
        for zaram_param, provider_param in param_map.items():
            value = request.get(zaram_param)
            if value is not None:
                normalized[provider_param] = value
            elif provider_param in defaults:
                normalized[provider_param] = defaults[provider_param]

        # Add any provider-specific extra params from request
        extra_params = request.get("provider_params", {})
        if isinstance(extra_params, dict):
            normalized.update(extra_params)

        modified_request = dict(request)
        modified_request["normalized_params"] = normalized
        modified_request["resolved_provider"] = provider

        return FilterResult(
            modified_request=modified_request,
            metadata={
                "provider": provider,
                "normalized_params": list(normalized.keys()),
            },
        )

    def _resolve_provider(self, model: str) -> Optional[str]:
        """Resolve provider from model name."""
        model_lower = model.lower()

        # Check known prefixes
        if model_lower.startswith("ollama/") or ":" in model and not any(p in model_lower for p in ["/", "gpt", "claude", "gemini"]):
            return "ollama"
        if model_lower.startswith("openai/") or model_lower.startswith("gpt-"):
            return "openai"
        if model_lower.startswith("anthropic/") or model_lower.startswith("claude-"):
            return "anthropic"
        if model_lower.startswith("google/") or model_lower.startswith("gemini-"):
            return "google"

        # Check registry if available
        if self.model_registry:
            try:
                model_info = self.model_registry.get_model(model)
                if model_info and hasattr(model_info, "provider"):
                    return model_info.provider
            except Exception:
                pass

        # Default to ollama for local models
        return "ollama"


def create_model_param_normalizer(model_registry: Optional[Any] = None) -> ModelParamNormalizer:
    """Factory function to create a ModelParamNormalizer."""
    return ModelParamNormalizer(model_registry=model_registry)