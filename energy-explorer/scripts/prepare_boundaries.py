"""Normalize a Statistics Canada Ontario GeoJSON query and create its search index.

Source: 2021/Cartographic_boundary_files/MapServer/14/query
where=PRUID='35', outFields=CFSAUID,PRUID, outSR=4326,
geometryPrecision=5, maxAllowableOffset=0.0003, f=geojson.
The source's offset generalizes geometry for display, not precise boundary work.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "public/data/ontario-fsas.geojson"
data = json.loads(path.read_text())
assert data["type"] == "FeatureCollection" and data["features"]


def points(coords):
    if isinstance(coords[0], (float, int)):
        yield coords
    else:
        for child in coords:
            yield from points(child)


index = []
seen = set()
for feature in data["features"]:
    props = feature["properties"]
    fsa = props.get("CFSAUID", props.get("fsa"))
    assert props.get("PRUID", "35") == "35"
    assert fsa and fsa not in seen
    seen.add(fsa)
    feature["id"] = fsa
    feature["properties"] = {"fsa": fsa}
    coords = list(points(feature["geometry"]["coordinates"]))
    bounds = [min(p[0] for p in coords), min(p[1] for p in coords), max(p[0] for p in coords), max(p[1] for p in coords)]
    index.append({"fsa": fsa, "bounds": bounds})
data["features"].sort(key=lambda f: f["id"])
path.write_text(json.dumps(data, separators=(",", ":")))
(ROOT / "public/data/fsa-index.json").write_text(json.dumps({"boundary_version": "statcan-2021", "fsas": sorted(index, key=lambda e: e["fsa"])}, separators=(",", ":")))
print(f"Prepared {len(index)} Ontario FSAs; {path.stat().st_size / 1e6:.2f} MB GeoJSON")
