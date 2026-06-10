#!/bin/bash
# post_render.sh — Run after Blender renders finish.
# Usage: ./pipeline/post_render.sh [loft2|depa1|both] [--esrgan]
#   --esrgan : also run Real-ESRGAN 4× upscale → 4096×2048 final

set -e
cd "$(dirname "$0")/.."

PYTHON="python3"
LOFT2_RAW="viewer/public/panoramas/cayena-loft2"
DEPA1_RAW="viewer/public/panoramas/cayena-depa1"
DO_ESRGAN=0

# Parse flags
POSITIONAL=()
for arg in "$@"; do
    case "$arg" in
        --esrgan) DO_ESRGAN=1 ;;
        *)        POSITIONAL+=("$arg") ;;
    esac
done
set -- "${POSITIONAL[@]:-}"

run_unit() {
    local unit="$1"
    local raw_dir=""
    case "$unit" in
        loft2) raw_dir="$LOFT2_RAW" ;;
        depa1) raw_dir="$DEPA1_RAW" ;;
        *) echo "Unknown unit: $unit"; exit 1 ;;
    esac

    echo ""
    echo "=== Post-render: $unit ==="
    echo "  Raw dir:      $raw_dir"
    echo "  Enhanced dir: $raw_dir/enhanced"

    # Check raw renders exist
    count=$(ls "$raw_dir"/*.jpg 2>/dev/null | wc -l | tr -d ' ')
    if [ "$count" -eq 0 ]; then
        echo "  ERROR: No JPEGs in $raw_dir"
        exit 1
    fi
    echo "  Found $count raw renders"

    # [1] Basic enhance (contrast + color + mild unsharp)
    echo ""
    echo "  [1/2] Enhancing $unit panoramas..."
    $PYTHON pipeline/enhance_panorama.py "$raw_dir" 2>&1

    # [2] Real-ESRGAN 4× upscale (optional, --esrgan flag)
    if [ "$DO_ESRGAN" -eq 1 ]; then
        echo ""
        echo "  [2/2] Real-ESRGAN upscale: enhanced/ → esrgan/ ..."
        $PYTHON pipeline/realesrgan_upscale.py "$raw_dir/enhanced" "$raw_dir/esrgan" 2>&1
        echo "  ESRGAN done → $raw_dir/esrgan/"
    else
        echo "  [2/2] Skipping ESRGAN (pass --esrgan to enable)."
    fi

    echo "  Done → $raw_dir/enhanced/"
}

case "${1:-both}" in
    loft2) run_unit loft2 ;;
    depa1) run_unit depa1 ;;
    both)
        run_unit loft2
        run_unit depa1
        ;;
    *) echo "Usage: $0 loft2|depa1|both"; exit 1 ;;
esac

echo ""
echo "=== All done. Dev server: http://localhost:5175 ==="
