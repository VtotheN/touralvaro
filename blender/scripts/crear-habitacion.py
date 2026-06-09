"""Genera una habitación demo con materiales PBR y la exporta a glTF.

Uso (desde la raíz del workspace):
    /Applications/Blender.app/Contents/MacOS/Blender -b \
        -P blender/scripts/crear-habitacion.py

Salidas:
    blender/escena-demo.blend
    viewer/public/models/escena-demo.glb
"""

import bpy
import math
import os
import sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLEND_OUT = os.path.join(WORKSPACE, "blender", "escena-demo.blend")
GLTF_OUT = os.path.join(WORKSPACE, "viewer", "public", "models", "escena-demo.glb")

# ---------------------------------------------------------------------------
# 1. Escena limpia
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1.0

# Cycles para futura compatibilidad con bake
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 32  # demo rápido

# ---------------------------------------------------------------------------
# 2. Materiales PBR
# ---------------------------------------------------------------------------
def make_pbr(name, base_color, roughness=0.7, metallic=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return mat


M_FLOOR = make_pbr("Piso_Madera", (0.32, 0.20, 0.13), roughness=0.55)
M_WALL = make_pbr("Pared", (0.92, 0.89, 0.83), roughness=0.92)
M_CEIL = make_pbr("Techo", (0.96, 0.95, 0.92), roughness=0.95)
M_TABLE = make_pbr("Madera_Mesa", (0.45, 0.27, 0.15), roughness=0.4)
M_SOFA = make_pbr("Sofa_Tela", (0.17, 0.24, 0.31), roughness=0.85)
M_WINDOW = make_pbr("Vidrio", (0.95, 0.97, 1.0), roughness=0.05, metallic=0.0)

# ---------------------------------------------------------------------------
# 3. Geometría
# ---------------------------------------------------------------------------
W, D, H = 6.0, 5.0, 2.8  # ancho, profundidad, altura

def add_plane(name, size_x, size_y, location, rotation, material):
    bpy.ops.mesh.primitive_plane_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size_x, size_y, 1)
    obj.rotation_euler = rotation
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.data.materials.append(material)
    return obj


def add_box(name, sx, sy, sz, location, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.data.materials.append(material)
    return obj


add_plane("Piso", W, D, (0, 0, 0), (0, 0, 0), M_FLOOR)
add_plane("Techo", W, D, (0, 0, H), (math.pi, 0, 0), M_CEIL)
add_plane("Pared_N", W, H, (0, D / 2, H / 2), (math.pi / 2, 0, 0), M_WALL)
add_plane("Pared_S", W, H, (0, -D / 2, H / 2), (-math.pi / 2, 0, 0), M_WALL)
add_plane("Pared_E", D, H, (W / 2, 0, H / 2), (math.pi / 2, 0, -math.pi / 2), M_WALL)
add_plane("Pared_O", D, H, (-W / 2, 0, H / 2), (math.pi / 2, 0, math.pi / 2), M_WALL)

# Ventana — recortar visualmente con un plano de vidrio + boolean simulado por offset
ventana = add_plane("Ventana", 1.8, 1.2, (W / 2 - 0.01, 0, 1.4), (math.pi / 2, 0, -math.pi / 2), M_WINDOW)

# Mesa centro
add_box("Mesa_Tablero", 1.4, 0.8, 0.05, (0, 0, 0.75), M_TABLE)
for x in (-0.6, 0.6):
    for y in (-0.3, 0.3):
        add_box(f"Pata_{x}_{y}", 0.05, 0.05, 0.75, (x, y, 0.375), M_TABLE)

# Sofá
add_box("Sofa_Base", 2.0, 0.9, 0.4, (-1.5, -1.5, 0.2), M_SOFA)
add_box("Sofa_Respaldo", 2.0, 0.2, 0.6, (-1.5, -1.95, 0.7), M_SOFA)

# ---------------------------------------------------------------------------
# 4. Iluminación
# ---------------------------------------------------------------------------
bpy.ops.object.light_add(type="SUN", location=(3, -3, 5))
sun = bpy.context.active_object
sun.data.energy = 3.0
sun.data.color = (1.0, 0.95, 0.85)
sun.rotation_euler = (math.radians(50), math.radians(30), math.radians(35))

bpy.ops.object.light_add(type="AREA", location=(W / 2 - 0.2, 0, 1.4))
ventana_luz = bpy.context.active_object
ventana_luz.data.energy = 200
ventana_luz.data.size = 1.5
ventana_luz.data.size_y = 1.0
ventana_luz.data.shape = "RECTANGLE"
ventana_luz.rotation_euler = (0, math.radians(90), 0)

# ---------------------------------------------------------------------------
# 5. Cámara (referencia, no se exporta a glTF como activa por defecto)
# ---------------------------------------------------------------------------
bpy.ops.object.camera_add(location=(0, -2.5, 1.7), rotation=(math.radians(85), 0, 0))
scene.camera = bpy.context.active_object

# ---------------------------------------------------------------------------
# 6. Guardado y export
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(BLEND_OUT), exist_ok=True)
os.makedirs(os.path.dirname(GLTF_OUT), exist_ok=True)

bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
print(f"[touralvaro] .blend guardado: {BLEND_OUT}")

# Export glTF
bpy.ops.export_scene.gltf(
    filepath=GLTF_OUT,
    export_format="GLB",
    export_apply=True,
    export_yup=True,
    export_cameras=False,
    export_lights=False,
    export_materials="EXPORT",
    export_image_format="AUTO",
    export_texture_dir="",
)
print(f"[touralvaro] glTF exportado: {GLTF_OUT}")

sys.exit(0)
