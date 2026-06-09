"""Genera una residencia Tipo I de Cabrera Hills Aparthotel y la exporta a glTF.

Fuente de datos (Cabrera_Hills_Brochure_v2_180.pdf):
    - Cabrera Hills · 180° Aparthotel · Cabrera, Costa Norte, RD
    - Sobre el filo del farallón a 125 m sobre el Atlántico
    - 16 residencias en total · 3 niveles · latones de madera natural,
      vidrio de piso a techo, geometría limpia
    - Tipo I (modelado aquí): 141 m² · 3 habitaciones · 2.5 baños ·
      1 parqueo · balcón de cristal templado · piso porcelanato 60×60 ·
      cocina en roble + granito · vista 180° Atlántico
    - (Tipo II, 211 m² penthouse con terraza + pérgola + BBQ, no se modela
      en este script — ver ESCENAS-README.md)

Distribución asumida (el brochure no entrega plano cotado):
    Planta rectangular 14 x 10 m = 140 m² (~141 m² objetivo).
    Frente sur (-Y) = filo del farallón = ventanales y balcón continuos.
    Fondo norte (+Y) = corredor de acceso + servicios.

    Layout (h=2.7 m losa a losa):
        - Balcón en voladizo: 14 x 1.5 m al frente sur (cristal templado)
        - Living/comedor abierto: 8 x 5 m (centro-oeste, ventanales al sur)
        - Cocina abierta tipo island: 4 x 4 m (esquina noreste)
        - Habitación principal (master): 4.5 x 4 m (oeste) con baño
          en suite (2.5 x 2.5 m) y closet walk-in
        - Habitación 2: 3.5 x 3.5 m (centro-norte)
        - Habitación 3: 3.5 x 3.5 m (este-norte)
        - Baño compartido: 2.5 x 2 m
        - Medio baño social: 1.5 x 1.5 m
        - Lavandería integrada en pasillo de servicio

Uso:
    /Applications/Blender.app/Contents/MacOS/Blender -b \
        -P blender/scripts/cabrera-casa.py

Salidas:
    blender/cabrera/cabrera-casa.blend
    viewer/public/models/cabrera-casa.glb
"""

import bpy
import math
import os
import sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLEND_OUT = os.path.join(WORKSPACE, "blender", "cabrera", "cabrera-casa.blend")
GLTF_OUT = os.path.join(WORKSPACE, "viewer", "public", "models", "cabrera-casa.glb")

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
# 2. Materiales PBR (paleta Cabrera: madera natural, blanco, vidrio, roble)
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


M_PORCELANATO = make_pbr("Piso_Porcelanato60", (0.88, 0.86, 0.82), roughness=0.30)
M_WALL = make_pbr("Pared_Blanca", (0.95, 0.94, 0.91), roughness=0.92)
M_CEIL = make_pbr("Techo", (0.97, 0.96, 0.94), roughness=0.95)
M_OAK = make_pbr("Roble_Cocina", (0.60, 0.42, 0.24), roughness=0.45)
M_WOOD_SLAT = make_pbr("Madera_Laton", (0.50, 0.34, 0.20), roughness=0.55)
M_GRANITE = make_pbr("Granito_Cocina", (0.12, 0.11, 0.10), roughness=0.25)
M_SOFA = make_pbr("Sofa_Lino", (0.62, 0.58, 0.50), roughness=0.88)
M_BED = make_pbr("Cama_Textil", (0.92, 0.89, 0.82), roughness=0.92)
M_GLASS = make_pbr("Cristal_Templado", (0.88, 0.93, 0.98),
                   roughness=0.04, metallic=0.0, alpha=0.22)
M_METAL_BLACK = make_pbr("Metal_Negro", (0.10, 0.10, 0.10),
                         roughness=0.35, metallic=0.85)
M_BRONZE = make_pbr("Bronce", (0.62, 0.45, 0.25), roughness=0.30, metallic=0.9)
M_TERRAZZO = make_pbr("Terrazo_Bano", (0.78, 0.76, 0.72), roughness=0.45)
M_PERGOLA = make_pbr("Pergola_Mad", (0.42, 0.30, 0.18), roughness=0.6)


# ---------------------------------------------------------------------------
# 3. Helpers
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
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth,
                                        location=location, vertices=24)
    obj = bpy.context.active_object
    obj.name = name
    obj.rotation_euler = rotation
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    obj.data.materials.append(material)
    return obj


