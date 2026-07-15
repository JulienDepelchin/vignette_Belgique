import json
import urllib.request
import urllib.parse

GH_VIGNETTE_FREE = "http://127.0.0.1:8989/route"  # motor_vehicle=no sur le regional
GH_NORMAL = "http://127.0.0.1:8991/route"  # sans restriction (avec vignette, autoroutes autorisees)

LILLE = (50.6367, 3.0635)

LIEUX = {
    "Bellewaerde": (50.845810, 2.949768),
    "Pairi_Daiza": (50.590627, 3.893746),
    "Famiflora": (50.717576, 3.282815),
    "Tournai": (50.606400, 3.386625),
    "Gabriels": (50.776567, 3.018049),
    "Real_Tabac": (50.789091, 3.139864),
    "King_Tabac": (50.726050, 3.194531),
    "Mont_Noir": (50.782355, 2.742627),
    "Charleroi_Aeroport": (50.471744, 4.473366),
    "Mouscron_GrandPlace": (50.743954, 3.214896),
    "Floralux_Dadizele": (50.840552, 3.113505),
}


def route(base_url, lat1, lon1, lat2, lon2):
    params = [("point", f"{lat1},{lon1}"), ("point", f"{lat2},{lon2}"),
              ("profile", "car"), ("points_encoded", "false")]
    url = base_url + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r)
        if "paths" in data and data["paths"]:
            p = data["paths"][0]
            return p["distance"] / 1000, p["time"] / 60000
        return None, None
    except Exception:
        return None, None


print(f"{'Lieu':<22} {'Sans vignette':<20} {'Avec vignette':<20} {'Delta km':<10} {'Delta temps':<12}")
print("-" * 90)
rows = []
for nom, (dlat, dlon) in LIEUX.items():
    km_free, min_free = route(GH_VIGNETTE_FREE, *LILLE, dlat, dlon)
    km_norm, min_norm = route(GH_NORMAL, *LILLE, dlat, dlon)

    if km_free is None or km_norm is None:
        print(f"{nom:<22} ECHEC")
        continue

    delta_km = km_free - km_norm
    delta_min = min_free - min_norm
    rows.append((nom, km_free, min_free, km_norm, min_norm, delta_km, delta_min))
    print(f"{nom:<22} {km_free:>6.1f} km / {min_free:>4.0f} min   {km_norm:>6.1f} km / {min_norm:>4.0f} min   "
          f"{delta_km:>+6.1f} km   {delta_min:>+5.0f} min")

print("\n=== JSON ===")
print(json.dumps([
    {"lieu": r[0], "sans_vignette_km": round(r[1], 1), "sans_vignette_min": round(r[2]),
     "avec_vignette_km": round(r[3], 1), "avec_vignette_min": round(r[4]),
     "delta_km": round(r[5], 1), "delta_min": round(r[6])}
    for r in rows
], ensure_ascii=False, indent=2))
