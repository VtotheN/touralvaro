"""
gen_apartment.py — Procedural apartment generator for touralvaro pipeline.
Usage: blender --background --python gen_apartment.py -- <config.json> <output.glb>
Config JSON schema:
{
  "name": "proyecto-x",
  "ceiling_height": 2.8,
  "rooms": [
    {
      "id": "sala",
      "label": "Sala",
      "x": 0, "y": 0,        // origin corner in meters
      "w": 5.0, "d": 4.0,    // width, depth in meters
      "doors": [             // optional
        {"wall": "right", "offset": 0.5, "width": 0.9, "height": 2.1}
      ],
      "windows": [           // optional
        {"wall": "front", "offset": 1.0, "width": 1.8, "height": 1.2, "sill": 0.9}
      ]
    }
  ]
}
"""
import bpy, sys, json, os, math, urllib.request

# ── Args ──────────────────────────────────────────────────────────────────────
argv = sys.argv
try:
    sep = argv.index("--")
    config_path = argv[sep + 1]
    output_path = argv[sep + 2]
except (ValueError, IndexError):
    config_path = "/tmp/apartment_config.json"
    output_path = "/tmp/apartment_output.glb"

with open(config_path) as f:
    cfg = json.load(f)

WALL_H = cfg.get("ceiling_height", 2.8)
WALL_T = 0.12  # wall thickness

# ── Reset scene ───────────────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
for obj in bpy.data.objects:
    bpy.data.objects.remove(obj, do_unlink=True)

# ── Texture cache dir (Polyhaven CC0 PBR) ────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
TEX_CACHE    = os.path.join(SCRIPT_DIR, "..", "pbr_textures")
POLYHAVEN    = "https://api.polyhaven.com"

def ensure_texture(ph_id, size="1k"):
    """Download Polyhaven PBR set if not cached. Returns dir path or None."""
    local = os.path.join(TEX_CACHE, ph_id)
    if os.path.isdir(local) and any(f.endswith(".jpg") for f in os.listdir(local)):
        return local
    os.makedirs(local, exist_ok=True)
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen(f"{POLYHAVEN}/files/{ph_id}", timeout=15) as r:
            files = _json.loads(r.read())
        map_keys = {"Diffuse": "diffuse", "nor_gl": "normal", "Roughness": "roughness", "AO": "ao"}
        for api_key, local_name in map_keys.items():
            try:
                url = files[api_key][size]["jpg"]["url"]
                urllib.request.urlretrieve(url, os.path.join(local, f"{local_name}.jpg"))
                print(f"    ↓ {ph_id}/{local_name}.jpg")
            except Exception:
                pass
        return local
    except Exception as e:
        print(f"  Polyhaven error {ph_id}: {e}")
        return None

# ── Material library ──────────────────────────────────────────────────────────
def make_mat(name, color, roughness=0.85, metallic=0.0, emission=None):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    links = m.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 2.0
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m

