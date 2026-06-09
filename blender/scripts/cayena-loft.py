"""Genera el apartamento PH Loft de Cayena Residences Fase 02 y lo exporta a glTF.

Fuente de datos (Cayena_Residences_Phase_02.pdf + Cayena_Loft_brochure.html):
    - PH Loft (Tipo B, unidades CL-02-01 a CL-02-08): 105 m² construidos
    - 1 habitación principal, 1.5 baños
    - Mezzanine / loft (segunda altura)
    - Doble altura (~5 m de techo en el área social)
    - Lavandería integrada
    - Piscina privada opcional (no se modela; opcional por unidad)
    - Vistas: mar, montaña, piscina, atardecer
    - Concepto: piedra local, carpintería en madera clara, ventanales verticales
      de piso a techo, "una tabla de surf apoyada al lado"

Distribución asumida (el PDF no entrega plano cotado, sólo área):
    Planta ~10.5 x 10 m = 105 m². Single-floor footprint con mezzanine encima
    del bloque de servicio (cocina + baño + lavandería).

    Planta baja (10.5 x 10 m, h=5 m libre en sala, 2.6 m bajo mezzanine):
        - Living/comedor doble altura: ~6.5 x 6.5 m al frente (ventanales)
        - Cocina abierta: ~4.0 x 3.0 m al fondo derecha (bajo mezzanine)
        - Baño social (1/2 baño): ~1.5 x 1.5 m
        - Lavandería: ~1.5 x 1.8 m
        - Escalera al mezzanine

    Mezzanine (~5 x 4 m sobre cocina/servicios, h=2.4 m):
        - Habitación principal abierta al doble altura
        - Baño completo (1.5 baños totales)

Uso:
    /Applications/Blender.app/Contents/MacOS/Blender -b \
        -P blender/scripts/cayena-loft.py

Salidas:
    blender/cayena/cayena-loft.blend
    viewer/public/models/cayena-loft.glb
"""

import bpy
import math
import os
import sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLEND_OUT = os.path.join(WORKSPACE, "blender", "cayena", "cayena-loft.blend")
GLTF_OUT = os.path.join(WORKSPACE, "viewer", "public", "models", "cayena-loft.glb")

# ---------------------------------------------------------------------------
# 1. Escena limpia
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1.0
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 32


# ---------------------------------------------------------------------------
# 2. Materiales PBR (paleta Cayena: piedra local, madera clara, blanco)
# ---------------------------------------------------------------------------
def make_pbr(name, base_color, roughness=0.7, metallic=0.0, alpha=1.0):
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
    if "Alpha" in bsdf.inputs and alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.blend_method = "BLEND"
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return mat


M_FLOOR_WOOD = make_pbr("Piso_MaderaClara", (0.62, 0.48, 0.32), roughness=0.45)
M_FLOOR_PORC = make_pbr("Piso_Porcelanato", (0.86, 0.83, 0.78), roughness=0.35)
M_WALL_WHITE = make_pbr("Pared_Blanca", (0.94, 0.92, 0.88), roughness=0.9)
M_WALL_STONE = make_pbr("Piedra_Local", (0.72, 0.66, 0.55), roughness=0.85)
M_CEIL = make_pbr("Techo", (0.97, 0.96, 0.94), roughness=0.95)
M_WOOD_LIGHT = make_pbr("Madera_Clara", (0.78, 0.62, 0.40), roughness=0.5)
M_WOOD_DARK = make_pbr("Madera_Mesa", (0.42, 0.27, 0.16), roughness=0.4)
M_SOFA = make_pbr("Sofa_Lino", (0.78, 0.72, 0.62), roughness=0.88)
M_GLASS = make_pbr("Vidrio", (0.88, 0.93, 0.98), roughness=0.05, metallic=0.0, alpha=0.25)
M_KITCHEN = make_pbr("Cocina_Granito", (0.18, 0.17, 0.16), roughness=0.3)
M_METAL = make_pbr("Metal_Bronce", (0.62, 0.45, 0.25), roughness=0.35, metallic=0.9)
M_BED = make_pbr("Cama_Textil", (0.92, 0.88, 0.80), roughness=0.92)
M_RAIL = make_pbr("Baranda", (0.20, 0.18, 0.16), roughness=0.4, metallic=0.6)

