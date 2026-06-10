#!/usr/bin/env python3
"""
realesrgan_upscale.py — Real-ESRGAN 4× upscale for panorama post-processing.

Downloads realesrgan-ncnn-vulkan binary (~100MB) on first run.
No PyTorch required. Uses Vulkan (MoltenVK on macOS Apple Silicon).

Usage:
    python3 pipeline/realesrgan_upscale.py <input.jpg> [output.jpg]
    python3 pipeline/realesrgan_upscale.py <directory>   # batch all *.jpg
    python3 pipeline/realesrgan_upscale.py --check       # verify install
"""

import os
import sys
import subprocess
import zipfile
import urllib.request
import shutil
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Binary management
# ──────────────────────────────────────────────────────────────────────────────

_TOOL_DIR  = Path(__file__).parent / "_realesrgan"
_BINARY    = _TOOL_DIR / "realesrgan-ncnn-vulkan"
_MODELS_OK = _TOOL_DIR / ".models_ok"

# GitHub release for macOS (Apple Silicon + x86 universal, MoltenVK included)
_RELEASE_URL = (
    "https://github.com/xinntao/Real-ESRGAN/releases/download/"
    "v0.2.5.0/realesrgan-ncnn-vulkan-20220424-macos.zip"
)
_ZIP_NAME = "realesrgan-ncnn-vulkan-20220424-macos.zip"


def _download_binary():
    _TOOL_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = _TOOL_DIR / _ZIP_NAME

    if not zip_path.exists():
        print(f"Downloading Real-ESRGAN binary (~60MB) …", flush=True)
        req = urllib.request.Request(
            _RELEASE_URL,
            headers={"User-Agent": "touralvaro-pipeline/1.0"},
        )

        def _reporthook(count, block, total):
            pct = min(100, count * block * 100 // total) if total > 0 else 0
            print(f"\r  {pct}% ", end="", flush=True)

        urllib.request.urlretrieve(_RELEASE_URL, zip_path, _reporthook)
        print()

    print("Extracting…", flush=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(_TOOL_DIR)

    # Find extracted binary (may be in a subdirectory)
    candidates = list(_TOOL_DIR.rglob("realesrgan-ncnn-vulkan"))
    if not candidates:
        raise RuntimeError("Binary not found after extraction")
    binary = candidates[0]
    if binary != _BINARY:
        shutil.copy2(binary, _BINARY)
    _BINARY.chmod(0o755)
    _models_ok_check()
    _MODELS_OK.touch()
    print(f"Real-ESRGAN ready at {_BINARY}")


def _models_ok_check():
    # Verify at least one model file exists
    models = list(_TOOL_DIR.rglob("*.bin"))
    if not models:
        raise RuntimeError(f"No .bin model files found in {_TOOL_DIR}")


def ensure_binary():
    if _BINARY.exists() and list(_TOOL_DIR.rglob(f"{_MODEL}.bin")):
        return
    _download_binary()


# ──────────────────────────────────────────────────────────────────────────────
# Upscale
# ──────────────────────────────────────────────────────────────────────────────

# Model choices: realesrgan-x4plus (best quality, ~60MB) or realesrgan-x4plus-anime
_MODEL = "realesrgan-x4plus"


def upscale(src: Path, dst: Path, final_w: int = 4096, final_h: int = 2048) -> Path:
    """
    4× Real-ESRGAN upscale. Input 1024×512 → output exactly 4096×2048 (no downsample).
    If input is larger (e.g. 2048×1024), Lanczos-downsamples after upscale.
    Returns dst path.
    """
    ensure_binary()

    # Find model dir (contains .bin and .param files)
    candidates = list(_TOOL_DIR.rglob(f"{_MODEL}.bin"))
    if not candidates:
        raise RuntimeError(f"Model {_MODEL}.bin not found in {_TOOL_DIR}")
    model_dir = candidates[0].parent

    # ESRGAN writes to a temp path, then we resize
    tmp_4x = dst.parent / f"_esrgan_{dst.stem}.png"
    dst.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(_BINARY),
        "-i", str(src),
        "-o", str(tmp_4x),
        "-n", _MODEL,
        "-s", "4",
        "-t", "512",           # tile size (fits M-series VRAM)
        "-m", str(model_dir),
    ]
    print(f"  ESRGAN: {src.name} → {tmp_4x.name}", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ESRGAN stderr: {result.stderr[:300]}")
        raise RuntimeError(f"realesrgan failed: {result.returncode}")

    # Downsample back to target resolution with Lanczos
    try:
        from PIL import Image
        img = Image.open(tmp_4x)
        if img.size != (final_w, final_h):
            img = img.resize((final_w, final_h), Image.LANCZOS)
        img.save(str(dst), "JPEG", quality=95, optimize=True, subsampling=0)
        tmp_4x.unlink(missing_ok=True)
        print(f"  → {dst.name} ({final_w}×{final_h})", flush=True)
    except ImportError:
        # PIL not available, keep 8K output as-is
        tmp_4x.rename(dst)
        print(f"  → {dst.name} (8K, PIL not available for downsample)")

    return dst


def upscale_dir(src_dir: Path, out_dir: Path | None = None):
    jpgs = sorted(src_dir.glob("*.jpg"))
    if not jpgs:
        print(f"No JPEGs in {src_dir}")
        return
    if out_dir is None:
        out_dir = src_dir / "esrgan"
    out_dir.mkdir(parents=True, exist_ok=True)
    for src in jpgs:
        dst = out_dir / src.name
        upscale(src, dst)
    print(f"\nDone → {out_dir}")


# ──────────────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--check":
        ensure_binary()
        print("OK")
        return

    src = Path(sys.argv[1])
    if src.is_dir():
        out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
        upscale_dir(src, out)
    else:
        dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.parent / "esrgan" / src.name
        upscale(src, dst)


if __name__ == "__main__":
    main()
