import os
import time
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class KeyStatus(BaseModel):
    alias: str
    masked_key: str
    is_manager_dedicated: bool
    is_healthy: bool
    total_calls: int = 0
    cooldown_remaining_sec: float = 0.0


class APIKeyEntry:
    def __init__(
        self,
        key: str,
        alias: str,
        is_manager_dedicated: bool = False,
    ) -> None:
        self.key = key.strip()
        self.alias = alias
        self.is_manager_dedicated = is_manager_dedicated
        self.last_used_at: float = 0.0
        self.unblock_at: float = 0.0
        self.total_calls: int = 0
        self.error_count: int = 0

    @property
    def masked_key(self) -> str:
        if len(self.key) <= 8:
            return "***"
        prefix = self.key[:4]
        suffix = self.key[-4:]
        return f"{prefix}...{suffix}"

    @property
    def is_healthy(self) -> bool:
        return time.monotonic() >= self.unblock_at

    @property
    def cooldown_remaining_sec(self) -> float:
        now = time.monotonic()
        return max(0.0, round(self.unblock_at - now, 1))


class KeyPoolManager:
    """Manages a pool of 5-10 API keys with dedicated allocation for higher managers,
    automatic round-robin rotation, and 429 rate-limit failover."""

    def __init__(self) -> None:
        self._keys: Dict[str, APIKeyEntry] = {}
        self._load_from_env()

    def _load_from_env(self) -> None:
        # 1. Dedicated manager keys (for CEO, CTO, Executives, Level <= 3)
        mgr_keys_str = os.getenv("GROQ_MANAGER_KEYS", "").strip()
        if mgr_keys_str:
            for i, raw_k in enumerate(mgr_keys_str.split(",")):
                k = raw_k.strip()
                if k and k not in [entry.key for entry in self._keys.values()]:
                    self.add_key(k, alias=f"manager_key_{i+1}", is_manager_dedicated=True)

        # 2. General multi-key pool (comma-separated list of keys)
        keys_pool_str = os.getenv("GROQ_API_KEYS", "").strip()
        if keys_pool_str:
            for i, raw_k in enumerate(keys_pool_str.split(",")):
                k = raw_k.strip()
                if k and k not in [entry.key for entry in self._keys.values()]:
                    self.add_key(k, alias=f"pool_key_{i+1}", is_manager_dedicated=False)

        # 3. Default fallback key
        default_key = os.getenv("GROQ_API_KEY", "").strip()
        if default_key and default_key not in ("your_groq_api_key_here", "no-key-set"):
            if default_key not in [entry.key for entry in self._keys.values()]:
                self.add_key(default_key, alias="default_key", is_manager_dedicated=False)

    def add_key(self, key: str, alias: Optional[str] = None, is_manager_dedicated: bool = False) -> str:
        k = key.strip()
        if not k:
            raise ValueError("API Key cannot be empty.")

        assigned_alias = alias or f"key_{len(self._keys) + 1}"
        self._keys[assigned_alias] = APIKeyEntry(
            key=k,
            alias=assigned_alias,
            is_manager_dedicated=is_manager_dedicated,
        )
        return assigned_alias

    def remove_key(self, alias: str) -> bool:
        if alias in self._keys:
            del self._keys[alias]
            return True
        return False

    def select_key_for_agent(
        self,
        agent_level: int = 5,
        dedicated_key: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Selects the best available API key.
        - If dedicated_key provided by manager: returns it immediately.
        - If agent_level <= 3 (CEO, Execs, Managers): prefers dedicated manager keys.
        - If associate: selects from general pool.
        - Automatic round-robin / least-recently-used among healthy keys.
        """
        # A) Agent has a custom dedicated key configured in their profile
        if dedicated_key and dedicated_key.strip():
            k = dedicated_key.strip()
            alias = f"custom_lvl{agent_level}_{k[-4:] if len(k) >= 4 else 'key'}"
            if alias not in self._keys:
                self.add_key(k, alias=alias, is_manager_dedicated=(agent_level <= 3))
            entry = self._keys[alias]
            entry.last_used_at = time.monotonic()
            entry.total_calls += 1
            return entry.key, entry.alias

        if not self._keys:
            # Fallback to env or placeholder if pool is empty
            fallback = os.getenv("GROQ_API_KEY", "no-key-set")
            return fallback, "fallback"

        now = time.monotonic()
        is_higher_manager = (agent_level <= 3)

        # Higher managers try manager-dedicated keys first
        if is_higher_manager:
            mgr_candidates = [
                entry for entry in self._keys.values()
                if entry.is_manager_dedicated and entry.is_healthy
            ]
            if mgr_candidates:
                # Least recently used
                chosen = min(mgr_candidates, key=lambda e: e.last_used_at)
                chosen.last_used_at = now
                chosen.total_calls += 1
                return chosen.key, chosen.alias

        # General pool candidates (or fallback for managers if manager pool exhausted)
        general_candidates = [
            entry for entry in self._keys.values()
            if entry.is_healthy and (not entry.is_manager_dedicated or is_higher_manager)
        ]

        if general_candidates:
            chosen = min(general_candidates, key=lambda e: e.last_used_at)
            chosen.last_used_at = now
            chosen.total_calls += 1
            return chosen.key, chosen.alias

        # If all healthy candidates exhausted, pick the one with lowest remaining cooldown
        all_candidates = list(self._keys.values())
        chosen = min(all_candidates, key=lambda e: e.unblock_at)
        chosen.last_used_at = now
        chosen.total_calls += 1
        return chosen.key, chosen.alias

    def mark_key_rate_limited(self, alias: str, cooldown_sec: float = 60.0) -> None:
        """Temporarily mark a key as rate-limited on 429 so the pool immediately rotates to another key."""
        if alias in self._keys:
            self._keys[alias].unblock_at = time.monotonic() + cooldown_sec
            self._keys[alias].error_count += 1

    def get_pool_status(self) -> List[KeyStatus]:
        return [
            KeyStatus(
                alias=entry.alias,
                masked_key=entry.masked_key,
                is_manager_dedicated=entry.is_manager_dedicated,
                is_healthy=entry.is_healthy,
                total_calls=entry.total_calls,
                cooldown_remaining_sec=entry.cooldown_remaining_sec,
            )
            for entry in self._keys.values()
        ]


key_pool = KeyPoolManager()
