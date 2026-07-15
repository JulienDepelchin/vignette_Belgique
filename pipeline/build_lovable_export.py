"""
Construit un export de donnees autonome, pret a etre commite dans un repo
consomme par une app Lovable (aucune interface generee ici -- uniquement des
fichiers de donnees organises).

Lit output/trajets.json (deja produit par `python -m pipeline.build_dataset`)
et les GeoJSON associes, et ecrit dans output/lovable/ :

  destinations.json     -- tableau leger pour la grille de cartes
  details/{id}.json      -- fiche detail complete par destination (reprend
                             stats/{id}.json + un tableau 'resume_delta' pret
                             a afficher pour la ligne d'icones "ce que change
                             l'absence de vignette")
  geo/{id}_avec.geojson    -- copie des traces (self-contained, pas de lien
  geo/{id}_sans.geojson       vers output/geojson/ a maintenir separement)
  README.md               -- description du schema pour prompter Lovable

Usage : python -m pipeline.build_lovable_export
(a lancer apres build_dataset -- ne relance aucun calcul, juste une mise en
forme/reorganisation des resultats deja produits)
"""
import json
import shutil

from . import config

OUT_LOVABLE = config.OUTPUT_DIR / "lovable"
OUT_DETAILS = OUT_LOVABLE / "details"
OUT_GEO = OUT_LOVABLE / "geo"


def _bbox_from_geojson(path):
    obj = json.loads(path.read_text(encoding="utf-8"))
    coords = obj["geometry"]["coordinates"]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return [min(lons), min(lats), max(lons), max(lats)]


def _resume_delta(d):
    """Liste prete a afficher pour la ligne d'icones 'ce que change l'absence
    de vignette' (mockup : +49 km / +55 min / +4.7 L / +6.30 EUR / +11.2 kg
    CO2 / +17 villages / +63 carrefours)."""
    delta = d["delta"]
    items = [
        {"cle": "distance", "label": "de distance", "valeur": delta["delta_km"], "unite": "km"},
        {"cle": "temps", "label": "de trajet", "valeur": delta["delta_temps_min"], "unite": "min"},
        {"cle": "carburant", "label": "de carburant", "valeur": delta["delta_carburant_l"], "unite": "L"},
        {"cle": "cout", "label": "de carburant", "valeur": delta["delta_cout_eur"], "unite": "EUR"},
        {"cle": "co2", "label": "de CO2 emis", "valeur": delta["delta_co2_kg"], "unite": "kg"},
    ]
    if delta.get("delta_villages_traverses") is not None:
        items.append({"cle": "villages", "label": "villages traverses",
                       "valeur": delta["delta_villages_traverses"], "unite": ""})
    if delta.get("delta_changements_de_route") is not None:
        items.append({"cle": "carrefours", "label": "carrefours",
                       "valeur": delta["delta_changements_de_route"], "unite": ""})
    return items


def main():
    OUT_DETAILS.mkdir(parents=True, exist_ok=True)
    OUT_GEO.mkdir(parents=True, exist_ok=True)

    trajets = json.loads(config.OUTPUT_TRAJETS_JSON.read_text(encoding="utf-8"))
    print(f"{len(trajets)} destinations a exporter pour Lovable")

    cards = []
    for d in trajets:
        dest_id = d["id"]

        # copie des GeoJSON dans le dossier autonome
        for label in ("avec", "sans"):
            src = config.OUTPUT_DIR / d[label]["geojson"]
            dst = OUT_GEO / src.name
            shutil.copy(src, dst)

        bbox_avec = _bbox_from_geojson(config.OUTPUT_GEOJSON_DIR / f"{dest_id}_avec.geojson")
        bbox_sans = _bbox_from_geojson(config.OUTPUT_GEOJSON_DIR / f"{dest_id}_sans.geojson")
        bbox = [
            min(bbox_avec[0], bbox_sans[0]), min(bbox_avec[1], bbox_sans[1]),
            max(bbox_avec[2], bbox_sans[2]), max(bbox_avec[3], bbox_sans[3]),
        ]

        card = {
            "id": dest_id,
            "nom": d["nom"],
            "depart": d["depart"],
            "avec": {"temps_min": d["avec"]["temps_min"], "distance_km": d["avec"]["distance_km"]},
            "sans": {"temps_min": d["sans"]["temps_min"], "distance_km": d["sans"]["distance_km"]},
            "delta_km": d["delta"]["delta_km"],
            "delta_temps_min": d["delta"]["delta_temps_min"],
            "bbox": bbox,
        }
        cards.append(card)

        detail = dict(d)  # copie
        detail["bbox"] = bbox
        detail["geo"] = {
            "avec": f"geo/{dest_id}_avec.geojson",
            "sans": f"geo/{dest_id}_sans.geojson",
        }
        detail["resume_delta"] = _resume_delta(d)
        detail["prix_vignette_eur_an"] = config.PRIX_VIGNETTE_EUR_AN
        (OUT_DETAILS / f"{dest_id}.json").write_text(
            json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    (OUT_LOVABLE / "destinations.json").write_text(
        json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Export termine -> {OUT_LOVABLE}")


if __name__ == "__main__":
    main()
