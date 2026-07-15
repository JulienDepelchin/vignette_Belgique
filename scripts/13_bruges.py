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
DEST_WGS84 = (3.224408, 51.208688)  # Bruges, Markt
# Bruges est a ~60km de la frontiere FR/BE (bien plus loin que les autres lieux) :
# on part d'une zone moderee autour de Bruges et on verifie si la composante
# atteignable reste contenue (pas besoin d'aller jusqu'a la frontiere pour
# repondre) avant d'elargir.
BBOX = (3.05, 51.10, 3.40, 51.30)

print("1. Fetch Wegenregister (zone moderee autour de Bruges)...")
gdf = fetch_wegsegment(BBOX, FLA / "wegenregister_pilote" / "wegsegment_bruges.gpkg")
print(f"   {len(gdf)} segments")

print("2. Filtre carrossabilite native...")
gdf_c = weg_carrossable_communal(gdf)
print(f"   {len(gdf_c)} segments")

print("3. Fetch/croisement OSM...")
osm = fetch_osm_highways(BBOX, FLA / "osm_bruges.gpkg")
gdf_final = apply_osm_crosscheck(gdf_c, osm)
print(f"   {len(gdf_final)} segments apres croisement OSM (exclus: {len(gdf_c)-len(gdf_final)})")

print("4. Graphe + composante atteignable...")
G, edge_geom = build_graph_weg(gdf_final)
node_coords = weg_node_coords(gdf_final)

dest_pt = gpd.GeoSeries([Point(DEST_WGS84)], crs="EPSG:4326").to_crs(gdf.crs).iloc[0]
dest, dd = nearest_node_weg(gdf_final, dest_pt)
print(f"destination a {dd:.1f}m")

reachable = nx.node_connected_component(G, dest)
print(f"noeuds atteignables (100% communal carrossable): {len(reachable)} / {G.number_of_nodes()}")

# verifier si la composante touche les bords de la bbox (signe qu'il faudrait elargir)
bbox_31370 = gpd.GeoSeries([Point(BBOX[0],BBOX[1]), Point(BBOX[2],BBOX[3])], crs="EPSG:4326").to_crs(gdf.crs)
xmin,ymin = bbox_31370.iloc[0].x, bbox_31370.iloc[0].y
xmax,ymax = bbox_31370.iloc[1].x, bbox_31370.iloc[1].y
xs = [n[0] for n in reachable if isinstance(n, tuple)] if False else [node_coords[n][0] for n in reachable if n in node_coords]
ys = [node_coords[n][1] for n in reachable if n in node_coords]
EDGE_TOL = 300
touches = {
    "ouest (vers France)": min(xs) < xmin+EDGE_TOL if xs else None,
    "sud": min(ys) < ymin+EDGE_TOL if ys else None,
    "est": max(xs) > xmax-EDGE_TOL if xs else None,
    "nord": max(ys) > ymax-EDGE_TOL if ys else None,
}
print("touche les bords de la zone recuperee:", touches)
print("(si 'ouest' est True, la composante pourrait continuer plus loin vers la frontiere -> elargir la zone)")
