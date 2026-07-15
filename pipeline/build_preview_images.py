"""
Genere une image statique (PNG) par destination, superposant les deux traces
(avec vignette en bleu, sans vignette en rouge) sur un vrai fond de carte
(tuiles OpenStreetMap via contextily) -- remplace les mini-cartes Leaflet
interactives dans la grille de cartes, plus fragiles et couteuses
(conteneurs de taille zero au montage, performance mobile).

Usage : python -m pipeline.build_preview_images
(a lancer apres build_dataset -- lit les GeoJSON deja exportes)

Necessite une connexion internet (telechargement des tuiles OSM/CartoDB au
premier passage ; contextily les met en cache localement ensuite).
"""
import json

import contextily as cx
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import LineString, Point

from . import config

OUT_DIR = config.OUTPUT_DIR / "lovable" / "previews"

COULEUR_AVEC = "#1d4ed8"   # bleu
COULEUR_SANS = "#dc2626"   # rouge
FIG_SIZE = (4, 3)          # pouces -- ratio 4:3, cf. cartes du mockup
DPI = 200                  # ~800x600px, net sur mobile retina
# CartoDB Positron : fond clair et sobre, contraste bien avec les traces
# colorees a cette petite taille (contrairement au rendu standard OSM,
# plus charge/colore). Pas de cle API requise.
BASEMAP_SOURCE = cx.providers.CartoDB.Positron


def _load_line_wgs84(path):
    obj = json.loads(path.read_text(encoding="utf-8"))
    return LineString(obj["geometry"]["coordinates"])  # [lon, lat]


def build_one(dest_id):
    line_avec = _load_line_wgs84(config.OUTPUT_GEOJSON_DIR / f"{dest_id}_avec.geojson")
    line_sans = _load_line_wgs84(config.OUTPUT_GEOJSON_DIR / f"{dest_id}_sans.geojson")

    # reprojection en Web Mercator (EPSG:3857), requis par les tuiles contextily
    gdf = gpd.GeoSeries([line_avec, line_sans], crs="EPSG:4326").to_crs("EPSG:3857")
    line_avec_m, line_sans_m = gdf.iloc[0], gdf.iloc[1]

    fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
    # l'axe occupe tout le canevas (pas de marge) -- indispensable pour que le
    # ratio 4:3 final soit garanti quelle que soit la forme du trace (sinon
    # bbox_inches="tight" recadrerait sur le contenu et casserait le ratio,
    # surtout visible sur les traces tres allonges nord-sud comme Floralux)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    for line, color, zorder in ((line_sans_m, COULEUR_SANS, 2), (line_avec_m, COULEUR_AVEC, 3)):
        xs, ys = line.xy
        ax.plot(xs, ys, color=color, linewidth=2.6, solid_capstyle="round",
                 path_effects=None, zorder=zorder, alpha=0.95)

    depart = Point(line_sans_m.coords[0])
    arrivee = Point(line_sans_m.coords[-1])
    ax.scatter([depart.x], [depart.y], color="white", edgecolor="#0f172a", linewidth=1.3, s=45, zorder=4)
    ax.scatter([arrivee.x], [arrivee.y], color="#0f172a", s=40, zorder=4, marker="s")

    ax.set_aspect("equal")
    ax.axis("off")

    # calcule une emprise centree qui respecte deja le ratio de FIG_SIZE (4:3)
    # avant d'appeler add_basemap -- indispensable : si on laisse
    # set_aspect("equal") seul ajuster la vue apres coup, le pavage de tuiles
    # contextily est recupere pour l'emprise "brute" (non ajustee) et laisse
    # des zones sans fond de carte sur les traces tres allonges (Floralux,
    # Mont Noir, Bellewaerde, Tournai)
    margin = 0.12
    all_x = list(line_avec_m.xy[0]) + list(line_sans_m.xy[0])
    all_y = list(line_avec_m.xy[1]) + list(line_sans_m.xy[1])
    minx, maxx = min(all_x), max(all_x)
    miny, maxy = min(all_y), max(all_y)
    span_x = (maxx - minx) * (1 + 2 * margin) or 1000
    span_y = (maxy - miny) * (1 + 2 * margin) or 1000
    center_x, center_y = (minx + maxx) / 2, (miny + maxy) / 2

    target_ratio = FIG_SIZE[0] / FIG_SIZE[1]
    if span_x / span_y < target_ratio:
        span_x = span_y * target_ratio
    else:
        span_y = span_x / target_ratio

    ax.set_xlim(center_x - span_x / 2, center_x + span_x / 2)
    ax.set_ylim(center_y - span_y / 2, center_y + span_y / 2)

    try:
        cx.add_basemap(ax, source=BASEMAP_SOURCE, attribution=False)
    except Exception as e:
        print(f"  [{dest_id}] fond de carte indisponible ({e}) -- image generee sans basemap")

    out_path = OUT_DIR / f"{dest_id}.png"
    fig.savefig(out_path)  # pas de bbox_inches="tight" : garde le ratio 4:3 fixe (cf. commentaire ci-dessus)
    plt.close(fig)
    return out_path


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    trajets = json.loads(config.OUTPUT_TRAJETS_JSON.read_text(encoding="utf-8"))
    for d in trajets:
        out_path = build_one(d["id"])
        print(f"{d['id']} -> {out_path}")

    # met a jour destinations.json et details/{id}.json avec le chemin de l'image
    lovable_dir = config.OUTPUT_DIR / "lovable"
    dests_path = lovable_dir / "destinations.json"
    dests = json.loads(dests_path.read_text(encoding="utf-8"))
    for d in dests:
        d["preview_image"] = f"previews/{d['id']}.png"
    dests_path.write_text(json.dumps(dests, ensure_ascii=False, indent=2), encoding="utf-8")

    details_dir = lovable_dir / "details"
    for d in dests:
        detail_path = details_dir / f"{d['id']}.json"
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        detail["preview_image"] = f"previews/{d['id']}.png"
        detail_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{len(trajets)} images generees -> {OUT_DIR}")
    print("destinations.json et details/*.json mis a jour avec le champ 'preview_image'")


if __name__ == "__main__":
    main()
