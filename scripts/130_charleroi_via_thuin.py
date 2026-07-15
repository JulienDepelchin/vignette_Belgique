import json
import urllib.request
import urllib.parse
from pathlib import Path
from xml.sax.saxutils import escape

GH_URL = "http://127.0.0.1:8989/route"
OUT_DIR = Path("d:/vignette_belgique/data/traces_finales_gpx")

LILLE = (50.6367, 3.0635)
THUIN = (50.339, 4.286)
CHARLEROI = (50.471744, 4.473366)


def route_via(points):
    params = [("point", f"{lat},{lon}") for lat, lon in points]
    params += [("profile", "car"), ("points_encoded", "false")]
    url = GH_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": json.loads(e.read().decode()).get("message")}


data = route_via([LILLE, THUIN, CHARLEROI])
if "error" in data:
    print("ECHEC:", data["error"])
else:
    p = data["paths"][0]
    km = p["distance"] / 1000
    minutes = p["time"] / 60000
    print(f"Lille -> Thuin -> Charleroi : {km:.2f} km, {minutes:.0f} min")

    coords = p["points"]["coordinates"]
    trkpts = "\n".join(f'      <trkpt lat="{lat}" lon="{lon}"></trkpt>' for lon, lat in coords)
    gpx = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="vignette-belgique" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>Charleroi_via_Thuin</name>
    <desc>{escape(f"Lille -> Thuin -> Charleroi Aeroport - {km:.2f} km - {minutes:.0f} min")}</desc>
    <trkseg>
{trkpts}
    </trkseg>
  </trk>
</gpx>
"""
    out_path = OUT_DIR / "Charleroi_Aeroport_via_Thuin.gpx"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(gpx)
    print(f"exporté: {out_path}")
