#!/usr/bin/env bash
# Optimiza el glTF con Draco (geometría) + WebP (texturas).
# Requiere @gltf-transform/cli instalado (npx lo resuelve si no).
set -euo pipefail

WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
INPUT="$WORKSPACE/viewer/public/models/escena-demo.glb"
OUTPUT="$WORKSPACE/viewer/public/models/escena-demo.optimized.glb"

if [ ! -f "$INPUT" ]; then
  echo "[error] No existe $INPUT. Ejecuta primero: bash scripts/run-blender.sh"
  exit 1
fi

echo "[touralvaro] Optimizando $INPUT..."
npx --yes @gltf-transform/cli optimize "$INPUT" "$OUTPUT" \
  --texture-compress webp

echo "[touralvaro] Salida: $OUTPUT"
ls -lh "$INPUT" "$OUTPUT"
