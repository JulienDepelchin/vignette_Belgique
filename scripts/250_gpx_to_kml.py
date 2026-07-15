import re
from pathlib import Path
from xml.sax.saxutils import escape

TRACES_DIR = Path("d:/vignette_belgique/data/traces_finales_definitives")
OUT_DIR = Path("d:/vignette_belgique/data/traces_finales_kml")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRKPT_RE = re.compile(r'<trkpt lat="([\-\d.]+)" lon="([\-\d.]+)"')

for fp in sorted(TRACES_DIR.glob("*.gpx")):
    text = fp.read_text(encoding="utf-8")
    pts = [(float(lat), float(lon)) for lat, lon in TRKPT_RE.findall(text)]
    coords_str = " ".join(f"{lon},{lat},0" for lat, lon in pts)
    name = fp.stem
    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{escape(name)} - vignette-free</name>
    <Style id="lineStyle">
      <LineStyle><color>ff0066ff</color><width>4</width></LineStyle>
    </Style>
    <Placemark>
      <name>{escape(name)}</name>
      <styleUrl>#lineStyle</styleUrl>
      <LineString>
        <tessellate>1</tessellate>
        <coordinates>{coords_str}</coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""
    out_path = OUT_DIR / f"{name}.kml"
    out_path.write_text(kml, encoding="utf-8")
    print(f"{name}: {len(pts)} points -> {out_path}")
