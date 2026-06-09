#!/usr/bin/env bash
# Orquestador "todo en uno" para desarrollo local.
# Genera escena si no existe, optimiza, e inicia el dev server.
set -euo pipefail

WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$WORKSPACE"

# 1) Generar escena demo si no existe
if [ ! -f viewer/public/models/escena-demo.glb ]; then
  echo "[dev] Generando escena demo (Blender headless)..."
  bash scripts/run-blender.sh
fi

# 2) Optimizar si no existe versión optimizada
if [ ! -f viewer/public/models/escena-demo.optimized.glb ] && [ -f viewer/public/models/escena-demo.glb ]; then
  echo "[dev] Optimizando .glb..."
  bash scripts/optimize.sh || echo "[dev] (optimize falló, continuando con el .glb sin comprimir)"
fi

# 3) Instalar deps si no existen
if [ ! -d viewer/node_modules ]; then
  echo "[dev] Instalando dependencias del viewer..."
  (cd viewer && npm install)
fi

# 4) Iniciar dev server
echo "[dev] Iniciando Vite en http://localhost:5173/"
cd viewer
exec npm run dev