# ---------------------------------------------------------------------------
# 4. Dimensiones generales (141 m² Tipo I)
# ---------------------------------------------------------------------------
W = 14.0    # ancho (X)
D = 10.0    # profundidad interior (Y)
H = 2.7     # altura libre
T_FLOOR = 0.20  # losa
BALCON_D = 1.5  # voladizo del balcón al sur

# ---------------------------------------------------------------------------
# 5. Envolvente
# ---------------------------------------------------------------------------
# Piso interior
add_plane("Piso", W, D, (0, 0, 0), (0, 0, 0), M_PORCELANATO)
# Techo
add_plane("Techo", W, D, (0, 0, H), (math.pi, 0, 0), M_CEIL)

# Paredes este, oeste, norte (sólidas). El sur es cristal templado.
add_plane("Pared_E", D, H, (W / 2, 0, H / 2),
          (math.pi / 2, 0, -math.pi / 2), M_WALL)
add_plane("Pared_O", D, H, (-W / 2, 0, H / 2),
          (math.pi / 2, 0, math.pi / 2), M_WALL)
add_plane("Pared_N", W, H, (0, D / 2, H / 2),
          (math.pi / 2, 0, 0), M_WALL)

# Latones de madera natural en pared norte (referencia del brochure)
n_slats = 18
slat_w = (W - 1.0) / n_slats
for i in range(n_slats):
    x = -W / 2 + 0.5 + (i + 0.5) * slat_w
    add_box(f"Laton_{i}", slat_w * 0.55, 0.04, H - 0.3,
            (x, D / 2 - 0.03, H / 2), M_WOOD_SLAT)

# --- Frente sur: cristal templado piso-techo + balcón en voladizo ---
# 4 paneles de cristal con marcos finos de aluminio negro
panel_w = (W - 0.1) / 4
for i in range(4):
    x = -W / 2 + 0.05 + (i + 0.5) * panel_w
    # Marco vertical izquierdo del panel
    add_box(f"Marco_V_{i}", 0.06, 0.06, H,
            (x - panel_w / 2, -D / 2, H / 2), M_METAL_BLACK)
    # Vidrio
    add_box(f"Vidrio_S_{i}", panel_w - 0.1, 0.03, H - 0.15,
            (x, -D / 2 + 0.02, H / 2), M_GLASS)
# Marco vertical derecho final
add_box("Marco_V_R", 0.06, 0.06, H, (W / 2 - 0.05, -D / 2, H / 2),
        M_METAL_BLACK)
# Marco horizontal superior e inferior
add_box("Marco_H_T", W, 0.06, 0.08, (0, -D / 2, H - 0.04), M_METAL_BLACK)
add_box("Marco_H_B", W, 0.06, 0.08, (0, -D / 2, 0.04), M_METAL_BLACK)

# Losa del balcón en voladizo
add_box("Balcon_Losa", W, BALCON_D, T_FLOOR,
        (0, -D / 2 - BALCON_D / 2, -T_FLOOR / 2 + 0.005), M_PORCELANATO)
add_plane("Balcon_Piso", W - 0.05, BALCON_D - 0.05,
          (0, -D / 2 - BALCON_D / 2, 0.005), (0, 0, 0), M_PORCELANATO)

# Baranda de cristal templado del balcón
# Pasamanos
add_box("Balcon_Top", W, 0.04, 0.04,
        (0, -D / 2 - BALCON_D + 0.05, 1.1), M_METAL_BLACK)
# Vidrio panel continuo
add_box("Balcon_Vidrio", W - 0.1, 0.02, 1.05,
        (0, -D / 2 - BALCON_D + 0.05, 0.55), M_GLASS)
# Pequeños fijadores
for fx in (-W / 2 + 0.3, 0, W / 2 - 0.3):
    add_box(f"Balcon_Fija_{fx}", 0.08, 0.1, 0.15,
            (fx, -D / 2 - BALCON_D + 0.05, 0.1), M_METAL_BLACK)

