# Brief technique — Testeur de trajets "sans vignette" (Belgique)

## Objectif
Pour 14 destinations belges fréquentées par les frontaliers du Nord/Pas-de-Calais, déterminer s'il est possible de rejoindre chacune depuis la frontière en n'empruntant **que des voiries communales** (donc exemptées de la future vignette, qui s'applique aux autoroutes et routes régionales).

Contrainte clé : la classification régional/communal doit venir de **sources officielles**, pas d'une heuristique OSM.

> **Note de mise à jour** : les §0 à §5 ci-dessous sont le brief technique *initial*, conservé tel quel comme trace de la réflexion de départ. La méthodologie a évolué en cours de route (voir **§7 Méthodologie finale**) — le plan `networkx` + INSPIRE/TN.RoadTransportNetwork s'est heurté à des trous de digitalisation trop nombreux pour être fiable, et a été remplacé par un moteur de routing dédié (GraphHopper) sur un extrait OSM taggé avec la classification officielle. Les résultats définitifs sont en **§8**.

---

## 0. Phase pilote (avant les 10 trajets)
Démarrer sur 2 lieux seulement, un par source de données, pour valider chaque pipeline de classification séparément avant de généraliser :
- **Pairi Daiza** (Wallonie) → valide la logique RES_ROUTIER_REGIONAL / INSPIRE TN.RoadLink
- **Bellewaerde** (Flandre) → valide la logique Wegenregister (`wegbeheerder`)

Objectif du pilote : confirmer que la classification régional/communal est fiable et que le graphe est routable, avant d'industrialiser sur les 8 autres lieux.

**Moteur de routing** : pas besoin d'OSRM/GraphHopper à ce stade. `networkx` (déjà dans votre stack Python) suffit sur un graphe borné à une zone restreinte — `nx.has_path` / `nx.shortest_path` couvrent le besoin sans monter de serveur de routing. Un vrai moteur dédié ne devient pertinent que pour une éventuelle V2 "planificateur ouvert aux lecteurs" nécessitant des réponses rapides sur des requêtes libres — pas pour valider 10 trajets pré-définis.

## 1. Sources officielles à utiliser

### Wallonie (Pairi Daiza)
Deux couches complémentaires du Géoportail de Wallonie :

- **Réseau routier régional** — la liste exhaustive de ce qui EST régional/autoroutier.
  - Service : `https://geoservices.wallonie.be/arcgis/rest/services/MOBILITE/RES_ROUTIER_REGIONAL/MapServer`
  - Téléchargement : GeoPackage, EPSG:31370 (Lambert 72), via la fiche catalogue du Géoportail
  - Codification du champ `CODE_ROUTE` : A = autoroute, B = bretelle, N = route régionale ("Nationale"), R = ring, T = route touristique. Tout ce qui porte un de ces préfixes = soumis à vignette.

- **INSPIRE TN.RoadTransportNetwork (RoadLink/RoadNode)** — le réseau routier complet (régional + communal), retenu comme source pour le graphe de routing wallon (voir justification ci-dessous).
  - Fiche : `https://geoportail.wallonie.be/catalogue/70c5ee8d-1554-468b-b5d4-7c976b046894.html`
  - Téléchargement direct (GML) : `http://geoservices.wallonie.be/geotraitement/spwdatadownload/get/70c5ee8d-1554-468b-b5d4-7c976b046894/TN.RoadTransportNetwork.gml.zip`
  - Avantage : structuré nativement en nœuds (`TN.RoadTransportNetwork.RoadNode`) et segments (`TN.RoadTransportNetwork.RoadLink`), donc a priori déjà pensé pour un usage réseau/routing, avec moins de nettoyage topologique à prévoir qu'une couche non structurée en nœuds/segments.
  - **Première étape en Claude Code, avant tout le reste** : télécharger ce GML et inspecter son schéma d'attributs (`gdf.columns` après lecture avec geopandas/fiona). Le standard INSPIRE Transport Network prévoit un champ `roadClassification`, mais rien ne garantit qu'il reflète la distinction administrative belge (gestionnaire = Région vs commune) plutôt qu'une simple classification fonctionnelle.

**Logique de classification Wallonie** : charger TN.RoadTransportNetwork (réseau complet, régional + communal) → jointure spatiale avec RES_ROUTIER_REGIONAL (buffer quelques mètres, les deux couches ne sont pas topologiquement identiques à 100%) → tout tronçon qui matche = régional, le reste = communal. Si l'inspection du schéma révèle que `roadClassification` permet déjà de trancher seul, cette jointure devient une simple vérification croisée plutôt qu'une étape obligatoire.

### Flandre (Bellewaerde, Plopsaland, Famiflora Mouscron, Bruges, tronçons carburant/tabac à Menen/Comines)
Une seule couche suffit : **Wegenregister** (Informatie Vlaanderen). Contrairement à la Wallonie, ce registre couvre déjà tout le réseau (région + provinces + communes) avec la classification intégrée.

- WMS : `http://geoservices.informatievlaanderen.be/raadpleegdiensten/Wegenregister/wms`
- Téléchargement : `download.vlaanderen.be`, thème Mobiliteit
- Attributs clés : `linkerwegbeheerder` / `rechterwegbeheerder` (gestionnaire à gauche/droite du tronçon). Valeur "Vlaams Gewest" = géré par l'AWV = **gewestweg = soumis à vignette**. Toute autre valeur (commune, province résiduelle) = communal.
- Un gewestweg porte toujours un numéro A (autoroute) ou N (route nationale) géré par l'AWV — ça permet une double vérification avec le champ `ref` si besoin, mais l'attribut `wegbeheerder` reste la source de vérité.

**Logique de classification Flandre** : filtrer directement sur `wegbeheerder = "Vlaams Gewest"` → régional. Reste → communal.

### Bruxelles
A priori hors périmètre pour vos 10 lieux actuels. Si besoin plus tard : Urbis / Bruxelles Mobilité, logique équivalente (gestionnaire = Région bruxelloise vs commune).

### Frontière France
Pas de contrainte vignette côté français — inutile de classifier le réseau français. Il faut juste un ou deux points d'entrée par axe frontalier (ex. sortie Neuville-en-Ferrain / Halluin / Comines) comme origine de chaque test.

---

## 2. Construction du graphe de routing

1. Charger les deux réseaux complets (INSPIRE TN.RoadTransportNetwork Wallonie + Wegenregister Flandre) dans un même CRS (reprojeter en EPSG:31370 ou EPSG:3812, à trancher selon ce qui minimise la déformation sur votre zone d'étude — les deux régions n'utilisent pas la même projection de base).
2. Fusionner en un seul GeoDataFrame avec un champ booléen harmonisé `soumis_vignette` (True/False) selon la logique région par région ci-dessus.
3. Construire un graphe topologique (`networkx`, ou `momepy`/`sgeop` pour la conversion GeoDataFrame → graphe si la topologie n'est pas déjà nettoyée). TN.RoadTransportNetwork est structuré en nœuds/segments nativement, donc a priori moins de travail que Wegenregister, qui n'est pas garanti "routable" tel quel.
4. Nettoyage à prévoir : nœuds dupliqués aux jonctions, sens uniques (si l'attribut existe), tronçons non connectés (fréquent aux limites de couches).

C'est l'étape la plus longue du pipeline — à budgéter plus de temps que la partie "test de connectivité" elle-même, qui est triviale une fois le graphe propre (`networkx.has_path` / `shortest_path`).

## 3. Test par destination
Pour Pairi Daiza et Bellewaerde en premier (pilote), puis pour chacun des 8 autres lieux une fois la méthode validée :
1. Géocoder précisément le point d'arrivée (adresse exacte du parking/entrée, pas juste le centre de la commune)
2. Retirer du graphe tous les tronçons `soumis_vignette = True`
3. Chercher un chemin entre le(s) point(s) d'entrée frontaliers pertinents et la destination
4. Si trouvé : calculer la distance/durée et comparer au trajet normal (avec vignette) pour donner le delta au lecteur
5. Si non trouvé : identifier le tronçon régional incontournable (souvent le dernier segment d'accès) — c'est en soi une info éditoriale intéressante

## 4. Validation manuelle obligatoire
Avant publication, vérifier à l'œil (QGIS, superposition avec Google Street View ou WalOnMap/Geopunt) chacun des 10 itinéraires calculés, en particulier :
- Les ronds-points et bretelles d'accès aux zones commerciales/parcs
- Les traversées de centre-ville où une N-route peut localement changer de statut
- La cohérence entre les deux sources (Wallonie/Flandre) au passage d'une frontière régionale interne (aucun de vos 10 lieux n'est concerné a priori, mais bon réflexe si la liste évolue)

## 5. Limite à mentionner dans l'article
Le texte juridique définitif de la vignette n'est pas encore publié (accord de coopération interrégional du 10/07/2026, pas encore un texte de loi). Le périmètre exact "autoroutes et routes régionales / exception routes communales" pourrait encore être précisé d'ici mai 2027 — à formuler avec prudence ("sur la base des règles annoncées à ce stade").

## 6. Les 14 lieux, géolocalisés

Power Oil (Menen) a été retiré de la liste (aucune route communale trouvée par aucune méthode testée, y compris avec un vrai moteur de routing — cf. journal de session). Cinq lieux ajoutés : La Panne (plage/côte), Mont Noir (Zwarteberg, Westouter), aéroport de Charleroi, Mouscron (Grand-Place), Floralux Dadizele.

**Attention région** : trois lieux administrativement en Wallonie malgré une situation géographique/linguistique flamande — Mouscron, Dottignies (Famiflora) et Comines-Warneton (Gabriëls) sont des communes wallonnes enclavées côté flamand. Vérifié par géocodage inversé, pas une supposition.

| # | Lieu | Commune | Région | Latitude | Longitude | Motif |
|---|------|---------|--------|----------|-----------|-------|
| 1 | Bellewaerde | Ieper | Flandre | 50.845810 | 2.949768 | Parc d'attractions |
| 2 | Pairi Daiza | Brugelette | Wallonie | 50.590627 | 3.893746 | Parc animalier |
| 3 | Plopsaland | De Panne | Flandre | 51.080738 | 2.598554 | Parc d'attractions |
| 4 | Famiflora | Mouscron (Dottignies) | Wallonie | 50.717576 | 3.282815 | Jardinerie |
| 5 | Bruges (Markt) | Bruges | Flandre | 51.208688 | 3.224408 | Tourisme urbain |
| 6 | Grand-Place | Tournai | Wallonie | 50.606400 | 3.386625 | Tourisme urbain |
| 7 | Gabriëls | Comines-Warneton | Wallonie | 50.776567 | 3.018049 | Carburant |
| 8 | Real Tabac & Co La Palma | Menen | Flandre | 50.789091 | 3.139864 | Tabac |
| 9 | King Tabac | Mouscron | Wallonie | 50.726050 | 3.194531 | Tabac |
| 10 | La Panne (plage) | De Panne | Flandre | 51.097367 | 2.581506 | Tourisme côtier |
| 11 | Mont Noir (Zwarteberg) | Westouter (Heuvelland) | Flandre | 50.782355 | 2.742627 | Nature / randonnée |
| 12 | Aéroport de Charleroi | Gosselies (Charleroi) | Wallonie | 50.471744 | 4.473366 | Aéroport |
| 13 | Mouscron (Grand-Place) | Mouscron | Wallonie | 50.743954 | 3.214896 | Tourisme urbain |
| 14 | Floralux Dadizele | Dadizele (Moorslede) | Flandre | 50.840552 | 3.113505 | Jardinerie |

**Note régionale importante** : la répartition Wallonie/Flandre est en réalité proche de 7/7 (Wallonie : Pairi Daiza, Tournai, Famiflora, Gabriëls, King Tabac, Charleroi, Mouscron Grand-Place ; Flandre : Bellewaerde, Plopsaland, Bruges, Real Tabac, La Panne, Mont Noir, Floralux) — très différent de l'hypothèse initiale du brief ("8 lieux sur 10 en Flandre"), qui reposait sur une lecture géographique plutôt qu'administrative. Les deux pipelines de classification (PICC et Wegenregister) sont donc sollicités à parts quasi égales.

---

## 7. Méthodologie finale (GraphHopper + OSM taggé)

Le plan initial (§2) reposait sur `networkx` + reconstruction manuelle de la topologie du PICC/Wegenregister. En pratique, le PICC a des trous de digitalisation réels (des rues visiblement continues sur le terrain et sur le Géoportail lui-même, mais coupées en fragments non connectés dans les données) — au point de rendre un lieu confirmé accessible sur le terrain (Famiflora) faussement "injoignable" par le graphe fait main. Plutôt que de rafistoler la reconstruction de topologie indéfiniment, le pipeline a basculé sur un vrai moteur de routing.

**Principe** : deux couches d'information séparées, un rôle chacune.
- **Classification officielle** (PICC pour la Wallonie, Wegenregister pour la Flandre) → dit *qui gère* chaque tronçon. C'est la seule source qui a une valeur juridique — jamais remplacée par une heuristique OSM.
- **OSM** (extrait Belgique via Geofabrik) → sert uniquement de squelette de routage. Beaucoup plus complet et mieux connecté topologiquement que les cartographies officielles brutes.

**Pipeline concret :**
1. Télécharger deux extraits OSM (Geofabrik) : Belgique + Nord-Pas-de-Calais, fusionnés en un seul PBF (`pyosmium.MergeInputReader`)
2. Récupérer le PICC (WAL) et le Wegenregister (FLA) sur toute la zone d'étude via leurs API respectives (REST/OGC), comme prévu au §1, et les fusionner en une couche unique `soumis_vignette` (bool) — **Belgique uniquement**, la France n'a pas de vignette donc pas de classification à faire côté français
3. Jointure spatiale déterministe : pour chaque tronçon OSM `highway=*` (Belgique + France), chercher le tronçon officiel le plus proche à moins de 15 m (plus-proche-unique, **pas** `gpd.sjoin_nearest` — cf. incident #1) ; si régional, taguer le tronçon OSM `motor_vehicle=no`. Les tronçons français ne matchent jamais (pas de données côté France) → restent non taggés → libres de circulation, cohérent avec l'absence de vignette française
4. Écrire un nouvel extrait PBF taggé, l'importer dans **GraphHopper** (profil "car" par défaut — respecte nativement `motor_vehicle=no`, aucun `CustomModel` sur mesure nécessaire)
5. Interroger l'API `/route` de GraphHopper avec **un point de départ unique et réel (Lille, Grand-Place)** vers chaque destination — le trajet emprunte librement les routes françaises, puis est restreint au communal une fois la frontière belge franchie

**Outils** : JDK portable (Temurin, zip, sans droits admin), GraphHopper (jar autonome), `pyosmium` (édition du PBF), le tout hébergé en local dans `tools/`.

**Incident notable #1, pour mémoire** : la première version de la jointure spatiale utilisait `gpd.sjoin_nearest(..., max_distance=15) + drop_duplicates(keep="first")`. Avec ~80 000 géométries dupliquées (collectes qui se chevauchent), les égalités de distance entre un tronçon régional et un tronçon communal proches étaient tranchées arbitrairement — jusqu'à ~30 % d'incohérence sur certains types de voirie. Remplacé par une jointure manuelle (buffer + `distance().idxmin()` explicite), déduplication de la couche de classification en amont. Audité après coup : ~1 % d'incohérence résiduelle (cas ambigus réels, pas un bug systématique).

**Incident notable #2, pour mémoire** : les premières collectes PICC/Wegenregister étaient des rectangles ponctuels autour de chaque lieu (pas une couverture continue). Plusieurs itinéraires calculés sortaient de ces rectangles sur une partie de leur trajet (ex. la N27 près de Charleroi, la N32 près de Floralux Dadizele) — dans ces zones non couvertes, aucun tronçon régional n'était taggé, donc l'itinéraire "roulait" dessus sans être bloqué. Corrigé par une collecte unique et continue sur toute la zone d'étude (lon 2.45–4.60, lat 50.25–51.32) : 118 652 tronçons PICC + 502 692 segments Wegenregister, 621 344 après déduplication. Le taux de correspondance OSM ↔ classification officielle est passé de ~15 % à ~67 %, et le nombre de tronçons bloqués de 21 636 à 75 587.

**Incident notable #3, pour mémoire** : GraphHopper "accroche" (snap) toujours l'origine/destination demandée au nœud routable le plus proche dans le graphe — silencieusement, sans avertir si ce nœud est en réalité loin ou du mauvais côté d'une route régionale. Repéré manuellement sur Famiflora (point d'arrivée réel à 161 m, de l'autre côté de la N511) puis généralisé : un contrôle automatique compare maintenant le point d'arrivée réel à la destination demandée et signale tout écart de plus de 60 m (colonnes `ecart_arrivee_m` / `alerte` dans les GeoJSON exportés). 5 lieux sur 14 sont concernés à ce stade (Bellewaerde, Plopsaland, Famiflora, Real Tabac, Gabriëls) — pour ceux-là, le dernier segment jusqu'à la destination exacte n'est probablement pas 100 % communal et mérite une correction manuelle (cf. §8).

**Fiabilité** : l'algorithme de plus court chemin est mathématiquement garanti optimal pour le graphe donné — aucun doute possible là-dessus, et changer de moteur (Valhalla, OSRM) ne changerait pas les résultats puisqu'ils utilisent tous le même principe sur les mêmes données. Le risque réside entièrement dans la **qualité des données de classification** (trous de couverture, tags manquants), pas dans le calcul. D'où l'audit ci-dessus, et la recommandation de vérification visuelle systématique (§4) qui reste valable.

**Incident notable #4, pour mémoire** : après la fusion Belgique + Nord-Pas-de-Calais, 3 lieux (Plopsaland, La Panne, Bruges) ont cessé de se connecter depuis Lille alors que Plopsaland/La Panne fonctionnaient très bien en test "frontière → lieu" isolé. Cause probable : l'élagage automatique des petites composantes déconnectées par GraphHopper (`prepare.min_network_size`, 200 arêtes par défaut) se comporte différemment sur ce graphe deux fois plus gros. Abaisser le seuil (200 → 20) a réparé Plopsaland/La Panne mais cassé Famiflora/Real Tabac au passage (une poche déconnectée gardée en vie a détourné l'accroche GraphHopper ailleurs) — piste abandonnée, pas de réglage stable trouvé. Une trace hybride (segment Lille→frontière + segment frontière→lieu réutilisé d'un test Belgique-seul) avait été tentée en solution provisoire, mais la vérification manuelle du tracé (passage forcé par les dunes de Bray-Dunes, N386 incontournable) a montré qu'elle n'était pas praticable. **Conclusion finale (après investigation approfondie, cf. incident #5)** : Plopsaland et La Panne sont **non joignables** en 100 % communal, au même titre que Bruges — confirmé par un quadrillage systématique de 315 points sur une zone de 14×15 km autour de La Panne (testant notamment Hondschoote, Oost-Cappel, Bambecque, Killem, Bierne, Warhem, Rexpoede, Herzeele), aucun ne rejoint la poche De Panne/Adinkerke. La seule route physique reliant Bray-Dunes (France) à De Panne (Belgique) semble être régionale (N34/N386/N39...). Bruges reste non joignable, confirmé indépendamment par 4+ méthodes différentes tout au long du projet.

**Incident notable #5, pour mémoire** : en creusant l'impasse La Panne, comparaison des tronçons bloqués avec la ligne de frontière officielle (`data/flandre/overpass_boundary_depanne_v2.json`) : la tolérance de jointure spatiale (15 m, cf. incident #1) déborde légèrement côté français près de certains postes-frontière, taguant à tort `motor_vehicle=no` sur des troncons réellement en France (ex. "Rue Albert 1er" ref D 60 à Bray-Dunes, immédiatement après la fin de la N386 belge) — alors que la classification officielle ne couvre que la Belgique et ne devrait jamais s'appliquer côté français. Corrigé (`scripts/190_patch_border_leak.py`) : retrait systématique du tag sur tout tronçon dont le `ref` matche le format départemental français (`D <nombre>`, jamais utilisé en Belgique) + une poignée de tronçons sans ref vérifiés manuellement contre la ligne de frontière — 32 tronçons corrigés au total, répartis sur plusieurs points de passage (Bray-Dunes/De Panne, mais aussi Watou/Poperinge et Steenvoorde, à re-vérifier pour Mont Noir). PBF corrigé : `tools/belgium-vignette-tagged-fixed.osm.pbf`. Ce bug était réel et corrigé, mais n'a pas suffi à rendre La Panne/Plopsaland joignables : le vrai verrou est un peu plus au nord, sur le tronçon côtier Bray-Dunes↔De Panne lui-même (cf. incident #4).

## 8. Résultats finaux (traces validées manuellement)

8 lieux ont été intégralement vérifiés et corrigés à la main par l'utilisateur dans gpx.studio, puis déplacés dans `data/traces_finales_definitives/` : Bellewaerde, Pairi Daiza, Famiflora, Tournai, Mont Noir, Aéroport de Charleroi, Mouscron (Grand-Place), Floralux Dadizele. Gabriëls, Real Tabac & Co La Palma et King Tabac ne sont pas repris dans cet ensemble définitif. Plopsaland, La Panne et Bruges restent non joignables en 100 % communal (cf. incidents #4/#5).

**Méthode de mesure** (`scripts/200_validate_final_traces.py`, `210_surface_breakdown.py`, `230_robust_time_distance.py`) :
- **Validation communale** : chaque point du tracé comparé à la classification officielle (tolérance 20 m). Résultat : uniquement des traversées ponctuelles de quelques mètres à quelques dizaines de mètres (ronds-points/carrefours, normales et attendues), sauf **Pairi Daiza** qui emprunte réellement ~170 m de la N504 (Rue de Gourgues/Grand'Rue) à travers le village de Wiers — alternative communale probable à proximité : Rue Saint-Hubert, à vérifier par l'utilisateur.
- **Distance** : longueur réelle du tracé dessiné (somme des segments), la mesure la plus fiable puisqu'elle ne dépend d'aucun rappariement automatique.
- **Temps** : le map-matching GraphHopper et le routage multi-points se sont révélés **peu fiables tels quels** sur ces traces dessinées à la main — un micro-passage imprécis peut forcer un détour de 10+ km dans le calcul sans que ce soit un vrai problème sur le terrain (repéré sur Famiflora : un détour de 11 km calculé pour un passage de 20 m près de l'arrivée). Solution retenue : vitesse moyenne mesurée sur les portions du tracé qui routent normalement, appliquée à la distance réelle totale.
- **"Cassures" locales détectées** (portion du tracé sans court chemin routable trouvé, donc à revérifier visuellement en priorité) :
  - Bellewaerde : ~(50.7591, 2.9612)
  - Charleroi : ~(50.7407, 4.3498) → (50.7399, 4.3536)
  - Famiflora : ~(50.7156-50.7186, 3.2726-3.2823), proche de l'arrivée — zone du croisement N511 déjà documentée (cf. incident #3), à confirmer que le tracé suit bien le passage court connu
  - Floralux : ~(50.8416, 3.1131), écart mineur
  - Pairi Daiza : la zone N504/Wiers ci-dessus, plus deux zones proches de (50.535-50.539, 3.603-3.621) à vérifier
  - Tournai : ~(50.5709, 3.3344)
  - Mont Noir et Mouscron : aucune cassure détectée

| Lieu | Distance (sans vignette) | Temps estimé | Avec vignette (Lille→dest, réseau libre) | Delta km | Delta temps | Δ carburant¹ | Δ coût¹ |
|---|---|---|---|---|---|---|---|
| Bellewaerde | 37,3 km | 54 min | 29,3 km / 40 min | +8,0 km | +14 min | +0,5 L | +0,9 € |
| Pairi Daiza | 95,6 km | 110 min | 73,2 km / 53 min | +22,4 km | +57 min | +1,5 L | +2,5 € |
| Famiflora | 23,7 km | 32 min | 20,5 km / 25 min | +3,2 km | +7 min | +0,2 L | +0,4 € |
| Tournai | 32,3 km | 35 min | 26,7 km / 25 min | +5,5 km | +10 min | +0,4 L | +0,6 € |
| Mont Noir | 41,9 km | 39 min | 35,9 km / 29 min | +6,0 km | +10 min | +0,4 L | +0,7 € |
| Aéroport de Charleroi | 225,7 km | 291 min | 118,0 km / 74 min | **+107,7 km** | **+217 min (3h37)** | **+7,0 L** | **+12,2 €** |
| Mouscron (Grand-Place) | 18,0 km | 23 min | 18,0 km / 23 min | ~0 | ~0 | ~0 | ~0 |
| Floralux Dadizele | 29,9 km | 39 min | 28,4 km / 30 min | +1,5 km | +9 min | +0,1 L | +0,2 € |

¹ Hypothèse illustrative : 6,5 L/100 km (moyenne essence tous types de route confondus), 1,75 €/L — **à ajuster selon le véhicule réellement retenu pour l'article**, ce n'est pas une mesure, juste un ordre de grandeur. Le delta est dominé par la distance, pas par le type de route.

**Répartition du revêtement** (`scripts/210_surface_breakdown.py`, correspondance au tronçon OSM le plus proche à 15 m près) :

| Lieu | Asphalté | Pavé | Non asphalté | Inconnu (tag absent)² |
|---|---|---|---|---|
| Bellewaerde | 59,5 % | 1,6 % | 0 % | 38,9 % |
| Charleroi | 57,8 % | 3,2 % | 2,9 % | 36,0 % |
| Famiflora | 62,7 % | 4,1 % | 0 % | 33,2 % |
| Floralux | 93,7 % | 1,9 % | 0 % | 4,3 % |
| Mont Noir | 97,9 % | 0,3 % | 1,6 % | 0,2 % |
| Mouscron | 72,4 % | 5,8 % | 0 % | 21,7 % |
| Pairi Daiza | 65,4 % | 4,3 % | 0 % | 30,3 % |
| Tournai | 82,7 % | 0,8 % | 0 % | 16,5 % |

² "Inconnu" = pas de tag `surface` sur le tronçon OSM correspondant — très probablement de l'asphalte en zone urbaine/résidentielle (défaut implicite), mais non vérifié : à ne pas présenter comme "non asphalté".

**À garder à l'esprit avant publication** :
- Distances à vol d'itinéraire réel (Lille Grand-Place → destination), pas des segments frontaliers artificiels — bien plus représentatif du trajet d'un frontalier, mais reste un point de départ éditorial parmi d'autres possibles (Douai, Valenciennes, Dunkerque... donneraient des chiffres différents).
- Pairi Daiza a un vrai passage régional (N504, Wiers) à corriger avant publication définitive des chiffres ci-dessus.
- Le texte juridique définitif de la vignette n'étant pas encore publié (§5), formuler ces chiffres avec la prudence qui s'impose.

**Export pour visualisation** : fichiers KML dans `data/traces_finales_kml/` (un par lieu), importables directement dans Google My Maps (mymaps.google.com → "Importer") pour une visualisation partageable. Limite : My Maps affiche le tracé mais ne permet pas de recalculer un itinéraire dessus (pas de temps/carburant Google sur le tracé exact). Pour un avis de recoupement grossier côté Google (temps, sans garantie qu'il suive exactement les mêmes routes communales), on peut générer une URL Google Maps Directions avec les points du tracé en étapes (`https://www.google.com/maps/dir/lat1,lon1/lat2,lon2/...`) — Google optimisera/simplifiera entre les étapes, donc ça reste indicatif, pas une validation.

## 9. Itinéraires alternatifs (historique)

GraphHopper ne calcule qu'un seul trajet par défaut (le "meilleur"). Sur demande (`algorithm=alternative_route`), il peut en proposer plusieurs, utile quand le trajet par défaut semble emprunter un passage peu réaliste. Cas d'usage réel sur Pairi Daiza (avant correction manuelle finale, cf. §8) :

| # | Distance | Temps | Latitude de franchissement FR/BE |
|---|---|---|---|
| 1 | 81,85 km | 117 min | 50,58 (le plus au nord) |
| 2 | 85,67 km | 117 min | 50,69 |
| 3 | 87,63 km | 117 min | 50,60 |
| 4 | 91,50 km | **111 min** | **50,52 (le plus au sud)** |

L'itinéraire 4 franchissait la frontière nettement plus au sud — piste qui a servi de base à la correction manuelle finale de Pairi Daiza. Le même réflexe (demander les alternatives) est à appliquer à tout lieu dont le tracé par défaut semble mal choisi avant de corriger à la main.

**Angle éditorial qui ressort** : les commerces frontaliers (tabac/carburant à Menen/Mouscron) ont un delta quasi nul — cohérent, ils sont collés à la frontière et n'empruntent jamais l'autoroute même dans le trajet "normal". Les grandes destinations plus profondes en Belgique (Charleroi, Bellewaerde, Pairi Daiza) demandent des heures de détour supplémentaire, Charleroi en tête avec +3h27.
