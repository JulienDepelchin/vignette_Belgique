import osmium

IN_BE = "d:/vignette_belgique/belgium-260713.osm.pbf"
IN_FR = "d:/vignette_belgique/nord-pas-de-calais-260713.osm.pbf"
OUT = "d:/vignette_belgique/tools/belgium_npdc_merged.osm.pbf"

merger = osmium.MergeInputReader()
n1 = merger.add_file(IN_BE)
n2 = merger.add_file(IN_FR)
print(f"ajouté: {n1} objets (BE), {n2} objets (FR)")

writer = osmium.SimpleWriter(OUT, overwrite=True)
merger.apply(writer)
writer.close()
print(f"écrit: {OUT}")