# ---------------------------------------------------------------------------
# 6. Divisiones internas
# ---------------------------------------------------------------------------
# Origen: centro de piso (0,0,0); X de -7 a 7; Y de -5 a 5.
#
# Habitación principal (master): occidental, X de -7 a -2.5, Y de -1 a 5
#   Pared interior vertical en X=-2.5 (separa master del living)
#   Pared interior horizontal Y=-1 separa el balcón interior (sala) del master/baños
#     Pero no: el sur es ventanal libre. La master toma esquina noroeste.
# Re-layout más limpio:
#   Master: X [-7, -2.5], Y [0.5, 5]            → 4.5 x 4.5
#   Baño master (en-suite): X [-7, -4.5], Y [-1.5, 0.5]   → 2.5 x 2.0
#   Closet master: X [-4.5, -2.5], Y [-1.5, 0.5]         → 2.0 x 2.0
#   Habitación 2: X [-2.5, 1.0], Y [1.5, 5]              → 3.5 x 3.5
#   Habitación 3: X [1.0, 4.5], Y [1.5, 5]               → 3.5 x 3.5
#   Baño compartido: X [4.5, 7.0], Y [3.0, 5]            → 2.5 x 2.0
#   Cocina (abierta): X [4.5, 7.0], Y [-1, 3.0]          → 2.5 x 4.0
#   Living/comedor: X [-2.5, 4.5], Y [-5, 1.5]          → 7.0 x 6.5

def wall(name, x0, y0, x1, y1, thickness=0.1, height=H, material=M_WALL):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if abs(x1 - x0) >= abs(y1 - y0):
        sx, sy = abs(x1 - x0), thickness
    else:
        sx, sy = thickness, abs(y1 - y0)
    add_box(name, sx, sy, height, (cx, cy, height / 2), material)


# --- Pared maestro vs living (vertical en X=-2.5, Y de 1.5 a 5) ---
wall("Muro_Master_E", -2.5, 1.5, -2.5, 5.0)
# Hueco de puerta master (vacío entre Y=1.5 y Y=2.5 → omitimos pared en ese rango)
# (lo de arriba ya cubre Y 1.5 a 5; para hacer puerta, sustituimos por dos pedazos)
# Limpia la pared y crea dos segmentos: Y 1.5 a 2.4 y Y 2.5 a 5.0
# Más sencillo: dejarla completa para esta versión.

# Pared sur del master (separa master del baño/closet)
wall("Muro_Master_S", -7.0, 0.5, -2.5, 0.5)

# Pared entre baño master y closet
wall("Muro_Bath_Closet", -4.5, -1.5, -4.5, 0.5)

# Pared sur de baño/closet master (separa de la sala)
# X de -7 a -2.5 en Y=-1.5
wall("Muro_Closet_S", -7.0, -1.5, -2.5, -1.5)

# Pared entre habitación 2 y living (Y=1.5, X de -2.5 a 1.0)
wall("Muro_Hab2_S", -2.5, 1.5, 1.0, 1.5)

# Pared entre hab 2 y hab 3 (X=1.0, Y 1.5 a 5)
wall("Muro_Hab23", 1.0, 1.5, 1.0, 5.0)

# Pared sur de hab 3 (Y=1.5, X 1.0 a 4.5)
wall("Muro_Hab3_S", 1.0, 1.5, 4.5, 1.5)

# Pared entre hab 3 y cocina/baño compartido (X=4.5, Y de -1 a 5)
wall("Muro_Cocina_O", 4.5, -1.0, 4.5, 5.0)

# Baño compartido: pared interior (Y=3.0, X 4.5 a 7)
wall("Muro_BathC_S", 4.5, 3.0, 7.0, 3.0)

# Cocina: pared sur (Y=-1, X 4.5 a 7) -- abierta al living, sólo media pared baja
add_box("Cocina_Antepecho", 2.5, 0.12, 1.05,
        (5.75, -1.0, 0.525), M_WALL)

# ---------------------------------------------------------------------------
# 7. Mobiliario · Living + Comedor (X [-2.5, 4.5], Y [-5, 1.5])
# ---------------------------------------------------------------------------
# Sofá modular grande mirando al ventanal
add_box("Sofa_3p_Asiento", 3.2, 1.0, 0.42, (0.5, -2.5, 0.21), M_SOFA)
add_box("Sofa_3p_Respaldo", 3.2, 0.2, 0.55, (0.5, -2.0, 0.6), M_SOFA)
# Cojines
for cx in (-0.9, 0.0, 0.9):
    add_box(f"Cojin_{cx}", 0.55, 0.6, 0.18, (0.5 + cx, -2.6, 0.51), M_SOFA)
