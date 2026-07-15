"""
Construit un "profil de route" (distance, temps, vitesse, repartition par type
de route, giratoires, changements de direction) a partir des reponses
GraphHopper -- soit une requete unique (itineraire "avec vignette", calcule de
zero), soit un routage segment par segment d'un trace GPX dessine a la main
(itineraire "sans vignette", deja fixe -- cf. README section "Limites
methodologiques" pour la justification de cette approche en deux temps).
"""
from dataclasses import dataclass, field

from . import config, gh_client
from .gpx_utils import haversine_m


@dataclass
class RouteProfile:
    points: list                     # [(lat, lon), ...] -- geometrie complete du trace
    distance_m: float                # distance totale (toujours la longueur reelle du trace)
    time_s: float                    # temps total (mesure ou estime, cf. methode)
    road_class_m: dict = field(default_factory=dict)   # {road_class: metres}
    speed_segments: list = field(default_factory=list)  # [(distance_m, vitesse_kmh), ...] segments "propres" uniquement
    roundabout_count: int = 0
    instruction_count: int = 0
    n_breaks: int = 0
    break_details: list = field(default_factory=list)
    method: str = ""                 # "route_unique" ou "legwise_gpx"

    @property
    def distance_km(self):
        return self.distance_m / 1000

    @property
    def time_min(self):
        return self.time_s / 60

    @property
    def avg_speed_kmh(self):
        if self.time_s <= 0:
            return None
        return self.distance_km / (self.time_s / 3600)

    @property
    def median_speed_kmh(self):
        if not self.speed_segments:
            return None
        # mediane ponderee par distance
        segs = sorted(self.speed_segments, key=lambda x: x[1])
        total = sum(d for d, _ in segs)
        if total <= 0:
            return None
        cum = 0
        half = total / 2
        for d, spd in segs:
            cum += d
            if cum >= half:
                return spd
        return segs[-1][1]

    def time_below_above_s(self, low_kmh, high_kmh):
        """Retourne (temps_s a vitesse < low, temps_s a vitesse > high) sur les segments 'propres'."""
        below = above = 0.0
        for dist_m, spd in self.speed_segments:
            if spd <= 0:
                continue
            t = dist_m / 1000 / spd * 3600
            if spd < low_kmh:
                below += t
            elif spd > high_kmh:
                above += t
        return below, above


def _cumulative_distances(coords_lonlat):
    """coords_lonlat: [[lon, lat], ...]. Retourne liste des distances cumulees (m) par index."""
    cum = [0.0]
    for i in range(1, len(coords_lonlat)):
        lon1, lat1 = coords_lonlat[i - 1]
        lon2, lat2 = coords_lonlat[i]
        cum.append(cum[-1] + haversine_m(lat1, lon1, lat2, lon2))
    return cum


def profile_from_single_route(path):
    """Construit un RouteProfile a partir d'une reponse GraphHopper /route unique
    (cas 'avec vignette', calcule de zero -- pas d'ambiguite de connectivite)."""
    coords = path["points"]["coordinates"]  # [[lon, lat], ...]
    points = [(lat, lon) for lon, lat in coords]
    cum = _cumulative_distances(coords)

    road_class_m = {}
    for start, end, cls in path.get("details", {}).get("road_class", []):
        road_class_m[cls] = road_class_m.get(cls, 0) + (cum[end] - cum[start])

    speed_segments = []
    for start, end, spd in path.get("details", {}).get("average_speed", []):
        if spd is None:
            continue
        d = cum[end] - cum[start]
        if d > 0:
            speed_segments.append((d, spd))

    roundabout_count = sum(
        1 for start, end, is_r in path.get("details", {}).get("roundabout", []) if is_r
    )

    instructions = path.get("instructions", [])
    instruction_count = max(0, len(instructions) - 1)  # exclut "arrive at destination"

    return RouteProfile(
        points=points,
        distance_m=path["distance"],
        time_s=path["time"] / 1000,
        road_class_m=road_class_m,
        speed_segments=speed_segments,
        roundabout_count=roundabout_count,
        instruction_count=instruction_count,
        method="route_unique",
    )


