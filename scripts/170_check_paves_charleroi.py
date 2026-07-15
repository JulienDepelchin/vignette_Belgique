import sys
import re
from pathlib import Path

import osmium
import geopandas as gpd
from shapely.geometry import LineString, Point

sys.stdout.reconfigure(encoding="utf-8")

PBF = "d:/vignette_belgique/tools/belgium_npdc_merged.osm.pbf"
GPX = Path("d:/vignette_belgique/data/traces_finales_gpx/Charleroi_Aeroport_option5.gpx")

PAVE_SURFACES = {"cobblestone", "sett", "unhewn_cobblestone", "paving_stones"}
TOLERANCE_M = 12

TRKPT_RE = re.compile(r'<trkpt lat="([\-\d.]+)" lon="([\-\d.]+)"\s*/?>')


class PaveHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.ways = []

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


print("lecture des paves dans le PBF fusionne...")
h = PaveHandler()
h.apply_file(PBF, locations=True)
print(f"{len(h.ways)} troncons paves/sett/paving_stones trouves dans toute la zone")

pave_gdf = gpd.GeoDataFrame(
    {"name": [w[0] for w in h.ways], "surface": [w[1] for w in h.ways]},
    geometry=[w[2] for w in h.ways], crs="EPSG:4326",
).to_crs("EPSG:31370")
pave_gdf["buf"] = pave_gdf.buffer(TOLERANCE_M)
sindex = gpd.GeoSeries(pave_gdf["buf"]).sindex

text = GPX.read_text(encoding="utf-8")
pts = [(float(lat), float(lon)) for lat, lon in TRKPT_RE.findall(text)]
print(f"\n{GPX.name}: {len(pts)} points")

gdf_pts = gpd.GeoSeries([Point(lon, lat) for lat, lon in pts], crs="EPSG:4326").to_crs("EPSG:31370")

hits = []
for i, pt in enumerate(gdf_pts):
    cand_idx = list(sindex.query(pt.buffer(1)))
    for ci in cand_idx:
        if pave_gdf["buf"].iloc[ci].contains(pt):
            hits.append((i, pts[i], pave_gdf["name"].iloc[ci], pave_gdf["surface"].iloc[ci]))
            break

if not hits:
    print("OK: aucun troncon pave/sett detecte")
else:
    print(f"ALERTE: {len(hits)} points sur troncon pave/sett detectes\n")
    # regrouper par sequences contigues
    groups = []
    cur = [hits[0]]
    for h_ in hits[1:]:
        if h_[0] - cur[-1][0] <= 3:
            cur.append(h_)
        else:
            groups.append(cur)
            cur = [h_]
    groups.append(cur)
    for g in groups:
        idx_start, idx_end = g[0][0], g[-1][0]
        names = sorted(set((x[2], x[3]) for x in g))
        print(f"  indices {idx_start}-{idx_end} ({idx_end-idx_start+1} points): {names}")
        print(f"    debut: {g[0][1]}  fin: {g[-1][1]}")
