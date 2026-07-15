"""
Statistiques editoriales derivees d'OpenStreetMap : communes traversees,
villages traverses, feux de circulation, repartition par type de route
administratif (communale/departementale/nationale-regionale/autoroute).

S'appuie sur des couches pre-extraites du PBF fusionne (cf. scripts/300-302),
chargees paresseusement et mises en cache au niveau module pour eviter de
recharger ~1,3M troncons a chaque appel.

Toute statistique non calculable de maniere fiable est retournee a None,
conformement a la consigne (mieux vaut null que trompeur).
"""
import re

from . import config

_communes_gdf = None
_places_gdf = None
_signals_gdf = None
_crossings_gdf = None
_roads_gdf = None
_roads_sindex = None

REF_AUTOROUTE = re.compile(r"^A\s?\d", re.I)
REF_NATIONALE_REGIONALE = re.compile(r"^N\s?\d", re.I)
REF_DEPARTEMENTALE = re.compile(r"^D\s?\d", re.I)
REF_RING = re.compile(r"^R\d", re.I)


def _lazy_import_gpd():
    import geopandas as gpd
    return gpd


_UNSET = object()


def _load_communes():
    global _communes_gdf
    if _communes_gdf is None:
        gpd = _lazy_import_gpd()
        if not config.OSM_COMMUNES_GPKG.exists():
            _communes_gdf = _UNSET
        else:
            _communes_gdf = gpd.read_file(config.OSM_COMMUNES_GPKG).to_crs("EPSG:31370")
            _communes_gdf["geometry"] = _communes_gdf.buffer(0)  # corrige d'eventuelles geometries invalides
    return None if _communes_gdf is _UNSET else _communes_gdf


def _load_places():
    global _places_gdf
    if _places_gdf is None:
        gpd = _lazy_import_gpd()
        if not config.OSM_PLACES_GPKG.exists():
            _places_gdf = _UNSET
        else:
            _places_gdf = gpd.read_file(config.OSM_PLACES_GPKG).to_crs("EPSG:31370")
    return None if _places_gdf is _UNSET else _places_gdf


def _load_signals():
    global _signals_gdf
    if _signals_gdf is None:
        gpd = _lazy_import_gpd()
        if not config.OSM_TRAFFIC_SIGNALS_GPKG.exists():
            _signals_gdf = _UNSET
        else:
            _signals_gdf = gpd.read_file(config.OSM_TRAFFIC_SIGNALS_GPKG).to_crs("EPSG:31370")
    return None if _signals_gdf is _UNSET else _signals_gdf


def _load_crossings():
    global _crossings_gdf
    if _crossings_gdf is None:
        gpd = _lazy_import_gpd()
        if not config.OSM_LEVEL_CROSSINGS_GPKG.exists():
            _crossings_gdf = _UNSET
        else:
            _crossings_gdf = gpd.read_file(config.OSM_LEVEL_CROSSINGS_GPKG).to_crs("EPSG:31370")
    return None if _crossings_gdf is _UNSET else _crossings_gdf


def _load_roads():
    global _roads_gdf, _roads_sindex
    if _roads_gdf is None:
        gpd = _lazy_import_gpd()
        if not config.OSM_ROADS_GPKG.exists():
            _roads_gdf = _UNSET
        else:
            _roads_gdf = gpd.read_file(config.OSM_ROADS_GPKG).to_crs("EPSG:31370")
            _roads_sindex = _roads_gdf.sindex
    if _roads_gdf is _UNSET:
        return None, None
    return _roads_gdf, _roads_sindex


def _points_to_line_gdf(points):
    gpd = _lazy_import_gpd()
    from shapely.geometry import LineString
    line = LineString([(lon, lat) for lat, lon in points])
    return gpd.GeoSeries([line], crs="EPSG:4326").to_crs("EPSG:31370").iloc[0]


def classify_ref(ref, highway):
    """Categorie administrative approximative a partir du ref OSM (prefixe
    A/N/D/R) avec repli sur la classe highway si pas de ref. cf. README pour
    les limites (le ref 'N' ne distingue pas nationale FR / regionale BE)."""
    if ref:
        for part in str(ref).split(";"):
            part = part.strip()
            if REF_AUTOROUTE.match(part):
                return "autoroute"
            if REF_NATIONALE_REGIONALE.match(part):
                return "nationale_regionale"
            if REF_DEPARTEMENTALE.match(part):
                return "departementale"
            if REF_RING.match(part):
                return "ring"
    if highway in ("motorway", "motorway_link"):
        return "autoroute"
    if highway in ("trunk", "trunk_link", "primary", "primary_link"):
        return "nationale_regionale"
    if highway in ("secondary", "secondary_link"):
        return "nationale_regionale"
    return "communale"


