import sys
import re
from pathlib import Path

import osmium
import geopandas as gpd
from shapely.geometry import LineString, Point

sys.stdout.reconfigure(encoding="utf-8")

PBF = "d:/vignette_belgique/tools/belgium_npdc_merged.osm.pbf"
TRACES_DIR = Path("d:/vignette_belgique/data/traces_finales_definitives")
FILES = ["Famiflora.gpx", "Pairi_Daiza.gpx", "Tournai.gpx"]

PAVE_SURFACES = {"cobblestone", "sett", "unhewn_cobblestone", "paving_stones"}
TOLERANCE_M = 12

TRKPT_RE = re.compile(r'<trkpt lat="([\-\d.]+)" lon="([\-\d.]+)"\s*/?>')


class PaveHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.ways = []  # (name, geometry)

    def way(self, w):
        surf = w.tags.get("surface", "")
        if surf not in PAVE_SURFACES:
            return
        if not w.nodes or not all(n.location.valid() for n in w.nodes):
            return
        coords = [(n.location.lon, n.location.lat) for n in w.nodes]
        if len(coords) < 2:
            return
        name = w.tags.get("name", "(sans nom)")
        self.ways.append((name, surf, LineString(coords)))


print("lecture des paves dans le PBF fusionne (peut prendre un moment)...")
h = PaveHandler()
h.apply_file(PBF, locations=True)
print(f"{len(h.ways)} troncons paves/sett/paving_stones trouves dans toute la zone")

if not h.ways:
    print("aucun trocon pave trouve, rien a verifier")
    raise SystemExit

pave_gdf = gpd.GeoDataFrame(
    {"name": [w[0] for w in h.ways], "surface": [w[1] for w in h.ways]},
    geometry=[w[2] for w in h.ways], crs="EPSG:4326",
).to_crs("EPSG:31370")
pave_gdf["geometry"] = pave_gdf.buffer(TOLERANCE_M)
pave_union = pave_gdf.union_all()
sindex = pave_gdf.sindex

for fname in FILES:
    fp = TRACES_DIR / fname
    text = fp.read_text(encoding="utf-8")
    pts = [(float(lat), float(lon)) for lat, lon in TRKPT_RE.findall(text)]
    gdf_pts = gpd.GeoSeries([Point(lon, lat) for lat, lon in pts], crs="EPSG:4326").to_crs("EPSG:31370")

    hits = []
    for i, pt in enumerate(gdf_pts):
        cand_idx = list(sindex.query(pt.buffer(1)))
        for ci in cand_idx:
            if pave_gdf.geometry.iloc[ci].contains(pt):
                hits.append((i, pts[i], pave_gdf["name"].iloc[ci], pave_gdf["surface"].iloc[ci]))
                break

    print(f"\n=== {fname} ({len(pts)} points) ===")
    if not hits:
        print("  OK: aucun troncon pave/sett detecte, tout est hors zone pavee")
    else:
        print(f"  ALERTE: {len(hits)} points sur troncon pave/sett detectes")
        seen_names = {}
        for idx, (lat, lon), name, surf in hits:
            seen_names.setdefault((name, surf), []).append((idx, lat, lon))
        for (name, surf), occ in seen_names.items():
            first = occ[0]
            print(f"    - {name} (surface={surf}): {len(occ)} points, ex. index {first[0]} ({first[1]:.6f},{first[2]:.6f})")
