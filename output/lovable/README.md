# Donnees pour l'app Lovable "Sans vignette"

Jeu de donnees statique, autonome (pas de dependance a une API backend),
genere par `python -m pipeline.build_dataset` puis `python -m
pipeline.build_lovable_export`. A committer tel quel dans le repo (ou dans
`public/data/` de l'app Lovable une fois generee).

## Fichiers

- **`destinations.json`** — tableau leger pour la grille de cartes (page
  d'accueil). Un objet par destination :
  ```json
  {
    "id": "pairi_daiza",
    "nom": "Pairi Daiza",
    "depart": "Lille",
    "avec": {"temps_min": 52.6, "distance_km": 73.19},
    "sans": {"temps_min": 109.4, "distance_km": 95.48},
    "delta_km": 22.29,
    "delta_temps_min": 56.8,
    "bbox": [minLon, minLat, maxLon, maxLat]
  }
  ```
  `bbox` sert a cadrer la mini-carte de la vignette (au sens carte de gamme,
  pas la vignette routiere !) sans avoir a charger le GeoJSON complet.

- **`details/{id}.json`** — fiche complete pour la page de detail d'une
  destination. Reprend la structure de `output/stats/{id}.json` (voir
  `README.md` racine pour le detail methodologique de chaque champ) plus :
  - `geo.avec` / `geo.sans` : chemins relatifs vers les GeoJSON (dans
    `geo/`), a fetcher pour tracer les deux itineraires sur la carte.
  - `bbox` : cadrage combine des deux traces.
  - `resume_delta` : tableau pret a afficher pour la ligne d'icones "ce que
    change l'absence de vignette" (distance, temps, carburant, cout, CO2, et
    si disponibles villages traverses / carrefours). Chaque entree :
    `{"cle": "distance", "label": "de distance", "valeur": 22.29, "unite": "km"}`.
  - `prix_vignette_eur_an` : **`null`** — le prix officiel de la vignette
    n'est pas encore publie au moment de la generation de ces donnees (cf.
    `brief_vignette_belgique.md` §5). Ne pas afficher de prix invente dans
    l'app tant que ce champ n'est pas renseigne manuellement dans
    `pipeline/config.py` (`PRIX_VIGNETTE_EUR_AN`) une fois la source
    officielle connue.
  - `etapes` : trajet "sans vignette" etape par etape (villages traverses
    dans l'ordre, avec une heure estimee par interpolation lineaire depuis
    `pipeline.config.DEPART_HEURE_DEFAUT`, configurable). **Heures indicatives**,
    pas un horaire garanti (ni trafic, ni arrets pris en compte).

- **`geo/{id}_avec.geojson`, `geo/{id}_sans.geojson`** — geometrie
  (LineString, WGS84) des deux itineraires, copiees depuis
  `output/geojson/` pour que ce dossier soit autonome (deplacable/commitable
  tel quel sans dependre du reste du repo).

## Champs a interpreter avec prudence dans l'UI

- `sans.nb_cassures_detectees > 0` : le trace a au moins une portion ou
  aucun court chemin routable n'a ete trouve lors du profilage (cf. README
  racine, section "itineraire sans vignette") — ne bloque pas l'affichage
  mais signale un trace qui merite une verification manuelle avant mise en
  avant editoriale forte.
- `analyse.distance_urbaine_km` : **estimation approximative** (buffers
  autour des lieux-dits OSM, pas une couche de zones baties officielle) —
  a presenter comme un ordre de grandeur, pas une mesure precise.
- `analyse.distance_nationale_regionale_km` : regroupe les routes
  nationales francaises ET regionales belges (memes prefixe `N` en
  OpenStreetMap, systemes administratifs differents) — ne pas presenter
  comme un decompte "vignette" precis, cf. README racine.
- Tous les montants carburant/CO2/cout sont des **estimations editoriales**
  (modele de consommation simplifie inspire de COPERT, prix carburant
  configurable) — a accompagner d'une mention explicite dans l'UI (l'icone
  "info" du mockup, par exemple).

## Regenerer

```
python -m pipeline.build_dataset
python -m pipeline.build_lovable_export
```

Rien n'est a editer a la main dans `output/lovable/` — tout est ecrase a
chaque regeneration.
