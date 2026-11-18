"""render_seggiolini.py - verifica: seggiolini veri sui 3 anelli + scale chiuse.
Uso: blender -b -P scripts/prove/render_seggiolini.py (nessun argomento).
Scrive render/stadio_seggiolini.png e render/tunnel_scale_chiuse.png."""
import bpy
import json
import os
import sys

RADICE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RADICE, "scripts"))
import tunnel  # noqa: E402

RENDER_DIR = os.path.abspath(os.path.join(RADICE, "render"))
OUT_TEX = os.path.abspath(os.path.join(RADICE, "out_prova"))
os.makedirs(OUT_TEX, exist_ok=True)
dati = json.load(open(os.path.join(RADICE, "squadra.json"), encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)
tunnel.costruisci(dati, OUT_TEX)
print("STADIO costruito", flush=True)

sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 32
sc.cycles.use_denoising = True
sc.view_settings.view_transform = "Standard"
sc.view_settings.exposure = 0.0
sc.render.resolution_x = 960
sc.render.resolution_y = 540
sc.render.image_settings.file_format = "PNG"
w = bpy.data.worlds.new("MondoVerifica")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.62, 0.70, 0.80, 1.0)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
sc.world = w
bpy.ops.object.light_add(type="SUN", location=(30, -40, 50))
bpy.context.active_object.data.energy = 3.0


def camera(nome, pos, tgt, lens=24.0):
    from mathutils import Vector
    cd = bpy.data.cameras.new(nome)
    cd.lens = lens
    co = bpy.data.objects.new(nome, cd)
    sc.collection.objects.link(co)
    co.location = pos
    co.rotation_euler = (Vector((tgt[0] - pos[0], tgt[1] - pos[1], tgt[2] - pos[2])).to_track_quat("-Z", "Y").to_euler())
    sc.camera = co


def wloc(x, u, z):
    p = tunnel.w((x, u, z))
    return (float(p[0]), float(p[1]), float(p[2]))


# stessa vista del video: campo dall'uscita del tunnel
camera("CamSeggiolini", wloc(0.7, 34.0, 1.8), wloc(0.0, 18.0, 1.85), lens=24.0)
sc.render.filepath = os.path.join(RENDER_DIR, "stadio_seggiolini.png")
bpy.ops.render.render(write_still=True)
print("WROTE seggiolini", flush=True)
# interna: scalinata chiusa vista dal tunnel
camera("CamScale", wloc(0.0, 3.5, 1.62), wloc(0.0, 17.0, 0.9), lens=24.0)
sc.render.filepath = os.path.join(RENDER_DIR, "tunnel_scale_chiuse.png")
bpy.ops.render.render(write_still=True)
print("WROTE scale", flush=True)
print("SEGGIOLINI_OK", flush=True)
