#!/usr/bin/env python3
"""
gen_tour_json.py — Generate tour.json with hotspot navigation from config.json.

Usage:
    python3 gen_tour_json.py <config.json> <output_tour.json>
    python3 gen_tour_json.py <config.json> <scene_id> <output_tour.json>

scene_id overrides config["id"] when given.
"""

import sys
import json
import math


def room_center(room):
    """Return (cx, cy) in Blender XY coords (X=east, Y=north)."""
    return (room["x"] + room["w"] / 2.0, room["y"] + room["d"] / 2.0)


def x_ranges_overlap(r1, r2, min_overlap=0.5):
    """X ranges overlap by at least min_overlap metres (needed for N/S wall sharing)."""
    r1_xmin, r1_xmax = r1["x"], r1["x"] + r1["w"]
    r2_xmin, r2_xmax = r2["x"], r2["x"] + r2["w"]
    overlap = min(r1_xmax, r2_xmax) - max(r1_xmin, r2_xmin)
    return overlap >= min_overlap


def y_ranges_overlap(r1, r2, min_overlap=0.5):
    """Y ranges overlap by at least min_overlap metres (needed for E/W wall sharing)."""
    r1_ymin, r1_ymax = r1["y"], r1["y"] + r1["d"]
    r2_ymin, r2_ymax = r2["y"], r2["y"] + r2["d"]
    overlap = min(r1_ymax, r2_ymax) - max(r1_ymin, r2_ymin)
    return overlap >= min_overlap


def gap_between(r1_min, r1_max, r2_min, r2_max):
    """Gap between two 1-D intervals.  Negative = they overlap."""
    if r2_min >= r1_max:
        return r2_min - r1_max
    if r1_min >= r2_max:
        return r1_min - r2_max
    return -(min(r1_max, r2_max) - max(r1_min, r2_min))


def are_adjacent(r1, r2, gap_threshold=0.6):
    """
    True if r1 and r2 share or nearly-share a wall.
    - East/West shared wall: Y ranges overlap ≥0.5 m, X gap ≤ gap_threshold.
    - North/South shared wall: X ranges overlap ≥0.5 m, Y gap ≤ gap_threshold.
    """
    x_gap = gap_between(r1["x"], r1["x"] + r1["w"], r2["x"], r2["x"] + r2["w"])
    y_gap = gap_between(r1["y"], r1["y"] + r1["d"], r2["y"], r2["y"] + r2["d"])

    east_west_adj   = y_ranges_overlap(r1, r2) and (0 <= x_gap <= gap_threshold)
    north_south_adj = x_ranges_overlap(r1, r2) and (0 <= y_gap <= gap_threshold)

    return east_west_adj or north_south_adj


def compute_yaw(from_room, to_room):
    """
    Compass yaw (degrees) from from_room toward to_room, in panorama space.

    Blender/config: X = east, Y = north.
    Three.js/Pannellum panorama: yaw 0 = looking along −Z (which maps to +Y = north).
    Formula: yaw = atan2(dx, dy)  where dy = cy_to − cy_from (positive = north).
    This gives 0 = north, 90 = east, 180/−180 = south, −90 = west.
    """
    cx1, cy1 = room_center(from_room)
    cx2, cy2 = room_center(to_room)
    dx = cx2 - cx1
    dy = cy2 - cy1
    return round(math.degrees(math.atan2(dx, dy)), 1)


def is_mezzanine(room):
    return room.get("z_offset", 0.0) >= 1.0


def build_adjacency(rooms, gap_threshold=0.6):
    """
    Return list of (kind, room_a_id, room_b_id) triples.
    kind is 'normal' or 'staircase'.
    """
    connections = []
    n = len(rooms)
    for i in range(n):
        for j in range(i + 1, n):
            r1, r2 = rooms[i], rooms[j]
            mez1, mez2 = is_mezzanine(r1), is_mezzanine(r2)

            if mez1 and mez2:
                # Mezzanine ↔ Mezzanine: treat as normal adjacency on their level
                if are_adjacent(r1, r2, gap_threshold):
                    connections.append(("normal", r1["id"], r2["id"]))
                continue

            if mez1 != mez2:
                # Mezzanine ↔ Ground: staircase link when footprints overlap
                if x_ranges_overlap(r1, r2, min_overlap=0.5) or y_ranges_overlap(r1, r2, min_overlap=0.5):
                    connections.append(("staircase", r1["id"], r2["id"]))
                continue

            # Ground ↔ Ground
            if are_adjacent(r1, r2, gap_threshold):
                connections.append(("normal", r1["id"], r2["id"]))

    return connections


