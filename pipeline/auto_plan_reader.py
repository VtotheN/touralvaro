"""
auto_plan_reader.py — Extract room dimensions from architectural floor plan images.
Usage: python3 auto_plan_reader.py <floor_plan.jpg> [--output config.json] [--scale 1.0]
       --scale: meters per 100 pixels (auto-detected if dimension text found)

Output: JSON config for gen_apartment.py
"""
import cv2
import numpy as np
import json
import sys
import argparse
import os
import re
from pathlib import Path

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("WARNING: pytesseract not available. Install: pip install pytesseract")
    print("         Also: brew install tesseract")

# ── CLI ────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Floor plan reader")
parser.add_argument("image", help="Floor plan image path")
parser.add_argument("--output", "-o", default=None, help="Output JSON path")
parser.add_argument("--scale", "-s", type=float, default=None, help="meters per 100px")
parser.add_argument("--name", default="proyecto", help="Project name")
parser.add_argument("--ceiling", type=float, default=2.8, help="Ceiling height in meters")
parser.add_argument("--debug", action="store_true", help="Save debug images")
args = parser.parse_args()

img_path = args.image
output_path = args.output or img_path.replace(".jpg", "_config.json").replace(".png", "_config.json")

# ── Load image ─────────────────────────────────────────────────────────────────
img = cv2.imread(img_path)
if img is None:
    print(f"ERROR: Cannot read {img_path}")
    sys.exit(1)

h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
print(f"Image: {w}×{h}px")

# ── Preprocessing ──────────────────────────────────────────────────────────────
# Increase contrast
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
enhanced = clahe.apply(gray)

# Threshold to binary
_, binary = cv2.threshold(enhanced, 200, 255, cv2.THRESH_BINARY_INV)
# Morphological cleanup
kernel = np.ones((3,3), np.uint8)
binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)

# ── OCR: extract dimension text ────────────────────────────────────────────────
dimensions_found = []
scale_meters_per_px = args.scale / 100.0 if args.scale else None

if OCR_AVAILABLE:
    try:
        ocr_text = pytesseract.image_to_string(img, config="--psm 11")
        # Match patterns like: 4.50, 3,20, 450, 320 (with optional m or cm)
        patterns = [
            r'\b(\d+[.,]\d{2})\s*m?\b',   # 4.50m, 3,20
            r'\b(\d{3,4})\s*cm\b',          # 450cm
            r'\b(\d{1,2}[.,]\d{1,2})\b',   # 4.5, 3.2
        ]
        for pat in patterns:
            matches = re.findall(pat, ocr_text)
            for m in matches:
                val = float(m.replace(",", "."))
                if 0.5 < val < 50:  # plausible room dimension in meters
                    dimensions_found.append(val)
        if dimensions_found:
            print(f"OCR dimensions found: {sorted(set(dimensions_found))}")
    except Exception as e:
        print(f"OCR warning: {e}")

# ── Contour detection: find rooms ─────────────────────────────────────────────
# Find thick contours (walls)
edges = cv2.Canny(enhanced, 50, 150)
edges = cv2.dilate(edges, kernel, iterations=1)

contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

# Filter and approximate contours to rectangles
rooms_raw = []
min_area_px = (w * h) * 0.005  # min 0.5% of image
max_area_px = (w * h) * 0.70   # max 70% of image

for cnt in contours:
    area = cv2.contourArea(cnt)
    if area < min_area_px or area > max_area_px:
        continue

    # Approximate to polygon
    epsilon = 0.03 * cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, epsilon, True)

    # Accept quadrilaterals (4-6 points for imperfect rectangles)
    if 4 <= len(approx) <= 6:
        x, y, rw, rh = cv2.boundingRect(approx)
        aspect = max(rw, rh) / max(min(rw, rh), 1)
        if aspect < 5.0:  # not too elongated
            rooms_raw.append({
                "px_x": x, "px_y": y,
                "px_w": rw, "px_h": rh,
                "px_area": area,
                "approx_pts": len(approx)
            })

