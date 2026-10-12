"""Secure API key management for web search providers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, asdict


@dataclass
class APIKeyEntry:
    """An API key entry with metadata."""
    provider: str
    key: str
    name: str = ""
    created_at: float = 0.0
    last_used: float = 0.0
    enabled: bool = True
    rate_limit_rpm: Optional[int] = None
    
    def __post_init__(self):
        import time
        if self.created_at == 0.0:
            self.created_at = time.time()


class APIKeyManager:
    """Manages API keys for search providers."""
    
    def __init__(self, storage_path: Optional[str] = None):
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            from core.paths import data_dir
            self.storage_path = Path(data_dir()) / "web_search_keys.json"
        
        self._keys: Dict[str, APIKeyEntry] = {}
        self._load()
    
    def _load(self) -> None:
        """Load keys from storage."""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)
            
            for entry_data in data.get("keys", []):
                entry = APIKeyEntry(**entry_data)
                self._keys[entry.provider] = entry
        except Exception:
            pass
    
    def _save(self) -> None:
        """Save keys to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "keys": [asdict(entry) for entry in self._keys.values()],
        }
        
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)
        
        # Set restrictive permissions
        try:
            os.chmod(self.storage_path, 0o600)
        except OSError:
            pass
    
    def set_key(
        self,
        provider: str,
        key: str,
        name: str = "",
        rate_limit_rpm: Optional[int] = None,
    ) -> None:
        """Set or update an API key."""
        import time
        
        if provider in self._keys:
            entry = self._keys[provider]
            entry.key = key
            entry.name = name or entry.name
            entry.rate_limit_rpm = rate_limit_rpm or entry.rate_limit_rpm
            entry.last_used = time.time()
        else:
            entry = APIKeyEntry(
                provider=provider,
                key=key,
                name=name,
                rate_limit_rpm=rate_limit_rpm,
            )
            self._keys[provider] = entry
        
        self._save()
    
    def get_key(self, provider: str) -> Optional[str]:
        """Get an API key."""
        entry = self._keys.get(provider)
        if entry and entry.enabled:
            import time
            entry.last_used = time.time()
            self._save()
            return entry.key
        return None
    
    def get_entry(self, provider: str) -> Optional[APIKeyEntry]:
        """Get full key entry."""
        return self._keys.get(provider)
    
    def remove_key(self, provider: str) -> bool:
        """Remove an API key."""
        if provider in self._keys:
            del self._keys[provider]
            self._save()
            return True
        return False
    
    def list_providers(self) -> Dict[str, Dict[str, Any]]:
        """List all configured providers."""
        return {
            provider: {
                "name": entry.name,
                "enabled": entry.enabled,
                "created_at": entry.created_at,
                "last_used": entry.last_used,
                "rate_limit_rpm": entry.rate_limit_rpm,
                "has_key": bool(entry.key),
            }
            for provider, entry in self._keys.items()
        }
    
    def enable_provider(self, provider: str, enabled: bool = True) -> bool:
        """Enable or disable a provider."""
        if provider in self._keys:
            self._keys[provider].enabled = enabled
            self._save()
            return True
        return False
    
    def get_all_keys(self) -> Dict[str, str]:
        """Get all enabled keys as a simple dict."""
        return {
            provider: entry.key
            for provider, entry in self._keys.items()
            if entry.enabled and entry.key
        }


def create_api_key_manager(storage_path: Optional[str] = None) -> APIKeyManager:
    """Factory function to create an APIKeyManager."""
    return APIKeyManager(storage_path)