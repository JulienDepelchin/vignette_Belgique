import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

DATA_DIR = Path("d:/vignette_belgique/data/traces_finales_gpx")
ORIG = DATA_DIR / "Charleroi_Aeroport_option4.gpx"
BYPASS_COORDS = Path("d:/vignette_belgique/scripts/tmp_bypass_coords.json")
OUT = DATA_DIR / "Charleroi_Aeroport_option5.gpx"

TRKPT_RE = re.compile(r'<trkpt lat="([\-\d.]+)" lon="([\-\d.]+)"\s*/?>')


def haversine(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, asin, sqrt
    R = 6371000
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
    return 2 * R * asin(sqrt(a))


text = ORIG.read_text(encoding="utf-8")
pts = [(float(lat), float(lon)) for lat, lon in TRKPT_RE.findall(text)]
print(f"trace originale: {len(pts)} points")

with open(BYPASS_COORDS, encoding="utf-8") as f:
    bypass_lonlat = json.load(f)
bypass = [(lat, lon) for lon, lat in bypass_lonlat]
print(f"deviation: {len(bypass)} points")

start_target = bypass[0]
end_target = bypass[-1]

dists_start = [haversine(lat, lon, *start_target) for lat, lon in pts]
dists_end = [haversine(lat, lon, *end_target) for lat, lon in pts]

idx_start = min(range(len(pts)), key=lambda i: dists_start[i])
idx_end = min(range(len(pts)), key=lambda i: dists_end[i])

print(f"point de raccord AVANT: index {idx_start}, {pts[idx_start]}, distance a la deviation: {dists_start[idx_start]:.0f}m")
print(f"point de raccord APRES: index {idx_end}, {pts[idx_end]}, distance a la deviation: {dists_end[idx_end]:.0f}m")

if idx_end <= idx_start:
    raise SystemExit(f"ERREUR: point de fin (idx {idx_end}) avant point de debut (idx {idx_start})")

merged = pts[:idx_start] + bypass + pts[idx_end + 1:]
print(f"trace fusionnee: {len(merged)} points ({len(pts)} - {idx_end - idx_start + 1} remplaces par {len(bypass)})")

trkpts = "\n".join(f'      <trkpt lat="{lat}" lon="{lon}"></trkpt>' for lat, lon in merged)
gpx = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="vignette-belgique" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>Charleroi_Aeroport_option5</name>
    <desc>{escape("Option 4 (corrigee a la main par l'utilisateur) avec contournement du Chemin de Catomoreau/Catamouriaux "
                   "(piste forestiere interdite aux voitures) via le centre de Waterloo + Chemin du Smohain / Chemin de la Marache, "
                   "sur voirie publique uniquement (aucune route privee, aucune piste interdite).")}</desc>
    <trkseg>
{trkpts}
    </trkseg>
  </trk>
</gpx>
"""
OUT.write_text(gpx, encoding="utf-8")
print(f"exporte: {OUT}")