def _road_segment_matches(points, tolerance_m=None):
    """Pour chaque segment du trace, trouve le troncon OSM le plus proche
    (osm_roads.gpkg) et retourne (distance_m, categorie, ref). Calcul partage
    par road_type_distance_m et major_refs_used pour eviter deux passes."""
    roads_gdf, sindex = _load_roads()
    if roads_gdf is None:
        return None
    tolerance_m = tolerance_m or config.ROAD_REF_JOIN_TOLERANCE_M
    gpd = _lazy_import_gpd()
    from shapely.geometry import Point

    matches = []
    for i in range(len(points) - 1):
        lat1, lon1 = points[i]
        lat2, lon2 = points[i + 1]
        mid_lat, mid_lon = (lat1 + lat2) / 2, (lon1 + lon2) / 2
        d_m = _segment_length_m(lat1, lon1, lat2, lon2)
        pt = gpd.GeoSeries([Point(mid_lon, mid_lat)], crs="EPSG:4326").to_crs("EPSG:31370").iloc[0]
        cand_idx = list(sindex.query(pt.buffer(tolerance_m)))
        if not cand_idx:
            matches.append((d_m, "inconnu", ""))
            continue
        dists = roads_gdf.geometry.iloc[cand_idx].distance(pt)
        best = dists.idxmin()
        if dists.loc[best] > tolerance_m:
            matches.append((d_m, "inconnu", ""))
            continue
        ref = roads_gdf["ref"].iloc[best]
        highway = roads_gdf["highway"].iloc[best]
        matches.append((d_m, classify_ref(ref, highway), ref))
    return matches


def road_type_distance_m(points, tolerance_m=None):
    """Repartition de la distance du trace par categorie administrative de
    route (communale/departementale/nationale_regionale/autoroute/ring)."""
    matches = _road_segment_matches(points, tolerance_m)
    if matches is None:
        return None
    result = {}
    for d_m, cat, _ref in matches:
        result[cat] = result.get(cat, 0.0) + d_m
    return result


def major_refs_used(points, min_km=None, tolerance_m=None):
    """Liste des references de route (ex. 'A1', 'E42', 'N7') dont le cumul de
    distance sur le trace depasse min_km -- pour l'affichage type badge
    'Routes empruntees'. Retourne [] si le trace est purement communal, None
    si la couche routes n'est pas disponible."""
    matches = _road_segment_matches(points, tolerance_m)
    if matches is None:
        return None
    min_km = min_km if min_km is not None else config.MAJOR_REF_MIN_KM
    ref_dist = {}
    for d_m, _cat, ref in matches:
        if not ref:
            continue
        for part in str(ref).split(";"):
            part = part.strip()
            if part:
                ref_dist[part] = ref_dist.get(part, 0.0) + d_m
    return sorted([r for r, d in ref_dist.items() if d / 1000 >= min_km],
                  key=lambda r: -ref_dist[r])


def _segment_length_m(lat1, lon1, lat2, lon2):
    from .gpx_utils import haversine_m
    return haversine_m(lat1, lon1, lat2, lon2)


def communes_traversees(points):
    """Liste des noms de communes (admin_level=8) traversees par le trace
    (au moins config.COMMUNE_MIN_OVERLAP_M de chevauchement)."""
    communes_gdf = _load_communes()
    if communes_gdf is None:
        return None
    line = _points_to_line_gdf(points)
    sindex = communes_gdf.sindex
    cand_idx = list(sindex.query(line.buffer(5)))
    names = []
    for idx in cand_idx:
        geom = communes_gdf.geometry.iloc[idx]
        inter = line.intersection(geom)
        if inter.length > config.COMMUNE_MIN_OVERLAP_M:
            name = communes_gdf["name"].iloc[idx]
            if name:
                names.append(name)
    return sorted(set(names))


def villages_traverses(points):
    """Noms des lieux (place=village/hamlet/town/city) a moins de
    config.VILLAGE_PROXIMITY_M du trace."""
    places_gdf = _load_places()
    if places_gdf is None:
        return None
    line = _points_to_line_gdf(points)
    sindex = places_gdf.sindex
    cand_idx = list(sindex.query(line.buffer(config.VILLAGE_PROXIMITY_M)))
    names = []
    for idx in cand_idx:
        pt = places_gdf.geometry.iloc[idx]
        if line.distance(pt) <= config.VILLAGE_PROXIMITY_M:
            name = places_gdf["name"].iloc[idx]
            if name:
                names.append(name)
    return sorted(set(names))


def nombre_feux(points):
    """Nombre de feux de circulation (highway=traffic_signals) a moins de
    config.TRAFFIC_SIGNAL_BUFFER_M du trace."""
    signals_gdf = _load_signals()
    if signals_gdf is None:
        return None
    line = _points_to_line_gdf(points)
    sindex = signals_gdf.sindex
    cand_idx = list(sindex.query(line.buffer(config.TRAFFIC_SIGNAL_BUFFER_M)))
    count = 0
    for idx in cand_idx:
        pt = signals_gdf.geometry.iloc[idx]
        if line.distance(pt) <= config.TRAFFIC_SIGNAL_BUFFER_M:
            count += 1
    return count


