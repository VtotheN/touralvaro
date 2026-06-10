"""
gen_panorama.py — 360° equirectangular panorama renderer for touralvaro pipeline.
Usage: blender --background --python gen_panorama.py -- <config.json> <output_dir>
Renders one {room_id}.jpg per room using Cycles + Nishita sky (no external HDRI/textures).
"""
import bpy, sys, json, os, math
from pathlib import Path

# Add pipeline/ to sys.path so materials_pbr is importable inside Blender
sys.path.insert(0, str(Path(__file__).parent))
from materials_pbr import build_pbr_material

# ── Args ──────────────────────────────────────────────────────────────────────
argv = sys.argv
try:
    sep = argv.index("--")
    config_path = argv[sep + 1]
    output_dir  = argv[sep + 2]
except (ValueError, IndexError):
    config_path = "/tmp/apartment_config.json"
    output_dir  = "/tmp/panoramas"

with open(config_path) as f:
    cfg = json.load(f)

os.makedirs(output_dir, exist_ok=True)

WALL_H  = cfg.get("ceiling_height", 2.8)
WALL_T  = 0.001   # near-zero gap between adjacent room walls → eliminates black void strips
THEME   = cfg.get("theme", "")
SAMPLES = cfg.get("render_samples", 256)

# PBR texture directories (Polyhaven CC0, downloaded by download_pbr.py)
PBR_DIR = Path(__file__).parent.parent / "pbr_textures"
_manifest_path = PBR_DIR / "manifest.json"
MANIFEST = {}
if _manifest_path.exists():
    import json as _j
    with open(_manifest_path) as _f:
        MANIFEST = _j.load(_f)
RES_W   = cfg.get("render_width",   2048)
RES_H   = cfg.get("render_height",  1024)

# ── Reset scene ───────────────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

# ── Render engine ─────────────────────────────────────────────────────────────
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = SAMPLES
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.01
scene.cycles.max_bounces = 12
scene.cycles.diffuse_bounces = 6
scene.cycles.glossy_bounces = 4
scene.cycles.transmission_bounces = 12
scene.cycles.sample_clamp_indirect = 4.0
try:
    scene.cycles.use_metalrt = True
except Exception:
    pass
scene.render.resolution_x = RES_W
scene.render.resolution_y = RES_H
# Render to EXR first (full HDR range), then convert to JPEG in enhance pipeline
USE_EXR = cfg.get("render_exr", False)
if USE_EXR:
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.exr_codec   = "ZIPS"
    scene.render.image_settings.color_depth = "32"
else:
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality     = 95

# GPU if available, fallback CPU
prefs = bpy.context.preferences.addons.get("cycles")
if prefs:
    cprefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        # Set compute_device_type before refresh — required on Blender 4.x macOS
        for _ct in ("METAL", "HIP", "OPTIX", "CUDA"):
            try:
                cprefs.compute_device_type = _ct
                cprefs.refresh_devices()
                if any(d.type == _ct for d in cprefs.devices):
                    for d in cprefs.devices:
                        d.use = (d.type == _ct)
                    break
            except Exception:
                continue
        else:
            cprefs.compute_device_type = "NONE"
            cprefs.refresh_devices()
        has_gpu = any(d.use for d in cprefs.devices if d.type in ("CUDA", "OPTIX", "HIP", "METAL"))
        if has_gpu:
            scene.cycles.device = "GPU"
            enabled = [f"{d.name}({d.type})" for d in cprefs.devices if d.use]
            print(f"Cycles: GPU ({', '.join(enabled)})")
        else:
            scene.cycles.device = "CPU"
            print("Cycles: CPU fallback")
    except Exception as _e:
        scene.cycles.device = "CPU"
        print(f"Cycles: CPU (device probe failed: {_e})")

# Denoising
scene.cycles.use_denoising = True
try:
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
except Exception:
    pass

# Exposure / color management
# AgX > Filmic for arch-viz — better highlight rolloff, more photographic
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look           = "None"
except Exception:
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look           = "Medium Contrast"
scene.view_settings.exposure = -1.0

# ── World / Sky ───────────────────────────────────────────────────────────────
# Interior setup: warm ambient fill (low strength) + separate sun lamp.
# Full Nishita sky at high strength causes: blown-out ceiling, black void through
# doorways (background shows where no geometry exists).
if scene.world is None:
    scene.world = bpy.data.worlds.new("World")
world = scene.world
world.use_nodes = True
wt = world.node_tree
wt.nodes.clear()

# Mix: Nishita sky (for realistic window glow) + warm white fallback
sky  = wt.nodes.new("ShaderNodeTexSky")
sky.sky_type      = "NISHITA"
sky.sun_elevation = math.radians(38)
sky.sun_rotation  = math.radians(135)
sky.turbidity     = 3.0
sky.air_density   = 1.0

# Warm white interior ambient — fills voids with neutral warmth not black
amb  = wt.nodes.new("ShaderNodeBackground")
amb.inputs["Color"].default_value    = (0.96, 0.91, 0.82, 1.0)  # warm white
amb.inputs["Strength"].default_value = 0.35

sky_bg = wt.nodes.new("ShaderNodeBackground")
sky_bg.inputs["Strength"].default_value = 0.20  # much dimmer sky
mix  = wt.nodes.new("ShaderNodeMixShader")
mix.inputs["Fac"].default_value = 0.65           # 65% warm ambient, 35% sky

out  = wt.nodes.new("ShaderNodeOutputWorld")
wt.links.new(sky.outputs["Color"], sky_bg.inputs["Color"])
wt.links.new(amb.outputs["Background"],     mix.inputs[1])
wt.links.new(sky_bg.outputs["Background"],  mix.inputs[2])
wt.links.new(mix.outputs["Shader"],         out.inputs["Surface"])

# Dedicated sun lamp — provides direct sunlight through windows independent of sky strength
bpy.ops.object.light_add(type="SUN", location=(50, 50, 50))
_sun = bpy.context.active_object
_sun.name = "sun_directional"
_sun.data.energy          = 2.0           # W/m² — balanced Caribbean sun
_sun.data.color           = (1.0, 0.97, 0.88)
_sun.data.angle           = math.radians(1.5)  # small disk = sharper shadows
_sun.rotation_euler = (math.radians(52), 0.0, math.radians(135))  # 38° elevation from south-west

# Skybox sphere — fallback backdrop that covers every opening exposing Blender background.
# camera-invisible (cycles_visibility.camera=False) so it never appears in render directly,
# but reflection/transmission rays hit it instead of the void. Radius > all room geometry.
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=200, location=(0, 0, 0))
_skybox = bpy.context.active_object
_skybox.name = "skybox_sphere"
_skybox_mat = bpy.data.materials.new("mat_skybox_bg")
_skybox_mat.use_nodes = True
_skybox_nodes = _skybox_mat.node_tree.nodes
_skybox_nodes.clear()
_skybox_em = _skybox_nodes.new("ShaderNodeEmission")
_skybox_em.inputs["Strength"].default_value = 1.2
_skybox_em.inputs["Color"].default_value = (0.53, 0.80, 0.92, 1.0)  # outdoor sky blue
_skybox_out = _skybox_nodes.new("ShaderNodeOutputMaterial")
_skybox_mat.node_tree.links.new(_skybox_em.outputs[0], _skybox_out.inputs[0])
_skybox.data.materials.append(_skybox_mat)
# Flip normals inward so rays escaping through openings see the sky-blue interior face
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.flip_normals()
bpy.ops.object.mode_set(mode='OBJECT')

# ── Material helpers ──────────────────────────────────────────────────────────
def _clear_new(name):
    if name in bpy.data.materials:
        return bpy.data.materials[name], False
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m, True

def _bsdf_out(m):
    nodes = m.node_tree.nodes
    links = m.node_tree.links
    out   = nodes.new("ShaderNodeOutputMaterial"); out.location = (800, 0)
    bsdf  = nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return bsdf, nodes, links

def _noise_colorramp(nodes, links, scale, detail, c0, c1, loc_x=-200):
    coord = nodes.new("ShaderNodeTexCoord"); coord.location = (loc_x - 400, 0)
    noise = nodes.new("ShaderNodeTexNoise");  noise.location = (loc_x - 200, 0)
    noise.inputs["Scale"].default_value  = scale
    noise.inputs["Detail"].default_value = detail
    links.new(coord.outputs["Object"], noise.inputs["Vector"])
    cr = nodes.new("ShaderNodeValToRGB"); cr.location = (loc_x, 0)
    cr.color_ramp.elements[0].color = (*c0, 1.0)
    cr.color_ramp.elements[1].color = (*c1, 1.0)
    links.new(noise.outputs["Fac"], cr.inputs["Fac"])
    return cr

def _musgrave_colorramp(nodes, links, scale, detail, c0, c1, loc_x=-200):
    # ShaderNodeTexMusgrave removed in Blender 4.x — use Noise with high detail
    coord = nodes.new("ShaderNodeTexCoord"); coord.location = (loc_x - 400, 0)
    mus   = nodes.new("ShaderNodeTexNoise"); mus.location   = (loc_x - 200, 0)
    mus.inputs["Scale"].default_value     = scale
    mus.inputs["Detail"].default_value    = detail
    mus.inputs["Roughness"].default_value = 0.7
    links.new(coord.outputs["Object"], mus.inputs["Vector"])
    cr = nodes.new("ShaderNodeValToRGB"); cr.location = (loc_x, 0)
    cr.color_ramp.elements[0].color = (*c0, 1.0)
    cr.color_ramp.elements[1].color = (*c1, 1.0)
    links.new(mus.outputs["Fac"], cr.inputs["Fac"])
    return cr

