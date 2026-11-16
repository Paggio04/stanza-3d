"""Spogliatoio v01 - CORREZIONE (sostituisce l'aggiunta precedente).
Ricostruisce da zero: barra con 20 maglie di sbieco, targhe reparto,
luce sera, 4 render. Esegui da C:\\Progetti\\stanza-3d:
  blender -b -P scripts\\spogliatoio_v01.py
Geometria maglia (locale): petto = +Y (scudo, interno colletto davanti),
schiena = -Y, maniche lungo X. Rotazione Z delle maglie: 0 = petto alla
camera, 115 = tre quarti di schiena (65 dalla schiena), 160 = quasi di
schiena (20 dalla schiena, prima di ogni reparto), hover ~ -8 petto avanti.
"""
import bpy, bmesh, json, math, os
from math import radians, cos, sin, pi
from mathutils import Vector, Matrix, Quaternion

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "squadra.json"), encoding="utf-8") as f:
    DATA = json.load(f)
RENDER_DIR = os.path.join(ROOT, "render")
BLEND_PATH = os.path.join(ROOT, "spogliatoio_v01.blend")

ANG_REST = radians(115.0)   # rot Z: tre quarti di schiena
ANG_LEAD = radians(160.0)   # rot Z: quasi di schiena (prima a sinistra)
ANG_HOVER = radians(0.0)    # rot Z hover: petto pieno frontale (max contrasto)
HOVER_DY = 0.25             # ...e 25 cm piu' avanti
BAR_Y, BAR_Z = 0.42, 1.78
GAP_IN, GAP_GROUP = 0.02, 0.35
JERSEY_W, JERSEY_T = 0.76, 0.11

def hx_of(phi):
    return (JERSEY_W * abs(cos(phi)) + JERSEY_T * abs(sin(phi))) / 2.0

# ---------- layout: intervalli X impaccati, niente compenetrazioni ----------
order = [r["nome"] for r in DATA["reparti"]]
by_num = {g["numero"]: g for g in DATA["giocatori"]}
JERSEYS, GROUPS = [], {}
for g in DATA["reparti"]:
    GROUPS[g["nome"]] = []
    for k, n in enumerate(g["numeri"]):
        # leader = prima del reparto in ordine di numero = la piu' a sinistra
        # per chi guarda (la scena e' specchiata in X apposta: +X a sinistra)
        lead = (k == 0)
        phi = ANG_LEAD if lead else ANG_REST
        JERSEYS.append({"numero": n, "reparto": g["nome"], "leader": lead,
                        "phi": phi, "hx": hx_of(phi),
                        "maglia": "Maglia_%02d" % n, "gruccia": "Gruccia_%02d" % n})
        GROUPS[g["nome"]].append(JERSEYS[-1])
xs, cur = [], 0.0
for i, j in enumerate(JERSEYS):
    cur += j["hx"] if i == 0 else JERSEYS[i - 1]["hx"] + j["hx"] + \
        (GAP_GROUP if j["reparto"] != JERSEYS[i - 1]["reparto"] else GAP_IN)
    xs.append(cur)
span = cur + JERSEYS[-1]["hx"]
off = span / 2.0
for j, x in zip(JERSEYS, xs):
    # X negata: +X appare a sinistra da camera, cosi' l'ordine a video
    # e' PORTIERI ... ATTACCANTI come in squadra.json
    j["x"] = off - x
X_MIN = JERSEYS[0]["x"] - JERSEYS[0]["hx"]
X_MAX = JERSEYS[-1]["x"] + JERSEYS[-1]["hx"]
for name, members in GROUPS.items():
    GROUPS[name] = {"members": members,
                    "cx": sum(m["x"] for m in members) / len(members),
                    "n": len(members)}
J10 = next(j for j in JERSEYS if j["numero"] == 10)
print("LAYOUT span=%.2f m  x=[%.2f, %.2f]  J10 x=%.2f" % (span, X_MIN, X_MAX, J10["x"]))
# ---------- scena, materiali, stanze ----------
def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
SC = bpy.context.scene
# hq con Cycles: EEVEE slavava i rossi contro le doghe
try:
    SC.render.engine = "CYCLES"
    SC.cycles.device = "CPU"
    SC.cycles.samples = 48
    SC.cycles.use_denoising = True
