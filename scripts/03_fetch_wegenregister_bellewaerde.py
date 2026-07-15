"""
Pilote Bellewaerde (Flandre) - étape 1 : récupération du réseau Wegenregister
autour de la fenêtre frontière FR <-> Bellewaerde (Ieper/Zonnebeke), via l'OGC
API Features de Digitaal Vlaanderen (pas de téléchargement de zip).

Source: https://geo.api.vlaanderen.be/Wegenregister/ogc/features/v1/collections/Wegsegment
Champ clé: wegbeheerder (code) / labelWegbeheerder (libellé)
  - préfixe "AWV..."   -> Vlaams Gewest (régional, soumis vignette)
  - code numérique     -> commune (NIS-achtige code)
  - "PARTIC"           -> privé (hors brief, à traiter à part)
  - préfixe "V...."    -> De Vlaamse Waterweg (jaagpaden, hors brief)
"""
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape

BASE_URL = "https://geo.api.vlaanderen.be/Wegenregister/ogc/features/v1/collections/Wegsegment/items"
OUT_DIR = Path("d:/vignette_belgique/data/flandre/wegenregister_pilote")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "wegsegment_bellewaerde.gpkg"

# bbox EPSG:4326 : frontière FR/BE pres d'Abele/Watou -> Bellewaerde (50.845810, 2.949768)
MINLON, MINLAT = 2.59, 50.77
MAXLON, MAXLAT = 2.96, 50.91

PAGE_SIZE = 1000


def fetch_page(start_index: int) -> dict:
    bbox = f"{MINLON},{MINLAT},{MAXLON},{MAXLAT}"
    params = {
        "bbox": bbox,
        "limit": str(PAGE_SIZE),
        "startIndex": str(start_index),
        "f": "application/geo+json",
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "vdn-data-journalism-research"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def classify(label: str) -> str:
    """Classification à partir de labelWegbeheerder (texte), pas du code brut :
    le code numérique seul est trompeur (ex. code '02000' = "Vlaams Gewest",
    '30000' = "Provincie West-Vlaanderen" - pas des codes NIS de commune, alors
    qu'ils sont numériques comme les vrais codes commune)."""
    if not label or label == "niet gekend":
        return "inconnu"
    if label == "Vlaams Gewest" or label.startswith("District "):
        return "regional"
    if label.startswith("Provincie "):
        return "provincial"
    if label.startswith("Particulier"):
        return "prive"
    if label.startswith("Afdeling "):
        return "waterweg"
    if label.startswith("Stad ") or label.startswith("Gemeente ") or label.startswith("Stadsbestuur"):
        return "communal"
    return "autre"


def main():
    start_index = 0
    all_features = []
    while True:
        data = fetch_page(start_index)
        feats = data.get("features", [])
        if not feats:
            break
        all_features.extend(feats)
        print(f"  startIndex={start_index}: +{len(feats)} segments (total={len(all_features)})")
        n_returned = data.get("numberReturned", len(feats))
        if n_returned < PAGE_SIZE:
            break
        start_index += PAGE_SIZE
        time.sleep(0.2)

    print(f"Total segments récupérés : {len(all_features)}")

    rows = []
    geoms = []
    for f in all_features:
        rows.append(f["properties"])
        geoms.append(shape(f["geometry"]))

    gdf = gpd.GeoDataFrame(pd.DataFrame(rows), geometry=geoms, crs="EPSG:4326")
    gdf["classification"] = gdf["labelWegbeheerder"].apply(classify)
    gdf = gdf.to_crs("EPSG:31370")
    gdf.to_file(OUT_FILE, driver="GPKG")
    print(f"Écrit : {OUT_FILE} ({len(gdf)} segments, CRS={gdf.crs})")

    print()
    print("Répartition classification :")
    print(gdf["classification"].value_counts(dropna=False))
    print()
    print("Répartition labelWegbeheerder (top 15) :")
    print(gdf["labelWegbeheerder"].value_counts(dropna=False).head(15))


if __name__ == "__main__":
    main()
