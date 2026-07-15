"""
Exporte les itinéraires alternatifs (algorithm=alternative_route) en GPX,
un fichier par option, pour comparaison visuelle dans gpx.studio/QGIS.
"""
import json
import urllib.request
import urllib.parse
from pathlib import Path
from xml.sax.saxutils import escape

GH_URL = "http://127.0.0.1:8989/route"
OUT_DIR = Path("d:/vignette_belgique/data/traces_finales_gpx")
OUT_DIR.mkdir(parents=True, exist_ok=True)

LILLE = (50.6367, 3.0635)


def alt_routes(lat1, lon1, lat2, lon2, max_paths=4):
    params = [
        ("point", f"{lat1},{lon1}"), ("point", f"{lat2},{lon2}"),
        ("profile", "car"), ("points_encoded", "false"),
        ("algorithm", "alternative_route"),
        ("alternative_route.max_paths", str(max_paths)),
        ("alternative_route.max_weight_factor", "2.0"),
        ("alternative_route.max_share_factor", "0.7"),
    ]
    url = GH_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def coords_to_gpx(nom, desc, coords):
    trkpts = "\n".join(f'      <trkpt lat="{lat}" lon="{lon}"></trkpt>' for lon, lat in coords)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="vignette-belgique" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>{escape(nom)}</name>
    <desc>{escape(desc)}</desc>
    <trkseg>
{trkpts}
    </trkseg>
  </trk>
</gpx>
"""


def export(nom_lieu, dest_lat, dest_lon):
    data = alt_routes(*LILLE, dest_lat, dest_lon)
    print(f"{nom_lieu}: {len(data['paths'])} itinéraires")
    for i, p in enumerate(data["paths"]):
        coords = p["points"]["coordinates"]
        km = p["distance"] / 1000
        minutes = p["time"] / 60000
        desc = f"Alternative {i+1}/{len(data['paths'])} - {km:.2f} km - {minutes:.0f} min - Lille -> {nom_lieu}"
        gpx = coords_to_gpx(f"{nom_lieu}_option{i+1}", desc, coords)
        out_path = OUT_DIR / f"{nom_lieu}_option{i+1}.gpx"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(gpx)
        print(f"  option {i+1}: {km:.2f} km, {minutes:.0f} min -> {out_path.name}")


if __name__ == "__main__":
    export("Pairi_Daiza", 50.590627, 3.893746)
