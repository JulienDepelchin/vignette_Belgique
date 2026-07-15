import json
import glob
import urllib.request
import urllib.parse
from pathlib import Path
from xml.sax.saxutils import escape

import geopandas as gpd
from shapely.geometry import LineString, Point

GH_URL = "http://127.0.0.1:8989/route"
OUT_DIR = Path("d:/vignette_belgique/data/traces_finales_gpx")
LILLE = (50.6367, 3.0635)
CHARLEROI = (50.471744, 4.473366)


def alt_routes(lat1, lon1, lat2, lon2, max_paths=6, max_weight_factor=3.0, max_share_factor=0.5):
    params = [
        ("point", f"{lat1},{lon1}"), ("point", f"{lat2},{lon2}"),
        ("profile", "car"), ("points_encoded", "false"),
        ("algorithm", "alternative_route"),
        ("alternative_route.max_paths", str(max_paths)),
        ("alternative_route.max_weight_factor", str(max_weight_factor)),
        ("alternative_route.max_share_factor", str(max_share_factor)),
    ]
    url = GH_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


# charge toutes les lignes frontieres deja collectees
border_files = set(glob.glob("data/**/*boundary*.json", recursive=True))
lines = []
for fp in border_files:
    try:
        with open(fp, encoding="utf-8") as f:
            osm = json.load(f)
        for el in osm.get("elements", []):
            geom = el.get("geometry")
            if geom:
                lines.append(LineString([(g["lon"], g["lat"]) for g in geom]))
    except Exception:
        pass
border = gpd.GeoSeries(lines, crs="EPSG:4326").to_crs("EPSG:31370").union_all() if lines else None


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


data = alt_routes(*LILLE, *CHARLEROI)
print(f"{len(data['paths'])} itinéraires trouvés pour Charleroi\n")

results = []
for i, p in enumerate(data["paths"]):
    coords = p["points"]["coordinates"]
    km = p["distance"] / 1000
    minutes = p["time"] / 60000

    crossing_info = ""
    if border is not None:
        gdf_pts = gpd.GeoSeries([Point(c) for c in coords], crs="EPSG:4326").to_crs("EPSG:31370")
        dists = gdf_pts.distance(border)
        idx_cross = dists.idxmin()
        clon, clat = coords[idx_cross]
        crossing_info = f"franchissement ~lat {clat:.3f} (dist ligne: {dists.loc[idx_cross]:.0f}m)"

    print(f"Option {i+1}: {km:.2f} km, {minutes:.0f} min, {crossing_info}")
    results.append((i + 1, km, minutes, crossing_info))

    desc = f"Option {i+1}/{len(data['paths'])} - {km:.2f} km - {minutes:.0f} min - Lille -> Charleroi Aeroport - {crossing_info}"
    gpx = coords_to_gpx(f"Charleroi_option{i+1}", desc, coords)
    out_path = OUT_DIR / f"Charleroi_Aeroport_option{i+1}.gpx"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(gpx)

print(f"\n{len(data['paths'])} GPX exportés dans {OUT_DIR}")
