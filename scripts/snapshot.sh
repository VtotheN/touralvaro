#!/usr/bin/env bash
# Captura screenshots de cada escena disponible usando un Chromium headless.
# Requiere el dev server corriendo en localhost:5173 (lo arranca si no está).
# Genera viewer/public/thumbnails/<escena>.jpg
set -euo pipefail

WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$WORKSPACE/viewer/public/thumbnails"
mkdir -p "$OUT_DIR"

# Levantar dev server si no responde
if ! curl -sf http://localhost:5173/ >/dev/null 2>&1; then
  echo "[snapshot] Iniciando dev server en background..."
  (cd "$WORKSPACE/viewer" && nohup npm run dev > /tmp/touralvaro-dev.log 2>&1 &)
  for i in {1..30}; do
    if curl -sf http://localhost:5173/ >/dev/null 2>&1; then break; fi
    sleep 0.5
  done
fi

# Ejecutar snapshot via Node + playwright (instalado on demand)
cd "$WORKSPACE/viewer"
if ! [ -d node_modules/playwright ]; then
  echo "[snapshot] Instalando playwright..."
  npm install --no-save playwright >/dev/null
  npx playwright install --with-deps chromium >/dev/null
fi

node "$WORKSPACE/scripts/snapshot.mjs"
echo "[snapshot] Listo. Thumbnails en $OUT_DIR/"
ls -lh "$OUT_DIR/"
