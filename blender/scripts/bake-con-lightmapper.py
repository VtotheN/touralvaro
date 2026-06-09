"""Bake con The Lightmapper (Naxela) en modo headless.

Uso:
    /Applications/Blender.app/Contents/MacOS/Blender \
        blender/escena-demo.blend \
        -b -P blender/scripts/bake-con-lightmapper.py

Comportamiento:
    1. Activa el addon `thelightmapper` (debe estar instalado en
       ~/Library/Application Support/Blender/5.1/scripts/addons/thelightmapper).
    2. Configura propiedades de escena (Cycles, samples bajos para demo,
       sin denoise OIDN externo, sin filtering OpenCV).
    3. Equivalente al botón "Enable for set" de TLM: marca todas las
       meshes como lightmapped, con resolución 512 y unwrap Smart.
    4. Llama a `thelightmapper.addon.utility.build.prepare_build(0, True)`
       que es lo que TLM lanza internamente cuando bakea en background.
    5. Cuando termina, re-guarda el .blend y exporta a
       `viewer/public/models/escena-demo-baked.glb`.

Si algo falla, escribe un marcador `blender/.tlm-failed` y sale con código 2
para que el runner shell pueda hacer fallback al script manual
`bake-lightmap.py`.
"""

import bpy
import os
import sys
import traceback

WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLEND_PATH = os.path.join(WORKSPACE, "blender", "escena-demo.blend")
GLB_OUT = os.path.join(WORKSPACE, "viewer", "public", "models", "escena-demo-baked.glb")
FAIL_MARKER = os.path.join(WORKSPACE, "blender", ".tlm-failed")

# Clean any previous failure marker
if os.path.exists(FAIL_MARKER):
    os.remove(FAIL_MARKER)


def fail(msg):
    print(f"[bake-tlm] FAIL: {msg}")
    with open(FAIL_MARKER, "w") as f:
        f.write(msg + "\n")
    sys.exit(2)


# ---------------------------------------------------------------------------
# 1. Cargar la escena explícitamente (por si se invocó sin -b path.blend)
# ---------------------------------------------------------------------------
if bpy.data.filepath != BLEND_PATH:
    if not os.path.exists(BLEND_PATH):
        fail(f"No existe {BLEND_PATH}. Corre primero scripts/run-blender.sh")
    bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)

print(f"[bake-tlm] Escena: {bpy.data.filepath}")
print(f"[bake-tlm] Objetos: {[o.name for o in bpy.context.scene.objects if o.type == 'MESH']}")


# ---------------------------------------------------------------------------
# 2. Habilitar The Lightmapper
# ---------------------------------------------------------------------------
try:
    bpy.ops.preferences.addon_enable(module="thelightmapper")
except Exception as e:
    fail(f"No se pudo activar el addon `thelightmapper`: {e!r}")

try:
    import thelightmapper  # noqa: F401
    from thelightmapper.addon.utility import build as tlm_build
except Exception as e:
    fail(f"No se pudo importar thelightmapper: {e!r}\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# 3. Configurar propiedades de escena
# ---------------------------------------------------------------------------
scene = bpy.context.scene
sp = scene.TLM_SceneProperties
ep = scene.TLM_EngineProperties

ep.tlm_lighting_mode = "combined"     # combined direct + indirect
ep.tlm_bake_mode = "Foreground"       # bake en este mismo proceso (no spawn subprocess)
ep.tlm_lightmap_savedir = "Lightmaps"

# Samples bajos para demo (Cycles)
try:
    ep.tlm_quality = "0"  # Preview
except Exception:
    pass

# Resolución por objeto (enum: '32','64','128','256','512','1024',...).
sp.tlm_mesh_lightmap_resolution = "512"
sp.tlm_mesh_lightmap_unwrap_mode = "SmartProject"

# Sin filtrado OpenCV (evita dependencia externa).
sp.tlm_filtering_use = False

# Sin denoising OIDN externo (puede pedir ruta al binario).
sp.tlm_denoise_use = False

# Sin encoding HDR (genera EXR/PNG estándar).
sp.tlm_encoding_use = False

# No usar red.
try:
    sp.tlm_network_render = False
except Exception:
    pass


# ---------------------------------------------------------------------------
# 4. "Enable for set" — marcar todos los MESH como lightmapped
# ---------------------------------------------------------------------------
print("[bake-tlm] Marcando meshes para lightmap...")
for obj in scene.objects:
    if obj.type == "MESH":
        obj.TLM_ObjectProperties.tlm_mesh_lightmap_use = True
        obj.TLM_ObjectProperties.tlm_mesh_lightmap_unwrap_mode = "SmartProject"
        obj.TLM_ObjectProperties.tlm_mesh_lightmap_resolution = "512"
        print(f"  + {obj.name}")


# ---------------------------------------------------------------------------
# 5. Guardar antes de bakear (TLM lo exige)
# ---------------------------------------------------------------------------
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
print(f"[bake-tlm] .blend re-guardado: {BLEND_PATH}")


# ---------------------------------------------------------------------------
# 6. Ejecutar el build
# ---------------------------------------------------------------------------
print("[bake-tlm] Iniciando prepare_build(0, True)...")
try:
    tlm_build.prepare_build(0, True)
except SystemExit:
    # TLM a veces hace sys.exit al terminar
    print("[bake-tlm] prepare_build llamó sys.exit (normal en algunos flujos)")
except Exception as e:
    fail(f"prepare_build error: {e!r}\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# 7. Re-guardar (TLM modifica el .blend con materiales nuevos)
# ---------------------------------------------------------------------------
try:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    print(f"[bake-tlm] .blend post-bake guardado: {BLEND_PATH}")
except Exception as e:
    print(f"[bake-tlm] WARN no se pudo re-guardar: {e!r}")


# ---------------------------------------------------------------------------
# 8. Exportar GLB
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(GLB_OUT), exist_ok=True)
print(f"[bake-tlm] Exportando a {GLB_OUT}")
try:
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
except Exception as e:
    fail(f"export_scene.gltf error: {e!r}\n{traceback.format_exc()}")

if not os.path.exists(GLB_OUT):
    fail(f"No se generó {GLB_OUT}")

print(f"[bake-tlm] OK: {GLB_OUT} ({os.path.getsize(GLB_OUT)} bytes)")
