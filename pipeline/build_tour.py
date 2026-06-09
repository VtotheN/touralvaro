#!/usr/bin/env python3
"""Universal tour build pipeline.
Usage: python3 pipeline/build_tour.py <project-dir> [scene-id]

Example: python3 pipeline/build_tour.py test_projects/proyecto_test_1/
Outputs:
  viewer/public/models/<scene-id>.glb
  viewer/public/waypoints/<scene-id>.json
  /tmp/tour_<scene-id>/<room>.png  (screenshots, optional)
"""
import subprocess, sys, os, json, shutil, pathlib, time

ROOT   = pathlib.Path(__file__).parent.parent
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"

def run(cmd, **kw):
    print(f"$ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        print(f"ERROR: exit {r.returncode}")
        sys.exit(r.returncode)
    return r

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)

    project_dir = pathlib.Path(sys.argv[1]).resolve()
    cfg_path    = project_dir / "config.json"
    if not cfg_path.exists():
        print(f"ERROR: {cfg_path} not found"); sys.exit(1)

    with open(cfg_path) as f:
        cfg = json.load(f)

    # Derive scene-id from project folder name (or config name field)
    scene_id = sys.argv[2] if len(sys.argv) > 2 else cfg.get("id", project_dir.name)
    print(f"\n{'='*60}")
    print(f"Building tour: {scene_id}")
    print(f"Project dir:   {project_dir}")
    print(f"{'='*60}\n")

    # Step 1: Generate GLB
    glb_out = ROOT / "viewer" / "public" / "models" / f"{scene_id}.glb"
    t0 = time.time()
    print("[1/3] Generating 3D model (Blender)...")
    run([BLENDER, "--background", "--python",
         str(ROOT / "pipeline" / "gen_apartment.py"),
         "--", str(cfg_path), str(glb_out)])
    print(f"      GLB: {glb_out}  ({glb_out.stat().st_size//1024} KB) [{time.time()-t0:.1f}s]\n")

    # Step 2: Generate waypoints
    wp_out = ROOT / "viewer" / "public" / "waypoints" / f"{scene_id}.json"
    wp_out.parent.mkdir(parents=True, exist_ok=True)
    print("[2/3] Generating waypoints...")
    run(["python3", str(ROOT / "pipeline" / "gen_waypoints.py"),
         str(cfg_path), str(wp_out)])
    print(f"      WP:  {wp_out}\n")

    # Step 3: Screenshots (optional, only if viewer is running)
    import socket
    viewer_up = False
    try:
        s = socket.create_connection(("localhost", 5174), timeout=1)
        s.close(); viewer_up = True
    except Exception:
        pass

    if viewer_up:
        print("[3/3] Taking screenshots (viewer detected)...")
        run(["node", str(ROOT / "viewer" / "screenshot.cjs"),
             scene_id, f"/tmp/tour_{scene_id}"])
    else:
        print("[3/3] Skipping screenshots (viewer not running on :5174)")

    print(f"\n{'='*60}")
    print(f"Tour ready: {scene_id}")
    print(f"  URL:  http://localhost:5174/?scene={scene_id}")
    print(f"  GLB:  {glb_out}")
    print(f"  WPs:  {wp_out}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
