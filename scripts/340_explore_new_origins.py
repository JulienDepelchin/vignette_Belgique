"""
Exploration rapide (routage brut, sans edition manuelle) pour la demande de
la redac : tester Dunkerque et Valenciennes comme nouveaux points de depart,
vers Zaventem, Charleroi, Pairi Daiza, Bellewaerde, Famiflora, Floralux et
Ostende (nouvelle destination, jamais testee).

Ceci n'est PAS le pipeline final (pas de trace GPX editee/verifiee a la
main) : juste un premier passage pour reperer les combinaisons plausibles,
les combinaisons suspectes (grosse deviation par rapport a la distance a vol
d'oiseau, symptome deja observe pour La Panne/Bruges/Plopsaland) et les
echecs purs.
"""
import json
import math
import sys
import urllib.parse
import urllib.request

GH_SANS = "http://127.0.0.1:8989/route"
GH_AVEC = "http://127.0.0.1:8991/route"

ORIGINS = {
    "dunkerque": (51.0347, 2.3773),      # place Jean-Bart
    "valenciennes": (50.3572, 3.5232),   # place d'Armes
}

DESTINATIONS = {
    "zaventem": (50.901389, 4.484444),
    "charleroi_aeroport": (50.471744, 4.473366),
    "pairi_daiza": (50.590627, 3.893746),
    "bellewaerde": (50.845810, 2.949768),
    "famiflora": (50.717576, 3.282815),
    "floralux_dadizele": (50.840552, 3.113505),
    "ostende": (51.2154, 2.9286),        # Wapenplein
}


def haversine_km(a, b):
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def route(base_url, start, end):
    params = [("point", f"{start[0]},{start[1]}"), ("point", f"{end[0]},{end[1]}"),
              ("profile", "car"), ("points_encoded", "false")]
    url = base_url + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return None, str(e)
    if "paths" not in data or not data["paths"]:
        return None, str(data)
    p = data["paths"][0]
    return {"distance_km": round(p["distance"] / 1000, 2), "time_min": round(p["time"] / 60000, 1)}, None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    for origin_id, origin_coord in ORIGINS.items():
        print(f"\n=== Depart : {origin_id} ===")
        for dest_id, dest_coord in DESTINATIONS.items():
            direct_km = haversine_km(origin_coord, dest_coord)

            avec, err_avec = route(GH_AVEC, origin_coord, dest_coord)
            sans, err_sans = route(GH_SANS, origin_coord, dest_coord)

            avec_s = f"{avec['distance_km']}km/{avec['time_min']}min" if avec else f"ECHEC ({err_avec})"
            if sans:
                ratio = sans["distance_km"] / direct_km if direct_km > 0 else 0
                flag = "  <-- A VERIFIER (detour important)" if ratio > 2.2 else ""
                sans_s = f"{sans['distance_km']}km/{sans['time_min']}min (ratio vs vol d'oiseau: {ratio:.1f}x){flag}"
            else:
                sans_s = f"ECHEC ({err_sans})"

            print(f"  -> {dest_id:22s} vol d'oiseau={direct_km:6.1f}km | avec={avec_s:35s} | sans={sans_s}")


if __name__ == "__main__":
    main()
