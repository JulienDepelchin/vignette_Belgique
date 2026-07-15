"""
Calcule une distance/temps robuste par trace finale, segment par segment
(sous-echantillonnage), en detectant les "cassures" locales (portion du trace
dessine a la main qui ne correspond a aucun chemin communal court reel) plutot
que de faire confiance aveuglement au map-matching ou a un routage multi-points
d'un coup (les deux se sont montres fragiles sur Famiflora : un micro-passage
pres de l'arrivee force un detour de ~11km au lieu de quelques metres).
"""
import json
import re
import sys
import urllib.request
import urllib.parse
from math import radians, sin, cos, asin, sqrt
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

TRKPT_RE = re.compile(r'<trkpt lat="([\-\d.]+)" lon="([\-\d.]+)"')
GH_URL = "http://127.0.0.1:8989/route"
TRACES_DIR = Path("d:/vignette_belgique/data/traces_finales_definitives")
SAMPLE_EVERY = 8
BREAK_RATIO = 3.0
BREAK_ABS_M = 300


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
    return 2 * R * asin(sqrt(a))


def route_leg(pt1, pt2):
    params = [("point", f"{pt1[0]},{pt1[1]}"), ("point", f"{pt2[0]},{pt2[1]}"),
              ("profile", "car"), ("points_encoded", "false")]
    url = GH_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.load(r)
        p = data["paths"][0]
        return p["distance"], p["time"]
    except Exception:
        return None, None


results = {}
for fp in sorted(TRACES_DIR.glob("*.gpx")):
    text = fp.read_text(encoding="utf-8")
    pts = [(float(lat), float(lon)) for lat, lon in TRKPT_RE.findall(text)]
    raw_km = sum(haversine(*pts[i], *pts[i + 1]) for i in range(len(pts) - 1)) / 1000

    sample = pts[::SAMPLE_EVERY]
    if sample[-1] != pts[-1]:
        sample.append(pts[-1])

    clean_dist_m = 0.0
    clean_time_ms = 0
    breaks = []
    for i in range(len(sample) - 1):
        p1, p2 = sample[i], sample[i + 1]
        direct = haversine(*p1, *p2)
        d, t = route_leg(p1, p2)
        is_break = d is None or (d - direct > BREAK_ABS_M and direct > 5 and d / direct > BREAK_RATIO)
        if is_break:
            breaks.append((i, p1, p2, direct, d))
            continue
        clean_dist_m += d
        clean_time_ms += t

    avg_speed_kmh = (clean_dist_m / 1000) / (clean_time_ms / 3600000) if clean_time_ms else None
    time_est_min = (raw_km / avg_speed_kmh) * 60 if avg_speed_kmh else None

    results[fp.stem] = {
        "raw_km": raw_km, "avg_speed_kmh": avg_speed_kmh, "time_est_min": time_est_min,
        "n_breaks": len(breaks), "breaks": [(i, p1, p2, direct, d) for i, p1, p2, direct, d in breaks],
    }
    print(f"{fp.stem}: distance={raw_km:.2f}km  vitesse moy. (segments propres)={avg_speed_kmh:.1f}km/h  temps estime={time_est_min:.1f}min  cassures={len(breaks)}")
    for i, p1, p2, direct, d in breaks:
        dstr = f"{d:.0f}m" if d else "ECHEC"
        print(f"    [{i}] {p1} -> {p2} : direct={direct:.0f}m route={dstr}")
    print()

with open("d:/vignette_belgique/scripts/tmp_robust_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("sauvegarde -> scripts/tmp_robust_results.json")
