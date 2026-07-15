import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("d:/vignette_belgique/scripts/tmp_robust_results.json", encoding="utf-8") as f:
    robust = json.load(f)
with open("d:/vignette_belgique/scripts/tmp_comparatif_results.json", encoding="utf-8") as f:
    comp = json.load(f)
comp_by_name = {c["name"]: c for c in comp}

CONSO_L100 = 6.5  # hypothese moyenne, essence, tous types de route confondus
PRIX_L = 1.75  # eur/L, hypothese

rows = []
for name, r in robust.items():
    c = comp_by_name.get(name)
    km_free = r["raw_km"]
    min_free = r["time_est_min"]
    km_norm = c["km_norm"]
    min_norm = c["min_norm"]
    delta_km = km_free - km_norm  # surcout (km) pour eviter la vignette
    delta_min = min_free - min_norm  # surcout (min) pour eviter la vignette
    conso_free_l = km_free * CONSO_L100 / 100
    conso_norm_l = km_norm * CONSO_L100 / 100
    delta_conso_l = conso_free_l - conso_norm_l
    delta_cout = delta_conso_l * PRIX_L
    rows.append({
        "name": name, "km_free": km_free, "min_free": min_free,
        "km_norm": km_norm, "min_norm": min_norm,
        "delta_km": delta_km, "delta_min": delta_min,
        "n_breaks": r["n_breaks"],
        "conso_free_l": conso_free_l, "conso_norm_l": conso_norm_l,
        "delta_conso_l": delta_conso_l, "delta_cout_eur": delta_cout,
    })

print(f"{'Lieu':<20} {'km SV':>7} {'min SV':>7} {'km AV':>7} {'min AV':>7} {'d_km':>7} {'d_min':>7} {'d_L':>6} {'d_EUR':>6} {'cassures':>8}")
for row in rows:
    print(f"{row['name']:<20} {row['km_free']:>7.1f} {row['min_free']:>7.0f} {row['km_norm']:>7.1f} {row['min_norm']:>7.0f} "
          f"{row['delta_km']:>+7.1f} {row['delta_min']:>+7.0f} {row['delta_conso_l']:>+6.1f} {row['delta_cout_eur']:>+6.1f} {row['n_breaks']:>8}")

with open("d:/vignette_belgique/scripts/tmp_final_table.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)
