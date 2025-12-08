"""
Cache utilities for GitHub Followers Tracker.
Provides functions for loading and saving cached data.
"""
import os
import json
import logging
import tempfile
from typing import Any, Dict, Iterator, List, Sequence

logger = logging.getLogger(__name__)

# Allow overriding the cache location via environment variable
CACHE_FILE = os.getenv('GFT_CACHE_FILE', 'data/user_following_cache.json')


def _get_cache_file_path() -> str:
    """Resolve the cache file path."""
    return os.path.abspath(CACHE_FILE)


def chunks(lst: Sequence[Any], n: int) -> Iterator[List[Any]]:
    """Yield successive n-sized chunks from lst."""
    if n <= 0:
        raise ValueError(f"Chunk size must be > 0, got {n}")

    logger.debug(f"Creating chunks of size {n} for list of length {len(lst)}")
    for i in range(0, len(lst), n):
        yield list(lst[i:i + n])


def load_cache() -> Dict[str, Any]:
    """Load cache from disk."""
    path = _get_cache_file_path()
    logger.debug(f"Loading cache from {path}")

    if not os.path.exists(path):
        logger.debug("Cache file not found")
        return {}

    try:
        with open(path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            if isinstance(data, dict):
                logger.debug(f"Loaded cache with {len(data)} entries")
                return data
            else:
                logger.warning("Cache file JSON root is not an object; resetting cache to empty")
                return {}
    except json.JSONDecodeError:
        logger.error(f"Failed to decode cache JSON at {path}; resetting to empty")
        return {}
    except OSError as e:
        logger.error(f"Error reading cache file {path}: {e}")
        return {}


def save_cache(cache: Dict[str, Any]) -> None:
    """Persist cache to disk atomically."""
    path = _get_cache_file_path()
    logger.debug(f"Saving cache with {len(cache)} entries to {path}")

    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    tmp_file = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False, dir=directory or None,
                                         prefix=os.path.basename(path) + '.', suffix='.tmp') as tf:
            tmp_file = tf.name
            json.dump(cache, tf, ensure_ascii=False, separators=(',', ':'))
            tf.flush()
            os.fsync(tf.fileno())
        os.replace(tmp_file, path)
        logger.debug("Cache saved successfully")
    except OSError as e:
        logger.error(f"Failed to save cache to {path}: {e}")
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass


def get_cache_value(key: str, default: Any = None) -> Any:
    """Get a single value from cache."""
    cache = load_cache()
    return cache.get(key, default)


def set_cache_value(key: str, value: Any) -> None:
    """Set a single value in cache."""
    cache = load_cache()
    cache[key] = value
    save_cache(cache)
