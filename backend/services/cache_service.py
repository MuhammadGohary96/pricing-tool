"""
Disk-based cache service for pricing data.

Enables zero-downtime app startup by caching aggregated data to disk.
Cache is refreshed in background every 6 hours.
"""

import pickle
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class DataCache:
    """Disk-based cache for pricing data with versioning and TTL."""

    CACHE_DIR = Path("cache/pricing_data")
    CACHE_VERSION = "v1.2"  # Match existing cache file; _global_df re-aggregated at load if stale-schema
    MAX_AGE_HOURS = 24  # Cache freshness threshold (24h)

    def __init__(self, cache_dir: Optional[Path] = None, max_age_hours: Optional[int] = None):
        """
        Initialize cache service.

        Args:
            cache_dir: Optional custom cache directory
            max_age_hours: Optional custom max age (default: 6 hours)
        """
        self.CACHE_DIR = cache_dir or self.CACHE_DIR
        self.MAX_AGE_HOURS = max_age_hours or self.MAX_AGE_HOURS

        # Create cache directory if it doesn't exist
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"[Cache] Initialized cache directory: {self.CACHE_DIR}")

    def get_cache_path(self, cache_key: str) -> Path:
        """Get path for cache file."""
        # Use hash of key to avoid filesystem issues with long names
        key_hash = hashlib.md5(cache_key.encode()).hexdigest()[:16]
        return self.CACHE_DIR / f"{cache_key}_{key_hash}_{self.CACHE_VERSION}.pkl"

    def save(self, cache_key: str, data: dict) -> bool:
        """
        Save data to cache with timestamp and version.

        Args:
            cache_key: Unique identifier for this cache entry
            data: Dictionary of data to cache

        Returns:
            True if save successful, False otherwise
        """
        cache_file = self.get_cache_path(cache_key)

        try:
            cache_data = {
                "data": data,
                "timestamp": datetime.now(),
                "version": self.CACHE_VERSION,
                "cache_key": cache_key,
            }

            # Write to temp file first, then rename (atomic operation)
            temp_file = cache_file.with_suffix('.tmp')
            with open(temp_file, "wb") as f:
                pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)

            temp_file.rename(cache_file)

            age_str = "just now"
            size_mb = cache_file.stat().st_size / (1024 * 1024)
            logger.info(f"[Cache] Saved '{cache_key}' ({size_mb:.1f} MB) to {cache_file.name}")
            return True

        except Exception as e:
            logger.error(f"[Cache] Error saving cache '{cache_key}': {e}")
            return False

    def load(self, cache_key: str) -> Optional[dict]:
        """
        Load data from cache if valid and fresh enough.

        Args:
            cache_key: Unique identifier for cache entry

        Returns:
            Cached data dictionary if valid, None otherwise
        """
        cache_file = self.get_cache_path(cache_key)

        if not cache_file.exists():
            logger.info(f"[Cache] No cache found for '{cache_key}'")
            return None

        try:
            with open(cache_file, "rb") as f:
                cache_data = pickle.load(f)

            # Validate cache structure
            if not isinstance(cache_data, dict) or "data" not in cache_data:
                logger.warning(f"[Cache] Invalid cache structure for '{cache_key}', ignoring")
                return None

            # Check version compatibility
            cached_version = cache_data.get("version")
            if cached_version != self.CACHE_VERSION:
                logger.warning(
                    f"[Cache] Version mismatch for '{cache_key}' "
                    f"(cached: {cached_version}, current: {self.CACHE_VERSION}), ignoring"
                )
                return None

            # Check cache age
            timestamp = cache_data.get("timestamp")
            if not isinstance(timestamp, datetime):
                logger.warning(f"[Cache] Invalid timestamp in cache '{cache_key}', ignoring")
                return None

            age = datetime.now() - timestamp
            age_hours = age.total_seconds() / 3600

            # NOTE: we deliberately do NOT reject stale-but-present cache here.
            # Returning slightly-old data lets the app start in seconds; the
            # background refresh (gated by is_stale()) brings it current without
            # blocking the UI. Rejecting here forced a full ~11-min BigQuery
            # re-download on every cold start past the TTL — the opposite of the
            # zero-downtime design. Only a version mismatch (above) invalidates.
            size_mb = cache_file.stat().st_size / (1024 * 1024)
            staleness = "fresh" if age_hours <= self.MAX_AGE_HOURS else f"STALE — bg refresh will run"
            logger.info(
                f"[Cache] Loaded '{cache_key}' from cache "
                f"({age_hours:.1f} hours old, {size_mb:.1f} MB, {staleness})"
            )
            return cache_data["data"]

        except Exception as e:
            logger.error(f"[Cache] Error loading cache '{cache_key}': {e}")
            return None

    def is_stale(self, cache_key: str) -> bool:
        """
        Check if cache exists and needs refresh.

        Args:
            cache_key: Unique identifier for cache entry

        Returns:
            True if cache is missing or stale, False if fresh
        """
        cache_file = self.get_cache_path(cache_key)

        if not cache_file.exists():
            return True

        try:
            with open(cache_file, "rb") as f:
                cache_data = pickle.load(f)

            # Check version
            if cache_data.get("version") != self.CACHE_VERSION:
                return True

            # Check age
            timestamp = cache_data.get("timestamp")
            if not isinstance(timestamp, datetime):
                return True

            age = datetime.now() - timestamp
            is_stale = age > timedelta(hours=self.MAX_AGE_HOURS)

            if is_stale:
                age_hours = age.total_seconds() / 3600
                logger.info(f"[Cache] '{cache_key}' is stale ({age_hours:.1f} hours old)")

            return is_stale

        except Exception as e:
            logger.error(f"[Cache] Error checking staleness of '{cache_key}': {e}")
            return True

    def invalidate(self, cache_key: str) -> bool:
        """
        Delete cache entry.

        Args:
            cache_key: Unique identifier for cache entry

        Returns:
            True if deleted, False if not found or error
        """
        cache_file = self.get_cache_path(cache_key)

        if not cache_file.exists():
            return False

        try:
            cache_file.unlink()
            logger.info(f"[Cache] Invalidated cache '{cache_key}'")
            return True
        except Exception as e:
            logger.error(f"[Cache] Error invalidating cache '{cache_key}': {e}")
            return False

    def clear_all(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of cache files deleted
        """
        count = 0
        try:
            for cache_file in self.CACHE_DIR.glob("*.pkl"):
                cache_file.unlink()
                count += 1
            logger.info(f"[Cache] Cleared {count} cache files")
        except Exception as e:
            logger.error(f"[Cache] Error clearing cache: {e}")

        return count

    def get_info(self, cache_key: str) -> Optional[dict]:
        """
        Get metadata about cache entry without loading data.

        Args:
            cache_key: Unique identifier for cache entry

        Returns:
            Dictionary with cache metadata or None
        """
        cache_file = self.get_cache_path(cache_key)

        if not cache_file.exists():
            return None

        try:
            stat = cache_file.stat()

            # Load just the metadata (first part of pickle)
            with open(cache_file, "rb") as f:
                cache_data = pickle.load(f)

            timestamp = cache_data.get("timestamp", datetime.min)
            age = datetime.now() - timestamp

            return {
                "cache_key": cache_key,
                "version": cache_data.get("version"),
                "timestamp": timestamp,
                "age_hours": age.total_seconds() / 3600,
                "size_mb": stat.st_size / (1024 * 1024),
                "is_stale": self.is_stale(cache_key),
            }

        except Exception as e:
            logger.error(f"[Cache] Error getting info for '{cache_key}': {e}")
            return None
