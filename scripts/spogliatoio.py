"""Spogliatoio v03 - un armadietto con la maglia vera.
Uso: blender -b -P scripts/spogliatoio.py
Dati solo da squadra.json. Unita' metri, Z su. Petto=+Y schiena=-Y (locale).
"""
import bpy
import bmesh
import json
import math
import os
import random
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "squadra.json"), encoding="utf-8") as f:
    DATA = json.load(f)
RENDER_DIR = os.path.join(ROOT, "render")
BLEND_PATH = os.path.join(ROOT, "spogliatoio.blend")
FONT_PATH = "C:/Windows/Fonts/arialbd.ttf"
random.seed(7)

C = DATA["colori"]
G10 = next(g for g in DATA["giocatori"] if g["numero"] == 10)

REG = {}


def log(m):
    print(m, flush=True)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for blk in list(bpy.data.meshes):
    if blk.users == 0:
        bpy.data.meshes.remove(blk)
for blk in list(bpy.data.materials):
    if blk.users == 0:
        bpy.data.materials.remove(blk)

SC = bpy.context.scene
SC.render.engine = "CYCLES"
SC.cycles.device = "CPU"
SC.cycles.samples = 128
try:
    SC.cycles.use_denoising = True
except Exception:
    pass
SC.render.film_transparent = False
SC.render.image_settings.file_format = "PNG"
try:
    SC.view_settings.view_transform = "Filmic"
    SC.view_settings.exposure = 0.0
except Exception:
    pass
W = bpy.data.worlds["World"]
W.use_nodes = True
bgnode = W.node_tree.nodes.get("Background")
if bgnode is not None:
    bgnode.inputs[0].default_value = (0.45, 0.45, 0.46, 1.0)
    try:
        bgnode.inputs[1].default_value = 1.0
    except Exception:
        pass


