"""steameditor.services.image_cache — LRU image cache with thumbnails."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from PIL import Image

_log = None


def _get_logger():
    global _log
    if _log is None:
        import logging
        _log = logging.getLogger("steameditor.image_cache")
    return _log


class ImageCache:
    """Thread-safe LRU image cache with size limit (strong refs)."""

    _instance: ImageCache | None = None
    _lock = threading.Lock()

    def __new__(cls, max_size_mb: int = 200):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init(max_size_mb)
            return cls._instance

    def _init(self, max_size_mb: int):
        self.max_bytes = max_size_mb * 1024 * 1024
        self._cache: dict[str, Image.Image] = {}
        self._sizes: dict[str, int] = {}
        self._access_order: list[str] = []
        self._lock = threading.RLock()

    def get(self, path: str | Path, max_size: tuple[int, int] | None = None) -> Optional[Image.Image]:
        """Get image from cache, optionally resized (returns copy if resized)."""
        path_str = str(path)
        with self._lock:
            img = self._cache.get(path_str)
            if img is None:
                return None
            # Move to front (LRU)
            if path_str in self._access_order:
                self._access_order.remove(path_str)
            self._access_order.insert(0, path_str)

            if max_size:
                # Return resized copy, keep original in cache
                copy = img.copy()
                copy.thumbnail(max_size, Image.LANCZOS)
                return copy
            return img.copy() if hasattr(img, "copy") else img

    def put(self, path: str | Path, img: Image.Image) -> None:
        """Add image to cache (stores copy to avoid external mutation)."""
        path_str = str(path)
        # Estimate memory: width * height * 4 (RGBA)
        size = img.width * img.height * 4
        with self._lock:
            # If already cached, remove old position first
            if path_str in self._cache:
                self._evict(path_str)
            self._evict_until_space(size)
            # Store a copy so external close/resize doesn't corrupt cache
            try:
                stored = img.copy()
            except Exception:
                stored = img
            self._cache[path_str] = stored
            self._sizes[path_str] = size
            self._access_order.insert(0, path_str)

    def _evict(self, path_str: str) -> None:
        self._cache.pop(path_str, None)
        self._sizes.pop(path_str, None)
        if path_str in self._access_order:
            self._access_order.remove(path_str)

    def _evict_until_space(self, needed: int) -> None:
        current = sum(self._sizes.values())
        while current + needed > self.max_bytes and self._access_order:
            oldest = self._access_order.pop()
            current -= self._sizes.pop(oldest, 0)
            self._cache.pop(oldest, None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._sizes.clear()
            self._access_order.clear()

    def stats(self) -> dict:
        with self._lock:
            return {
                "entries": len(self._cache),
                "size_mb": sum(self._sizes.values()) / 1024 / 1024,
                "max_mb": self.max_bytes / 1024 / 1024,
            }


def get_image_cache() -> ImageCache:
    return ImageCache()


# ════════════════════════════════════════════════════════════════════
# Thumbnail Generator (with cache integration)
# ════════════════════════════════════════════════════════════════════

_thumbnail_cache: ImageCache | None = None
_thumb_lock = threading.Lock()


def _create_thumbnail_cache() -> ImageCache:
    """Create independent 100MB cache bypassing main singleton."""
    obj = object.__new__(ImageCache)
    obj._init(100)  # type: ignore
    return obj


def get_thumbnail(path: str | Path, size: tuple[int, int] = (256, 256)) -> Image.Image:
    """Get or generate thumbnail for an image/GIF."""
    global _thumbnail_cache
    if _thumbnail_cache is None:
        with _thumb_lock:
            if _thumbnail_cache is None:
                _thumbnail_cache = _create_thumbnail_cache()

    cached = _thumbnail_cache.get(path, size)
    if cached:
        return cached

    # Generate
    try:
        img = Image.open(path)
        # For GIF, use first frame
        if hasattr(img, "n_frames") and img.n_frames > 1:
            img.seek(0)
        img = img.convert("RGBA")
        img.thumbnail(size, Image.LANCZOS)

        # Dark background for transparency
        bg = Image.new("RGBA", img.size, (28, 28, 28, 255))
        bg.paste(img, mask=img.split()[3])
        result = bg.convert("RGB")

        _thumbnail_cache.put(path, result)
        return result
    except Exception as e:
        _get_logger().error(f"[THUMBNAIL ERR] {path} | {e}")
        # Return placeholder
        placeholder = Image.new("RGB", size, (40, 40, 40))
        return placeholder