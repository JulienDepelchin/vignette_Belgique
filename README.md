# Pipeline vignette-belgique — comparateur avec/sans vignette

Pipeline entièrement automatisé qui, à partir d'itinéraires "sans vignette" (routes
communales uniquement, vérifiés et corrigés à la main) génère l'itinéraire "avec
vignette" équivalent (le plus rapide, autoroutes/nationales autorisées), calcule
toutes les statistiques comparables entre les deux, et produit un jeu de données
JSON/GeoJSON/GPX prêt à l'emploi pour un article ou un comparateur.

Aucune interface web n'est produite : uniquement des fichiers de données.

## Reproductibilité

```
python -m pipeline.build_dataset
```

Pour ajouter ou modifier une destination : ajouter/éditer une ligne dans
`input/destinations.csv`, déposer le GPX correspondant dans
`input/gpx_sans_vignette/`, relancer la commande — tout est recalculé, rien n'est
mis en cache entre deux exécutions (hormis les couches OSM auxiliaires
pré-extraites, cf. plus bas).

## Prérequis

- Python 3, bibliothèques : `geopandas`, `shapely` (voir aussi `osmium` pour la
  pré-extraction des couches OSM, section suivante).
- Deux instances **GraphHopper** locales doivent tourner :
  - `http://127.0.0.1:8989` — graphe **restreint** (communal uniquement côté
    belge, réseau français libre) — sert uniquement à profiler les itinéraires
    "sans vignette" segment par segment (cf. méthode ci-dessous), pas à générer
    l'itinéraire "avec vignette".
  - `http://127.0.0.1:8991` — graphe **libre** (autoroutes/nationales
    autorisées) — sert à calculer l'itinéraire "avec vignette".

  Les URLs sont configurables dans `pipeline/config.py`.

## Choix technique : GraphHopper

Le brief demandait de choisir entre OpenRouteService, GraphHopper ou Valhalla.
**GraphHopper** a été retenu :