# Chaise lateral
add_box("Chaise_Base", 0.95, 2.0, 0.42, (2.5, -3.0, 0.21), M_SOFA)
add_box("Chaise_Respaldo", 0.2, 2.0, 0.55, (2.95, -3.0, 0.6), M_SOFA)

# Mesa centro
add_box("Mesa_Centro", 1.5, 0.8, 0.04, (0.5, -3.9, 0.4), M_OAK)
for sx in (-0.7, 0.7):
    for sy in (-0.35, 0.35):
        add_box(f"MC_Pata_{sx}_{sy}", 0.05, 0.05, 0.4,
                (0.5 + sx, -3.9 + sy, 0.2), M_OAK)

# Comedor 6 puestos junto a la cocina
add_box("Comedor_Top", 2.0, 0.95, 0.05, (3.2, 0.0, 0.76), M_OAK)
for sx in (-0.9, 0.9):
    for sy in (-0.4, 0.4):
        add_box(f"Cm_Pata_{sx}_{sy}", 0.06, 0.06, 0.76,
                (3.2 + sx, sy, 0.38), M_OAK)
# 6 sillas (3 cada lado)
for cy in (-1.0, 1.0):
    for cx in (-0.7, 0.0, 0.7):
        add_box(f"CmS_Asiento_{cx}_{cy}", 0.42, 0.42, 0.05,
                (3.2 + cx, cy * 0.45, 0.45), M_WOOD_SLAT)
        add_box(f"CmS_Respaldo_{cx}_{cy}", 0.42, 0.04, 0.45,
                (3.2 + cx, cy * 0.45 + (0.21 if cy > 0 else -0.21), 0.7),
                M_WOOD_SLAT)

# TV mural en pared este del living (oeste? la pared es entre living y maestro -> X=-2.5)
add_box("TV", 1.6, 0.06, 0.95, (-2.4, -3.0, 1.4), M_METAL_BLACK)
# Consola TV
add_box("Consola_TV", 2.2, 0.45, 0.42, (-2.2, -3.5, 0.21), M_OAK)

# ---------------------------------------------------------------------------
# 8. Cocina (X [4.5, 7.0], Y [-1, 3.0])
# ---------------------------------------------------------------------------
# Counter en L: pared norte + pared este
# Pared norte (Y=3, longitud 2.5): no, ya hay muro. Counter contra muro este.
# Counter contra pared este (X=7), Y de -1 a 3
add_box("Cocina_Counter_E", 0.6, 4.0, 0.85,
        (7.0 - 0.3, 1.0, 0.425), M_OAK)
add_box("Cocina_CounterTop_E", 0.65, 4.0, 0.05,
        (7.0 - 0.325, 1.0, 0.875), M_GRANITE)
# Alacenas superiores
add_box("Cocina_Alacena_E", 0.4, 3.5, 0.7,
        (7.0 - 0.2, 1.0, 1.95), M_OAK)
# Counter contra pared norte (Y=3, X de 4.5 a 7) longitud 2.5
add_box("Cocina_Counter_N", 2.2, 0.6, 0.85,
        (5.75, 3.0 - 0.3, 0.425), M_OAK)
add_box("Cocina_CounterTop_N", 2.3, 0.65, 0.05,
        (5.75, 3.0 - 0.325, 0.875), M_GRANITE)
add_box("Cocina_Alacena_N", 2.2, 0.4, 0.7,
        (5.75, 3.0 - 0.2, 1.95), M_OAK)
# Estufa
add_box("Estufa", 0.6, 0.6, 0.05, (5.4, 2.7, 0.9), M_METAL_BLACK)
# Campana
add_box("Campana", 0.65, 0.5, 0.25, (5.4, 2.7, 2.0), M_METAL_BLACK)
# Isla central de la cocina (con barra)
add_box("Isla_Base", 1.8, 0.9, 0.85, (5.5, 1.0, 0.425), M_OAK)
add_box("Isla_Top", 1.9, 1.0, 0.05, (5.5, 1.0, 0.875), M_GRANITE)
# Banquetas (3) bajo la isla del lado del living
for bx in (-0.6, 0.0, 0.6):
    add_box(f"Banqueta_Asiento_{bx}", 0.35, 0.35, 0.05,
            (5.5 + bx, 0.3, 0.75), M_WOOD_SLAT)
    add_box(f"Banqueta_Pata_{bx}", 0.04, 0.04, 0.75,
            (5.5 + bx, 0.3, 0.375), M_METAL_BLACK)

