"""
Modele de consommation carburant et d'emissions CO2, inspire de la forme
generale des courbes COPERT (vitesse -> consommation). Voir README.md pour la
methodologie complete, les sources et les limites.

Ce n'est PAS une implementation du logiciel COPERT officiel (coefficients
sous licence EEA/EMISIA specifiques par categorie de vehicule/norme Euro) --
c'est une courbe simplifiee qui en reproduit le comportement qualitatif
(surconsommation en ville / optimum vers 60-80 km/h / remontee autoroute),
appliquee segment par segment a partir des vitesses reelles renvoyees par le
moteur de routage (et non une consommation moyenne fixe unique).
"""
from . import config


def speed_to_conso_l100(speed_kmh):
    """Interpolation lineaire dans la table config.COPERT_CONSO_L100."""
    table = sorted(config.COPERT_CONSO_L100.items())
    if speed_kmh <= table[0][0]:
        return table[0][1]
    if speed_kmh >= table[-1][0]:
        return table[-1][1]
    for (s0, c0), (s1, c1) in zip(table, table[1:]):
        if s0 <= speed_kmh <= s1:
            t = (speed_kmh - s0) / (s1 - s0)
            return c0 + t * (c1 - c0)
    return table[-1][1]


def compute_consumption(profile, carburant_type=None, price_eur_l=None):
    """
    profile : road_profile.RouteProfile
    Integre la courbe vitesse->consommation segment par segment sur les
    portions ou la vitesse reelle est connue (profile.speed_segments). Pour le
    reste de la distance (cassures/segments non classifies, cf.
    road_profile.profile_from_gpx_legwise), applique la vitesse moyenne globale
    du trace comme repli -- documente via 'part_distance_classifiee_vitesse_pct'
    dans le resultat pour transparence.
    """
    carburant_type = carburant_type or config.CARBURANT_TYPE
    price = price_eur_l if price_eur_l is not None else config.PRIX_CARBURANT_EUR_L
    co2_factor = config.CO2_FACTOR_KG_PER_L[carburant_type]

    total_l = 0.0
    classified_m = 0.0
    for dist_m, speed_kmh in profile.speed_segments:
        conso_l100 = speed_to_conso_l100(speed_kmh)
        total_l += (dist_m / 1000) * conso_l100 / 100
        classified_m += dist_m

    remainder_m = max(0.0, profile.distance_m - classified_m)
    if remainder_m > 0:
        fallback_speed = profile.avg_speed_kmh or 50
        conso_l100 = speed_to_conso_l100(fallback_speed)
        total_l += (remainder_m / 1000) * conso_l100 / 100

    co2_kg = total_l * co2_factor
    cout_eur = total_l * price
    pct_classifie = round(100 * classified_m / profile.distance_m, 1) if profile.distance_m else None

    return {
        "carburant_l": round(total_l, 2),
        "co2_kg": round(co2_kg, 2),
        "cout_eur": round(cout_eur, 2),
        "carburant_type": carburant_type,
        "prix_eur_l": price,
        "co2_factor_kg_l": co2_factor,
        "part_distance_avec_vitesse_mesuree_pct": pct_classifie,
    }
