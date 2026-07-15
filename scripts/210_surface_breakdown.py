"""
Repartition du revetement (asphalte / pave / non-asphalte / inconnu) le long de
chaque trace finale, par correspondance au troncon OSM le plus proche (PBF
fusionne non restreint, pour couvrir aussi le cote francais).
"""
import re
import sys
from pathlib import Path

import osmium
import geopandas as gpd
from shapely.geometry import LineString, Point

sys.stdout.reconfigure(encoding="utf-8")

PBF = "d:/vignette_belgique/tools/belgium_npdc_merged.osm.pbf"
TRACES_DIR = Path("d:/vignette_belgique/data/traces_finales_definitives")
TOLERANCE_M = 15

ASPHALT = {"asphalt", "concrete", "concrete:plates", "concrete:lanes", "paved", "metal", "wood"}
PAVE = {"cobblestone", "sett", "unhewn_cobblestone", "paving_stones"}
NON_ASPHALT = {"gravel", "fine_gravel", "dirt", "ground", "compacted", "unpaved",
               "grass", "sand", "mud", "earth", "pebblestone", "woodchips"}

TRKPT_RE = re.compile(r'<trkpt lat="([\-\d.]+)" lon="([\-\d.]+)"')


class SurfaceHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.ways = []

    def way(self, w):
        if "highway" not in w.tags:
            return
        if not w.nodes or not all(n.location.valid() for n in w.nodes):
            return
        coords = [(n.location.lon, n.location.lat) for n in w.nodes]
        if len(coords) < 2:
            return
        surf = w.tags.get("surface", "")
        self.ways.append((surf, LineString(coords)))


def categorize(surf):
    if not surf:
        return "inconnu"
    if surf in ASPHALT:
        return "asphalte"
    if surf in PAVE:
        return "pave"
    if surf in NON_ASPHALT:
        return "non_asphalte"
    return "autre"


print("Lecture des surfaces OSM (PBF non restreint, complet)...")
h = SurfaceHandler()
h.apply_file(PBF, locations=True)
print(f"  {len(h.ways)} troncons highway avec geometrie\n")

ways_gdf = gpd.GeoDataFrame(
    {"surface": [w[0] for w in h.ways], "categorie": [categorize(w[0]) for w in h.ways]},
    geometry=[w[1] for w in h.ways], crs="EPSG:4326",
).to_crs("EPSG:31370")
sidx = ways_gdf.sindex

from math import radians, sin, cos, asin, sqrt


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
    return 2 * R * asin(sqrt(a))


results = {}
for fp in sorted(TRACES_DIR.glob("*.gpx")):
    text = fp.read_text(encoding="utf-8")
    pts = [(float(lat), float(lon)) for lat, lon in TRKPT_RE.findall(text)]

    seg_km = {"asphalte": 0.0, "pave": 0.0, "non_asphalte": 0.0, "autre": 0.0, "inconnu": 0.0}
    total_km = 0.0
    for i in range(len(pts) - 1):
        lat1, lon1 = pts[i]
        lat2, lon2 = pts[i + 1]
        d = haversine(lat1, lon1, lat2, lon2)
        total_km += d / 1000
        midlat, midlon = (lat1 + lat2) / 2, (lon1 + lon2) / 2
        pt = gpd.GeoSeries([Point(midlon, midlat)], crs="EPSG:4326").to_crs("EPSG:31370").iloc[0]
        cand_idx = list(sidx.query(pt.buffer(TOLERANCE_M)))
        if not cand_idx:
            seg_km["inconnu"] += d / 1000
            continue
        dists = ways_gdf.geometry.iloc[cand_idx].distance(pt)
        best = dists.idxmin()
        if dists.loc[best] > TOLERANCE_M:
            seg_km["inconnu"] += d / 1000
            continue
        cat = ways_gdf["categorie"].iloc[best]
        seg_km[cat] += d / 1000

    results[fp.stem] = (total_km, seg_km)
    print(f"{fp.stem}: {total_km:.2f} km total")
    for cat, km in seg_km.items():
        if km > 0.01:
            pct = 100 * km / total_km
            print(f"    {cat}: {km:.2f} km ({pct:.1f}%)")
    print()

print("\n=== RESUME ===")
print(f"{'Lieu':<20} {'km total':>10} {'asphalte %':>12} {'pave %':>9} {'non-asph %':>12} {'inconnu %':>11}")
for name, (total, seg) in results.items():
    print(f"{name:<20} {total:>10.2f} {100*seg['asphalte']/total:>11.1f}% {100*seg['pave']/total:>8.1f}% {100*seg['non_asphalte']/total:>11.1f}% {100*seg['inconnu']/total:>10.1f}%")