def profile_from_gpx_legwise(points, url=None):
    """
    Construit un RouteProfile robuste a partir d'un trace GPX dessine/edite a la
    main : on echantillonne le trace (config.SAMPLE_EVERY_N_POINTS) et on route
    chaque segment individuellement. Un segment dont le routage s'ecarte
    fortement de la distance directe (cf. config.BREAK_*) est traite comme une
    "cassure" (micro-imprecision de dessin ou vrai trou de connectivite) :
    sa distance reelle (directe) est comptee dans la distance totale et bascule
    dans le bucket road_class "non_classifie", mais n'alimente pas les stats de
    vitesse/temps (qui seraient faussees par le detour de contournement calcule).
    Le temps total est ensuite estime en appliquant la vitesse moyenne mesuree
    sur les segments propres a la distance totale reelle du trace.
    """
    url = url or config.GH_SANS_VIGNETTE_URL
    raw_distance_m = sum(haversine_m(*points[i], *points[i + 1]) for i in range(len(points) - 1))

    sample = points[::config.SAMPLE_EVERY_N_POINTS]
    if sample[-1] != points[-1]:
        sample.append(points[-1])

    clean_distance_m = 0.0
    clean_time_s = 0.0
    road_class_m = {}
    speed_segments = []
    roundabout_count = 0
    instruction_count = 0
    breaks = []

    for i in range(len(sample) - 1):
        p1, p2 = sample[i], sample[i + 1]
        direct = haversine_m(*p1, *p2)
        leg = gh_client.route_or_none([p1, p2], url)
        is_break = (
            leg is None
            or (leg["distance"] - direct > config.BREAK_ABS_THRESHOLD_M
                and direct > 5
                and leg["distance"] / direct > config.BREAK_RATIO_THRESHOLD)
        )
        if is_break:
            breaks.append({
                "index": i, "from": p1, "to": p2,
                "direct_m": direct, "routed_m": leg["distance"] if leg else None,
            })
            road_class_m["non_classifie"] = road_class_m.get("non_classifie", 0) + direct
            continue

        coords = leg["points"]["coordinates"]
        cum = _cumulative_distances(coords)
        for start, end, cls in leg.get("details", {}).get("road_class", []):
            road_class_m[cls] = road_class_m.get(cls, 0) + (cum[end] - cum[start])
        for start, end, spd in leg.get("details", {}).get("average_speed", []):
            if spd is None:
                continue
            d = cum[end] - cum[start]
            if d > 0:
                speed_segments.append((d, spd))
        roundabout_count += sum(1 for s, e, r in leg.get("details", {}).get("roundabout", []) if r)
        instruction_count += max(0, len(leg.get("instructions", [])) - 1)

        clean_distance_m += leg["distance"]
        clean_time_s += leg["time"] / 1000

    avg_speed_kmh = (clean_distance_m / 1000) / (clean_time_s / 3600) if clean_time_s else None
    time_s = (raw_distance_m / 1000 / avg_speed_kmh) * 3600 if avg_speed_kmh else None

    # normalisation : road_class_m doit sommer a la distance totale reelle
    total_classified = sum(road_class_m.values())
    if total_classified > 0:
        scale = raw_distance_m / total_classified
        road_class_m = {k: v * scale for k, v in road_class_m.items()}

    return RouteProfile(
        points=points,
        distance_m=raw_distance_m,
        time_s=time_s if time_s is not None else 0.0,
        road_class_m=road_class_m,
        speed_segments=speed_segments,
        roundabout_count=roundabout_count,
        instruction_count=instruction_count,
        n_breaks=len(breaks),
        break_details=breaks,
        method="legwise_gpx",
    )
