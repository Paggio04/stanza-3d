"""Spogliatoio v02 - la maglia vera.
Uso: blender -b -P scripts/spogliatoio.py
Dati solo da squadra.json. Geometria maglia: petto=+Y schiena=-Y.
"""
import bpy
import bmesh
import json
import math
import os
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "squadra.json"), encoding="utf-8") as f:
    DATA = json.load(f)
RENDER_DIR = os.path.join(ROOT, "render")
BLEND_PATH = os.path.join(ROOT, "spogliatoio.blend")
FONT_PATH = "C:/Windows/Fonts/arialbd.ttf"

BAR_Y, BAR_Z = 0.42, 1.78
GAP_IN, GAP_GROUP = 0.02, 0.35
HOVER_DY = 0.25
REST_BACK = math.radians(45.0)
LEAD_BACK = math.radians(25.0)
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
SC.cycles.samples = 64
try:
    SC.cycles.use_denoising = True
except Exception:
    pass
SC.render.film_transparent = False
SC.render.image_settings.file_format = "PNG"
try:
    SC.view_settings.view_transform = "Filmic"
    SC.view_settings.exposure = -1.2
except Exception:
    pass
W = bpy.data.worlds["World"]
W.use_nodes = True
bgnode = W.node_tree.nodes.get("Background")
if bgnode is not None:
    bgnode.inputs[0].default_value = (0.004, 0.004, 0.007, 1.0)
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


