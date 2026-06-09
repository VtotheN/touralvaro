"""Skeleton para bake de lightmap manual (sin The Lightmapper addon).

Este script se ejecuta DENTRO de Blender con la escena abierta:
    Edit → Preferences → Add-ons → enable "glTF" si no está
    Texto editor en Blender → abrir este archivo → Run Script

O headless con una escena guardada:
    /Applications/Blender.app/Contents/MacOS/Blender escena-demo.blend \
        -b -P blender/scripts/bake-lightmap.py

Recomendación real: instalar The Lightmapper (Naxela) y usarlo con GUI.
Este script es para cuando no se tiene el addon disponible.
"""

import bpy
import os

LIGHTMAP_RES = 1024
SAMPLES = 256
OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "blender", "lightmaps"
)
os.makedirs(OUT_DIR, exist_ok=True)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True

bake_targets = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render]

for obj in bake_targets:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # 1) Generar UV2 si no existe
    if "UVMap_Lightmap" not in obj.data.uv_layers:
        uv2 = obj.data.uv_layers.new(name="UVMap_Lightmap")
        obj.data.uv_layers.active = uv2
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=66, island_margin=0.02)
        bpy.ops.object.mode_set(mode="OBJECT")

    # 2) Crear imagen target
    img_name = f"LM_{obj.name}"
    img = bpy.data.images.get(img_name) or bpy.data.images.new(
        name=img_name, width=LIGHTMAP_RES, height=LIGHTMAP_RES, alpha=False, float_buffer=True
    )

    # 3) Inyectar nodo Image Texture en el material
    if obj.data.materials:
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                continue
            nt = mat.node_tree
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = img
            tex.select = True
            nt.nodes.active = tex

    obj.select_set(False)

# 4) Bake
for obj in bake_targets:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

bpy.ops.object.bake(
    type="DIFFUSE",
    pass_filter={"INDIRECT", "DIRECT"},
    use_clear=True,
    margin=4,
)

# 5) Guardar imágenes
for obj in bake_targets:
    img = bpy.data.images.get(f"LM_{obj.name}")
    if not img:
        continue
    path = os.path.join(OUT_DIR, f"LM_{obj.name}.exr")
    img.filepath_raw = path
    img.file_format = "OPEN_EXR"
    img.save()
    print(f"[bake] {path}")

print("[bake] hecho. Conecta cada LM_{nombre}.exr como lightMap en el material correspondiente.")
