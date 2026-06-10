# DEPRECATED 2026-06-10 — unused dead code, replaced by gen_panorama.py + enhance_panorama.py + post_render.sh
"""
render_to_pbr.py — Extract materials from architectural renders and apply to Blender scene.
Usage: python3 render_to_pbr.py <renders_dir/> <config.json> [--blend-output scene.blend]

Analyzes render images → detects surface types → downloads PBR from Polyhaven →
generates a Blender Python script to apply materials → optionally runs Blender.
"""
import os, sys, json, requests, argparse
from pathlib import Path
from PIL import Image
import numpy as np

# ── CLI ────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("renders_dir", help="Directory with render images")
parser.add_argument("config", help="apartment config.json from auto_plan_reader")
parser.add_argument("--blend-output", default=None)
parser.add_argument("--download-dir", default="./pbr_textures")
args = parser.parse_args()

renders_dir = Path(args.renders_dir)
download_dir = Path(args.download_dir)
download_dir.mkdir(exist_ok=True)

# ── Polyhaven PBR catalog (free, CC0) ─────────────────────────────────────────
POLYHAVEN_API = "https://api.polyhaven.com"

# Material detection rules: dominant color → surface type → Polyhaven asset
MATERIAL_RULES = [
    # (hue_range_deg, sat_min, val_min, val_max, surface_type, polyhaven_id)
    ((20, 40),  0.2, 0.2, 0.6,  "wood_floor",     "wood_floor_deck"),
    ((20, 45),  0.1, 0.5, 0.9,  "wood_light",     "light_wood"),
    ((0,  30),  0.0, 0.8, 1.0,  "wall_white",     None),  # solid color, no texture
    ((200, 230), 0.0, 0.3, 0.9, "wall_white",     None),
    ((0,  360), 0.0, 0.15, 0.55, "concrete",      "concrete_floor"),
    ((15, 35),  0.3, 0.3, 0.7,  "stone_floor",   "cobblestone_floor"),
    ((0,  30),  0.0, 0.6, 1.0,  "marble",        "marble_01"),
    ((200, 240), 0.1, 0.2, 0.8, "tile_gray",     "ceramic_tiles"),
    ((0,  360), 0.0, 0.05, 0.3, "dark_floor",    "dark_wood_floor"),
]

def rgb_to_hsv(arr):
    """Convert Nx3 float32 [0-1] RGB array to H[0-360], S[0-1], V[0-1]."""
    r, g, b = arr[:,0], arr[:,1], arr[:,2]
    maxc = np.max(arr, axis=1)
    minc = np.min(arr, axis=1)
    v = maxc
    s = np.where(maxc != 0, (maxc - minc) / maxc, 0)
    diff = maxc - minc + 1e-9
    rc = (maxc - r) / diff
    gc = (maxc - g) / diff
    bc = (maxc - b) / diff
    h = np.where(r == maxc, bc - gc,
        np.where(g == maxc, 2.0 + rc - bc, 4.0 + gc - rc))
    h = (h / 6.0) % 1.0 * 360
    return float(np.median(h)), float(np.median(s)), float(np.median(v))

def zone_hsv(arr, y0_frac, y1_frac, samples=1000):
    """Sample HSV from a horizontal band of the image."""
    h, w = arr.shape[:2]
    y0, y1 = int(h * y0_frac), int(h * y1_frac)
    band = arr[y0:y1].reshape(-1, 3)
    if len(band) == 0:
        return 0.0, 0.0, 0.9
    idx = np.random.choice(len(band), min(samples, len(band)), replace=False)
    sample = band[idx].astype(np.float32) / 255.0
    return rgb_to_hsv(sample)

def match_rule(hue, sat, val):
    for (h_min, h_max), s_min, v_min, v_max, surface, ph_id in MATERIAL_RULES:
        h_ok = (h_min <= hue <= h_max) or (h_min == 0 and h_max == 360)
        if h_ok and sat >= s_min and v_min <= val <= v_max:
            return surface, ph_id
    return "wall_white", None

def detect_surface(img_path):
    """Zone-based detection: bottom=floor, middle=walls, full=fallback."""
    try:
        img = Image.open(img_path).convert("RGB")
        img.thumbnail((300, 300))
        arr = np.array(img)
        # Bottom 30% → floor
        fh, fs, fv = zone_hsv(arr, 0.70, 1.00)
        floor_surf, floor_ph = match_rule(fh, fs, fv)
        # Middle 40% → walls
        wh, ws, wv = zone_hsv(arr, 0.30, 0.70)
        wall_surf, wall_ph = match_rule(wh, ws, wv)
        # If floor zone is clearly darker/warmer than wall → use it; else wall_white fallback
        floor_is_distinct = (fv < wv - 0.1) or (fs > 0.15 and fs > ws + 0.05)
        if not floor_is_distinct:
            floor_surf, floor_ph = "wall_white", None
        hsv_summary = (fh, fs, fv)
        print(f"    floor_zone H={fh:.0f}° S={fs:.2f} V={fv:.2f} → {floor_surf}")
        print(f"    wall_zone  H={wh:.0f}° S={ws:.2f} V={wv:.2f} → {wall_surf}")
        return floor_surf, floor_ph, wall_surf, wall_ph, hsv_summary
    except Exception as e:
        print(f"  detect error {img_path}: {e}")
        return "wall_white", None, "wall_white", None, (0, 0, 0.9)