def emat(name, rgb, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nn = nt.nodes
    e = nn.new("ShaderNodeEmission")
    try:
        e.inputs[0].default_value = (*rgb, 1.0)
    except Exception:
        pass
    try:
        e.inputs[1].default_value = strength
    except Exception:
        pass
    out = None
    for _nn in nn:
        if _nn.type == "OUTPUT_MATERIAL":
            out = _nn
            break
    if out is not None:
        try:
            nt.links.new(e.outputs[0], out.inputs[0])
        except Exception:
            pass
    for _nn in list(nn):
        if _nn.type == "BSDF_PRINCIPLED":
            try:
                nn.remove(_nn)
            except Exception:
                pass
    return m


C = DATA["colori"]
M_BASE = pmat("M_Maglia", hexrgb(C["maglia"]), 0.7)
M_PORT = pmat("M_Portieri", hexrgb(C["portieri"]), 0.7)

M_DETT = pmat("M_Dettagli", hexrgb(C["dettagli"]), 0.7)
M_SCRIT = pmat("M_Scritte", hexrgb(C["scritte"]), 0.6)
M_SCUDO = pmat("M_Scudo", hexrgb("#9aa0a6"), 0.5, 0.1)
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


for _mp in (M_BASE, M_PORT, M_DETT, M_SCRIT):
    try:
        trama(_mp)
    except Exception as e:
        log("trama ko su %s: %r" % (_mp.name, e))
for _mp in (M_BASE, M_PORT):
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

# ---- SAGOMA piatta: busto 0.52x0.72, maniche 0.20, spalla 12 gradi ----
STEP = 0.02
BW, BLEN = 0.52, 0.72
SL = 0.20
SH_Z = -0.10
SLOPE = math.tan(math.radians(12.0)) * (BW / 2.0)
HEM_Z = SH_Z - BLEN
NECK_HW, NECK_D_F = 0.075, 0.08
SP_X0, SP_X1 = NECK_HW, BW / 2.0
SH_DROP = math.tan(math.radians(12.0)) * (SP_X1 - SP_X0)
TOP_F = SH_Z + SH_DROP
SL_ANG = math.radians(40.0)
ARM_W, CUFF_W = 0.22, 0.17
NECK_D_B = 0.025
GF, GB = 0.0, -0.06
XS_MIN = -(BW / 2.0 + SL * math.cos(SL_ANG) + CUFF_W / 2.0 + 0.03)
XS_MAX = -XS_MIN


def box(name, sx, sy, sz, loc, mat, rot=None):
    bpy.ops.mesh.primitive_cube_add(location=loc,
                                    rotation=rot or (0, 0, 0))
    _oo = bpy.context.active_object
    _oo.name = name
    _oo.scale = (sx / 2.0, sy / 2.0, sz / 2.0)
    bpy.ops.object.transform_apply(scale=True)
    _oo.data.materials.append(mat)
    return _oo


def tube(name, p1, p2, r, mat):
    import mathutils as _m
    _dd = _m.Vector(p2) - _m.Vector(p1)
    _ln = _dd.length
    bpy.ops.mesh.primitive_cylinder_add(
        radius=r, depth=_ln, location=(_m.Vector(p1) + _m.Vector(p2)) / 2)
    _oo = bpy.context.active_object
    _oo.name = name
    _oo.rotation_mode = "QUATERNION"
    _oo.rotation_quaternion = _m.Vector((0, 0, 1)).rotation_difference(
        _dd.normalized())
    _oo.rotation_mode = "XYZ"
    return _oo


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for _oo in objs:
        _oo.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    _jj = bpy.context.active_object
    _jj.name = name
    return _jj


def spalla_z(x):
    """Quota spalla: inclinata 12 gradi da bordo collo a punto spalla."""
    ax = abs(x)
    if ax <= SP_X0:
        return TOP_F
    if ax >= SP_X1:
        return SH_Z
    t = (ax - SP_X0) / (SP_X1 - SP_X0)
    return TOP_F + t * (SH_Z - TOP_F)


def bordo_obiettivo(x, z):
    """Punto della sagoma analitica per i vertici di bordo.
    Ritorna (bx, bz): spalla/manica su rette, collo su ellisse, fondo."""
    sgn = 1.0 if x >= 0 else -1.0
    ax = abs(x)
    # collo: ellisse (davanti 8 cm, dietro si usa la stessa: lo scollo
    # dietro e' meno profondo ma il bordo griglia e' quello davanti)
    if ax < NECK_HW + 0.02 and z > TOP_F - NECK_D_F - 0.03:
        qx = max(-1.0, min(1.0, x / NECK_HW))
        bz = TOP_F - NECK_D_F * (1.0 - qx ** 2) ** 0.5
        return (x, bz)
    # spalla del busto: retta da (SP_X0, TOP_F) a (SP_X1, SH_Z)
    if ax <= SP_X1 + 0.01 and z > SH_Z - 0.05:
        t = max(0.0, min(1.0, (ax - SP_X0) / (SP_X1 - SP_X0)))
        bx = SP_X0 + t * (SP_X1 - SP_X0)
        return (sgn * bx, spalla_z(bx))
    # manica: lato alto (sw=0) e lato basso (sw=-larg) + polso (su=SL)
    if ax > BW / 2.0 - 0.01:
        o, u, w = sleeve_frame(sgn)
        rel = Vector((x, 0.0, z)) - o
        su = max(0.0, min(SL, rel.dot(u)))
        sw = rel.dot(w)
        larg = 2.0 * sleeve_half(su)
        if sw > -larg / 2.0:
            pt = o + u * su
        elif su >= SL - 0.01:
            pt = o + u * SL + w * max(-larg, min(0.0, sw))
        else:
            pt = o + u * su + w * (-larg)
        return (pt.x, pt.z)
    # fondo
    return (max(-BW / 2.0, min(BW / 2.0, x)), HEM_Z)


def sleeve_frame(sgn):
    """Base punto spalla + versori asse manica (u) e polso (w)."""
    ox = sgn * SP_X1
    oz = SH_Z
    u = Vector((sgn * math.cos(SL_ANG), 0.0, -math.sin(SL_ANG)))
    w = Vector((sgn * math.sin(SL_ANG), 0.0, math.cos(SL_ANG)))
    return Vector((ox, 0.0, oz)), u, w


def sleeve_half(su):
    """Mezza larghezza manica: 0.22 al giromanica -> 0.17 al polso."""
    t = min(1.0, max(0.0, su / SL))
    return (ARM_W / 2.0) * (1.0 - t) + (CUFF_W / 2.0) * t


def inside_sleeve(x, z):
    """Tutta la manica sta SOTTO la linea spalla: -larg <= sw <= 0.
    Il lato alto (sw=0) prolunga la spalla verso il basso a 40 gradi."""
    sgn = 1.0 if x > 0 else -1.0
    o, u, w = sleeve_frame(sgn)
    rel = Vector((x, 0.0, z)) - o
    su = rel.dot(u)
    sw = rel.dot(w)
    if not (-0.01 <= su <= SL + 0.01):
        return False
    return -2.0 * sleeve_half(su) - 0.005 <= sw <= 0.0 + 0.005


def inside_front(x, z):
    if z < HEM_Z:
        return False
    if abs(x) <= BW / 2.0:
        if z > TOP_F - NECK_D_F and abs(x) < NECK_HW:
            q = ((x / NECK_HW) ** 2
                 + ((z - TOP_F) / NECK_D_F) ** 2)
            if q < 1.0:
                return False
        return z <= spalla_z(x) + 1e-9
    return inside_sleeve(x, z)


def inside_back(x, z):
    if z < HEM_Z:
        return False
    if abs(x) <= BW / 2.0:
        if z > SH_Z + SH_DROP - NECK_D_B and abs(x) < NECK_HW:
            q = ((x / NECK_HW) ** 2
                 + ((z - (SH_Z + SH_DROP)) / NECK_D_B) ** 2)
            if q < 1.0:
                return False
        return z <= spalla_z(x) + SH_DROP * 0.0 + 1e-9
    return inside_front(x, z)


def open_neck(x, z):
    return abs(x) < NECK_HW + STEP and z > TOP_F - NECK_D_F - STEP


def open_hem(x, z):
    return z <= HEM_Z + STEP * 0.6


def open_cuff(x, z):
    # polso = bordo esterno della manica (lontano dal busto)
    if abs(x) <= BW / 2.0 or not inside_sleeve(x, z):
        return False
    sgn = 1.0 if x > 0 else -1.0
    o, u, w = sleeve_frame(sgn)
    su = (Vector((x, 0.0, z)) - o).dot(u)
    return su >= SL - STEP * 1.2

# UNA SOLA MESH: fronte+retro condividono le cuciture chiuse.
# Stessa griglia X/Z; sui bordi CHIUSI (spalle, fianchi, sopra/sotto
# manica) un vertice condiviso in Y media; al centro fronte y=0 e
# retro y=-6 cm. Aperti: collo, fondo, polsi (vertici separati).
XS_MIN = -(BW / 2.0 + SL * math.cos(SL_ANG) + CUFF_W / 2.0 + 0.03)
XS_MAX = -XS_MIN
NX = int(round((XS_MAX - XS_MIN) / STEP))
NZ = int(round((TOP_F - HEM_Z) / STEP)) + 2


def seam_closed(x, z):
    if open_neck(x, z) or open_hem(x, z) or open_cuff(x, z):
        return False
    for dx, dz in ((STEP, 0), (-STEP, 0), (0, STEP), (0, -STEP)):
        if not inside_front(x + dx, z + dz):
            return True
    return False


bpy.ops.object.select_all(action="DESELECT")
_mesh = bpy.data.meshes.new("MagliaMesh")
_bm = bmesh.new()
_vf = {}
_vb = {}
_seam = {}
_YC = (GF + GB) / 2.0
for _iz in range(NZ + 1):
    for _ix in range(NX + 1):
        _x = XS_MIN + _ix * STEP
        _z = TOP_F - _iz * STEP
        _inf = inside_front(_x, _z)
        _inb = inside_back(_x, _z)
        if not _inf and not _inb:
            continue
        if _inf and _inb and seam_closed(_x, _z):
            _seam[(_ix, _iz)] = _bm.verts.new((_x, _YC, _z))
        else:
            if _inf:
                _vf[(_ix, _iz)] = _bm.verts.new((_x, GF, _z))
            if _inb:
                _vb[(_ix, _iz)] = _bm.verts.new((_x, GB, _z))
_bm.verts.ensure_lookup_table()


def _cell(d, ix, iz):
    return d.get((ix, iz))


_PQ = 0
for _iz in range(NZ):
    for _ix in range(NX):
        for _dd in (_vf, _vb):
            _a = _cell(_dd, _ix, _iz) or _cell(_seam, _ix, _iz)
            _b = _cell(_dd, _ix + 1, _iz) or _cell(_seam, _ix + 1, _iz)
            _c = _cell(_dd, _ix + 1, _iz + 1) or _cell(
                _seam, _ix + 1, _iz + 1)
            _d = _cell(_dd, _ix, _iz + 1) or _cell(_seam, _ix, _iz + 1)
            if _a is not None and _b is not None \
                    and _c is not None and _d is not None:
                try:
                    _bm.faces.new((_a, _b, _c, _d))
                    _PQ += 1
                except ValueError:
                    pass
_bm.to_mesh(_mesh)
_bm.free()
maglia = bpy.data.objects.new("Maglia_Base", _mesh)
SC.collection.objects.link(maglia)
bpy.context.view_layer.objects.active = maglia
maglia.select_set(True)
maglia.data.update()
log("MESH UNICA cuciture condivise: quads=%d vertici=%d"
    % (_PQ, len(_mesh.vertices)))
# sciolti (senza facce: cadrebbero nel cloth) -> rimossi
_bmx = bmesh.new()
_bmx.from_mesh(maglia.data)
_bmx.verts.ensure_lookup_table()
_sciolti = [vv for vv in list(_bmx.verts) if not vv.link_faces]
for _vv in _sciolti:
    _bmx.verts.remove(_vv)
_bmx.to_mesh(maglia.data)
_bmx.free()
maglia.data.update()
log("VERTICI sciolti rimossi: %d" % len(_sciolti))
REG["sciolti"] = len(_sciolti)

# UV = sagoma piatta pre-simulazione (proiezione X/Z)
bpy.context.view_layer.objects.active = maglia
maglia.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
_bm = bmesh.from_edit_mesh(maglia.data)
_uve = _bm.loops.layers.uv.verify()
_XW = XS_MAX - XS_MIN
_ZW = TOP_F - HEM_Z
for _f in _bm.faces:
    for _lp in _f.loops:
        _co = _lp.vert.co
        _lp[_uve].uv = ((float(_co.x - XS_MIN)) / _XW,
                        (float(TOP_F - _co.z)) / _ZW)
bmesh.update_edit_mesh(maglia.data)
bpy.ops.object.mode_set(mode="OBJECT")

# ---- gruccia-collider dritta (solo l'orientamento) ----
# Bracci lungo x (spessore y 2 cm), sotto i vertici bloccati: si
# sposta la GRUCCIA sotto la maglia, non la maglia.
_ho = 0.0
_gr_y = (_YC + 0.0)
_br = [((-0.26, _gr_y, SH_Z), (-0.02, _gr_y, TOP_F)),
       ((0.02, _gr_y, TOP_F), (0.26, _gr_y, SH_Z)),
       ((-0.26, _gr_y, SH_Z), (0.26, _gr_y, SH_Z))]
bpy.ops.object.select_all(action="DESELECT")
_gruccia_parts = [
    tube("tmp_g", (0, _gr_y, 0.02), (0, _gr_y, TOP_F + 0.06), 0.008, M_GRU),
    tube("tmp_g", *_br[0], 0.011, M_GRU),
    tube("tmp_g", *_br[1], 0.011, M_GRU),
    tube("tmp_g", *_br[2], 0.008, M_GRU)]
for _gg in _gruccia_parts:
    bpy.ops.object.select_all(action="DESELECT")
    _gg.select_set(True)
    bpy.context.view_layer.objects.active = _gg
    bpy.ops.object.transform_apply(location=False, rotation=True,
                                   scale=True)
bpy.context.view_layer.update()
gru = join(_gruccia_parts, "Gruccia_Prova")
gru.location = (0, 0, 0)
gru.rotation_euler = (0, 0, 0)
# gruccia sotto i pin: i bracci seguono la spalla meno 2 mm
_sy = min(vv.co.y for vv in maglia.data.vertices
         if SP_X0 - 0.005 < abs(vv.co.x) < SP_X1 + 0.005)
gru.location = (0, _sy - 0.002 - _gr_y, -0.002)
bpy.context.view_layer.update()
log("GRU box: x=[%.3f,%.3f] y=[%.3f,%.3f] (sotto i pin)"
    % (min(vv.co.x for vv in gru.data.vertices),
       max(vv.co.x for vv in gru.data.vertices),
       min((gru.matrix_world @ vv.co).y for vv in gru.data.vertices),
       max((gru.matrix_world @ vv.co).y for vv in gru.data.vertices)))
gru.select_set(True)
bpy.context.view_layer.objects.active = gru
gru.modifiers.new(name="Collisione", type="COLLISION")
try:
    _cs = gru.collision
    _cs.thickness_outer = 0.005
    _cs.thickness_inner = 0.002
    _cs.use = True
    _cs.use_culling = False
    _cs.use_normal = False
except Exception as e:
    log("collision setup ko: %r" % (e,))

# ---- cloth: pin sulla linea spalla (versione 10:00) ----
bpy.ops.object.select_all(action="DESELECT")
maglia.select_set(True)
bpy.context.view_layer.objects.active = maglia
_ztop = max(vv.co.z for vv in maglia.data.vertices)
_sx = sorted([vv for vv in maglia.data.vertices
              if SP_X0 - 0.005 < vv.co.x < SP_X1 + 0.005
              and vv.co.z > spalla_z(min(abs(vv.co.x), SP_X1)) - 0.012],
             key=lambda vv: (round(vv.co.x / STEP), vv.co.y))
_dx = sorted([vv for vv in maglia.data.vertices
              if -(SP_X1 + 0.005) < vv.co.x < -(SP_X0 - 0.005)
              and vv.co.z > spalla_z(min(abs(vv.co.x), SP_X1)) - 0.012],
             key=lambda vv: (round(vv.co.x / STEP), vv.co.y))
_pinz = [vv.index for vv in _sx[:20] + _dx[:20]]
log("PIN linea spalla: %d vertici" % len(_pinz))
REG["pin"] = len(_pinz)
vg_pin = maglia.vertex_groups.new(name="Spalle")
if _pinz:
    vg_pin.add(_pinz, 1.0, "REPLACE")

mod = maglia.modifiers.new(name="Cloth", type="CLOTH")
cs = mod.settings
cs.quality = 10
cs.mass = 0.15
cs.vertex_group_mass = "Spalle"
for _kk, _vv in (("tension_stiffness", 10.0),
                 ("compression_stiffness", 10.0),
                 ("shear_stiffness", 5.0),
                 ("bending_stiffness", 0.5),
                 ("bending_damping", 0.5),
                 ("air_damping", 1.0)):
    try:
        setattr(cs, _kk, _vv)
    except Exception:
        pass
cs.use_pressure = True
try:
    cs.pressure_factor = 0.15
except Exception:
    pass
try:
    _cc = mod.collision_settings
    for _kk, _vv in (("use_self_collision", True),
                     ("self_distance_min", 0.003),
                     ("collision_quality", 4),
                     ("distance_min", 0.005)):
        try:
            setattr(_cc, _kk, _vv)
        except Exception:
            pass
except Exception as ee:
    log("mod.collision_settings ko: %r" % (ee,))
SC.frame_start = 1
SC.frame_end = 100
SC.frame_current = 1
try:
    mod.point_cache.frame_start = 1
    mod.point_cache.frame_end = 100
except Exception:
    pass
try:
    bpy.ops.ptcache.bake_all(bake=True)
    REG["cloth"] = "bake_all ok, 100 frame"
    log("CLOTH bake ok")
except Exception as e:
    REG["cloth"] = "bake_all FALLITO: %r" % (e,)
    log("CLOTH bake FALLITO: %r" % (e,))
SC.frame_set(100)
bpy.context.view_layer.update()

# rifinitura + scala misurata + slot materiali
sm = maglia.modifiers.new(name="Subdiv", type="SUBSURF")
sm.levels = 1
sm.render_levels = 1
so = maglia.modifiers.new(name="Spessore", type="SOLIDIFY")
so.thickness = 0.002
so.offset = 0.0
for _pp in maglia.data.polygons:
    _pp.use_smooth = True
bpy.ops.object.select_all(action="DESELECT")
maglia.select_set(True)
bpy.context.view_layer.objects.active = maglia
bpy.ops.object.convert(target="MESH")
maglia = bpy.context.active_object
maglia.name = "Maglia_Base"
_Mmi = [min(vv.co[k] for vv in maglia.data.vertices) for k in range(3)]
_Mma = [max(vv.co[k] for vv in maglia.data.vertices) for k in range(3)]
_sx = 0.52 / max((_Mma[0] - _Mmi[0]), 1e-6)
_sy = 0.72 / max((_Mmi[2] - _Mma[2]), 1e-6)
_s = min(_sx, _sy, 1.5)
maglia.scale = (_s, _s, _s)
bpy.ops.object.transform_apply(scale=True)
_JW = max(vv.co.x for vv in maglia.data.vertices) - \
    min(vv.co.x for vv in maglia.data.vertices)
_JY = max(vv.co.y for vv in maglia.data.vertices) - \
    min(vv.co.y for vv in maglia.data.vertices)
_JB = min(vv.co.y for vv in maglia.data.vertices)
log("MAGLIA_BASE scala=%.3f Lx=%.3f prof=%.3f" % (_s, _JW, _JY))
REG["scala"] = round(_s, 4)
maglia.data.materials.clear()
for _mm in (M_BASE, M_DETT, M_SCRIT, M_SCUDO, M_INT, M_GRU):
    maglia.data.materials.append(_mm)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.object.material_slot_assign()
bpy.ops.object.mode_set(mode="OBJECT")

# ---- layout: semi-ampiezza dall'ingombro reale misurato ----
def hx_of(phi):
    return (_JW * abs(math.cos(phi)) + _JY * abs(math.sin(phi))) / 2.0


_rest = math.pi - REST_BACK
_lead = math.pi - LEAD_BACK
JERSEYS, GROUPS = [], {}
for _gg in DATA["reparti"]:
    GROUPS[_gg["nome"]] = []
    for _kk, _nn in enumerate(_gg["numeri"]):
        _ld = (_kk == 0)
        _phi = _lead if _ld else _rest
        JERSEYS.append({"numero": _nn, "reparto": _gg["nome"],
                        "leader": _ld, "phi": _phi, "hx": hx_of(_phi),
                        "maglia": "Maglia_%02d" % _nn,
                        "gruccia": "Gruccia_%02d" % _nn})
        GROUPS[_gg["nome"]].append(JERSEYS[-1])
_xs, _cur = [], 0.0
for _ii, _jj in enumerate(JERSEYS):
    _cur += _jj["hx"] if _ii == 0 else JERSEYS[_ii - 1]["hx"] + _jj["hx"] + (
        GAP_GROUP if _jj["reparto"] != JERSEYS[_ii - 1]["reparto"]
        else GAP_IN)
    _xs.append(_cur)
_span = _cur + JERSEYS[-1]["hx"]
_off = _span / 2.0
for _jj, _xx in zip(JERSEYS, _xs):
    _jj["x"] = _xx - _off
X_MIN = JERSEYS[0]["x"] - JERSEYS[0]["hx"]
X_MAX = JERSEYS[-1]["x"] + JERSEYS[-1]["hx"]
for _nm, _mm in GROUPS.items():
    GROUPS[_nm] = {"members": _mm,
                   "cx": sum(_m["x"] for _m in _mm) / len(_mm),
                   "n": len(_mm)}
J10 = next(jj for jj in JERSEYS if jj["numero"] == 10)
log("LAYOUT span=%.2f x=[%.2f, %.2f] J10 x=%.2f" % (_span, X_MIN, X_MAX,
                                                    J10["x"]))
REG["span"] = "span=%.2f" % _span

# rifiniture locali (colletto/polsi/righe/scudo+tappo), join coi materiali
_gf = 0.0
_gb = -0.06 * _s
_colletti = []
try:
    _nx = 16
    _epts = [(_s * NECK_HW * 0.98 * math.cos(2 * math.pi * _ii / _nx),
              _gf + 0.001,
              (TOP_F * _s - 0.035 * _s) + _s * NECK_D_F * 0.9
              * (math.sin(2 * math.pi * _ii / _nx) * 0.5 + 0.5) * 0.35)
             for _ii in range(_nx)]
    _parts = []
    for _ii in range(_nx):
        _parts.append(tube("tmp_c", _epts[_ii], _epts[(_ii + 1) % _nx],
                           0.012, M_DETT))
    _colletti.append(join(_parts, "tmp_collo"))
except Exception as e:
    log("colletto ko: %r" % (e,))
_polsi = []
try:
    _psx = BW * _s / 2.0 + SL * _s * math.cos(SL_ANG)
    for _sgn in (-1.0, 1.0):
        _pc = []
        for _ii in range(10):
            _aa = 2 * math.pi * _ii / 10
            _pc.append((_sgn * _psx + 0.011 * math.cos(_aa),
                        (_gf + _gb) / 2.0 + 0.011 * math.sin(_aa),
                        (SH_Z - 0.10) * _s))
        _pp2 = []
        for _ii in range(10):
            _pp2.append(tube("tmp_p", _pc[_ii], _pc[(_ii + 1) % 10],
                             0.011, M_DETT))
        _polsi.append(join(_pp2, "tmp_polso"))
except Exception as e:
    log("polsi ko: %r" % (e,))
_righe = []
for _sxgn in (-1.0, 1.0):
    _xc = _sxgn * (BW * _s / 2.0 + SL * _s * 0.45)
    _righe.append(tube("tmp", (_xc, _gf + 0.031 * _s, (SH_Z - 0.06) * _s),
                       (_xc, _gf + 0.031 * _s, (SH_Z - 0.145) * _s),
                       0.004, M_DETT))
bpy.ops.mesh.primitive_cylinder_add(radius=NECK_HW * _s * 0.9, depth=0.02,
                                    location=(0, (_gf + _gb) / 2.0,
                                              (SH_Z - 0.045) * _s))
_tappo = bpy.context.active_object
_tappo.name = "tmp_tappo"
_tappo.scale = (1.0, 0.55, 1.0)
bpy.ops.object.transform_apply(scale=True)
_sc = box("tmp_scudo", 0.07, 0.006, 0.085,
          (-0.10, 0.035, (SH_Z - 0.10) * _s), M_SCUDO)
bpy.ops.object.select_all(action="DESELECT")
maglia.select_set(True)
for _oo in (_colletti + _polsi + _righe + [_tappo, _sc]):
    _oo.select_set(True)
bpy.context.view_layer.objects.active = maglia
bpy.ops.object.join()
maglia = bpy.context.active_object
maglia.name = "Maglia_Base"
log("MAGLIA_BASE completa: vertici=%d mats=%d"
    % (len(maglia.data.vertices), len(maglia.data.materials)))
maglia.hide_render = True
maglia.hide_viewport = True

# 20 copie sulla mesh condivisa (linked) + grucce
MAG = {}
for _jj in JERSEYS:
    _cp = bpy.data.objects.new(_jj["maglia"], maglia.data)
    SC.collection.objects.link(_cp)
    if _jj["reparto"] == "PORTIERI":
        try:
            _cp.material_slots[0].link = "OBJECT"
            _cp.material_slots[0].material = M_PORT
        except Exception as e:
            log("slot portieri ko %s: %r" % (_cp.name, e))
    _parts = [tube("tmp", (0, 0, 0), (0, 0, 0.09), 0.008, M_GRU),
              tube("tmp", (-0.24, 0, -0.10), (0, 0, 0.02), 0.011, M_GRU),
              tube("tmp", (0.24, 0, -0.10), (0, 0, 0.02), 0.011, M_GRU),
              tube("tmp", (-0.24, 0, -0.10), (0.24, 0, -0.10), 0.008, M_GRU)]
    _gr = join(_parts, _jj["gruccia"])
    for _oo in (_cp, _gr):
        _oo.location = (_jj["x"], BAR_Y, BAR_Z)
        _oo.rotation_euler = (0, 0, _jj["phi"])
    MAG[_jj["maglia"]] = (_cp, _gr)
log("COPIE: %d mesh condivisa" % len(MAG))

# ---- nome+numero sul retro (oggetti separati, parent alla copia) ----
# Le scritte restano oggetti TESTO separati (niente join: il join le
# gonfia a scatole), parent alla copia con trasformazioni locali.
def testo_obj(txt, h, mat):
    bpy.ops.object.text_add(location=(0, 0, 0))
    _tt = bpy.context.active_object
    _tt.data.body = txt
    try:
        _tt.data.font = bpy.data.fonts.load(FONT_PATH)
    except Exception:
        pass
    _tt.data.align_x = "CENTER"
    _tt.data.align_y = "CENTER"
    _tt.data.size = h
    _tt.data.extrude = 0.0
    _tt.data.space_character = 1.05
    _tt.data.materials.clear()
    _tt.data.materials.append(mat)
    return _tt


by_num = {g["numero"]: g for g in DATA["giocatori"]}
for _jj in JERSEYS:
    _gg = by_num[_jj["numero"]]
    _cp = MAG[_jj["maglia"]][0]
    for _txt, _h, _lz in ((_gg["nome"].upper(), 0.055, -0.16),
                          (str(_jj["numero"]), 0.20, -0.40)):
        _tt = testo_obj(_txt, _h, M_SCRIT)
        _tt.name = "Testo_%02d_%s" % (_jj["numero"],
                                      "nome" if _lz > -0.3 else "num")
        # locale alla copia: schiena -Y, testo girato verso -Y.
        # Nomi lunghi: ancorati a sinistra del centro per non uscire
        # dal fianco destro della maglia.
        if _lz > -0.3:
            _tt.location = (-0.16, _JB - 0.001, _lz)
        else:
            _tt.location = (0, _JB - 0.001, _lz)
        _tt.rotation_euler = (math.pi / 2.0, 0, -math.pi / 2.0)
        _tt.parent = _cp
        _tt.parent_type = "OBJECT"
log("SCRITTE retro: 40 oggetti testo parent alle copie")

# ---- stanza, barra, targhe, stemma, luci, camere ----
WALL_W = _span + 2.6
muro = box("Muro", WALL_W, 0.1, 9.0, (0, -0.05, 4.5), M_MURO)
pav = box("Pavimento", WALL_W + 2, 16.0, 0.1, (0, 6.4, -0.05), M_PAV)
_sl = []
_xx = -_span / 2 - 0.8
while _xx <= _span / 2 + 0.8:
    _sl.append(box("Doga", 0.12, 0.03, 2.6, (_xx, 0.03, 1.3), M_LEGNO))
    _xx += 0.17
join(_sl, "Parete_Doghe")
box("StrisciaCalda", _span + 1.2, 0.04, 0.10, (0, 0.06, 2.38), M_WARM)
box("StrisciaBlu", _span + 1.2, 0.05, 0.05, (0, 0.06, 0.07), M_BLUE)
_bar = [tube("Barra_tmp", (X_MIN - 0.25, BAR_Y, BAR_Z),
             (X_MAX + 0.15, BAR_Y, BAR_Z), 0.021, M_CROMO),
        tube("Barra_tmp", (X_MAX + 0.15, BAR_Y, BAR_Z),
             (X_MAX + 0.15, 0.06, BAR_Z), 0.021, M_CROMO)]
join(_bar, "Barra")
for _pp, _qq in [((X_MIN - 0.25, BAR_Y, 0.0), (X_MIN - 0.25, BAR_Y, BAR_Z)),
                 ((X_MAX + 0.15, 0.06, 0.0), (X_MAX + 0.15, 0.06, BAR_Z))]:
    box("Staffa", 0.05, 0.05, 0.06, ((_pp[0] + _qq[0]) / 2,
                                     (_pp[1] + _qq[1]) / 2,
                                     (_pp[2] + _qq[2]) / 2), M_CROMO)

# targhe + stemma muro + luci + camere
def make_plaque(key, text, cx):
    _w = max(0.70, 0.075 * len(text))
    _pp = box("Targa_%s" % key.title(), _w, 0.03, 0.16, (cx, 0.06, 2.19),
              M_TARGA)
    bpy.ops.object.text_add(location=(cx, 0.045, 2.19))
    _tt = bpy.context.active_object
    _tt.name = "Targa_Testo_%s" % key.title()
    _tt.data.body = text
    _tt.data.align_x = "CENTER"
    try:
        _tt.data.size = 0.10
    except Exception:
        pass
    _tt.data.materials.clear()
    _tt.data.materials.append(M_TESTO)
    _tt.rotation_euler = (math.pi / 2.0, 0, math.pi)
    return _pp


for _rr in DATA["reparti"]:
    _nn2 = _rr["nome"]
    make_plaque(_nn2, "%s %d" % (_nn2, GROUPS[_nn2]["n"]), GROUPS[_nn2]["cx"])
_scudo_c = box("Stemma_Muro", 0.42, 0.03, 0.60, (0, 0.06, 2.95), M_SCUDO)
bpy.ops.object.text_add(location=(0, 0.045, 2.95))
_st = bpy.context.active_object
_st.name = "Stemma_Testo"
_st.data.body = "STEMMA"
_st.data.align_x = "CENTER"
try:
    _st.data.size = 0.11
except Exception:
    pass
_st.data.materials.clear()
_st.data.materials.append(M_INT)
_st.rotation_euler = (math.pi / 2.0, 0, math.pi)
log("TARGHE + STEMMA muro ok")


def lamp(name, kind, energy, loc, color, angle=0.9, target=None,
         target_xyz=None, shadow=False):
    bpy.ops.object.light_add(type=kind, location=loc)
    LL = bpy.context.active_object
    LL.name = name
    try:
        LL.data.use_shadow = shadow
    except Exception:
        pass
    LL.data.energy = energy
    LL.data.color = color
    try:
        if kind == "SPOT":
            LL.data.spot_size = angle
    except Exception:
        pass
    if target_xyz is not None:
        _t = bpy.data.objects.new("tgt_%s" % name, None)
        SC.collection.objects.link(_t)
        _t.location = target_xyz
        target = _t
    if target is not None:
        cc = LL.constraints.new("TRACK_TO")
        cc.target = target
        cc.track_axis = "TRACK_NEGATIVE_Z"
        cc.up_axis = "UP_Y"
    return LL


SC.world.node_tree.nodes.get("Background").inputs[1].default_value = 1.0
lamp("SoleCaldo", "SUN", 0.22, (0, 8.0, 9.0), (1.0, 0.62, 0.35),
     target_xyz=(0, 0.0, 1.4))
lamp("SoleFreddoCam", "SUN", 0.06, (0, 11.0, 4.0), (0.55, 0.65, 0.9),
     target_xyz=(0, 0.0, 1.0))
for _ii, _px in enumerate([-5.0, -2.5, 0.0, 2.5, 5.0]):
    lamp("PuntoCaldo%d" % _ii, "POINT", 60, (_px, 1.6, 2.3),
         (1.0, 0.63, 0.36))
lamp("SpotMaglia10", "SPOT", 80, (J10["x"], 1.9, 2.9), (1.0, 0.8, 0.6),
     angle=0.5, target=MAG["Maglia_10"][0], shadow=True)
lamp("LuceBluPavimento", "POINT", 60, (0.5, 0.8, 0.35), (0.30, 0.50, 1.0))

# camere + inquadrature automatiche + 7 render + salvataggio
def camera(name, loc, tgt_xyz, lens=50):
    bpy.ops.object.camera_add(location=loc)
    cm = bpy.context.active_object
    cm.name = name
    cm.data.lens = lens
    _t = bpy.data.objects.new("tmp_tgt", None)
    SC.collection.objects.link(_t)
    _t.location = tgt_xyz
    cc = cm.constraints.new("TRACK_TO")
    cc.target = _t
    cc.track_axis = "TRACK_NEGATIVE_Z"
    cc.up_axis = "UP_Y"
    return cm


def fit_cam(cam, punti, marg=0.06):
    bpy.context.view_layer.update()
    _mnx = _mxx = _mny = _mxy = 0.5
    for _t in range(40):
        bpy.context.view_layer.update()
        _xs = []
        _ys = []
        for _p in punti:
            try:
                _ndc = world_to_camera_view(SC, cam, Vector(_p))
            except Exception:
                continue
            _xs.append(_ndc.x)
            _ys.append(_ndc.y)
        if not _xs:
            break
        _mnx, _mxx = min(_xs), max(_xs)
        _mny, _mxy = min(_ys), max(_ys)
        if (_mnx > marg and _mxx < 1 - marg
                and _mny > marg and _mxy < 1 - marg):
            break
        _d = cam.location - cam.constraints[0].target.location
        cam.location = cam.location + _d * 0.06
    log("%s fit: x[%.2f,%.2f] y[%.2f,%.2f]" % (cam.name, _mnx, _mxx,
                                               _mny, _mxy))
    return (_mnx, _mxx, _mny, _mxy)


def punti_maglia(jj):
    _cp, _ = MAG[jj["maglia"]]
    bpy.context.view_layer.update()
    return [tuple(_cp.matrix_world @ Vector(cc)) for cc in _cp.bound_box]


CAM_ALL = camera("Cam_Totale", (0, 7.2, 1.35), (0, 0.1, 1.35), lens=26)
CAM_DET = camera("Cam_Reparto", (0, 7.5, 1.45), (0, BAR_Y, 1.30), lens=50)
_all = []
for _jj in JERSEYS:
    _all += punti_maglia(_jj)
_all += [(X_MIN - 0.4, BAR_Y, BAR_Z), (X_MAX + 0.3, BAR_Y, BAR_Z)]
CAM_ALL.location = (_span * 0.42, 5.4, 1.7)
CAM_ALL.constraints[0].target.location = (0, 0.15, 1.30)
fit_cam(CAM_ALL, _all + [(0, 0.06, 2.95), (0, 0.06, 0.07)])
_mez = [jj for jj in JERSEYS if jj["reparto"] == "CENTROCAMPISTI"]
_rep = []
for _jj in _mez:
    _rep += punti_maglia(_jj)
_cx = GROUPS["CENTROCAMPISTI"]["cx"]
CAM_DET.location = (_cx, 3.1, 1.42)
CAM_DET.constraints[0].target.location = (_cx, BAR_Y, 1.28)
fit_cam(CAM_DET, _rep)
CAM_V = camera("Cam_9x16", (0, 3.1, 1.42), (0, BAR_Y, 1.28), lens=50)
_cxd = GROUPS["DIFENSORI"]["cx"]
CAM_V.location = (_cxd, 3.1, 1.42)
CAM_V.constraints[0].target.location = (_cxd, BAR_Y, 1.28)
_dif = []
for _jj in [jj for jj in JERSEYS if jj["reparto"] == "DIFENSORI"]:
    _dif += punti_maglia(_jj)
fit_cam(CAM_V, _dif)
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)


