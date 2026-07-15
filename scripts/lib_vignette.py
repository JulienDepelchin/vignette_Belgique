"""
Bibliothèque commune pour le testeur "sans vignette" - factorise le pipeline
validé sur les pilotes Tournai (WAL/PICC) et Bellewaerde (FLA/Wegenregister) :

  1. fetch (PICC REST ou Wegenregister OGC API Features, pagination)
  2. filtre à 3 niveaux : administratif (GESTION/wegbeheerder) + fonctionnel
     natif (NATUR_CODE / morfologischeWegklasse) + croisement OSM
     (highway/surface/tracktype) pour la carrossabilité réelle
  3. composante connexe atteignable depuis la destination (méthode "depuis
     la destination" - évite de deviner un point d'entrée frontalier)
  4. vérification de proximité à la frontière FR/BE (ligne admin_level=2 OSM)
"""
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import Point, LineString, MultiLineString, shape
from shapely.ops import linemerge

DATA_DIR = Path("d:/vignette_belgique/data")

NON_CARROSSABLE_HIGHWAY = {"track", "path", "footway", "cycleway", "bridleway", "steps", "pedestrian"}
NON_CARROSSABLE_SURFACE = {"unpaved", "ground", "grass", "dirt", "sand", "mud", "earth"}
BAD_TRACKTYPE = {"grade3", "grade4", "grade5"}
NON_CARROSSABLE_MORFO = "wandel- of fietsweg, niet toegankelijk voor andere voertuigen"


