import sys
sys.path.insert(0, "d:/vignette_belgique/scripts")
from lib_vignette import (
    fetch_wegsegment, weg_carrossable_communal, build_graph_weg, nearest_node_weg,
    fetch_osm_highways, apply_osm_crosscheck, fetch_border_line, analyse_reachability,
    weg_node_coords,
)
import geopandas as gpd
from shapely.geometry import Point
import networkx as nx
from pathlib import Path

FLA = Path("d:/vignette_belgique/data/flandre")

ZONES = {
    "bellewaerde": {
        "bbox": (2.59, 50.77, 2.96, 50.91),
        "weg_cache": "wegsegment_bellewaerde_v2.gpkg",
        "osm_cache": "osm_bellewaerde_v2.gpkg",
        "border_cache": "overpass_boundary_ieper_v2.json",
        "destinations": {"Bellewaerde": (2.949768, 50.845810)},
    },
    "plopsaland": {
        "bbox": (2.50, 51.02, 2.68, 51.13),
        "weg_cache": "wegsegment_plopsaland_v2.gpkg",
        "osm_cache": "osm_plopsaland_v2.gpkg",
        "border_cache": "overpass_boundary_depanne_v2.json",
        "destinations": {"Plopsaland": (2.598554, 51.080738)},
    },
    "bruges": {
        "bbox": (3.05, 51.10, 3.40, 51.30),
        "weg_cache": "wegsegment_bruges_v2.gpkg",
        "osm_cache": "osm_bruges_v2.gpkg",
        "border_cache": None,  # zone ne touche pas la frontiere, deja verifie
        "destinations": {"Bruges (Markt)": (3.224408, 51.208688)},
    },
    "menen": {
        "bbox": (2.968, 50.688, 3.333, 50.819),
        "weg_cache": "wegsegment_cluster_menen_v2.gpkg",
        "osm_cache": "osm_cluster_menen_v2.gpkg",
        "border_cache": "overpass_boundary_menen_v2.json",
        "destinations": {
            "Power Oil (Menen)": (3.167773, 50.771470),
            "Real Tabac & Co La Palma (Menen)": (3.139864, 50.789091),
        },
    },
}

results = {}

for zone_name, cfg in ZONES.items():
    print(f"\n{'='*60}\nZONE: {zone_name}\n{'='*60}")
    gdf = fetch_wegsegment(cfg["bbox"], FLA / "wegenregister_pilote" / cfg["weg_cache"])
    print(f"Wegenregister: {len(gdf)} segments")
    gdf_c = weg_carrossable_communal(gdf)
    osm = fetch_osm_highways(cfg["bbox"], FLA / cfg["osm_cache"])
    print(f"OSM: {len(osm)} ways, CRS={osm.crs}")
    gdf_final = apply_osm_crosscheck(gdf_c, osm)
    print(f"Carrossable final: {len(gdf_final)} (exclus par OSM: {len(gdf_c)-len(gdf_final)})")

    G, edge_geom = build_graph_weg(gdf_final)
    node_coords = weg_node_coords(gdf_final)
    border = fetch_border_line(cfg["bbox"], FLA / cfg["border_cache"]) if cfg["border_cache"] else None

    for dest_name, (lon, lat) in cfg["destinations"].items():
        pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(gdf.crs).iloc[0]
        node, dd = nearest_node_weg(gdf_final, pt)
        if node not in G:
            print(f"{dest_name}: hors graphe filtré")
            results[dest_name] = {"error": "hors graphe"}
            continue
        comp = nx.node_connected_component(G, node)
        print(f"\n{dest_name}: à {dd:.1f}m, poche={len(comp)}")
        if border is None:
            print("  (zone contenue, pas de test frontière - cf. analyse initiale)")
            results[dest_name] = {"poche": len(comp), "note": "zone non frontaliere"}
            continue
        result = analyse_reachability(G, node, border, tol_m=50, get_coord=lambda n: node_coords.get(n))
        print(f"  atteint_frontiere={result['atteint_frontiere']}")
        if result["atteint_frontiere"]:
            best = min(result["near_border_nodes"], key=lambda n: nx.shortest_path_length(G, node, n, weight="weight"))
            km = nx.shortest_path_length(G, node, best, weight="weight") / 1000
            print(f"  >>> {km:.2f} km")
            results[dest_name] = {"poche": len(comp), "km": km}
        else:
            results[dest_name] = {"poche": len(comp), "km": None}

print("\n\n=== RÉSUMÉ FINAL FLANDRE ===")
for k, v in results.items():
    print(k, v)
