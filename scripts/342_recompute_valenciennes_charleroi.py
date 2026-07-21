"""
Recalcule le trajet Valenciennes -> Charleroi (sans vignette) en excluant le
troncon "track" qui franchit la frontiere a Saint-Aybert/Hensies (barriere
physique constatee sur place par l'utilisateur, non taguee dans OSM).

Remplace data/traces_finales_gpx/Valenciennes_Charleroi_Aeroport_brut.gpx.
"""
import json
import sys
import urllib.request

import geopandas as gpd
from shapely.geometry import LineString

sys.path.insert(0, "d:/vignette_belgique")
from pipeline.gpx_utils import write_gpx

GH_URL = "http://127.0.0.1:8989/route"
OUT_PATH = "d:/vignette_belgique/data/traces_finales_gpx/Valenciennes_Charleroi_Aeroport_brut.gpx"

ORIGIN = (50.3572, 3.5232)
DEST = (50.471744, 4.473366)

# way 281006855 (troncon qui franchit la frontiere) + way 281007051 (embranchement voisin)
track_coords = [
    (3.669959, 50.437302), (3.669737, 50.437221), (3.669356, 50.437079), (3.669085, 50.436967),
    (3.668511, 50.436724), (3.668098, 50.436558), (3.667693, 50.436381), (3.667229, 50.436169),
    (3.667052, 50.436088), (3.666827, 50.436), (3.666532, 50.435906), (3.666194, 50.435827),
    (3.666043, 50.4358), (3.665998, 50.435783), (3.665971, 50.435757), (3.665932, 50.435741),
    (3.665904, 50.435723), (3.665805, 50.435701),
    (3.665328, 50.437449), (3.66544, 50.437486), (3.665543, 50.437518), (3.665636, 50.437548),
    (3.665797, 50.437595), (3.666033, 50.43766), (3.666218, 50.437694),
]
line = LineString(track_coords)
gs = gpd.GeoSeries([line], crs="EPSG:4326").to_crs("EPSG:31370")
buffered = gs.buffer(40).to_crs("EPSG:4326").iloc[0]
zone_coords = [list(c) for c in buffered.exterior.coords]

body = {
    "points": [[ORIGIN[1], ORIGIN[0]], [DEST[1], DEST[0]]],
    "profile": "car",
    "points_encoded": False,
    "instructions": True,
    "custom_model": {
        "priority": [{"if": "in_zone1", "multiply_by": "0"}],
        "areas": {
            "zone1": {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [zone_coords]}},
        },
    },
}

req = urllib.request.Request(
    GH_URL, data=json.dumps(body).encode("utf-8"),
    headers={"Content-Type": "application/json"}, method="POST",
)
with urllib.request.urlopen(req, timeout=30) as r:
    data = json.load(r)

p = data["paths"][0]
print(f"{p['distance']/1000:.2f} km, {p['time']/60000:.0f} min")

coords = p["points"]["coordinates"]  # [lon, lat]
points = [(lat, lon) for lon, lat in coords]
write_gpx(points, OUT_PATH, name="Valenciennes -> Charleroi_Aeroport (brut, sans vignette, contournement Saint-Aybert)")
print(f"{len(points)} points -> {OUT_PATH}")
