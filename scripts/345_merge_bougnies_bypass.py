import json
import sys

sys.path.insert(0, "d:/vignette_belgique")
from pipeline.gpx_utils import read_gpx_points, write_gpx

IN_PATH = "d:/vignette_belgique/data/traces_finales_gpx/Valenciennes_Mons_brut.gpx"
OUT_PATH = "d:/vignette_belgique/data/traces_finales_gpx/Valenciennes_Mons_brut.gpx"
BYPASS_JSON = "d:/vignette_belgique/scripts/tmp_bypass_bougnies_coords.json"

BEFORE = (50.38445, 3.94227)
AFTER = (50.38869, 3.94469)


def closest_index(points, target, start=0, end=None):
    end = end if end is not None else len(points)
    best_i, best_d = None, float("inf")
    for i in range(start, end):
        lat, lon = points[i]
        d = (lat - target[0]) ** 2 + (lon - target[1]) ** 2
        if d < best_d:
            best_d, best_i = d, i
    return best_i


points = read_gpx_points(IN_PATH)
print(f"trace complete : {len(points)} points")

i_before = closest_index(points, BEFORE)
i_after = closest_index(points, AFTER, start=i_before)
print(f"avant (Rue Neuve) = {i_before} {points[i_before]}")
print(f"apres (Rue Neuve) = {i_after} {points[i_after]}")

with open(BYPASS_JSON, encoding="utf-8") as f:
    bypass_coords = json.load(f)
bypass_points = [(lat, lon) for lon, lat in bypass_coords]

new_points = points[: i_before + 1] + bypass_points + points[i_after:]
print(f"nouvelle trace : {len(new_points)} points (segment remplace: {i_after - i_before} -> {len(bypass_points)})")

write_gpx(new_points, OUT_PATH, name="Valenciennes -> Mons (brut, sans vignette, evite Rue Neuve pavee a Bougnies)")
print(f"-> {OUT_PATH}")
