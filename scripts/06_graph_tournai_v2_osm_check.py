"""
Pilote Tournai v2 : ajoute un croisement OSM (highway/surface/tracktype/access)
au filtre PICC (GESTION=Commune + NATUR_CODE=VCO), après constat terrain que
VCO/CHA ne suffit pas à garantir la carrossabilité (ex. Chemin de Bouvines,
classé VCO mais en réalité highway=cycleway/surface=ground en OSM).

OSM sert ici de vérification physique (praticabilité), pas de classification
administrative (régional/communal) - cohérent avec le brief.
"""
import json

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString, MultiLineString, Point

PICC_FILE = "d:/vignette_belgique/data/wallonie/picc_pilote/voirie_axe_tournai.gpkg"
OSM_FILE = "d:/vignette_belgique/data/wallonie/refs/osm_highways_tournai_full.json"
SNAP_DECIMALS = 2
ORIGIN_31370 = (72685.20647361004, 142872.75562151894)  # Rue de Créplaine, frontière FR/BE
DEST_WGS84 = (3.386625, 50.606400)  # Tournai Grand-Place

NON_CARROSSABLE_HIGHWAY = {"track", "path", "footway", "cycleway", "bridleway", "steps", "pedestrian"}
NON_CARROSSABLE_SURFACE = {"unpaved", "ground", "grass", "dirt", "sand", "mud", "earth"}
BAD_TRACKTYPE = {"grade3", "grade4", "grade5"}


def snap(c):
    return (round(c[0], SNAP_DECIMALS), round(c[1], SNAP_DECIMALS))


def iter_lines(geom):
    if isinstance(geom, LineString):
        yield geom
    elif isinstance(geom, MultiLineString):
        yield from geom.geoms


def load_osm():
    with open(OSM_FILE, encoding="utf-8") as f:
        osm = json.load(f)
    rows, geoms = [], []
    for el in osm["elements"]:
        geom = el.get("geometry")
        tags = el.get("tags", {})
        if not geom or len(geom) < 2:
            continue
        geoms.append(LineString([(g["lon"], g["lat"]) for g in geom]))
        rows.append({
            "highway": tags.get("highway"),
            "surface": tags.get("surface"),
            "tracktype": tags.get("tracktype"),
        })
    return gpd.GeoDataFrame(pd.DataFrame(rows), geometry=geoms, crs="EPSG:4326").to_crs("EPSG:31370")


def is_osm_carrossable(row) -> bool:
    if row["highway"] in NON_CARROSSABLE_HIGHWAY:
        # highway=track avec tracktype grade1/grade2 (revetement solide) reste tolere
        if row["highway"] == "track" and row["tracktype"] not in BAD_TRACKTYPE:
            return True
        return False
    if row["surface"] in NON_CARROSSABLE_SURFACE:
        return False
    if row["tracktype"] in BAD_TRACKTYPE:
        return False
    return True


def main():
    gdf = gpd.read_file(PICC_FILE)
    gdf_carrossable_picc = gdf[(gdf["GESTION"] == "Commune") & (gdf["NATUR_CODE"] == "VCO")].copy()
    print(f"Segments Commune+VCO (avant croisement OSM) : {len(gdf_carrossable_picc)}")

    osm_gdf = load_osm()
    print(f"Ways OSM chargés : {len(osm_gdf)}")
    sidx = osm_gdf.sindex

    flags = []
    for geom in gdf_carrossable_picc.geometry:
        mid = geom.interpolate(0.5, normalized=True)
        idx = list(sidx.query(mid.buffer(10)))
        if not idx:
            flags.append(True)  # pas de correspondance OSM -> on ne filtre pas sur une absence de donnée
            continue
        cand = osm_gdf.iloc[idx].copy()
        cand["d"] = cand.geometry.distance(mid)
        nearest = cand.sort_values("d").iloc[0]
        flags.append(is_osm_carrossable(nearest))

    gdf_carrossable_picc["osm_carrossable"] = flags
    n_excl = (~gdf_carrossable_picc["osm_carrossable"]).sum()
    print(f"Segments exclus par le croisement OSM : {n_excl}")

    gdf_final = gdf_carrossable_picc[gdf_carrossable_picc["osm_carrossable"]]

    G = nx.Graph()
    edge_geom = {}
    for _, row in gdf_final.iterrows():
        for line in iter_lines(row.geometry):
            coords = list(line.coords)
            if len(coords) < 2:
                continue
            u, v = snap(coords[0]), snap(coords[-1])
            G.add_edge(u, v, weight=line.length, rue=row.get("RUE_NOM1"))
            edge_geom[frozenset((u, v))] = line

    origin = snap(ORIGIN_31370)
    dest_pt = gpd.GeoSeries([Point(DEST_WGS84)], crs="EPSG:4326").to_crs(gdf.crs).iloc[0]

    def nearest_node(G, pt):
        best, bd = None, float("inf")
        for n in G.nodes:
            d = (n[0] - pt.x) ** 2 + (n[1] - pt.y) ** 2
            if d < bd:
                best, bd = n, d
        return best, bd ** 0.5

    if origin not in G:
        print("ORIGINE absente du graphe filtré - impasse locale ou tronçon exclu")
        return
    dest, dd = nearest_node(G, dest_pt)
    print(f"Destination à {dd:.1f} m du noeud le plus proche")

    if nx.has_path(G, origin, dest):
        path = nx.shortest_path(G, origin, dest, weight="weight")
        km = nx.shortest_path_length(G, origin, dest, weight="weight") / 1000
        print(f"\n>>> CHEMIN TROUVÉ (VCO + carrossable OSM) : {km:.2f} km, {len(path)} noeuds")
        rues = []
        for u, v in zip(path[:-1], path[1:]):
            r = G.get_edge_data(u, v).get("rue")
            if r and (not rues or rues[-1] != r):
                rues.append(r)
        print("Rues :", rues)

        # export pour QGIS
        segs = [edge_geom[frozenset((u, v))] for u, v in zip(path[:-1], path[1:]) if frozenset((u, v)) in edge_geom]
        from shapely.ops import linemerge
        trace = gpd.GeoDataFrame({"longueur_km": [km]}, geometry=[linemerge(segs)], crs=gdf.crs)
        trace.to_file("d:/vignette_belgique/data/wallonie/picc_pilote/trace_tournai.gpkg", layer="trace_v2_osm_check", driver="GPKG")
        print("Export : layer trace_v2_osm_check")
    else:
        print("\n>>> AUCUN CHEMIN trouvé avec ce filtre renforcé")


if __name__ == "__main__":
    main()
