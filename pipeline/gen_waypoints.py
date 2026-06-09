#!/usr/bin/env python3
"""Auto-generate waypoints JSON from apartment config.
Usage: python3 gen_waypoints.py <config.json> <out.json>
"""
import json, sys, os

EYE_H = 1.80

def room_waypoint(room):
    rid  = room["id"]
    x0, y0, w, d = room["x"], room["y"], room["w"], room["d"]
    cx   = x0 + w / 2
    cy   = y0 + d / 2
    # Three.js: x=x, y=EYE_H, z=-(y)
    return {
        "id":       rid,
        "label":    room.get("label", rid.capitalize()),
        "position": [round(cx, 2), EYE_H, round(-cy, 2)]
    }

def main():
    cfg_path = sys.argv[1]
    out_path = sys.argv[2]
    with open(cfg_path) as f:
        cfg = json.load(f)
    rooms = cfg.get("rooms", [])
    waypoints = [room_waypoint(r) for r in rooms]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(waypoints, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(waypoints)} waypoints → {out_path}")

if __name__ == "__main__":
    main()
