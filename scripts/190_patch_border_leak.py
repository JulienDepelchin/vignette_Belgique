"""
Corrige la fuite de classification a la frontiere France-Belgique : des troncons
cotes francais (ref D-route departementale, ou petites rues sans ref adjacentes)
ont ete taggues motor_vehicle=no par erreur (tolerance de jointure spatiale de 15m
qui deborde legerement sur le cote francais pres de la frontiere). On ne doit
jamais bloquer un troncon reellement situe en France : la classification
officielle ne couvre que la Belgique par construction.

Strategie :
1. Retire motor_vehicle=no/vignette_source sur tout troncon dont le ref matche
   le format francais "D <nombre>" (route departementale, jamais utilise en
   Belgique) - fix systematique valable sur toute la zone d'etude.
2. Retire aussi sur une liste explicite de way IDs verifies manuellement cote
   francais pres du poste-frontiere Bray-Dunes/De Panne (sans ref exploitable),
   verifies par comparaison geometrique avec la ligne de frontiere officielle
   (overpass_boundary_depanne_v2.json).
"""
import re
import sys

import osmium

sys.stdout.reconfigure(encoding="utf-8")

IN_PBF = "d:/vignette_belgique/tools/belgium-vignette-tagged.osm.pbf"
OUT_PBF = "d:/vignette_belgique/tools/belgium-vignette-tagged-fixed.osm.pbf"

FRENCH_DROAD_RE = re.compile(r"^D\s?\d+")

# way IDs verifies manuellement cote francais pres de la frontiere Bray-Dunes/De Panne
# (cf. comparaison avec data/flandre/overpass_boundary_depanne_v2.json)
MANUAL_FRENCH_SIDE_IDS = {
    929291146,   # Rue des Dunes (FR, residentielle, sans ref)
    1134119205,  # service sans nom, cote FR
    1134119206,  # service sans nom, cote FR
}


def is_french_ref(ref):
    if not ref:
        return False
    return any(FRENCH_DROAD_RE.match(part.strip()) for part in ref.split(";"))


class PatchHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.n_seen = 0
        self.n_patched = 0
        self.patched_ids = []

    def way(self, w):
        self.n_seen += 1
        if w.tags.get("motor_vehicle") == "no":
            ref = w.tags.get("ref", "")
            if is_french_ref(ref) or w.id in MANUAL_FRENCH_SIDE_IDS:
                self.n_patched += 1
                self.patched_ids.append((w.id, w.tags.get("name", ""), ref))


print("Passe 1 : identification des troncons a corriger...")
h = PatchHandler()
h.apply_file(IN_PBF, locations=False)
print(f"  {h.n_seen} ways scannes, {h.n_patched} a corriger (retrait motor_vehicle=no)")
for wid, name, ref in h.patched_ids:
    print(f"    way/{wid} name={name!r} ref={ref!r}")

patched_id_set = {wid for wid, _, _ in h.patched_ids}

print("\nPasse 2 : ecriture du PBF corrige...")


class Rewriter(osmium.SimpleHandler):
    def __init__(self, writer):
        super().__init__()
        self.writer = writer

    def node(self, n):
        self.writer.add_node(n)

    def way(self, w):
        if w.id in patched_id_set:
            tags = dict(w.tags)
            tags.pop("motor_vehicle", None)
            tags.pop("vignette_source", None)
            w = w.replace(tags=tags, nodes=list(w.nodes))
        self.writer.add_way(w)

    def relation(self, r):
        self.writer.add_relation(r)


with osmium.SimpleWriter(OUT_PBF, overwrite=True) as writer:
    rw = Rewriter(writer)
    rw.apply_file(IN_PBF, locations=False)

print(f"Termine -> {OUT_PBF}")