def pmat(name, rgb, rough=0.8, metallic=0.0, ecol=None, estr=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = None
    for _nn in m.node_tree.nodes:
        if _nn.type == "BSDF_PRINCIPLED":
            bsdf = _nn
            break
    if bsdf is not None:
        for _kk, _vv in (("Base Color", (*rgb, 1.0)), ("Roughness", rough)):
            try:
                bsdf.inputs[_kk].default_value = _vv
            except Exception:
                pass
        try:
            bsdf.inputs["Metallic"].default_value = metallic
        except Exception:
            pass
        if ecol is not None:
            for _kk, _vv in (("Emission Color", (*ecol, 1.0)),
                             ("Emission Strength", estr)):
                try:
                    bsdf.inputs[_kk].default_value = _vv
                except Exception:
                    pass
    return m


M_BASE = pmat("M_Maglia", hexrgb(C["maglia"]), 0.65)
M_DETT = pmat("M_Dettagli", hexrgb(C["dettagli"]), 0.5)
M_SCRIT = pmat("M_Scritte", hexrgb(C["scritte"]), 0.5)
M_SCUDO = pmat("M_Scudo", hexrgb("#9aa0a6"), 0.5, 0.0)
M_GRU = pmat("M_Gruccia", hexrgb("#3a3b3d"), 0.6)
M_CROMO = pmat("M_Cromo", (0.75, 0.77, 0.8), 0.25, 1.0)
M_LEGNO = pmat("M_Legno", hexrgb("#7c5230"), 0.7)
M_BIANCO = pmat("M_Bianco", hexrgb("#e8e9eb"), 0.6)
M_NICCHIA = pmat("M_Nicchia", hexrgb("#3a3b3e"), 0.9)
M_PAV = pmat("M_Pavimento", hexrgb("#cfd2d6"), 0.3, 0.0)
M_SEDUTA = pmat("M_Seduta", hexrgb("#eceff1"), 0.55)
M_FOTO = pmat("M_Foto", hexrgb("#9aa0a6"), 0.8)
M_BIANCO_T = pmat("M_TestoBianco", (1.0, 1.0, 1.0), 0.5,
                  ecol=(1.0, 1.0, 1.0), estr=0.35)
M_BORR = pmat("M_Borraccia", hexrgb("#7fb3d5"), 0.4)
M_SCARPA = pmat("M_Scarpa", hexrgb("#1c1d20"), 0.6)
M_SUOLA = pmat("M_Suola", hexrgb("#f2f2f2"), 0.6)


def trama(mp):
    nt = mp.node_tree
    bsdf = None
    for _nn in nt.nodes:
        if _nn.type == "BSDF_PRINCIPLED":
            bsdf = _nn
            break
    if bsdf is None:
        return
    try:
        tex = nt.nodes.new("ShaderNodeTexCoord")
        wave = nt.nodes.new("ShaderNodeTexWave")
        wave.wave_type = "BANDS"
        wave.bands_direction = "Z"
        wave.inputs["Scale"].default_value = 260.0
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.18
        bump.inputs["Distance"].default_value = 0.0006
        nt.links.new(tex.outputs["UV"], wave.inputs["Vector"])
        nt.links.new(wave.outputs["Color"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    except Exception as ee:
        print("trama link ko: %r" % (ee,), flush=True)


for _mp in (M_BASE, M_DETT, M_SCRIT):
    try:
        trama(_mp)
    except Exception as e:
        log("trama ko su %s: %r" % (_mp.name, e))
for _mp in (M_BASE,):
    try:
        _b = None
        for _nn in _mp.node_tree.nodes:
            if _nn.type == "BSDF_PRINCIPLED":
                _b = _nn
                break
        if _b is not None:
            _b.inputs["Sheen Weight"].default_value = 0.35
    except Exception:
        pass
# __P2__ maglia: contorno campionato, pannelli, saldature
BW, BLEN = 0.52, 0.72
SL = 0.20
SH_Z = 0.62
FOND_Z = SH_Z - BLEN
NECK_HW = 0.075
NECK_F, NECK_B = 0.08, 0.025
TOP_F = SH_Z - 0.039
TOP_B = SH_Z - 0.012
SP_X0, SP_X1 = NECK_HW, BW / 2.0
SL_ANG = math.radians(50.0)
ARM_W, CUFF_W = 0.20, 0.15
GF, GB = 0.0, -0.06
STEP = 0.015


def spalla_zf(x):
    ax = min(abs(x), SP_X1)
    if ax <= SP_X0:
        return TOP_F
    return TOP_F + (ax - SP_X0) / (SP_X1 - SP_X0) * (SH_Z - TOP_F)


def spalla_zb(x):
    ax = min(abs(x), SP_X1)
    if ax <= SP_X0:
        return TOP_B
    return TOP_B + (ax - SP_X0) / (SP_X1 - SP_X0) * (SH_Z - TOP_B)


def sleeve_frame(sgn):
    o = Vector((sgn * SP_X1, 0.0, SH_Z))
    u = Vector((sgn * math.cos(SL_ANG), 0.0, -math.sin(SL_ANG)))
    w = Vector((sgn * math.sin(SL_ANG), 0.0, math.cos(SL_ANG)))
    return o, u, w


def sleeve_half(su):
    t = min(1.0, max(0.0, su / SL))
    return (ARM_W / 2.0) * (1.0 - t) + (CUFF_W / 2.0) * t


def campiona(p0, p1, step=STEP):
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    n = max(1, int(round(L / step)))
    return [(p0[0] + (p1[0] - p0[0]) * i / n,
             p0[1] + (p1[1] - p0[1]) * i / n) for i in range(n + 1)]


def ellisse(cx, cz, a, b, a0, a1, n):
    out = []
    for i in range(n + 1):
        t = a0 + (a1 - a0) * i / n
        out.append((cx + a * math.cos(t), cz + b * math.sin(t)))
    return out


def contorno(front):
    NECK = NECK_F if front else NECK_B
    TOP = TOP_F if front else TOP_B
    dx = []
    dx += campiona((-BW / 2.0, FOND_Z), (BW / 2.0, FOND_Z))
    dx += campiona((BW / 2.0, FOND_Z), (BW / 2.0 - 0.02, SH_Z - 0.17))[1:]
    o, u, w = sleeve_frame(1.0)
    cB = (o.x + u.x * SL - w.x * CUFF_W, o.z + u.z * SL - w.z * CUFF_W)
    cT = (o.x + u.x * SL, o.z + u.z * SL)
    dx += campiona((BW / 2.0 - 0.02, SH_Z - 0.17), cB)[1:]
    dx += campiona(cB, cT)[1:]
    dx += campiona(cT, (SP_X1, SH_Z))[1:]
    dx += campiona((SP_X1, SH_Z), (SP_X0, TOP))[1:]
    dx += ellisse(0.0, TOP, NECK_HW, NECK, 0.0, math.pi, 12)[1:]
    dx += campiona((-SP_X0, TOP), (-SP_X1, SH_Z))[1:]
    o2, u2, w2 = sleeve_frame(-1.0)
    cT2 = (o2.x + u2.x * SL, o2.z + u2.z * SL)
    cB2 = (o2.x + u2.x * SL - w2.x * CUFF_W, o2.z + u2.z * SL - w2.z * CUFF_W)
    dx += campiona((-SP_X1, SH_Z), cT2)[1:]
    dx += campiona(cT2, cB2)[1:]
    dx += campiona(cB2, (-BW / 2.0 + 0.02, SH_Z - 0.17))[1:]
    dx += campiona((-BW / 2.0 + 0.02, SH_Z - 0.17),
                   (-BW / 2.0, FOND_Z))[1:]
    return dx


OUT_F = contorno(True)
OUT_B = contorno(False)
log("contorno: %d punti fronte, %d retro" % (len(OUT_F), len(OUT_B)))
# __P3__ pannello con triangle_fill + suddivisione lati <= 2cm
# (bordo: vertici originali, niente smooth)
def pannello(outline, y0):
    me = bpy.data.meshes.new("tmp_pan")
    bm = bmesh.new()
    vs = [bm.verts.new((x, y0, z)) for (x, z) in outline]
    bm.verts.ensure_lookup_table()
    try:
        bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False,
                                edges=[bm.edges.new((vs[i], vs[(i + 1) % len(vs)]))
                                       for i in range(len(vs))])
    except Exception as e:
        log("triangle_fill ko: %r" % (e,))
    bordo_idx = set(v.index for v in vs)
    for _it in range(60):
        long_e = [e for e in bm.edges
                  if (e.verts[0].co - e.verts[1].co).length > 0.02]
        if not long_e:
            break
        bmesh.ops.subdivide_edges(bm, edges=long_e, cuts=1, use_grid_fill=True)
        bm.verts.ensure_lookup_table()
    for _p in range(3):
        for v in list(bm.verts):
            if v.index in bordo_idx or len(v.link_edges) == 0:
                continue
            nb = [e.other_vert(v) for e in v.link_edges]
            c = Vector((0.0, 0.0, 0.0))
            for n in nb:
                c += n.co
            v.co = (v.co + c / len(nb)) / 2.0
    bm.verts.ensure_lookup_table()
    bm.to_mesh(me)
    bm.free()
    ntri = len(me.polygons)
    log("pannello y=%.2f: %d tri" % (y0, ntri))
    return me


ME_F = pannello(OUT_F, GF)
ME_B = pannello(OUT_B, GB)


def bordo_set(me, outline):
    pts = [(x, z) for (x, z) in outline]
    bs = set()
    for v in me.vertices:
        for (x, z) in pts:
            if abs(v.co.x - x) < 0.004 and abs(v.co.z - z) < 0.004:
                bs.add(v.index)
                break
    return bs


BF = bordo_set(ME_F, OUT_F)
BB = bordo_set(ME_B, OUT_B)


def cuciture(outline):
    sp, up, dn, fi = [], [], [], []
    for (x, z) in outline:
        ax = abs(x)
        if SP_X0 <= ax <= SP_X1 and z > SH_Z - 0.06:
            sp.append((x, z))
        elif ax > BW / 2.0 - 0.03 and z > SH_Z - 0.20:
            o, u, w = sleeve_frame(1.0 if x > 0 else -1.0)
            rel = Vector((x, 0.0, z)) - o
            sw = rel.dot(w)
            if sw > -0.10:
                up.append((x, z))
            else:
                dn.append((x, z))
        elif abs(ax - BW / 2.0) < 0.035:
            fi.append((x, z))
    return {"spalla": sp, "sopra": up, "sotto": dn, "fianco": fi}


CF, CB = cuciture(OUT_F), cuciture(OUT_B)
# __P4__ saldo 1 a 1 solo cuciture (fondo/collo/polsi aperti) + mesh unica
def vicino(me, bset, pt):
    best, bd = -1, 1e9
    for v in me.vertices:
        if v.index not in bset:
            continue
        d = math.hypot(v.co.x - pt[0], v.co.z - pt[1])
        if d < bd:
            bd, best = d, v.index
    return best


SALD = []
for k in ("spalla", "sopra", "sotto", "fianco"):
    for pt in CF[k]:
        iF = vicino(ME_F, BF, pt)
        iB = vicino(ME_B, BB, pt)
        if iF >= 0 and iB >= 0:
            SALD.append((iF, iB))
log("saldature 1a1: %d" % len(SALD))

bm = bmesh.new()
vF = [bm.verts.new((v.co.x, GF, v.co.z)) for v in ME_F.vertices]
vB = [bm.verts.new((v.co.x, GB, v.co.z)) for v in ME_B.vertices]
bm.verts.ensure_lookup_table()
for p in ME_F.polygons:
    try:
        bm.faces.new([vF[i] for i in p.vertices])
    except ValueError:
        pass
for p in ME_B.polygons:
    try:
        bm.faces.new([vB[i] for i in [p.vertices[0]] + list(reversed(p.vertices[1:]))])
    except ValueError:
        pass
mp = dict(SALD)
for iF, iB in mp.items():
    try:
        mid = (vF[iF].co + vB[iB].co) / 2.0
        bmesh.ops.pointmerge(bm, verts=[vF[iF], vB[iB]], merge_co=mid)
    except Exception:
        pass
bm.verts.ensure_lookup_table()
_mesh = bpy.data.meshes.new("MagliaMesh")
bm.to_mesh(_mesh)
bm.free()
maglia = bpy.data.objects.new("Maglia_Base", _mesh)
SC.collection.objects.link(maglia)
bpy.context.view_layer.objects.active = maglia
maglia.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.004)
bpy.ops.object.mode_set(mode="OBJECT")
maglia.data.uv_layers.new(name="UV")
um = maglia.data.uv_layers.active
for p in maglia.data.polygons:
    for li in p.loop_indices:
        co = maglia.data.vertices[maglia.data.loops[li].vertex_index].co
        um.data[li].uv = ((co.x + 0.55) / 1.1, (co.z + 0.2) / 1.0)
log("mesh unica: %d vertici %d facce" % (len(maglia.data.vertices),
                                         len(maglia.data.polygons)))
REG["mesh"] = "%dV %dF sald=%d" % (len(maglia.data.vertices),
                                   len(maglia.data.polygons), len(SALD))
# __P5__ gruccia dentro + pin spalla + rumore + cloth + bake
def tube(name, p1, p2, r, mat=None):
    d = Vector(p2) - Vector(p1)
    ln = d.length
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=ln,
                                        location=((Vector(p1) + Vector(p2)) / 2.0))
    o = bpy.context.active_object
    o.name = name
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    o.rotation_mode = "XYZ"
    if mat is not None:
        o.data.materials.clear()
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


