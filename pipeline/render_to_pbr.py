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

def dominant_hsv(img_array, samples=2000):
    """Get dominant color in HSV space via k-means-like sampling."""
    h_img, w_img = img_array.shape[:2]
    pixels = img_array.reshape(-1, 3)
    # Sample random pixels
    idx = np.random.choice(len(pixels), min(samples, len(pixels)), replace=False)
    sample = pixels[idx].astype(np.float32) / 255.0
    # Convert RGB→HSV manually
    r, g, b = sample[:,0], sample[:,1], sample[:,2]
    maxc = np.max(sample, axis=1)
    minc = np.min(sample, axis=1)
    v = maxc
    s = np.where(maxc != 0, (maxc - minc) / maxc, 0)
    # H calculation
    diff = maxc - minc + 1e-9
    rc = (maxc - r) / diff
    gc = (maxc - g) / diff
    bc = (maxc - b) / diff
    h = np.where(r == maxc, bc - gc,
        np.where(g == maxc, 2.0 + rc - bc, 4.0 + gc - rc))
    h = (h / 6.0) % 1.0 * 360
    # Median values
    return float(np.median(h)), float(np.median(s)), float(np.median(v))

def detect_surface(img_path):
    """Detect surface type from image dominant color."""
    try:
        img = Image.open(img_path).convert("RGB")
        img.thumbnail((200, 200))
        arr = np.array(img)
        hue, sat, val = dominant_hsv(arr)
        for (h_min, h_max), s_min, v_min, v_max, surface, ph_id in MATERIAL_RULES:
            h_ok = (h_min <= hue <= h_max) or (h_min == 0 and h_max == 360)
            if h_ok and sat >= s_min and v_min <= val <= v_max:
                return surface, ph_id, (hue, sat, val)
        return "wall_white", None, (hue, sat, val)
    except Exception as e:
        print(f"  detect error {img_path}: {e}")
        return "wall_white", None, (0, 0, 0.9)

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

    surface, ph_id, hsv = detect_surface(str(img_path))
    print(f"  {img_path.name} → {room_key}: {surface} (H={hsv[0]:.0f}° S={hsv[1]:.2f} V={hsv[2]:.2f})")
    room_materials[room_key] = {"surface": surface, "ph_id": ph_id, "hsv": list(hsv)}
    all_surfaces[surface] = ph_id

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
        surface = ROOM_MATERIALS.get(room_key, {{}}).get("surface", "wood_floor")
        tex_dir = TEXTURE_DIRS.get(surface)
        mat = make_pbr_mat(f"mat_floor_{{room_key}}", tex_dir, (0.52, 0.38, 0.22, 1), 0.6)
    elif "wall" in name_lower or "base" in name_lower:
        mat = make_pbr_mat("mat_wall", None, (0.94, 0.93, 0.91, 1), 0.88)
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
