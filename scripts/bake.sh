#!/usr/bin/env bash
# Orquesta: (1) instala The Lightmapper si no está, (2) intenta bake con TLM,
# (3) si falla, fallback al bake manual; en ambos casos genera
# viewer/public/models/escena-demo-baked.glb.
set -euo pipefail

BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
ADDONS_DIR="$HOME/Library/Application Support/Blender/5.1/scripts/addons"
TLM_DIR="$ADDONS_DIR/thelightmapper"
TLM_ZIP_URL="https://github.com/Naxela/The_Lightmapper/archive/refs/heads/master.zip"
BLEND="$WORKSPACE/blender/escena-demo.blend"
GLB_OUT="$WORKSPACE/viewer/public/models/escena-demo-baked.glb"
GLB_DEMO="$WORKSPACE/viewer/public/models/escena-demo.glb"
FAIL_MARKER="$WORKSPACE/blender/.tlm-failed"

if [ ! -x "$BLENDER_BIN" ]; then
  echo "[bake.sh] ERROR: Blender no encontrado en $BLENDER_BIN"
  exit 1
fi

if [ ! -f "$BLEND" ]; then
  echo "[bake.sh] No existe $BLEND. Ejecuto run-blender.sh primero..."
  bash "$WORKSPACE/scripts/run-blender.sh"
fi

# -----------------------------------------------------------------------------
# 1. Instalar The Lightmapper si no está
# -----------------------------------------------------------------------------
if [ ! -d "$TLM_DIR" ]; then
  echo "[bake.sh] Instalando The Lightmapper en $TLM_DIR"
  mkdir -p "$ADDONS_DIR"
  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT
  echo "[bake.sh] Descargando $TLM_ZIP_URL"
  curl -fsSL -o "$TMP_DIR/tlm.zip" "$TLM_ZIP_URL"
  unzip -q "$TMP_DIR/tlm.zip" -d "$TMP_DIR"
  # El zip extrae a The_Lightmapper-master; lo renombramos a thelightmapper
  # porque el addon hace `import thelightmapper` internamente.
  mv "$TMP_DIR/The_Lightmapper-master" "$TLM_DIR"
  echo "[bake.sh] The Lightmapper instalado"
else
  echo "[bake.sh] The Lightmapper ya instalado en $TLM_DIR"
fi

# -----------------------------------------------------------------------------
# 2. Asegurar que el addon esté habilitado
# -----------------------------------------------------------------------------
echo "[bake.sh] Activando addon..."
"$BLENDER_BIN" -b --python-expr "
import bpy
try:
    bpy.ops.preferences.addon_enable(module='thelightmapper')
    bpy.ops.wm.save_userpref()
    print('[enable] OK')
except Exception as e:
    print('[enable] ERROR:', repr(e))
    raise
" 2>&1 | tail -5

# -----------------------------------------------------------------------------
# 3. Limpiar marcador previo
# -----------------------------------------------------------------------------
rm -f "$FAIL_MARKER"
rm -f "$GLB_OUT"

# -----------------------------------------------------------------------------
# 4. Intentar bake con TLM
# -----------------------------------------------------------------------------
echo "[bake.sh] Intentando bake con The Lightmapper..."
set +e
"$BLENDER_BIN" -b "$BLEND" -P "$WORKSPACE/blender/scripts/bake-con-lightmapper.py"
TLM_EXIT=$?
set -e

TLM_OK=0
if [ $TLM_EXIT -eq 0 ] && [ -f "$GLB_OUT" ] && [ ! -f "$FAIL_MARKER" ]; then
  TLM_OK=1
fi

# -----------------------------------------------------------------------------
# 5. Fallback si TLM falló
# -----------------------------------------------------------------------------
if [ $TLM_OK -eq 0 ]; then
  echo "[bake.sh] ============================================="
  echo "[bake.sh] TLM falló o no produjo GLB. Usando fallback."
  echo "[bake.sh] Razón:"
  if [ -f "$FAIL_MARKER" ]; then
    cat "$FAIL_MARKER"
  fi
  echo "[bake.sh] Exit code TLM: $TLM_EXIT"
  echo "[bake.sh] ============================================="
  set +e
  "$BLENDER_BIN" -b -P "$WORKSPACE/blender/scripts/bake-fallback.py"
  FB_EXIT=$?
  set -e
  if [ $FB_EXIT -ne 0 ] || [ ! -f "$GLB_OUT" ]; then
    echo "[bake.sh] ERROR: fallback también falló (exit $FB_EXIT)"
    exit $FB_EXIT
  fi
  echo "[bake.sh] Fallback OK"
fi

# -----------------------------------------------------------------------------
# 6. Reporte final
# -----------------------------------------------------------------------------
echo ""
echo "[bake.sh] ===== RESULTADO ====="
ls -lh "$GLB_OUT"
if [ -f "$GLB_DEMO" ]; then
  echo "[bake.sh] Comparación con demo original:"
  ls -lh "$GLB_DEMO"
  DEMO_SIZE=$(stat -f%z "$GLB_DEMO")
  BAKED_SIZE=$(stat -f%z "$GLB_OUT")
  echo "[bake.sh] demo:  $DEMO_SIZE bytes"
  echo "[bake.sh] baked: $BAKED_SIZE bytes"
  if [ "$BAKED_SIZE" -gt "$DEMO_SIZE" ]; then
    echo "[bake.sh] OK: el baked es más grande (esperado por texturas embebidas)"
  else
    echo "[bake.sh] WARN: el baked NO es más grande — posible bake fallido o sin texturas"
  fi
fi
echo "[bake.sh] Hecho."
