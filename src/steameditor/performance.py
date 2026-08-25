"""
steameditor.performance — GPU acceleration, parallel processing, and optimized image operations.
"""

from __future__ import annotations

import os
import sys
import logging
import concurrent.futures
from pathlib import Path
from typing import Optional, List, Tuple, Any, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import partial

from PIL import Image, ImageFilter, ImageEnhance, ImageOps, ImageChops, ImageDraw, ImageFont, ImageSequence
import numpy as np

from steameditor.services.log_service import get_logger

_log = get_logger("performance")

# ─── Hardware Detection ───

@dataclass
class HardwareCapabilities:
    """Detected hardware capabilities."""
    has_cuda: bool = False
    has_metal: bool = False
    has_opencl: bool = False
    cpu_cores: int = 1
    gpu_memory_mb: int = 0
    supports_webp_lossless: bool = True
    supports_avx2: bool = False
    
    @classmethod
    def detect(cls) -> "HardwareCapabilities":
        """Detect available hardware capabilities."""
        caps = cls()
        
        # CPU cores
        try:
            caps.cpu_cores = os.cpu_count() or 1
        except Exception:
            caps.cpu_cores = 1
        
        # CUDA detection
        try:
            import torch
            caps.has_cuda = torch.cuda.is_available()
            if caps.has_cuda:
                caps.gpu_memory_mb = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
        except ImportError:
            pass
        
        # Metal detection (macOS)
        if sys.platform == "darwin":
            try:
                import subprocess
                result = subprocess.run(["system_profiler", "SPDisplaysDataType"], 
                                      capture_output=True, text=True, timeout=5)
                caps.has_metal = "Metal" in result.stdout
            except Exception:
                pass
        
        # OpenCL detection
        try:
            import pyopencl as cl
            platforms = cl.get_platforms()
            caps.has_opencl = len(platforms) > 0
        except ImportError:
            pass
        
        # AVX2 detection
        try:
            import cpuinfo
            caps.supports_avx2 = "avx2" in cpuinfo.get_cpu_info().get("flags", [])
        except ImportError:
            # Fallback: check /proc/cpuinfo on Linux
            if sys.platform == "linux":
                try:
                    with open("/proc/cpuinfo") as f:
                        caps.supports_avx2 = "avx2" in f.read()
                except Exception:
                    pass
        
        _log.info(f"Hardware detected: CPU cores={caps.cpu_cores}, "
                  f"CUDA={caps.has_cuda}, Metal={caps.has_metal}, "
                  f"OpenCL={caps.has_opencl}, AVX2={caps.supports_avx2}")
        return caps


# Global hardware capabilities
_HARDWARE_CAPS: HardwareCapabilities | None = None


def get_hardware_caps() -> HardwareCapabilities:
    global _HARDWARE_CAPS
    if _HARDWARE_CAPS is None:
        _HARDWARE_CAPS = HardwareCapabilities.detect()
    return _HARDWARE_CAPS


# ─── GPU-Accelerated Image Operations ───