# ---------------------------------------------------------------------------
# Overpass (frontière + OSM highways) - tuilé, avec retry / pause anti rate-limit
# ---------------------------------------------------------------------------
def overpass_query(query: str, out_path: Path, timeout=90, retries=5) -> bool:
    if out_path.exists():
        return True
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                "https://overpass-api.de/api/interpreter",
                data=urllib.parse.urlencode({"data": query}).encode(),
                headers={"User-Agent": "vdn-data-journalism-research"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                content = r.read()
            json.loads(content)  # valide avant d'écrire
            with open(out_path, "wb") as f:
                f.write(content)
            time.sleep(5)  # ménager le serveur public avant la requête suivante
            return True
        except Exception as e:
            wait = 20 + attempt * 20
            print(f"  overpass tentative {attempt+1} échouée ({e}), pause {wait}s...")
            time.sleep(wait)
    return False


def fetch_osm_highways(bbox_wgs84, out_path: Path, tile_deg=0.12) -> gpd.GeoDataFrame:
    """bbox_wgs84 = (minlon, minlat, maxlon, maxlat). Tuile automatiquement
    pour éviter les timeouts Overpass sur les grandes zones."""
    if out_path.exists():
        return gpd.read_file(out_path)

    minlon, minlat, maxlon, maxlat = bbox_wgs84
    import math
    nx_tiles = max(1, math.ceil((maxlon - minlon) / tile_deg))
    ny_tiles = max(1, math.ceil((maxlat - minlat) / tile_deg))

    rows, geoms, seen_ids = [], [], set()
    for i in range(nx_tiles):
        for j in range(ny_tiles):
            t_minlon = minlon + i * tile_deg
            t_maxlon = min(minlon + (i + 1) * tile_deg, maxlon)
            t_minlat = minlat + j * tile_deg
            t_maxlat = min(minlat + (j + 1) * tile_deg, maxlat)
            tile_path = out_path.parent / f"_tile_{out_path.stem}_{i}_{j}.json"
            query = f'[out:json][timeout:60];way({t_minlat},{t_minlon},{t_maxlat},{t_maxlon})[highway];out geom;'
            ok = overpass_query(query, tile_path)
            if not ok:
                print(f"  tuile {i},{j} définitivement échouée, ignorée")
                continue
            with open(tile_path, encoding="utf-8") as f:
                osm = json.load(f)
            for el in osm.get("elements", []):
                if el["id"] in seen_ids:
                    continue
                seen_ids.add(el["id"])
                geom = el.get("geometry")
                tags = el.get("tags", {})
                if not geom or len(geom) < 2:
                    continue
                geoms.append(LineString([(g["lon"], g["lat"]) for g in geom]))
                rows.append({"highway": tags.get("highway"), "surface": tags.get("surface"),
                             "tracktype": tags.get("tracktype")})
            time.sleep(2)

    gdf = gpd.GeoDataFrame(pd.DataFrame(rows), geometry=geoms, crs="EPSG:4326").to_crs("EPSG:31370")
    gdf.to_file(out_path, driver="GPKG")
    return gdf


def fetch_border_line(bbox_wgs84, out_path: Path) -> "shapely.geometry.base.BaseGeometry":
    if out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            osm = json.load(f)
    else:
        minlon, minlat, maxlon, maxlat = bbox_wgs84
        query = f'[out:json][timeout:40];way({minlat},{minlon},{maxlat},{maxlon})["boundary"="administrative"]["admin_level"="2"];out geom;'
        ok = overpass_query(query, out_path)
        if not ok:
            raise RuntimeError("impossible de récupérer la frontière FR/BE")
        with open(out_path, encoding="utf-8") as f:
            osm = json.load(f)
    lines = [LineString([(g["lon"], g["lat"]) for g in el["geometry"]]) for el in osm["elements"] if el.get("geometry")]
    return gpd.GeoSeries(lines, crs="EPSG:4326").to_crs("EPSG:31370").union_all()


def is_carrossable_osm(row) -> bool:
    if row["highway"] in NON_CARROSSABLE_HIGHWAY:
        if row["highway"] == "track" and row["tracktype"] not in BAD_TRACKTYPE:
            return True
        return False
    if row["surface"] in NON_CARROSSABLE_SURFACE:
        return False
    if row["tracktype"] in BAD_TRACKTYPE:
        return False
    return True


def apply_osm_crosscheck(gdf: gpd.GeoDataFrame, osm_gdf: gpd.GeoDataFrame, buffer_m=10) -> gpd.GeoDataFrame:
    if osm_gdf.crs != gdf.crs:
        osm_gdf = osm_gdf.to_crs(gdf.crs)
    sidx = osm_gdf.sindex
    flags = []
    for geom in gdf.geometry:
        mid = geom.interpolate(0.5, normalized=True)
        idx = list(sidx.query(mid.buffer(buffer_m)))
        if not idx:
            flags.append(True)
            continue
        cand = osm_gdf.iloc[idx].copy()
        cand["d"] = cand.geometry.distance(mid)
        flags.append(is_carrossable_osm(cand.sort_values("d").iloc[0]))
    out = gdf.copy()
    out["osm_carrossable"] = flags
    return out[out["osm_carrossable"]]


# ---------------------------------------------------------------------------
# WALLONIE - PICC (ArcGIS REST)
# ---------------------------------------------------------------------------
PICC_URL = "https://geoservices.wallonie.be/arcgis/rest/services/TOPOGRAPHIE/PICC_VDIFF/MapServer/21/query"
PICC_FIELDS = "GEOREF_ID,NATUR_CODE,NATUR_DESC,TYPE_CODE,TYPE_DESC,GESTION,RUE_NOM1,COMMU_NOM1,VOIRIE_NOM,BDR_ID"


def fetch_picc(bbox_wgs84, out_path: Path, page_size=2000) -> gpd.GeoDataFrame:
    if out_path.exists():
        return gpd.read_file(out_path)
    minlon, minlat, maxlon, maxlat = bbox_wgs84
    offset, all_features = 0, []
    while True:
        params = {
            "f": "geojson", "geometry": f"{minlon},{minlat},{maxlon},{maxlat}",
            "geometryType": "esriGeometryEnvelope", "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects", "where": "1=1",
            "outFields": PICC_FIELDS, "returnGeometry": "true", "outSR": "4326",
            "orderByFields": "GEOREF_ID",  # pagination stable obligatoire (sinon offset-based skip des enregistrements)
            "resultOffset": str(offset), "resultRecordCount": str(page_size),
        }
        url = PICC_URL + "?" + urllib.parse.urlencode(params)
        data = None
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    data = json.load(r)
                break
            except Exception as e:
                wait = 5 * (attempt + 1)
                print(f"    [fetch_picc] erreur page offset={offset} ({e}), retry dans {wait}s...", flush=True)
                time.sleep(wait)
        if data is None:
            raise RuntimeError(f"fetch_picc: échec définitif à offset={offset}")
        feats = data.get("features", [])
        if not feats:
            break
        all_features.extend(feats)
        if len(feats) < page_size:
            break
        offset += page_size
        if offset % (page_size * 10) == 0:
            print(f"    [fetch_picc] {offset} tronçons récupérés...", flush=True)
        time.sleep(0.15)

    print(f"    [fetch_picc] total brut: {len(all_features)} tronçons, construction GeoDataFrame...", flush=True)
    rows = [f["properties"] for f in all_features]
    geoms = [shape(f["geometry"]) for f in all_features]
    gdf = gpd.GeoDataFrame(pd.DataFrame(rows), geometry=geoms, crs="EPSG:4326").to_crs("EPSG:31370")
    gdf.to_file(out_path, driver="GPKG")
    return gdf


def picc_carrossable_communal(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf[(gdf["GESTION"] == "Commune") & (gdf["NATUR_CODE"] == "VCO")]


def build_graph_picc(gdf: gpd.GeoDataFrame, snap_decimals=2):
    def snap(c):
        return (round(c[0], snap_decimals), round(c[1], snap_decimals))

    def iter_lines(geom):
        if isinstance(geom, LineString):
            yield geom
        elif isinstance(geom, MultiLineString):
            yield from geom.geoms

    G = nx.Graph()
    edge_geom = {}
    for _, row in gdf.iterrows():
        for line in iter_lines(row.geometry):
            coords = list(line.coords)
            if len(coords) < 2:
                continue
            u, v = snap(coords[0]), snap(coords[-1])
            G.add_edge(u, v, weight=line.length)
            edge_geom[frozenset((u, v))] = line
    return G, edge_geom


def build_graph_picc_tolerant(gdf: gpd.GeoDataFrame, tolerance_m=15):
    """Comme build_graph_picc, mais fusionne les extrémités de tronçons à
    moins de `tolerance_m` les unes des autres en un même noeud (union-find
    sur KDTree), au lieu d'un arrondi de coordonnées exact. Nécessaire car le
    PICC n'a pas de topologie de noeuds native : deux tronçons voisins mais
    digitalisés séparément peuvent avoir des extrémités décalées de plusieurs
    mètres (ex. cas réel observé : 11,6 m d'écart entre deux rues qui se
    touchent), ce qu'un simple round() ne rattrape pas."""
    import numpy as np
    from scipy.spatial import cKDTree

    def iter_lines(geom):
        if isinstance(geom, LineString):
            yield geom
        elif isinstance(geom, MultiLineString):
            yield from geom.geoms

    endpoints = []  # (x, y)
    edges_raw = []  # (idx_start, idx_end, length, row_index)
    lines_by_edge = []
    for row_idx, row in gdf.iterrows():
        for line in iter_lines(row.geometry):
            coords = list(line.coords)
            if len(coords) < 2:
                continue
            i0 = len(endpoints)
            endpoints.append(coords[0])
            i1 = len(endpoints)
            endpoints.append(coords[-1])
            edges_raw.append((i0, i1, line.length))
            lines_by_edge.append(line)

    pts = np.array(endpoints)
    tree = cKDTree(pts)
    pairs = tree.query_pairs(r=tolerance_m)

    parent = list(range(len(pts)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in pairs:
        union(a, b)

    G = nx.Graph()
    edge_geom = {}
    for (i0, i1, length), line in zip(edges_raw, lines_by_edge):
        u, v = find(i0), find(i1)
        if u == v:
            continue  # boucle sur elle-même après fusion, ignorée
        G.add_edge(u, v, weight=length)
        edge_geom[frozenset((u, v))] = line

    # coordonnées représentatives par cluster (pour repérage/distance)
    cluster_coord = {}
    for i, p in enumerate(endpoints):
        r = find(i)
        cluster_coord.setdefault(r, p)

    return G, edge_geom, cluster_coord


def nearest_node_coord(G: nx.Graph, point: Point):
    best, bd = None, float("inf")
    for n in G.nodes:
        d = (n[0] - point.x) ** 2 + (n[1] - point.y) ** 2
        if d < bd:
            best, bd = n, d
    return best, bd ** 0.5


def nearest_node_clustered(G: nx.Graph, cluster_coord: dict, point: Point):
    best, bd = None, float("inf")
    for n in G.nodes:
        c = cluster_coord.get(n)
        if c is None:
            continue
        d = (c[0] - point.x) ** 2 + (c[1] - point.y) ** 2
        if d < bd:
            best, bd = n, d
    return best, bd ** 0.5


# ---------------------------------------------------------------------------
# FLANDRE - Wegenregister (OGC API Features)
# ---------------------------------------------------------------------------
WEGSEGMENT_URL = "https://geo.api.vlaanderen.be/Wegenregister/ogc/features/v1/collections/Wegsegment/items"


def classify_wegbeheerder(label: str) -> str:
    if not label or label == "niet gekend":
        return "inconnu"
    if label == "Vlaams Gewest" or label.startswith("District "):
        return "regional"
    if label.startswith("Provincie "):
        return "provincial"
    if label.startswith("Particulier"):
        return "prive"
    if label.startswith("Afdeling "):
        return "waterweg"
    if label.startswith("Stad ") or label.startswith("Gemeente ") or label.startswith("Stadsbestuur"):
        return "communal"
    return "autre"


def fetch_wegsegment(bbox_wgs84, out_path: Path, page_size=1000) -> gpd.GeoDataFrame:
    if out_path.exists():
        return gpd.read_file(out_path)
    minlon, minlat, maxlon, maxlat = bbox_wgs84
    start_index, all_features = 0, []
    while True:
        params = {"bbox": f"{minlon},{minlat},{maxlon},{maxlat}", "limit": str(page_size),
                   "startIndex": str(start_index), "f": "application/geo+json"}
        url = WEGSEGMENT_URL + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "vdn-data-journalism-research"})
        data = None
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = json.load(r)
                break
            except Exception as e:
                wait = 5 * (attempt + 1)
                print(f"    [fetch_wegsegment] erreur page startIndex={start_index} ({e}), retry dans {wait}s...", flush=True)
                time.sleep(wait)
        if data is None:
            raise RuntimeError(f"fetch_wegsegment: échec définitif à startIndex={start_index}")
        feats = data.get("features", [])
        if not feats:
            break
        all_features.extend(feats)
        n_returned = data.get("numberReturned", len(feats))
        if n_returned < page_size:
            break
        start_index += page_size
        if start_index % (page_size * 10) == 0:
            print(f"    [fetch_wegsegment] {start_index} segments récupérés...", flush=True)
        time.sleep(0.15)

    print(f"    [fetch_wegsegment] total brut: {len(all_features)} segments, construction GeoDataFrame...", flush=True)
    rows = [f["properties"] for f in all_features]
    geoms = [shape(f["geometry"]) for f in all_features]
    gdf = gpd.GeoDataFrame(pd.DataFrame(rows), geometry=geoms, crs="EPSG:4326")
    gdf["classification"] = gdf["labelWegbeheerder"].apply(classify_wegbeheerder)
    gdf = gdf.to_crs("EPSG:31370")
    gdf.to_file(out_path, driver="GPKG")
    return gdf


def weg_carrossable_communal(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf[(gdf["classification"] == "communal")
               & (gdf["morfologischeWegklasse"] != NON_CARROSSABLE_MORFO)
               & (gdf["morfologischeWegklasse"] != "aardeweg")]


def build_graph_weg(gdf: gpd.GeoDataFrame):
    G = nx.Graph()
    edge_geom = {}
    for _, row in gdf.iterrows():
        u, v = row["beginknoopObjectId"], row["eindknoopObjectId"]
        G.add_edge(u, v, weight=row.geometry.length)
        edge_geom[frozenset((u, v))] = row.geometry
    return G, edge_geom


def nearest_node_weg(gdf: gpd.GeoDataFrame, point: Point):
    best, bd, best_node = None, float("inf"), None
    for _, row in gdf.iterrows():
        for node_id, coord in [(row["beginknoopObjectId"], row.geometry.coords[0]),
                                (row["eindknoopObjectId"], row.geometry.coords[-1])]:
            d = (coord[0] - point.x) ** 2 + (coord[1] - point.y) ** 2
            if d < bd:
                bd, best_node = d, node_id
    return best_node, bd ** 0.5


# ---------------------------------------------------------------------------
# Analyse commune : composante atteignable depuis la destination
# ---------------------------------------------------------------------------
def analyse_reachability(G: nx.Graph, dest_node, border_geom, tol_m=50, get_coord=None):
    """get_coord(node) -> (x,y). Par défaut le noeud EST la coordonnée (cas PICC,
    snappé). Pour Wegenregister (noeuds = ID entiers), fournir un get_coord basé
    sur beginknoopObjectId/eindknoopObjectId."""
    if get_coord is None:
        get_coord = lambda n: n
    reachable = nx.node_connected_component(G, dest_node)
    near_border = []
    for n in reachable:
        coord = get_coord(n)
        if coord is not None and Point(coord).distance(border_geom) < tol_m:
            near_border.append(n)
    return {
        "n_reachable": len(reachable),
        "reachable_nodes": reachable,
        "near_border_nodes": near_border,
        "atteint_frontiere": len(near_border) > 0,
    }


def weg_node_coords(gdf: gpd.GeoDataFrame) -> dict:
    coords = {}
    for _, row in gdf.iterrows():
        coords[row["beginknoopObjectId"]] = row.geometry.coords[0]
        coords[row["eindknoopObjectId"]] = row.geometry.coords[-1]
    return coords