# ---------------------------------------------------------------------------
# 3. Helpers de geometría
# ---------------------------------------------------------------------------
def add_box(name, sx, sy, sz, location, material, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    obj.rotation_euler = rotation
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.data.materials.append(material)
    return obj


def add_plane(name, sx, sy, location, rotation, material):
    bpy.ops.mesh.primitive_plane_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, 1)
    obj.rotation_euler = rotation
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.data.materials.append(material)
    return obj


def add_cylinder(name, radius, depth, location, material, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=location, vertices=24)
    obj = bpy.context.active_object
    obj.name = name
    obj.rotation_euler = rotation
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    obj.data.materials.append(material)
    return obj


# ---------------------------------------------------------------------------
# 4. Dimensiones generales (105 m² PH Loft)
# ---------------------------------------------------------------------------
W = 10.5   # ancho (X)
D = 10.0   # profundidad (Y)
H_TALL = 5.0   # doble altura sala
H_MEZ = 2.6    # altura libre bajo mezzanine
T_MEZ = 0.20   # espesor losa mezzanine

# Origen: centro del piso de planta baja.
# Frente (sur, -Y): ventanales doble altura.
# Fondo (norte, +Y): cocina + servicio.
# Mezzanine ocupa la franja norte (cocina + servicios encima).
MEZ_DEPTH = 4.0   # franja Y ocupada por mezzanine (desde la pared norte hacia el sur)
MEZ_Y0 = D / 2 - MEZ_DEPTH  # límite sur del mezzanine

# ---------------------------------------------------------------------------
# 5. Envolvente (piso, techo, paredes)
# ---------------------------------------------------------------------------
# Piso planta baja
add_plane("Piso_PB", W, D, (0, 0, 0), (0, 0, 0), M_FLOOR_WOOD)

# Techo doble altura (zona sur, sobre living)
add_plane("Techo_Doble", W, D - MEZ_DEPTH, (0, -MEZ_DEPTH / 2, H_TALL),
          (math.pi, 0, 0), M_CEIL)
# Techo final sobre mezzanine
add_plane("Techo_Mez", W, MEZ_DEPTH, (0, D / 2 - MEZ_DEPTH / 2, H_TALL),
          (math.pi, 0, 0), M_CEIL)

# Paredes laterales (este y oeste) -- planos planos hasta H_TALL
add_plane("Pared_E", D, H_TALL, (W / 2, 0, H_TALL / 2),
          (math.pi / 2, 0, -math.pi / 2), M_WALL_WHITE)
add_plane("Pared_O", D, H_TALL, (-W / 2, 0, H_TALL / 2),
          (math.pi / 2, 0, math.pi / 2), M_WALL_WHITE)

# Pared norte (fondo) -- piedra local, full height
add_plane("Pared_N_Piedra", W, H_TALL, (0, D / 2, H_TALL / 2),
          (math.pi / 2, 0, 0), M_WALL_STONE)

# Pared sur -- mayormente ventanales. Marco de muro a ambos lados.
# Antepecho bajo (0 a 0.4m)
add_box("Antepecho_S", W, 0.15, 0.4, (0, -D / 2, 0.2), M_WALL_WHITE)
# Pilastras laterales (vertical) + central
for x in (-W / 2 + 0.2, -W / 6, W / 6, W / 2 - 0.2):
    add_box(f"Pilastra_{x:.2f}", 0.15, 0.15, H_TALL, (x, -D / 2, H_TALL / 2),
            M_WOOD_LIGHT)
# Cabezal alto
add_box("Cabezal_S", W, 0.15, 0.3, (0, -D / 2, H_TALL - 0.15), M_WALL_WHITE)
# Vidrio: tres paneles
for x in (-W / 3, 0, W / 3):
    add_box(f"Vidrio_S_{x:.1f}", W / 3 - 0.25, 0.04, H_TALL - 0.7,
            (x, -D / 2 + 0.02, 0.4 + (H_TALL - 0.7) / 2), M_GLASS)

# ---------------------------------------------------------------------------
# 6. Mezzanine (losa elevada + baranda)
# ---------------------------------------------------------------------------
mez_z = H_MEZ  # 2.6 m del piso al underside? -- losa empieza a 2.6, espesor 0.2 -> top a 2.8
# Losa del mezzanine (sólo en franja norte)
add_box("Mezzanine_Losa", W, MEZ_DEPTH, T_MEZ,
        (0, D / 2 - MEZ_DEPTH / 2, mez_z + T_MEZ / 2), M_FLOOR_WOOD)