# gruccia dentro le spalle; gancio giu' (appesa all'asta)
PIN_X = [x for x in [SP_X0 + i * STEP for i in range(99)]
         if SP_X0 <= x <= SP_X1 - 0.03]
HZ = spalla_zf(SP_X0) - 0.004
GAN_TOP = HZ + 0.035
parts = [tube("g_tmp", (-a, 0.0, HZ - 0.012 * abs(a) / SP_X1),
              (-b, 0.0, HZ - 0.012 * abs(b) / SP_X1), 0.007, M_GRU)
         for (a, b) in [(-0.21, -0.075), (-0.075, 0.075), (0.075, 0.21)]]
gan = tube("g_tmp", (0, 0.0, HZ + 0.005), (0, 0.0, GAN_TOP), 0.007, M_GRU)
parts.append(gan)
gru = join(parts, "Gruccia")
gru.location = (0, -0.01, 0)

bpy.ops.object.select_all(action="DESELECT")
maglia.select_set(True)
bpy.context.view_layer.objects.active = maglia
pin_idx = [v.index for v in maglia.data.vertices
           if SP_X0 - 0.004 <= abs(v.co.x) <= SP_X1 - 0.03 + 0.004
           and v.co.z > spalla_zf(v.co.x) - 0.014]
log("pin spalla: %d vertici" % len(pin_idx))
REG["pin"] = len(pin_idx)
vg = maglia.vertex_groups.new(name="Spalle")
if pin_idx:
    vg.add(pin_idx, 1.0, "REPLACE")
