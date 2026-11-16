import bpy, os, math
blend = "C:\\Progetti\\stanza-3d\\spogliatoio_v01.blend"
bpy.ops.wm.open_mainfile(filepath=blend)
for n in ["Maglia_10", "Maglia_09", "Gruccia_10"]:
    o = bpy.data.objects[n]
    print(n, "loc=%s" % str(tuple(round(v, 3) for v in o.location)),
          "rotz=%.1f" % math.degrees(o.rotation_euler[2]))
for m in bpy.data.materials:
    if "Scudo" in m.name or "Dettagli" in m.name or "Portieri" in m.name:
        print("MAT:", m.name)
ntot = sum(1 for o in bpy.data.objects if o.name.startswith("Maglia_"))
print("NMAGLIE:", ntot)
