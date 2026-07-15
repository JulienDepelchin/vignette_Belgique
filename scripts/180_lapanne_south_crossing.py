import json
import sys
import urllib.request
import urllib.parse

sys.stdout.reconfigure(encoding="utf-8")

GH_URL = "http://127.0.0.1:8989/route"
LILLE = (50.6367, 3.0635)
LA_PANNE = (51.097367, 2.581506)


def route(points, extra=None):
    params = [("point", f"{lat},{lon}") for lat, lon in points]
    params += [("profile", "car"), ("points_encoded", "false"), ("instructions", "true")]
    if extra:
        params += extra
    url = GH_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": json.loads(e.read().decode()).get("message")}


print("=== Direct Lille -> La Panne ===")
data = route([LILLE, LA_PANNE])
if "error" in data:
    print("ECHEC:", data["error"])
else:
    p = data["paths"][0]
    print(f"{p['distance']/1000:.2f} km, {p['time']/60000:.0f} min")
    for instr in p.get("instructions", []):
        print(" -", instr["text"])

print("\n=== Alternatives Lille -> La Panne ===")
data2 = route([LILLE, LA_PANNE], extra=[
    ("algorithm", "alternative_route"),
    ("alternative_route.max_paths", "5"),
    ("alternative_route.max_weight_factor", "3.0"),
    ("alternative_route.max_share_factor", "0.5"),
])
if "error" in data2:
    print("ECHEC:", data2["error"])
else:
    for i, p in enumerate(data2["paths"]):
        km = p["distance"] / 1000
        minutes = p["time"] / 60000
        coords = p["points"]["coordinates"]
        # trouve le point le plus au sud proche de la frontiere (min lat parmi les points > lon 2.4)
        print(f"\nOption {i+1}: {km:.2f} km, {minutes:.0f} min, {len(coords)} points")
        for instr in p.get("instructions", [])[:15]:
            print("  -", instr["text"])