me = maglia.data
for v in me.vertices:
    if v.index in pin_idx:
        continue
    v.co.x += random.uniform(-0.0025, 0.0025)
    v.co.y += random.uniform(-0.002, 0.002)
    v.co.z += random.uniform(-0.0025, 0.0025)

bpy.ops.object.select_all(action="DESELECT")
maglia.select_set(True)
bpy.context.view_layer.objects.active = maglia
mod = maglia.modifiers.new(name="Cloth", type="CLOTH")
cs = mod.settings
cs.quality = 10
cs.mass = 0.12
cs.vertex_group_mass = "Spalle"
for kk, vv in (("tension_stiffness", 15.0), ("compression_stiffness", 15.0),
               ("shear_stiffness", 7.0), ("bending_stiffness", 0.25),
               ("bending_damping", 0.5), ("air_damping", 0.5)):
    try:
        setattr(cs, kk, vv)
    except Exception:
        pass
cs.use_pressure = True
try:
    cs.pressure_factor = 0.02
except Exception as ee:
    log("pressure ko: %r" % (ee,))
try:
    cc = mod.collision_settings
    for kk, vv in (("collision_quality", 4), ("distance_min", 0.004)):
        try:
            setattr(cc, kk, vv)
        except Exception:
            pass
except Exception as ee:
    log("collision_settings ko: %r" % (ee,))
