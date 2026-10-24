"""
Prepares the local ManimGL engine (../manimlib) before anything renders.

Must run before the first Scene is created, which is why `animai/__init__.py`
calls `bootstrap()` before importing manimlib.
"""
from __future__ import annotations

import os
import sys

_bootstrapped = False


def bootstrap() -> None:
    global _bootstrapped
    if _bootstrapped:
        return
    _bootstrapped = True
    _select_gpu_backend()


def _select_gpu_backend() -> None:
    # wgpu-native crashes on some Windows machines (seen on hybrid AMD + NVIDIA laptops)
    # when it initializes every graphics backend at once. Any single backend works, so
    # pick one up front. ANIMAI_GPU_BACKEND=auto leaves wgpu's default behavior.
    default = "Vulkan" if sys.platform == "win32" else "auto"
    backend = os.environ.get("ANIMAI_GPU_BACKEND", default)
    if backend.lower() == "auto":
        return
    try:
        from wgpu.backends.wgpu_native.extras import set_instance_extras
        set_instance_extras(backends=[backend])
    except (ImportError, RuntimeError):
        # Older wgpu without extras, or the instance already exists: nothing to do
        pass
