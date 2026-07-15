"""
Orchestrateur principal : lit input/destinations.csv + input/gpx_sans_vignette/,
calcule l'itineraire "avec vignette" pour chaque destination, profile les deux
itineraires (distance/temps/vitesse/type de route/consommation/CO2/stats
editoriales), exporte GPX+GeoJSON, et ecrit un JSON par destination plus un
fichier agrege output/trajets.json.

Usage : python -m pipeline.build_dataset
Relancable a volonte : ajouter une ligne a destinations.csv + le GPX
correspondant dans gpx_sans_vignette/, puis relancer -- tout est recalcule.
"""
import csv
import sys
import time

from . import config, consumption, gh_client, osm_stats, road_profile
from .gpx_utils import points_to_geojson, read_gpx_points, write_gpx, write_json


def _ensure_dirs():
    for d in (config.OUTPUT_GEOJSON_DIR, config.OUTPUT_GPX_DIR, config.OUTPUT_STATS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _read_destinations():
    with open(config.DESTINATIONS_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _routes_empruntees_badges(profile, label):
    refs = osm_stats.major_refs_used(profile.points)
    if refs is None:
        return None
    if label == "sans":
        # trace normalement 100% communal (cf. brief) : les eventuels refs
        # trouves (typiquement des D-routes francaises, jamais restreintes)
        # sont ajoutes apres le badge "Communales" pour transparence
        return ["Communales"] + refs
    return refs if refs else ["Communales"]


def _leg_dict(profile, label, dest_id):
    conso = consumption.compute_consumption(profile)
    geojson_name = f"{dest_id}_{label}.geojson"
    gpx_name = f"{dest_id}_{label}.gpx"

    geojson_obj = points_to_geojson(profile.points, properties={
        "id": dest_id, "variante": label, "distance_km": round(profile.distance_km, 2),
    })
    write_json(geojson_obj, config.OUTPUT_GEOJSON_DIR / geojson_name)
    write_gpx(profile.points, config.OUTPUT_GPX_DIR / gpx_name, name=f"{dest_id}_{label}")

    return {
        "distance_km": round(profile.distance_km, 2),
        "temps_min": round(profile.time_min, 1) if profile.time_s else None,
        "vitesse_moyenne_kmh": round(profile.avg_speed_kmh, 1) if profile.avg_speed_kmh else None,
        "carburant_l": conso["carburant_l"],
        "cout_carburant_eur": conso["cout_eur"],
        "co2_kg": conso["co2_kg"],
        "distance_urbaine_km": osm_stats.distance_urbaine_km(profile.points),
        "routes_empruntees": _routes_empruntees_badges(profile, label),
        "geojson": f"geojson/{geojson_name}",
        "gpx": f"gpx/{gpx_name}",
        "methode": profile.method,
        "nb_cassures_detectees": profile.n_breaks,
    }


def _delta_dict(avec, sans, analyse_avec=None, analyse_sans=None):
    def d(dict_a, dict_s, key):
        a, s = dict_a.get(key), dict_s.get(key)
        if a is None or s is None:
            return None
        return round(s - a, 2)

    result = {
        "delta_km": d(avec, sans, "distance_km"),
        "delta_temps_min": d(avec, sans, "temps_min"),
        "delta_carburant_l": d(avec, sans, "carburant_l"),
        "delta_cout_eur": d(avec, sans, "cout_carburant_eur"),
        "delta_co2_kg": d(avec, sans, "co2_kg"),
    }
    if analyse_avec and analyse_sans:
        result["delta_villages_traverses"] = d(analyse_avec, analyse_sans, "nb_villages_traverses")
        result["delta_changements_de_route"] = d(analyse_avec, analyse_sans, "nb_changements_de_route")
    return result


def _analyse_dict(profile):
    road_m = osm_stats.road_type_distance_m(profile.points)
    communes = osm_stats.communes_traversees(profile.points)
    villages = osm_stats.villages_traverses(profile.points)
    feux = osm_stats.nombre_feux(profile.points)
    passages_a_niveau = osm_stats.nombre_passages_a_niveau(profile.points)
    t_below, t_above = profile.time_below_above_s(
        config.SPEED_LOW_THRESHOLD_KMH, config.SPEED_HIGH_THRESHOLD_KMH
    )

    def km_for(cat):
        if road_m is None:
            return None
        return round(road_m.get(cat, 0.0) / 1000, 2)

    return {
        "communes_traversees": communes,
        "nb_communes_traversees": len(communes) if communes is not None else None,
        "villages_traverses": villages,
        "nb_villages_traverses": len(villages) if villages is not None else None,
        "nb_giratoires": profile.roundabout_count,
        "nb_changements_de_route": profile.instruction_count,
        "nb_feux": feux,
        "nb_passages_a_niveau": passages_a_niveau,
        "distance_communale_km": km_for("communale"),
        "distance_departementale_km": km_for("departementale"),
        "distance_nationale_regionale_km": km_for("nationale_regionale"),
        "distance_autoroute_km": km_for("autoroute"),
        "distance_ring_km": km_for("ring"),
        "distance_type_inconnu_km": km_for("inconnu") if road_m else None,
        "distance_urbaine_km": osm_stats.distance_urbaine_km(profile.points),  # estimation, cf. README
        "temps_moins_50kmh_min": round(t_below / 60, 1) if profile.speed_segments else None,
        "temps_plus_90kmh_min": round(t_above / 60, 1) if profile.speed_segments else None,
        "vitesse_moyenne_kmh": round(profile.avg_speed_kmh, 1) if profile.avg_speed_kmh else None,
        "vitesse_mediane_kmh": round(profile.median_speed_kmh, 1) if profile.median_speed_kmh else None,
    }


def build_one(dest):
    dest_id = dest["id"]
    nom = dest["nom"]
    depart = (float(dest["latitude_depart"]), float(dest["longitude_depart"]))
    arrivee = (float(dest["latitude"]), float(dest["longitude"]))
    gpx_path = config.GPX_SANS_VIGNETTE_DIR / dest["gpx_filename"]

    print(f"[{dest_id}] lecture GPX sans-vignette ({gpx_path.name})...")
    points_sans = read_gpx_points(gpx_path)
    profile_sans = road_profile.profile_from_gpx_legwise(points_sans)
    if profile_sans.n_breaks:
        print(f"[{dest_id}]   ATTENTION : {profile_sans.n_breaks} cassure(s) detectee(s), cf. stats/{dest_id}.json -> sans.nb_cassures_detectees")

    print(f"[{dest_id}] calcul itineraire avec-vignette (le plus rapide, autoroutes autorisees)...")
    path_avec = gh_client.route([depart, arrivee], config.GH_AVEC_VIGNETTE_URL)
    profile_avec = road_profile.profile_from_single_route(path_avec)

    print(f"[{dest_id}] export GPX/GeoJSON + calcul consommation/CO2...")
    avec = _leg_dict(profile_avec, "avec", dest_id)
    sans = _leg_dict(profile_sans, "sans", dest_id)

    print(f"[{dest_id}] statistiques editoriales OSM (communes/villages/feux/types de route)...")
    analyse_avec = _analyse_dict(profile_avec)
    analyse = _analyse_dict(profile_sans)
    delta = _delta_dict(avec, sans, analyse_avec, analyse)

    etapes = osm_stats.route_steps(
        profile_sans.points, profile_sans.time_min,
        depart_nom=dest["depart"], arrivee_nom=nom,
    )

    result = {
        "id": dest_id,
        "nom": nom,
        "depart": dest["depart"],
        "avec": avec,
        "sans": sans,
        "delta": delta,
        "analyse": analyse,
        "etapes": etapes,
    }
    write_json(result, config.OUTPUT_STATS_DIR / f"{dest_id}.json")
    return result


def main():
    t0 = time.time()
    _ensure_dirs()
    destinations = _read_destinations()
    print(f"{len(destinations)} destinations a traiter\n")

    results = []
    for dest in destinations:
        try:
            results.append(build_one(dest))
        except Exception as e:
            print(f"[{dest['id']}] ECHEC : {e}", file=sys.stderr)
        print()

    write_json(results, config.OUTPUT_TRAJETS_JSON)
    print(f"Termine en {time.time()-t0:.0f}s -> {config.OUTPUT_TRAJETS_JSON} ({len(results)}/{len(destinations)} destinations)")


if __name__ == "__main__":
    main()