SC.frame_start = 1
SC.frame_end = 100
SC.frame_current = 1
try:
    mod.point_cache.frame_start = 1
    mod.point_cache.frame_end = 100
except Exception:
    pass
gru.select_set(True)
bpy.context.view_layer.objects.active = gru
gru.modifiers.new(name="Collisione", type="COLLISION")
try:
    gru.collision.thickness_outer = 0.005
    gru.collision.thickness_inner = 0.002
    gru.collision.use = True
except Exception as e:
    log("collision setup ko: %r" % (e,))
bpy.ops.object.select_all(action="DESELECT")
maglia.select_set(True)
bpy.context.view_layer.objects.active = maglia
try:
    bpy.ops.ptcache.bake_all(bake=True)
    REG["cloth"] = "bake_all ok 100f"
    log("CLOTH bake ok")
except Exception as e:
    REG["cloth"] = "FALLITO %r" % (e,)
    log("CLOTH FALLITO %r" % (e,))
SC.frame_set(100)
bpy.context.view_layer.update()
zs = [v.co.z for v in maglia.data.vertices]
ys = [v.co.y for v in maglia.data.vertices]
xs = [v.co.x for v in maglia.data.vertices]
REG["mis"] = "alt=%.3f larg=%.3f prof=%.3f fondosotto=%s" % (
    max(zs) - min(zs), max(xs) - min(xs), max(ys) - min(ys),
    all(z >= FOND_Z - 0.06 for z in zs))
log(REG["mis"] + " gruccia_z=%.3f pinmin=%.3f" % (
    HZ, min(v.co.z for v in maglia.data.vertices if v.index in set(pin_idx))
    if pin_idx else -9))
# __P6__ rifinitura: subdivision+solidify, costine, scritte, armadietto
bpy.ops.object.select_all(action="DESELECT")
maglia.select_set(True)
bpy.context.view_layer.objects.active = maglia
sm = maglia.modifiers.new(name="Subdiv", type="SUBSURF")
sm.levels = 1
sm.render_levels = 1
so = maglia.modifiers.new(name="Spessore", type="SOLIDIFY")
so.thickness = 0.002
so.offset = 0.0
for pp in maglia.data.polygons:
    pp.use_smooth = True
bpy.ops.object.convert(target="MESH")
maglia = bpy.context.active_object
maglia.name = "Maglia_Base"
maglia.data.materials.clear()
for mm in (M_BASE, M_DETT, M_SCRIT, M_SCUDO):
    maglia.data.materials.append(mm)
# costine: poliestere tecnico leggermente lucido
for mm in (M_BASE, M_DETT, M_SCRIT):
    try:
        for nn in mm.node_tree.nodes:
            if nn.type == "BSDF_PRINCIPLED":
                nn.inputs["Roughness"].default_value = 0.5
                try:
                    nn.inputs["Sheen Weight"].default_value = 0.3
                except Exception:
                    pass
                break
    except Exception:
        pass
# costine rifinite altrove
# costine: colletto sottile + polsini sottili, colore dettagli
def costina_tubo(pts, r=0.006):
    ts = [tube("tmp_c", pts[i], pts[i + 1], r, M_DETT)
          for i in range(len(pts) - 1)]
    return join(ts, "tmp_costina")


def costina_anello(cx, cy, cz, rx, ry, tub=0.011):
    bpy.ops.mesh.primitive_torus_add(location=(cx, cy, cz),
                                     major_radius=rx, minor_radius=tub)
    t = bpy.context.active_object
    t.name = "tmp_cost"
    t.scale = (1.0, ry / rx, 1.0)
    bpy.ops.object.transform_apply(location=False, scale=True)
    try:
        t.data.materials.clear()
        t.data.materials.append(M_DETT)
    except Exception:
        pass
    return t


COL = []
try:
    COL.append(costina_anello(0, (GF + GB) / 2, (TOP_F + TOP_B) / 2,
                               NECK_HW + 0.006, (NECK_F + NECK_B) / 2 + 0.006,
                               0.007))
    log("colletto: 1 anello sottile")
except Exception as e:
    log("costine ko: %r" % (e,))
