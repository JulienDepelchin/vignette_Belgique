import sys
import time
sys.path.insert(0, "d:/vignette_belgique/scripts")
from lib_vignette import fetch_picc, fetch_wegsegment
from pathlib import Path
import geopandas as gpd
import pandas as pd

WAL = Path("d:/vignette_belgique/data/wallonie")
FLA = Path("d:/vignette_belgique/data/flandre")

# zone complete d'etude (union de tous les lieux + marge)
BBOX = (2.45, 50.25, 4.60, 51.32)

t0 = time.time()
print("Fetch PICC (zone complete)...")
picc = fetch_picc(BBOX, WAL / "picc_pilote" / "voirie_axe_zone_complete.gpkg")
print(f"  {len(picc)} tronçons PICC ({time.time()-t0:.0f}s)")

print("Fetch Wegenregister (zone complete)...")
weg = fetch_wegsegment(BBOX, FLA / "wegenregister_pilote" / "wegsegment_zone_complete.gpkg")
print(f"  {len(weg)} segments Wegenregister ({time.time()-t0:.0f}s)")

print("Fusion en classification unifiée...")
picc_c = picc[["GESTION", "geometry"]].copy()
picc_c["soumis_vignette"] = picc_c["GESTION"] == "Service public de Wallonie"
picc_c["source"] = "PICC"
picc_c = picc_c[["soumis_vignette", "source", "geometry"]].to_crs("EPSG:4326")

weg_c = weg[["classification", "geometry"]].copy()
weg_c["soumis_vignette"] = weg_c["classification"] == "regional"
weg_c["source"] = "WEG"
weg_c = weg_c[["soumis_vignette", "source", "geometry"]].to_crs("EPSG:4326")

combined = pd.concat([picc_c, weg_c], ignore_index=True)
combined = gpd.GeoDataFrame(combined, crs="EPSG:4326")
combined = combined[~combined.geometry.duplicated()].reset_index(drop=True)
combined.to_file("d:/vignette_belgique/data/classification_unifiee.gpkg", driver="GPKG")
print(f"Classification unifiée (zone complète, dédupliquée) : {len(combined)} segments -> data/classification_unifiee.gpkg")
print(f"Terminé en {time.time()-t0:.0f}s")