# ── Deduplicate overlapping rooms ─────────────────────────────────────────────
def iou(a, b):
    ix = max(0, min(a["px_x"]+a["px_w"], b["px_x"]+b["px_w"]) - max(a["px_x"], b["px_x"]))
    iy = max(0, min(a["px_y"]+a["px_h"], b["px_y"]+b["px_h"]) - max(a["px_y"], b["px_y"]))
    inter = ix * iy
    union = a["px_w"]*a["px_h"] + b["px_w"]*b["px_h"] - inter
    return inter / max(union, 1)

rooms_raw.sort(key=lambda r: -r["px_area"])
rooms_dedup = []
for r in rooms_raw:
    overlap = any(iou(r, kept) > 0.4 for kept in rooms_dedup)
    if not overlap:
        rooms_dedup.append(r)

rooms_dedup = rooms_dedup[:12]  # max 12 rooms
print(f"Rooms detected: {len(rooms_dedup)}")

# ── Scale estimation ──────────────────────────────────────────────────────────
if scale_meters_per_px is None:
    if dimensions_found and rooms_dedup:
        # Estimate: median OCR dimension / median room pixel size
        med_dim = sorted(dimensions_found)[len(dimensions_found)//2]
        med_px = sorted([max(r["px_w"], r["px_h"]) for r in rooms_dedup])[len(rooms_dedup)//2]
        scale_meters_per_px = med_dim / med_px
        print(f"Scale auto-detected: {scale_meters_per_px:.4f} m/px")
    else:
        # Fallback: assume image is 20m wide
        scale_meters_per_px = 20.0 / w
        print(f"Scale fallback (20m width): {scale_meters_per_px:.4f} m/px")

# ── Build room configs ────────────────────────────────────────────────────────
ROOM_NAMES = ["sala", "comedor", "cocina", "master", "hab2", "hab3", "baño", "terraza", "hall", "estudio", "lavanderia", "despensa"]

config_rooms = []
for i, room in enumerate(rooms_dedup):
    room_w = round(room["px_w"] * scale_meters_per_px, 2)
    room_d = round(room["px_h"] * scale_meters_per_px, 2)
    room_x = round(room["px_x"] * scale_meters_per_px, 2)
    # Flip Y (image Y is inverted vs 3D)
    room_y = round((h - room["px_y"] - room["px_h"]) * scale_meters_per_px, 2)

    # Skip too-small or too-large rooms
    if room_w < 1.5 or room_d < 1.5:
        continue
    if room_w > 20 or room_d > 20:
        continue

    name = ROOM_NAMES[i] if i < len(ROOM_NAMES) else f"room_{i}"
    label = name.replace("hab", "Habitación ").replace("baño", "Baño").title()

    config_rooms.append({
        "id": name,
        "label": label,
        "x": room_x,
        "y": room_y,
        "w": room_w,
        "d": room_d,
    })
    print(f"  {name}: {room_w}×{room_d}m at ({room_x}, {room_y})")

# ── Final config ──────────────────────────────────────────────────────────────
config = {
    "name": args.name,
    "ceiling_height": args.ceiling,
    "scale_detected": round(scale_meters_per_px * 100, 3),
    "rooms": config_rooms,
    "_meta": {
        "source_image": img_path,
        "image_size": [w, h],
        "ocr_dimensions": dimensions_found,
        "rooms_found": len(config_rooms),
        "note": "Review and adjust room positions/dimensions before generating GLB"
    }
}

with open(output_path, "w") as f:
    json.dump(config, f, indent=2)
print(f"\nConfig saved: {output_path}")
print(f"Rooms: {len(config_rooms)}")
print("\nNEXT: blender --background --python gen_apartment.py -- " + output_path + " output.glb")

# ── Debug visualization ───────────────────────────────────────────────────────
if args.debug:
    debug_img = img.copy()
    for r in rooms_dedup[:len(config_rooms)]:
        cv2.rectangle(debug_img,
                      (r["px_x"], r["px_y"]),
                      (r["px_x"]+r["px_w"], r["px_y"]+r["px_h"]),
                      (0, 255, 0), 2)
    debug_path = img_path.replace(".jpg", "_debug.jpg").replace(".png", "_debug.jpg")
    cv2.imwrite(debug_path, debug_img)
    print(f"Debug image: {debug_path}")
