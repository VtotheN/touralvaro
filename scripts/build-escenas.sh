#!/usr/bin/env bash
# Genera las escenas Cayena Loft y Cabrera Casa en Blender headless,
# y reporta los tamaños finales de los .glb resultantes.
set -euo pipefail

BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"

CAYENA_SCRIPT="$WORKSPACE/blender/scripts/cayena-loft.py"
CABRERA_SCRIPT="$WORKSPACE/blender/scripts/cabrera-casa.py"
CAYENA_GLB="$WORKSPACE/viewer/public/models/cayena-loft.glb"
CABRERA_GLB="$WORKSPACE/viewer/public/models/cabrera-casa.glb"

if [ ! -x "$BLENDER_BIN" ]; then
  echo "[error] Blender no encontrado en $BLENDER_BIN"
  echo "        Instálalo desde https://www.blender.org/download/"
  exit 1
fi

echo "[escenas] === Generando Cayena Loft (PH Loft 105 m²) ==="
"$BLENDER_BIN" -b -P "$CAYENA_SCRIPT"

echo ""
echo "[escenas] === Generando Cabrera Casa (Tipo I 141 m²) ==="
"$BLENDER_BIN" -b -P "$CABRERA_SCRIPT"

echo ""
echo "[escenas] === Resultados ==="
for glb in "$CAYENA_GLB" "$CABRERA_GLB"; do
  if [ -f "$glb" ]; then
    size=$(ls -lh "$glb" | awk '{print $5}')
    bytes=$(stat -f%z "$glb" 2>/dev/null || stat -c%s "$glb")
    name=$(basename "$glb")
    echo "  $name → $size ($bytes bytes)"
  else
    echo "  [error] No existe: $glb"
    exit 1
  fi
done

echo ""
echo "[escenas] Listo. Modelos en viewer/public/models/"