except Exception:
    try:
        SC.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        SC.render.engine = "BLENDER_EEVEE"
SC.render.film_transparent = False
SC.render.image_settings.file_format = "PNG"
try:
    SC.view_settings.view_transform = "Filmic"
    SC.view_settings.exposure = -1.2
    SC.cycles.samples = 48
    SC.eevee.taa_render_samples = 64
except Exception:
    pass
W = bpy.data.worlds["World"]
W.use_nodes = True
bg = W.node_tree.nodes.get("Background")
if bg is not None:
    bg.inputs[0].default_value = (0.004, 0.004, 0.007, 1.0)
    bg.inputs[1].default_value = 1.0

def pmat(name, rgb, rough=0.8, metallic=0.0, ecol=None, estr=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    try:
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metallic
        if ecol is not None:
            b.inputs["Emission Color"].default_value = (*ecol, 1.0)
            b.inputs["Emission Strength"].default_value = estr
    except Exception:
        pass
    return m

def emat(name, rgb, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    n = nt.nodes
    e = n.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*rgb, 1.0)
    e.inputs["Strength"].default_value = strength
    out = n.get("Material Output")
    nt.links.new(e.outputs["Emission"], out.inputs["Surface"])
    try:
        n.remove(n.get("Principled BSDF"))
    except Exception:
        pass
    return m

C = DATA["colori"]
M_BASE = pmat("M_Maglia", hexrgb(C["maglia"]), 0.85)
M_PORT = pmat("M_Portieri", hexrgb(C["portieri"]), 0.85)
M_DETT = pmat("M_Dettagli", hexrgb(C["dettagli"]), 0.7)
M_SCUDO = pmat("M_Scudo", hexrgb("#c9a227"), 0.4, 0.6)
M_INT = pmat("M_Interno", hexrgb("#101114"), 0.95)
M_GRU = pmat("M_Gruccia", hexrgb("#1a1b1e"), 0.5)
M_CROMO = pmat("M_Cromo", (0.75, 0.77, 0.8), 0.25, 1.0)
M_LEGNO = pmat("M_Legno", hexrgb("#2a1c12"), 0.8)
M_MURO = pmat("M_Muro", hexrgb("#33333a"), 0.95)
M_PAV = pmat("M_Pavimento", hexrgb("#17181c"), 0.55, 0.1)
M_TARGA = pmat("M_Targa", hexrgb("#201d18"), 0.6)
M_TESTO = pmat("M_Testo", hexrgb(C["dettagli"]), 0.6,
               ecol=hexrgb(C["dettagli"]), estr=0.7)
M_WARM = emat("M_StrisciaCalda", (1.0, 0.62, 0.30), 3.0)
M_BLUE = emat("M_StrisciaBlu", (0.30, 0.50, 1.0), 1.6)

def box(name, sx, sy, sz, loc, mat, rot=None):
    bpy.ops.mesh.primitive_cube_add(location=loc,
                                    rotation=rot or (0, 0, 0))
    o = bpy.context.active_object
    o.name = name
    o.scale = (sx / 2.0, sy / 2.0, sz / 2.0)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(mat)
    return o

def tube(name, p1, p2, r, mat):
    d = Vector(p2) - Vector(p1)
    ln = d.length
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=ln,
                                        location=(Vector(p1) + Vector(p2)) / 2)
    o = bpy.context.active_object
    o.name = name
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    o.rotation_mode = "XYZ"
    o.data.materials.append(mat)
    return o

def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    j = bpy.context.active_object
    j.name = name
    return j