- déjà déployé, validé et corrigé sur ce projet (classification officielle
  régionale/communale injectée via tag `motor_vehicle=no`, cf.
  `brief_vignette_belgique.md` pour l'historique complet de la méthodologie et
  des incidents corrigés) — repartir d'OpenRouteService ou Valhalla aurait
  demandé de refaire tout ce travail de A à Z sans bénéfice évident ;
  - fonctionne en local (portable, sans droits admin, cf. contrainte
    d'environnement), donc reproductible sans dépendance à un service tiers
    limité en quota (contrairement à l'API publique OpenRouteService) ;
- expose nativement les `path details` nécessaires (`road_class`,
  `average_speed`, `roundabout`) utilisés pour les statistiques éditoriales et
  le modèle de consommation.

## Arborescence

```
input/
  destinations.csv
  gpx_sans_vignette/*.gpx
output/
  geojson/       *_avec.geojson, *_sans.geojson
  gpx/           *_avec.gpx, *_sans.gpx
  stats/         {id}.json (un fichier par destination)
  trajets.json   agrégat de toutes les destinations
data/
  osm_communes.gpkg, osm_places.gpkg, osm_traffic_signals.gpkg, osm_roads.gpkg
  (couches auxiliaires pré-extraites du PBF fusionné, cf. scripts/300-302_*.py
  — à régénérer uniquement si le PBF source change, pas à chaque run)
pipeline/
  config.py         constantes et hypothèses (prix carburant, CO2, courbe conso...)
  gh_client.py       client HTTP GraphHopper
  gpx_utils.py        lecture/écriture GPX, conversion GeoJSON, haversine
  road_profile.py     construit un "profil" (distance/temps/vitesse/type de route) à partir d'une réponse GraphHopper
  consumption.py       modèle de consommation/CO2
  osm_stats.py          statistiques éditoriales (communes, villages, feux, type de route)
  build_dataset.py       orchestrateur principal
```

## destinations.csv

Colonnes : `id, nom, latitude, longitude, depart, latitude_depart,
longitude_depart, gpx_filename`.

`gpx_filename` est un ajout au schéma demandé, nécessaire pour faire
correspondre sans ambiguïté chaque ligne à son fichier GPX (les noms de
fichiers ne suivent pas tous exactement la même convention que `id`).

## Méthode, destination par destination

### 1. Itinéraire "avec vignette"

Une seule requête `/route` vers le graphe libre (port 8991), profil `car`,
sans contrainte — GraphHopper renvoie directement le chemin le plus rapide
(autoroutes/nationales autorisées). Aucune ambiguïté : c'est un calcul de
zéro, pas un rapprochement d'un tracé existant.

### 2. Itinéraire "sans vignette"

Le GPX est déjà le résultat d'une vérification manuelle (cf.
`brief_vignette_belgique.md` §8) — on ne le recalcule pas, on le **profile**.

**Problème rencontré et méthode retenue** : un rapprochement automatique
(map-matching GraphHopper `/match`, ou un routage multi-points forçant le
passage par tous les points du tracé) s'est montré peu fiable sur des tracés
dessinés/édités à la main dans gpx.studio. Exemple concret observé sur
Famiflora : un micro-passage de ~20 m près de l'arrivée, imprécis de
quelques mètres par rapport au réseau routable réel, faisait calculer un
détour de 11 km par l'algorithme — alors que sur le terrain, il n'y a aucun
problème.

**Solution** (`pipeline/road_profile.profile_from_gpx_legwise`) :
1. Le tracé est échantillonné tous les `N` points (`config.SAMPLE_EVERY_N_POINTS`,
   8 par défaut).
2. Chaque segment entre deux points échantillonnés est routé individuellement
   sur le graphe restreint (port 8989).
3. Si la distance routée dépasse fortement la distance directe (à la fois en
   ratio et en valeur absolue — seuils `BREAK_RATIO_THRESHOLD` /
   `BREAK_ABS_THRESHOLD_M`), le segment est classé "cassure" : sa distance
   directe est comptée dans la distance totale (dans le bucket de type de
   route `non_classifie`), mais il n'alimente pas les statistiques de vitesse
   — pour ne pas polluer le calcul avec un détour de contournement qui ne
   représente pas la conduite réelle prévue.
4. La **distance totale** retenue est toujours la longueur réelle du tracé
   dessiné (somme des segments GPX bruts) — c'est la mesure la plus fiable,
   indépendante de tout rapprochement automatique.
5. Le **temps total** est estimé en appliquant la vitesse moyenne mesurée sur
   les segments "propres" à la distance totale réelle.

Chaque fichier `stats/{id}.json` indique `sans.nb_cassures_detectees` : un
nombre > 0 signale un point du tracé à revérifier visuellement en priorité
(cf. `brief_vignette_belgique.md` §8 pour la liste déjà identifiée avant ce
pipeline).

### 3. Distance / temps / vitesse

- `distance_km` : longueur réelle du tracé (les deux méthodes, cf. ci-dessus).
- `temps_min` : mesuré directement pour "avec vignette" (une seule requête),
  estimé par extrapolation de vitesse pour "sans vignette" (cf. ci-dessus).
- `vitesse_moyenne_kmh` = distance / temps.
- `vitesse_mediane_kmh` (dans `analyse`) : médiane pondérée par distance des
  vitesses de segment (`average_speed` renvoyé par GraphHopper), calculée
  uniquement sur les portions "propres" (hors cassures).

### 4-5. Modèle de consommation, CO2, coût

**Ce n'est pas le logiciel COPERT officiel.** COPERT (COmputer Programme to
calculate Emissions from Road Transport) est le modèle de référence européen
(Agence européenne pour l'environnement / EMISIA), mais son usage complet
nécessite des jeux de coefficients spécifiques par catégorie de véhicule et
norme Euro, non librement redistribuables. Ce pipeline utilise une **courbe
simplifiée inspirée de la forme générale des courbes COPERT** vitesse →
consommation pour une voiture particulière essence "moyenne" :

| Vitesse (km/h) | Conso (L/100km) |
|---|---|
| 0-10 | 11,5 → 10,5 (conduite hachée, ville dense) |
| 20-40 | 9,2 → 7,1 |
| 50-70 | 6,4 → 5,7 (zone la plus efficiente) |
| 80-100 | 5,8 → 6,5 |
| 110-130 | 7,0 → 8,3 (remontée : traînée aérodynamique) |

(table complète et interpolée linéairement entre points, `pipeline/config.py`
→ `COPERT_CONSO_L100`). Ce comportement en U (forte conso en ville, optimum
vers 60-80 km/h, remontée sur autoroute) est bien documenté dans la
littérature COPERT/EEA ; les valeurs numériques exactes sont calibrées à la
main sur des ordres de grandeur ADEME/EEA usuels, **pas issues d'une
régression sur les données COPERT brutes**.

**Différence clé avec une hypothèse "consommation fixe"** : la courbe est
appliquée **segment par segment**, à partir des vitesses réelles renvoyées par
GraphHopper (`average_speed` path detail) pour chaque tronçon du trajet — un
trajet avec plus de portions à 30 km/h en ville aura mécaniquement une
consommation par km plus élevée qu'un trajet à 70 km/h de moyenne, même à
distance égale.

**CO2** : `carburant_l × facteur_kg_par_L`. Facteur essence = 2,31 kgCO2/L
(combustion directe, hors amont production — source : standard ADEME Base
Carbone / EEA). Configurable dans `config.CO2_FACTOR_KG_PER_L` (une valeur
diesel 2,51 est aussi fournie si besoin).

**Coût** : `carburant_l × prix_eur_l`. Prix par défaut 1,75 €/L
(`config.PRIX_CARBURANT_EUR_L`) — **hypothèse éditoriale à ajuster au prix du
jour**, ce n'est pas une donnée mesurée.

**Segments non classifiés (cassures)** : reçoivent la vitesse moyenne globale
du trajet comme repli pour le calcul de consommation (faute de vitesse réelle
mesurée à cet endroit). Le champ `part_distance_avec_vitesse_mesuree_pct`
(non exposé dans le JSON final mais calculable via `pipeline.consumption`)
indique la part du trajet couverte par une vitesse réellement mesurée.

### 6. Deltas

`delta_km`, `delta_temps_min`, `delta_carburant_l`, `delta_cout_eur`,
`delta_co2_kg` = valeur **sans vignette − avec vignette** (donc positif = coût
supplémentaire pour éviter la vignette).

### 7. Statistiques éditoriales (`analyse`)

Calculées sur l'itinéraire **sans vignette** (le sujet principal du
comparateur). Toute statistique non calculable de façon fiable est à `null`.