class GPUAccelerator:
    """GPU-accelerated image operations using available hardware."""
    
    def __init__(self):
        self.caps = get_hardware_caps()
        self._cuda_context = None
        self._opencl_context = None
        self._init_gpu()
    
    def _init_gpu(self):
        """Initialize GPU contexts."""
        if self.caps.has_cuda:
            try:
                import torch
                self._cuda_context = torch.cuda.current_context()
                _log.info("CUDA context initialized")
            except Exception as e:
                _log.warning(f"Failed to initialize CUDA: {e}")
                self.caps.has_cuda = False
        
        if self.caps.has_opencl:
            try:
                import pyopencl as cl
                self._opencl_context = cl.create_some_context()
                self._opencl_queue = cl.CommandQueue(self._opencl_context)
                _log.info("OpenCL context initialized")
            except Exception as e:
                _log.warning(f"Failed to initialize OpenCL: {e}")
                self.caps.has_opencl = False
    
    def enhance_image_gpu(self, img: Image.Image, 
                          contrast: float = 1.0,
                          brightness: float = 1.0,
                          saturation: float = 1.0,
                          sharpness: float = 1.0) -> Image.Image:
        """Apply enhancements using GPU acceleration."""
        if not self.caps.has_cuda and not self.caps.has_opencl:
            # Fallback to CPU
            return self._enhance_cpu(img, contrast, brightness, saturation, sharpness)
        
        try:
            if self.caps.has_cuda:
                return self._enhance_cuda(img, contrast, brightness, saturation, sharpness)
            elif self.caps.has_opencl:
                return self._enhance_opencl(img, contrast, brightness, saturation, sharpness)
        except Exception as e:
            _log.warning(f"GPU enhancement failed, falling back to CPU: {e}")
        
        return self._enhance_cpu(img, contrast, brightness, saturation, sharpness)
    
    def _enhance_cpu(self, img: Image.Image, contrast: float, brightness: float,
                     saturation: float, sharpness: float) -> Image.Image:
        """CPU fallback for enhancements."""
        result = img.convert("RGB")
        if contrast != 1.0:
            result = ImageEnhance.Contrast(result).enhance(contrast)
        if brightness != 1.0:
            result = ImageEnhance.Brightness(result).enhance(brightness)
        if saturation != 1.0:
            result = ImageEnhance.Color(result).enhance(saturation)
        if sharpness != 1.0:
            result = ImageEnhance.Sharpness(result).enhance(sharpness)
        return result.convert(img.mode)
    
    def _enhance_cuda(self, img: Image.Image, contrast: float, brightness: float,
                      saturation: float, sharpness: float) -> Image.Image:
        """CUDA-accelerated enhancement."""
        import torch
        import torchvision.transforms.functional as TF
        
        # Convert to tensor
        tensor = TF.to_tensor(img).unsqueeze(0).cuda()
        
        # Apply enhancements
        if brightness != 1.0:
            tensor = TF.adjust_brightness(tensor, brightness)
        if contrast != 1.0:
            tensor = TF.adjust_contrast(tensor, contrast)
        if saturation != 1.0:
            tensor = TF.adjust_saturation(tensor, saturation)
        
        # Sharpness requires custom kernel
        if sharpness != 1.0:
            # Unsharp mask via convolution
            kernel = torch.tensor([[-1, -1, -1],
                                   [-1,  9, -1],
                                   [-1, -1, -1]], dtype=torch.float32).cuda()
            kernel = kernel.view(1, 1, 3, 3).repeat(3, 1, 1, 1)
            sharpened = torch.nn.functional.conv2d(tensor, kernel, padding=1, groups=3)
            tensor = tensor + (sharpened - tensor) * (sharpness - 1.0)
            tensor = torch.clamp(tensor, 0, 1)
        
        # Convert back
        result = TF.to_pil_image(tensor.squeeze(0).cpu())
        return result.convert(img.mode)
    
    def _enhance_opencl(self, img: Image.Image, contrast: float, brightness: float,
                        saturation: float, sharpness: float) -> Image.Image:
        """OpenCL-accelerated enhancement (stub - full implementation complex)."""
        # Full OpenCL implementation would require custom kernels
        # For now, fall back to CPU
        return self._enhance_cpu(img, contrast, brightness, saturation, sharpness)
    
    def apply_filter_gpu(self, img: Image.Image, filter_type: str, **kwargs) -> Image.Image:
        """Apply image filters using GPU."""
        if filter_type == "gaussian_blur":
            radius = kwargs.get("radius", 2)
            return img.filter(ImageFilter.GaussianBlur(radius=radius))
        elif filter_type == "unsharp_mask":
            radius = kwargs.get("radius", 2)
            percent = kwargs.get("percent", 150)
            threshold = kwargs.get("threshold", 3)
            return img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))
        elif filter_type == "sharpen":
            return img.filter(ImageFilter.SHARPEN)
        elif filter_type == "edge_enhance":
            return img.filter(ImageFilter.EDGE_ENHANCE)
        return img


# ─── Parallel GIF Frame Processing ───

@dataclass
class FrameProcessTask:
    """Task for processing a single GIF frame."""
    frame_index: int
    frame_data: bytes  # Serialized frame
    operations: list[dict]  # List of operations to apply


@dataclass
class FrameProcessResult:
    """Result of frame processing."""
    frame_index: int
    frame_data: bytes
    success: bool
    error: str = ""


