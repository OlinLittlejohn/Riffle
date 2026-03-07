#!/usr/bin/env python3
"""
Riffle — Fetch OSM geometry for new rivers and append to RIVER_GEOMETRY.js

Run this when adding new rivers. It fetches only the rivers listed in
NEW_RIVERS and appends them to your existing RIVER_GEOMETRY.js file.

Usage:
  python3 fetch_geometry.py

Requirements:
  pip install requests
"""

import requests
import json
import time
import re

# Add new rivers here whenever you expand the map
NEW_RIVERS = [
    "Columbia River",
    "Snake River",
]

BBOX = "41.9,-124.7,46.5,-116.4"  # slightly expanded north for Snake/Columbia
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def fetch_one(river_name, retries=4):
    query = (
        f'[out:json][timeout:60];'
        f'way["waterway"="river"]["name"="{river_name}"]({BBOX});'
        f'out geom;'
    )
    for attempt in range(retries):
        try:
            r = requests.post(OVERPASS_URL, data={"data": query}, timeout=90)
            if r.status_code == 429:
                wait = 45 * (attempt + 1)
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if r.status_code == 504:
                wait = 20 * (attempt + 1)
                print(f"    Gateway timeout, waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()["elements"]
        except requests.exceptions.Timeout:
            wait = 20 * (attempt + 1)
            print(f"    Request timeout, waiting {wait}s...")
            time.sleep(wait)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(15)
            else:
                raise
    raise Exception(f"Failed after {retries} attempts")


def elements_to_segments(elements, river_name):
    segments = []
    for el in elements:
        if not el.get("geometry"):
            continue
        if el.get("tags", {}).get("name") != river_name:
            continue
        coords = [[round(p["lat"], 5), round(p["lon"], 5)] for p in el["geometry"]]
        if len(coords) >= 2:
            segments.append(coords)
    return segments


def main():
    new_geometry = {}

    print("=== Fetching new rivers ===\n")
    for i, name in enumerate(NEW_RIVERS):
        print(f"[{i+1}/{len(NEW_RIVERS)}] {name}...", flush=True)
        try:
            elements = fetch_one(name)
            segs = elements_to_segments(elements, name)
            if segs:
                new_geometry[name] = {"segments": segs}
                pts = sum(len(s) for s in segs)
                print(f"  OK: {len(segs)} segments, {pts} points")
            else:
                print(f"  No segments found")
        except Exception as e:
            print(f"  FAILED: {e}")
        if i < len(NEW_RIVERS) - 1:
            time.sleep(6)

    if not new_geometry:
        print("\nNo rivers fetched. Check your connection and try again.")
        return

    # Read existing RIVER_GEOMETRY.js and append new entries
    existing_file = "RIVER_GEOMETRY.js"
    try:
        existing = open(existing_file).read()
        # Strip the const declaration and trailing semicolon to get raw JSON
        json_str = re.sub(r'^const RIVER_GEOMETRY = ', '', existing.strip())
        json_str = re.sub(r';$', '', json_str)
        geometry = json.loads(json_str)
        print(f"\nLoaded existing {existing_file} ({len(geometry)} rivers)")
    except Exception as e:
        print(f"\nCould not read {existing_file}: {e}")
        print("Creating new file with fetched rivers only.")
        geometry = {}

    # Merge new rivers in
    for name, data in new_geometry.items():
        if name in geometry:
            print(f"  Overwriting existing entry for {name}")
        else:
            print(f"  Adding {name}")
        geometry[name] = data

    # Write back
    js_output = "const RIVER_GEOMETRY = " + json.dumps(geometry, separators=(",", ":")) + ";"
    with open(existing_file, "w") as f:
        f.write(js_output)

    print(f"\nDone! {existing_file} now has {len(geometry)} rivers.")
    print("\nInstructions:")
    print("  1. Commit the updated RIVER_GEOMETRY.js to your GitHub repo")
    print("  2. No changes needed to index.html")


if __name__ == "__main__":
    main()