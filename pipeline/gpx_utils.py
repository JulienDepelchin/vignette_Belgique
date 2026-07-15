"""Lecture/ecriture GPX, conversion GeoJSON, geometrie de base."""
import json
import re
from math import radians, sin, cos, asin, sqrt
from pathlib import Path
from xml.sax.saxutils import escape

TRKPT_RE = re.compile(r'<trkpt lat="([\-\d.]+)" lon="([\-\d.]+)"')

EARTH_RADIUS_M = 6371000


def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


def read_gpx_points(path):
    """Retourne une liste de tuples (lat, lon) dans l'ordre du trace."""
    text = Path(path).read_text(encoding="utf-8")
    return [(float(lat), float(lon)) for lat, lon in TRKPT_RE.findall(text)]


def total_distance_m(points):
    return sum(haversine_m(*points[i], *points[i + 1]) for i in range(len(points) - 1))


def points_to_gpx(points, name, desc=""):
    trkpts = "\n".join(f'      <trkpt lat="{lat}" lon="{lon}"></trkpt>' for lat, lon in points)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="vignette-belgique-pipeline" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>{escape(name)}</name>
    <desc>{escape(desc)}</desc>
    <trkseg>
{trkpts}
    </trkseg>
  </trk>
</gpx>
"""


def points_to_geojson(points, properties=None):
    """points: liste de (lat, lon). GeoJSON attend (lon, lat)."""
    return {
        "type": "Feature",
        "properties": properties or {},
        "geometry": {
            "type": "LineString",
            "coordinates": [[lon, lat] for lat, lon in points],
        },
    }


def write_json(obj, path):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_gpx(points, path, name, desc=""):
    Path(path).write_text(points_to_gpx(points, name, desc), encoding="utf-8")
