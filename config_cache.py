"""Configuration caching system for performance optimization."""

from typing import Any, ClassVar, Dict, Generic, TypeVar
from config import SimulationConfig
from logger import log

T = TypeVar("T")


class ConfigCache(Generic[T]):
    """
    Generic configuration cache for storing frequently accessed values.

    Provides thread-safe caching with expiration and validation.
    """

    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        """
        Initialize configuration cache.

        Args:
            max_size: Maximum number of items to cache
            ttl_seconds: Time-to-live for cached items in seconds
        """
        self._cache: Dict[str, Any] = {}
        self._access_times: Dict[str, float] = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._hits = 0
        self._misses = 0

    def get(self, key: str, getter_func: callable) -> T:
        """
        Get a cached value or compute and cache it if not found.

        Args:
            key: Cache key
            getter_func: Function to compute value if not cached

        Returns:
            Cached or newly computed value
        """
        import time

        current_time = time.time()

        # Check if value is in cache and not expired
        if key in self._cache:
            access_time = self._access_times.get(key, 0)
            if current_time - access_time < self._ttl_seconds:
                self._hits += 1
                self._access_times[key] = current_time  # Update access time
                return self._cache[key]

        # Value not in cache or expired - compute and cache it
        self._misses += 1
        value = getter_func()

        # Add to cache (enforce size limit)
        self._cache[key] = value
        self._access_times[key] = current_time

        if len(self._cache) > self._max_size:
            self._evict_oldest()

        return value

    def _evict_oldest(self) -> None:
        """Evict the oldest accessed item from cache."""
        if not self._access_times:
            return

        oldest_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        del self._cache[oldest_key]
        del self._access_times[oldest_key]

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
        self._access_times.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> dict:
        """Get cache performance statistics."""
        return {
            "cache_size": len(self._cache),
            "hit_rate": self._hits / (self._hits + self._misses)
            if (self._hits + self._misses) > 0
            else 0,
            "hits": self._hits,
            "misses": self._misses,
        }


class AgentConfigCache:
    """
    Agent-specific configuration cache with support for nested config access.

    Optimized for agent performance with automatic cache invalidation.
    """

    def __init__(self, config: SimulationConfig):
        """
        Initialize agent configuration cache.

        Args:
            config: Simulation configuration to cache
        """
        self._config = config
        self._cache = ConfigCache[str]()
        self._section_caches: Dict[str, ConfigCache] = {}

    def get_config_value(self, path: str) -> Any:
        """
        Get a configuration value with caching.

        Args:
            path: Dot-separated path to config value (e.g., 'company.base_wage')

        Returns:
            Configuration value
        """

        def getter():
            try:
                keys = path.split(".")
                value = self._config
                for key in keys:
                    value = getattr(value, key)
                return value
            except (AttributeError, KeyError):
                return None

        return self._cache.get(path, getter)

    def get_section_cache(self, section: str) -> ConfigCache:
        """
        Get a dedicated cache for a configuration section.

        Args:
            section: Configuration section name

        Returns:
            Dedicated ConfigCache instance
        """
        if section not in self._section_caches:
            self._section_caches[section] = ConfigCache()
        return self._section_caches[section]

    def invalidate_cache(self) -> None:
        """Invalidate all cached values."""
        self._cache.clear()
        for cache in self._section_caches.values():
            cache.clear()

    def get_all_stats(self) -> dict:
        """Get statistics for all caches."""
        stats = {"main_cache": self._cache.get_stats(), "section_caches": {}}

        for section, cache in self._section_caches.items():
            stats["section_caches"][section] = cache.get_stats()

        return stats


class GlobalConfigCache:
    """
    Global configuration cache singleton for the simulation.

    Provides centralized configuration caching across all agents.
    """

    _instance = None

    def __new__(cls, config: SimulationConfig | None = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: SimulationConfig | None = None):
        if self._initialized:
            if config is not None:
                self._config = config
                self._cache.clear()
            return

        self._config = config
        self._cache = ConfigCache(max_size=200)
        self._initialized = True

    def initialize(self, config: SimulationConfig) -> None:
        """Initialize the global cache with a configuration."""
        self._config = config
        self._cache.clear()

    def get_config_value(self, path: str) -> Any:
        """
        Get a configuration value from the global cache.

        Args:
            path: Dot-separated path to config value

        Returns:
            Configuration value
        """
        if not self._config:
            raise ValueError("GlobalConfigCache not initialized")

        def getter():
            try:
                keys = path.split(".")
                value = self._config
                for key in keys:
                    value = getattr(value, key)
                return value
            except (AttributeError, KeyError):
                return None

        return self._cache.get(path, getter)

    def clear_cache(self) -> None:
        """Clear the global cache."""
        self._cache.clear()

    def get_cache_stats(self) -> dict:
        """Get global cache statistics."""
        return self._cache.get_stats()


# Convenience function for easy access
def get_cached_config_value(path: str) -> Any:
    """
    Get a configuration value from the global cache.

    Args:
        path: Dot-separated path to config value

    Returns:
        Configuration value
    """
    cache = GlobalConfigCache()
    return cache.get_config_value(path)