def set_rest():
    # posa da dietro: schiena (-Y) verso la camera (+Y). Posa base:
    # petto=+Y, quindi rotazione Z di PI + angolo riposo.
    for _jj in JERSEYS:
        _back = math.pi + (math.pi - _jj["phi"])
        for _oo in MAG[_jj["maglia"]]:
            _oo.location = (_jj["x"], BAR_Y, BAR_Z)
            _oo.rotation_euler = (0, 0, _back)
        _jj["rest"] = _back


def render(path, cam, rx, ry):
    if os.path.exists(path):
        log("SKIP (esiste): %s" % path)
        return
    SC.camera = cam
    SC.render.resolution_x, SC.render.resolution_y = rx, ry
    SC.render.resolution_percentage = 100
    SC.render.filepath = path
    bpy.ops.render.render(write_still=True)
    log("RENDER: %s" % path)


set_rest()
render(os.path.join(RENDER_DIR, "v02_barra.png"), CAM_ALL, 1920, 1080)
render(os.path.join(RENDER_DIR, "v02_reparto.png"), CAM_DET, 1920, 1080)
render(os.path.join(RENDER_DIR, "v02_9x16.png"), CAM_V, 1080, 1920)
# girata: la 10 ruota di PI (petto alla camera) e avanza di 25 cm
for _oo in MAG["Maglia_10"]:
    _oo.location = (J10["x"], BAR_Y + HOVER_DY, BAR_Z)
    _oo.rotation_euler = (0, 0, J10.get("rest", math.pi) + math.pi)
