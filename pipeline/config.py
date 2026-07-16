"""
Configuration centrale du pipeline vignette-belgique.

Toutes les hypotheses de calcul (prix carburant, facteur CO2, courbe de
consommation) sont ici, avec leurs sources, pour etre facilement ajustables
et documentees en un seul endroit. Voir README.md pour le detail methodologique.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Arborescence
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
DESTINATIONS_CSV = INPUT_DIR / "destinations.csv"
GPX_SANS_VIGNETTE_DIR = INPUT_DIR / "gpx_sans_vignette"

# Base pour les URLs absolues des assets exposes a Lovable (images, GeoJSON).
# Des chemins relatifs ("previews/x.png") laissent Lovable deviner par
# rapport a quoi les resoudre -- souvent mal, d'ou des images qui ne
# s'affichent pas. Des URLs absolues completes eliminent cette ambiguite.
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/JulienDepelchin/vignette_Belgique/main/output/lovable"

OUTPUT_DIR = ROOT / "output"
OUTPUT_GEOJSON_DIR = OUTPUT_DIR / "geojson"
OUTPUT_GPX_DIR = OUTPUT_DIR / "gpx"
OUTPUT_STATS_DIR = OUTPUT_DIR / "stats"
OUTPUT_TRAJETS_JSON = OUTPUT_DIR / "trajets.json"

DATA_DIR = ROOT / "data"
OSM_COMMUNES_GPKG = DATA_DIR / "osm_communes.gpkg"
OSM_PLACES_GPKG = DATA_DIR / "osm_places.gpkg"
OSM_TRAFFIC_SIGNALS_GPKG = DATA_DIR / "osm_traffic_signals.gpkg"
OSM_ROADS_GPKG = DATA_DIR / "osm_roads.gpkg"
OSM_LEVEL_CROSSINGS_GPKG = DATA_DIR / "osm_level_crossings.gpkg"

# ---------------------------------------------------------------------------
# Moteur de routage : GraphHopper (choisi car deja deploye et valide sur ce
# projet -- cf. README section "Choix technique" pour la justification face
# a OpenRouteService/Valhalla)
# ---------------------------------------------------------------------------
GH_SANS_VIGNETTE_URL = "http://127.0.0.1:8989/route"  # graphe restreint (communal only, cote belge)
GH_AVEC_VIGNETTE_URL = "http://127.0.0.1:8991/route"  # graphe libre (autoroutes/nationales autorisees)
GH_PROFILE = "car"
GH_TIMEOUT_S = 30

# Sous-echantillonnage + detection de "cassures" pour profiler un trace dessine
# a la main (cf. README section "Limites methodologiques") : un trace GPX
# dessine/edite manuellement ne correspond pas toujours exactement a un
# cheminement routable court entre deux points consecutifs (edition
# approximative dans gpx.studio, ou vrai micro-trou de connectivite). On
# echantillonne le trace puis on route chaque segment ; un segment route est
# considere comme une "cassure" (donc exclu des stats de type de route/vitesse,
# mais sa distance reelle est quand meme comptee dans la distance totale) si :
SAMPLE_EVERY_N_POINTS = 8
BREAK_RATIO_THRESHOLD = 3.0   # route/direct > ce ratio...
BREAK_ABS_THRESHOLD_M = 300   # ...ET route - direct > ce seuil absolu (m)

# ---------------------------------------------------------------------------
# Tolerances de jointure spatiale (metres, calcul en EPSG:31370 Lambert 72)
# ---------------------------------------------------------------------------
ROAD_REF_JOIN_TOLERANCE_M = 15
COMMUNE_MIN_OVERLAP_M = 30        # longueur min. de trace dans une commune pour la compter "traversee"
VILLAGE_PROXIMITY_M = 300         # distance max. noeud 'place' <-> trace pour compter le village comme traverse
TRAFFIC_SIGNAL_BUFFER_M = 20      # distance max. feu <-> trace
LEVEL_CROSSING_BUFFER_M = 20      # distance max. passage a niveau <-> trace

# Rayon (m) approximatif de la zone "urbaine" autour d'un noeud 'place', par
# type -- sert a estimer 'distance_urbaine_km' (cf. README : ceci est une
# approximation faute de couche de zones baties fiable, PAS une mesure).
URBAN_BUFFER_M_BY_PLACE_TYPE = {
    "hamlet": 150, "suburb": 500, "village": 350, "town": 700, "city": 1500,
}

# Badge "routes empruntees" : un ref n'est liste que s'il totalise au moins
# cette distance (km) sur le trajet, pour eviter de lister des tronçons
# anecdotiques
MAJOR_REF_MIN_KM = 1.0

# Heure de depart par defaut pour le calcul des horaires d'etape (etapes.json)
DEPART_HEURE_DEFAUT = "08:00"

# Prix de la vignette -- tarifs communiques par l'utilisateur (a sourcer
# formellement -- reference officielle a joindre avant publication, cf.
# skill verif-data). Tarif annuel selon la classe d'emission du vehicule
# (equivalence Crit'Air) ; tarif journalier idem mais seuls les tarifs
# "zero emission" et "Crit'Air 4/5" ont ete communiques explicitement -- la
# valeur "critair_3" journaliere est interpolee lineairement a partir du
# ratio annuel (100/125 = 0.8) et n'est PAS confirmee : gardee a None tant
# qu'elle n'est pas verifiee, plutot que presentee comme un chiffre officiel.
PRIX_VIGNETTE = {
    "devise": "EUR",
    "annuel": {
        "zero_emission": 90,
        "critair_3": 100,
        "critair_4_5": 125,
    },
    "journalier": {
        "zero_emission": 8.10,
        "critair_3": None,  # non communique explicitement, cf. note ci-dessus
        "critair_4_5": 11.25,
    },
    "source": None,  # a completer : reference officielle avant publication
}

# ---------------------------------------------------------------------------
# Seuils de vitesse pour les statistiques (km/h)
# ---------------------------------------------------------------------------
SPEED_LOW_THRESHOLD_KMH = 50
SPEED_HIGH_THRESHOLD_KMH = 90

# ---------------------------------------------------------------------------
# Hypotheses economiques (configurables, cf. README)
# ---------------------------------------------------------------------------
# Prix constate le 16/07/2026 (moyenne France, source : releve utilisateur --
# prix carburant tres volatil, a rafraichir regulierement avant publication,
# ne pas laisser cette valeur figee des mois).
PRIX_CARBURANT_EUR_L_PAR_TYPE = {
    "essence": 1.943,  # SP95-E10
    "diesel": 2.016,
}
PRIX_CARBURANT_EUR_L = PRIX_CARBURANT_EUR_L_PAR_TYPE["essence"]
CO2_FACTOR_KG_PER_L = {
    # Source : facteurs d'emission standard combustion carburant (ADEME Base Carbone / EEA) :
    # essence (SP95/E10) ~2.31 kgCO2/L, diesel ~2.51-2.68 kgCO2/L selon la reference.
    "essence": 2.31,
    "diesel": 2.51,
}
CARBURANT_TYPE = "essence"

# ---------------------------------------------------------------------------
# Modele de consommation inspire de COPERT (cf. README section "Modele de
# consommation" pour la methodologie complete et ses limites)
# ---------------------------------------------------------------------------
# NB : ceci n'est PAS le logiciel COPERT officiel (qui necessite des jeux de
# coefficients specifiques par categorie de vehicule/norme Euro, sous licence
# EEA/EMISIA). C'est une approximation inspiree de la forme generale des
# courbes COPERT vitesse -> consommation pour une voiture particuliere
# essence "moyenne" (mix de normes Euro), qui reproduit le comportement bien
# documente : surconsommation a basse vitesse (conduite hachee, ville),
# optimum autour de 60-80 km/h, legere remontee sur autoroute (trainee
# aerodynamique). Coefficients calibres a la main sur des ordres de grandeur
# ADEME/EEA usuels (pas de regression sur donnees COPERT brutes).
COPERT_CONSO_L100 = {
    # borne_min_vitesse_kmh: consommation (L/100km) pour une conduite a cette vitesse
    0: 11.5,
    10: 10.5,
    20: 9.2,
    30: 8.0,
    40: 7.1,
    50: 6.4,
    60: 5.9,
    70: 5.7,
    80: 5.8,
    90: 6.1,
    100: 6.5,
    110: 7.0,
    120: 7.6,
    130: 8.3,
}