def largest_room(rooms):
    """Return id of the ground-floor room with the greatest area."""
    ground = [r for r in rooms if not is_mezzanine(r)]
    if not ground:
        return rooms[0]["id"]
    return max(ground, key=lambda r: r["w"] * r["d"])["id"]


def generate_tour(config, scene_override=None):
    scene    = scene_override if scene_override else config["id"]
    name     = config.get("name", scene)
    rooms    = config["rooms"]
    room_map = {r["id"]: r for r in rooms}

    connections = build_adjacency(rooms)

    # Diagnostics
    print(f"Scene: {scene}")
    print(f"Rooms: {[r['id'] for r in rooms]}")
    print("Connections found:")
    for conn in connections:
        kind, a, b = conn
        print(f"  {a} <-> {b}  [{kind}]")
    if not connections:
        print("  (none — all rooms isolated)")

    # Build hotspot lists per room
    hotspots_by_room = {r["id"]: [] for r in rooms}

    for conn in connections:
        kind, a_id, b_id = conn
        ra = room_map[a_id]
        rb = room_map[b_id]
        mez_a = is_mezzanine(ra)

        if kind == "normal":
            yaw_ab = compute_yaw(ra, rb)
            hotspots_by_room[a_id].append({
                "target": b_id,
                "label":  rb["label"],
                "yaw":    yaw_ab,
                "pitch":  -8
            })
            yaw_ba = compute_yaw(rb, ra)
            hotspots_by_room[b_id].append({
                "target": a_id,
                "label":  ra["label"],
                "yaw":    yaw_ba,
                "pitch":  -8
            })

        else:  # staircase
            ground_id = b_id if mez_a else a_id
            mez_id    = a_id if mez_a else b_id
            rg = room_map[ground_id]
            rm = room_map[mez_id]

            yaw_up   = compute_yaw(rg, rm)
            yaw_down = compute_yaw(rm, rg)

            hotspots_by_room[ground_id].append({
                "target": mez_id,
                "label":  "Mezanine",
                "yaw":    yaw_up,
                "pitch":  -20
            })
            hotspots_by_room[mez_id].append({
                "target": ground_id,
                "label":  "Planta Baja",
                "yaw":    yaw_down,
                "pitch":  -20
            })

    # Build rooms output
    rooms_out = []
    for room in rooms:
        rid = room["id"]
        rooms_out.append({
            "id":       rid,
            "label":    room["label"],
            "panorama": f"/panoramas/{scene}/{rid}.jpg",
            "hotspots": hotspots_by_room[rid]
        })

    # Floorplan — ground floor only
    ground_rooms = [r for r in rooms if not is_mezzanine(r)]
    all_x = [r["x"] for r in ground_rooms] + [r["x"] + r["w"] for r in ground_rooms]
    all_y = [r["y"] for r in ground_rooms] + [r["y"] + r["d"] for r in ground_rooms]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    fp_rooms = [
        {
            "id":    r["id"],
            "x":     r["x"],
            "y":     r["y"],
            "w":     r["w"],
            "h":     r["d"],   # panoViewer minimap uses "h"
            "label": r["label"]
        }
        for r in ground_rooms
    ]

    floorplan = {
        "bounds": {
            "minX": round(min_x, 3),
            "minY": round(min_y, 3),
            "maxX": round(max_x, 3),
            "maxY": round(max_y, 3)
        },
        "rooms": fp_rooms
    }

    return {
        "scene":     scene,
        "name":      name,
        "startRoom": largest_room(rooms),
        "rooms":     rooms_out,
        "floorplan": floorplan
    }


def main():
    if len(sys.argv) == 3:
        config_path  = sys.argv[1]
        scene_id     = None
        output_path  = sys.argv[2]
    elif len(sys.argv) == 4:
        config_path  = sys.argv[1]
        scene_id     = sys.argv[2]
        output_path  = sys.argv[3]
    else:
        print("Usage: python3 gen_tour_json.py <config.json> [<scene_id>] <output_tour.json>")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    tour = generate_tour(config, scene_override=scene_id)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tour, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {output_path}")


if __name__ == "__main__":
    main()