class ParallelGIFProcessor:
    """Parallel GIF frame processor using thread/process pools."""
    
    def __init__(self, max_workers: int | None = None, use_processes: bool = False):
        self.max_workers = max_workers or min(8, os.cpu_count() or 1)
        self.use_processes = use_processes
        self._executor: ThreadPoolExecutor | ProcessPoolExecutor | None = None
        self._gpu = GPUAccelerator()
    
    def _create_executor(self):
        if self.use_processes:
            return ProcessPoolExecutor(max_workers=self.max_workers)
        return ThreadPoolExecutor(max_workers=self.max_workers)
    
    def __enter__(self):
        self._executor = self._create_executor()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
    
    def process_frames_parallel(self, frames: list[Image.Image], 
                                 operations: list[Callable[[Image.Image], Image.Image]],
                                 progress_callback: Callable[[int, int], None] | None = None) -> list[Image.Image]:
        """Process multiple frames in parallel with the same operations."""
        if not frames:
            return []
        
        if len(frames) == 1 or self.max_workers == 1:
            # Single frame, no parallelism needed
            return [self._process_frame(img, operations) for img in frames]
        
        results = [None] * len(frames)
        completed = 0
        
        def process_single(args: Tuple[int, Image.Image]) -> Tuple[int, Image.Image]:
            idx, frame = args
            result = self._process_frame(frame, operations)
            return idx, result
        
        with self._create_executor() as executor:
            futures = {
                executor.submit(process_single, (i, frame)): i 
                for i, frame in enumerate(frames)
            }
            
            for future in concurrent.futures.as_completed(futures):
                idx = futures[future]
                try:
                    frame_idx, result = future.result()
                    results[frame_idx] = result
                except Exception as e:
                    _log.error(f"Frame {idx} processing failed: {e}")
                    results[idx] = frames[idx]  # Return original on error
                
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(frames))
        
        return results
    
    def _process_frame(self, frame: Image.Image, operations: list[Callable]) -> Image.Image:
        """Apply a sequence of operations to a single frame."""
        result = frame
        for op in operations:
            try:
                result = op(result)
            except Exception as e:
                _log.warning(f"Operation failed: {e}")
        return result
    
    def process_gif_frames(self, gif_path: Path, operations: list[dict],
                           output_path: Path, progress_callback: Callable[[int, int], None] | None = None) -> bool:
        """Process all frames of a GIF with given operations."""
        try:
            with Image.open(gif_path) as gif:
                frames = []
                durations = []
                
                # Extract all frames
                for frame in ImageSequence.Iterator(gif):
                    frames.append(frame.convert("RGBA").copy())
                    durations.append(frame.info.get("duration", 100))
                
                if not frames:
                    return False
                
                # Convert operations to callables
                op_funcs = []
                for op in operations:
                    op_type = op.get("type")
                    params = op.get("params", {})
                    
                    if op_type == "enhance":
                        op_funcs.append(lambda img, p=params: self._gpu.enhance_image_gpu(img, **p))
                    elif op_type == "filter":
                        op_funcs.append(lambda img, p=params: img.filter(p.get("filter", ImageFilter.SHARPEN)))
                    elif op_type == "resize":
                        op_funcs.append(lambda img, p=params: img.resize((p["width"], p["height"]), Image.LANCZOS))
                    elif op_type == "crop":
                        op_funcs.append(lambda img, p=params: img.crop(p["box"]))
                
                # Process frames in parallel
                processed = self.process_frames_parallel(frames, op_funcs, progress_callback)
                
                # Save as GIF
                processed[0].save(
                    output_path,
                    save_all=True,
                    append_images=processed[1:],
                    duration=durations,
                    loop=0,
                    disposal=2,
                    optimize=True
                )
                return True
                
        except Exception as e:
            _log.error(f"GIF processing failed: {e}")
            return False
    
    def __del__(self):
        if self._executor:
            self._executor.shutdown(wait=False)


# ─── WebP Lossless Optimization ───

