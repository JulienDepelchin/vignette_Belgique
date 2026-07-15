"""Extrait les passages a niveau (railway=level_crossing) du PBF fusionne."""
import sys
import osmium
import geopandas as gpd
from shapely.geometry import Point

sys.stdout.reconfigure(encoding="utf-8")

PBF = "d:/vignette_belgique/tools/belgium_npdc_merged.osm.pbf"
OUT = "d:/vignette_belgique/data/osm_level_crossings.gpkg"


class Handler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.rows = []

    def node(self, n):
        if not n.location.valid():
            return
        if n.tags.get("railway") == "level_crossing":
            self.rows.append({"geometry": Point(n.location.lon, n.location.lat)})


print("Lecture des passages a niveau...")
h = Handler()
h.apply_file(PBF, locations=False)
print(f"{len(h.rows)} passages a niveau")
gpd.GeoDataFrame(h.rows, crs="EPSG:4326").to_file(OUT, driver="GPKG")
print(f"exporte -> {OUT}")