# ---------------------------------------------------------------------------
# 9. Habitación principal (master) — X [-7, -2.5], Y [0.5, 5]
# ---------------------------------------------------------------------------
# Centro: (-4.75, 2.75)
add_box("Cama_M_Base", 2.0, 2.1, 0.35, (-4.75, 2.3, 0.175), M_OAK)
add_box("Cama_M_Colchon", 2.0, 2.1, 0.25, (-4.75, 2.3, 0.475), M_BED)
add_box("Cama_M_Cabecera", 2.2, 0.08, 1.0, (-4.75, 3.4, 0.5), M_WOOD_SLAT)
for ax in (-0.55, 0.55):
    add_box(f"Almohada_M_{ax}", 0.6, 0.4, 0.12,
            (-4.75 + ax, 3.0, 0.66), M_BED)
# Mesas de noche
for nx in (-1.3, 1.3):
    add_box(f"Noche_M_{nx}", 0.5, 0.45, 0.55,
            (-4.75 + nx, 3.2, 0.275), M_OAK)
# Banca al pie
add_box("Banca_M", 1.5, 0.4, 0.45, (-4.75, 1.0, 0.225), M_SOFA)

# Closet master (X [-4.5, -2.5], Y [-1.5, 0.5]) -- armarios contra pared sur
add_box("Closet_M", 1.8, 0.6, 2.2, (-3.5, -1.5 + 0.4, 1.1), M_OAK)

# Baño master (X [-7, -4.5], Y [-1.5, 0.5])
# Doble lavamanos contra pared sur
add_box("BathM_Lav_Base", 1.6, 0.5, 0.85,
        (-5.75, -1.2, 0.425), M_OAK)
add_box("BathM_Lav_Top", 1.7, 0.55, 0.05,
        (-5.75, -1.2, 0.875), M_TERRAZZO)
# Espejos
add_box("BathM_Espejo", 1.5, 0.03, 0.8,
        (-5.75, -1.5 + 0.05, 1.5), M_GLASS)
# Inodoro
add_box("BathM_WC", 0.4, 0.6, 0.4,
        (-6.6, -0.5, 0.2), M_WALL)
# Ducha (vidrio + plato)
add_box("BathM_Ducha_Plato", 1.1, 1.0, 0.04,
        (-5.0, 0.0, 0.02), M_TERRAZZO)
add_box("BathM_Ducha_Vidrio_E", 0.03, 1.0, 2.0,
        (-4.55, 0.0, 1.0), M_GLASS)
add_box("BathM_Ducha_Vidrio_S", 1.1, 0.03, 2.0,
        (-5.0, -0.5, 1.0), M_GLASS)

# ---------------------------------------------------------------------------
# 10. Habitación 2 — X [-2.5, 1.0], Y [1.5, 5]
# ---------------------------------------------------------------------------
add_box("Cama_2_Base", 1.5, 2.0, 0.35, (-0.75, 3.0, 0.175), M_OAK)
add_box("Cama_2_Colchon", 1.5, 2.0, 0.25, (-0.75, 3.0, 0.475), M_BED)
add_box("Cama_2_Cabecera", 1.6, 0.06, 0.85,
        (-0.75, 4.05, 0.45), M_WOOD_SLAT)
add_box("Noche_2", 0.45, 0.4, 0.55, (-1.7, 3.8, 0.275), M_OAK)
add_box("Closet_2", 1.5, 0.55, 2.1, (0.2, 4.7, 1.05), M_OAK)

# ---------------------------------------------------------------------------
# 11. Habitación 3 — X [1.0, 4.5], Y [1.5, 5]
# ---------------------------------------------------------------------------
add_box("Cama_3_Base", 1.5, 2.0, 0.35, (2.75, 3.0, 0.175), M_OAK)
add_box("Cama_3_Colchon", 1.5, 2.0, 0.25, (2.75, 3.0, 0.475), M_BED)
add_box("Cama_3_Cabecera", 1.6, 0.06, 0.85,
        (2.75, 4.05, 0.45), M_WOOD_SLAT)