def make_pbr_mat(name, tex_dir, tile_scale=2.0, roughness=0.7):
    """Create PBR material from Polyhaven texture directory."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    links = m.node_tree.links
    nodes.clear()
    out  = nodes.new("ShaderNodeOutputMaterial"); out.location  = (600, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (300, 0)
    bsdf.inputs["Roughness"].default_value = roughness
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    if tex_dir and os.path.isdir(tex_dir):
        coord   = nodes.new("ShaderNodeTexCoord"); coord.location   = (-600, 0)
        mapping = nodes.new("ShaderNodeMapping");  mapping.location = (-400, 0)
        mapping.inputs["Scale"].default_value = (tile_scale, tile_scale, tile_scale)
        links.new(coord.outputs["UV"], mapping.inputs["Vector"])

        def load_img(fname, colorspace="sRGB"):
            p = os.path.join(tex_dir, fname)
            if not os.path.exists(p): return None
            img = bpy.data.images.load(p)
            img.colorspace_settings.name = colorspace
            return img

        diff = load_img("diffuse.jpg", "sRGB")
        norm = load_img("normal.jpg",  "Non-Color")
        roug = load_img("roughness.jpg", "Non-Color")
        ao   = load_img("ao.jpg",      "Non-Color")

        if diff:
            tex = nodes.new("ShaderNodeTexImage"); tex.location = (-200, 300)
            tex.image = diff
            links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
            if ao:
                ao_tex = nodes.new("ShaderNodeTexImage"); ao_tex.location = (-200, 0)
                ao_tex.image = ao
                mix = nodes.new("ShaderNodeMixRGB"); mix.location = (0, 200)
                mix.blend_type = "MULTIPLY"; mix.inputs["Fac"].default_value = 0.8
                links.new(mapping.outputs["Vector"], ao_tex.inputs["Vector"])
                links.new(tex.outputs["Color"],    mix.inputs[1])
                links.new(ao_tex.outputs["Color"], mix.inputs[2])
                links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
            else:
                links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

        if roug:
            tex = nodes.new("ShaderNodeTexImage"); tex.location = (-200, -200)
            tex.image = roug
            links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
            links.new(tex.outputs["Color"], bsdf.inputs["Roughness"])

        if norm:
            tex  = nodes.new("ShaderNodeTexImage"); tex.location  = (-200, -500)
            nmap = nodes.new("ShaderNodeNormalMap"); nmap.location = (0,    -400)
            tex.image = norm
            links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
            links.new(tex.outputs["Color"],   nmap.inputs["Color"])
            links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    else:
        bsdf.inputs["Base Color"].default_value = (0.52, 0.38, 0.22, 1.0)

    return m

# Download key textures (non-blocking: if offline, falls back to solid color)
print("Ensuring PBR textures...")
TEX_WOOD_FLOOR = ensure_texture("wood_floor_deck")
TEX_PARQUET    = ensure_texture("parquet_floor")
TEX_CONCRETE   = ensure_texture("concrete_wall_005")

# Room-type to floor texture mapping
FLOOR_TEX = {
    "sala":    TEX_WOOD_FLOOR,
    "comedor": TEX_WOOD_FLOOR,
    "master":  TEX_WOOD_FLOOR,
    "hab":     TEX_WOOD_FLOOR,
    "hab2":    TEX_WOOD_FLOOR,
    "pasillo": TEX_CONCRETE,
    "cocina":  TEX_CONCRETE,
    "baño":    TEX_CONCRETE,
    "_default": TEX_WOOD_FLOOR,
}

def get_floor_tex(room_id):
    for key, tex in FLOOR_TEX.items():
        if key in room_id.lower():
            return tex
    return FLOOR_TEX["_default"]

MATS = {
    "floor_wood":    None,  # created per-room with PBR
    "floor_tile":    None,
    "wall_white":    make_mat("wall_white",    (0.95, 0.94, 0.92), 0.88),
    "wall_concrete": make_mat("wall_concrete", (0.70, 0.68, 0.65), 0.92),
    "ceiling":       make_mat("ceiling",       (0.99, 0.99, 0.98), 0.96),
    "door_wood":     make_mat("door_wood",     (0.45, 0.30, 0.18), 0.55),
    "window_frame":  make_mat("window_frame",  (0.72, 0.70, 0.68), 0.20),
    "glass":         make_mat("glass",         (0.80, 0.90, 1.00), 0.05, 0.0),
    "baseboard":     make_mat("baseboard",     (0.99, 0.99, 0.98), 0.30),
}
glass_mat = MATS["glass"]
glass_mat.blend_method = "BLEND"
glass_mat.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.12

# ── Mesh helpers ──────────────────────────────────────────────────────────────
def add_plane(name, w, d, x, y, z, rx=0, ry=0, rz=0, mat_name="wall_white"):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x + w/2, y + d/2, z))
    o = bpy.context.active_object
    o.name = name
    o.scale = (w, d, 1)
    o.rotation_euler = (rx, ry, rz)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    if mat_name in MATS:
        o.data.materials.append(MATS[mat_name])
    # use_auto_smooth removed in Blender 4.1+; shade_flat is correct for arch geometry
    return o

def add_box(name, w, d, h, x, y, z, mat_name="wall_white"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x + w/2, y + d/2, z + h/2))
    o = bpy.context.active_object
    o.name = name
    o.scale = (w, d, h)
    bpy.ops.object.transform_apply(scale=True)
    if mat_name in MATS:
        o.data.materials.append(MATS[mat_name])
    return o

# ── Boolean cutter ────────────────────────────────────────────────────────────
def cut_opening(target_obj, x, y, z, w, d, h):
    """Boolean-subtract a box from target_obj to create door/window openings."""
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

# ── Wall builder with openings ────────────────────────────────────────────────
def build_wall(name, x0, y0, x1, y1, height, openings=None, mat_name="wall_white"):
    """Build a wall segment with optional door/window cutouts."""
    dx = x1 - x0
    dy = y1 - y0
    length = math.sqrt(dx*dx + dy*dy)
    angle = math.atan2(dy, dx)
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2

    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, height/2))
    wall = bpy.context.active_object
    wall.name = name
    wall.scale = (length, WALL_T, height)
    wall.rotation_euler = (0, 0, angle)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    wall.data.materials.append(MATS[mat_name])

    if openings:
        for op in openings:
            ow = op.get("width", 0.9)
            oh = op.get("height", 2.1)
            sill = op.get("sill", 0.0)
            offset = op.get("offset", 0.5)
            # Local-space cut along wall length
            local_x = offset - length/2
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            ox = cx + cos_a * local_x - sin_a * 0
            oy = cy + sin_a * local_x + cos_a * 0
            cut_opening(wall, ox - ow/2, oy - WALL_T, sill, ow, WALL_T*3, oh)

            # Add door/window geometry
            if sill == 0:
                # Door frame
                add_box(f"{name}_door_frame", ow + 0.08, 0.08, oh + 0.05,
                        ox - (ow+0.08)/2, oy - 0.04, 0, "window_frame")
                # Door leaf
                add_box(f"{name}_door_leaf", ow - 0.04, 0.04, oh - 0.04,
                        ox - (ow-0.04)/2, oy - 0.02, 0.02, "door_wood")
            else:
                # Window sill
                add_box(f"{name}_win_sill", ow + 0.1, 0.15, 0.04,
                        ox - (ow+0.1)/2, oy - 0.075, sill - 0.02, "window_frame")
                # Window glass
                add_box(f"{name}_win_glass", ow - 0.06, 0.02, oh - 0.06,
                        ox - (ow-0.06)/2, oy - 0.01, sill + 0.03, "glass")
                # Window frame — 4 thin strips (top, bottom, left, right), not a solid plate
                ft = 0.05  # strip thickness
                fd = 0.06  # depth
                add_box(f"{name}_win_frame_t", ow, fd, ft,
                        ox - ow/2, oy - fd/2, sill + oh - ft, "window_frame")
                add_box(f"{name}_win_frame_b", ow, fd, ft,
                        ox - ow/2, oy - fd/2, sill, "window_frame")
                add_box(f"{name}_win_frame_l", ft, fd, oh,
                        ox - ow/2, oy - fd/2, sill, "window_frame")
                add_box(f"{name}_win_frame_r", ft, fd, oh,
                        ox + ow/2 - ft, oy - fd/2, sill, "window_frame")
    return wall

# ── Room builder ──────────────────────────────────────────────────────────────
waypoints = []

def build_room(room):
    rid = room["id"]
    label = room.get("label", rid)
    x, y = room["x"], room["y"]
    w, d = room["w"], room["d"]
    doors = room.get("doors", [])
    windows = room.get("windows", [])
    is_kitchen = "cocina" in rid.lower() or "kitchen" in rid.lower()
    is_bathroom = "baño" in rid.lower() or "bath" in rid.lower()

    # PBR floor material per room
    floor_tex = get_floor_tex(rid)
    pbr_floor_name = f"floor_{rid}"
    tile_scale = 1.5 if (is_kitchen or is_bathroom) else 2.5
    floor_pbr = make_pbr_mat(pbr_floor_name, floor_tex, tile_scale=tile_scale, roughness=0.62)
    MATS[pbr_floor_name] = floor_pbr

    # Floor with UV smart project for texture
    floor_obj = add_plane(f"{rid}_floor", w, d, x, y, 0, mat_name="wall_white")
    floor_obj.data.materials.clear()
    floor_obj.data.materials.append(floor_pbr)
    # UV unwrap floor
    bpy.context.view_layer.objects.active = floor_obj
    bpy.ops.object.select_all(action='DESELECT')
    floor_obj.select_set(True)
    bpy.ops.object.editmode_toggle()
    bpy.ops.uv.smart_project(angle_limit=66, island_margin=0.0)
    bpy.ops.object.editmode_toggle()

    # Ceiling
    add_plane(f"{rid}_ceiling", w, d, x, y, WALL_H, rx=math.pi, mat_name="ceiling")

    # Baseboard (decorative trim at floor level)
    add_box(f"{rid}_base_s", w, 0.01, 0.10, x, y, 0, "baseboard")
    add_box(f"{rid}_base_n", w, 0.01, 0.10, x, y + d - 0.01, 0, "baseboard")
    add_box(f"{rid}_base_w", 0.01, d, 0.10, x, y, 0, "baseboard")
    add_box(f"{rid}_base_e", 0.01, d, 0.10, x + w - 0.01, y, 0, "baseboard")

    WALL_ALIAS = {"front": "south", "back": "north", "left": "west", "right": "east",
                  "south": "south", "north": "north", "west": "west", "east": "east"}
    wall_openings = {"south": [], "north": [], "west": [], "east": []}
    for door in doors:
        key = WALL_ALIAS.get(door["wall"], "south")
        wall_openings[key].append({**door, "sill": 0})
    for win in windows:
        key = WALL_ALIAS.get(win["wall"], "south")
        wall_openings[key].append({**win, "sill": win.get("sill", 0.9)})

    build_wall(f"{rid}_wall_s", x, y, x+w, y, WALL_H, wall_openings["south"])
    build_wall(f"{rid}_wall_n", x, y+d, x+w, y+d, WALL_H, wall_openings["north"])
    build_wall(f"{rid}_wall_w", x, y, x, y+d, WALL_H, wall_openings["west"])
    build_wall(f"{rid}_wall_e", x+w, y, x+w, y+d, WALL_H, wall_openings["east"])

    # Waypoint at center, eye height
    cx = x + w/2
    cy = y + d/2
    waypoints.append({
        "id": rid,
        "label": label,
        "position": [round(cx, 3), 1.8, round(-cy, 3)]  # Blender→Three.js: Y→-Z
    })
    print(f"  Built room: {rid} ({w}×{d}m)")

# ── Lighting (auto per room) ──────────────────────────────────────────────────
def add_room_lights(rooms):
    for room in rooms:
        x, y = room["x"], room["y"]
        w, d = room["w"], room["d"]
        cx = x + w/2
        cy = y + d/2
        area = w * d
        # POINT lights (GLTF-exportable; AREA not supported by exporter)
        bpy.ops.object.light_add(type="POINT", location=(cx, cy, WALL_H - 0.3))
        light = bpy.context.active_object
        light.name = f"light_{room['id']}"
        light.data.energy = area * 250  # candela, proportional to room area
        light.data.shadow_soft_size = min(w, d) * 0.4
        light.data.color = (1.0, 0.97, 0.92)  # warm white

# ── Sun / ambient ─────────────────────────────────────────────────────────────
bpy.ops.object.light_add(type="SUN", location=(5, 5, 8))
sun = bpy.context.active_object
sun.data.energy = 2.0
sun.data.angle = 0.2
sun.rotation_euler = (math.radians(45), 0, math.radians(30))

if bpy.context.scene.world is None:
    bpy.context.scene.world = bpy.data.worlds.new("World")
world = bpy.context.scene.world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg is None:
    bg = world.node_tree.nodes.new("ShaderNodeBackground")
bg.inputs["Color"].default_value = (0.6, 0.7, 1.0, 1.0)
bg.inputs["Strength"].default_value = 0.4

# ── Build all rooms ───────────────────────────────────────────────────────────
print(f"\nBuilding: {cfg.get('name', 'apartment')}")
rooms = cfg.get("rooms", [])
for room in rooms:
    build_room(room)
add_room_lights(rooms)
print(f"Rooms built: {len(rooms)}")

# ── Export GLB ────────────────────────────────────────────────────────────────
os.makedirs(os.path.dirname(output_path), exist_ok=True) if os.path.dirname(output_path) else None
bpy.ops.export_scene.gltf(
    filepath=output_path,
    export_format="GLB",
    export_lights=True,
    export_materials="EXPORT",
    export_apply=True,
    export_draco_mesh_compression_enable=True,
    export_draco_mesh_compression_level=6,
)
size_kb = os.path.getsize(output_path) / 1024
print(f"\nGLB exported: {output_path} ({size_kb:.1f} KB)")

# ── Export waypoints ──────────────────────────────────────────────────────────
wp_path = output_path.replace(".glb", "_waypoints.json")
with open(wp_path, "w") as f:
    json.dump(waypoints, f, indent=2)
print(f"Waypoints: {wp_path} ({len(waypoints)} points)")
print("DONE")