def _wave_colorramp(nodes, links, scale, distortion, c0, c1, loc_x=-200):
    """Wood grain: wave BANDS + noise mix → realistic grain, not ring pattern."""
    coord = nodes.new("ShaderNodeTexCoord"); coord.location = (loc_x - 600, 0)
    wave  = nodes.new("ShaderNodeTexWave");  wave.location  = (loc_x - 400, 0)
    wave.wave_type  = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value      = scale
    wave.inputs["Distortion"].default_value = distortion * 1.8  # more irregular grain
    wave.inputs["Detail"].default_value     = 4.0
    wave.inputs["Detail Scale"].default_value = 2.5
    wave.inputs["Detail Roughness"].default_value = 0.6
    links.new(coord.outputs["Object"], wave.inputs["Vector"])
    # Mix with noise for random knots/variation
    noise = nodes.new("ShaderNodeTexNoise"); noise.location = (loc_x - 400, -200)
    noise.inputs["Scale"].default_value   = scale * 0.5
    noise.inputs["Detail"].default_value  = 6.0
    noise.inputs["Roughness"].default_value = 0.7
    links.new(coord.outputs["Object"], noise.inputs["Vector"])
    mix = nodes.new("ShaderNodeMixRGB"); mix.location = (loc_x - 200, 0)
    mix.blend_type = "MULTIPLY"
    mix.inputs["Fac"].default_value = 0.25
    links.new(wave.outputs["Color"],  mix.inputs["Color1"])
    links.new(noise.outputs["Fac"],   mix.inputs["Color2"])
    cr = nodes.new("ShaderNodeValToRGB"); cr.location = (loc_x, 0)
    cr.color_ramp.elements[0].color = (*c0, 1.0)
    cr.color_ramp.elements[1].color = (*c1, 1.0)
    links.new(mix.outputs["Color"], cr.inputs["Fac"])
    return cr

def _bump_noise(nodes, links, bsdf, strength, scale=8, detail=6):
    coord  = nodes.new("ShaderNodeTexCoord"); coord.location  = (-600, -300)
    noise  = nodes.new("ShaderNodeTexNoise"); noise.location  = (-400, -300)
    noise.inputs["Scale"].default_value  = scale
    noise.inputs["Detail"].default_value = detail
    bump   = nodes.new("ShaderNodeBump");     bump.location   = (-100, -300)
    bump.inputs["Strength"].default_value = strength
    links.new(coord.outputs["Object"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"],    bump.inputs["Height"])
    links.new(bump.outputs["Normal"],  bsdf.inputs["Normal"])

def _bump_musgrave(nodes, links, bsdf, strength, scale=30, detail=8):
    coord = nodes.new("ShaderNodeTexCoord"); coord.location = (-600, -300)
    mus   = nodes.new("ShaderNodeTexNoise"); mus.location   = (-400, -300)
    mus.inputs["Scale"].default_value     = scale
    mus.inputs["Detail"].default_value    = detail
    mus.inputs["Roughness"].default_value = 0.7
    bump  = nodes.new("ShaderNodeBump");    bump.location   = (-100, -300)
    bump.inputs["Strength"].default_value = strength
    links.new(coord.outputs["Object"], mus.inputs["Vector"])
    links.new(mus.outputs["Fac"],      bump.inputs["Height"])
    links.new(bump.outputs["Normal"],  bsdf.inputs["Normal"])

def _voronoi_colorramp(nodes, links, scale, c0, c1, loc_x=-200):
    coord = nodes.new("ShaderNodeTexCoord");    coord.location = (loc_x - 400, 0)
    vor   = nodes.new("ShaderNodeTexVoronoi");  vor.location   = (loc_x - 200, 0)
    vor.inputs["Scale"].default_value = scale
    links.new(coord.outputs["Object"], vor.inputs["Vector"])
    cr = nodes.new("ShaderNodeValToRGB"); cr.location = (loc_x, 0)
    cr.color_ramp.elements[0].color = (*c0, 1.0)
    cr.color_ramp.elements[1].color = (*c1, 1.0)
    links.new(vor.outputs["Distance"], cr.inputs["Fac"])
    return cr

# ── Caribbean PBR material library ───────────────────────────────────────────
def mat_travertine():
    m, new = _clear_new("travertine")
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    # Slightly darker range for better contrast with bright linen furniture
    cr = _noise_colorramp(nodes, links, 6, 8, (0.70, 0.64, 0.53), (0.82, 0.76, 0.64))
    links.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.52
    _bump_noise(nodes, links, bsdf, 0.65)   # visible stone surface texture
    return m

def mat_stucco_warm():
    m, new = _clear_new("stucco_warm")
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    # Warmer, slightly darker walls → sofa/linen pops against them
    cr = _musgrave_colorramp(nodes, links, 25, 10, (0.78, 0.72, 0.64), (0.86, 0.81, 0.73))
    links.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.90
    _bump_musgrave(nodes, links, bsdf, 0.40)  # visible plaster micro-texture
    return m

def mat_walnut():
    m, new = _clear_new("walnut")
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    cr = _wave_colorramp(nodes, links, 18, 2.5, (0.10, 0.05, 0.01), (0.35, 0.20, 0.08))
    links.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.55
    # Wood grain surface bump
    _bump_musgrave(nodes, links, bsdf, 0.25, scale=20, detail=6)
    return m

def mat_dark_stone():
    m, new = _clear_new("dark_stone")
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    cr = _voronoi_colorramp(nodes, links, 6, (0.16, 0.14, 0.12), (0.24, 0.22, 0.20))
    links.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.25
    bsdf.inputs["Specular IOR Level"].default_value = 0.7
    return m

def mat_rattan():
    m, new = _clear_new("rattan")
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    cr = _noise_colorramp(nodes, links, 20, 4, (0.62, 0.48, 0.28), (0.78, 0.64, 0.44))
    links.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.88
    # Visible weave pattern
    _bump_noise(nodes, links, bsdf, 0.55, scale=25, detail=6)
    return m

def mat_linen_white():
    m, new = _clear_new("linen_white")
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    # Bright ivory/cream — stands out against warmer, darker walls
    bsdf.inputs["Base Color"].default_value = (0.97, 0.94, 0.88, 1.0)
    bsdf.inputs["Roughness"].default_value  = 0.93
    bsdf.inputs["Subsurface Weight"].default_value = 0.05
    # Fabric micro-bump for cloth texture
    _bump_noise(nodes, links, bsdf, 0.35, scale=40, detail=8)
    return m

def mat_charcoal():
    m, new = _clear_new("charcoal")
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    bsdf.inputs["Base Color"].default_value = (0.10, 0.09, 0.09, 1.0)
    bsdf.inputs["Roughness"].default_value  = 0.90
    # Fabric texture
    _bump_noise(nodes, links, bsdf, 0.30, scale=35, detail=8)
    return m

def mat_kitchen_white():
    m, new = _clear_new("kitchen_white")
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    bsdf.inputs["Base Color"].default_value = (0.88, 0.87, 0.86, 1.0)
    bsdf.inputs["Roughness"].default_value  = 0.18
    return m

def mat_ceramic_white():
    m, new = _clear_new("ceramic_white")
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    bsdf.inputs["Base Color"].default_value = (0.93, 0.92, 0.91, 1.0)
    bsdf.inputs["Roughness"].default_value  = 0.08
    return m

def mat_metal_chrome():
    m, new = _clear_new("metal_chrome")
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    bsdf.inputs["Base Color"].default_value = (0.82, 0.82, 0.82, 1.0)
    bsdf.inputs["Metallic"].default_value   = 1.0
    bsdf.inputs["Roughness"].default_value  = 0.05
    return m

def mat_outdoor_stone():
    m, new = _clear_new("outdoor_stone")
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    cr = _noise_colorramp(nodes, links, 6, 4, (0.58, 0.52, 0.44), (0.70, 0.64, 0.56))
    links.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.82
    return m

def mat_tropical_green():
    m, new = _clear_new("tropical_green")
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    bsdf.inputs["Base Color"].default_value = (0.10, 0.28, 0.12, 1.0)
    bsdf.inputs["Roughness"].default_value  = 0.88
    bsdf.inputs["Subsurface Weight"].default_value = 0.08
    return m

def mat_wood_oak():
    m, new = _clear_new("wood_oak")
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    cr = _wave_colorramp(nodes, links, 10, 2, (0.42, 0.26, 0.10), (0.65, 0.44, 0.22))
    links.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.68
    return m

def mat_glass():
    m, new = _clear_new("glass")
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    bsdf.inputs["Base Color"].default_value = (0.85, 0.92, 1.0, 1.0)
    bsdf.inputs["Transmission Weight"].default_value = 1.0
    bsdf.inputs["IOR"].default_value       = 1.5
    bsdf.inputs["Roughness"].default_value = 0.0
    m.blend_method = "BLEND"
    return m

def mat_flat(name, color, roughness=0.85, metallic=0.0):
    m, new = _clear_new(name)
    if not new: return m
    bsdf, nodes, links = _bsdf_out(m)
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value  = roughness
    bsdf.inputs["Metallic"].default_value   = metallic
    return m

def mat_ceiling_caribbean():
    return mat_flat("ceiling_carib", (0.96, 0.93, 0.90), roughness=0.92)

def mat_kitchen_black():
    return mat_flat("kitchen_black", (0.10, 0.10, 0.10), roughness=0.40)

# Build material lookup used by add_box/add_plane
def _build_mats():
    is_caribbean = THEME == "caribbean_luxury"

    def _pbr(blender_name, scale=1.0, fallback_fn=None):
        """PBR from Polyhaven if downloaded, procedural fallback otherwise."""
        asset_id = MANIFEST.get(blender_name)
        if asset_id:
            pbr_dir = PBR_DIR / asset_id
            if pbr_dir.exists() and (pbr_dir / "diff.jpg").exists():
                return build_pbr_material(blender_name, pbr_dir, scale=scale)
        return fallback_fn() if fallback_fn else mat_flat(blender_name, (0.70, 0.67, 0.62), 0.80)

    d = {
        # Large surfaces — PBR with appropriate tiling scale
        "travertine":     _pbr("travertine",    scale=0.5, fallback_fn=mat_travertine),
        "stucco_warm":    _pbr("stucco_warm",   scale=0.3, fallback_fn=mat_stucco_warm),
        "walnut":         _pbr("walnut",        scale=0.6, fallback_fn=mat_walnut),
        "outdoor_stone":  _pbr("outdoor_stone", scale=0.4, fallback_fn=mat_outdoor_stone),
        "wood_oak":       _pbr("wood_oak",      scale=0.4, fallback_fn=mat_wood_oak),
        "ceramic_white":  _pbr("ceramic_white", scale=1.0, fallback_fn=mat_ceramic_white),
        "rattan":         _pbr("rattan",        scale=1.5, fallback_fn=mat_rattan),
        "linen_white":    _pbr("linen_white",   scale=0.8, fallback_fn=mat_linen_white),
        "concrete":       _pbr("concrete",      scale=0.3, fallback_fn=mat_stucco_warm),
        # Procedural for non-PBR materials
        "dark_stone":     mat_dark_stone(),
        "charcoal":       mat_charcoal(),
        "kitchen_white":  mat_kitchen_white(),
        "metal_chrome":   mat_metal_chrome(),
        "tropical_green": mat_tropical_green(),
        "glass":          mat_glass(),
        "kitchen_black":  mat_kitchen_black(),
        # Aliases
        "wood_walnut":    _pbr("walnut",    scale=0.6, fallback_fn=mat_walnut),
        "wood_dark":      _pbr("walnut",    scale=0.6, fallback_fn=mat_walnut),
        "wood_medium":    _pbr("wood_oak",  scale=0.4, fallback_fn=mat_wood_oak),
        "wood_light":     _pbr("wood_oak",  scale=0.4, fallback_fn=mat_wood_oak),
        "rattan_cream":   _pbr("rattan",    scale=1.5, fallback_fn=mat_rattan),
        "fabric_gray":    mat_flat("fabric_gray",  (0.38, 0.38, 0.42), 0.90),
        "fabric_cream":   _pbr("linen_white", scale=0.8, fallback_fn=mat_linen_white),
        "marble_counter": _pbr("marble",    scale=0.5, fallback_fn=mat_dark_stone),
        "rug_warm":       mat_flat("rug_warm",     (0.55, 0.42, 0.32), 0.95),
        "cushion_blue":   mat_flat("cushion_blue", (0.28, 0.38, 0.58), 0.88),
        "door_wood":      _pbr("wood_oak",  scale=0.4, fallback_fn=mat_wood_oak),
        "window_frame":   mat_flat("window_frame", (0.72, 0.70, 0.68), 0.20),
    }
    wall_mat    = "stucco_warm" if is_caribbean else "wall_white"
    ceiling_mat = "ceiling_carib" if is_caribbean else "ceiling"
    base_mat    = "wood_oak" if is_caribbean else "baseboard"
    d["wall_white"]    = _pbr("stucco_warm", scale=0.3, fallback_fn=mat_stucco_warm) if is_caribbean else mat_flat("wall_white", (0.95, 0.94, 0.92), 0.88)
    d["ceiling"]       = mat_ceiling_caribbean() if is_caribbean else mat_flat("ceiling", (0.99, 0.99, 0.98), 0.96)
    d["ceiling_warm"]  = mat_ceiling_caribbean()
    d["baseboard"]     = _pbr("wood_oak", scale=0.4, fallback_fn=mat_wood_oak) if is_caribbean else mat_flat("baseboard", (0.99, 0.99, 0.98), 0.30)
    return d, wall_mat, ceiling_mat, base_mat

MATS, _WALL_MAT, _CEIL_MAT, _BASE_MAT = _build_mats()

def _get_mat(name):
    if name in MATS:
        return MATS[name]
    # fallback: create flat gray
    m = mat_flat(name, (0.7, 0.7, 0.7))
    MATS[name] = m
    return m

# ── UV helper ─────────────────────────────────────────────────────────────────
def _uv_smart_project(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=66, island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')

# ── Mesh helpers ──────────────────────────────────────────────────────────────
def add_plane(name, w, d, x, y, z, rx=0, ry=0, rz=0, mat_name="wall_white"):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x + w/2, y + d/2, z))
    o = bpy.context.active_object
    o.name = name
    o.scale = (w, d, 1)
    o.rotation_euler = (rx, ry, rz)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    _uv_smart_project(o)
    o.data.materials.clear()
    o.data.materials.append(_get_mat(mat_name))
    return o

def add_box(name, w, d, h, x, y, z, mat_name="wall_white"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x + w/2, y + d/2, z + h/2))
    o = bpy.context.active_object
    o.name = name
    o.scale = (w, d, h)
    bpy.ops.object.transform_apply(scale=True)
    _uv_smart_project(o)
    o.data.materials.clear()
    o.data.materials.append(_get_mat(mat_name))
    return o