# __P8__ scudetto petto + nome/numero retro figli + shrinkwrap
def testo_obj(txt, h, mat):
    bpy.ops.object.text_add(location=(0, 0, 0))
    t = bpy.context.active_object
    t.data.body = txt
    try:
        t.data.font = bpy.data.fonts.load(FONT_PATH)
    except Exception:
        pass
    t.data.align_x = "CENTER"
    t.data.align_y = "CENTER"
    t.data.size = h
    t.data.extrude = 0.0
    t.data.materials.clear()
    t.data.materials.append(mat)
    return t


FIGLI = list(COL)
# scudo piatto petto: a destra di chi guarda = sinistra di chi la indossa
bpy.ops.mesh.primitive_circle_add(vertices=6, radius=0.035,
                                 location=(0.13, GF + 0.004, 0.38))
sc = bpy.context.active_object
sc.name = "Scudo"
sc.scale = (1.0, 0.25, 1.25)
bpy.ops.object.transform_apply(scale=True)
sc.data.materials.clear()
sc.data.materials.append(M_SCUDO)
FIGLI.append(sc)
# nome+numero: testo->mesh sulla schiena (lato -Y)
for txt, h, lz in ((G10["nome"].upper(), 0.06, 0.33),
                   (str(G10["numero"]), 0.25, 0.02)):
    t = testo_obj(txt, h, M_SCRIT)
    # vetro dalla camera -Y: testo specchiato, rot X +90 (faccia a -Y)
    t.location = (0, -0.095, lz)
    t.rotation_euler = (math.pi / 2.0, 0, math.pi)
    bpy.ops.object.select_all(action="DESELECT")
    t.select_set(True)
    bpy.context.view_layer.objects.active = t
    bpy.ops.object.convert(target="MESH")
    t = bpy.context.active_object
    t.name = "Scritta_%s" % txt.replace(" ", "_")
    log("scritta %s: loc=%s rot=%s" % (t.name, tuple(round(v, 3) for v in t.location),
                                       tuple(round(v, 1) for v in t.rotation_euler)))
    # larghezza nome: max 80% schiena a quell'altezza
    if h < 0.1:
        xs = [v.co.x for v in t.data.vertices]
        w = max(xs) - min(xs) if xs else 0.4
        log("nome w=%.3f" % w)
        if w > 0.42:
            s = 0.42 / w
            t.scale = (s, s, s)
            bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.select_all(action="DESELECT")
    t.select_set(True)
    bpy.context.view_layer.objects.active = t
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.subdivide(number_cuts=2)
    bpy.ops.object.mode_set(mode="OBJECT")
    sw = t.modifiers.new(name="Adatta", type="SHRINKWRAP")
    sw.target = maglia
    sw.wrap_method = "PROJECT"
    sw.wrap_mode = "OUTSIDE_SURFACE"
    try:
        sw.use_negative_direction = False
    except Exception:
        pass
    sw.offset = 0.002
    FIGLI.append(t)
for o in FIGLI:
    try:
        o.parent = maglia
        o.parent_type = "OBJECT"
    except Exception as ee:
        log("parent ko %s: %r" % (o.name, ee))
log("figli maglia: %d" % len(FIGLI))
# __P9__ armadietto legno + pilastri + targa + cornice FOTO + nicchia
def box(name, sx, sy, sz, loc, mat):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = (sx / 2.0, sy / 2.0, sz / 2.0)
    bpy.ops.object.transform_apply(scale=True)
    if mat is not None:
        o.data.materials.clear()
        o.data.materials.append(mat)
    return o


def camera(name, loc, tgt, lens=50):
    bpy.ops.object.camera_add(location=loc)
    c = bpy.context.active_object
    c.name = name
    d = Vector(tgt) - Vector(loc)
    c.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    c.data.lens = lens
    return c


VANO_W, VANO_H, VANO_D = 0.95, 2.6, 0.55
legno = [box("LegnoSup", VANO_W, VANO_D, 0.10, (0, 0, VANO_H - 0.05), M_LEGNO),
         box("LegnoSx", 0.10, VANO_D, VANO_H, (-VANO_W / 2 + 0.05, 0, VANO_H / 2), M_LEGNO),
         box("LegnoDx", 0.10, VANO_D, VANO_H, (VANO_W / 2 - 0.05, 0, VANO_H / 2), M_LEGNO),
         box("LegnoZoc", VANO_W, VANO_D, 0.18, (0, 0, 0.09), M_LEGNO)]
