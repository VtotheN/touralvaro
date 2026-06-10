#!/bin/bash
# watch_render.sh — Wait for Blender renders to finish, then auto-enhance.
# Usage: ./pipeline/watch_render.sh [loft2|depa1|both]
# Run in background: nohup ./pipeline/watch_render.sh both &

set -e
cd "$(dirname "$0")/.."

TARGET="${1:-both}"
PYTHON="python3"

echo "[watch] Waiting for Blender to finish... (target=$TARGET)"
echo "[watch] Started at $(date)"

# Wait for all Blender processes to exit
while pgrep -x Blender > /dev/null 2>&1; do
    sleep 10
done

echo "[watch] Blender done at $(date)"

# Verify files exist
if [ "$TARGET" = "loft2" ] || [ "$TARGET" = "both" ]; then
    count_l=$(ls viewer/public/panoramas/cayena-loft2/*.jpg 2>/dev/null | wc -l | tr -d ' ')
    echo "[watch] loft2 raw renders: $count_l"
fi
if [ "$TARGET" = "depa1" ] || [ "$TARGET" = "both" ]; then
    count_d=$(ls viewer/public/panoramas/cayena-depa1/*.jpg 2>/dev/null | wc -l | tr -d ' ')
    echo "[watch] depa1 raw renders: $count_d"
fi

echo "[watch] Verifying render counts..."
for unit in loft2 depa1; do
    if [ "$TARGET" = "$unit" ] || [ "$TARGET" = "both" ]; then
        raw_dir="viewer/public/panoramas/cayena-$unit"
        config_file="test_projects/cayena-$unit/config.json"
        expected=$(python3 -c "import json,sys; d=json.load(open('$config_file')); print(len(d['rooms']))" 2>/dev/null || echo 0)
        actual=$(ls "$raw_dir"/*.jpg 2>/dev/null | wc -l | tr -d ' ')
        echo "[watch] $unit: expected $expected rooms, found $actual renders"
        if [ "$actual" -lt "$expected" ]; then
            echo "[watch] WARNING: $unit is incomplete ($actual/$expected). Some rooms may be missing."
        fi
    fi
done

echo "[watch] Running post_render.sh $TARGET ..."
./pipeline/post_render.sh "$TARGET"

echo "[watch] All done. $(date)"
echo "[watch] Tour: http://localhost:5175"
