#!/usr/bin/env python3 (called via blender --python)
"""
gen_preview.py — EEVEE Next fast panorama preview.

THE IMPOSSIBLE: "Need Cycles (slow) for quality renders."
REALITY: EEVEE Next (Blender 4.x) has screen-space ray tracing, ambient
         occlusion, and bloom. 10× faster than Cycles, acceptable quality
         for client previews and iteration.

Pipeline:
  - Same geometry/materials as gen_panorama.py (shared config format)
  - EEVEE Next engine with AO + SSR + Bloom
  - 512×256 output (fast preview) OR 2048×1024 (full preview)
  - Runs in ~30s vs ~7min per room

Usage:
    blender --background --python gen_preview.py -- <config.json> <output_dir> [--full]

Output: <output_dir>/preview/<room_id>.jpg
"""

import sys, os, json, math

import bpy

# ── Args ──────────────────────────────────────────────────────────────────────
args  = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(args) < 2:
    print("Usage: blender --background --python gen_preview.py -- <config> <outdir> [--full]")
    sys.exit(1)

cfg_path   = args[0]
output_dir = os.path.join(args[1], "preview")
full_res   = "--full" in args

with open(cfg_path) as f:
    cfg = json.load(f)

THEME  = cfg.get("theme", "caribbean_luxury")
WALL_H = cfg.get("wall_height", 2.85)
WALL_T = 0.001

os.makedirs(output_dir, exist_ok=True)

# ── Scene setup ───────────────────────────────────────────────────────────────
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"

# Resolution
if full_res:
    scene.render.resolution_x = 2048
    scene.render.resolution_y = 1024
else:
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 512

scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "JPEG"
scene.render.image_settings.quality = 88

# EEVEE Next quality settings
eevee = scene.eevee
try:
    eevee.use_taa_reprojection = True
    eevee.taa_samples          = 32
    eevee.taa_render_samples   = 64
    # Ambient Occlusion
    eevee.use_gtao    = True
    eevee.gtao_distance  = 1.2
    eevee.gtao_factor    = 0.8
    # Screen Space Reflections
    eevee.use_ssr       = True
    eevee.use_ssr_halfres = True
    eevee.ssr_quality   = 0.75
    # Bloom (glow on windows)
    eevee.use_bloom        = True
    eevee.bloom_threshold  = 1.2
    eevee.bloom_intensity  = 0.15
    eevee.bloom_radius     = 3.0
    # Shadows
    eevee.shadow_cube_size      = "1024"
    eevee.shadow_cascade_size   = "1024"
    eevee.use_shadow_high_bitdepth = True
except Exception as e:
    print(f"  EEVEE setting warn: {e}")

# Tonemapping
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look           = "None"
except Exception:
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look           = "Medium Contrast"
scene.view_settings.exposure = -0.5

# ── World ─────────────────────────────────────────────────────────────────────
if scene.world is None:
    scene.world = bpy.data.worlds.new("World")
world = scene.world
world.use_nodes = True
wt = world.node_tree
wt.nodes.clear()

sky = wt.nodes.new("ShaderNodeTexSky")
sky.sky_type      = "NISHITA"
sky.sun_elevation = math.radians(38)
sky.sun_rotation  = math.radians(135)
sky.turbidity     = 3.0
sky.air_density   = 1.0

amb = wt.nodes.new("ShaderNodeBackground")
amb.inputs["Color"].default_value    = (0.96, 0.91, 0.82, 1.0)
amb.inputs["Strength"].default_value = 0.12

sky_bg = wt.nodes.new("ShaderNodeBackground")
sky_bg.inputs["Strength"].default_value = 0.20

mix = wt.nodes.new("ShaderNodeMixShader")
mix.inputs["Fac"].default_value = 0.65

out = wt.nodes.new("ShaderNodeOutputWorld")
wt.links.new(sky.outputs["Color"], sky_bg.inputs["Color"])
wt.links.new(amb.outputs["Background"],    mix.inputs[1])
wt.links.new(sky_bg.outputs["Background"], mix.inputs[2])
wt.links.new(mix.outputs["Shader"],        out.inputs["Surface"])

# Sun lamp
bpy.ops.object.light_add(type="SUN", location=(50, 50, 50))
_sun = bpy.context.active_object
_sun.name = "sun_directional"
_sun.data.energy        = 4.5
_sun.data.color         = (1.0, 0.97, 0.88)
_sun.data.angle         = math.radians(1.5)
_sun.rotation_euler     = (math.radians(52), 0.0, math.radians(135))

