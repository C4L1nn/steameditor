"""Tests for ImageCache — strong LRU, eviction, thumbnail."""
import pathlib

from PIL import Image

from steameditor.services.image_cache import ImageCache, get_thumbnail


def test_put_and_get():
    # Use fresh instance bypassing singleton
    cache = object.__new__(ImageCache)
    cache._init(10)  # 10MB
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    cache.put("k1", img)
    retrieved = cache.get("k1")
    assert retrieved is not None
    assert retrieved.size == (100, 100)
    # Returned copy should not be same object
    assert retrieved is not img
    cache.clear()


def test_lru_eviction():
    cache = object.__new__(ImageCache)
    cache._init(max_size_mb=0)  # Force eviction on every put (almost)
    # Estimate: 100x100*4 = 40KB, so 0 MB will evict immediately? Use 0.04MB
    cache.max_bytes = 40 * 1024  # 40KB
    img1 = Image.new("RGB", (100, 100), (255, 0, 0))
    img2 = Image.new("RGB", (100, 100), (0, 255, 0))
    cache.put("k1", img1)
    assert cache.get("k1") is not None
    cache.put("k2", img2)
    # k1 should be evicted (LRU, oldest)
    assert cache.get("k1") is None
    assert cache.get("k2") is not None
    cache.clear()


def test_get_with_resize_returns_copy():
    cache = object.__new__(ImageCache)
    cache._init(10)
    img = Image.new("RGB", (200, 200), (10, 20, 30))
    cache.put("k", img)
    thumb = cache.get("k", max_size=(50, 50))
    assert thumb is not None
    assert thumb.size[0] <= 50 and thumb.size[1] <= 50
    # Original still 200x200
    orig = cache.get("k")
    assert orig.size == (200, 200)
    cache.clear()


def test_put_overwrites_existing():
    cache = object.__new__(ImageCache)
    cache._init(10)
    img1 = Image.new("RGB", (50, 50), (255, 0, 0))
    img2 = Image.new("RGB", (60, 60), (0, 255, 0))
    cache.put("k", img1)
    cache.put("k", img2)
    retrieved = cache.get("k")
    assert retrieved.size == (60, 60)
    assert cache.stats()["entries"] == 1
    cache.clear()


def test_lru_order_on_get():
    cache = object.__new__(ImageCache)
    cache._init(10)
    cache.max_bytes = 80 * 1024  # 80KB -> holds 2 images max
    a = Image.new("RGB", (100, 100), (1, 1, 1))  # 40KB
    b = Image.new("RGB", (100, 100), (2, 2, 2))
    c = Image.new("RGB", (100, 100), (3, 3, 3))
    cache.put("a", a)
    cache.put("b", b)
    # Access a to make it most recent
    cache.get("a")
    # Now put c -> should evict b (least recent), not a
    cache.put("c", c)
    assert cache.get("a") is not None
    assert cache.get("b") is None
    assert cache.get("c") is not None
    cache.clear()


def test_stats():
    cache = object.__new__(ImageCache)
    cache._init(1)
    assert cache.stats()["entries"] == 0
    img = Image.new("RGB", (10, 10), (0, 0, 0))
    cache.put("x", img)
    assert cache.stats()["entries"] == 1
    cache.clear()
    assert cache.stats()["entries"] == 0


def test_get_thumbnail_generates_and_caches(tmp_path):
    p = tmp_path / "img.png"
    Image.new("RGB", (200, 200), (80, 120, 200)).save(p)
    t1 = get_thumbnail(p, size=(64, 64))
    assert t1.size[0] <= 64 and t1.size[1] <= 64
    # Second call should be cached (same visual result)
    t2 = get_thumbnail(p, size=(64, 64))
    assert t2.size == t1.size


def test_get_thumbnail_handles_gif(tmp_path):
    p = tmp_path / "anim.gif"
    frames = [Image.new("RGB", (100, 100), (i * 40, 0, 0)) for i in range(3)]
    frames[0].save(p, save_all=True, append_images=frames[1:], duration=80, loop=0)
    t = get_thumbnail(p, size=(32, 32))
    assert t.size[0] <= 32


def test_get_thumbnail_missing_returns_placeholder(tmp_path):
    p = tmp_path / "nonexistent.png"
    t = get_thumbnail(p, size=(32, 32))
    assert t.size == (32, 32)
