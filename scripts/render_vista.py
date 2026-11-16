"""Renderizza una vista dal blend base. Uso:
  blender -b spogliatoio_v01.blend -P scripts\\render_vista.py -- VISTA
VISTA: totale | dettaglio | fronte | girata"""
import bpy, os, sys
from math import radians
import math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER_DIR = os.path.join(ROOT, "render")
argv = sys.argv
VISTA = argv[argv.index("--") + 1] if "--" in argv else "totale"
SC = bpy.context.scene
try:
    SC.render.engine = "CYCLES"
    SC.cycles.device = "CPU"
    SC.cycles.samples = 48
    SC.cycles.use_denoising = True
except Exception:
    pass
try:
    SC.eevee.taa_samples = 1
except Exception:
    pass

BAR_Y, BAR_Z = 0.42, 1.78
J10X = bpy.data.objects["Maglia_10"].location.x

def shot(objs, locs, rots):
    for name, loc, rot in zip(objs, locs, rots):
        o = bpy.data.objects[name]
        o.location = loc
        o.rotation_euler = rot

BASE = {}
for o in bpy.data.objects:
    if o.name.startswith("Maglia_") or o.name.startswith("Gruccia_"):
        BASE[o.name] = (tuple(o.location), tuple(o.rotation_euler))

PLAN = {
    "totale": ("Cam_Totale", "v01_16x9.png", 1920, 1080),
    "dettaglio": ("Cam_Dettaglio", "v01_primo_piano.png", 1920, 1080),
    "fronte": ("Cam_Fronte", "v01_maglia_fronte.png", 1080, 1080),
    "girata": ("Cam_Totale", "v01_maglia_girata.png", 1920, 1080),
}
CAM, FILE, RX, RY = PLAN[VISTA]
if VISTA in ("fronte", "girata"):
    if "Maglia_10" not in bpy.data.objects:
        raise RuntimeError("Maglia_10 mancante nel blend")
if VISTA == "fronte":
    bpy.ops.object.camera_add(location=(0, 4.2, 1.35))
    cam = bpy.context.active_object
    cam.name = "Cam_Fronte"
    cam.data.lens = 55
    tgt = bpy.data.objects.new("tmp_f", None)
    SC.collection.objects.link(tgt)
    tgt.location = (0, 2.2, 1.28)
    c = cam.constraints.new("TRACK_TO")
    c.target = tgt
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    # luce frontale calda: illumina il petto (le POINT stanno dietro la maglia)
    bpy.ops.object.light_add(type="POINT", location=(0, 3.3, 1.7))
    lf = bpy.context.active_object
    lf.name = "PuntoFronte"
    lf.data.energy = 50
    lf.data.color = (1.0, 0.68, 0.42)
    try:
        lf.data.use_shadow = False
    except Exception:
        pass
    # maglia 10: sola, di PETTO (rot Z = 0 = petto +Y verso camera),
    # gruccia nascosta (hide_render), non davanti al petto
    m10 = bpy.data.objects["Maglia_10"]
    g10 = bpy.data.objects["Gruccia_10"]
    m10.location = (0, 2.2, 1.35)
    m10.rotation_euler = (0, 0, 0)
    g10.location = (0, 2.2, 1.35)
    g10.rotation_euler = (0, 0, 0)
    g10.hide_render = True
    SC.camera = bpy.data.objects[CAM]
    SC.render.resolution_x, SC.render.resolution_y = RX, RY
    SC.render.resolution_percentage = 100
    out = os.path.join(RENDER_DIR, FILE)
    SC.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("RENDER:", out)
    g10.hide_render = False
elif VISTA == "girata":
    # hover: petto PIENO frontale (rot 0) + 25 cm avanti + luce dedicata
    shot(["Maglia_10", "Gruccia_10"],
         [(J10X, BAR_Y + 0.25, BAR_Z)] * 2, [(0, 0, 0.0)] * 2)
    bpy.ops.object.light_add(type="POINT",
                             location=(J10X, BAR_Y + 1.1, BAR_Z + 0.3))
    lh = bpy.context.active_object
    lh.name = "PuntoHover10"
    lh.data.energy = 40
    lh.data.color = (1.0, 0.72, 0.45)
    try:
        lh.data.use_shadow = False
    except Exception:
        pass
    print("GIRATA Maglia_10:",
          tuple(round(v, 3) for v in bpy.data.objects["Maglia_10"].location),
          "rotz=%.1f" % math.degrees(
              bpy.data.objects["Maglia_10"].rotation_euler[2]))
    out = os.path.join(RENDER_DIR, FILE)
    if os.path.exists(out):
        print("SKIP (esiste):", out)
    else:
        SC.camera = bpy.data.objects[CAM]
        SC.render.resolution_x, SC.render.resolution_y = RX, RY
        SC.render.resolution_percentage = 100
        SC.render.filepath = out
        bpy.ops.render.render(write_still=True)
        print("RENDER:", out)
else:
    out = os.path.join(RENDER_DIR, FILE)
    if os.path.exists(out):
        print("SKIP (esiste):", out)
    else:
        SC.camera = bpy.data.objects[CAM]
        SC.render.resolution_x, SC.render.resolution_y = RX, RY
        SC.render.resolution_percentage = 100
        SC.render.filepath = out
        bpy.ops.render.render(write_still=True)
        print("RENDER:", out)
    bpy.ops.render.render(write_still=True)
    print("RENDER:", out)