bpy.ops.object.light_add(type="POINT",
                         location=(J10["x"], BAR_Y + 1.1, BAR_Z + 0.3))
_lh = bpy.context.active_object
_lh.name = "PuntoHover10"
_lh.data.energy = 40
_lh.data.color = (1.0, 0.72, 0.45)
try:
    _lh.data.use_shadow = False
except Exception:
    pass
render(os.path.join(RENDER_DIR, "v02_girata.png"), CAM_DET, 1920, 1080)
set_rest()
try:
    bpy.data.objects.remove(_lh)
except Exception:
    pass
_cp10, _gr10 = MAG["Maglia_10"]
_cp10.location = (0, 2.2, 1.35)
_cp10.rotation_euler = (0, 0, 0)
_gr10.location = (0, 2.2, 1.35)
_gr10.rotation_euler = (0, 0, 0)
for _oo in (_cp10, _gr10):
    pass
_nasc = []
for _oo in list(bpy.data.objects):
    if _oo in (_cp10, _gr10) or _oo.type in ("CAMERA", "LIGHT"):
        continue
    if _oo.name.startswith(("Maglia_", "Gruccia_", "Targa_")) \
            or _oo.name in ("Barra", "Staffa", "Staffa.001",
                            "Stemma_Muro", "Stemma_Testo"):
        try:
            _oo.hide_render = True
            _nasc.append(_oo)
        except Exception:
            pass