def download_pbr(ph_id, size="1k"):
    """Download PBR texture set from Polyhaven."""
    local_dir = download_dir / ph_id
    if local_dir.exists() and any(local_dir.iterdir()):
        print(f"  PBR cached: {ph_id}")
        return str(local_dir)
    local_dir.mkdir(exist_ok=True)
    try:
        # Get asset info
        resp = requests.get(f"{POLYHAVEN_API}/files/{ph_id}", timeout=10)
        if resp.status_code != 200:
            return None
        files = resp.json()
        # Download: diffuse (Color), roughness, normal, AO
        maps = {
            "diffuse":   ("diffuse", "Color"),
            "roughness": ("roughness",),
            "normal":    ("nor_gl",),
            "ao":        ("ao",),
        }
        downloaded = {}
        for map_name, keys in maps.items():
            for key in keys:
                try:
                    url = files.get("Diffuse" if map_name=="diffuse" else
                                   "Roughness" if map_name=="roughness" else
                                   "nor_gl" if map_name=="normal" else "AO",
                                   {}).get(size, {}).get("jpg", {}).get("url")
                    if not url:
                        # fallback search
                        for k, v in files.items():
                            if map_name.lower() in k.lower():
                                url = v.get(size, v.get("1k", {})).get("jpg", {}).get("url")
                                if url: break
                    if url:
                        r = requests.get(url, timeout=30)
                        fname = local_dir / f"{map_name}.jpg"
                        with open(fname, "wb") as f:
                            f.write(r.content)
                        downloaded[map_name] = str(fname)
                        print(f"    ↓ {map_name}.jpg ({len(r.content)//1024}KB)")
                        break
                except Exception:
                    pass
        return str(local_dir) if downloaded else None
    except Exception as e:
        print(f"  Polyhaven error {ph_id}: {e}")
        return None

# ── Analyze renders ────────────────────────────────────────────────────────────
render_files = []
for ext in ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG"]:
    render_files.extend(renders_dir.glob(ext))

print(f"\nAnalyzing {len(render_files)} render images...")

room_materials = {}  # room_name → {surface_type, ph_id, color_hsv}
all_surfaces = {}    # surface_type → {ph_id, local_dir}

for img_path in render_files:
    stem = img_path.stem.lower()
    # Try to match render filename to room name
    room_key = None
    for keyword in ["sala", "cocina", "master", "hab", "baño", "comedor", "terraza", "balcon"]:
        if keyword in stem:
            room_key = keyword
            break
    if room_key is None:
        room_key = f"room_{len(room_materials)}"

    floor_surf, floor_ph, wall_surf, wall_ph, hsv = detect_surface(str(img_path))
    print(f"  {img_path.name} → {room_key}: floor={floor_surf} wall={wall_surf}")
    room_materials[room_key] = {
        "floor_surface": floor_surf, "floor_ph_id": floor_ph,
        "wall_surface":  wall_surf,  "wall_ph_id":  wall_ph,
        "hsv": list(hsv)
    }
    all_surfaces[floor_surf] = floor_ph
    all_surfaces[wall_surf]  = wall_ph

# ── Download PBR textures ──────────────────────────────────────────────────────
print(f"\nDownloading PBR textures...")
texture_dirs = {}
for surface, ph_id in all_surfaces.items():
    if ph_id:
        print(f"  {surface} → {ph_id}")
        local = download_pbr(ph_id)
        texture_dirs[surface] = local
    else:
        texture_dirs[surface] = None