def add_plant_sphere(name, r, x, y, z, mat_name="tropical_green"):
    """Organic plant canopy — UV sphere instead of box. Looks like foliage."""
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=r, segments=12, ring_count=8,
        location=(x + r, y + r, z + r * 0.7))
    o = bpy.context.active_object
    o.name = name
    # Slightly irregular shape — more organic
    o.scale = (1.0 + (hash(name) % 3) * 0.08,
               1.0 + (hash(name[1:]) % 3) * 0.06,
               0.80 + (hash(name[2:]) % 3) * 0.06)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.clear()
    o.data.materials.append(_get_mat(mat_name))
    return o

# ── Boolean cutter ────────────────────────────────────────────────────────────
def cut_opening(target_obj, x, y, z, w, d, h):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x + w/2, y + d/2, z + h/2))
    cutter = bpy.context.active_object
    cutter.scale = (w + 0.01, d + 0.01, h + 0.01)
    bpy.ops.object.transform_apply(scale=True)
    cutter.display_type = "WIRE"
    mod = target_obj.modifiers.new("cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter
    bpy.context.view_layer.objects.active = target_obj
    bpy.ops.object.modifier_apply(modifier="cut")
    bpy.data.objects.remove(cutter, do_unlink=True)

# ── Wall builder ──────────────────────────────────────────────────────────────
def build_wall(name, x0, y0, x1, y1, height, openings=None, mat_name="wall_white", z_off=0.0):
    dx = x1 - x0; dy = y1 - y0
    length = math.sqrt(dx*dx + dy*dy)
    angle  = math.atan2(dy, dx)
    cx = (x0 + x1) / 2; cy = (y0 + y1) / 2

    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, z_off + height/2))
    wall = bpy.context.active_object
    wall.name = name
    wall.scale = (length, WALL_T, height)
    wall.rotation_euler = (0, 0, angle)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    wall.data.materials.clear()
    wall.data.materials.append(_get_mat(mat_name))

    if openings:
        for op in openings:
            ow = op.get("width", 0.9); oh = op.get("height", 2.1)
            sill = op.get("sill", 0.0); offset = op.get("offset", 0.5)
            local_x = offset - length / 2
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            ox = cx + cos_a * local_x
            oy = cy + sin_a * local_x
            cut_opening(wall, ox - ow/2, oy - WALL_T, sill + z_off, ow, WALL_T*3, oh)
            if sill == 0:
                # Open doorway — no door leaf; slim frame only so light passes through
                add_box(f"{name}_door_frame", ow + 0.08, 0.08, oh + 0.05,
                        ox - (ow+0.08)/2, oy - 0.04, z_off, "window_frame")
            else:
                add_box(f"{name}_win_sill",    ow + 0.1,  0.15, 0.04,
                        ox - (ow+0.1)/2,  oy - 0.075, sill + z_off - 0.02, "window_frame")
                add_box(f"{name}_win_glass",   ow - 0.06, 0.02, oh - 0.06,
                        ox - (ow-0.06)/2, oy - 0.01,  sill + z_off + 0.03, "glass")
                ft = 0.05; fd = 0.06
                add_box(f"{name}_wf_t", ow, fd, ft, ox - ow/2, oy - fd/2, sill + z_off + oh - ft, "window_frame")
                add_box(f"{name}_wf_b", ow, fd, ft, ox - ow/2, oy - fd/2, sill + z_off,           "window_frame")
                add_box(f"{name}_wf_l", ft, fd, oh, ox - ow/2, oy - fd/2, sill + z_off,           "window_frame")
                add_box(f"{name}_wf_r", ft, fd, oh, ox + ow/2 - ft, oy - fd/2, sill + z_off,      "window_frame")
    _uv_smart_project(wall)
    return wall

