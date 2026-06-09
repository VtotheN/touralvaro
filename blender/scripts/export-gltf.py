"""Re-exporta una .blend existente a .glb con los presets correctos para Three.js.

Uso:
    /Applications/Blender.app/Contents/MacOS/Blender path/al.blend \
        -b -P blender/scripts/export-gltf.py -- output.glb

Si no se pasa output, escribe a viewer/public/models/escena-demo.glb.
"""

import bpy
import os
import sys

argv = sys.argv
if "--" in argv:
    extra = argv[argv.index("--") + 1:]
else:
    extra = []

WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(WORKSPACE, "viewer", "public", "models", "escena-demo.glb")
out = extra[0] if extra else DEFAULT_OUT

os.makedirs(os.path.dirname(out), exist_ok=True)

bpy.ops.export_scene.gltf(
    filepath=out,
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
print(f"[export] {out}")
