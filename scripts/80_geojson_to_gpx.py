"""
Convertit les traces GeoJSON exportées (data/traces_finales/) en fichiers GPX,
un par lieu, pour édition manuelle dans gpx.studio.
"""
import json
from pathlib import Path
from xml.sax.saxutils import escape

IN_DIR = Path("d:/vignette_belgique/data/traces_finales")
OUT_DIR = Path("d:/vignette_belgique/data/traces_finales_gpx")
OUT_DIR.mkdir(parents=True, exist_ok=True)

GPX_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="vignette-belgique" xmlns="http://www.topografix.com/GPX/1/1">
"""
GPX_FOOTER = "</gpx>\n"


def feature_to_gpx(feature):
    props = feature["properties"]
    coords = feature["geometry"]["coordinates"]  # [lon, lat]
    nom = escape(str(props.get("lieu", "trace")))
    dist = props.get("distance_km", "")
    origine = escape(str(props.get("origine", "")))
    alerte = props.get("alerte")

    desc = f"Origine: {origine} | Distance: {dist} km"
    if alerte:
        desc += f" | ALERTE: {escape(str(alerte))}"

    trkpts = "\n".join(f'      <trkpt lat="{lat}" lon="{lon}"></trkpt>' for lon, lat in coords)

    return f"""{GPX_HEADER}  <trk>
    <name>{nom}</name>
    <desc>{escape(desc)}</desc>
    <trkseg>
{trkpts}
    </trkseg>
  </trk>
{GPX_FOOTER}"""


def main():
    geojson_files = list(IN_DIR.glob("trace_*.geojson"))
    geojson_files = [f for f in geojson_files if f.name not in ("trace_toutes.geojson",)]

    for f in geojson_files:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        if not data["features"]:
            continue
        feature = data["features"][0]
        gpx_content = feature_to_gpx(feature)
        out_name = f.stem.replace("trace_", "") + ".gpx"
        out_path = OUT_DIR / out_name
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(gpx_content)
        print(f"  {out_path.name}")

    print(f"\n{len(geojson_files)} fichiers GPX écrits dans {OUT_DIR}")


if __name__ == "__main__":
    main()
