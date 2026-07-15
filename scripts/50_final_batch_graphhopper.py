import json
import time
import urllib.request
import urllib.parse

GH_URL = "http://127.0.0.1:8989/route"

LIEUX = {
    "Bellewaerde (Ieper)": {
        "dest": (50.845810, 2.949768),
        "origines": {"Boeschepestraat (frontiere confirmee)": (50.79666213236193, 2.727624356296882)},
    },
    "Pairi Daiza (Brugelette)": {
        "dest": (50.590627, 3.893746),
        "origines": {"Quievrain-frontiere": (50.408, 3.6875)},
    },
    "Plopsaland (De Panne)": {
        "dest": (51.080738, 2.598554),
        "origines": {"Smekaertstraat nord (frontiere confirmee)": (51.075791, 2.55549)},
    },
    "Famiflora (Dottignies)": {
        "dest": (50.717576, 3.282815),
        "origines": {"Roubaix-frontiere": (50.700, 3.260)},
    },
    "Bruges (Markt)": {
        "dest": (51.208688, 3.224408),
        "origines": {"Boeschepestraat (frontiere confirmee)": (50.79666213236193, 2.727624356296882)},
    },
    "Tournai (Grand-Place)": {
        "dest": (50.606400, 3.386625),
        "origines": {"Rue de Creplaine (frontiere confirmee)": (50.60576544737798, 3.2708757761016787)},
    },
    "Gabriels (Comines-Warneton)": {
        "dest": (50.776567, 3.018049),
        "origines": {"Comines (FR)": (50.766, 3.017)},
    },
    "Real Tabac (Menen)": {
        "dest": (50.789091, 3.139864),
        "origines": {"Halluin (FR)": (50.781, 3.121)},
    },
    "King Tabac (Mouscron)": {
        "dest": (50.726050, 3.194531),
        "origines": {"Tourcoing-frontiere": (50.718, 3.174)},
    },
    "La Panne (plage)": {
        "dest": (51.097367, 2.581506),
        "origines": {"proche 51.0888 (frontiere confirmee)": (51.088778, 2.545716)},
    },
    "Mont Noir (Zwarteberg)": {
        "dest": (50.782355, 2.742627),
        "origines": {"Boeschepestraat (frontiere confirmee)": (50.79666213236193, 2.727624356296882)},
    },
    "Aeroport de Charleroi": {
        "dest": (50.471744, 4.473366),
        "origines": {"Erquelinnes (FR/BE)": (50.3030620, 4.1584553)},
    },
    "Mouscron (Grand-Place)": {
        "dest": (50.743954, 3.214896),
        "origines": {"Neuville-en-Ferrain (FR)": (50.734, 3.174)},
    },
    "Floralux Dadizele": {
        "dest": (50.840552, 3.113505),
        "origines": {"Halluin (FR)": (50.781, 3.121)},
    },
}


def route(lat1, lon1, lat2, lon2):
    params = [("point", f"{lat1},{lon1}"), ("point", f"{lat2},{lon2}"),
              ("profile", "car"), ("points_encoded", "false")]
    url = GH_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.load(r)
        if "paths" in data and data["paths"]:
            p = data["paths"][0]
            return p["distance"], data
        return None, data
    except urllib.error.HTTPError as e:
        return None, json.loads(e.read().decode())


results = {}
for nom, cfg in LIEUX.items():
    dlat, dlon = cfg["dest"]
    best = None
    for label, (olat, olon) in cfg["origines"].items():
        dist, raw = route(olat, olon, dlat, dlon)
        status = f"{dist/1000:.2f} km" if dist else f"ECHEC ({raw.get('message','')[:70]})"
        print(f"{nom} <- {label}: {status}")
        if dist and (best is None or dist < best[1]):
            best = (label, dist)
        time.sleep(0.1)
    results[nom] = best
    print()

print("\n=== RESULTAT FINAL PAR LIEU ===")
for nom, best in results.items():
    if best:
        print(f"{nom}: {best[1]/1000:.2f} km (via {best[0]})")
    else:
        print(f"{nom}: AUCUNE ORIGINE TESTEE N'A DONNE DE ROUTE")
