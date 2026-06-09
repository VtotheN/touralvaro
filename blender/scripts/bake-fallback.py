"""Bake fallback manual (sin The Lightmapper) — abre la escena, hace bake
con Cycles, y exporta a viewer/public/models/escena-demo-baked.glb.

Reutiliza la lógica de `bake-lightmap.py` (preserva ese archivo intacto).
Se invoca SOLO si `bake-con-lightmapper.py` produce blender/.tlm-failed.

Uso:
    /Applications/Blender.app/Contents/MacOS/Blender -b \
        -P blender/scripts/bake-fallback.py
"""

import bpy
import math
import os
import sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLEND_PATH = os.path.join(WORKSPACE, "blender", "escena-demo.blend")
GLB_OUT = os.path.join(WORKSPACE, "viewer", "public", "models", "escena-demo-baked.glb")
LIGHTMAP_DIR = os.path.join(WORKSPACE, "blender", "lightmaps")

LIGHTMAP_RES = 512
SAMPLES = 64

os.makedirs(LIGHTMAP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(GLB_OUT), exist_ok=True)

# 1) Abrir la escena
if not os.path.exists(BLEND_PATH):
    print(f"[bake-fallback] ERROR: no existe {BLEND_PATH}", file=sys.stderr)
    sys.exit(1)
bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.cycles.device = "CPU"

bake_targets = [
    o for o in scene.objects
    if o.type == "MESH" and not o.hide_render
]
print(f"[bake-fallback] {len(bake_targets)} meshes")

# 2) UV2 + nodo Image Texture en cada material
for obj in bake_targets:
    bpy.context.view_layer.objects.active = obj

    # UV2
    if "UVMap_Lightmap" not in obj.data.uv_layers:
        uv2 = obj.data.uv_layers.new(name="UVMap_Lightmap")
        obj.data.uv_layers.active = uv2

        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        try:
            bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
        except Exception as e:
            print(f"[bake-fallback] smart_project failed on {obj.name}: {e!r}")
        bpy.ops.object.mode_set(mode="OBJECT")
        obj.select_set(False)

    # Imagen target
    img_name = f"LM_{obj.name}"
    img = bpy.data.images.get(img_name)
    if not img:
        img = bpy.data.images.new(
            name=img_name,
            width=LIGHTMAP_RES,
            height=LIGHTMAP_RES,
            alpha=False,
            float_buffer=True,
        )

    # Inyectar nodo en TODOS los materiales del objeto
    if obj.data.materials:
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                continue
            nt = mat.node_tree
            # Evitar duplicar el nodo
            existing = next(
                (n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image == img),
                None,
            )
            if existing:
                tex = existing
            else:
                tex = nt.nodes.new("ShaderNodeTexImage")
                tex.image = img
            # Marcar como activo para el bake
            for n in nt.nodes:
                n.select = False
            tex.select = True
            nt.nodes.active = tex


# 3) Seleccionar todos y bake (DIFFUSE direct+indirect)
bpy.ops.object.select_all(action="DESELECT")
for obj in bake_targets:
    obj.select_set(True)
if bake_targets:
    bpy.context.view_layer.objects.active = bake_targets[0]

print("[bake-fallback] Bakeando...")
try:
    bpy.ops.object.bake(
        type="DIFFUSE",
        pass_filter={"INDIRECT", "DIRECT"},
        use_clear=True,
        margin=4,
    )
except Exception as e:
    print(f"[bake-fallback] bake error: {e!r}")
    sys.exit(2)

# 4) Guardar imágenes como PNG (más portable que EXR para glTF)
for obj in bake_targets:
    img = bpy.data.images.get(f"LM_{obj.name}")
    if not img:
        continue
    path = os.path.join(LIGHTMAP_DIR, f"LM_{obj.name}.png")
    img.filepath_raw = path
    img.file_format = "PNG"
    try:
        img.save()
        print(f"[bake-fallback] {path}")
    except Exception as e:
        print(f"[bake-fallback] WARN no se guardó {path}: {e!r}")

# 5) Re-conectar el nodo de lightmap como Base Color para que el GLB
#    incorpore el baked lighting visible (los Principled BSDF actuales).
for obj in bake_targets:
    img = bpy.data.images.get(f"LM_{obj.name}")
    if not img or not obj.data.materials:
        continue
    for mat in obj.data.materials:
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        tex_node = next(
            (n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image == img),
            None,
        )
        if not tex_node:
            continue
        bsdf = next(
            (n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"),
            None,
        )
        if not bsdf:
            continue
        # Conectar imagen al Base Color
        try:
            nt.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
        except Exception as e:
            print(f"[bake-fallback] link warning {mat.name}: {e!r}")

# 6) Guardar el .blend con cambios (opcional, para inspección)
try:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    print(f"[bake-fallback] .blend guardado: {BLEND_PATH}")
except Exception as e:
    print(f"[bake-fallback] WARN no se pudo re-guardar: {e!r}")

# 7) Exportar GLB
print(f"[bake-fallback] Exportando GLB a {GLB_OUT}")
bpy.ops.export_scene.gltf(
    filepath=GLB_OUT,
    export_format="GLB",
    export_apply=True,
    export_yup=True,
    export_cameras=False,
    export_lights=False,
    export_materials="EXPORT",
    export_image_format="AUTO",
    export_texcoords=True,
    export_normals=True,
    export_tangents=True,
)

if not os.path.exists(GLB_OUT):
    print(f"[bake-fallback] ERROR: no se generó {GLB_OUT}", file=sys.stderr)
    sys.exit(3)

print(f"[bake-fallback] OK: {GLB_OUT} ({os.path.getsize(GLB_OUT)} bytes)")
