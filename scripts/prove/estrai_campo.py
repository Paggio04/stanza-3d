import bpy, os
video = r"C:\Users\program02\Videos\Registrazione 2026-11-18 091754.mp4"
outdir = r"C:\Progetti\stanza-3d\render"
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_percentage = 75
sc.render.image_settings.file_format = "PNG"
se = sc.sequence_editor
if se is None:
    sc.sequence_editor_create()
    se = sc.sequence_editor
strip = se.strips.new_movie("vid", video, 1, 1)
n = strip.frame_final_duration
print("MOVIE frames:", n, strip.elements[0].orig_width, strip.elements[0].orig_height, flush=True)
sc.render.resolution_x = strip.elements[0].orig_width
sc.render.resolution_y = strip.elements[0].orig_height
# fotogrammi subito dopo la schermata nera: campionamento fitto all'inizio
for i, f in enumerate([3, 6, 10, 16, 24, 35, 50, 70, 100, 150]):
    if f > n:
        continue
    sc.frame_set(f)
    sc.render.filepath = os.path.join(outdir, "video_campo_%02d_f%03d.png" % (i, f))
    bpy.ops.render.render(write_still=True)
    print("WROTE", sc.render.filepath, flush=True)
