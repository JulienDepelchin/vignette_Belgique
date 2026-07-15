import re
import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

sys.stdout.reconfigure(encoding="utf-8")

TRACES_DIR = Path("d:/vignette_belgique/data/traces_finales_definitives")
CLASSIF_FILE = "d:/vignette_belgique/data/classification_unifiee.gpkg"
TOLERANCE_M = 20  # coherent avec la tolerance de jointure utilisee dans le pipeline (15m) + marge pour trace dessinee a la main

TRKPT_RE = re.compile(r'<trkpt lat="([\-\d.]+)" lon="([\-\d.]+)"')

print("Chargement de la classification officielle...")
classif = gpd.read_file(CLASSIF_FILE).to_crs("EPSG:31370")
sidx = classif.sindex
print(f"  {len(classif)} segments\n")

files = sorted(TRACES_DIR.glob("*.gpx"))
print(f"{len(files)} traces a verifier : {[f.name for f in files]}\n")

report = {}
for fp in files:
    text = fp.read_text(encoding="utf-8")
    pts = [(float(lat), float(lon)) for lat, lon in TRKPT_RE.findall(text)]
    gdf_pts = gpd.GeoSeries([Point(lon, lat) for lat, lon in pts], crs="EPSG:4326").to_crs("EPSG:31370")

    violations = []
    for i, pt in enumerate(gdf_pts):
        cand_idx = list(sidx.query(pt.buffer(TOLERANCE_M)))
        if not cand_idx:
            continue
        dists = classif.geometry.iloc[cand_idx].distance(pt)
        best = dists.idxmin()
        if dists.loc[best] > TOLERANCE_M:
            continue
        if classif["soumis_vignette"].iloc[best]:
            violations.append((i, pts[i], dists.loc[best]))

    print(f"=== {fp.name} ({len(pts)} points) ===")
    if not violations:
        print("  OK : aucun point proche d'une route regionale classee")
    else:
        # regrouper en sequences contigues
        groups = []
        cur = [violations[0]]
        for v in violations[1:]:
            if v[0] - cur[-1][0] <= 3:
                cur.append(v)
            else:
                groups.append(cur)
                cur = [v]
        groups.append(cur)
        print(f"  ALERTE : {len(violations)} points proches d'une route REGIONALE en {len(groups)} zone(s)")
        from math import radians, sin, cos, asin, sqrt

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371000
            p1, p2 = radians(lat1), radians(lat2)
            dphi = radians(lat2 - lat1)
            dlmb = radians(lon2 - lon1)
            a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
            return 2 * R * asin(sqrt(a))

        for g in groups:
            i0, i1 = g[0][0], g[-1][0]
            (lat0, lon0), (lat1, lon1) = g[0][1], g[-1][1]
            span_m = haversine(lat0, lon0, lat1, lon1)
            tag = "TRAVERSEE probable (court)" if span_m < 40 else "A VERIFIER (long)"
            print(f"    indices {i0}-{i1} ({i1-i0+1} pts, ~{span_m:.0f}m) : {g[0][1]} -> {g[-1][1]}, dist min {min(x[2] for x in g):.1f}m -- {tag}")
    report[fp.name] = violations
    print()

print("=== RESUME ===")
for name, v in report.items():
    print(f"  {name}: {'OK' if not v else f'{len(v)} points suspects'}")
