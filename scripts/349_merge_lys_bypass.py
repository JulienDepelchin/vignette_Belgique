import json
import sys

sys.path.insert(0, "d:/vignette_belgique")
from pipeline.gpx_utils import read_gpx_points, write_gpx

IN_PATH = "d:/vignette_belgique/data/traces_finales_gpx/Dunkerque_Kortrijk_brut.gpx"
OUT_PATH = "d:/vignette_belgique/data/traces_finales_gpx/Dunkerque_Kortrijk_brut.gpx"
BYPASS_JSON = "d:/vignette_belgique/scripts/tmp_bypass_lys_local_coords.json"

I_BEFORE = 1120
I_AFTER = 1191

points = read_gpx_points(IN_PATH)
print(f"trace complete : {len(points)} points")
print(f"avant = {I_BEFORE} {points[I_BEFORE]}")
print(f"apres = {I_AFTER} {points[I_AFTER]}")

with open(BYPASS_JSON, encoding="utf-8") as f:
    bypass_coords = json.load(f)
bypass_points = [(lat, lon) for lon, lat in bypass_coords]

new_points = points[: I_BEFORE + 1] + bypass_points + points[I_AFTER:]
print(f"nouvelle trace : {len(new_points)} points (segment remplace: {I_AFTER - I_BEFORE} -> {len(bypass_points)})")

write_gpx(new_points, OUT_PATH, name="Dunkerque -> Kortrijk (brut, sans vignette, evite halage Lys via Wervik)")
print(f"-> {OUT_PATH}")
