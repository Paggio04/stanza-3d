import bpy, os
video = r"C:\Users\program02\Videos\Registrazione 2026-11-18 095402.mp4"
outdir = r"C:\Progetti\stanza-3d\render"
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_percentage = 75
sc.render.image_settings.file_format = "PNG"
se = sc.sequence_editor
if se is None:
    sc.sequence_editor_create()
    se = sc.sequence_editor
strip = se.strips.new_movie("vid2", video, 1, 1)
n = strip.frame_final_duration
print("MOVIE2 frames:", n, strip.elements[0].orig_width, strip.elements[0].orig_height, flush=True)
sc.render.resolution_x = strip.elements[0].orig_width
sc.render.resolution_y = strip.elements[0].orig_height
# 10 fotogrammi oltre ai 2 dell'utente (tunnel f1, sala f2): campionamento fitto su tutto il video
import math
idx = sorted(set([int(n * k / 11) for k in range(1, 11)]))
for i, f in enumerate(idx):
    f = max(1, min(n, f))
    sc.frame_set(f)
    sc.render.filepath = os.path.join(outdir, "video2_%02d_f%03d.png" % (i, f))
    bpy.ops.render.render(write_still=True)
    print("WROTE", sc.render.filepath, flush=True)
print("VIDEO2_OK", len(idx), flush=True)