# ── Room builder ──────────────────────────────────────────────────────────────
def build_room(room):
    rid   = room["id"]
    x, y  = room["x"], room["y"]
    w, d  = room["w"], room["d"]
    z_off = room.get("z_offset", 0.0)
    doors   = room.get("doors", [])
    windows = room.get("windows", [])
    is_caribbean = THEME == "caribbean_luxury"

    wall_mat    = "stucco_warm"   if is_caribbean else "wall_white"
    ceiling_mat = "ceiling_warm"  if is_caribbean else "ceiling"
    base_mat    = "wood_oak"      if is_caribbean else "baseboard"

    # Floor material selection
    is_wet   = any(k in rid.lower() for k in ("baño", "bath", "loft_bano", "cocina", "pasillo"))
    is_terra = "terraza" in rid.lower()
    if is_caribbean and is_terra:
        floor_mat = "outdoor_stone"
    elif is_caribbean:
        floor_mat = "travertine"
    elif is_wet:
        floor_mat = "ceramic_white"
    else:
        floor_mat = "wood_oak"

    add_plane(f"{rid}_floor",   w, d, x, y, z_off,          mat_name=floor_mat)
    if "terraza" in rid.lower():
        # Sky-emission ceiling for terraza — prevents black void above open outdoor space
        if "mat_sky_ceil" not in MATS:
            _tc_mat = bpy.data.materials.new("mat_sky_ceil")
            _tc_mat.use_nodes = True
            _tc_nodes = _tc_mat.node_tree.nodes
            _tc_nodes.clear()
            _tc_em = _tc_nodes.new("ShaderNodeEmission")
            _tc_em.inputs["Strength"].default_value = 2.5
            _tc_em.inputs["Color"].default_value = (0.45, 0.68, 0.90, 1.0)
            _tc_out = _tc_nodes.new("ShaderNodeOutputMaterial")
            _tc_mat.node_tree.links.new(_tc_em.outputs[0], _tc_out.inputs[0])
            MATS["mat_sky_ceil"] = _tc_mat
        add_plane(f"{rid}_ceiling", w, d, x, y, z_off + WALL_H, rx=math.pi, mat_name="mat_sky_ceil")
    else:
        add_plane(f"{rid}_ceiling", w, d, x, y, z_off + WALL_H, rx=math.pi, mat_name=ceiling_mat)

    add_box(f"{rid}_base_s", w,    0.01, 0.10, x,             y,             z_off, base_mat)
    add_box(f"{rid}_base_n", w,    0.01, 0.10, x,             y + d - 0.01,  z_off, base_mat)
    add_box(f"{rid}_base_w", 0.01, d,    0.10, x,             y,             z_off, base_mat)
    add_box(f"{rid}_base_e", 0.01, d,    0.10, x + w - 0.01, y,             z_off, base_mat)

    WALL_ALIAS = {"front": "south", "back": "north", "left": "west", "right": "east",
                  "south": "south", "north": "north", "west": "west", "east": "east"}
    wall_openings = {"south": [], "north": [], "west": [], "east": []}
    for door in doors:
        key = WALL_ALIAS.get(door["wall"], "south")
        wall_openings[key].append({**door, "sill": 0})
    for win in windows:
        key = WALL_ALIAS.get(win["wall"], "south")
        wall_openings[key].append({**win, "sill": win.get("sill", 0.9)})

    build_wall(f"{rid}_wall_s", x,   y,   x+w, y,   WALL_H, wall_openings["south"], wall_mat, z_off)
    build_wall(f"{rid}_wall_n", x,   y+d, x+w, y+d, WALL_H, wall_openings["north"], wall_mat, z_off)
    build_wall(f"{rid}_wall_w", x,   y,   x,   y+d, WALL_H, wall_openings["west"],  wall_mat, z_off)
    build_wall(f"{rid}_wall_e", x+w, y,   x+w, y+d, WALL_H, wall_openings["east"],  wall_mat, z_off)

    # Backdrops — prevent black void visible through doorways AND large windows.
    # For doors: warm wall-colored box just outside opening (at z_off, door height).
    # For windows: sky-blue emission plane just outside window (at sill height).
    BD = 0.40  # depth behind wall
    BT = 0.06  # backdrop thickness
    for door in doors:
        dw  = door.get("width", 0.9)
        dh  = door.get("height", 2.1)
        off = door.get("offset", 0.5)
        key = WALL_ALIAS.get(door["wall"], "south")
        bw  = dw - 0.05
        bh  = dh - 0.05
        if key == "south":
            ox = x + off
            add_box(f"{rid}_bd_s_{off}", bw, BT, bh, ox - bw/2, y - BD, z_off, wall_mat)
        elif key == "north":
            ox = x + off
            add_box(f"{rid}_bd_n_{off}", bw, BT, bh, ox - bw/2, y + d + BD - BT, z_off, wall_mat)
        elif key == "west":
            oy = y + off
            add_box(f"{rid}_bd_w_{off}", BT, bw, bh, x - BD, oy - bw/2, z_off, wall_mat)
        elif key == "east":
            oy = y + off
            add_box(f"{rid}_bd_e_{off}", BT, bw, bh, x + w + BD - BT, oy - bw/2, z_off, wall_mat)
    # Window backdrops — large openings (5×2.7m) must never show Blender void.
    # Sky-emission plane placed 0.5m outside wall at window center height.
    _win_mat_name = "mat_window_sky"
    if _win_mat_name not in MATS:
        _wm = bpy.data.materials.new(_win_mat_name)
        _wm.use_nodes = True
        _wm_nodes = _wm.node_tree.nodes
        _wm_nodes.clear()
        _wm_em = _wm_nodes.new("ShaderNodeEmission")
        _wm_em.inputs["Strength"].default_value = 3.0
        _wm_em.inputs["Color"].default_value = (0.75, 0.88, 1.00, 1.0)  # bright daylight
        _wm_out = _wm_nodes.new("ShaderNodeOutputMaterial")
        _wm.node_tree.links.new(_wm_em.outputs[0], _wm_out.inputs[0])
        MATS[_win_mat_name] = _wm
    for win in windows:
        ww   = win.get("width", 1.0)
        wh   = win.get("height", 1.2)
        sill = win.get("sill", 0.9)
        off  = win.get("offset", 0.5)
        key  = WALL_ALIAS.get(win["wall"], "south")
        wz   = z_off + sill + wh / 2   # vertical center of window
        if key == "south":
            ox = x + off + ww / 2
            add_box(f"{rid}_wbd_s_{off}", ww + 0.2, BT, wh + 0.2, ox - (ww+0.2)/2, y - BD - 0.1, wz - (wh+0.2)/2, _win_mat_name)
        elif key == "north":
            ox = x + off + ww / 2
            add_box(f"{rid}_wbd_n_{off}", ww + 0.2, BT, wh + 0.2, ox - (ww+0.2)/2, y + d + BD, wz - (wh+0.2)/2, _win_mat_name)
        elif key == "west":
            oy = y + off + ww / 2
            add_box(f"{rid}_wbd_w_{off}", BT, ww + 0.2, wh + 0.2, x - BD - 0.1, oy - (ww+0.2)/2, wz - (wh+0.2)/2, _win_mat_name)
        elif key == "east":
            oy = y + off + ww / 2
            add_box(f"{rid}_wbd_e_{off}", BT, ww + 0.2, wh + 0.2, x + w + BD, oy - (ww+0.2)/2, wz - (wh+0.2)/2, _win_mat_name)

    print(f"  Built room: {rid} ({w}×{d}m) z={z_off}")

