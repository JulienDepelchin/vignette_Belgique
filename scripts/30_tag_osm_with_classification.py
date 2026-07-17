"""
Tague chaque way OSM `highway=*` dans la zone d'interet en fonction de la
classification officielle (PICC Wallonie + Wegenregister Flandre + road_management
Bruxelles Mobilite, cf. scripts/320_fetch_merge_brussels.py) : les troncons
soumis a la vignette (regional) recoivent `motor_vehicle=no`, une restriction
d'acces OSM standard que le profil "car" par defaut de GraphHopper respecte
nativement - pas besoin d'EncodedValue custom ni de build Java personnalise.
"""
import sys
import time

import geopandas as gpd
import osmium
import pandas as pd
from shapely.geometry import LineString, Point

IN_PBF = "d:/vignette_belgique/tools/belgium_npdc_merged.osm.pbf"
OUT_PBF = "d:/vignette_belgique/tools/belgium-vignette-tagged.osm.pbf"
CLASSIF_FILE = "d:/vignette_belgique/data/classification_unifiee.gpkg"

# bbox englobant la Belgique (zone d'etude) + le Nord-Pas-de-Calais (Lille et au-dela) :
# la classification officielle ne couvre que la Belgique, donc les troncons francais ne
# matcheront jamais et resteront non-tagges (= libres, coherent avec l'absence de vignette
# cote francais) - inutile de restreindre la bbox au cote belge.
BBOX = (1.55, 49.90, 4.60, 51.32)  # (minlon, minlat, maxlon, maxlat)

TEST_MODE = "--test" in sys.argv
JOIN_TOLERANCE_M = 15


def main():
    t0 = time.time()
    print("Chargement de la classification officielle...")
    classif = gpd.read_file(CLASSIF_FILE).to_crs("EPSG:31370")
    before = len(classif)
    classif = classif[~classif.geometry.duplicated()].reset_index(drop=True)
    print(f"  {len(classif)} segments officiels (dédupliqué de {before})")

    print("Passe 1 : lecture des ways OSM highway=* dans la zone...")
    fp = osmium.FileProcessor(IN_PBF).with_locations()
    way_copies = []
    geoms = []
    minlon, minlat, maxlon, maxlat = BBOX
    n_seen = 0
    for obj in fp:
        if not obj.is_way():
            continue
        if "highway" not in obj.tags:
            continue
        try:
            coords = [(n.lon, n.lat) for n in obj.nodes]
        except Exception:
            continue
        if len(coords) < 2:
            continue
        # filtre bbox rapide sur le premier point
        lon0, lat0 = coords[0]
        if not (minlon <= lon0 <= maxlon and minlat <= lat0 <= maxlat):
            continue
        way_copies.append(obj.replace(tags=dict(obj.tags), nodes=list(obj.nodes)))
        geoms.append(LineString(coords))
        n_seen += 1
        if TEST_MODE and n_seen >= 5000:
            break
        if n_seen % 100000 == 0:
            print(f"  ... {n_seen} ways collectés ({time.time()-t0:.0f}s)")

    print(f"Total ways highway dans la zone : {len(way_copies)} ({time.time()-t0:.0f}s)")

    print("Passe 2 : jointure spatiale (plus proche déterministe, tolérance {}m)...".format(JOIN_TOLERANCE_M))
    ways_gdf = gpd.GeoDataFrame({"idx": range(len(geoms))}, geometry=geoms, crs="EPSG:4326").to_crs("EPSG:31370")
    ways_gdf["mid"] = ways_gdf.geometry.interpolate(0.5, normalized=True)
    mids = ways_gdf.set_geometry("mid")

    # jointure manuelle (buffer + distance explicite + idxmin) : évite l'ambiguïté de
    # gpd.sjoin_nearest quand plusieurs candidats sont à distance quasi-égale (cas fréquent
    # ici vu le grand nombre de géométries dupliquées/proches issues de collectes qui se
    # chevauchent) - sjoin_nearest + drop_duplicates(keep="first") s'est avéré non fiable
    # dans ce cas (choix arbitraire entre un candidat régional et un communal à égalité).
    sidx = classif.sindex
    classif_soumis = classif["soumis_vignette"].to_numpy()
    vignette_map = {}
    n_matched = 0
    for row in mids.itertuples(index=False):
        idx, pt = row.idx, row.mid
        cand_idx = list(sidx.query(pt.buffer(JOIN_TOLERANCE_M)))
        if not cand_idx:
            continue
        dists = classif.geometry.iloc[cand_idx].distance(pt)
        best = dists.idxmin()
        if dists.loc[best] > JOIN_TOLERANCE_M:
            continue
        vignette_map[idx] = bool(classif_soumis[best])
        n_matched += 1
        if idx % 100000 == 0 and idx > 0:
            print(f"  ... {idx} traités ({time.time()-t0:.0f}s)")

    print(f"  {n_matched}/{len(way_copies)} ways matchés à une classification officielle")
    n_regional = sum(1 for v in vignette_map.values() if v is True)
    print(f"  dont {n_regional} tagués régional (soumis vignette)")

    print("Passe 3 : écriture du PBF tagué...")
    n_blocked = 0
    with osmium.BackReferenceWriter(OUT_PBF, ref_src=IN_PBF, overwrite=True) as writer:
        for i, way in enumerate(way_copies):
            v = vignette_map.get(i)
            if v is True:
                tags = dict(way.tags)
                tags["motor_vehicle"] = "no"
                tags["vignette_source"] = "regional"  # tracabilite, sans effet sur le routing
                way.tags = tags
                n_blocked += 1
            writer.add_way(way)
    print(f"  {n_blocked} ways bloqués (motor_vehicle=no, soumis vignette)")

    print(f"Terminé en {time.time()-t0:.0f}s -> {OUT_PBF}")


if __name__ == "__main__":
    main()