# ---------- stanze: muro, doghe di legno scuro, pavimento, strisce luce --
# (niente soffitto: si vedeva come fascia nera nel render 16x9)
WALL_W = span + 2.6
muro = box("Muro", WALL_W, 0.1, 9.0, (0, -0.05, 4.5), M_MURO)
# pavimento lungo anche dietro la camera (y=11): niente vuoto inquadrato
pav = box("Pavimento", WALL_W + 2, 16.0, 0.1, (0, 6.4, -0.05), M_PAV)
slats = []
x = -span / 2 - 0.8
while x <= span / 2 + 0.8:
    slats.append(box("Doga", 0.12, 0.03, 2.6, (x, 0.03, 1.3), M_LEGNO))
    x += 0.17
join(slats, "Parete_Doghe")
box("StrisciaCalda", span + 1.2, 0.04, 0.10, (0, 0.06, 2.38), M_WARM)
box("StrisciaBlu", span + 1.2, 0.05, 0.05, (0, 0.06, 0.07), M_BLUE)
# ---------- barra con piega a gomito verso il muro ----------
bar_segs = [tube("Barra_tmp", (X_MIN - 0.25, BAR_Y, BAR_Z),
                 (X_MAX + 0.15, BAR_Y, BAR_Z), 0.021, M_CROMO),
            tube("Barra_tmp", (X_MAX + 0.15, BAR_Y, BAR_Z),
                 (X_MAX + 0.15, 0.06, BAR_Z), 0.021, M_CROMO)]
BARRA = join(bar_segs, "Barra")
for p, q in [((X_MIN - 0.25, BAR_Y, 0.0), (X_MIN - 0.25, BAR_Y, BAR_Z)),
             ((X_MAX + 0.15, 0.06, 0.0), (X_MAX + 0.15, 0.06, BAR_Z))]:
    box("Staffa", 0.05, 0.05, 0.06, ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2,
        (p[2] + q[2]) / 2), M_CROMO)

# ---------- gruccia (oggetto separato, condivide origine sul gancio) ----------
def make_hanger(name, mat):
    parts = [tube("tmp", (0, 0, 0), (0, 0, 0.09), 0.008, mat),
             tube("tmp", (-0.24, 0, -0.10), (0, 0, 0.02), 0.011, mat),
             tube("tmp", (0.24, 0, -0.10), (0, 0, 0.02), 0.011, mat),
             tube("tmp", (-0.24, 0, -0.10), (0.24, 0, -0.10), 0.008, mat)]
    return join(parts, name)

# ---------- maglia (oggetto separato, completa anche davanti) ----------
def make_jersey(name, base_mat):
    b = base_mat
    parts = [
        box("tmp", 0.44, 0.10, 0.62, (0, 0, -0.42), b),        # busto
        box("tmp", 0.46, 0.11, 0.10, (0, 0, -0.15), b),        # spalle
        box("tmp", 0.15, 0.09, 0.30, (-0.295, 0, -0.30), b),   # manica L
        box("tmp", 0.15, 0.09, 0.30, (0.295, 0, -0.30), b),    # manica R
        box("tmp", 0.16, 0.10, 0.05, (-0.295, 0, -0.43), M_DETT),
        box("tmp", 0.16, 0.10, 0.05, (0.295, 0, -0.43), M_DETT),
        # scudo segnaposto: placca sul PETTO locale (+Y), a sinistra;
        # il petto +Y guarda la camera con rot Z=0 (fronte/hover)
        box("tmp", 0.09, 0.02, 0.12, (-0.10, 0.055, -0.16), M_SCUDO),
        # colletto: apertura scura in alto + bordi
        box("tmp", 0.13, 0.09, 0.06, (0, 0, -0.11), M_INT),
        box("tmp", 0.05, 0.095, 0.06, (-0.085, 0, -0.11), b),
        box("tmp", 0.05, 0.095, 0.06, (0.085, 0, -0.11), b),
        box("tmp", 0.18, 0.02, 0.05, (0, 0.05, -0.10), b),   # bordo collo petto
        box("tmp", 0.18, 0.02, 0.05, (0, -0.05, -0.10), b),  # bordo collo retro
    ]
    return join(parts, name)

