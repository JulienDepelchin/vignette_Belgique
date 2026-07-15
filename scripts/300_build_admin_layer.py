"""
Extrait les limites communales (admin_level=8) du PBF fusionne pour permettre
le comptage 'nombre de communes traversees' par tracé.
"""
import sys
import osmium
import osmium.geom
import geopandas as gpd
from shapely import wkb as shapely_wkb

sys.stdout.reconfigure(encoding="utf-8")

PBF = "d:/vignette_belgique/tools/belgium_npdc_merged.osm.pbf"
OUT = "d:/vignette_belgique/data/osm_communes.gpkg"

wkbfab = osmium.geom.WKBFactory()


class AdminHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.n_areas = 0

    def area(self, a):
        self.n_areas += 1
        if a.tags.get("boundary") != "administrative":
            return
        if a.tags.get("admin_level") != "8":
            return
        name = a.tags.get("name", "")
        try:
            wkb = wkbfab.create_multipolygon(a)
        except Exception:
            return
        geom = shapely_wkb.loads(wkb, hex=True)
        self.rows.append({"name": name, "geometry": geom})


print("Assemblage des zones administratives (peut prendre plusieurs minutes)...")
h = AdminHandler()
h.apply_file(PBF, locations=True, idx="flex_mem")
print(f"{h.n_areas} areas vues, {len(h.rows)} communes (admin_level=8) retenues")

if h.rows:
    gdf = gpd.GeoDataFrame(h.rows, crs="EPSG:4326")
    gdf.to_file(OUT, driver="GPKG")
    print(f"exporte -> {OUT}")
else:
    print("AUCUNE commune extraite -- verifier le filtre / la disponibilite des relations dans le PBF")
