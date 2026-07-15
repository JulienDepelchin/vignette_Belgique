import sys
sys.path.insert(0, "d:/vignette_belgique/scripts")
from pathlib import Path
from lib_vignette import (
    fetch_wegsegment, weg_carrossable_communal, build_graph_weg, nearest_node_weg,
    fetch_osm_highways, apply_osm_crosscheck, fetch_border_line, analyse_reachability,
    weg_node_coords,
)
import geopandas as gpd
from shapely.geometry import Point
import networkx as nx

FLA = Path("d:/vignette_belgique/data/flandre")

DESTINATIONS = {
    "Famiflora (Mouscron)": (3.282815, 50.717576),
    "Power Oil (Menen)": (3.167773, 50.771470),
    "Gabriëls (Comines)": (3.018049, 50.776567),
    "Real Tabac & Co La Palma (Menen)": (3.139864, 50.789091),
    "King Tabac (Mouscron)": (3.194531, 50.726050),
}

BBOX = (2.968, 50.688, 3.333, 50.819)

print("1. Fetch Wegenregister...")
gdf = fetch_wegsegment(BBOX, FLA / "wegenregister_pilote" / "wegsegment_cluster_menen.gpkg")
print(f"   {len(gdf)} segments")

print("2. Filtre classification=communal + hors piéton/vélo/aardeweg...")
gdf_c = weg_carrossable_communal(gdf)
print(f"   {len(gdf_c)} segments carrossables communaux")

print("3. Fetch/croisement OSM...")
osm = fetch_osm_highways(BBOX, FLA / "osm_cluster_menen.gpkg")
print(f"   {len(osm)} ways OSM")
gdf_final = apply_osm_crosscheck(gdf_c, osm)
print(f"   {len(gdf_final)} segments après croisement OSM (exclus: {len(gdf_c)-len(gdf_final)})")

print("4. Graphe + noeuds/frontière...")
G, edge_geom = build_graph_weg(gdf_final)
node_coords = weg_node_coords(gdf_final)
border = fetch_border_line(BBOX, FLA / "overpass_boundary_menen.json")

print("\n=== Résultats par destination ===")
for nom, (lon, lat) in DESTINATIONS.items():
    dest_pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(gdf.crs).iloc[0]
    dest, dd = nearest_node_weg(gdf_final, dest_pt)
    if dest not in G:
        print(f"{nom}: destination hors graphe filtré (?)")
        continue
    result = analyse_reachability(G, dest, border, tol_m=50, get_coord=lambda n: node_coords.get(n))
    print(f"\n{nom} (destination à {dd:.1f} m du réseau carrossable) :")
    print(f"   noeuds atteignables : {result['n_reachable']}")
    print(f"   atteint la frontière FR/BE : {result['atteint_frontiere']}")
    if result["atteint_frontiere"]:
        best = min(result["near_border_nodes"], key=lambda n: nx.shortest_path_length(G, dest, n, weight="weight"))
        km = nx.shortest_path_length(G, dest, best, weight="weight") / 1000
        print(f"   plus proche point frontière atteint : {km:.2f} km ({len(result['near_border_nodes'])} points frontière atteints au total)")