# Piso transitable del mezzanine (madera clara, fino)
add_plane("Mezzanine_Piso", W - 0.1, MEZ_DEPTH - 0.1,
          (0, D / 2 - MEZ_DEPTH / 2, mez_z + T_MEZ + 0.005),
          (0, 0, 0), M_WOOD_LIGHT)

# Baranda frontal del mezzanine (mirando al living)
rail_top = mez_z + T_MEZ + 1.0
rail_y = D / 2 - MEZ_DEPTH
# Pasamanos
add_box("Baranda_Top", W - 0.2, 0.05, 0.05,
        (0, rail_y + 0.05, rail_top), M_RAIL)
# Riel inferior
add_box("Baranda_Bottom", W - 0.2, 0.05, 0.05,
        (0, rail_y + 0.05, mez_z + T_MEZ + 0.1), M_RAIL)
# Postes verticales cada 0.8 m
n_posts = int((W - 0.4) / 0.8) + 1
for i in range(n_posts):
    x = -W / 2 + 0.2 + i * (W - 0.4) / (n_posts - 1)
    add_box(f"Baranda_Post_{i}", 0.04, 0.04, 1.0,
            (x, rail_y + 0.05, mez_z + T_MEZ + 0.5), M_RAIL)

# ---------------------------------------------------------------------------
# 7. Escalera al mezzanine (lateral oeste, recta, 12 escalones)
# ---------------------------------------------------------------------------
n_steps = 13
step_run = 0.28
step_rise = (mez_z + T_MEZ) / n_steps
stair_x = -W / 2 + 0.7   # arrimado a pared oeste
stair_y0 = D / 2 - MEZ_DEPTH - 0.3  # arranca justo al sur del mezzanine
for i in range(n_steps):
    add_box(f"Escalon_{i}",
            1.0, step_run, step_rise,
            (stair_x, stair_y0 - i * step_run - step_run / 2,
             (i + 0.5) * step_rise),
            M_WOOD_LIGHT)

# ---------------------------------------------------------------------------
# 8. Mobiliario planta baja — sala
# ---------------------------------------------------------------------------
# Sofá modular en L mirando hacia ventanales
add_box("Sofa_Largo", 3.0, 0.95, 0.45, (-1.5, -1.5, 0.225), M_SOFA)
add_box("Sofa_Respaldo", 3.0, 0.2, 0.55, (-1.5, -1.05, 0.65 + 0.05), M_SOFA)
add_box("Sofa_Chaise", 0.95, 1.8, 0.45, (0.5, -1.0, 0.225), M_SOFA)

# Mesa de centro
add_box("Mesa_Centro_Top", 1.4, 0.7, 0.04, (-1.4, -3.0, 0.4), M_WOOD_DARK)
for sx in (-0.65, 0.65):
    for sy in (-0.3, 0.3):
        add_box(f"Mesa_Pata_{sx}_{sy}", 0.04, 0.04, 0.4,
                (-1.4 + sx, -3.0 + sy, 0.2), M_WOOD_DARK)

# "Tabla de surf apoyada" (referencia del brochure)
surf = add_box("Tabla_Surf", 0.5, 1.9, 0.06,
               (W / 2 - 0.6, -D / 2 + 1.2, 1.0), M_WOOD_LIGHT,
               rotation=(math.radians(75), 0, math.radians(8)))

# Comedor 4 puestos
add_box("Mesa_Comedor", 1.6, 0.9, 0.05, (2.0, 0.5, 0.76), M_WOOD_DARK)
for sx in (-0.7, 0.7):
    for sy in (-0.35, 0.35):
        add_box(f"MComedor_Pata_{sx}_{sy}", 0.06, 0.06, 0.76,
                (2.0 + sx, 0.5 + sy, 0.38), M_WOOD_DARK)
# 4 sillas (simples)
for (cx, cy) in ((2.0, -0.4), (2.0, 1.4), (1.2, 0.5), (2.8, 0.5)):
    add_box(f"Silla_Asiento_{cx}_{cy}", 0.42, 0.42, 0.05,
            (cx, cy, 0.45), M_WOOD_LIGHT)
    add_box(f"Silla_Respaldo_{cx}_{cy}", 0.42, 0.04, 0.45,
            (cx, cy + (0.21 if cy > 0.5 else -0.21), 0.7), M_WOOD_LIGHT)