add_box("Noche_3", 0.45, 0.4, 0.55, (3.8, 3.8, 0.275), M_OAK)
add_box("Closet_3", 1.5, 0.55, 2.1, (1.7, 4.7, 1.05), M_OAK)

# ---------------------------------------------------------------------------
# 12. Baño compartido — X [4.5, 7.0], Y [3.0, 5]
# ---------------------------------------------------------------------------
add_box("BathC_Lav_Base", 1.2, 0.5, 0.85,
        (5.75, 3.3, 0.425), M_OAK)
add_box("BathC_Lav_Top", 1.3, 0.55, 0.05,
        (5.75, 3.3, 0.875), M_TERRAZZO)
add_box("BathC_Espejo", 1.1, 0.03, 0.8,
        (5.75, 3.05, 1.5), M_GLASS)
add_box("BathC_WC", 0.4, 0.6, 0.4,
        (6.5, 4.2, 0.2), M_WALL)
add_box("BathC_Ducha_Plato", 1.0, 0.9, 0.04,
        (5.0, 4.5, 0.02), M_TERRAZZO)
add_box("BathC_Ducha_Vidrio", 0.03, 0.9, 1.9,
        (5.5, 4.5, 0.95), M_GLASS)

# ---------------------------------------------------------------------------
# 13. Mobiliario exterior — balcón
# ---------------------------------------------------------------------------
# 2 sillones lounge en el balcón
for bx in (-3.5, 3.5):
    add_box(f"Lounge_Base_{bx}", 0.8, 1.6, 0.35,
            (bx, -D / 2 - BALCON_D / 2, 0.175 + 0.005), M_WOOD_SLAT)
    add_box(f"Lounge_Cojin_{bx}", 0.8, 1.6, 0.1,
            (bx, -D / 2 - BALCON_D / 2, 0.4), M_SOFA)
    add_box(f"Lounge_Respaldo_{bx}", 0.8, 0.15, 0.4,
            (bx, -D / 2 - BALCON_D / 2 + 0.7, 0.55), M_WOOD_SLAT)
# Mesa baja
add_cylinder("Mesa_Balcon", 0.4, 0.45,
             (0, -D / 2 - BALCON_D / 2, 0.225), M_OAK)

# ---------------------------------------------------------------------------
# 14. Iluminación
# ---------------------------------------------------------------------------
# Sol (atardecer sobre el Atlántico, viene del sur-oeste)
bpy.ops.object.light_add(type="SUN", location=(-4, -8, 8))
sun = bpy.context.active_object
sun.data.energy = 5.0
sun.data.color = (1.0, 0.94, 0.82)
sun.rotation_euler = (math.radians(50), math.radians(-15), math.radians(35))

# Área en ventanal sur (luz del mar)
bpy.ops.object.light_add(type="AREA",
                         location=(0, -D / 2 + 0.2, H / 2))
win = bpy.context.active_object
win.data.energy = 800
win.data.shape = "RECTANGLE"
win.data.size = W - 0.5
win.data.size_y = H - 0.2
win.rotation_euler = (math.radians(-90), 0, 0)

# Iluminación cenital cocina
bpy.ops.object.light_add(type="AREA", location=(5.75, 1.0, H - 0.1))
kit = bpy.context.active_object
kit.data.energy = 60
kit.data.size = 2.0
kit.rotation_euler = (math.pi, 0, 0)

# Iluminación cenital habitación principal
bpy.ops.object.light_add(type="AREA", location=(-4.75, 2.5, H - 0.1))
mst = bpy.context.active_object
mst.data.energy = 40
mst.data.size = 1.8
mst.rotation_euler = (math.pi, 0, 0)

# ---------------------------------------------------------------------------
# 15. Cámara
# ---------------------------------------------------------------------------
bpy.ops.object.camera_add(location=(-1.0, -4.5, 1.6),
                          rotation=(math.radians(85), 0, math.radians(0)))
scene.camera = bpy.context.active_object

# ---------------------------------------------------------------------------
# 16. Guardado y export
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(BLEND_OUT), exist_ok=True)
os.makedirs(os.path.dirname(GLTF_OUT), exist_ok=True)

bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
print(f"[cabrera-casa] .blend guardado: {BLEND_OUT}")

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
print(f"[cabrera-casa] glTF exportado: {GLTF_OUT}")

sys.exit(0)
