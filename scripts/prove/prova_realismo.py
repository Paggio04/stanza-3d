"""prova_realismo.py - render di confronto Cycles: campo, tunnel, armadietto.
Uso: blender -b -P scripts/prove/prova_realismo.py (nessun argomento).
Scrive in render/prova_realismo_*.png (percorsi assoluti)."""
import bpy
import json
import math
import os
import sys

RADICE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RADICE, "scripts"))
import maglia  # noqa: E402
import sala  # noqa: E402
import tunnel  # noqa: E402

RENDER_DIR = os.path.abspath(os.path.join(RADICE, "render"))
OUT_TEX = os.path.abspath(os.path.join(RADICE, "out_prova"))
os.makedirs(OUT_TEX, exist_ok=True)

dati = json.load(open(os.path.join(RADICE, "squadra.json"), encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)

lista = sala.costruisci_sala(dati)
print("SALA armadietti:", len(lista), flush=True)
ob_t = tunnel.costruisci(dati, OUT_TEX)
print("TUNNEL costruito", flush=True)

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
# mondo chiaro neutro
w = bpy.data.worlds.new("ProvaMondo")
w.use_nodes = True
bg = w.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.75, 0.78, 0.82, 1.0)
bg.inputs[1].default_value = 0.6
sc.world = w
# sole
bpy.ops.object.light_add(type="SUN", location=(20, -30, 40))
sole = bpy.context.active_object
sole.data.energy = 3.0


def camera(nome, pos, tgt, lens=24.0):
    cd = bpy.data.cameras.new(nome)
    cd.lens = lens
    co = bpy.data.objects.new(nome, cd)
    sc.collection.objects.link(co)
    co.location = pos
    d = (tgt[0] - pos[0], tgt[1] - pos[1], tgt[2] - pos[2])
    from mathutils import Vector
    co.rotation_euler = Vector(d).to_track_quat("-Z", "Y").to_euler()
    sc.camera = co
    return co


def wloc(x, u, z):
    import numpy as np
    p = tunnel.w((x, u, z))
    return (float(p[0]), float(p[1]), float(p[2]))


# 1. campo: come il percorso, vicino alla bocca
camera("CamCampo", wloc(0.7, 34.0, 1.8), wloc(0.0, 18.0, 1.85), lens=24.0)
sc.render.filepath = os.path.join(RENDER_DIR, "prova_realismo_campo.png")
bpy.ops.render.render(write_still=True)
print("WROTE campo", flush=True)
# 2. interno tunnel
camera("CamTunnel", wloc(0.0, 3.5, 1.62), wloc(0.0, -6.0, 1.55), lens=24.0)
sc.render.filepath = os.path.join(RENDER_DIR, "prova_realismo_tunnel.png")
bpy.ops.render.render(write_still=True)
print("WROTE tunnel", flush=True)
# 3. armadietto della 10 di fronte
camera("CamSala", (0.0, -3.3, 1.55), (0.0, 4.4, 1.45), lens=28.0)
sc.render.filepath = os.path.join(RENDER_DIR, "prova_realismo_sala.png")
bpy.ops.render.render(write_still=True)
print("WROTE sala", flush=True)
print("PROVA_REALISMO_OK", flush=True)
