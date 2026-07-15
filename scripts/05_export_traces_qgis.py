"""
Export des itinéraires calculés (pilotes Tournai et Bellewaerde) en GeoPackage
pour vérification visuelle manuelle (QGIS + Street View / WalOnMap / Geopunt),
conformément au §4 du brief (validation manuelle obligatoire avant publication).

Produit :
- data/wallonie/picc_pilote/trace_tournai.gpkg      (itinéraire + points origine/destination)
- data/flandre/wegenregister_pilote/trace_bellewaerde.gpkg
"""
import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import Point, LineString, MultiLineString, Point as ShPoint
from shapely.ops import linemerge


# ---------------------------------------------------------------------------
# TOURNAI (Wallonie / PICC)
# ---------------------------------------------------------------------------
def export_tournai():
    IN_FILE = "d:/vignette_belgique/data/wallonie/picc_pilote/voirie_axe_tournai.gpkg"
    OUT_FILE = "d:/vignette_belgique/data/wallonie/picc_pilote/trace_tournai.gpkg"
    SNAP_DECIMALS = 2
    ORIGIN_31370 = (72685.20647361004, 142872.75562151894)  # Rue de Créplaine, frontière FR/BE
    DEST_WGS84 = (3.386625, 50.606400)  # Tournai Grand-Place

    def snap(c):
        return (round(c[0], SNAP_DECIMALS), round(c[1], SNAP_DECIMALS))

    def iter_lines(geom):
        if isinstance(geom, LineString):
            yield geom
        elif isinstance(geom, MultiLineString):
            yield from geom.geoms

    gdf = gpd.read_file(IN_FILE)
    gdf_communal = gdf[gdf["GESTION"] == "Commune"]

    G = nx.Graph()
    edge_geom = {}
    for _, row in gdf_communal.iterrows():
        for line in iter_lines(row.geometry):
            coords = list(line.coords)
            if len(coords) < 2:
                continue
            u, v = snap(coords[0]), snap(coords[-1])
            G.add_edge(u, v, weight=line.length, rue=row.get("RUE_NOM1"), commune=row.get("COMMU_NOM1"))
            edge_geom[frozenset((u, v))] = line

    dest_pt = gpd.GeoSeries([Point(DEST_WGS84)], crs="EPSG:4326").to_crs(gdf.crs).iloc[0]

    origin = snap(ORIGIN_31370)

    def nearest(G, pt):
        best, bd = None, float("inf")
        for n in G.nodes:
            d = (n[0] - pt.x) ** 2 + (n[1] - pt.y) ** 2
            if d < bd:
                best, bd = n, d
        return best, bd ** 0.5

    dest, dd = nearest(G, dest_pt)
    path = nx.shortest_path(G, origin, dest, weight="weight")
    length_km = nx.shortest_path_length(G, origin, dest, weight="weight") / 1000

    segs = []
    for u, v in zip(path[:-1], path[1:]):
        line = edge_geom.get(frozenset((u, v)))
        if line is not None:
            segs.append(line)

    trace = gpd.GeoDataFrame(
        {"lieu": ["Tournai (Grand-Place)"], "longueur_km": [length_km], "origine": ["Rue de Créplaine (frontière FR/BE)"]},
        geometry=[linemerge(segs)],
        crs=gdf.crs,
    )
    points = gpd.GeoDataFrame(
        {"role": ["origine_frontiere", "destination"]},
        geometry=[Point(origin), Point(dest)],
        crs=gdf.crs,
    )

    trace.to_file(OUT_FILE, layer="trace", driver="GPKG")
    points.to_file(OUT_FILE, layer="points", driver="GPKG")
    print(f"Tournai : {length_km:.2f} km -> écrit dans {OUT_FILE} (layers: trace, points)")


# ---------------------------------------------------------------------------
# BELLEWAERDE (Flandre / Wegenregister)
# ---------------------------------------------------------------------------
def export_bellewaerde():
    IN_FILE = "d:/vignette_belgique/data/flandre/wegenregister_pilote/wegsegment_bellewaerde.gpkg"
    OUT_FILE = "d:/vignette_belgique/data/flandre/wegenregister_pilote/trace_bellewaerde.gpkg"

    ORIGIN_NODE = 1655996  # Boeschepestraat, frontière (le plus court des 6 candidats testés)
    ORIGIN_LABEL = "Boeschepestraat (frontière FR/BE, ~Boeschepe)"
    PROXY_DEST_NODE = 1858861  # noeud communal public le plus proche de Bellewaerde (~130 m, cf. accès privé/régional)

    gdf = gpd.read_file(IN_FILE)
    gdf_sv = gdf[gdf["classification"] != "regional"]

    G = nx.Graph()
    edge_geom = {}
    for _, row in gdf_sv.iterrows():
        u, v = row["beginknoopObjectId"], row["eindknoopObjectId"]
        G.add_edge(u, v, weight=row.geometry.length,
                   straat=row.get("linkerstraatnaam") or row.get("rechterstraatnaam"))
        edge_geom[frozenset((u, v))] = row.geometry

    path = nx.shortest_path(G, ORIGIN_NODE, PROXY_DEST_NODE, weight="weight")
    length_km = nx.shortest_path_length(G, ORIGIN_NODE, PROXY_DEST_NODE, weight="weight") / 1000

    segs = [edge_geom[frozenset((u, v))] for u, v in zip(path[:-1], path[1:]) if frozenset((u, v)) in edge_geom]

    trace = gpd.GeoDataFrame(
        {
            "lieu": ["Bellewaerde (jusqu'au dernier noeud communal public, ~130 m de l'entrée)"],
            "longueur_km": [length_km],
            "origine": [ORIGIN_LABEL],
            "note": ["Accès final (~130 m) sur Meenseweg (régionale) ou voirie privée du parc - à vérifier visuellement"],
        },
        geometry=[linemerge(segs)],
        crs=gdf.crs,
    )

    # coordonnées des noeuds origine/destination pour repère visuel
    o_geom = None
    d_geom = None
    for _, row in gdf.iterrows():
        if row["beginknoopObjectId"] == ORIGIN_NODE:
            o_geom = Point(row.geometry.coords[0])
        elif row["eindknoopObjectId"] == ORIGIN_NODE:
            o_geom = Point(row.geometry.coords[-1])
        if row["beginknoopObjectId"] == PROXY_DEST_NODE:
            d_geom = Point(row.geometry.coords[0])
        elif row["eindknoopObjectId"] == PROXY_DEST_NODE:
            d_geom = Point(row.geometry.coords[-1])
        if o_geom is not None and d_geom is not None:
            break

    points = gpd.GeoDataFrame(
        {"role": ["origine_frontiere", "proxy_destination"]},
        geometry=[o_geom, d_geom],
        crs=gdf.crs,
    )

    trace.to_file(OUT_FILE, layer="trace", driver="GPKG")
    points.to_file(OUT_FILE, layer="points", driver="GPKG")
    print(f"Bellewaerde : {length_km:.2f} km -> écrit dans {OUT_FILE} (layers: trace, points)")


if __name__ == "__main__":
    export_tournai()
    export_bellewaerde()
