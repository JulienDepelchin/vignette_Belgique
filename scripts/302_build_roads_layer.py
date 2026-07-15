"""
Cache reutilisable des troncons routiers (highway=*) avec ref/highway/surface,
pour la classification par type de route (communale/departementale/nationale/
autoroute) et par revetement dans le pipeline.
"""
import sys
import osmium
import geopandas as gpd
from shapely.geometry import LineString

sys.stdout.reconfigure(encoding="utf-8")

PBF = "d:/vignette_belgique/tools/belgium_npdc_merged.osm.pbf"
OUT = "d:/vignette_belgique/data/osm_roads.gpkg"

EXCLUDE = {"path", "footway", "cycleway", "steps", "bridleway", "pedestrian", "platform", "proposed", "construction"}


class Handler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.rows = []

    def way(self, w):
        hw = w.tags.get("highway")
        if not hw or hw in EXCLUDE:
            return
        if not w.nodes or not all(n.location.valid() for n in w.nodes):
            return
        coords = [(n.location.lon, n.location.lat) for n in w.nodes]
        if len(coords) < 2:
            return
        self.rows.append({
            "highway": hw,
            "ref": w.tags.get("ref", ""),
            "surface": w.tags.get("surface", ""),
            "name": w.tags.get("name", ""),
            "geometry": LineString(coords),
        })


print("Lecture des troncons routiers (peut prendre quelques minutes)...")
h = Handler()
h.apply_file(PBF, locations=True)
print(f"{len(h.rows)} troncons")

gdf = gpd.GeoDataFrame(h.rows, crs="EPSG:4326")
gdf.to_file(OUT, driver="GPKG")
print(f"exporte -> {OUT}")