box("PilSx", 0.12, 0.10, VANO_H, (-VANO_W / 2 - 0.06, 0.0, VANO_H / 2), M_BIANCO)
box("PilDx", 0.12, 0.10, VANO_H, (VANO_W / 2 + 0.06, 0.0, VANO_H / 2), M_BIANCO)
box("Targa10", 0.60, 0.02, 0.12, (0, VANO_D / 2 - 0.10, 2.32), M_DETT)
tt = testo_obj(G10["nome"].upper(), 0.07, M_BIANCO_T)
tt.name = "Targa_Testo"
tt.location = (0, VANO_D / 2 - 0.085, 2.32)
tt.rotation_euler = (math.pi / 2.0, 0, math.pi)
box("Cornice", 0.32, 0.03, 0.42, (0, 0.02, 1.86), M_LEGNO)
box("Foto", 0.28, 0.032, 0.38, (0, 0.02, 1.86), M_FOTO)
tf = testo_obj("FOTO", 0.08, M_BIANCO_T)
tf.name = "Foto_Testo"
tf.location = (0, 0.045, 1.86)
tf.rotation_euler = (math.pi / 2.0, 0, math.pi)
box("NicchiaFondo", 0.80, 0.03, 1.10, (0, -VANO_D / 2 + 0.10, 1.10), M_NICCHIA)
box("Seduta", 0.80, 0.45, 0.10, (0, 0.05, 0.45), M_SEDUTA)
box("KitSx", 0.30, 0.28, 0.09, (-0.18, 0.02, 0.545), M_DETT)
box("KitDx", 0.30, 0.28, 0.09, (0.16, 0.02, 0.545), M_BASE)
box("KitPiega", 0.24, 0.22, 0.05, (-0.02, 0.02, 0.615), M_DETT)
bpy.ops.mesh.primitive_cylinder_add(radius=0.035, depth=0.19, location=(0.30, 0.02, 0.60))
bor = bpy.context.active_object
bor.name = "Borraccia"
bor.data.materials.clear()
bor.data.materials.append(M_BORR)
box("VanoSx", 0.36, 0.40, 0.14, (-0.20, 0.0, 0.09), M_NICCHIA)
box("VanoDx", 0.36, 0.40, 0.14, (0.20, 0.0, 0.09), M_NICCHIA)
for sgn, px in ((-1.0, -0.20), (1.0, 0.20)):
    bpy.ops.mesh.primitive_cube_add(location=(px + sgn * 0.05, 0.06, 0.20))
    sp = bpy.context.active_object
    sp.name = "Scarpa_%s" % ("Sx" if sgn < 0 else "Dx")
    sp.scale = (0.11, 0.16, 0.05)
    bpy.ops.object.transform_apply(scale=True)
    sp.data.materials.clear()
    sp.data.materials.append(M_SCARPA)
    bpy.ops.mesh.primitive_cube_add(location=(px + sgn * 0.05, 0.06, 0.165))
    su = bpy.context.active_object
    su.name = "Suola_%s" % ("Sx" if sgn < 0 else "Dx")
    su.scale = (0.115, 0.165, 0.012)
    bpy.ops.object.transform_apply(scale=True)
    su.data.materials.clear()
    su.data.materials.append(M_SUOLA)
box("Pavimento", 4.0, 4.0, 0.10, (0, 1.5, -0.05), M_PAV)
# asta + maglia di schiena (camera a +Y: BE di schiena guarda la camera)
MAGA_Y, MAGA_Z = 0.10, 1.10
asta = tube("Asta", (-0.35, MAGA_Y, 1.72), (0.35, MAGA_Y, 1.72), 0.012, M_CROMO)
maglia.location = (0, MAGA_Y, MAGA_Z)
maglia.rotation_euler = (0, 0, 0)
gru.location = (0, MAGA_Y - 0.01, MAGA_Z)
gru.rotation_euler = (0, 0, 0)
# gancio dal collo verso l'asta
gan2 = tube("GancioAsta", (0, MAGA_Y - 0.01, MAGA_Z + GAN_TOP),
            (0, MAGA_Y, 1.72), 0.007, M_GRU)
log("asta z=1.72 gancio_top=%.3f" % (MAGA_Z + GAN_TOP,))
# __P10__ luci chiare + camere + prove maglia + render finali
bpy.ops.object.light_add(type="SUN", location=(1.5, 2.5, 4.0))
sun = bpy.context.active_object
sun.name = "Sole"
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(55), 0, math.radians(20))
bpy.ops.object.light_add(type="SUN", location=(-2.0, 3.0, 3.0))
fill = bpy.context.active_object
fill.name = "Riempi"
fill.data.energy = 1.0
bpy.ops.object.light_add(type="POINT", location=(0, 1.2, 2.4))
pl = bpy.context.active_object
pl.name = "PuntoNicchia"
pl.data.energy = 25
pl.data.color = (1.0, 0.95, 0.88)
try:
    pl.data.use_shadow = False