for j in JERSEYS:
    g = make_hanger(j["gruccia"], M_GRU)
    base = M_PORT if j["reparto"] == "PORTIERI" else M_BASE
    m = make_jersey(j["maglia"], base)
    for o in (g, m):
        o.location = (j["x"], BAR_Y, BAR_Z)
        o.rotation_euler = (0, 0, j["phi"])
    # origine di maglia+gruccia sul gancio: ruotano insieme
    bpy.ops.object.select_all(action="DESELECT")

# verifica: nessuna compenetrazione fra maglie adiacenti (in ordine di X)
ok = True
per_x = sorted(JERSEYS, key=lambda j: j["x"])
for i in range(1, len(per_x)):
    a, b = per_x[i - 1], per_x[i]
    # il gap di reparto dipende dalla coppia di reparti adiacenti a video
    gap_ab = GAP_IN if a["reparto"] == b["reparto"] else GAP_GROUP
    need = a["hx"] + b["hx"] + gap_ab - 1e-6
    if (b["x"] - a["x"]) < need:
        ok = False
        print("COMPENETRAZIONE: %s-%s" % (a["maglia"], b["maglia"]))
print("INTERPENETRATION_CHECK:", "OK" if ok else "FAIL")
groups_x = " | ".join("%s %d @%.2f" % (n, GROUPS[n]["n"], GROUPS[n]["cx"])
                      for n in order)
print("GRUPPI:", groups_x)
# ---------- targhe reparto sul muro (nome + quante maglie) ----------
def make_plaque(key, text, cx):
    w = max(0.70, 0.075 * len(text))
    p = box("Targa_%s" % key.title(), w, 0.03, 0.16, (cx, 0.06, 2.19), M_TARGA)
    bpy.ops.object.text_add(location=(cx, 0.085, 2.19))
    t = bpy.context.active_object
    t.name = "Targa_Testo_%s" % key.title()
    t.data.body = text
    t.data.align_x = "CENTER"
    t.data.extrude = 0.004
    try:
        t.data.size = 0.10
    except Exception:
        pass
    # testo dritto sul muro: normale +Y (verso camera), alto +Z
    t.rotation_mode = "QUATERNION"
    q1 = Vector((0, 0, 1)).rotation_difference(Vector((0, 1, 0)))
    t.rotation_quaternion = Quaternion((0, 0, 1, 0)) @ q1
    t.data.materials.append(M_TESTO)
    return p, t

for r in DATA["reparti"]:
    n = r["nome"]
    make_plaque(n, "%s %d" % (n, GROUPS[n]["n"]), GROUPS[n]["cx"])

# ---------- luce sera: calda sopra/dietro, blu in basso, penombra ----------
def lamp(name, kind, energy, loc, color, size=0.5, angle=0.9, target=None,
         target_xyz=None, shadow=False):
    bpy.ops.object.light_add(type=kind, location=loc)
    L = bpy.context.active_object
    L.name = name
    if target_xyz is not None:
        tgt = bpy.data.objects.new("tgt_%s" % name, None)
        SC.collection.objects.link(tgt)
        tgt.location = target_xyz
        target = tgt
    # luci mai visibili in camera (in Cycles: oggetti invisibili ai raggi camera)
    try:
        L.visible_camera = False
    except Exception:
        pass
    try:
        L.data.use_shadow = shadow
    except Exception:
        pass
    L.data.energy = energy
    L.data.color = color
    try:
        if kind == "AREA":
            L.data.size = size
        if kind == "SPOT":
            L.data.spot_size = angle
    except Exception:
        pass
    if target is not None:
        c = L.constraints.new("TRACK_TO")
        c.target = target
        c.track_axis = "TRACK_NEGATIVE_Z"
        c.up_axis = "UP_Y"
    return L

