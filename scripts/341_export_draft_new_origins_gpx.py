"""
Genere les traces "sans vignette" brutes (premier passage GraphHopper, pas
encore corrigees a la main) pour les 12 combinaisons Dunkerque/Valenciennes
juges plausibles lors de l'exploration (340_explore_new_origins.py).

Sortie : data/traces_finales_gpx/{Origine}_{Destination}_brut.gpx, a ouvrir
et corriger dans gpx.studio comme pour les traces precedentes (Zaventem,
Charleroi, etc.).

Ostende est explicitement exclu : reseau communal non connecte au reste du
graphe restreint (cf. 340_explore_new_origins.py, ConnectionNotFoundException
dans les deux sens), meme symptome que La Panne/Plopsaland/Bruges.
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, "d:/vignette_belgique")
from pipeline.gpx_utils import write_gpx

GH_SANS = "http://127.0.0.1:8989/route"

OUT_DIR = Path("d:/vignette_belgique/data/traces_finales_gpx")

ORIGINS = {
    "Dunkerque": (51.0347, 2.3773),
    "Valenciennes": (50.3572, 3.5232),
}

DESTINATIONS = {
    "Zaventem": (50.901389, 4.484444),
    "Charleroi_Aeroport": (50.471744, 4.473366),
    "Pairi_Daiza": (50.590627, 3.893746),
    "Bellewaerde": (50.845810, 2.949768),
    "Famiflora": (50.717576, 3.282815),
    "Floralux_Dadizele": (50.840552, 3.113505),
}


def route_points(start, end):
    params = [("point", f"{start[0]},{start[1]}"), ("point", f"{end[0]},{end[1]}"),
              ("profile", "car"), ("points_encoded", "false")]
    url = GH_SANS + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read())
    coords = data["paths"][0]["points"]["coordinates"]  # [lon, lat]
    return [(lat, lon) for lon, lat in coords]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for origin_name, origin_coord in ORIGINS.items():
        for dest_name, dest_coord in DESTINATIONS.items():
            points = route_points(origin_coord, dest_coord)
            out_path = OUT_DIR / f"{origin_name}_{dest_name}_brut.gpx"
            write_gpx(points, out_path, name=f"{origin_name} -> {dest_name} (brut, sans vignette)")
            print(f"{out_path.name}: {len(points)} points")


if __name__ == "__main__":
    main()
