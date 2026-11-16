import bpy, time
t0 = time.time()
def stamp(msg):
    print("T+%.1fs %s" % (time.time() - t0, msg), flush=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
stamp("pulito")
bpy.ops.mesh.primitive_cube_add()
stamp("un cubo ok")
bpy.ops.object.text_add()
stamp("testo ok")
