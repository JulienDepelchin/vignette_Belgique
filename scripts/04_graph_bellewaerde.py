"""
Pilote Bellewaerde (Flandre) - étape 2 : graphe networkx à partir des noeuds
natifs du Wegenregister (beginknoopObjectId/eindknoopObjectId - pas de
snapping de coordonnées nécessaire ici, contrairement au PICC wallon) et test
de connectivité "sans vignette" (on retire les segments classification ==
'regional'; on garde communal/prive/waterweg/provincial dans le graphe de
base, cf. discussion sur ces catégories).
"""
from pathlib import Path

import geopandas as gpd
import networkx as nx
from shapely.geometry import Point

IN_FILE = Path("d:/vignette_belgique/data/flandre/wegenregister_pilote/wegsegment_bellewaerde.gpkg")

# Destination : Bellewaerde (brief §6)
DEST_WGS84 = (2.949768, 50.845810)  # (lon, lat)


def build_graph(gdf: gpd.GeoDataFrame) -> nx.Graph:
    G = nx.Graph()
    for _, row in gdf.iterrows():
        u, v = row["beginknoopObjectId"], row["eindknoopObjectId"]
        G.add_edge(
            u, v,
            weight=row.geometry.length,
            straat=row.get("linkerstraatnaam") or row.get("rechterstraatnaam"),
            classification=row["classification"],
        )
    return G


def nearest_node_by_coord(gdf: gpd.GeoDataFrame, G: nx.Graph, point: Point):
    """Trouve le noeud du graphe géométriquement le plus proche d'un point,
    en repartant des extrémités de segments (les noeuds n'ont pas de couche
    géométrique dédiée récupérée ici)."""
    best, best_d, best_node = None, float("inf"), None
    for _, row in gdf.iterrows():
        geom = row.geometry
        for node_id, coord in [(row["beginknoopObjectId"], geom.coords[0]),
                                (row["eindknoopObjectId"], geom.coords[-1])]:
            d = (coord[0] - point.x) ** 2 + (coord[1] - point.y) ** 2
            if d < best_d:
                best_d, best_node = d, node_id
    return best_node, best_d ** 0.5


def main():
    gdf = gpd.read_file(IN_FILE)
    print(f"Segments chargés : {len(gdf)}")
    print(gdf["classification"].value_counts())

    dest_pt = gpd.GeoSeries([Point(DEST_WGS84)], crs="EPSG:4326").to_crs(gdf.crs).iloc[0]

    G_full = build_graph(gdf)
    print(f"\nGraphe complet : {G_full.number_of_nodes()} noeuds, {G_full.number_of_edges()} arêtes")
    components = list(nx.connected_components(G_full))
    components.sort(key=len, reverse=True)
    print(f"Composantes connexes : {len(components)}, plus grande : {len(components[0])} noeuds "
          f"({100*len(components[0])/G_full.number_of_nodes():.1f}%)")

    # graphe "sans vignette" : on retire uniquement les segments 'regional'
    gdf_sans_vignette = gdf[gdf["classification"] != "regional"]
    G = build_graph(gdf_sans_vignette)
    print(f"\nGraphe sans vignette (retire regional) : {G.number_of_nodes()} noeuds, "
          f"{G.number_of_edges()} arêtes (retiré {G_full.number_of_edges()-G.number_of_edges()} segments régionaux)")

    dest, dd = nearest_node_by_coord(gdf_sans_vignette, G, dest_pt)
    print(f"Noeud destination (Bellewaerde) le plus proche : {dest}, à {dd:.1f} m")

    comps = list(nx.connected_components(G))
    comps.sort(key=len, reverse=True)
    dest_comp = next(i for i, c in enumerate(comps) if dest in c)
    print(f"Destination -> composante #{dest_comp} (taille {len(comps[dest_comp])}/{G.number_of_nodes()})")

    # candidats frontaliers (rues nommées trouvées à la frontière)
    candidats = {
        "Steenvoordestraat (1802898)": 1802898,
        "Houtkerkestraat (1669546)": 1669546,
        "Boeschepestraat (1655996)": 1655996,
        "Abelestationsstraat (1687490)": 1687490,
        "Casseldreef (1650875)": 1650875,
        "Gemenestraat (1656655)": 1656655,
    }
    print()
    for nom, node in candidats.items():
        if node not in G:
            print(f"{nom}: absent du graphe sans-vignette (?)")
            continue
        o_comp = next((i for i, c in enumerate(comps) if node in c), None)
        same = o_comp == dest_comp
        print(f"{nom}: composante #{o_comp} (taille {len(comps[o_comp])}) - meme composante que Bellewaerde: {same}")
        if same:
            length_km = nx.shortest_path_length(G, node, dest, weight="weight") / 1000
            print(f"   >>> CHEMIN TROUVE : {length_km:.2f} km")


if __name__ == "__main__":
    main()
