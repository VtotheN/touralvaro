"""
instant_bake.py — Automated lighting bake for touralvaro pipeline.
Usage: blender --background --python instant_bake.py -- <input.glb> <output.glb>
       [--samples 128] [--texture-size 1024] [--margin 4]
Bakes combined GI+shadows+lighting to vertex color or lightmap texture.
Output: GLB with baked lighting, ready for Three.js viewer.
"""
import bpy, sys, os, math

# ── Args ──────────────────────────────────────────────────────────────────────
argv = sys.argv
try:
    sep = argv.index("--")
    input_path  = argv[sep + 1]
    output_path = argv[sep + 2]
    samples = int(argv[sep + 3]) if len(argv) > sep + 3 else 128
    tex_size = int(argv[sep + 4]) if len(argv) > sep + 4 else 1024
except (ValueError, IndexError):
    print("Usage: blender --bg --python instant_bake.py -- input.glb output.glb [samples] [tex_size]")
    sys.exit(1)

print(f"\nINSTANT-BAKE: {input_path}")
print(f"Samples: {samples} | Texture: {tex_size}×{tex_size}")

# ── Load scene ────────────────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
ext = os.path.splitext(input_path)[1].lower()
if ext == ".glb" or ext == ".gltf":
    bpy.ops.import_scene.gltf(filepath=input_path)
elif ext == ".blend":
    bpy.ops.wm.open_mainfile(filepath=input_path)
else:
    print(f"ERROR: unsupported format {ext}")
    sys.exit(1)

# ── Cycles setup ─────────────────────────────────────────────────────────────
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = samples
scene.cycles.use_denoising = True
scene.cycles.device = "CPU"  # GPU fallback handled automatically

# Try GPU if available
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"  # macOS
    prefs.get_devices()
    for dev in prefs.devices:
        dev.use = True
    scene.cycles.device = "GPU"
    print("Using GPU (Metal)")
except Exception:
    print("Using CPU")

# ── Collect all mesh objects ───────────────────────────────────────────────────
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
print(f"Meshes to bake: {len(meshes)}")

if not meshes:
    print("ERROR: no meshes found")
    sys.exit(1)

# ── UV unwrap all meshes ──────────────────────────────────────────────────────
bpy.ops.object.select_all(action="DESELECT")
for obj in meshes:
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.select_set(False)
print("UV unwrap done")

# ── Create lightmap textures per object ───────────────────────────────────────
lightmap_images = {}
for obj in meshes:
    tex_name = f"LM_{obj.name}"
    img = bpy.data.images.new(tex_name, width=tex_size, height=tex_size)
    img.colorspace_settings.name = "Non-Color"
    lightmap_images[obj.name] = img

    # Add image texture node to each material (used as bake target)
    for slot in obj.material_slots:
        mat = slot.material
        if mat is None:
            continue
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        # Remove existing bake nodes
        for n in [n for n in nodes if n.name == "BAKE_TARGET"]:
            nodes.remove(n)
        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.name = "BAKE_TARGET"
        tex_node.image = img
        # Select it (bake writes to selected image node)
        nodes.active = tex_node

print("Lightmap textures created")

# ── Bake ──────────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action="DESELECT")

for i, obj in enumerate(meshes):
    print(f"  Baking [{i+1}/{len(meshes)}]: {obj.name}")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    try:
        bpy.ops.object.bake(
            type="COMBINED",
            use_pass_direct=True,
            use_pass_indirect=True,
            use_pass_color=True,
            use_selected_to_active=False,
            margin=4,
        )
    except Exception as e:
        print(f"    SKIP (bake error): {e}")

    obj.select_set(False)

print("Baking complete")

# ── Wire lightmap into material (replace with baked emission) ─────────────────
for obj in meshes:
    img = lightmap_images[obj.name]
    for slot in obj.material_slots:
        mat = slot.material
        if mat is None:
            continue
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        bake_node = nodes.get("BAKE_TARGET")
        if bake_node is None:
            continue

        # Find or create output
        out_node = next((n for n in nodes if n.type == "OUTPUT_MATERIAL"), None)
        if out_node is None:
            continue

        # Simple lightmap mix: multiply original color by baked light
        bsdf_node = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf_node:
            mix = nodes.new("ShaderNodeMixRGB")
            mix.blend_type = "MULTIPLY"
            mix.inputs["Fac"].default_value = 0.8

            # Get original base color input
            base_color = bsdf_node.inputs["Base Color"]
            if base_color.links:
                links.new(base_color.links[0].from_socket, mix.inputs["Color1"])
            else:
                mix.inputs["Color1"].default_value = base_color.default_value

            links.new(bake_node.outputs["Color"], mix.inputs["Color2"])
            links.new(mix.outputs["Color"], bsdf_node.inputs["Base Color"])

print("Lightmap wired into materials")

# ── Export baked GLB ──────────────────────────────────────────────────────────
bpy.ops.export_scene.gltf(
    filepath=output_path,
    export_format="GLB",
    export_lights=False,  # baked — no need for realtime lights
    export_materials="EXPORT",
    export_apply=True,
    export_draco_mesh_compression_enable=True,
    export_draco_mesh_compression_level=6,
)

size_kb = os.path.getsize(output_path) / 1024
print(f"\nBAKED GLB: {output_path} ({size_kb:.1f} KB)")
print("DONE — set 'baked: true' in scenes.js for this scene")
