#!/usr/bin/env bash
# pipeline_zero.sh — Full automation: floor plan + renders → live tour URL
# Usage: ./pipeline_zero.sh <project_name> <floor_plan.jpg> <renders_dir/> [--bake] [--vr]
# Output: viewer/public/models/<project>.glb + waypoints.json + scenes.js updated

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIEWER_DIR="$SCRIPT_DIR/../viewer"
MODELS_DIR="$VIEWER_DIR/public/models"
WAYPOINTS_DIR="$VIEWER_DIR/public/waypoints"
BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"

PROJECT_NAME="$1"
FLOOR_PLAN="$2"
RENDERS_DIR="$3"
DO_BAKE=false
DO_VR=false

for arg in "$@"; do
  [[ "$arg" == "--bake" ]] && DO_BAKE=true
  [[ "$arg" == "--vr"   ]] && DO_VR=true
done

if [[ -z "$PROJECT_NAME" || -z "$FLOOR_PLAN" || -z "$RENDERS_DIR" ]]; then
  echo "Usage: $0 <name> <floor_plan.jpg> <renders_dir/> [--bake] [--vr]"
  exit 1
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  PIPELINE ZERO — touralvaro              ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Project: $PROJECT_NAME"
echo "║  Plan: $FLOOR_PLAN"
echo "║  Renders: $RENDERS_DIR"
echo "║  Bake: $DO_BAKE | VR: $DO_VR"
echo "╚══════════════════════════════════════════╝"
echo ""

TMP_DIR="/tmp/pipeline_$PROJECT_NAME"
mkdir -p "$TMP_DIR"
mkdir -p "$MODELS_DIR" "$WAYPOINTS_DIR"

# ── PHASE 1: Read floor plan ────────────────────────────────────────────────
echo "▶ PHASE 1 — Reading floor plan..."
CONFIG_PATH="$TMP_DIR/config.json"
python3 "$SCRIPT_DIR/auto_plan_reader.py" \
  "$FLOOR_PLAN" \
  --output "$CONFIG_PATH" \
  --name "$PROJECT_NAME"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "ERROR: Floor plan reader failed. Create config.json manually."
  exit 1
fi
echo "  Config: $CONFIG_PATH"

# ── PHASE 2: Generate 3D geometry ──────────────────────────────────────────
echo ""
echo "▶ PHASE 2 — Generating 3D geometry (Blender)..."
RAW_GLB="$TMP_DIR/${PROJECT_NAME}_raw.glb"
WAYPOINTS_TMP="$TMP_DIR/${PROJECT_NAME}_raw_waypoints.json"

"$BLENDER" --background --python "$SCRIPT_DIR/gen_apartment.py" \
  -- "$CONFIG_PATH" "$RAW_GLB" 2>&1 | grep -E "DONE|Built|ERROR|Traceback"

if [[ ! -f "$RAW_GLB" ]]; then
  echo "ERROR: Blender geometry generation failed"
  exit 1
fi
echo "  GLB: $RAW_GLB ($(du -h "$RAW_GLB" | cut -f1))"

# ── PHASE 3: Apply materials from renders ──────────────────────────────────
echo ""
echo "▶ PHASE 3 — Extracting materials from renders..."
python3 "$SCRIPT_DIR/render_to_pbr.py" \
  "$RENDERS_DIR" \
  "$CONFIG_PATH" 2>&1 | grep -v "^$"

# ── PHASE 4: Bake lighting (optional) ─────────────────────────────────────
FINAL_GLB="$TMP_DIR/${PROJECT_NAME}_final.glb"
if [[ "$DO_BAKE" == "true" ]]; then
  echo ""
  echo "▶ PHASE 4 — Baking lighting (this takes ~30 min)..."
  BAKED_GLB="$TMP_DIR/${PROJECT_NAME}_baked.glb"
  "$BLENDER" --background --python "$SCRIPT_DIR/instant_bake.py" \
    -- "$RAW_GLB" "$BAKED_GLB" 128 1024 2>&1 | grep -E "DONE|Baking|ERROR"
  [[ -f "$BAKED_GLB" ]] && FINAL_GLB="$BAKED_GLB" || FINAL_GLB="$RAW_GLB"
else
  echo ""
  echo "▶ PHASE 4 — Skipping bake (use --bake for GI lighting)"
  FINAL_GLB="$RAW_GLB"
fi

# ── PHASE 5: Optimize GLB ─────────────────────────────────────────────────
echo ""
echo "▶ PHASE 5 — Optimizing GLB..."
OPTIMIZED_GLB="$MODELS_DIR/${PROJECT_NAME}.glb"

if command -v gltf-transform &>/dev/null; then
  gltf-transform optimize "$FINAL_GLB" "$OPTIMIZED_GLB" \
    --compress draco \
    --texture-compress ktx2 \
    --simplify 2>&1 | tail -3
else
  cp "$FINAL_GLB" "$OPTIMIZED_GLB"
  echo "  (gltf-transform not found, copied raw — install: npm i -g @gltf-transform/cli)"
fi

SIZE=$(du -h "$OPTIMIZED_GLB" | cut -f1)
echo "  Final GLB: $OPTIMIZED_GLB ($SIZE)"

# ── PHASE 6: Copy waypoints ────────────────────────────────────────────────
echo ""
echo "▶ PHASE 6 — Installing waypoints..."
if [[ -f "$WAYPOINTS_TMP" ]]; then
  cp "$WAYPOINTS_TMP" "$WAYPOINTS_DIR/${PROJECT_NAME}.json"
  WP_COUNT=$(python3 -c "import json; d=json.load(open('$WAYPOINTS_DIR/${PROJECT_NAME}.json')); print(len(d))")
  echo "  Waypoints: $WAYPOINTS_DIR/${PROJECT_NAME}.json ($WP_COUNT points)"
else
  echo "  WARNING: no waypoints file found, creating empty"
  echo "[]" > "$WAYPOINTS_DIR/${PROJECT_NAME}.json"
fi

# ── PHASE 7: Register scene in viewer ────────────────────────────────────────
echo ""
echo "▶ PHASE 7 — Registering scene..."
SCENES_JS="$VIEWER_DIR/src/scenes.js"
BAKED_FLAG="$( [[ "$DO_BAKE" == "true" ]] && echo "true" || echo "false" )"

python3 - <<PYEOF
import re, json
scenes_path = "$SCENES_JS"
project = "$PROJECT_NAME"
baked = $BAKED_FLAG

with open(scenes_path) as f:
    content = f.read()

# Check if already registered
if f"id: '{project}'" in content:
    print(f"  Scene '{project}' already registered")
else:
    new_entry = f"""  {{
    id: '{project}',
    label: '{project.replace("-", " ").title()}',
    url: '/models/{project}.glb',
    baked: {str(baked).lower()},
  }},"""
    content = content.replace("export const KNOWN_SCENES = [",
                               f"export const KNOWN_SCENES = [\n{new_entry}")
    with open(scenes_path, "w") as f:
        f.write(content)
    print(f"  Scene '{project}' added to scenes.js")
PYEOF

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  ✓ PIPELINE ZERO COMPLETE                ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  GLB:       $OPTIMIZED_GLB"
echo "  Waypoints: $WAYPOINTS_DIR/${PROJECT_NAME}.json"
echo "  URL:       http://localhost:5174/?scene=$PROJECT_NAME"
echo ""
echo "  Restart dev server or run: npm run build"
echo ""