# ── Shared helpers (minimal subset from gen_panorama.py) ─────────────────────
def _get_mat(name):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    links = m.node_tree.links
    nodes.clear()
    out_n = nodes.new("ShaderNodeOutputMaterial")
    bsdf  = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out_n.inputs["Surface"])
    # Simple color map
    colors = {
        "wall_white":    ((0.92, 0.90, 0.86), 0.85),
        "stucco_warm":   ((0.90, 0.86, 0.80), 0.90),
        "travertine":    ((0.82, 0.77, 0.68), 0.75),
        "wood_oak":      ((0.45, 0.30, 0.15), 0.80),
        "walnut":        ((0.22, 0.14, 0.08), 0.75),
        "dark_stone":    ((0.12, 0.10, 0.10), 0.30),
        "linen_white":   ((0.90, 0.88, 0.84), 0.85),
        "charcoal":      ((0.15, 0.14, 0.13), 0.75),
        "rattan":        ((0.55, 0.40, 0.20), 0.85),
        "metal_chrome":  ((0.85, 0.85, 0.88), 0.10),
        "glass":         ((0.85, 0.92, 0.95), 0.05),
        "ceiling":       ((0.97, 0.97, 0.95), 0.90),
        "ceiling_warm":  ((0.96, 0.94, 0.90), 0.90),
        "outdoor_stone": ((0.55, 0.52, 0.45), 0.80),
        "kitchen_black": ((0.10, 0.10, 0.10), 0.40),
        "window_frame":  ((0.92, 0.92, 0.92), 0.60),
        "water_pool":    ((0.20, 0.55, 0.65), 0.05),
    }
    c, r = colors.get(name, ((0.80, 0.80, 0.80), 0.80))
    bsdf.inputs["Base Color"].default_value = (*c, 1.0)
    bsdf.inputs["Roughness"].default_value  = r
    if name in ("metal_chrome",):
        bsdf.inputs["Metallic"].default_value = 0.90
    if name in ("glass", "water_pool"):
        bsdf.inputs["Alpha"].default_value = 0.15
        m.blend_method = "BLEND"
    return m

def add_box(name, sx, sy, sz, x, y, z, mat_name="wall_white"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x+sx/2, y+sy/2, z+sz/2))
    o = bpy.context.active_object
    o.name = name
    o.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.clear()
    o.data.materials.append(_get_mat(mat_name))

def add_plane(name, sx, sy, x, y, z, rx=0, mat_name="wall_white"):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x+sx/2, y+sy/2, z))
    o = bpy.context.active_object
    o.name = name
    o.scale = (sx, sy, 1)
    o.rotation_euler = (rx, 0, 0)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    o.data.materials.clear()
    o.data.materials.append(_get_mat(mat_name))

def build_room_simple(room):
    rid = room["id"]
    x, y = room["x"], room["y"]
    w, d = room["w"], room["d"]
    z_off = room.get("z_offset", 0.0)

    is_terraza = "terraza" in rid.lower()
    wall_mat    = "stucco_warm"
    ceiling_mat = "ceiling_warm"

    is_wet = any(k in rid.lower() for k in ("bano", "bath"))
    floor_mat = "outdoor_stone" if is_terraza else ("travertine" if True else "wood_oak")

    add_plane(f"{rid}_floor",   w, d, x, y, z_off,           mat_name=floor_mat)
    if not is_terraza:
        add_plane(f"{rid}_ceiling", w, d, x, y, z_off + WALL_H, rx=math.pi, mat_name=ceiling_mat)

    add_box(f"{rid}_wall_s", w,    WALL_T, WALL_H, x,         y,         z_off, wall_mat)
    add_box(f"{rid}_wall_n", w,    WALL_T, WALL_H, x,         y+d-WALL_T,z_off, wall_mat)
    add_box(f"{rid}_wall_w", WALL_T, d,   WALL_H, x,         y,         z_off, wall_mat)
    add_box(f"{rid}_wall_e", WALL_T, d,   WALL_H, x+w-WALL_T,y,         z_off, wall_mat)

    # Simple interior lights
    area_m2 = w * d
    bpy.ops.object.light_add(type="AREA",
        location=(x + w/2, y + d/2, z_off + WALL_H - 0.05))
    lt = bpy.context.active_object
    lt.name = f"lt_{rid}"
    lt.data.shape = "RECTANGLE"
    lt.data.size   = min(w * 0.6, 2.0)
    lt.data.size_y = min(d * 0.6, 2.0)
    lt.data.energy = area_m2 * 80
    lt.data.color  = (1.0, 0.97, 0.90)
    lt.rotation_euler = (math.pi, 0.0, 0.0)

# ── Camera ────────────────────────────────────────────────────────────────────
cam_data = bpy.data.cameras.new("PanoCam")
cam_data.type          = "PANO"
cam_data.panorama_type = "EQUIRECTANGULAR"
cam_obj = bpy.data.objects.new("PanoCam", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# ── Build + render ────────────────────────────────────────────────────────────
rooms = cfg.get("rooms", [])
print(f"\nBuilding preview: {cfg.get('name', 'apt')} — {len(rooms)} rooms")
for room in rooms:
    build_room_simple(room)

print(f"Rendering {len(rooms)} EEVEE previews → {output_dir}")
for room in rooms:
    rid = room["id"]
    x, y = room["x"], room["y"]
    w, d = room["w"], room["d"]
    z_off = room.get("z_offset", 0.0)

    cam_obj.location       = (x + w/2, y + d/2, 1.65 + z_off)
    cam_obj.rotation_euler = (math.radians(90), 0.0, 0.0)

    out_path = os.path.join(output_dir, f"{rid}.jpg")
    scene.render.filepath = out_path

    print(f"  {rid}...", end=" ", flush=True)
    bpy.ops.render.render(write_still=True)
    print(f"→ {out_path}")

print(f"\nDONE — {len(rooms)} previews in {output_dir}")
