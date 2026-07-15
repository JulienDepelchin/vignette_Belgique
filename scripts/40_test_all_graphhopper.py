import json
import time
import urllib.request
import urllib.parse

GH_URL = "http://127.0.0.1:8989/route"

# destination : (lat, lon, [candidats origine FR proches, lat/lon])
LIEUX = {
    "Bellewaerde (Ieper)": {
        "dest": (50.845810, 2.949768),
        "origines": {"Boeschepe (FR)": (50.796, 2.5375), "Steenvoorde (FR)": (50.813, 2.573)},
    },
    "Pairi Daiza (Brugelette)": {
        "dest": (50.590627, 3.893746),
        "origines": {"Bavay (FR)": (50.297, 3.792), "Feignies (FR)": (50.315, 3.926), "Quievrain-frontiere": (50.408, 3.6875)},
    },
    "Plopsaland (De Panne)": {
        "dest": (51.080738, 2.598554),
        "origines": {"Bray-Dunes (FR)": (51.076, 2.520), "Ghyvelde (FR)": (51.030, 2.548)},
    },
    "Famiflora (Dottignies)": {
        "dest": (50.717576, 3.282815),
        "origines": {"Wattrelos (FR)": (50.706, 3.217), "Neuville-en-Ferrain (FR)": (50.734, 3.174), "Roubaix-frontiere": (50.700, 3.260)},
    },
    "Bruges (Markt)": {
        "dest": (51.208688, 3.224408),
        "origines": {"Boeschepe (FR)": (50.796, 2.5375)},
    },
    "Tournai (Grand-Place)": {
        "dest": (50.606400, 3.386625),
        "origines": {"Rue de Creplaine (frontiere confirmee)": (50.60576544737798, 3.2708757761016787)},
    },
    "Power Oil (Menen)": {
        "dest": (50.771470, 3.167773),
        "origines": {"Halluin (FR)": (50.781, 3.121), "Roncq (FR)": (50.752, 3.132)},
    },
    "Gabriels (Comines-Warneton)": {
        "dest": (50.776567, 3.018049),
        "origines": {"Comines (FR)": (50.766, 3.017), "Wervicq-Sud (FR)": (50.775, 3.038)},
    },
    "Real Tabac (Menen)": {
        "dest": (50.789091, 3.139864),
        "origines": {"Halluin (FR)": (50.781, 3.121)},
    },
    "King Tabac (Mouscron)": {
        "dest": (50.726050, 3.194531),
        "origines": {"Neuville-en-Ferrain (FR)": (50.734, 3.174), "Tourcoing-frontiere": (50.718, 3.174)},
    },
}


def route(lat1, lon1, lat2, lon2):
    params = [("point", f"{lat1},{lon1}"), ("point", f"{lat2},{lon2}"),
              ("profile", "car"), ("points_encoded", "false")]
    url = GH_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.load(r)
        if "paths" in data and data["paths"]:
            p = data["paths"][0]
            return p["distance"], p["time"] / 1000, data
        return None, None, data
    except urllib.error.HTTPError as e:
        return None, None, {"error": e.read().decode()}


results = {}
for nom, cfg in LIEUX.items():
    dlat, dlon = cfg["dest"]
    best = None
    for label, (olat, olon) in cfg["origines"].items():
        dist, t, raw = route(olat, olon, dlat, dlon)
        status = f"{dist/1000:.2f} km" if dist else f"ECHEC ({raw.get('message', raw.get('error',''))[:80]})"
        print(f"{nom} <- {label}: {status}")
        if dist and (best is None or dist < best[1]):
            best = (label, dist, t)
        time.sleep(0.1)
    results[nom] = best
    print()

print("\n=== MEILLEUR RESULTAT PAR LIEU ===")
for nom, best in results.items():
    if best:
        print(f"{nom}: {best[1]/1000:.2f} km (via {best[0]})")
    else:
        print(f"{nom}: AUCUNE ORIGINE TESTEE N'A DONNE DE ROUTE")