# ── Interior point lights ─────────────────────────────────────────────────────
def add_room_lights(rooms):
    for room in rooms:
        x, y  = room["x"], room["y"]
        w, d  = room["w"], room["d"]
        z_off = room.get("z_offset", 0.0)
        area  = w * d

        # Primary area light — ceiling plane (warm white, soft shadows)
        # Placed 45cm below ceiling to avoid backscatter whitening the ceiling plane.
        bpy.ops.object.light_add(type="AREA",
            location=(x + w/2, y + d/2, z_off + WALL_H - 0.45))
        main_light = bpy.context.active_object
        main_light.name = f"light_{room['id']}_main"
        main_light.data.shape  = "RECTANGLE"
        main_light.data.size   = min(w * 0.55, 2.2)
        main_light.data.size_y = min(d * 0.55, 2.2)
        main_light.data.energy = area * 6   # was 30 → blown ceiling; 6W/m² gives ~400lux
        main_light.data.color  = (1.0, 0.97, 0.90)
        # rotation (0,0,0) = faces -Z = downward. No rotation needed.

        # Recessed spots — 4 corners at 80% room size
        n_spots = 4 if area > 6 else 2
        spot_xs = [x + w * 0.25, x + w * 0.75] if n_spots == 2 else \
                  [x + w * 0.2, x + w * 0.8, x + w * 0.2, x + w * 0.8]
        spot_ys = [y + d * 0.5, y + d * 0.5] if n_spots == 2 else \
                  [y + d * 0.25, y + d * 0.25, y + d * 0.75, y + d * 0.75]
        for k, (sx, sy) in enumerate(zip(spot_xs, spot_ys)):
            bpy.ops.object.light_add(type="SPOT",
                location=(sx, sy, z_off + WALL_H - 0.08))
            spot = bpy.context.active_object
            spot.name = f"light_{room['id']}_spot{k}"
            spot.data.energy          = area * 2.5  # was 10
            spot.data.color           = (1.0, 0.95, 0.85)
            spot.data.spot_size       = math.radians(55)
            spot.data.spot_blend      = 0.35
            spot.data.shadow_soft_size = 0.12
            # rotation (0,0,0) = faces -Z = downward

        # Warm fill near floor (bounce light simulation)
        bpy.ops.object.light_add(type="POINT",
            location=(x + w/2, y + d/2, z_off + 0.25))
        fill = bpy.context.active_object
        fill.name = f"light_{room['id']}_fill"
        fill.data.energy          = area * 1.5  # was 5
        fill.data.color           = (1.0, 0.92, 0.78)
        fill.data.shadow_soft_size = min(w, d) * 0.5

        # Window fill lights — invisible area lights just outside each window
        # Simulates daylight entering through glass. 6500K daylight color.
        WALL_ALIAS = {"south": "south", "north": "north", "west": "west", "east": "east",
                      "front": "south", "back": "north", "left": "west", "right": "east"}
        for win in room.get("windows", []):
            ww   = win.get("width", 1.0)
            wh   = win.get("height", 1.2)
            sill = win.get("sill", 0.9)
            off  = win.get("offset", 0.5)
            key  = WALL_ALIAS.get(win["wall"], "south")
            wz   = z_off + sill + wh / 2
            energy = ww * wh * 180  # W per m² of window opening

            if key == "south":
                lx, ly = x + off + ww/2, y - 1.2
                rot = (math.pi/2, 0, 0)
            elif key == "north":
                lx, ly = x + off + ww/2, y + d + 1.2
                rot = (-math.pi/2, 0, 0)
            elif key == "west":
                lx, ly = x - 1.2, y + off + ww/2
                rot = (0, math.pi/2, 0)
            else:  # east
                lx, ly = x + w + 1.2, y + off + ww/2
                rot = (0, -math.pi/2, 0)

            bpy.ops.object.light_add(type="AREA", location=(lx, ly, wz))
            wl = bpy.context.active_object
            wl.name = f"light_{room['id']}_win_{key}_{off}"
            wl.data.shape  = "RECTANGLE"
            wl.data.size   = ww
            wl.data.size_y = wh
            wl.data.energy = ww * wh * 25   # 25W/m² window fill (was 120, too blown)
            wl.data.color  = (0.75, 0.87, 1.0)  # 6500K daylight
            wl.rotation_euler = rot