| Statistique | Source | Fiabilité |
|---|---|---|
| `nb_communes_traversees` / `communes_traversees` | polygones `admin_level=8` extraits du PBF fusionné (`data/osm_communes.gpkg`) | Bonne — seuil de chevauchement mini `COMMUNE_MIN_OVERLAP_M` (30 m) pour éviter de compter une commune juste effleurée |
| `nb_villages_traverses` / `villages_traverses` | nœuds OSM `place=village/hamlet/town/city` à moins de 300 m du tracé | Approximative — un nœud `place` proche ne garantit pas que la route traverse le centre du village |
| `nb_giratoires` | path detail `roundabout` de GraphHopper | Bonne, sur les segments routés (pas sur les cassures) |
| `nb_changements_de_route` | nombre d'instructions de navigation GraphHopper (proxy pour les intersections/changements de direction) | Approximative — dépend de la granularité de génération d'instructions de GraphHopper, pas un vrai comptage d'intersections cartographiques |
| `nb_feux` | nœuds OSM `highway=traffic_signals` à moins de 20 m du tracé | Bonne si OSM est à jour localement |
| `distance_communale/departementale/nationale_regionale/autoroute_km` | classification du `ref` OSM du tronçon le plus proche (préfixe A/N/D, repli sur `highway` si pas de ref) | **Limite importante** : le préfixe `N` recouvre à la fois les routes nationales françaises et les routes régionales belges (deux systèmes administratifs différents) — regroupées ici sous `nationale_regionale` faute de distinction fiable par le seul `ref`. Ne pas confondre avec la classification "soumis à vignette" du projet (PICC/Wegenregister), qui est une source différente et plus fiable pour la Belgique (cf. `brief_vignette_belgique.md`). **`distance_autoroute_km` peut être non nul même sur le trajet "sans vignette"** : seul le réseau régional/communal **belge** est restreint dans ce projet, le réseau français reste libre de circulation (cf. brief §7) — un trajet qui utilise une autoroute française avant la frontière (ex. Pairi Daiza) est donc normal, pas une erreur |
| `distance_urbaine_km` | — | **Toujours `null`** : aucune couche de zones urbaines/agglomération fiable n'est disponible dans ce pipeline (les polygones `landuse` OSM sont trop incomplets pour ce niveau de précision). À ajouter si une source adaptée est trouvée (ex. couches IGN/AGIV) |
| `temps_moins_50kmh_min` / `temps_plus_90kmh_min` | intégration de `average_speed` sur les segments propres | Bonne sur la part mesurée du trajet |
| `vitesse_moyenne_kmh` / `vitesse_mediane_kmh` | cf. section 3 | Bonne |

## Limites méthodologiques générales

- **Origine unique (Lille, Grand-Place)** pour tous les calculs "avec
  vignette" — un point de départ éditorial parmi d'autres possibles (Douai,
  Valenciennes, Dunkerque donneraient des chiffres différents), cf.
  `brief_vignette_belgique.md`.
- Le tracé "sans vignette" de **Pairi Daiza** contient encore, au moment de la
  rédaction de ce README, un passage réel par une route régionale (N504,
  village de Wiers, ~170 m) identifié mais pas encore corrigé — les chiffres
  associés à cette destination sont donc à considérer comme provisoires tant
  que le tracé n'a pas été repris (cf. `brief_vignette_belgique.md` §8).
- Le texte juridique définitif de la vignette n'étant pas publié au moment de
  ce travail, l'ensemble de la méthodologie (quelles routes seront réellement
  soumises) reste sujet à ajustement.
- Le modèle de consommation est une approximation illustrative, pas une mesure
  embarquée réelle (consommation constructeur, style de conduite, météo,
  charge du véhicule, etc. non pris en compte).

## Précision attendue

- Distances : ±quelques % (mesure directe des tracés, fiable).
- Temps : ±10-20 % (extrapolation de vitesse moyenne sur "sans vignette" ;
  mesure directe donc plus fiable sur "avec vignette").
- Consommation/CO2/coût : ordre de grandeur éditorial, pas une mesure
  scientifique — à présenter avec les hypothèses explicitement mentionnées
  (prix du carburant, modèle de consommation simplifié).
- Statistiques éditoriales : cf. tableau ci-dessus, fiabilité variable par
  statistique, toujours vérifiables à la main via les GeoJSON exportés.