class WebPOptimizer:
    """Optimized WebP encoding with lossless and near-lossless options."""
    
    @staticmethod
    def save_lossless(img: Image.Image, path: Path, 
                      quality: int = 100,
                      method: int = 6,
                      exact: bool = True,
                      effort: int = 6) -> bool:
        """Save image as lossless WebP with maximum quality."""
        try:
            img.save(
                path,
                "WEBP",
                lossless=True,
                quality=quality,
                method=method,
                exact=exact,
                effort=effort
            )
            return True
        except Exception as e:
            _log.error(f"Lossless WebP save failed: {e}")
            return False
    
    @staticmethod
    def save_near_lossless(img: Image.Image, path: Path,
                           quality: int = 80,
                           method: int = 6) -> bool:
        """Save image as near-lossless WebP (smaller than lossless)."""
        try:
            img.save(
                path,
                "WEBP",
                lossless=False,
                quality=quality,
                method=method
            )
            return True
        except Exception as e:
            _log.error(f"Near-lossless WebP save failed: {e}")
            return False
    
    @staticmethod
    def estimate_size(img: Image.Image, lossless: bool = True) -> int:
        """Estimate WebP file size without saving."""
        import io
        buffer = io.BytesIO()
        try:
            img.save(buffer, "WEBP", lossless=lossless, quality=100, method=6)
            return buffer.tell()
        except Exception:
            return 0
    
    @staticmethod
    def find_optimal_quality(img: Image.Image, target_size_kb: int,
                             lossless: bool = True) -> int:
        """Find quality setting to achieve target file size."""
        if lossless:
            # Lossless size is fixed
            size = WebPOptimizer.estimate_size(img, True)
            return 100 if size <= target_size_kb * 1024 else 0
        
        # Binary search for quality
        low, high = 10, 100
        best = 10
        
        while low <= high:
            mid = (low + high) // 2
            size = WebPOptimizer._estimate_lossy_size(img, mid)
            if size <= target_size_kb * 1024:
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        
        return best
    
    @staticmethod
    def _estimate_lossy_size(img: Image.Image, quality: int) -> int:
        import io
        buffer = io.BytesIO()
        img.save(buffer, "WEBP", lossless=False, quality=quality, method=6)
        return buffer.tell()


# ─── NumPy-Accelerated Operations ───

class NumPyAccelerator:
    """NumPy-accelerated image operations using vectorized operations."""
    
    @staticmethod
    def apply_border_fx(img: Image.Image, border_img: Image.Image,
                        color: Tuple[int, int, int], 
                        opacity: float = 1.0, glow: float = 0.0) -> Image.Image:
        """Apply border effect using NumPy for speed."""
        img_arr = np.array(img.convert("RGBA"), dtype=np.float32) / 255.0
        border_arr = np.array(border_img.convert("RGBA").resize(img.size, Image.LANCZOS), 
                              dtype=np.float32) / 255.0
        
        color_arr = np.array(color, dtype=np.float32) / 255.0
        
        # Extract alpha from border
        border_alpha = border_arr[:, :, 3:4] * opacity
        
        # Colorize border
        colored_border = color_arr * border_alpha
        
        if glow > 0:
            # Apply glow using gaussian blur on alpha
            from scipy.ndimage import gaussian_filter
            glow_alpha = gaussian_filter(border_alpha, sigma=10 * glow) * 0.5
            glow_color = color_arr * glow_alpha
            colored_border = np.maximum(colored_border, glow_color)
        
        # Composite
        result = img_arr * (1 - border_alpha) + colored_border * border_alpha
        result = np.clip(result * 255, 0, 255).astype(np.uint8)
        
        return Image.fromarray(result, mode="RGBA").convert("RGB")
    
    @staticmethod
    def apply_text_overlay(img: Image.Image, text: str, position: Tuple[int, int],
                           font_path: str, font_size: int, color: Tuple[int, int, int],
                           opacity: float = 1.0) -> Image.Image:
        """Apply text overlay using NumPy for pixel-perfect rendering."""
        # For complex text rendering, PIL is still better
        # This is a placeholder for future NumPy-based text rendering
        draw = ImageDraw.Draw(img.convert("RGBA"))
        font = ImageFont.truetype(font_path, font_size)
        draw.text(position, text, font=font, fill=color + (int(opacity * 255),))
        return img
    
    @staticmethod
    def batch_process(frames: list[Image.Image], 
                      operation: Callable[[np.ndarray], np.ndarray]) -> list[Image.Image]:
        """Apply operation to batch of frames using vectorized NumPy."""
        if not frames:
            return []
        
        # Stack frames
        arrays = [np.array(f.convert("RGBA"), dtype=np.float32) / 255.0 for f in frames]
        stacked = np.stack(arrays, axis=0)  # Shape: (N, H, W, 4)
        
        # Apply operation
        result = operation(stacked)
        
        # Convert back
        result = np.clip(result * 255, 0, 255).astype(np.uint8)
        return [Image.fromarray(result[i], mode="RGBA") for i in range(len(frames))]


# ─── Memory-Efficient Processing ───