# luci: niente AREA (i loro quad finivano inquadrati dalla camera).
# Wash generale con SUN (paralleli, niente decadimento, mai inquadrati);
# luce sulle maglie con POINT vicini alla barra, senza ombre; dramma con
# uno SPOT con ombra sulla maglia 10.
SC.world.node_tree.nodes.get("Background").inputs[1].default_value = 1.0
lamp("SoleCaldo", "SUN", 0.22, (0, 8.0, 9.0), (1.0, 0.62, 0.35),
     target_xyz=(0, 0.0, 1.4))
lamp("SoleFreddoCam", "SUN", 0.06, (0, 11.0, 4.0), (0.55, 0.65, 0.9),
     target_xyz=(0, 0.0, 1.0))
PX = [-5.0, -2.5, 0.0, 2.5, 5.0]
for i, px in enumerate(PX):
    lamp("PuntoCaldo%d" % i, "POINT", 60, (px, 1.6, 2.3), (1.0, 0.63, 0.36))
lamp("SpotMaglia10", "SPOT", 80, (J10["x"], 1.9, 2.9), (1.0, 0.8, 0.6),
     angle=0.5, target=bpy.data.objects["Maglia_10"], shadow=True)
lamp("LuceBluPavimento", "POINT", 60, (0.5, 0.8, 0.35), (0.30, 0.50, 1.0))

# ---------- camere ----------
def camera(name, loc, target_xyz, lens=50):
    bpy.ops.object.camera_add(location=loc)
    cm = bpy.context.active_object
    cm.name = name
    cm.data.lens = lens
    tgt = bpy.data.objects.new("tmp_tgt", None)
    SC.collection.objects.link(tgt)
    tgt.location = target_xyz
    c = cm.constraints.new("TRACK_TO")
    c.target = tgt
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    return cm

CAM_ALL = camera("Cam_Totale", (0, 7.2, 1.35), (0, 0.1, 1.35), lens=26)
CAM_DET = camera("Cam_Dettaglio", (J10["x"], 7.5, 1.45),
                 (J10["x"], BAR_Y, 1.30), lens=110)

# ---------- render ----------
def render(path, cam, rx, ry):
    if os.path.exists(path):
        print("SKIP (esiste):", path)
        return
    SC.camera = cam
    SC.render.resolution_x, SC.render.resolution_y = rx, ry
    SC.render.resolution_percentage = 100
    SC.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("RENDER:", path)

MAG = {j["maglia"]: (bpy.data.objects[j["maglia"]],
      bpy.data.objects[j["gruccia"]]) for j in JERSEYS}

def set_rest():
    for j in JERSEYS:
        for o in MAG[j["maglia"]]:
            o.location = (j["x"], BAR_Y, BAR_Z)
            o.rotation_euler = (0, 0, j["phi"])

bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

BUILD_ONLY = os.environ.get("V01_BUILD_ONLY") == "1"
if BUILD_ONLY:
    print("BUILD_ONLY: scena salvata, nessun render.")
else:
    set_rest()
    render(os.path.join(RENDER_DIR, "v01_16x9.png"), CAM_ALL, 1920, 1080)
    render(os.path.join(RENDER_DIR, "v01_primo_piano.png"), CAM_DET, 1920, 1080)

# v01_maglia_girata: maglia 10 verso camera e 25 cm avanti (hover)
if not BUILD_ONLY:
    for o in MAG["Maglia_10"]:
        o.location = (J10["x"], BAR_Y + HOVER_DY, BAR_Z)
        o.rotation_euler = (0, 0, ANG_HOVER)
    render(os.path.join(RENDER_DIR, "v01_maglia_girata.png"), CAM_ALL, 1920, 1080)
    set_rest()

# v01_maglia_fronte: maglia 10 staccata, petto alla camera (1080x1080)
if not BUILD_ONLY:
    for o in MAG["Maglia_10"]:
        o.location = (0, 2.2, 1.35)
        o.rotation_euler = (0, 0, 0)
    CAM_F = camera("Cam_Fronte", (0, 3.15, 1.35), (0, 2.2, 1.30), lens=55)
    render(os.path.join(RENDER_DIR, "v01_maglia_fronte.png"), CAM_F, 1080, 1080)
print("FINITO. blend:", BLEND_PATH)