# ── Furniture (replicated from gen_apartment.py, Caribbean materials) ─────────
def place_furniture(room_id, x0, y0, w, d, z_off=0.0):
    xi  = x0 + 0.15;       yi  = y0 + 0.15
    xe  = x0 + w - 0.15;   ye  = y0 + d - 0.15
    iw  = xe - xi;          id_ = ye - yi
    _z  = lambda z: z + z_off

    if room_id == "sala":
        sw  = min(iw - 0.40, 3.50)
        sx  = xi + (iw - sw) / 2
        sBy = ye - 0.18
        add_box("sala_sofa_back",    sw,          0.18, 0.88, sx,               sBy,        0.00, "linen_white")
        add_box("sala_sofa_base",    sw,          0.90, 0.42, sx,               sBy - 0.90, 0.00, "linen_white")
        add_box("sala_sofa_arm_l",   0.18,        0.90, 0.62, sx,               sBy - 0.90, 0.00, "linen_white")
        add_box("sala_sofa_arm_r",   0.18,        0.90, 0.62, sx + sw - 0.18,   sBy - 0.90, 0.00, "linen_white")
        cSW = sw / 3 - 0.04
        add_box("sala_cush1", cSW, 0.72, 0.10, sx + 0.03,          sBy - 0.88, 0.42, "charcoal")
        add_box("sala_cush2", cSW, 0.72, 0.10, sx + sw/3 + 0.01,   sBy - 0.88, 0.42, "charcoal")
        add_box("sala_cush3", cSW, 0.72, 0.10, sx + 2*sw/3 - 0.01, sBy - 0.88, 0.42, "travertine")
        ctW = min(iw * 0.28, 1.40); ctD = min(id_ * 0.17, 0.70)
        ctX = xi + (iw - ctW) / 2; ctY = sBy - 0.90 - 0.45 - ctD
        add_box("sala_coffee_top",  ctW,        ctD,        0.04, ctX,        ctY,        0.38, "dark_stone")
        add_box("sala_coffee_body", ctW - 0.10, ctD - 0.10, 0.38, ctX + 0.05, ctY + 0.05, 0.00, "walnut")
        rgW = min(iw - 0.30, 4.00); rgD = min(id_ * 0.50, 2.20)
        rgY = sBy - 0.90 - 0.35 - rgD
        add_box("sala_rug", rgW, rgD, 0.02, xi + (iw - rgW) / 2, max(rgY, yi), 0.00, "rattan")
        tvW = min(iw - 1.00, 3.00); tvX = xi + (iw - tvW) / 2
        add_box("sala_tv_unit",   tvW,        0.45, 0.50, tvX,        yi,        0.00, "walnut")
        add_box("sala_tv_screen", tvW - 0.30, 0.04, 0.58, tvX + 0.15, yi - 0.01, 0.52, "metal_chrome")

    elif room_id == "comedor":
        tW = min(iw * 0.48, 1.40); tD = min(id_ * 0.22, 0.85)
        tX = xi + (iw - tW) / 2;   tY = yi + (id_ - tD) / 2
        add_box("com_table_top",  tW,        tD,        0.04, tX,        tY,        0.73, "walnut")
        add_box("com_table_body", tW - 0.06, tD - 0.06, 0.73, tX + 0.03, tY + 0.03, 0.00, "walnut")
        for i in range(2):
            cX = tX + i * (tW / 2)
            add_box(f"com_cs{i}_seat", 0.45, 0.45, 0.44, cX, tY - 0.60,       0.00, "rattan")
            add_box(f"com_cs{i}_back", 0.45, 0.06, 0.44, cX, tY - 0.22,       0.44, "rattan")
            add_box(f"com_cn{i}_seat", 0.45, 0.45, 0.44, cX, tY + tD + 0.15,  0.00, "rattan")
            add_box(f"com_cn{i}_back", 0.45, 0.06, 0.44, cX, tY + tD + 0.53,  0.44, "rattan")

    elif room_id == "cocina":
        ctrE_d = id_ - 0.10
        add_box("coc_ctr_e_base", 0.55, ctrE_d,        0.88, xe - 0.55, yi,        0.00, "kitchen_white")
        add_box("coc_ctr_e_top",  0.60, ctrE_d + 0.06, 0.04, xe - 0.57, yi - 0.03, 0.88, "dark_stone")
        ctrS_w = iw - 0.62
        add_box("coc_ctr_s_base", ctrS_w,        0.55, 0.88, xi,        yi,        0.00, "kitchen_white")
        add_box("coc_ctr_s_top",  ctrS_w + 0.06, 0.60, 0.04, xi - 0.03, yi - 0.03, 0.88, "dark_stone")
        islW = min(iw * 0.42, 1.40); islD = min(id_ * 0.18, 0.75)
        islX = xi + (iw - 0.55 - islW) * 0.40; islY = yi + 0.65 + 0.35
        add_box("coc_island",     islW,        islD,        0.92, islX,        islY,        0.00, "kitchen_white")
        add_box("coc_island_top", islW + 0.06, islD + 0.06, 0.03, islX - 0.03, islY - 0.03, 0.92, "dark_stone")
        add_box("coc_cab_e", 0.35, ctrE_d, 0.70, xe - 0.35, yi,        1.55, "kitchen_white")
        add_box("coc_cab_s", ctrS_w - 0.10, 0.35, 0.70, xi, yi,        1.55, "kitchen_white")
        add_box("coc_sink",  0.48, 0.46, 0.04, xe - 0.52, yi + id_ * 0.25, 0.88, "metal_chrome")

    elif room_id == "master":
        bW = min(iw * 0.42, 1.80); bD = min(id_ * 0.55, 2.00)
        bX = xi + (iw - bW) / 2 - 0.25; bY = ye - bD - 0.05
        add_box("mas_bed_frame",  bW,         bD,   0.20, bX,             bY,             0.00, "walnut")
        add_box("mas_mattress",   bW,         bD,   0.25, bX,             bY,             0.20, "linen_white")
        add_box("mas_pillow1",    bW * 0.46,  0.48, 0.12, bX + 0.04,      bY + bD - 0.52, 0.45, "linen_white")
        add_box("mas_pillow2",    bW * 0.46,  0.48, 0.12, bX + bW * 0.50, bY + bD - 0.52, 0.45, "linen_white")
        add_box("mas_bedcover",   bW,         bD,   0.06, bX,             bY,             0.45, "charcoal")
        add_box("mas_headboard",  bW + 0.10,  0.12, 0.90, bX - 0.05,      ye - 0.12,      0.00, "walnut")
        add_box("mas_ns_l",       0.45, 0.45, 0.50, bX - 0.55,            bY,             0.00, "walnut")
        add_box("mas_ns_r",       0.45, 0.45, 0.50, bX + bW + 0.10,       bY,             0.00, "walnut")
        add_box("mas_wardrobe",   1.30, 0.60, 2.40, xe - 1.30,            yi,             0.00, "wood_oak")

    elif room_id == "hab2":
        bW = min(iw * 0.44, 1.60); bD = min(id_ * 0.52, 1.90)
        bX = xi + (iw - bW) / 2 - 0.20; bY = ye - bD - 0.05
        add_box("h2_bed_frame",  bW,         bD,   0.20, bX,             bY,             0.00, "wood_oak")
        add_box("h2_mattress",   bW,         bD,   0.22, bX,             bY,             0.20, "linen_white")
        add_box("h2_headboard",  bW + 0.10,  0.12, 0.80, bX - 0.05,      ye - 0.12,      0.00, "wood_oak")
        add_box("h2_pillow",     bW - 0.08,  0.45, 0.10, bX + 0.04,      bY + bD - 0.50, 0.42, "linen_white")
        add_box("h2_bedcover",   bW,         bD,   0.05, bX,             bY,             0.42, "charcoal")
        add_box("h2_ns",         0.42, 0.42, 0.48, bX - 0.52,            bY,             0.00, "wood_oak")
        add_box("h2_desk",       1.20, 0.55, 0.75, xe - 1.20,            yi,             0.00, "walnut")
        add_box("h2_chair_seat", 0.48, 0.48, 0.46, xe - 1.08,            yi + 0.65,      0.00, "rattan")
        add_box("h2_wardrobe",   0.65, 0.58, 2.40, xi,                   yi,             0.00, "wood_oak")

    elif room_id == "baño":
        add_box("ban_toilet_base", 0.38, 0.55, 0.40, xe - 0.42, yi,        0.00, "ceramic_white")
        add_box("ban_toilet_tank", 0.35, 0.16, 0.32, xe - 0.40, yi,        0.40, "ceramic_white")
        add_box("ban_toilet_seat", 0.34, 0.45, 0.04, xe - 0.40, yi + 0.02, 0.38, "ceramic_white")
        vanW = min(iw * 0.38, 0.70)
        add_box("ban_vanity_cab",  vanW,        0.48, 0.82, xi,        yi,         0.00, "kitchen_white")
        add_box("ban_vanity_top",  vanW + 0.06, 0.52, 0.03, xi - 0.03, yi - 0.02,  0.82, "dark_stone")
        add_box("ban_sink",        vanW - 0.18, 0.36, 0.06, xi + 0.09, yi + 0.06,  0.82, "ceramic_white")
        add_box("ban_mirror",      vanW,        0.03, 0.80, xi,        yi - 0.03,  0.88, "metal_chrome")
        sh = min(min(iw, id_) * 0.50, 0.85)
        add_box("ban_shower_tray", sh,   sh,   0.06, xe - sh,        ye - sh,        0.00, "travertine")
        add_box("ban_shower_w1",   sh,   0.04, 2.00, xe - sh,        ye - sh - 0.04, 0.00, "ceramic_white")
        add_box("ban_shower_w2",   0.04, sh + 0.08, 2.00, xe - sh - 0.04, ye - sh - 0.08, 0.00, "ceramic_white")

    elif room_id == "pasillo":
        conX = xi + iw * 0.35
        add_box("pas_console",     1.00, 0.32, 0.82, conX,        yi,        0.00, "walnut")
        add_box("pas_console_top", 1.06, 0.36, 0.03, conX - 0.03, yi - 0.02, 0.82, "dark_stone")
        add_box("pas_deco1",       0.12, 0.12, 0.22, conX + 0.15, yi + 0.01, 0.85, "ceramic_white")
        add_box("pas_deco2",       0.18, 0.18, 0.35, conX + 0.55, yi + 0.01, 0.85, "travertine")

    elif "loft_master" in room_id or "loft_mez_master" in room_id:
        add_box(f"{room_id}_headpanel", w, 0.10, WALL_H * 0.80, x0, ye - 0.10, _z(0.00), "walnut")
        bW = min(iw * 0.70, 1.80); bD = min(id_ * 0.60, 2.00)
        bX = xi + (iw - bW) / 2;   bY = ye - bD - 0.10
        add_box(f"{room_id}_bed_frame", bW,         bD,   0.22, bX,             bY,             _z(0.00), "walnut")
        add_box(f"{room_id}_mattress",  bW,         bD,   0.24, bX,             bY,             _z(0.22), "linen_white")
        add_box(f"{room_id}_bedcover",  bW,         bD,   0.07, bX,             bY,             _z(0.46), "charcoal")
        add_box(f"{room_id}_pillow1",   bW * 0.45,  0.50, 0.12, bX + 0.04,      bY + bD - 0.55, _z(0.46), "linen_white")
        add_box(f"{room_id}_pillow2",   bW * 0.45,  0.50, 0.12, bX + bW * 0.50, bY + bD - 0.55, _z(0.46), "linen_white")
        add_box(f"{room_id}_ns_l", 0.48, 0.42, 0.50, bX - 0.58,      bY + 0.10, _z(0.00), "walnut")
        add_box(f"{room_id}_ns_r", 0.48, 0.42, 0.50, bX + bW + 0.10, bY + 0.10, _z(0.00), "walnut")
        tvW = min(iw * 0.55, 1.20); tvX = xi + (iw - tvW) / 2
        add_box(f"{room_id}_tv", tvW, 0.04, 0.62, tvX, yi - 0.02, _z(0.80), "metal_chrome")
        fcx = x0 + w / 2; fcy = y0 + d / 2; fz = _z(WALL_H - 0.20)
        add_box(f"{room_id}_fan_hub", 0.20, 0.20, 0.12, fcx - 0.10, fcy - 0.10, fz, "metal_chrome")
        add_box(f"{room_id}_fan_b1",  0.80, 0.14, 0.03, fcx - 0.40, fcy - 0.07, fz - 0.03, "wood_oak")
        add_box(f"{room_id}_fan_b3",  0.14, 0.80, 0.03, fcx - 0.07, fcy - 0.40, fz - 0.03, "wood_oak")
        px = bX + bW + 0.10; py = bY
        add_box(f"{room_id}_pot",    0.28, 0.28, 0.30, px,        py,        _z(0.00), "travertine")
        add_box(f"{room_id}_trunk",  0.08, 0.08, 0.55, px + 0.10, py + 0.10, _z(0.30), "walnut")
        add_plant_sphere(f"{room_id}_canopy", 0.30, px - 0.02, py - 0.02, _z(0.85))
        # Mezzanine balcony railing at east open edge (overlooks sala below)
        if "mez" in room_id:
            rail_x = x0 + w - 0.08  # east edge
            # Door gap on east wall: offset=1.0 from south, width=0.9
            gap_c = y0 + 1.0; gap_hw = 0.45
            gap_s = gap_c - gap_hw; gap_e = gap_c + gap_hw
            # Travertine base sill segments
            if gap_s > y0:
                add_box(f"{room_id}_rail_sill_a", 0.08, gap_s - y0, 0.30,
                        rail_x, y0, _z(0.00), "travertine")
            if y0 + d > gap_e:
                add_box(f"{room_id}_rail_sill_b", 0.08, (y0 + d) - gap_e, 0.30,
                        rail_x, gap_e, _z(0.00), "travertine")
            # Glass panels above sill
            if gap_s > y0:
                add_box(f"{room_id}_rail_glass_a", 0.02, gap_s - y0, 0.62,
                        rail_x + 0.03, y0, _z(0.30), "glass")
            if y0 + d > gap_e:
                add_box(f"{room_id}_rail_glass_b", 0.02, (y0 + d) - gap_e, 0.62,
                        rail_x + 0.03, gap_e, _z(0.30), "glass")
            # Chrome top rail cap (continuous)
            add_box(f"{room_id}_rail_cap", 0.05, d, 0.06,
                    rail_x + 0.01, y0, _z(0.92), "metal_chrome")
            # Vertical chrome posts every ~0.8m
            n_posts = max(1, int(d / 0.8))
            for ip in range(n_posts + 1):
                py2 = y0 + ip * (d / n_posts)
                # Skip if inside door gap
                if gap_s <= py2 <= gap_e:
                    continue
                add_box(f"{room_id}_rail_post{ip}", 0.04, 0.04, 0.92,
                        rail_x + 0.02, py2, _z(0.00), "metal_chrome")

    elif "loft_bano" in room_id or "loft_mez_bano" in room_id:
        add_box(f"{room_id}_toilet_base", 0.38, 0.55, 0.40, xe - 0.42, yi,        _z(0.00), "ceramic_white")
        add_box(f"{room_id}_toilet_tank", 0.35, 0.16, 0.32, xe - 0.40, yi,        _z(0.40), "ceramic_white")
        add_box(f"{room_id}_toilet_seat", 0.34, 0.45, 0.04, xe - 0.40, yi + 0.02, _z(0.38), "ceramic_white")
        vanW = min(iw * 0.42, 0.80)
        add_box(f"{room_id}_vanity_cab",  vanW,        0.50, 0.84, xi,        yi,         _z(0.00), "walnut")
        add_box(f"{room_id}_vanity_top",  vanW + 0.06, 0.54, 0.03, xi - 0.03, yi - 0.02,  _z(0.84), "dark_stone")
        add_box(f"{room_id}_sink",        vanW - 0.20, 0.38, 0.06, xi + 0.10, yi + 0.07,  _z(0.84), "ceramic_white")
        add_box(f"{room_id}_mirror",      vanW,        0.03, 0.80, xi,        yi - 0.03,  _z(0.90), "metal_chrome")
        sh = min(min(iw, id_) * 0.50, 0.85)
        add_box(f"{room_id}_shower_tray", sh,   sh,        0.06, xe - sh,        ye - sh,        _z(0.00), "travertine")
        add_box(f"{room_id}_shower_w1",   sh,   0.04,      2.00, xe - sh,        ye - sh - 0.04, _z(0.00), "ceramic_white")
        add_box(f"{room_id}_shower_w2",   0.04, sh + 0.08, 2.00, xe - sh - 0.04, ye - sh - 0.08, _z(0.00), "ceramic_white")

    elif "loft_sala" in room_id:
        cabW = iw - 0.30
        add_box(f"{room_id}_cab_base",  cabW,        0.58, 0.90, xi,        ye - 0.58, _z(0.00), "kitchen_white")
        add_box(f"{room_id}_cab_top",   cabW + 0.06, 0.62, 0.03, xi - 0.03, ye - 0.60, _z(0.90), "dark_stone")
        add_box(f"{room_id}_cab_upper", cabW,        0.36, 0.72, xi,        ye - 0.36, _z(1.48), "kitchen_white")
        add_box(f"{room_id}_cooktop",   0.60, 0.50, 0.03, xi + iw * 0.35, ye - 0.55, _z(0.90), "kitchen_black")
        add_box(f"{room_id}_sink",      0.48, 0.38, 0.05, xi + 0.10, ye - 0.52, _z(0.90), "metal_chrome")
        islW = min(iw * 0.32, 1.40); islD = min(id_ * 0.14, 0.80)
        islX = xi + iw * 0.15; islY = yi + id_ * 0.50
        add_box(f"{room_id}_isl_base", islW,        islD,        0.92, islX,        islY,        _z(0.00), "kitchen_white")
        add_box(f"{room_id}_isl_top",  islW + 0.06, islD + 0.06, 0.03, islX - 0.03, islY - 0.03, _z(0.92), "dark_stone")
        for i in range(2):
            sx = islX + 0.18 + i * (islW / 2)
            add_box(f"{room_id}_stool{i}_seat", 0.40, 0.40, 0.04, sx, islY - 0.55, _z(0.70), "rattan")
            add_box(f"{room_id}_stool{i}_leg",  0.06, 0.06, 0.70, sx + 0.17, islY - 0.38, _z(0.00), "metal_chrome")
        dtW = min(iw * 0.28, 1.50); dtD = min(id_ * 0.16, 0.85)
        dtX = xi + iw * 0.58; dtY = yi + id_ * 0.48
        add_box(f"{room_id}_dtable_top",  dtW,        dtD,        0.04, dtX,        dtY,        _z(0.74), "walnut")
        add_box(f"{room_id}_dtable_base", dtW - 0.08, dtD - 0.08, 0.74, dtX + 0.04, dtY + 0.04, _z(0.00), "walnut")
        chair_pos = [
            (dtX + 0.10,       dtY - 0.55),
            (dtX + dtW - 0.50, dtY - 0.55),
            (dtX + 0.10,       dtY + dtD + 0.15),
            (dtX + dtW - 0.50, dtY + dtD + 0.15),
        ]
        for i, (cx_, cy_) in enumerate(chair_pos):
            add_box(f"{room_id}_dc{i}_seat", 0.45, 0.45, 0.44, cx_, cy_, _z(0.00), "rattan")
            add_box(f"{room_id}_dc{i}_back", 0.45, 0.06, 0.44, cx_, cy_ + 0.38, _z(0.44), "rattan")
        sfW = min(iw * 0.52, 2.80); sfX = xi + (iw - sfW) / 2; sfY = yi
        add_box(f"{room_id}_sofa_back",  sfW,          0.20, 0.92, sfX,              sfY,        _z(0.00), "linen_white")
        add_box(f"{room_id}_sofa_base",  sfW,          0.95, 0.44, sfX,              sfY + 0.20, _z(0.00), "linen_white")
        add_box(f"{room_id}_sofa_arm_l", 0.20,         0.95, 0.64, sfX,              sfY + 0.20, _z(0.00), "linen_white")
        add_box(f"{room_id}_sofa_arm_r", 0.20,         0.95, 0.64, sfX + sfW - 0.20, sfY + 0.20, _z(0.00), "linen_white")
        for i, rx in enumerate([sfX - 0.90, sfX + sfW + 0.10]):
            add_box(f"{room_id}_ratt{i}_seat", 0.70, 0.70, 0.38, rx, sfY + 0.10, _z(0.00), "rattan")
            add_box(f"{room_id}_ratt{i}_back", 0.70, 0.12, 0.60, rx, sfY + 0.62, _z(0.38), "rattan")
        ctW = min(sfW * 0.50, 1.20); ctD = 0.60
        ctX = xi + (iw - ctW) / 2; ctY = sfY + 1.20
        add_box(f"{room_id}_ct_top",  ctW,        ctD,        0.04, ctX,        ctY,        _z(0.38), "dark_stone")
        add_box(f"{room_id}_ct_base", ctW - 0.10, ctD - 0.10, 0.38, ctX + 0.05, ctY + 0.05, _z(0.00), "walnut")
        add_box(f"{room_id}_pot1",    0.30, 0.30, 0.35, xe - 0.40, yi + 0.20, _z(0.00), "travertine")
        add_plant_sphere(f"{room_id}_canopy1", 0.35, xe - 0.40, yi + 0.10, _z(0.35))

    elif "terraza" in room_id:
        for i in range(2):
            lbY = yi + 0.40 + i * 2.40
            add_box(f"{room_id}_lb{i}_base", 1.80, 0.72, 0.28, xi + 0.20, lbY,        _z(0.00), "rattan")
            add_box(f"{room_id}_lb{i}_back", 1.80, 0.08, 0.38, xi + 0.20, lbY,        _z(0.28), "rattan")
            add_box(f"{room_id}_lb{i}_mat",  1.72, 0.66, 0.06, xi + 0.24, lbY + 0.03, _z(0.28), "linen_white")
        add_box(f"{room_id}_side_table", 0.50, 0.50, 0.45, xi + 0.55, yi + 1.60, _z(0.00), "travertine")
        for i in range(3):
            px = xi + iw - 0.40; py = yi + 0.50 + i * 1.60
            add_box(f"{room_id}_plant{i}_pot",    0.32, 0.32, 0.38, px,        py,        _z(0.00), "travertine")
            add_box(f"{room_id}_plant{i}_trunk",  0.10, 0.10, 0.70, px + 0.11, py + 0.11, _z(0.38), "walnut")
            add_plant_sphere(f"{room_id}_plant{i}_canopy", 0.38, px - 0.08, py - 0.08, _z(1.08))