# ── Generate Blender material script ─────────────────────────────────────────
blender_script = f'''"""
apply_materials.py — Auto-generated by render_to_pbr.py
Run: blender --background input.blend --python apply_materials.py -- output.blend
"""
import bpy, os

TEXTURE_DIRS = {json.dumps(texture_dirs, indent=2)}
ROOM_MATERIALS = {json.dumps(room_materials, indent=2)}

def load_texture(path):
    if path and os.path.exists(path):
        if path in bpy.data.images:
            return bpy.data.images[path]
        return bpy.data.images.load(path)
    return None

def make_pbr_mat(name, tex_dir, base_color=(0.9, 0.88, 0.85, 1.0), roughness=0.85):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    out.location = (300, 0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    if tex_dir and os.path.isdir(tex_dir):
        diffuse_path = os.path.join(tex_dir, "diffuse.jpg")
        rough_path   = os.path.join(tex_dir, "roughness.jpg")
        normal_path  = os.path.join(tex_dir, "normal.jpg")
        ao_path      = os.path.join(tex_dir, "ao.jpg")

        coord = nodes.new("ShaderNodeTexCoord"); coord.location = (-800, 0)
        mapping = nodes.new("ShaderNodeMapping"); mapping.location = (-600, 0)
        links.new(coord.outputs["UV"], mapping.inputs["Vector"])

        if os.path.exists(diffuse_path):
            diff_tex = nodes.new("ShaderNodeTexImage")
            diff_tex.location = (-300, 200)
            diff_tex.image = load_texture(diffuse_path)
            diff_tex.image.colorspace_settings.name = "sRGB"
            links.new(mapping.outputs["Vector"], diff_tex.inputs["Vector"])
            links.new(diff_tex.outputs["Color"], bsdf.inputs["Base Color"])

        if os.path.exists(rough_path):
            rough_tex = nodes.new("ShaderNodeTexImage")
            rough_tex.location = (-300, -100)
            rough_tex.image = load_texture(rough_path)
            rough_tex.image.colorspace_settings.name = "Non-Color"
            links.new(mapping.outputs["Vector"], rough_tex.inputs["Vector"])
            links.new(rough_tex.outputs["Color"], bsdf.inputs["Roughness"])

        if os.path.exists(normal_path):
            norm_tex = nodes.new("ShaderNodeTexImage")
            norm_tex.location = (-300, -350)
            norm_tex.image = load_texture(normal_path)
            norm_tex.image.colorspace_settings.name = "Non-Color"
            norm_map = nodes.new("ShaderNodeNormalMap")
            norm_map.location = (-50, -350)
            links.new(mapping.outputs["Vector"], norm_tex.inputs["Vector"])
            links.new(norm_tex.outputs["Color"], norm_map.inputs["Color"])
            links.new(norm_map.outputs["Normal"], bsdf.inputs["Normal"])
    else:
        bsdf.inputs["Base Color"].default_value = base_color
        bsdf.inputs["Roughness"].default_value = roughness

    return mat

# Apply materials to objects by name matching
for obj in bpy.data.objects:
    if obj.type != "MESH":
        continue
    name_lower = obj.name.lower()
    mat = None

    if "floor" in name_lower:
        room_key = next((k for k in ROOM_MATERIALS if k in name_lower), None)
        rm = ROOM_MATERIALS.get(room_key, {{}})
        surface = rm.get("floor_surface", "wood_floor")
        tex_dir = TEXTURE_DIRS.get(surface)
        mat = make_pbr_mat(f"mat_floor_{{room_key or 'default'}}", tex_dir, (0.52, 0.38, 0.22, 1), 0.6)
    elif "wall" in name_lower or "base" in name_lower:
        room_key = next((k for k in ROOM_MATERIALS if k in name_lower), None)
        rm = ROOM_MATERIALS.get(room_key, {{}})
        w_surface = rm.get("wall_surface", "wall_white")
        w_tex = TEXTURE_DIRS.get(w_surface)
        mat = make_pbr_mat(f"mat_wall_{{room_key or 'default'}}", w_tex, (0.94, 0.93, 0.91, 1), 0.88)
    elif "ceiling" in name_lower or "ceil" in name_lower:
        mat = make_pbr_mat("mat_ceiling", None, (0.98, 0.98, 0.97, 1), 0.96)
    elif "glass" in name_lower:
        mat = make_pbr_mat("mat_glass", None, (0.8, 0.9, 1.0, 1), 0.05)
        mat.blend_method = "BLEND"
        mat.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.15
    elif "door" in name_lower:
        mat = make_pbr_mat("mat_door", None, (0.45, 0.30, 0.18, 1), 0.55)

    if mat and obj.material_slots:
        obj.material_slots[0].material = mat
    elif mat:
        obj.data.materials.append(mat)

print("Materials applied successfully")
'''

# ── Save scripts ──────────────────────────────────────────────────────────────
script_path = renders_dir / "apply_materials.py"
with open(script_path, "w") as f:
    f.write(blender_script)

# Save summary
summary = {
    "renders_analyzed": len(render_files),
    "room_materials": room_materials,
    "pbr_surfaces": {k: bool(v) for k, v in texture_dirs.items()},
    "apply_script": str(script_path),
    "next_step": f"blender --background model.glb --python {script_path}"
}
summary_path = renders_dir / "materials_summary.json"
with open(summary_path, "w") as f:
    json.dump(summary, f, indent=2)

print(f"\nBlender script: {script_path}")
print(f"Summary: {summary_path}")
print(f"\nNEXT STEP:")
print(f"  blender --background model.glb --python {script_path}")
