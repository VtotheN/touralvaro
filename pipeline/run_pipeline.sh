#!/bin/bash
# run_pipeline.sh — Full render + enhance pipeline for both units.
# Run from repo root. Waits for any active Blender render before starting next.

set -e
cd "$(dirname "$0")/.."

BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
PYTHON="python3"
DEPA1_CFG="test_projects/cayena-depa1/config.json"
LOFT2_CFG="test_projects/cayena-loft2/config.json"
DEPA1_OUT="viewer/public/panoramas/cayena-depa1"
LOFT2_OUT="viewer/public/panoramas/cayena-loft2"

echo "=== touralvaro full pipeline ==="
echo "$(date)"

# Wait for any running Blender to finish
if pgrep -x Blender > /dev/null 2>&1; then
    echo "Blender already running — waiting..."
    while pgrep -x Blender > /dev/null 2>&1; do sleep 15; done
    echo "Previous render done."
fi

# --- Enhance whatever is already done for depa1 (if v2 files exist) ---
if ls "$DEPA1_OUT"/*.jpg 2>/dev/null | head -1 | grep -q jpg; then
    echo ""
    echo "[1/4] Enhancing depa1 panoramas..."
    $PYTHON pipeline/enhance_panorama.py "$DEPA1_OUT" 2>&1 | tee /tmp/enhance_depa1.log
fi

# --- Render loft2 v2 ---
echo ""
echo "[2/4] Rendering loft2 v2 (5 rooms × ~17 min)..."
$BLENDER --background --python pipeline/gen_panorama.py -- \
    "$LOFT2_CFG" "$LOFT2_OUT" 2>&1 | tee /tmp/render_loft2_v2.log

echo ""
echo "[3/4] Enhancing loft2 panoramas..."
$PYTHON pipeline/enhance_panorama.py "$LOFT2_OUT" 2>&1 | tee /tmp/enhance_loft2.log

echo ""
echo "[4/4] Done!"
echo "depa1 enhanced: $DEPA1_OUT/enhanced/"
echo "loft2 enhanced: $LOFT2_OUT/enhanced/"
echo "$(date)"
