#!/usr/bin/env python3
"""
download_pbr.py — Download CC0 PBR textures from Polyhaven for touralvaro Phase 1.
Usage: python3 pipeline/download_pbr.py [--dir pbr_textures] [--res 2k]
"""
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path(__file__).parent.parent / "pbr_textures"
RES = "2k"

# Polyhaven direct download URL pattern
# https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/{id}/{id}_{map}_{res}.jpg
PH_BASE = "https://dl.polyhaven.org/file/ph-assets/Textures"

TEXTURE_SETS = {
    "volcanic_herringbone_01": {
        "desc": "travertine/stone floor+walls",
        "maps": ["diff", "nor_gl", "rough", "ao"],
        "ext": "jpg",
        "blender_name": "travertine",
    },
    "white_plaster_rough_01": {
        "desc": "white plaster walls",
        "maps": ["diff", "nor_gl", "rough", "ao"],
        "ext": "jpg",
        "blender_name": "stucco_warm",
    },
    "rough_linen": {
        "desc": "linen fabric (sofa/cushions)",
        "maps": ["diff", "nor_gl", "rough"],
        "ext": "jpg",
        "blender_name": "linen_white",
    },
    "blue_floor_tiles_01": {
        "desc": "ceramic tiles (bathroom)",
        "maps": ["diff", "nor_gl", "rough", "ao"],
        "ext": "jpg",
        "blender_name": "ceramic_white",
    },
    "oak_veneer_01": {
        "desc": "oak wood veneer",
        "maps": ["diff", "nor_gl", "rough", "ao"],
        "ext": "jpg",
        "blender_name": "wood_oak",
    },
    "marble_01": {
        "desc": "marble (countertops/surfaces)",
        "maps": ["diff", "nor_gl", "rough"],
        "ext": "jpg",
        "blender_name": "marble",
    },
    "concrete_wall_005": {
        "desc": "concrete wall",
        "maps": ["diff", "nor_gl", "rough", "ao"],
        "ext": "jpg",
        "blender_name": "concrete",
    },
    "dark_wood": {
        "desc": "dark wood planks (walnut)",
        "maps": ["diff", "nor_gl", "rough", "ao"],
        "ext": "jpg",
        "blender_name": "walnut",
    },
    "stone_wall_05": {
        "desc": "rough stone (outdoor/terraza)",
        "maps": ["diff", "nor_gl", "rough", "ao"],
        "ext": "jpg",
        "blender_name": "outdoor_stone",
    },
    "bi_stretch": {
        "desc": "wicker/rattan",
        "maps": ["diff", "nor_gl", "rough"],
        "ext": "jpg",
        "blender_name": "rattan",
    },
}

def ph_url(asset_id: str, map_type: str, res: str, ext: str) -> str:
    return f"{PH_BASE}/{ext}/{res}/{asset_id}/{asset_id}_{map_type}_{res}.{ext}"

def download_file(url: str, dst: Path) -> tuple[str, bool, str]:
    if dst.exists() and dst.stat().st_size > 10_000:
        return str(dst.name), True, "cached"
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "touralvaro-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r, open(dst, "wb") as f:
            f.write(r.read())
        return str(dst.name), True, f"{dst.stat().st_size // 1024}KB"
    except urllib.error.HTTPError as e:
        return str(dst.name), False, f"HTTP {e.code}"
    except Exception as e:
        return str(dst.name), False, str(e)[:60]

def build_download_list(base_dir: Path, res: str):
    jobs = []
    for asset_id, info in TEXTURE_SETS.items():
        out_dir = base_dir / asset_id
        for m in info["maps"]:
            url = ph_url(asset_id, m, res, info["ext"])
            dst = out_dir / f"{m}.{info['ext']}"
            jobs.append((url, dst, asset_id, m))
    return jobs

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(BASE_DIR))
    ap.add_argument("--res", default=RES)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    base_dir = Path(args.dir)
    jobs = build_download_list(base_dir, args.res)
    total = len(jobs)
    print(f"Downloading {total} texture maps ({args.res}) → {base_dir}")
    print(f"Using {args.workers} parallel workers\n")

    ok = 0
    fail = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download_file, url, dst): (asset_id, m)
                   for url, dst, asset_id, m in jobs}
        for fut in as_completed(futures):
            asset_id, m = futures[fut]
            name, success, msg = fut.result()
            status = "✓" if success else "✗"
            print(f"  {status} {asset_id}/{m}: {msg}")
            if success:
                ok += 1
            else:
                fail += 1

    print(f"\n{ok}/{total} downloaded, {fail} failed")
    if fail > 0:
        print("NOTE: Failed textures will fall back to procedural in Blender.")

    # Write manifest mapping blender_name → asset_id
    manifest_path = base_dir / "manifest.json"
    import json
    manifest = {info["blender_name"]: asset_id for asset_id, info in TEXTURE_SETS.items()}
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest → {manifest_path}")

if __name__ == "__main__":
    main()