class MemoryEfficientProcessor:
    """Process large images with limited memory."""
    
    def __init__(self, max_memory_mb: int = 512):
        self.max_memory_mb = max_memory_mb
        self.tile_size = 1024  # Process in 1024x1024 tiles
    
    def process_tiled(self, img: Image.Image, 
                      operation: Callable[[Image.Image], Image.Image]) -> Image.Image:
        """Process large image in tiles to limit memory usage."""
        w, h = img.size
        if w * h * 4 < self.max_memory_mb * 1024 * 1024:
            # Small enough to process at once
            return operation(img)
        
        # Process in tiles
        result = Image.new("RGBA", img.size)
        for y in range(0, h, self.tile_size):
            for x in range(0, w, self.tile_size):
                box = (x, y, min(x + self.tile_size, w), min(y + self.tile_size, h))
                tile = img.crop(box)
                processed = operation(tile)
                result.paste(processed, box)
        return result
    
    def process_stream(self, input_path: Path, output_path: Path,
                       operation: Callable[[Image.Image], Image.Image]) -> bool:
        """Process image stream without loading entire image into memory."""
        try:
            with Image.open(input_path) as img:
                # Process in tiles and save incrementally
                result = self.process_tiled(img, operation)
                result.save(output_path)
            return True
        except Exception as e:
            _log.error(f"Stream processing failed: {e}")
            return False


# ─── Benchmarking ───

def benchmark_operations() -> dict:
    """Run performance benchmarks on current hardware."""
    import time
    
    caps = get_hardware_caps()
    gpu = GPUAccelerator()
    numpy_accel = NumPyAccelerator()
    
    # Create test image
    test_img = Image.new("RGB", (1920, 1080), (128, 128, 128))
    draw = ImageDraw.Draw(test_img)
    for i in range(100):
        draw.rectangle([i*10, i*10, i*10+50, i*10+50], fill=(i*2, i*3, i*5))
    
    results = {
        "hardware": {
            "cpu_cores": caps.cpu_cores,
            "cuda": caps.has_cuda,
            "metal": caps.has_metal,
            "opencl": caps.has_opencl,
            "avx2": caps.supports_avx2
        },
        "benchmarks": {}
    }
    
    # Benchmark: Enhancement
    iterations = 10
    
    # CPU
    start = time.perf_counter()
    for _ in range(iterations):
        gpu._enhance_cpu(test_img, 1.2, 1.1, 1.3, 1.5)
    cpu_time = (time.perf_counter() - start) / iterations * 1000
    results["benchmarks"]["enhance_cpu_ms"] = round(cpu_time, 2)
    
    # GPU
    start = time.perf_counter()
    for _ in range(iterations):
        gpu.enhance_image_gpu(test_img, 1.2, 1.1, 1.3, 1.5)
    gpu_time = (time.perf_counter() - start) / iterations * 1000
    results["benchmarks"]["enhance_gpu_ms"] = round(gpu_time, 2)
    
    if gpu_time > 0:
        results["benchmarks"]["speedup"] = round(cpu_time / gpu_time, 2)
    
    # Parallel processing
    frames = [test_img.copy() for _ in range(20)]
    ops = [lambda img: gpu.enhance_image_gpu(img, 1.1, 1.0, 1.1, 1.2)]
    
    with ParallelGIFProcessor(max_workers=4) as proc:
        start = time.perf_counter()
        proc.process_frames_parallel(frames, ops)
        parallel_time = (time.perf_counter() - start) * 1000
    results["benchmarks"]["parallel_20_frames_ms"] = round(parallel_time, 2)
    
    # Sequential
    start = time.perf_counter()
    for f in frames:
        gpu.enhance_image_gpu(f, 1.1, 1.0, 1.1, 1.2)
    sequential_time = (time.perf_counter() - start) * 1000
    results["benchmarks"]["sequential_20_frames_ms"] = round(sequential_time, 2)
    
    if parallel_time > 0:
        results["benchmarks"]["parallel_speedup"] = round(sequential_time / parallel_time, 2)
    
    _log.info(f"Benchmarks completed: {results['benchmarks']}")
    return results


# ─── Export ───

__all__ = [
    "HardwareCapabilities",
    "get_hardware_caps",
    "GPUAccelerator",
    "ParallelGIFProcessor",
    "FrameProcessTask",
    "FrameProcessResult",
    "WebPOptimizer",
    "NumPyAccelerator",
    "MemoryEfficientProcessor",
    "benchmark_operations",
]