except Exception:
    pass
CAM_A = camera("Cam_Armadietto", (0, 2.9, 1.35), (0, 0.0, 1.30), lens=42)
CAM_3 = camera("Cam_34", (1.9, 2.4, 1.5), (0, 0.0, 1.25), lens=45)


def render(path, cam, rx, ry, samples=128):
    if __import__("os").path.exists(path):
        log("SKIP (esiste): %s" % path)
        return
    SC.camera = cam
    SC.render.resolution_x, SC.render.resolution_y = rx, ry
    SC.render.resolution_percentage = 100
    SC.render.filepath = path
    SC.cycles.samples = samples
    bpy.ops.render.render(write_still=True)
    log("RENDER: %s" % path)


# prove maglia da sola, fondo neutro, luce da camera
import os as _os
_mag0, _gru0 = maglia.location.copy(), gru.location.copy()
_magR, _gruR = maglia.rotation_euler.copy(), gru.rotation_euler.copy()
_nas = []
for o in list(bpy.data.objects):
    if o in (maglia, gru) or o.type in ("CAMERA", "LIGHT"):
        continue
    try:
        o.hide_render = True
        _nas.append(o)
    except Exception:
        pass
maglia.location = (0, 0, 0.0)
gru.location = (0, 0, 0.0)
maglia.rotation_euler = (0, 0, math.pi)
gru.rotation_euler = (0, 0, math.pi)
bpy.ops.object.light_add(type="POINT", location=(0, 2.2, 0.3))
_lf = bpy.context.active_object
_lf.data.energy = 60
try:
    _lf.data.use_shadow = False
except Exception:
    pass
CAM_P = camera("Cam_Prova", (0, 4.2, -0.10), (0, 0, -0.05), lens=35)
render(_os.path.join(RENDER_DIR, "v03_prova_maglia.png"), CAM_P, 800, 800, 32)
CAM_L = camera("Cam_Lato", (4.2, 0.0, -0.10), (0, 0, -0.05), lens=35)
render(_os.path.join(RENDER_DIR, "v03_prova_maglia_lato.png"), CAM_L, 800, 800, 32)
try:
    bpy.data.objects.remove(_lf)
except Exception:
    pass
for o in _nas:
    try:
        o.hide_render = False
    except Exception:
        pass
# retro/fronte maglia da sola: tutto nascosto tranne maglia+figli+gruccia
_nas2 = []
for o in list(bpy.data.objects):
    if o == maglia or o == gru or o.parent == maglia or o.type in ("CAMERA", "LIGHT"):
        continue
    try:
        o.hide_render = True
        _nas2.append(o)
    except Exception:
        pass
bpy.ops.object.light_add(type="POINT", location=(0, -1.6, 0.5))
_lr = bpy.context.active_object
_lr.data.energy = 60
try:
    _lr.data.use_shadow = False
except Exception:
    pass
CAM_BR = camera("Cam_Retro", (0, -1.9, 0.05), (0, 0, 0.0), lens=55)
render(_os.path.join(RENDER_DIR, "v03_maglia_retro.png"), CAM_BR, 1080, 1080)
try:
    bpy.data.objects.remove(_lr)
except Exception:
    pass
maglia.rotation_euler = (0, 0, 0)
gru.rotation_euler = (0, 0, 0)
bpy.ops.object.light_add(type="POINT", location=(0, 2.0, 0.5))
_lf2 = bpy.context.active_object
_lf2.data.energy = 60
try:
    _lf2.data.use_shadow = False
except Exception:
    pass
CAM_FR = camera("Cam_Fronte", (0, 2.0, 0.05), (0, 0, 0.0), lens=55)
render(_os.path.join(RENDER_DIR, "v03_maglia_fronte.png"), CAM_FR, 1080, 1080)
try:
    bpy.data.objects.remove(_lf2)
except Exception:
    pass
for o in _nas2:
    try:
        o.hide_render = False
    except Exception:
        pass
maglia.location, gru.location = _mag0, _gru0
maglia.rotation_euler, gru.rotation_euler = _magR, _gruR
render(_os.path.join(RENDER_DIR, "v03_armadietto.png"), CAM_A, 1200, 1800)
render(_os.path.join(RENDER_DIR, "v03_armadietto_34.png"), CAM_3, 1600, 1200)
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
log("FINITO blend: %s" % BLEND_PATH)
print("REGISTRO_DATI: %s" % (REG,), flush=True)









