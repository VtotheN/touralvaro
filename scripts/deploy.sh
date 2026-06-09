#!/usr/bin/env bash
# Build de producción + opciones de deploy.
# Uso:
#   bash scripts/deploy.sh build           # solo build local
#   bash scripts/deploy.sh vercel          # build + deploy a Vercel
#   bash scripts/deploy.sh netlify         # build + deploy a Netlify
#   bash scripts/deploy.sh preview         # build + preview server local
set -euo pipefail

WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$WORKSPACE/viewer"

CMD="${1:-build}"

echo "[deploy] Building producción..."
npm run build

DIST="$WORKSPACE/viewer/dist"

case "$CMD" in
  build)
    echo "[deploy] Build listo en: $DIST"
    du -sh "$DIST"
    ;;
  preview)
    echo "[deploy] Preview en http://localhost:4173/"
    npm run preview
    ;;
  vercel)
    if ! command -v vercel >/dev/null 2>&1; then
      echo "[deploy] Vercel CLI no encontrada. Instalando..."
      npm install -g vercel
    fi
    cd "$DIST"
    vercel deploy --prod --yes
    ;;
  netlify)
    if ! command -v netlify >/dev/null 2>&1; then
      echo "[deploy] Netlify CLI no encontrada. Instalando..."
      npm install -g netlify-cli
    fi
    netlify deploy --dir="$DIST" --prod
    ;;
  *)
    echo "[deploy] Comando desconocido: $CMD"
    echo "  Opciones: build | preview | vercel | netlify"
    exit 1
    ;;
esac