def nombre_passages_a_niveau(points):
    """Nombre de passages a niveau (railway=level_crossing) a moins de
    config.LEVEL_CROSSING_BUFFER_M du trace."""
    crossings_gdf = _load_crossings()
    if crossings_gdf is None:
        return None
    line = _points_to_line_gdf(points)
    sindex = crossings_gdf.sindex
    cand_idx = list(sindex.query(line.buffer(config.LEVEL_CROSSING_BUFFER_M)))
    count = 0
    for idx in cand_idx:
        pt = crossings_gdf.geometry.iloc[idx]
        if line.distance(pt) <= config.LEVEL_CROSSING_BUFFER_M:
            count += 1
    return count


def villages_traverses_ordonnes(points):
    """Comme villages_traverses, mais retourne une liste de dicts
    {name, place_type, position_km} triee dans l'ordre de parcours du trace
    (projection sur la ligne), avec deduplication des lieux tres proches les
    uns des autres le long du trace (garde le type le plus 'important':
    city > town > village > suburb > hamlet)."""
    places_gdf = _load_places()
    if places_gdf is None:
        return None
    line = _points_to_line_gdf(points)
    total_len = line.length
    sindex = places_gdf.sindex
    cand_idx = list(sindex.query(line.buffer(config.VILLAGE_PROXIMITY_M)))

    importance = {"city": 4, "town": 3, "village": 2, "suburb": 1, "hamlet": 0}
    entries = []
    for idx in cand_idx:
        pt = places_gdf.geometry.iloc[idx]
        if line.distance(pt) > config.VILLAGE_PROXIMITY_M:
            continue
        name = places_gdf["name"].iloc[idx]
        if not name:
            continue
        pos_m = line.project(pt)
        entries.append({
            "name": name, "place_type": places_gdf["place_type"].iloc[idx],
            "position_km": round(pos_m / 1000, 2), "_pos_m": pos_m,
        })
    entries.sort(key=lambda e: e["_pos_m"])

    # deduplication : fusionne les entrees a moins de 400m les unes des autres
    # le long du trace (garde la plus 'importante')
    deduped = []
    for e in entries:
        if deduped and (e["_pos_m"] - deduped[-1]["_pos_m"]) < 400:
            if importance.get(e["place_type"], 0) > importance.get(deduped[-1]["place_type"], 0):
                deduped[-1] = e
            continue
        deduped.append(e)

    for e in deduped:
        del e["_pos_m"]
    return deduped


def distance_urbaine_km(points):
    """Estimation (approximative) de la distance parcourue en zone
    urbaine/bati, par union des buffers autour des noeuds 'place' proches du
    trace (rayon variable selon le type de lieu, cf.
    config.URBAN_BUFFER_M_BY_PLACE_TYPE). PROXY, pas une mesure sur couche de
    zones baties reelle -- cf. README limites."""
    places_gdf = _load_places()
    if places_gdf is None:
        return None
    gpd = _lazy_import_gpd()
    line = _points_to_line_gdf(points)
    sindex = places_gdf.sindex
    cand_idx = list(sindex.query(line.buffer(max(config.URBAN_BUFFER_M_BY_PLACE_TYPE.values()))))
    if not cand_idx:
        return 0.0

    buffers = []
    for idx in cand_idx:
        pt = places_gdf.geometry.iloc[idx]
        radius = config.URBAN_BUFFER_M_BY_PLACE_TYPE.get(places_gdf["place_type"].iloc[idx], 300)
        if line.distance(pt) <= radius:
            buffers.append(pt.buffer(radius))
    if not buffers:
        return 0.0
    from shapely.ops import unary_union
    union = unary_union(buffers)
    inter = line.intersection(union)
    return round(inter.length / 1000, 2)


def route_steps(points, total_time_min, depart_heure=None, depart_nom="Depart", arrivee_nom="Arrivee"):
    """Construit la liste d'etapes (villages traverses, dans l'ordre, avec une
    heure estimee par interpolation lineaire de la distance parcourue) pour
    l'affichage 'trajet etape par etape'. depart_heure au format 'HH:MM'."""
    import datetime

    villages = villages_traverses_ordonnes(points)
    if villages is None:
        return None
    depart_heure = depart_heure or config.DEPART_HEURE_DEFAUT
    t0 = datetime.datetime.strptime(depart_heure, "%H:%M")

    line = _points_to_line_gdf(points)
    total_km = line.length / 1000
    if total_km <= 0 or total_time_min <= 0:
        return None

    def heure_a(position_km):
        frac = min(1.0, max(0.0, position_km / total_km))
        return (t0 + datetime.timedelta(minutes=frac * total_time_min)).strftime("%H:%M")

    EDGE_SKIP_KM = 0.5  # evite un doublon depart/arrivee si un lieu-dit est juste a cote

    steps = [{"heure": t0.strftime("%H:%M"), "lieu": depart_nom, "position_km": 0.0, "type": "depart"}]
    for v in villages:
        if v["position_km"] < EDGE_SKIP_KM or v["position_km"] > total_km - EDGE_SKIP_KM:
            continue
        steps.append({
            "heure": heure_a(v["position_km"]), "lieu": v["name"],
            "position_km": v["position_km"], "type": "traversee_village",
        })
    steps.append({
        "heure": heure_a(total_km), "lieu": arrivee_nom,
        "position_km": round(total_km, 2), "type": "arrivee",
    })
    return steps
