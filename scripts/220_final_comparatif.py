import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

MATCH_URL = "http://127.0.0.1:8989/match"
ROUTE_NORMAL_URL = "http://127.0.0.1:8991/route"
TRACES_DIR = Path("d:/vignette_belgique/data/traces_finales_definitives")

LILLE = (50.6367, 3.0635)

# nom_fichier -> (lat, lon) destination, pour la requete "avec vignette" (port 8991)
DESTINATIONS = {
    "Bellewaerde": (50.845810, 2.949768),
    "Pairi_Daiza": (50.590627, 3.893746),
    "Famiflora": (50.717576, 3.282815),
    "Tournai": (50.606400, 3.386625),
    "Mont_Noir": (50.782355, 2.742627),
    "Charleroi_Aeroport": (50.471744, 4.473366),
    "Mouscron_GrandPlace": (50.743954, 3.214896),
    "Floralux_Dadizele": (50.840552, 3.113505),
}


def map_match(gpx_path):
    with open(gpx_path, "rb") as f:
        body = f.read()
    params = [("profile", "car"), ("points_encoded", "false"), ("details", "road_class")]
    url = MATCH_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/gpx+xml"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    p = data["paths"][0]
    road_class = {}
    for start, end, cls in p.get("details", {}).get("road_class", []):
        road_class[cls] = road_class.get(cls, 0) + (end - start)
    return p["distance"] / 1000, p["time"] / 60000, road_class


def route_normal(dest):
    params = [("point", f"{LILLE[0]},{LILLE[1]}"), ("point", f"{dest[0]},{dest[1]}"),
              ("profile", "car"), ("points_encoded", "false")]
    url = ROUTE_NORMAL_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.load(r)
    p = data["paths"][0]
    return p["distance"] / 1000, p["time"] / 60000


results = []
for name, dest in DESTINATIONS.items():
    gpx_path = TRACES_DIR / f"{name}.gpx"
    km_free, min_free, road_class = map_match(gpx_path)
    km_norm, min_norm = route_normal(dest)
    delta_km = km_norm - km_free
    delta_min = min_norm - min_free
    results.append({
        "name": name, "km_free": km_free, "min_free": min_free,
        "km_norm": km_norm, "min_norm": min_norm,
        "delta_km": delta_km, "delta_min": delta_min, "road_class": road_class,
    })
    print(f"{name}:")
    print(f"  SANS vignette (trace validee, map-match) : {km_free:.2f} km, {min_free:.1f} min")
    print(f"  AVEC vignette (Lille->dest, reseau libre) : {km_norm:.2f} km, {min_norm:.1f} min")
    print(f"  delta : {delta_km:+.2f} km, {delta_min:+.1f} min")
    print(f"  road_class (nb points par type) : {road_class}")
    print()

with open("d:/vignette_belgique/scripts/tmp_comparatif_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("Resultats sauvegardes -> scripts/tmp_comparatif_results.json")
