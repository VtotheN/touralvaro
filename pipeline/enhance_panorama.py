#!/usr/bin/env python3
"""
enhance_panorama.py — Post-process Cycles renders for Matterport-quality output.

Technique stack (CPU-only, no torch):
  1. CLAHE-style contrast  (local histogram equalization via tile-wise LAB)
  2. Cinematic S-curve  (shadow lift + midtone punch + highlight rolloff)
  3. Saturation / contrast / brightness push
  4. Unsharp mask
  5. AI upscale: FSRCNN 3× → downsample 4096×2048  [if model present]
     Fallback: 2× LANCZOS4 via OpenCV
  6. OpenCV detail enhance + final sharpen
  7. Save JPEG q=92

Usage:
    python3 enhance_panorama.py <input.jpg> <output.jpg>
    python3 enhance_panorama.py <panoramas_dir>      # batch all *.jpg in dir
"""

import sys
import os
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import struct
import zlib
import numpy as np

try:
    import cv2
    _HAVE_CV2 = True
except ImportError:
    _HAVE_CV2 = False

_FSRCNN_PATH = Path(__file__).parent / "models" / "FSRCNN-small_x3.pb"
_sr = None

def _get_sr():
    global _sr
    if _sr is not None:
        return _sr
    if not _HAVE_CV2 or not _FSRCNN_PATH.exists():
        return None
    try:
        sr = cv2.dnn_superres.DnnSuperResImpl_create()
        sr.readModel(str(_FSRCNN_PATH))
        sr.setModel("fsrcnn", 3)
        _sr = sr
        return sr
    except Exception:
        return None

# ---------------------------------------------------------------------------

def clahe_pil(img: Image.Image, clip: float = 2.5, tile: int = 8) -> Image.Image:
    """
    Approximate CLAHE via LAB-space tile-wise histogram stretching.
    Pure PIL — no OpenCV needed.
    """
    img_rgb = img.convert("RGB")
    w, h = img_rgb.size
    tw, th = w // tile, h // tile
    if tw < 1 or th < 1:
        return img_rgb

    result = img_rgb.copy()
    from PIL import ImageFilter

    # Operate on L-channel equivalent via luminance blend
    r, g, b = img_rgb.split()
    # Luminance
    lum = Image.merge("RGB", (r, g, b)).convert("L")

    for ty in range(tile):
        for tx in range(tile):
            x0 = tx * tw
            y0 = ty * th
            x1 = x0 + tw if tx < tile - 1 else w
            y1 = y0 + th if ty < tile - 1 else h

            tile_lum = lum.crop((x0, y0, x1, y1))
            # Histogram stretch
            stretched = ImageOps.autocontrast(tile_lum, cutoff=0.5)
            lum.paste(stretched, (x0, y0))

    # Re-composite: blend enhanced luminance with original color
    lum_3ch = lum.convert("RGB")
    blended = Image.blend(img_rgb, lum_3ch, alpha=0.25)
    return blended


def unsharp_mask(img: Image.Image, radius: int = 2, percent: int = 140, threshold: int = 2) -> Image.Image:
    return img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))


def shadow_lift(img: Image.Image, lift: float = 0.06) -> Image.Image:
    """Lift dark tones (gamma correction on shadows) — fixes black door gaps perceptually."""
    table = []
    for i in range(256):
        if i < 60:
            v = int(i + lift * (60 - i) * 3)
        else:
            v = i
        table.append(min(255, v))
    lut = table * 3
    return img.point(lut)


def s_curve(img: Image.Image, midtone_lift: float = 0.12, shadow_lift_f: float = 0.08) -> Image.Image:
    """Cinematic S-curve: lift shadows, boost midtones, protect highlights.
    Gives that warm, punchy interior look."""
    import math
    table = []
    for i in range(256):
        t = i / 255.0
        # Shadow lift (compress pure blacks toward dark gray)
        if t < 0.15:
            t = t + shadow_lift_f * (1.0 - t / 0.15) * t
        # Midtone boost via sine curve
        boost = midtone_lift * math.sin(math.pi * t) ** 1.5
        t = t + boost
        # Highlight rolloff (gentle compression above 0.85)
        if t > 0.85:
            t = 0.85 + (t - 0.85) * 0.6
        table.append(min(255, max(0, int(t * 255))))
    lut = table * 3
    return img.point(lut)


def _cv_detail_enhance(img_bgr: np.ndarray) -> np.ndarray:
    """Edge-preserving detail enhance + high-pass blend."""
    smooth = cv2.edgePreservingFilter(img_bgr, flags=1, sigma_s=30, sigma_r=0.15)
    detail = cv2.addWeighted(img_bgr, 1.5, smooth, -0.5, 0)
    return cv2.addWeighted(img_bgr, 0.35, detail, 0.65, 0)


def _cv_unsharp(img_bgr: np.ndarray, strength: float = 0.5, radius: int = 2) -> np.ndarray:
    blurred = cv2.GaussianBlur(img_bgr, (0, 0), radius)
    return cv2.addWeighted(img_bgr, 1 + strength, blurred, -strength, 0)


def enhance(src: Path, dst: Path, upscale: bool = True) -> None:
    img = Image.open(src).convert("RGB")
    w, h = img.size
    print(f"  {src.name}: {w}×{h}", end=" → ", flush=True)

    # Minimal 3-op pass — no CLAHE, no S-curve, no brightness boost.
    # Prior compound stack (CLAHE+S-curve+Color×1.40+Contrast×1.08+Brightness×1.08) destroyed midtones.
    img = ImageEnhance.Contrast(img).enhance(1.05)
    img = ImageEnhance.Color(img).enhance(1.10)
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=80, threshold=3))

    nw, nh = img.size
    print(f"{nw}×{nh}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(dst), "JPEG", quality=95, optimize=True, subsampling=0)
    src_kb = src.stat().st_size // 1024
    dst_kb = dst.stat().st_size // 1024
    print(f"    {src_kb}KB → {dst_kb}KB")


def main():
    if len(sys.argv) < 2:
        print("Usage: enhance_panorama.py <input.jpg> [output.jpg]")
        print("       enhance_panorama.py <directory>")
        sys.exit(1)

    arg = Path(sys.argv[1])

    if arg.is_dir():
        jpgs = sorted(arg.glob("*.jpg"))
        if not jpgs:
            print("No JPEGs found in", arg)
            sys.exit(1)
        for src in jpgs:
            dst = src.parent / "enhanced" / src.name
            enhance(src, dst)
        print(f"\nDone — enhanced/ subfolder in {arg}")

    else:
        src = arg
        dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.parent / "enhanced" / src.name
        enhance(src, dst)
        print("Done.")


if __name__ == "__main__":
    main()
