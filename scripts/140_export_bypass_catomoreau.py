import json
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path("d:/vignette_belgique/data/traces_finales_gpx/Charleroi_bypass_Catomoreau.gpx")

with open("d:/vignette_belgique/scripts/tmp_bypass_coords.json", encoding="utf-8") as f:
    coords = json.load(f)  # [lon, lat] pairs

trkpts = "\n".join(f'      <trkpt lat="{lat}" lon="{lon}"></trkpt>' for lon, lat in coords)
gpx = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="vignette-belgique" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>Charleroi_bypass_Catomoreau</name>
    <desc>{escape("Deviation qui evite le Chemin de Catomoreau/Catamouriaux (piste forestiere interdite aux voitures) "
                   "et les routes privees (Drieve d'Argenteuil). Passe par le centre de Waterloo puis Chemin du Smohain / "
                   "Chemin de la Marache. Remplace le trace entre lat 50.691134,lon 4.419758 (juste avant Catomoreau) "
                   "et lat 50.68278,lon 4.43967 (jonction Chemin de l'Alouette / Chemin n46, sur Chemin de la Sablonniere).")}</desc>
    <trkseg>
{trkpts}
    </trkseg>
  </trk>
</gpx>
"""
with open(OUT, "w", encoding="utf-8") as f:
    f.write(gpx)
print(f"exporte: {OUT} ({len(coords)} points)")
