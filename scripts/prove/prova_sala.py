"""prova_sala.py - render Cycles della sola sala (campo/tunnel esclusi): 2 viste.
Uso: blender -b -P scripts/prove/prova_sala.py (nessun argomento).
Scrive render/prova_sala_34.png e render/prova_sala_fronte.png (assoluti)."""
import bpy
import json
import math
import os
import sys

RADICE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RADICE, "scripts"))
import sala  # noqa: E402

RENDER_DIR = os.path.abspath(os.path.join(RADICE, "render"))
dati = json.load(open(os.path.join(RADICE, "squadra.json"), encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)
lista = sala.costruisci_sala(dati)
print("SALA armadietti:", len(lista), flush=True)

sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 32
sc.cycles.use_denoising = True
sala.luci_e_mondo(sc)
sc.cycles.samples = 32
sc.render.resolution_x = 960
sc.render.resolution_y = 540
sc.render.image_settings.file_format = "PNG"


def camera(nome, pos, tgt, lens=24.0):
    from mathutils import Vector
    cd = bpy.data.cameras.new(nome)
    cd.lens = lens
    co = bpy.data.objects.new(nome, cd)
    sc.collection.objects.link(co)
    co.location = pos
    co.rotation_euler = (Vector((tgt[0] - pos[0], tgt[1] - pos[1], tgt[2] - pos[2])).to_track_quat("-Z", "Y").to_euler())
    sc.camera = co


# vista come il sito: dal centro verso gli 11 titolari
camera("Cam34", (0.6, -3.0, 1.7), (0.0, 4.2, 1.3), lens=20.0)
sc.render.filepath = os.path.join(RENDER_DIR, "prova_sala_34.png")
bpy.ops.render.render(write_still=True)
print("WROTE sala_34", flush=True)
camera("CamFronte", (0.0, -2.2, 1.55), (0.0, 4.4, 1.5), lens=28.0)
sc.render.filepath = os.path.join(RENDER_DIR, "prova_sala_fronte.png")
bpy.ops.render.render(write_still=True)
print("WROTE sala_fronte", flush=True)
print("PROVA_SALA_OK", flush=True)
