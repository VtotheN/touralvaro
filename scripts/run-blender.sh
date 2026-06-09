#!/usr/bin/env bash
# Ejecuta el script de generación de la escena demo en Blender headless.
set -euo pipefail

BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$WORKSPACE/blender/scripts/crear-habitacion.py"

if [ ! -x "$BLENDER_BIN" ]; then
  echo "[error] Blender no encontrado en $BLENDER_BIN"
  echo "        Instálalo desde https://www.blender.org/download/"
  exit 1
fi

echo "[touralvaro] Generando escena demo en Blender headless..."
"$BLENDER_BIN" -b -P "$SCRIPT"
echo "[touralvaro] Hecho. glTF en viewer/public/models/escena-demo.glb"
