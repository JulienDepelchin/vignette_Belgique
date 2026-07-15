import sys
sys.path.insert(0, "d:/vignette_belgique/scripts")
from lib_vignette import (
    fetch_picc, picc_carrossable_communal, build_graph_picc_tolerant, nearest_node_clustered,
    fetch_osm_highways, apply_osm_crosscheck, fetch_border_line, analyse_reachability,
)
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import linemerge
import networkx as nx
from pathlib import Path

WAL = Path("d:/vignette_belgique/data/wallonie")

ZONES = {
    "tournai": {
        "bbox": (3.255, 50.590, 3.410, 50.625),
        "picc_cache": "voirie_axe_tournai_v3.gpkg",
        "osm_cache": "osm_tournai_v3.gpkg",
        "border_cache": "overpass_boundary_tournai.json",
        "destinations": {"Tournai (Grand-Place)": (3.386625, 50.606400)},
    },
    "pairi_daiza": {
        "bbox": (3.60, 50.32, 3.96, 50.63),
        "picc_cache": "voirie_axe_pairi_daiza_v2.gpkg",
        "osm_cache": "osm_pairi_daiza_v2.gpkg",
        "border_cache": "overpass_boundary_pairi_daiza.json",
        "destinations": {"Pairi Daiza": (3.893746, 50.590627)},
    },
    "mouscron_comines": {
        "bbox": (2.93, 50.68, 3.35, 50.82),
        "picc_cache": "voirie_axe_mouscron_comines_v2.gpkg",
        "osm_cache": "osm_mouscron_comines_v2.gpkg",
        "border_cache": "overpass_boundary_mouscron_comines.json",
        "destinations": {
            "Famiflora (Dottignies/Mouscron)": (3.282815, 50.717576),
            "King Tabac (Mouscron)": (3.194531, 50.726050),
            "Gabriëls (Comines-Warneton)": (3.018049, 50.776567),
        },
    },
}

TOLERANCES = [15, 30, 50, 75, 110, 150, 200]

results = {}

for zone_name, cfg in ZONES.items():
    print(f"\n{'='*60}\nZONE: {zone_name}\n{'='*60}")
    gdf = fetch_picc(cfg["bbox"], WAL / "picc_pilote" / cfg["picc_cache"])
    print(f"PICC: {len(gdf)} tronçons")
    gdf_c = picc_carrossable_communal(gdf)
    osm = fetch_osm_highways(cfg["bbox"], WAL / "refs" / cfg["osm_cache"])
    print(f"OSM: {len(osm)} ways, CRS={osm.crs}")
    gdf_final = apply_osm_crosscheck(gdf_c, osm)
    print(f"Carrossable final: {len(gdf_final)} (exclus par OSM: {len(gdf_c)-len(gdf_final)})")
    border = fetch_border_line(cfg["bbox"], WAL / "refs" / cfg["border_cache"])

    for dest_name, (lon, lat) in cfg["destinations"].items():
        print(f"\n--- {dest_name} ---")
        found = False
        for tol in TOLERANCES:
            G, edge_geom, cluster_coord = build_graph_picc_tolerant(gdf_final, tolerance_m=tol)
            pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(gdf.crs).iloc[0]
            node, dd = nearest_node_clustered(G, cluster_coord, pt)
            comp_size = len(nx.node_connected_component(G, node))
            result = analyse_reachability(G, node, border, tol_m=50, get_coord=lambda n: cluster_coord.get(n))
            print(f"  tol={tol}m: poche={comp_size}, atteint_frontiere={result['atteint_frontiere']}")
            if result["atteint_frontiere"]:
                best = min(result["near_border_nodes"], key=lambda n: nx.shortest_path_length(G, node, n, weight="weight"))
                km = nx.shortest_path_length(G, node, best, weight="weight") / 1000
                path = nx.shortest_path(G, node, best, weight="weight")
                print(f"  >>> TROUVÉ à tol={tol}m : {km:.2f} km")
                results[dest_name] = {"tol": tol, "km": km, "poche": comp_size}
                # export trace
                segs = [edge_geom[frozenset((u, v))] for u, v in zip(path[:-1], path[1:]) if frozenset((u, v)) in edge_geom]
                safe_name = dest_name.split(" ")[0].replace("(", "").replace(")", "")
                trace = gpd.GeoDataFrame({"longueur_km": [km], "tolerance_m": [tol]}, geometry=[linemerge(segs)], crs=gdf.crs)
                trace.to_file(WAL / "picc_pilote" / f"trace_final_{safe_name}.gpkg", driver="GPKG")
                found = True
                break
        if not found:
            print(f"  >>> NON JOIGNABLE même à {TOLERANCES[-1]}m")
            results[dest_name] = {"tol": None, "km": None, "poche": comp_size}

print("\n\n=== RÉSUMÉ FINAL WALLONIE ===")
for k, v in results.items():
    print(k, v)
