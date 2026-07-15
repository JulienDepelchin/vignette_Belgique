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

DESTINATIONS = {
    "Famiflora (Dottignies/Mouscron)": (3.282815, 50.717576),
    "King Tabac (Mouscron)": (3.194531, 50.726050),
    "Gabriëls (Comines-Warneton)": (3.018049, 50.776567),
}

BBOX = (2.93, 50.68, 3.35, 50.82)

print("1. Fetch PICC...")
gdf = fetch_picc(BBOX, WAL / "picc_pilote" / "voirie_axe_mouscron_comines.gpkg")
print(f"   {len(gdf)} tronçons")

print("2. Filtre GESTION=Commune + NATUR_CODE=VCO...")
gdf_c = picc_carrossable_communal(gdf)
print(f"   {len(gdf_c)} tronçons")

print("3. Fetch/croisement OSM...")
osm = fetch_osm_highways(BBOX, WAL / "refs" / "osm_mouscron_comines.gpkg")
print(f"   {len(osm)} ways OSM")
gdf_final = apply_osm_crosscheck(gdf_c, osm)
print(f"   {len(gdf_final)} tronçons après croisement OSM (exclus: {len(gdf_c)-len(gdf_final)})")

print("4. Graphe + frontière...")
G, edge_geom = build_graph_picc(gdf_final)
border = fetch_border_line(BBOX, WAL / "refs" / "overpass_boundary_mouscron_comines.json")

print("\n=== Résultats par destination ===")
for nom, (lon, lat) in DESTINATIONS.items():
    dest_pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(gdf.crs).iloc[0]
    dest, dd = nearest_node_coord(G, dest_pt)
    result = analyse_reachability(G, dest, border, tol_m=50)
    print(f"\n{nom} (destination à {dd:.1f} m du réseau carrossable) :")
    print(f"   noeuds atteignables : {result['n_reachable']}")
    print(f"   atteint la frontière FR/BE : {result['atteint_frontiere']}")
    if result["atteint_frontiere"]:
        best = min(result["near_border_nodes"], key=lambda n: nx.shortest_path_length(G, dest, n, weight="weight"))
        km = nx.shortest_path_length(G, dest, best, weight="weight") / 1000
        print(f"   plus proche point frontière atteint : {km:.2f} km ({len(result['near_border_nodes'])} points frontière atteints au total)")
