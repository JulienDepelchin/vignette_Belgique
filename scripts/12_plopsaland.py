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
DEST_WGS84 = (2.598554, 51.080738)  # Plopsaland, De Panne
BBOX = (2.50, 51.02, 2.68, 51.13)  # De Panne est a la cote, tres pres de la frontiere (Bray-Dunes/Ghyvelde)

print("1. Fetch Wegenregister...")
gdf = fetch_wegsegment(BBOX, FLA / "wegenregister_pilote" / "wegsegment_plopsaland.gpkg")
print(f"   {len(gdf)} segments")

print("2. Filtre carrossabilite native...")
gdf_c = weg_carrossable_communal(gdf)
print(f"   {len(gdf_c)} segments")

print("3. Fetch/croisement OSM...")
osm = fetch_osm_highways(BBOX, FLA / "osm_plopsaland.gpkg")
gdf_final = apply_osm_crosscheck(gdf_c, osm)
print(f"   {len(gdf_final)} segments apres croisement OSM (exclus: {len(gdf_c)-len(gdf_final)})")

print("4. Graphe + frontiere...")
G, edge_geom = build_graph_weg(gdf_final)
node_coords = weg_node_coords(gdf_final)
border = fetch_border_line(BBOX, FLA / "overpass_boundary_depanne.json")

dest_pt = gpd.GeoSeries([Point(DEST_WGS84)], crs="EPSG:4326").to_crs(gdf.crs).iloc[0]
dest, dd = nearest_node_weg(gdf_final, dest_pt)
print(f"destination a {dd:.1f}m")

result = analyse_reachability(G, dest, border, tol_m=50, get_coord=lambda n: node_coords.get(n))
print(f"\n>>> noeuds atteignables: {result['n_reachable']}")
print(f">>> atteint la frontiere: {result['atteint_frontiere']}")
if result['atteint_frontiere']:
    best = min(result['near_border_nodes'], key=lambda n: nx.shortest_path_length(G, dest, n, weight='weight'))
    km = nx.shortest_path_length(G, dest, best, weight='weight')/1000
    print(f"   plus proche: {km:.2f} km ({len(result['near_border_nodes'])} points frontiere atteints)")
