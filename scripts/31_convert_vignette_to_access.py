"""
Deuxième passe (rapide, sur le fichier déjà réduit) : convertit le tag
`vignette=yes` en restriction d'accès standard OSM (`motor_vehicle=no`)
que GraphHopper respecte nativement avec son profil "car" par défaut -
pas besoin d'EncodedValue custom ni de build Java personnalisé.
"""
import osmium

IN_PBF = "d:/vignette_belgique/tools/belgium-vignette-tagged.osm.pbf"
OUT_PBF = "d:/vignette_belgique/tools/belgium-vignette-final.osm.pbf"


def main():
    fp = osmium.FileProcessor(IN_PBF)
    n_way = 0
    n_blocked = 0
    with osmium.SimpleWriter(OUT_PBF, overwrite=True) as writer:
        for obj in fp:
            if obj.is_way():
                n_way += 1
                if obj.tags.get("vignette") == "yes":
                    w = obj.replace(tags=dict(obj.tags, motor_vehicle="no"), nodes=list(obj.nodes))
                    writer.add_way(w)
                    n_blocked += 1
                else:
                    writer.add_way(obj)
            elif obj.is_node():
                writer.add_node(obj)
            elif obj.is_relation():
                writer.add_relation(obj)
    print(f"ways: {n_way}, dont bloqués motor_vehicle=no (soumis vignette): {n_blocked}")
    print(f"écrit: {OUT_PBF}")


if __name__ == "__main__":
    main()
