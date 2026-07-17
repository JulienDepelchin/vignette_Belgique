"""
Recupere la classification officielle "gestionnaire de voirie" de la Region
de Bruxelles-Capitale (Bruxelles Mobilite, WFS bm_network:road_management,
CC0) et la fusionne dans data/classification_unifiee.gpkg, jusqu'ici limitee
a la Wallonie (PICC) et la Flandre (Wegenregister).

Champ road_manager : "REG" = regional (soumis vignette), "33" = communal
"article 33" (gestion communale, approbation regionale requise pour
modification -- reste communal au sens de la vignette), "VLA" = deborde en
territoire flamand (deja couvert par le Wegenregister, ignore ici pour
eviter un doublon/conflit), valeurs manquantes ignorees (~9 sur 13287,
negligeable).

Usage : python scripts/320_fetch_merge_brussels.py
"""
import sys
import urllib.request

import geopandas as gpd

sys.stdout.reconfigure(encoding="utf-8")

WFS_URL = (
    "https://data.mobility.brussels/geoserver/bm_network/wfs"
    "?service=wfs&version=2.0.0&request=GetFeature"
    "&typeName=bm_network:road_management&outputFormat=application/json"
)
CLASSIF_FILE = "d:/vignette_belgique/data/classification_unifiee.gpkg"
BXL_RAW_FILE = "d:/vignette_belgique/data/bruxelles_road_management.gpkg"

MANAGER_TO_SOUMIS = {"REG": True, "33": False}  # VLA et None exclus explicitement


def fetch():
    print("Telechargement de la couche road_management (Bruxelles Mobilite)...")
    with urllib.request.urlopen(WFS_URL, timeout=60) as r:
        raw = r.read()
    tmp_path = "d:/vignette_belgique/data/_tmp_bxl_road_management.json"
    with open(tmp_path, "wb") as f:
        f.write(raw)
    gdf = gpd.read_file(tmp_path)
    print(f"  {len(gdf)} entites brutes, CRS={gdf.crs}")
    return gdf


def main():
    gdf = fetch()

    before = len(gdf)
    gdf = gdf[gdf["road_manager"].isin(MANAGER_TO_SOUMIS.keys())].copy()
    print(f"  {len(gdf)}/{before} retenues (road_manager REG ou 33 ; VLA et valeurs manquantes exclus)")

    gdf["soumis_vignette"] = gdf["road_manager"].map(MANAGER_TO_SOUMIS)
    gdf["source"] = "BXL"
    gdf = gdf[["soumis_vignette", "source", "geometry"]]

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:31370")
    else:
        gdf = gdf.to_crs("EPSG:31370")

    n_reg = int(gdf["soumis_vignette"].sum())
    print(f"  dont {n_reg} regionaux (soumis vignette), {len(gdf) - n_reg} communaux (article 33)")

    gdf.to_file(BXL_RAW_FILE, driver="GPKG")
    print(f"Sauvegarde brute -> {BXL_RAW_FILE}")

    print("\nFusion avec la classification unifiee existante...")
    classif = gpd.read_file(CLASSIF_FILE).to_crs("EPSG:31370")
    before_n = len(classif)
    print(f"  classification existante : {before_n} entites")

    merged = gpd.GeoDataFrame(
        pd_concat([classif, gdf]), crs="EPSG:31370"
    )
    merged = merged[~merged.geometry.duplicated()].reset_index(drop=True)
    print(f"  apres fusion + dedoublonnage : {len(merged)} entites (etait {before_n})")

    merged.to_file(CLASSIF_FILE, driver="GPKG")
    print(f"Ecrit -> {CLASSIF_FILE}")


def pd_concat(dfs):
    import pandas as pd
    return pd.concat(dfs, ignore_index=True)


if __name__ == "__main__":
    main()