# ── Exterior environment ──────────────────────────────────────────────────────
def add_exterior_environment(cfg):
    """Add outdoor geometry so terraza panorama (and window views) show a
    Caribbean setting instead of void.  Adds: ground plane, pool, palm trees,
    and building facade panels."""

    rooms = cfg.get("rooms", [])

    # Bounding box of the whole building footprint
    all_x = [r["x"] for r in rooms] + [r["x"] + r["w"] for r in rooms]
    all_y = [r["y"] for r in rooms] + [r["y"] + r["d"] for r in rooms]
    bld_min_x = min(all_x); bld_max_x = max(all_x)
    bld_min_y = min(all_y); bld_max_y = max(all_y)
    bld_cx    = (bld_min_x + bld_max_x) / 2
    bld_cy    = (bld_min_y + bld_max_y) / 2

    # 1. Large ground plane (80 m × 80 m) centred on building
    bpy.ops.mesh.primitive_plane_add(size=80, location=(bld_cx, bld_cy, -0.01))
    ground = bpy.context.active_object
    ground.name = "ext_ground"
    ground.data.materials.clear()
    m_ground, new = _clear_new("ext_ground_mat")
    if new:
        bsdf, nodes, links = _bsdf_out(m_ground)
        cr = _noise_colorramp(nodes, links, 5, 4,
                              (0.28, 0.36, 0.24), (0.40, 0.50, 0.32))
        links.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.90
        _bump_noise(nodes, links, bsdf, 0.25, scale=6, detail=4)
    ground.data.materials.append(m_ground)

    # 2. Pool — in front of the terraza east wall
    # Terraza is at x ≈ bld_max_x; pool goes east of it
    pool_cx = bld_max_x + 3.5
    pool_cy = bld_cy - 0.5
    pool_w  = 6.0
    pool_d  = 4.0
    pool_h  = 0.05  # thin water surface

    # Pool deck (travertine surround)
    bpy.ops.mesh.primitive_plane_add(
        size=1,
        location=(pool_cx, pool_cy, 0.0))
    deck = bpy.context.active_object
    deck.name = "ext_pool_deck"
    deck.scale = (pool_w + 2.0, pool_d + 2.0, 1)
    bpy.ops.object.transform_apply(scale=True)
    deck.data.materials.clear()
    deck.data.materials.append(_get_mat("travertine"))

    # Water surface
    bpy.ops.mesh.primitive_plane_add(
        size=1,
        location=(pool_cx, pool_cy, 0.06))
    pool = bpy.context.active_object
    pool.name = "ext_pool_water"
    pool.scale = (pool_w, pool_d, 1)
    bpy.ops.object.transform_apply(scale=True)
    pool.data.materials.clear()
    m_water, new = _clear_new("ext_water_mat")
    if new:
        bsdf, nodes, links = _bsdf_out(m_water)
        bsdf.inputs["Base Color"].default_value    = (0.05, 0.30, 0.55, 1.0)
        bsdf.inputs["Roughness"].default_value     = 0.05
        bsdf.inputs["Transmission Weight"].default_value = 0.60
        bsdf.inputs["IOR"].default_value           = 1.33
        # Slight emission for water glow
        emit = nodes.new("ShaderNodeEmission")
        emit.location = (0, -200)
        emit.inputs["Color"].default_value    = (0.04, 0.22, 0.45, 1.0)
        emit.inputs["Strength"].default_value = 0.15
        add_mix = nodes.new("ShaderNodeAddShader")
        add_mix.location = (600, -100)
        out_node = None
        for n in nodes:
            if n.type == "OUTPUT_MATERIAL":
                out_node = n; break
        links.new(bsdf.outputs["BSDF"], add_mix.inputs[0])
        links.new(emit.outputs["Emission"], add_mix.inputs[1])
        links.new(add_mix.outputs["Shader"], out_node.inputs["Surface"])
        m_water.blend_method = "BLEND"
    pool.data.materials.append(m_water)

    # 3. Palm trees scattered outside the building
    import random
    random.seed(42)
    palm_positions = [
        (bld_max_x + 2.0, bld_min_y - 4.0),
        (bld_max_x + 7.0, bld_min_y - 2.0),
        (bld_max_x + 9.0, bld_cy + 3.0),
        (bld_max_x + 5.5, bld_max_y + 3.5),
        (bld_cx - 2.0,    bld_min_y - 6.0),
        (bld_cx + 4.0,    bld_min_y - 8.0),
        (bld_min_x - 4.0, bld_cy - 2.0),
        (bld_min_x - 6.0, bld_cy + 4.0),
    ]
    # Build shared frond material once
    m_fronds, frond_new = _clear_new("ext_palm_frond_mat")
    if frond_new:
        bsdf_f, nodes_f, links_f = _bsdf_out(m_fronds)
        # Noise-varied tropical green
        coord_f = nodes_f.new("ShaderNodeTexCoord"); coord_f.location = (-600, 0)
        noise_f = nodes_f.new("ShaderNodeTexNoise");  noise_f.location = (-400, 0)
        noise_f.inputs["Scale"].default_value   = 20.0
        noise_f.inputs["Detail"].default_value  = 8.0
        noise_f.inputs["Roughness"].default_value = 0.7
        cr_f = nodes_f.new("ShaderNodeValToRGB"); cr_f.location = (-200, 0)
        cr_f.color_ramp.elements[0].color = (0.05, 0.22, 0.04, 1.0)
        cr_f.color_ramp.elements[1].color = (0.18, 0.52, 0.08, 1.0)
        links_f.new(coord_f.outputs["Object"], noise_f.inputs["Vector"])
        links_f.new(noise_f.outputs["Fac"],    cr_f.inputs["Fac"])
        links_f.new(cr_f.outputs["Color"],     bsdf_f.inputs["Base Color"])
        bsdf_f.inputs["Roughness"].default_value = 0.75
        bsdf_f.inputs["Subsurface Weight"].default_value = 0.12

    for i, (px, py) in enumerate(palm_positions):
        trunk_h = random.uniform(4.5, 6.5)
        trunk_r = random.uniform(0.10, 0.14)

        # Tapered trunk: wide base, narrower top via two cylinders
        m_trunk, new = _clear_new("ext_palm_trunk_mat")
        if new:
            bsdf, nodes, links = _bsdf_out(m_trunk)
            cr = _wave_colorramp(nodes, links, 8, 1.5,
                                 (0.28, 0.18, 0.08), (0.48, 0.32, 0.16))
            links.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
            bsdf.inputs["Roughness"].default_value = 0.85

        # Lower trunk (full radius)
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=8, radius=trunk_r,
            depth=trunk_h * 0.7,
            location=(px, py, trunk_h * 0.35))
        trunk_lo = bpy.context.active_object
        trunk_lo.name = f"ext_palm{i}_trunk_lo"
        trunk_lo.data.materials.clear()
        trunk_lo.data.materials.append(m_trunk)

        # Upper trunk (tapered to 60% radius, slight lean)
        lean_x = random.uniform(-0.15, 0.15)
        lean_y = random.uniform(-0.15, 0.15)
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=8, radius=trunk_r * 0.6,
            depth=trunk_h * 0.35,
            location=(px + lean_x * 0.5, py + lean_y * 0.5, trunk_h * 0.825))
        trunk_hi = bpy.context.active_object
        trunk_hi.name = f"ext_palm{i}_trunk_hi"
        trunk_hi.data.materials.clear()
        trunk_hi.data.materials.append(m_trunk)

        # Crown fronds: 10 elongated planes fanning out from trunk top
        # Each frond: 2.8m long, 0.25m wide, angled 35° down, rotated around Z
        frond_base_z = trunk_h + 0.3
        n_fronds = 10
        for j in range(n_fronds):
            az = math.radians(j * (360.0 / n_fronds) + random.uniform(-8, 8))
            # Frond as primitive plane, scaled and rotated
            bpy.ops.mesh.primitive_plane_add(
                size=1.0,
                location=(px + math.sin(az) * 0.4,
                           py + math.cos(az) * 0.4,
                           frond_base_z))
            frond = bpy.context.active_object
            frond.name = f"ext_palm{i}_frond{j}"
            # Scale to frond shape
            frond.scale = (0.22, 2.8, 1.0)
            bpy.ops.object.transform_apply(scale=True)
            # Tilt down 38° and point outward (az around Z, -38° around X)
            frond.rotation_euler = (
                math.radians(-38) + random.uniform(-5, 5) * math.pi / 180,
                0.0,
                az + math.pi / 2
            )
            # Shift frond tip further out after rotation
            frond.location = (
                px + math.sin(az) * 0.5,
                py + math.cos(az) * 0.5,
                frond_base_z
            )
            frond.data.materials.clear()
            frond.data.materials.append(m_fronds)

        # Small coconut cluster at crown center
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.18, segments=8, ring_count=6,
            location=(px, py, frond_base_z - 0.1))
        nuts = bpy.context.active_object
        nuts.name = f"ext_palm{i}_nuts"
        m_nuts, new_n = _clear_new("ext_palm_nuts_mat")
        if new_n:
            bsdf_n, _, _ = _bsdf_out(m_nuts)
            bsdf_n.inputs["Base Color"].default_value = (0.25, 0.45, 0.12, 1.0)
            bsdf_n.inputs["Roughness"].default_value  = 0.90
        nuts.data.materials.clear()
        nuts.data.materials.append(m_nuts)

    # 4. Building facade panels (exterior stucco faces visible from outside)
    facade_h = WALL_H * 2.0  # two-storey facade height

    # South facade (covers south face of whole building)
    bld_w = bld_max_x - bld_min_x
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(bld_cx, bld_min_y - WALL_T / 2, facade_h / 2))
    fsouth = bpy.context.active_object
    fsouth.name = "ext_facade_south"
    fsouth.scale = (bld_w + WALL_T * 2, WALL_T, facade_h)
    bpy.ops.object.transform_apply(scale=True)
    fsouth.data.materials.clear()
    fsouth.data.materials.append(_get_mat("stucco_warm"))

    # East facade (covers east face — the terraza exterior wall)
    bld_d = bld_max_y - bld_min_y
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(bld_max_x + WALL_T / 2, bld_cy, facade_h / 2))
    feast = bpy.context.active_object
    feast.name = "ext_facade_east"
    feast.scale = (WALL_T, bld_d + WALL_T * 2, facade_h)
    bpy.ops.object.transform_apply(scale=True)
    feast.data.materials.clear()
    feast.data.materials.append(_get_mat("stucco_warm"))

    # West facade
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(bld_min_x - WALL_T / 2, bld_cy, facade_h / 2))
    fwest = bpy.context.active_object
    fwest.name = "ext_facade_west"
    fwest.scale = (WALL_T, bld_d + WALL_T * 2, facade_h)
    bpy.ops.object.transform_apply(scale=True)
    fwest.data.materials.clear()
    fwest.data.materials.append(_get_mat("stucco_warm"))

    print(f"  Exterior environment: ground + pool + {len(palm_positions)} palms + facade panels")


