# DEPRECATED 2026-06-10 — unused dead code, replaced by gen_panorama.py + enhance_panorama.py + post_render.sh
#!/usr/bin/env python3
"""
neural_panorama.py — THE IMPOSSIBLE PIECE.

Takes Blender Cycles renders (correct geometry, rough lighting) and runs
AI img2img to produce photorealistic 360° panoramas via Replicate API.

No GPU needed. ~30–60 sec/image via cloud API.

Requirements:
    pip install replicate pillow

Setup:
    export REPLICATE_API_TOKEN=<your_token>   # get at replicate.com

Supported models (set MODEL env var or use default):
    - stability-ai/stable-diffusion-img2img (default, fast)
    - adirik/interior-design (fine-tuned interior photorealism)
    - jagilley/controlnet-scribble (structure-guided generation)

Usage:
    python3 neural_panorama.py <input_dir> [output_dir]
    python3 neural_panorama.py <input.jpg> [output.jpg]

    # All rooms in a scene:
    python3 neural_panorama.py viewer/public/panoramas/cayena-depa1/

    # Single room:
    python3 neural_panorama.py viewer/public/panoramas/cayena-depa1/loft_sala.jpg neural_loft_sala.jpg
"""

import os
import sys
import json
import base64
import time
from pathlib import Path
from PIL import Image
from io import BytesIO
import urllib.request
import urllib.error

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")

# Room-specific prompts for photorealistic Caribbean apartment
ROOM_PROMPTS = {
    "loft_sala":   "luxury Caribbean open-plan living room kitchen dining, warm tropical sunlight, white walls, concrete countertops, natural rattan furniture, indoor tropical plants, wood floor, photorealistic interior photography, ultra sharp, 8k",
    "loft_master": "luxury Caribbean bedroom, white linen bedding, warm tropical sunlight through window, wood floor, minimalist modern design, photorealistic interior photography, ultra sharp, 8k",
    "loft_bano":   "luxury Caribbean bathroom, white marble, warm lighting, tropical plants, clean minimalist design, photorealistic interior photography, ultra sharp, 8k",
    "terraza":     "luxury Caribbean terrace rooftop, tropical garden, pool visible, palm trees, blue sky, warm sunlight, outdoor furniture, photorealistic photography, ultra sharp, 8k",
    "loft_mez_master": "luxury mezzanine bedroom Caribbean loft, high ceilings, tropical sunlight, white walls, modern furniture, photorealistic interior photography, ultra sharp, 8k",
    "loft_mez_bano":   "luxury mezzanine bathroom Caribbean loft, white walls, warm lighting, photorealistic interior photography, ultra sharp, 8k",
}
DEFAULT_PROMPT = "luxury Caribbean apartment interior, warm tropical sunlight, white walls, natural materials, photorealistic interior photography, ultra sharp, 8k"
NEGATIVE_PROMPT = "blurry, cartoon, 3d render, cgi, low quality, dark, ugly, deformed, shadows too dark, overexposed, flat"

# Replicate model — adirik/interior-design is best for this use case
MODEL = os.environ.get("NEURAL_MODEL", "adirik/interior-design:76604baddc85b1b4616e1c6475eca080da339c8875bd4996705440484a6eac38")


def img_to_b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def b64_to_img(b64: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(b64)))


def download_image(url: str) -> Image.Image:
    req = urllib.request.Request(url, headers={"User-Agent": "touralvaro/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return Image.open(BytesIO(resp.read()))


def replicate_prediction(model: str, input_data: dict) -> dict:
    token = REPLICATE_API_TOKEN
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN not set. Run: export REPLICATE_API_TOKEN=<token>")

    # Create prediction
    payload = json.dumps({"version": model.split(":")[-1], "input": input_data}).encode()
    req = urllib.request.Request(
        "https://api.replicate.com/v1/predictions",
        data=payload,
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Replicate API error {e.code}: {e.read().decode()}")

    pred_id = result["id"]
    poll_url = f"https://api.replicate.com/v1/predictions/{pred_id}"

    # Poll until done
    print(f"    Prediction {pred_id} started...", end="", flush=True)
    for _ in range(120):
        time.sleep(3)
        req2 = urllib.request.Request(
            poll_url,
            headers={"Authorization": f"Token {token}"},
        )
        with urllib.request.urlopen(req2, timeout=20) as resp:
            status = json.loads(resp.read())
        state = status.get("status")
        if state == "succeeded":
            print(" done.")
            return status["output"]
        elif state in ("failed", "canceled"):
            raise RuntimeError(f"Prediction {state}: {status.get('error')}")
        print(".", end="", flush=True)

    raise RuntimeError("Prediction timed out after 6 minutes")


def enhance_room(src: Path, dst: Path, room_id: str) -> None:
    print(f"  {room_id}: {src.name}", end=" ")

    # Build input image data URI for Replicate
    data_uri = f"data:image/jpeg;base64,{img_to_b64(src)}"

    prompt = ROOM_PROMPTS.get(room_id, DEFAULT_PROMPT)

    # adirik/interior-design takes image + prompt
    try:
        output_urls = replicate_prediction(MODEL, {
            "image":           data_uri,
            "prompt":          prompt,
            "negative_prompt": NEGATIVE_PROMPT,
            "num_inference_steps": 50,
            "guidance_scale":  7.5,
            "strength":        0.65,   # 0.65 = strong AI improvement while preserving layout
        })
    except RuntimeError as e:
        print(f"\n    SKIP (API error): {e}")
        return

    # Download result
    if isinstance(output_urls, list):
        output_url = output_urls[0]
    else:
        output_url = output_urls

    result_img = download_image(output_url)

    # Upscale back to equirectangular 4096×2048 (AI output is smaller)
    orig = Image.open(src)
    result_img = result_img.resize(orig.size, Image.LANCZOS)

    dst.parent.mkdir(parents=True, exist_ok=True)
    result_img.save(str(dst), "JPEG", quality=92, optimize=True, subsampling=0)
    print(f"→ {dst.name} ({result_img.size[0]}×{result_img.size[1]})")


def main():
    if not REPLICATE_API_TOKEN:
        print("ERROR: REPLICATE_API_TOKEN not set.")
        print("  1. Sign up at https://replicate.com")
        print("  2. Get token at https://replicate.com/account/api-tokens")
        print("  3. export REPLICATE_API_TOKEN=<your_token>")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: neural_panorama.py <dir_or_file> [output_dir_or_file]")
        sys.exit(1)

    arg = Path(sys.argv[1])

    if arg.is_dir():
        out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else arg / "neural"
        jpgs = sorted(arg.glob("*.jpg"))
        if not jpgs:
            print("No JPEGs found in", arg); sys.exit(1)
        for src in jpgs:
            room_id = src.stem
            dst = out_dir / src.name
            enhance_room(src, dst, room_id)
        print(f"\nDone — neural/ subfolder in {arg}")
    else:
        src = arg
        dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.parent / "neural" / src.name
        room_id = src.stem
        enhance_room(src, dst, room_id)
        print("Done.")


if __name__ == "__main__":
    main()
