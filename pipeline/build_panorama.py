# DEPRECATED 2026-06-10 — unused dead code, replaced by gen_panorama.py + enhance_panorama.py + post_render.sh
#!/usr/bin/env python3
"""Full panoramic tour build pipeline.
Usage: python3 pipeline/build_panorama.py <project_dir>

Example: python3 pipeline/build_panorama.py test_projects/cayena-depa1/

Outputs (all relative to repo root):
  viewer/public/models/{scene_id}.glb
  viewer/public/waypoints/{scene_id}.json
  viewer/public/panoramas/{scene_id}/{room_id}.jpg
  viewer/public/panoramas/{scene_id}/tour.json
"""
import subprocess, sys, os, json, shutil, pathlib, time, socket

ROOT    = pathlib.Path(__file__).parent.parent
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"


def run(cmd, **kw):
    print(f"$ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        print(f"ERROR: exit {r.returncode}")
        sys.exit(r.returncode)
    return r


def viewer_running(port=5174):
    try:
        s = socket.create_connection(("localhost", port), timeout=1)
        s.close()
        return True
    except Exception:
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)

    project_dir = pathlib.Path(sys.argv[1]).resolve()
    cfg_path    = project_dir / "config.json"
    if not cfg_path.exists():
        print(f"ERROR: {cfg_path} not found"); sys.exit(1)

    with open(cfg_path) as f:
        cfg = json.load(f)

    scene_id = cfg.get("id", project_dir.name)
    t_start  = time.time()

    print(f"\n{'='*60}")
    print(f"Building panoramic tour: {scene_id}")
    print(f"Project dir:             {project_dir}")
    print(f"{'='*60}\n")

    # ── Output dirs ───────────────────────────────────────────────────────────
    models_dir    = ROOT / "viewer" / "public" / "models"
    waypoints_dir = ROOT / "viewer" / "public" / "waypoints"
    pano_dir      = ROOT / "viewer" / "public" / "panoramas" / scene_id

    models_dir.mkdir(parents=True, exist_ok=True)
    waypoints_dir.mkdir(parents=True, exist_ok=True)
    pano_dir.mkdir(parents=True, exist_ok=True)

    glb_out  = models_dir    / f"{scene_id}.glb"
    wp_out   = waypoints_dir / f"{scene_id}.json"
    tour_out = pano_dir      / "tour.json"

    # ── Step 1: GLB via Blender ───────────────────────────────────────────────
    t0 = time.time()
    print("[1/4] Generating 3D model (Blender → GLB)...")
    run([BLENDER, "--background", "--python",
         str(ROOT / "pipeline" / "gen_apartment.py"),
         "--", str(cfg_path), str(glb_out)])
    print(f"      GLB: {glb_out}  ({glb_out.stat().st_size // 1024} KB) [{time.time()-t0:.1f}s]\n")

    # ── Step 2: Waypoints ─────────────────────────────────────────────────────
    t0 = time.time()
    print("[2/4] Generating waypoints...")
    run(["python3", str(ROOT / "pipeline" / "gen_waypoints.py"),
         str(cfg_path), str(wp_out)])
    print(f"      WP:  {wp_out}  [{time.time()-t0:.1f}s]\n")

    # ── Step 3: Panoramas via Blender ─────────────────────────────────────────
    t0 = time.time()
    print("[3/4] Rendering equirectangular panoramas (Blender + Cycles)...")
    run([BLENDER, "--background", "--python",
         str(ROOT / "pipeline" / "gen_panorama.py"),
         "--", str(cfg_path), str(pano_dir)])
    # Collect rendered files
    rendered = sorted(pano_dir.glob("*.jpg"))
    kb_total = sum(f.stat().st_size for f in rendered) // 1024
    print(f"      Panoramas rendered: {len(rendered)} files, {kb_total} KB total [{time.time()-t0:.1f}s]")
    for r in rendered:
        print(f"        {r.name}  ({r.stat().st_size // 1024} KB)")
    print()

    # ── Step 4: tour.json ─────────────────────────────────────────────────────
    t0 = time.time()
    print("[4/4] Generating tour.json...")
    run(["python3", str(ROOT / "pipeline" / "gen_tour_json.py"),
         str(cfg_path), scene_id, str(tour_out)])
    print(f"      tour.json: {tour_out}  [{time.time()-t0:.1f}s]\n")

    # ── Optional: verify viewer is up ─────────────────────────────────────────
    if viewer_running():
        print("Viewer detected on :5174 — panorama URLs:")
        rooms = cfg.get("rooms", [])
        for room in rooms:
            rid = room["id"]
            print(f"  http://localhost:5174/?mode=pano&scene={scene_id}&room={rid}")
    else:
        print("Viewer not running on :5174 (start with: cd viewer && npm run dev)")

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"Done: {scene_id}  [{elapsed:.1f}s total]")
    print(f"  FPS URL:  http://localhost:5174/?scene={scene_id}")
    print(f"  Pano URL: http://localhost:5174/?mode=pano&scene={scene_id}")
    print(f"  GLB:      {glb_out}")
    print(f"  WPs:      {wp_out}")
    print(f"  Panos:    {pano_dir}/")
    print(f"  tour.json:{tour_out}")
    rooms = cfg.get("rooms", [])
    print(f"\n  Rooms ({len(rooms)}):")
    for room in rooms:
        jpg = pano_dir / f"{room['id']}.jpg"
        size = f"{jpg.stat().st_size // 1024} KB" if jpg.exists() else "MISSING"
        print(f"    {room['id']:30s}  {size}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
