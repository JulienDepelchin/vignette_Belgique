"""
Construit des traces hybrides Lille -> frontiere (segment calcule sur le graphe
actuel, France+Belgique fusionnes) + frontiere -> destination (segment deja
valide separement sur le graphe Belgique seul, reutilise tel quel), pour les
lieux ou le trajet Lille->destination direct echoue dans le graphe fusionne
(Plopsaland, La Panne).
"""
import json
import urllib.request
import urllib.parse
from pathlib import Path

GH_URL = "http://127.0.0.1:8989/route"
TRACES_DIR = Path("d:/vignette_belgique/data/traces_finales")

LILLE = (50.6367, 3.0635)

CAS = {
    # point d'origine approximatif utilisé pour le test frontière->lieu (celui-ci
    # se connecte bien à Lille) ; le vrai point de jonction (première coordonnée
    # de la trace existante) est légèrement différent (~300-400m) - petit écart
    # de raccord à ajuster à la main lors de la finition GPX.
    "Plopsaland": {"lille_side_lonlat": (2.55549, 51.075791)},
    "La_Panne": {"lille_side_lonlat": (2.55549, 51.075791)},  # meme jonction que Plopsaland (Smekaertstraat), la seule qui se connecte a Lille dans ce secteur
}


def route(lat1, lon1, lat2, lon2):
    params = [("point", f"{lat1},{lon1}"), ("point", f"{lat2},{lon2}"),
              ("profile", "car"), ("points_encoded", "false")]
    url = GH_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


for nom, cfg in CAS.items():
    blon, blat = cfg["lille_side_lonlat"]
    data = route(LILLE[0], LILLE[1], blat, blon)
    p = data["paths"][0]
    seg1_coords = p["points"]["coordinates"]
    seg1_km = p["distance"] / 1000
    print(f"{nom}: Lille -> frontière = {seg1_km:.2f} km")

    with open(TRACES_DIR / f"trace_{nom}.geojson", encoding="utf-8") as f:
        existing = json.load(f)
    seg2_coords = existing["features"][0]["geometry"]["coordinates"]
    seg2_km = existing["features"][0]["properties"]["distance_km"]
    print(f"{nom}: frontière -> destination (déjà validé) = {seg2_km} km")

    combined_coords = seg1_coords + seg2_coords
    total_km = round(seg1_km + seg2_km, 2)

    feature = {
        "type": "Feature",
        "properties": {
            "lieu": nom,
            "origine": "Lille (Grand-Place), hybride: segment auto + segment frontière validé séparément",
            "distance_km": total_km,
            "distance_lille_frontiere_km": round(seg1_km, 2),
            "distance_frontiere_destination_km": seg2_km,
            "note": "Trace hybride : le trajet direct Lille->destination échoue dans le graphe fusionné (souci de sous-réseau élagué près de la côte). Concaténation de deux segments validés séparément - léger écart de raccord (~300-400m) entre les deux à ajuster à la main.",
        },
        "geometry": {"type": "LineString", "coordinates": combined_coords},
    }
    out = {"type": "FeatureCollection", "features": [feature]}
    with open(TRACES_DIR / f"trace_{nom}_hybride.geojson", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"{nom}: TOTAL = {total_km} km -> trace_{nom}_hybride.geojson\n")
