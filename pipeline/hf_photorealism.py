#!/usr/bin/env python3
"""
hf_photorealism.py — FREE AI photorealism via HuggingFace Inference API.

ASSUMPTION BROKEN: "AI photorealism requires paid API (Replicate)."
REALITY: HuggingFace Inference API is FREE (rate-limited, no token needed for many models).
         With token (free account at huggingface.co): higher rate limits.

Pipeline:
  1. Load enhanced Cycles render (4096×2048)
  2. Downscale to 1024×512 for API (faster, within limits)
  3. Send to HF img2img endpoint (interior design model)
  4. Upscale result back to 4096×2048 with LANCZOS
  5. Blend with original (preserve room layout)
  6. Save to hf_neural/ subfolder

Usage:
    python3 hf_photorealism.py <panoramas_dir>
    python3 hf_photorealism.py <panoramas_dir> --token hf_xxxx

Models tried (in order of quality):
    1. Salesforce/blip-diffusion (free, no token)
    2. stabilityai/stable-diffusion-xl-refiner-1.0 (better quality, free tier)
    3. lllyasviel/sd-controlnet-canny (edge-guided, preserves room layout)
"""

import sys
import os
import time
import json
import base64
import urllib.request
import urllib.error
from io import BytesIO
from pathlib import Path
from PIL import Image

HF_API = "https://api-inference.huggingface.co"

ROOM_PROMPTS = {
    "loft_master":    "luxury Caribbean master bedroom, warm afternoon light, white linen bedding, rattan furniture, high quality photography, architectural digest",
    "loft_sala":      "luxury Caribbean open plan living room kitchen, warm sunlight through large windows, rattan chairs, dark stone countertops, architectural digest",
    "loft_bano":      "luxury Caribbean bathroom, travertine stone, chrome fixtures, warm ambient lighting, spa-like, architectural photography",
    "loft_bano_g":    "luxury Caribbean bathroom, travertine stone, chrome fixtures, warm ambient lighting, spa-like, architectural photography",
    "loft_mez_master":"luxury Caribbean loft bedroom on mezzanine, dramatic ceiling height, warm afternoon light, walnut wood floor",
    "loft_mez_bano":  "luxury Caribbean bathroom on mezzanine, clean minimal design, warm lighting, spa quality",
    "terraza":        "luxury Caribbean rooftop terrace, tropical garden, rattan loungers, blue sky, ocean breeze, architectural photography",
    "_default":       "luxury Caribbean interior, warm natural light, high-end furniture, architectural digest quality photography",
}

def room_prompt(stem: str) -> str:
    for k, v in ROOM_PROMPTS.items():
        if k in stem:
            return v
    return ROOM_PROMPTS["_default"]

def img_to_b64(img: Image.Image, fmt="JPEG") -> str:
    buf = BytesIO()
    img.save(buf, format=fmt, quality=90)
    return base64.b64encode(buf.getvalue()).decode()

def b64_to_img(data: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(data)))

def hf_img2img(img: Image.Image, prompt: str, strength: float = 0.55,
               token: str = None) -> Image.Image | None:
    """
    Call HuggingFace img2img inference endpoint.
    Falls back through models until one works.
    """
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Resize to API-friendly size
    w, h = img.size
    api_img = img.resize((1024, 512), Image.LANCZOS)

    payload = json.dumps({
        "inputs": img_to_b64(api_img),
        "parameters": {
            "prompt": prompt + ", photorealistic, 8k, sharp focus",
            "negative_prompt": "blurry, low quality, cartoon, cgi, 3d render, noisy",
            "strength": strength,
            "guidance_scale": 7.5,
            "num_inference_steps": 30,
        }
    }).encode()

    # Try models in order
    models = [
        "lllyasviel/sd-controlnet-depth",
        "runwayml/stable-diffusion-v1-5",
        "stabilityai/stable-diffusion-2-1",
    ]

    for model in models:
        url = f"{HF_API}/models/{model}"
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            print(f"    Trying {model}...", end=" ", flush=True)
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read()
                # HF returns raw image bytes (not JSON) for image models
                result_img = Image.open(BytesIO(body)).convert("RGB")
                # Upscale back to original size
                result_img = result_img.resize((w, h), Image.LANCZOS)
                print("OK")
                return result_img
        except urllib.error.HTTPError as e:
            if e.code == 503:
                body = e.read().decode()
                if "loading" in body.lower() or "estimated_time" in body.lower():
                    try:
                        info = json.loads(body)
                        wait = min(info.get("estimated_time", 20), 30)
                        print(f"loading, wait {wait:.0f}s...", end=" ", flush=True)
                        time.sleep(wait)
                        # Retry once
                        req2 = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                        with urllib.request.urlopen(req2, timeout=120) as resp2:
                            result_img = Image.open(BytesIO(resp2.read())).convert("RGB")
                            result_img = result_img.resize((w, h), Image.LANCZOS)
                            print("OK")
                            return result_img
                    except Exception:
                        pass
                print(f"503 {e.read()[:60] if hasattr(e,'read') else ''}")
            elif e.code == 429:
                print("rate-limited, skip")
            else:
                print(f"HTTP {e.code}")
        except Exception as ex:
            print(f"error: {ex}")

    return None


def blend_ai_original(ai: Image.Image, orig: Image.Image,
                       alpha: float = 0.75) -> Image.Image:
    """Blend AI result with original to preserve room structure."""
    if ai.size != orig.size:
        ai = ai.resize(orig.size, Image.LANCZOS)
    return Image.blend(orig, ai, alpha=alpha)


def process_dir(src_dir: Path, token: str = None) -> None:
    out_dir = src_dir / "hf_neural"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Prefer enhanced/ subfolder as input if it exists
    input_dir = src_dir / "enhanced" if (src_dir / "enhanced").exists() else src_dir
    jpgs = sorted(input_dir.glob("*.jpg"))
    if not jpgs:
        print(f"No JPEGs in {input_dir}")
        return

    print(f"HF neural pass: {len(jpgs)} rooms → {out_dir}")
    for src in jpgs:
        dst = out_dir / src.name
        if dst.exists():
            print(f"  {src.name}: skip (exists)")
            continue

        print(f"  {src.name}:")
        img = Image.open(src).convert("RGB")
        prompt = room_prompt(src.stem)
        print(f"    prompt: {prompt[:60]}...")

        ai_img = hf_img2img(img, prompt, strength=0.55, token=token)
        if ai_img:
            # Blend AI result (75%) with original (25%) — keeps layout
            final = blend_ai_original(ai_img, img, alpha=0.75)
        else:
            print(f"    AI failed, using enhanced only")
            final = img

        final.save(str(dst), "JPEG", quality=92, optimize=True, subsampling=0)
        sz = dst.stat().st_size // 1024
        print(f"    → {sz}KB")
        time.sleep(2)  # be nice to free tier

    print(f"\nDone → {out_dir}")


def main():
    token = None
    args = sys.argv[1:]

    if "--token" in args:
        idx = args.index("--token")
        token = args[idx + 1]
        args = [a for i, a in enumerate(args) if i not in (idx, idx + 1)]

    if not args:
        print("Usage: hf_photorealism.py <panoramas_dir> [--token hf_xxx]")
        sys.exit(1)

    process_dir(Path(args[0]), token=token)


if __name__ == "__main__":
    main()
