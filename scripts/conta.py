import bpy
print("OGGETTI:", len(bpy.data.objects))
for o in bpy.data.objects:
    print(" -", o.type, o.name)