# ---------------------------------------------------------------------------
# 9. Cocina (al fondo, bajo el mezzanine, lado este)
# ---------------------------------------------------------------------------
# Isla
add_box("Cocina_Isla_Base", 2.4, 0.9, 0.85, (1.5, D / 2 - 2.2, 0.425),
        M_WOOD_LIGHT)
add_box("Cocina_Isla_Top", 2.5, 1.0, 0.05, (1.5, D / 2 - 2.2, 0.875),
        M_KITCHEN)

# Counter a la pared norte
add_box("Cocina_Counter", 4.5, 0.65, 0.85, (1.75, D / 2 - 0.35, 0.425),
        M_WOOD_LIGHT)
add_box("Cocina_Counter_Top", 4.6, 0.7, 0.05, (1.75, D / 2 - 0.35, 0.875),
        M_KITCHEN)
# Alacenas superiores
add_box("Cocina_Alacena", 4.5, 0.4, 0.7, (1.75, D / 2 - 0.25, 1.85),
        M_WOOD_LIGHT)
# Campana extractora (volumen simple)
add_box("Campana", 0.7, 0.45, 0.25, (1.75, D / 2 - 0.35, 1.5),
        M_METAL)

# ---------------------------------------------------------------------------
# 10. Baño social (1/2 baño) — esquina noroeste planta baja
# ---------------------------------------------------------------------------
bath_x, bath_y = -W / 2 + 1.0, D / 2 - 1.0
# Paredes divisorias
add_box("Bath1_Wall_S", 2.0, 0.08, H_MEZ, (-W / 2 + 1.0, MEZ_Y0 + 1.0, H_MEZ / 2),
        M_WALL_WHITE)
add_box("Bath1_Wall_E", 0.08, 2.0, H_MEZ, (-W / 2 + 2.0, MEZ_Y0 + 2.0, H_MEZ / 2),
        M_WALL_WHITE)
# Inodoro (cilindro tapa + box)
add_box("Bath1_WC", 0.4, 0.6, 0.4, (bath_x - 0.4, bath_y - 0.4, 0.2), M_WALL_WHITE)
# Lavamanos
add_box("Bath1_Lav_Base", 0.5, 0.4, 0.85, (bath_x + 0.4, bath_y - 0.2, 0.425),
        M_WOOD_DARK)
add_box("Bath1_Lav_Top", 0.55, 0.42, 0.05, (bath_x + 0.4, bath_y - 0.2, 0.875),
        M_FLOOR_PORC)

# ---------------------------------------------------------------------------
# 11. Lavandería — esquina noreste planta baja (junto cocina)
# ---------------------------------------------------------------------------
laund_x, laund_y = W / 2 - 0.9, D / 2 - 0.9
add_box("Lav_Wall_S", 1.8, 0.08, H_MEZ,
        (W / 2 - 0.9, MEZ_Y0 + 1.8, H_MEZ / 2), M_WALL_WHITE)
add_box("Lav_Wall_W", 0.08, 1.8, H_MEZ,
        (W / 2 - 1.8, MEZ_Y0 + 1.8 + 0.9, H_MEZ / 2), M_WALL_WHITE)
# Lavadora + secadora apiladas
add_box("Lavadora", 0.65, 0.65, 0.85, (laund_x, laund_y, 0.425), M_WALL_WHITE)
add_box("Secadora", 0.65, 0.65, 0.85, (laund_x, laund_y, 0.425 + 0.85 + 0.05),
        M_WALL_WHITE)
# Detalle: puerta circular acero
add_cylinder("Lavadora_Puerta", 0.22, 0.05,
             (laund_x, laund_y - 0.32, 0.425 + 0.1), M_METAL,
             rotation=(math.pi / 2, 0, 0))
add_cylinder("Secadora_Puerta", 0.22, 0.05,
             (laund_x, laund_y - 0.32, 0.425 + 0.85 + 0.05 + 0.1), M_METAL,
             rotation=(math.pi / 2, 0, 0))

# ---------------------------------------------------------------------------
# 12. Mobiliario mezzanine — dormitorio + baño completo
# ---------------------------------------------------------------------------
mez_floor_z = mez_z + T_MEZ + 0.01
# Cama king mirando hacia el doble altura
bed_x, bed_y = -1.5, D / 2 - MEZ_DEPTH + 1.6
add_box("Cama_Base", 1.8, 2.0, 0.35, (bed_x, bed_y, mez_floor_z + 0.175),
        M_WOOD_DARK)
add_box("Cama_Colchon", 1.8, 2.0, 0.25,
        (bed_x, bed_y, mez_floor_z + 0.35 + 0.125), M_BED)
