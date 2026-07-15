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
  `preview_image` : chemin vers une image statique PNG (dans `previews/`)
  superposant les deux traces (avec=bleu, sans=rouge, rond=depart,
  carre=arrivee) — **a utiliser pour la grille de cartes plutot qu'une
  carte Leaflet live par carte** : une mini-carte interactive par carte
  s'est averee peu fiable (conteneur de taille zero au montage, cout de
  performance sur mobile avec 8+ cartes Leaflet simultanees). Generee par
  `python -m pipeline.build_preview_images`.

- **`details/{id}.json`** — fiche complete pour la page de detail d'une
  destination. Reprend la structure de `output/stats/{id}.json` (voir
  `README.md` racine pour le detail methodologique de chaque champ) plus :
  - `geo.avec` / `geo.sans` : chemins relatifs vers les GeoJSON (dans
    `geo/`), a fetcher pour tracer les deux itineraires sur la carte de
    detail (celle-ci reste une vraie carte Leaflet interactive, contrairement
    aux vignettes de la grille). **Piege classique Leaflet + GeoJSON** : les
    coordonnees GeoJSON sont `[longitude, latitude]`, alors que Leaflet
    attend `[latitude, longitude]` pour `L.polyline()`. Si le trace
    n'apparait pas (fond de carte visible mais aucune ligne), c'est presque
    toujours parce que le code construit une polyline a la main a partir de
    `geometry.coordinates` brut sans inverser les paires. Utiliser le
    composant `<GeoJSON data={geojson} />` de react-leaflet (ou
    `L.geoJSON(data)` en Leaflet pur), qui gere cette inversion nativement
    — ne jamais passer `coordinates` directement a `L.polyline()`.
  - `bbox` : cadrage combine des deux traces.
  - `preview_image` : meme champ que dans `destinations.json`.
  - `resume_delta` : tableau pret a afficher pour la ligne d'icones "ce que
    change l'absence de vignette" (distance, temps, carburant, cout, CO2, et
    si disponibles villages traverses / carrefours). Chaque entree :
    `{"cle": "distance", "label": "de distance", "valeur": 22.29, "unite": "km"}`.
  - `prix_vignette` : tarifs de la vignette, par classe d'emission du
    vehicule (equivalence Crit'Air) :
    ```json
    {
      "devise": "EUR",
      "annuel": {"zero_emission": 90, "critair_3": 100, "critair_4_5": 125},
      "journalier": {"zero_emission": 8.10, "critair_3": null, "critair_4_5": 11.25},
      "source": null
    }
    ```
    Le tarif depend du vehicule du lecteur, pas de la destination — l'UI
    devrait presenter une fourchette (ou un selecteur de classe) plutot
    qu'un chiffre unique. `journalier.critair_3` est `null` : seuls les
    tarifs "zero emission" (8,10 EUR) et "Crit'Air 4/5" (11,25 EUR) ont ete
    communiques explicitement ; ne pas interpoler/afficher une valeur
    inventee pour la classe intermediaire. `source` est `null` — **a
    completer avec une reference officielle avant publication** (cf. skill
    `verif-data`), ces chiffres n'ont pour l'instant ete que communiques
    verbalement dans cette session de travail.
    Ce prix est une info de reference affichee a cote du trajet "avec
    vignette" (cf. mockup) — il n'est **pas** integre dans `delta_cout_eur`,
    qui ne couvre que le delta de carburant (le cout reel de la vignette
    depend de la frequence d'usage annuel/journalier du vehicule du lecteur,
    une hypothese que ce pipeline ne peut pas faire a sa place).
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
