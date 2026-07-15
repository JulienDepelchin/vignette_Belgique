import sys
sys.path.insert(0, "d:/vignette_belgique/scripts")
from pathlib import Path
from lib_vignette import (
    fetch_picc, picc_carrossable_communal, build_graph_picc, nearest_node_coord,
    fetch_osm_highways, apply_osm_crosscheck, fetch_border_line, analyse_reachability,
)
import geopandas as gpd
from shapely.geometry import Point
import networkx as nx

WAL = Path("d:/vignette_belgique/data/wallonie")
DEST_WGS84 = (3.893746, 50.590627)  # Pairi Daiza
BBOX = (3.60, 50.32, 3.96, 50.63)  # frontière sud (Mons/Quiévrain/Angreau) -> Pairi Daiza

print("1. Fetch PICC...")
gdf = fetch_picc(BBOX, WAL / "picc_pilote" / "voirie_axe_pairi_daiza.gpkg")
print(f"   {len(gdf)} tronçons")

print("2. Filtre GESTION=Commune + NATUR_CODE=VCO...")
gdf_c = picc_carrossable_communal(gdf)
print(f"   {len(gdf_c)} tronçons carrossables communaux (PICC)")

print("3. Fetch/croisement OSM...")
osm = fetch_osm_highways(BBOX, WAL / "refs" / "osm_pairi_daiza.gpkg")
print(f"   {len(osm)} ways OSM")
gdf_final = apply_osm_crosscheck(gdf_c, osm)
print(f"   {len(gdf_final)} tronçons après croisement OSM (exclus: {len(gdf_c)-len(gdf_final)})")

print("4. Graphe + composante atteignable depuis Pairi Daiza...")
G, edge_geom = build_graph_picc(gdf_final)
dest_pt = gpd.GeoSeries([Point(DEST_WGS84)], crs="EPSG:4326").to_crs(gdf.crs).iloc[0]
dest, dd = nearest_node_coord(G, dest_pt)
print(f"   destination à {dd:.1f} m du réseau carrossable le plus proche")

print("5. Frontière FR/BE...")
border = fetch_border_line(BBOX, WAL / "refs" / "overpass_boundary_pairi_daiza.json")

result = analyse_reachability(G, dest, border, tol_m=50)
print(f"\n>>> Noeuds atteignables (100% communal carrossable) : {result['n_reachable']}")
print(f">>> Atteint la frontière FR/BE (<50m) : {result['atteint_frontiere']}")
if result["atteint_frontiere"]:
    for n in result["near_border_nodes"][:5]:
        km = nx.shortest_path_length(G, dest, n, weight="weight") / 1000
        print(f"   noeud {n} -> {km:.2f} km")
