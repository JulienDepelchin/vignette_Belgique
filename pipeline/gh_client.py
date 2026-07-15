"""Client HTTP minimal pour l'API /route de GraphHopper."""
import json
import urllib.error
import urllib.parse
import urllib.request

from . import config

DETAILS = ["road_class", "average_speed", "roundabout", "road_environment"]


class RoutingError(Exception):
    pass


def route(points, url, details=None, instructions=True):
    """
    points : liste de (lat, lon), au moins 2 (depart, arrivee, + eventuels via).
    Retourne le premier "path" de la reponse GraphHopper (dict), ou leve
    RoutingError si aucun chemin trouve.
    """
    params = [("point", f"{lat},{lon}") for lat, lon in points]
    params += [("profile", config.GH_PROFILE), ("points_encoded", "false")]
    if instructions:
        params.append(("instructions", "true"))
    for d in (details if details is not None else DETAILS):
        params.append(("details", d))
    full_url = url + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(full_url, timeout=config.GH_TIMEOUT_S) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        msg = json.loads(e.read().decode()).get("message", str(e))
        raise RoutingError(msg)
    if "paths" not in data or not data["paths"]:
        raise RoutingError("no path in response")
    return data["paths"][0]


def route_or_none(points, url, details=None, instructions=True):
    try:
        return route(points, url, details=details, instructions=instructions)
    except RoutingError:
        return None