bpy.ops.object.light_add(type="POINT", location=(0, 1.1, 1.7))
_lf = bpy.context.active_object
_lf.data.energy = 55
_lf.data.color = (1.0, 0.68, 0.42)
try:
    _lf.data.use_shadow = False
except Exception:
    pass
CAM_B = camera("Cam_Retro", (0, 3.2, 1.3), (0, 2.2, 1.25), lens=45)
render(os.path.join(RENDER_DIR, "v02_retro.png"), CAM_B, 1080, 1080)
for _oo in _nasc:
    try:
        _oo.hide_render = False
    except Exception:
        pass
set_rest()
_cp10.location = (0, 2.2, 1.35)
_cp10.rotation_euler = (0, 0, math.pi)
_gr10.location = (0, 2.2, 1.35)
_gr10.rotation_euler = (0, 0, math.pi)
CAM_F = camera("Cam_Fronte", (0, 3.2, 1.3), (0, 2.2, 1.25), lens=45)
_nasc2 = []
for _oo in list(bpy.data.objects):
    if _oo in (_cp10, _gr10, CAM_F, _lf) or _oo.type == "LIGHT":
        continue
    if _oo.name.startswith(("Maglia_", "Gruccia_", "Targa_")) \
            or _oo.name in ("Barra", "Staffa", "Staffa.001",
                            "Stemma_Muro", "Stemma_Testo"):
        try:
            _oo.hide_render = True
            _nasc2.append(_oo)
        except Exception:
            pass
render(os.path.join(RENDER_DIR, "v02_fronte.png"), CAM_F, 1080, 1080)
for _oo in _nasc2:
    try:
        _oo.hide_render = False
    except Exception:
        pass
log("FINITO. blend: %s" % BLEND_PATH)
print("REGISTRO_DATI: %s" % REG, flush=True)

