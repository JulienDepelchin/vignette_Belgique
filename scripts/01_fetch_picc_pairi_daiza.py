"""
Pilote Pairi Daiza (Wallonie) - étape 1 : récupération du réseau PICC Voirie-Axe
autour de la fenêtre frontière FR (Angreau) <-> Pairi Daiza (Brugelette), via le
service ArcGIS REST du PICC (pas de téléchargement du shapefile complet).

Source: https://geoservices.wallonie.be/arcgis/rest/services/TOPOGRAPHIE/PICC_VDIFF/MapServer/21
Champ clé: GESTION ("Commune" vs "Service public de Wallonie")
"""
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape

BASE_URL = "https://geoservices.wallonie.be/arcgis/rest/services/TOPOGRAPHIE/PICC_VDIFF/MapServer/21/query"
OUT_DIR = Path("d:/vignette_belgique/data/wallonie/picc_pilote")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "voirie_axe_tournai.gpkg"

# bbox EPSG:4326 : frontière FR/BE près de la Chaussée de Lille/Rue du Moulin
# Jourdain (Tournai, ~50.6058-50.6079, 3.2709) -> Tournai Grand-Place (50.6064, 3.3866)
MINLON, MINLAT = 3.255, 50.590
MAXLON, MAXLAT = 3.410, 50.625

FIELDS = "GEOREF_ID,NATUR_CODE,NATUR_DESC,TYPE_CODE,TYPE_DESC,GESTION,RUE_NOM1,COMMU_NOM1,VOIRIE_NOM,BDR_ID"
PAGE_SIZE = 2000


def fetch_page(offset: int) -> dict:
    bbox = f"{MINLON},{MINLAT},{MAXLON},{MAXLAT}"
    params = {
        "f": "geojson",
        "geometry": bbox,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "where": "1=1",
        "outFields": FIELDS,
        "returnGeometry": "true",
        "outSR": "4326",
        "resultOffset": str(offset),
        "resultRecordCount": str(PAGE_SIZE),
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def main():
    offset = 0
    all_features = []
    while True:
        data = fetch_page(offset)
        feats = data.get("features", [])
        if not feats:
            break
        all_features.extend(feats)
        print(f"  offset={offset}: +{len(feats)} tronçons (total={len(all_features)})")
        if len(feats) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.2)  # ménager le service public

    print(f"Total tronçons récupérés : {len(all_features)}")

    rows = []
    geoms = []
    for f in all_features:
        rows.append(f["properties"])
        geoms.append(shape(f["geometry"]))

    gdf = gpd.GeoDataFrame(pd.DataFrame(rows), geometry=geoms, crs="EPSG:4326")
    gdf = gdf.to_crs("EPSG:31370")  # Lambert 72, cohérent avec le brief
    gdf.to_file(OUT_FILE, driver="GPKG")
    print(f"Écrit : {OUT_FILE} ({len(gdf)} tronçons, CRS={gdf.crs})")

    print()
    print("Répartition GESTION :")
    print(gdf["GESTION"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
