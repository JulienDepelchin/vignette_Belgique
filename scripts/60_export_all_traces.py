import json
import time
import math
import urllib.request
import urllib.parse
from pathlib import Path

GH_URL = "http://127.0.0.1:8989/route"
OUT_DIR = Path("d:/vignette_belgique/data/traces_finales")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SNAP_ALERT_M = 60

LILLE = (50.6367, 3.0635)  # Grand-Place, origine unique pour tous les trajets

LIEUX = {
    "Bellewaerde": (50.845810, 2.949768),
    "Pairi_Daiza": (50.590627, 3.893746),
    "Plopsaland": (51.080738, 2.598554),
    "Famiflora": (50.717576, 3.282815),
    "Tournai": (50.606400, 3.386625),
    "Gabriels": (50.776567, 3.018049),
    "Real_Tabac": (50.789091, 3.139864),
    "King_Tabac": (50.726050, 3.194531),
    "La_Panne": (51.097367, 2.581506),
    "Mont_Noir": (50.782355, 2.742627),
    "Charleroi_Aeroport": (50.471744, 4.473366),
    "Mouscron_GrandPlace": (50.743954, 3.214896),
    "Floralux_Dadizele": (50.840552, 3.113505),
    "Bruges": (51.208688, 3.224408),
}


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def route(lat1, lon1, lat2, lon2):
    params = [("point", f"{lat1},{lon1}"), ("point", f"{lat2},{lon2}"),
              ("profile", "car"), ("points_encoded", "false")]
    url = GH_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": json.loads(e.read().decode()).get("message", "erreur inconnue")}


all_features = []
summary = []
for nom, (dlat, dlon) in LIEUX.items():
    olat, olon = LILLE
    data = route(olat, olon, dlat, dlon)
    if "error" in data:
        print(f"{nom}: ECHEC ({data['error'][:80]})")
        summary.append((nom, None, None, data["error"][:80]))
        continue

    p = data["paths"][0]
    coords = p["points"]["coordinates"]
    dist_km = round(p["distance"] / 1000, 2)
    arrivee = coords[-1]
    ecart_arrivee_m = haversine_m(dlat, dlon, arrivee[1], arrivee[0])

    alerte = ""
    if ecart_arrivee_m > SNAP_ALERT_M:
        alerte = f"[ALERTE] ARRIVEE A {ecart_arrivee_m:.0f}m DE LA DESTINATION DEMANDEE"

    print(f"{nom}: {dist_km} km {alerte}")
    summary.append((nom, dist_km, ecart_arrivee_m, alerte or "OK"))

    feature = {
        "type": "Feature",
        "properties": {
            "lieu": nom, "origine": "Lille (Grand-Place)", "distance_km": dist_km,
            "ecart_arrivee_m": round(ecart_arrivee_m, 1), "alerte": alerte or None,
        },
        "geometry": {"type": "LineString", "coordinates": coords},
    }
    all_features.append(feature)

    single = {"type": "FeatureCollection", "features": [feature]}
    with open(OUT_DIR / f"trace_{nom}.geojson", "w", encoding="utf-8") as f:
        json.dump(single, f, ensure_ascii=False)
    time.sleep(0.1)

combined = {"type": "FeatureCollection", "features": all_features}
with open(OUT_DIR / "trace_toutes.geojson", "w", encoding="utf-8") as f:
    json.dump(combined, f, ensure_ascii=False)

print(f"\n{len(all_features)} traces exportées dans {OUT_DIR}")
print("\n=== RESUME (depuis Lille) ===")
for nom, dist, ecart, statut in summary:
    print(f"{nom}: {dist if dist else '---'} km | {statut}")
