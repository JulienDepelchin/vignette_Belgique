"""
Extrait les noeuds 'place' (villages/hameaux/villes) et les feux de circulation
(highway=traffic_signals) du PBF fusionne, pour les statistiques editoriales
(villages traverses, nombre de feux).
"""
import sys
import osmium
import geopandas as gpd
from shapely.geometry import Point

sys.stdout.reconfigure(encoding="utf-8")

PBF = "d:/vignette_belgique/tools/belgium_npdc_merged.osm.pbf"
OUT_PLACES = "d:/vignette_belgique/data/osm_places.gpkg"
OUT_SIGNALS = "d:/vignette_belgique/data/osm_traffic_signals.gpkg"

PLACE_TYPES = {"city", "town", "village", "hamlet", "suburb"}


class Handler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.places = []
        self.signals = []

    def node(self, n):
        if not n.location.valid():
            return
        place = n.tags.get("place")
        if place in PLACE_TYPES:
            self.places.append({
                "name": n.tags.get("name", ""), "place_type": place,
                "geometry": Point(n.location.lon, n.location.lat),
            })
        if n.tags.get("highway") == "traffic_signals":
            self.signals.append({"geometry": Point(n.location.lon, n.location.lat)})


print("Lecture des noeuds place/traffic_signals...")
h = Handler()
h.apply_file(PBF, locations=False)
print(f"{len(h.places)} noeuds 'place', {len(h.signals)} feux de circulation")

gpd.GeoDataFrame(h.places, crs="EPSG:4326").to_file(OUT_PLACES, driver="GPKG")
gpd.GeoDataFrame(h.signals, crs="EPSG:4326").to_file(OUT_SIGNALS, driver="GPKG")
print(f"exporte -> {OUT_PLACES}, {OUT_SIGNALS}")
