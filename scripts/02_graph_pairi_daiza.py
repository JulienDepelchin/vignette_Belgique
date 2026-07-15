"""
Pilote Pairi Daiza (Wallonie) - étape 2 : construction du graphe networkx
à partir du PICC Voirie-Axe téléchargé (script 01), et test de connectivité
"sans vignette" (uniquement GESTION == 'Commune').

Topologie : PICC Voirie-Axe n'a pas de noeuds routables natifs (pas de
from-node/to-node) -> on reconstruit la topologie par snapping des
extrémités de lignes (arrondi au cm), comme anticipé dans le brief pour
Wegenregister.
"""
from pathlib import Path

import geopandas as gpd
import networkx as nx
from shapely.geometry import Point, LineString, MultiLineString

IN_FILE = Path("d:/vignette_belgique/data/wallonie/picc_pilote/voirie_axe_tournai.gpkg")

# Origine : stub communal (sans nom) collé à la Chaussée de Lille (N-road,
# régionale) côté belge, juste à la frontière FR/BE à l'ouest de Tournai.
# Point donné par le journaliste (A27/E42) affiné vers l'alternative
# communale la plus proche repérée dans le PICC - à confirmer visuellement
# (WalOnMap/Street View) avant publication : rien ne garantit que ce tronçon
# se prolonge réellement côté français.
ORIGIN_WGS84 = (3.2708757761016787, 50.60576544737798)  # (lon, lat)
# Destination : Tournai, Grand-Place (brief §6)
DEST_WGS84 = (3.386625, 50.606400)  # (lon, lat)

SNAP_DECIMALS = 2  # arrondi en mètres (EPSG:31370) -> précision 1 cm


def snap(coord):
    return (round(coord[0], SNAP_DECIMALS), round(coord[1], SNAP_DECIMALS))


def iter_lines(geom):
    if isinstance(geom, LineString):
        yield geom
    elif isinstance(geom, MultiLineString):
        yield from geom.geoms


def build_graph(gdf: gpd.GeoDataFrame) -> nx.Graph:
    G = nx.Graph()
    for _, row in gdf.iterrows():
        for line in iter_lines(row.geometry):
            coords = list(line.coords)
            if len(coords) < 2:
                continue
            u = snap(coords[0])
            v = snap(coords[-1])
            length = line.length
            G.add_edge(
                u, v,
                weight=length,
                gestion=row["GESTION"],
                rue=row.get("RUE_NOM1"),
                commune=row.get("COMMU_NOM1"),
                voirie_nom=row.get("VOIRIE_NOM"),
            )
    return G


def nearest_node(G: nx.Graph, point: Point):
    best, best_d = None, float("inf")
    for n in G.nodes:
        d = (n[0] - point.x) ** 2 + (n[1] - point.y) ** 2
        if d < best_d:
            best, best_d = n, d
    return best, best_d ** 0.5


def main():
    gdf = gpd.read_file(IN_FILE)
    print(f"Tronçons chargés : {len(gdf)}  (CRS={gdf.crs})")

    origin_pt = gpd.GeoSeries([Point(ORIGIN_WGS84)], crs="EPSG:4326").to_crs(gdf.crs).iloc[0]
    dest_pt = gpd.GeoSeries([Point(DEST_WGS84)], crs="EPSG:4326").to_crs(gdf.crs).iloc[0]

    # --- graphe complet (diagnostic topologique, avant filtrage vignette) ---
    G_full = build_graph(gdf)
    print(f"\nGraphe complet : {G_full.number_of_nodes()} noeuds, {G_full.number_of_edges()} arêtes")
    components = list(nx.connected_components(G_full))
    components.sort(key=len, reverse=True)
    print(f"Composantes connexes : {len(components)}")
    print(f"  plus grande composante : {len(components[0])} noeuds "
          f"({100*len(components[0])/G_full.number_of_nodes():.1f}% du total)")
    if len(components) > 1:
        print(f"  tailles des 5 suivantes : {[len(c) for c in components[1:6]]}")

    origin_full, d_origin_full = nearest_node(G_full, origin_pt)
    dest_full, d_dest_full = nearest_node(G_full, dest_pt)
    print(f"\nNoeud origine (Angreau, frontière) le plus proche : à {d_origin_full:.1f} m")
    print(f"Noeud destination (Pairi Daiza) le plus proche : à {d_dest_full:.1f} m")
    same_component = any(
        origin_full in c and dest_full in c for c in components
    )
    print(f"Origine et destination dans la même composante (réseau complet) : {same_component}")

    # --- graphe "sans vignette" : on retire les tronçons régionaux ---
    gdf_communal = gdf[gdf["GESTION"] == "Commune"]
    G_communal = build_graph(gdf_communal)
    print(f"\nGraphe communal seul : {G_communal.number_of_nodes()} noeuds, "
          f"{G_communal.number_of_edges()} arêtes "
          f"(retiré : {G_full.number_of_edges() - G_communal.number_of_edges()} tronçons régionaux)")

    origin_c, d_origin_c = nearest_node(G_communal, origin_pt)
    dest_c, d_dest_c = nearest_node(G_communal, dest_pt)
    print(f"Noeud origine dans le graphe communal : à {d_origin_c:.1f} m de la frontière (Angreau)")
    print(f"Noeud destination dans le graphe communal : à {d_dest_c:.1f} m de Pairi Daiza")

    if nx.has_path(G_communal, origin_c, dest_c):
        path = nx.shortest_path(G_communal, origin_c, dest_c, weight="weight")
        length_km = nx.shortest_path_length(G_communal, origin_c, dest_c, weight="weight") / 1000
        print(f"\n>>> CHEMIN TROUVÉ sans route régionale : {length_km:.1f} km, {len(path)} noeuds")
    else:
        print("\n>>> AUCUN CHEMIN trouvé dans le graphe communal seul entre origine et destination.")
        print("    (soit un vrai obstacle régional incontournable, soit un trou topologique du graphe -"
              " à vérifier avant conclusion, cf. §4 du brief : validation manuelle QGIS obligatoire)")


if __name__ == "__main__":
    main()