add_box("Cama_Cabecera", 1.9, 0.08, 0.9,
        (bed_x, bed_y + 1.04, mez_floor_z + 0.45), M_WOOD_LIGHT)
# Almohadas
for ax in (-0.45, 0.45):
    add_box(f"Almohada_{ax}", 0.55, 0.35, 0.1,
            (bed_x + ax, bed_y + 0.75, mez_floor_z + 0.65), M_BED)
# Mesas de noche
for nx in (-1.15, 0.15):
    add_box(f"Noche_{nx}", 0.45, 0.4, 0.55,
            (bed_x + nx, bed_y + 0.95, mez_floor_z + 0.275), M_WOOD_LIGHT)

# Baño en mezzanine (lado este)
m_bath_x = 2.0
m_bath_y = D / 2 - 1.5
add_box("Bath2_Wall_S", 3.0, 0.08, 2.4,
        (2.0, MEZ_Y0 + MEZ_DEPTH - 3.0, mez_floor_z + 1.2), M_WALL_WHITE)
add_box("Bath2_Wall_W", 0.08, 3.0, 2.4,
        (0.5, D / 2 - 1.5, mez_floor_z + 1.2), M_WALL_WHITE)
# Ducha (vidrio)
add_box("Ducha_Vidrio", 0.04, 1.0, 1.9,
        (2.8, D / 2 - 1.0, mez_floor_z + 0.95), M_GLASS)
# Plato de ducha
add_box("Ducha_Plato", 1.0, 1.0, 0.05,
        (3.0, D / 2 - 0.5, mez_floor_z + 0.025), M_FLOOR_PORC)
# Inodoro
add_box("Bath2_WC", 0.4, 0.6, 0.4,
        (1.1, D / 2 - 0.5, mez_floor_z + 0.2), M_WALL_WHITE)
# Lavamanos doble
add_box("Bath2_Lav_Base", 1.4, 0.5, 0.85,
        (1.7, D / 2 - 1.2, mez_floor_z + 0.425), M_WOOD_LIGHT)
add_box("Bath2_Lav_Top", 1.5, 0.55, 0.05,
        (1.7, D / 2 - 1.2, mez_floor_z + 0.875), M_FLOOR_PORC)

# Closet pared este del dormitorio
add_box("Closet", 0.6, 2.2, 1.9,
        (W / 2 - 0.5, D / 2 - MEZ_DEPTH + 1.5, mez_floor_z + 0.95),
        M_WOOD_LIGHT)

# ---------------------------------------------------------------------------
# 13. Iluminación natural (sol + área en ventanales)
# ---------------------------------------------------------------------------
bpy.ops.object.light_add(type="SUN", location=(3, -6, 8))
sun = bpy.context.active_object
sun.data.energy = 4.0
sun.data.color = (1.0, 0.96, 0.88)
sun.rotation_euler = (math.radians(55), math.radians(20), math.radians(40))

# Área grande en ventanal sur
bpy.ops.object.light_add(type="AREA", location=(0, -D / 2 + 0.3, H_TALL / 2))
win = bpy.context.active_object
win.data.energy = 600
win.data.shape = "RECTANGLE"
win.data.size = W - 1.0
win.data.size_y = H_TALL - 0.7
win.rotation_euler = (math.radians(-90), 0, 0)

# Luz interior cocina
bpy.ops.object.light_add(type="AREA", location=(1.75, D / 2 - 0.5, H_MEZ - 0.1))
kit = bpy.context.active_object
kit.data.energy = 80
kit.data.size = 2.5
kit.rotation_euler = (math.pi, 0, 0)

# ---------------------------------------------------------------------------
# 14. Cámara (referencia)
# ---------------------------------------------------------------------------
bpy.ops.object.camera_add(location=(-3.5, -4.0, 1.7),
                          rotation=(math.radians(82), 0, math.radians(-30)))
scene.camera = bpy.context.active_object

# ---------------------------------------------------------------------------
# 15. Guardado y export
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(BLEND_OUT), exist_ok=True)
os.makedirs(os.path.dirname(GLTF_OUT), exist_ok=True)

bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
print(f"[cayena-loft] .blend guardado: {BLEND_OUT}")

bpy.ops.export_scene.gltf(
    filepath=GLTF_OUT,
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
print(f"[cayena-loft] glTF exportado: {GLTF_OUT}")

sys.exit(0)