# ── 360° camera setup ─────────────────────────────────────────────────────────
cam_data = bpy.data.cameras.new("PanoCam")
cam_data.type         = "PANO"
cam_data.panorama_type = "EQUIRECTANGULAR"
cam_obj = bpy.data.objects.new("PanoCam", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# ── Build all rooms + lights ──────────────────────────────────────────────────
print(f"\nBuilding: {cfg.get('name', 'apartment')}")
rooms = cfg.get("rooms", [])
for room in rooms:
    build_room(room)
add_exterior_environment(cfg)
add_room_lights(rooms)
print(f"Rooms built: {len(rooms)}")

for room in rooms:
    place_furniture(room["id"], room["x"], room["y"], room["w"], room["d"], room.get("z_offset", 0.0))
print("Furniture placed")

# ── Per-room render loop ──────────────────────────────────────────────────────
print(f"\nRendering {len(rooms)} panoramas → {output_dir}")
for room in rooms:
    rid   = room["id"]
    x, y  = room["x"], room["y"]
    w, d  = room["w"], room["d"]
    z_off = room.get("z_offset", 0.0)

    cam_x = x + w / 2
    cam_y = y + d / 2
    cam_z = 1.65 + z_off

    cam_obj.location       = (cam_x, cam_y, cam_z)
    cam_obj.rotation_euler = (math.radians(90), 0.0, 0.0)

    out_path = os.path.join(output_dir, f"{rid}.jpg")
    scene.render.filepath = out_path

    print(f"  Rendering {rid} at ({cam_x:.2f}, {cam_y:.2f}, {cam_z:.2f}) ...")
    bpy.ops.render.render(write_still=True)
    print(f"  → {out_path}")

print(f"\nDONE — {len(rooms)} panoramas written to {output_dir}")
