"""tshirt.py - maglietta bianca da manichino ("ghost mannequin"), modellata e resa in Blender come nell'immagine di riferimento.

Uso:  blender -b -P tshirt.py -- CARTELLA [PIXEL_LARGHEZZA [CAMPIONI]]

Scrive CARTELLA/tshirt.png (render Cycles), CARTELLA/tshirt.blend e CARTELLA/tshirt.glb.
Come si costruisce (niente simulazione):
 1. torso a sezioni ellittiche (spalle in pendenza, petto pieno, fianchi, orlo) + due maniche a tubo curvo con sezione ellittica;
 2. le tre parti si uniscono con un Remesh a voxel (unione morbida, raccordi spalla/manica senza spigoli) e si lisciano;
 3. si tagliano le aperture (collo, due polsini, orlo) e il guscio si ispessisce verso l'interno: 4 mm di tessuto, 9 mm sugli orli (risvolto);
 4. girocollo a costine, leggere grinze (rumore) e materiale cotone bianco con sheen.
"""
import math
import os
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Vector


def _smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ forme
TORSO = [  # z, rx, ry   (misurati sul riferimento: proporzione larghezza/altezza 0,83; busto 0,35 m, orlo 0,38 m)
    (0.000, 0.070, 0.066), (-0.010, 0.105, 0.075), (-0.025, 0.158, 0.084), (-0.042, 0.196, 0.092),
    (-0.062, 0.214, 0.097), (-0.085, 0.210, 0.100), (-0.110, 0.198, 0.103), (-0.140, 0.182, 0.105),
    (-0.220, 0.174, 0.106), (-0.330, 0.172, 0.102),
    (-0.460, 0.172, 0.098), (-0.600, 0.180, 0.095), (-0.740, 0.192, 0.093)]
Z_ORLO = -0.740
NECK_RX, NECK_RY, NECK_Z = 0.070, 0.062, -0.006
SLEEVE = {  # manica "set-in": parte quasi orizzontale sulla spalla e poi cade, svasata verso il polsino
    "pts": [(0.130, -0.088), (0.176, -0.096), (0.211, -0.128), (0.236, -0.195), (0.258, -0.292)],
    "ru": [0.047, 0.054, 0.062, 0.064, 0.062], "rv": [0.058, 0.056, 0.054, 0.051, 0.048]}


def _ring_loft(bm, anelli, chiudi_alto=True, chiudi_basso=True):
    n = len(anelli[0])
    vs = [[bm.verts.new(p) for p in ring] for ring in anelli]
    for i in range(len(vs) - 1):
        for k in range(n):
            bm.faces.new((vs[i][k], vs[i][(k + 1) % n], vs[i + 1][(k + 1) % n], vs[i + 1][k]))
    if chiudi_alto:
        bm.faces.new(vs[0][::-1])
    if chiudi_basso:
        bm.faces.new(vs[-1])


def _mesh_da_bm(bm, nome):
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def torso(nseg=64):
    bm = bmesh.new()
    anelli = []
    for (z, rx, ry) in TORSO:
        yc = 0.010 * float(_smooth(-0.02, -0.22, z)) - 0.004
        anelli.append([(rx * math.cos(2 * math.pi * k / nseg), yc + ry * math.sin(2 * math.pi * k / nseg), z) for k in range(nseg)])
    _ring_loft(bm, anelli)
    return _mesh_da_bm(bm, "Torso")


def manica(lato, nseg=40):
    bm = bmesh.new()
    P = [Vector((lato * x, 0.0, z)) for (x, z) in SLEEVE["pts"]]
    # polilinea piu' fitta (Catmull-Rom semplice)
    dense, ru, rv = [], [], []
    for i in range(len(P) - 1):
        for t in np.linspace(0, 1, 6, endpoint=(i == len(P) - 2)):
            p0, p1 = P[max(0, i - 1)], P[i]
            p2, p3 = P[i + 1], P[min(len(P) - 1, i + 2)]
            pt = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
            dense.append(pt)
            ru.append(SLEEVE["ru"][i] * (1 - t) + SLEEVE["ru"][i + 1] * t)
            rv.append(SLEEVE["rv"][i] * (1 - t) + SLEEVE["rv"][i + 1] * t)
    anelli = []
    for i, c in enumerate(dense):
        tg = (dense[min(i + 1, len(dense) - 1)] - dense[max(i - 1, 0)]).normalized()
        u = tg.cross(Vector((0, 1, 0))).normalized()
        v = Vector((0, 1, 0))
        anelli.append([tuple(c + u * (ru[i] * math.cos(2 * math.pi * k / nseg)) + v * (rv[i] * math.sin(2 * math.pi * k / nseg))) for k in range(nseg)])
    _ring_loft(bm, anelli)
    ob = _mesh_da_bm(bm, "Manica%+d" % lato)
    return ob, dense[-1], (dense[-1] - dense[-2]).normalized()


def unisci_e_taglia():
    t = torso()
    m1, e1, d1 = manica(+1)
    m2, e2, d2 = manica(-1)
    for o in (t, m1, m2):
        o.select_set(True)
    bpy.context.view_layer.objects.active = t
    bpy.ops.object.join()
    ob = t
    ob.name = "Maglietta"
    rm = ob.modifiers.new("Remesh", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = 0.0045
    rm.use_smooth_shade = True
    bpy.ops.object.modifier_apply(modifier="Remesh")
    sm = ob.modifiers.new("Liscia", "SMOOTH")
    sm.factor = 0.8
    sm.iterations = 14
    bpy.ops.object.modifier_apply(modifier="Liscia")
    # taglio delle aperture: orlo e polsini con piani esatti (bordi puliti), collo con scollo piu' basso davanti
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, Z_ORLO), plane_no=(0, 0, 1),
                           clear_outer=False, clear_inner=True)
    for lato, (e, d) in ((1, (e1, d1)), (-1, (e2, d2))):
        fs = [f for f in bm.faces if lato * f.calc_center_median().x > 0.178 and f.calc_center_median().z > -0.40]          # solo la manica: il piano non deve toccare il busto
        es = list({ed for f in fs for ed in f.edges})
        vs = list({v for f in fs for v in f.verts})
        bmesh.ops.bisect_plane(bm, geom=vs + es + fs, plane_co=tuple(e), plane_no=tuple(d), clear_outer=True, clear_inner=False)
    togli = []
    for f in bm.faces:
        c = f.calc_center_median()
        if abs(c.x) >= NECK_RX or c.z <= -0.075:
            continue
        w = math.sqrt(1.0 - (c.x / NECK_RX) ** 2)
        quota = NECK_Z - (0.046 if c.y > 0 else 0.010) * w          # scollo: davanti a goccia, dietro quasi dritto
        if c.z > quota:
            togli.append(f)
    bmesh.ops.delete(bm, geom=togli, context="FACES")
    # bordo del collo senza scalini: lisciatura laplaciana solo lungo l'anello di bordo
    bv = [v for v in bm.verts if any(e.is_boundary for e in v.link_edges) and v.co.z > -0.09 and abs(v.co.x) < 0.1]
    for _ in range(40):
        nuovi = {}
        for v in bv:
            vic = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(vic) == 2:
                nuovi[v] = (v.co + 0.5 * (vic[0].co + vic[1].co)) / 2.0 * 1.0
                nuovi[v] = 0.5 * v.co + 0.25 * (vic[0].co + vic[1].co)
        for v, c in nuovi.items():
            v.co = c
    # niente vertici sciolti; poi il peso dell'orlo (distanza dai bordi liberi)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def pieghe_frontali(ob):
    """Pieghe di caduta sul davanti (ventaglio dalle ascelle verso il petto, tensione sotto il collo, onde del ventre): creste e solchi morbidi
    spostati lungo la normale (asse Y) del guscio, piu' leggeri dietro."""
    me = ob.data
    n = len(me.vertices)
    pos = np.array([v.co[:] for v in me.vertices])
    X, Z = pos[:, 0], pos[:, 2]

    def cresta(p0, p1, amp, w):
        a = np.array(p0); b = np.array(p1)
        ab = b - a
        t = np.clip(((X - a[0]) * ab[0] + (Z - a[1]) * ab[1]) / (ab @ ab), 0.0, 1.0)
        d2 = (X - (a[0] + t * ab[0])) ** 2 + (Z - (a[1] + t * ab[1])) ** 2
        return amp * np.exp(-d2 / w ** 2) * np.sin(np.pi * np.clip(t, 0, 1)) ** 0.5
    dy = np.zeros(n)
    for sg, k in ((1, 1.0), (-1, 0.8)):                         # il lato sinistro e' un po' diverso dal destro
        dy += k * cresta((sg * 0.172, -0.125), (sg * 0.035, -0.235), 0.0028, 0.017)
        dy += k * cresta((sg * 0.176, -0.160), (sg * 0.075, -0.345), 0.0023, 0.020)
        dy += k * cresta((sg * 0.168, -0.098), (sg * 0.060, -0.172), -0.0023, 0.015)
        dy += k * cresta((sg * 0.080, -0.045), (sg * 0.135, -0.105), -0.0020, 0.016)
        dy += k * cresta((sg * 0.105, -0.200), (sg * 0.118, -0.700), 0.0045, 0.035)       # ombre larghe e morbide verticali del busto
        dy += k * cresta((sg * 0.152, -0.210), (sg * 0.158, -0.660), -0.0035, 0.030)
        dy += k * cresta((sg * 0.205, -0.105), (sg * 0.240, -0.265), 0.0030, 0.012)       # pieghe di caduta sulle maniche
        dy += k * cresta((sg * 0.188, -0.115), (sg * 0.214, -0.250), -0.0061, 0.011)
        dy += k * cresta((sg * 0.232, -0.125), (sg * 0.252, -0.215), 0.0038, 0.010)
        dy += k * cresta((sg * 0.215, -0.170), (sg * 0.246, -0.236), -0.0042, 0.009)       # pieghe corte e storte: la stoffa non cade a righe regolari
        dy += k * cresta((sg * 0.196, -0.200), (sg * 0.222, -0.262), 0.0035, 0.008)
        dy += k * cresta((sg * 0.240, -0.150), (sg * 0.230, -0.205), -0.0030, 0.009)
        dy += k * cresta((sg * 0.060, -0.390), (sg * 0.085, -0.640), 0.0020, 0.030)
        dy += k * cresta((sg * 0.130, -0.420), (sg * 0.150, -0.600), -0.0017, 0.026)
    dy += cresta((-0.12, -0.625), (0.10, -0.600), 0.0014, 0.020)
    fronte = pos[:, 1] > 0
    for i in range(n):
        v = me.vertices[i]
        if fronte[i]:
            v.co.y += dy[i]
        else:
            v.co.y -= 0.35 * dy[i]
    me.update()


def pesi_orlo(ob):
    me = ob.data
    n = len(me.vertices)
    pos = np.array([v.co[:] for v in me.vertices])
    bordo = set()
    from collections import Counter
    cnt = Counter()
    for p in me.polygons:
        for a, b in zip(p.vertices, list(p.vertices[1:]) + [p.vertices[0]]):
            cnt[tuple(sorted((a, b)))] += 1
    for (a, b), c in cnt.items():
        if c == 1:
            bordo.add(a)
            bordo.add(b)
    bp = pos[sorted(bordo)]
    vg = ob.vertex_groups.new(name="orlo")
    vc = ob.vertex_groups.new(name="cucitura")
    vp = ob.vertex_groups.new(name="pieghe")
    ca = me.color_attributes.new("lineacu", "FLOAT_COLOR", "POINT")
    bp2 = np.array([p for p in bp if not (p[2] > -0.09 and abs(p[0]) < 0.1)])     # bordi liberi tranne il collo
    for i in range(n):
        d = float(np.sqrt(((bp - pos[i]) ** 2).sum(1)).min()) if len(bp) else 1.0
        w = 0.42 + 0.58 * (1.0 - float(_smooth(0.012, 0.034, d)))
        vg.add([i], w, "REPLACE")
        d2 = float(np.sqrt(((bp2 - pos[i]) ** 2).sum(1)).min()) if len(bp2) else 1.0
        x, y, z = pos[i]
        wp = max(math.exp(-(((abs(x) - 0.17) ** 2 + (z + 0.12) ** 2) / 0.08 ** 2)),            # ascelle
                 math.exp(-((x ** 2 + (z + 0.05) ** 2) / 0.09 ** 2)),                           # sotto il collo
                 0.45 * math.exp(-((z + 0.70) ** 2) / 0.07 ** 2))                                       # sopra l'orlo
        vp.add([i], wp, "REPLACE")
        wcu = math.exp(-(((d2 - 0.020) / 0.0055) ** 2))
        ca.data[i].color = (wcu, wcu, wcu, 1.0)
        vc.add([i], wcu, "REPLACE")          # riga di cucitura del risvolto a 2 cm dal bordo
    return vg


def collo(ob_parent):
    """Girocollo a costine: nastro lungo l'ellisse del collo (sezione 3 x 1,1 cm arrotondata)."""
    # il nastro segue il bordo reale dell'apertura del collo (anello di bordo del guscio gia' tagliato)
    me = ob_parent.data
    adj = {}
    for e in me.edges:
        pass
    from collections import Counter, defaultdict
    cnt = Counter()
    for p in me.polygons:
        for a, b in zip(p.vertices, list(p.vertices[1:]) + [p.vertices[0]]):
            cnt[tuple(sorted((a, b)))] += 1
    adj = defaultdict(list)
    for (a, b), c in cnt.items():
        if c == 1:
            va, vb = me.vertices[a].co, me.vertices[b].co
            if va.z > -0.09 and vb.z > -0.09 and abs(va.x) < 0.1 and abs(vb.x) < 0.1:
                adj[a].append(b)
                adj[b].append(a)
    start = max(adj, key=lambda i: me.vertices[i].co.y)
    ordine, prev, cur = [start], None, start
    while True:
        nxt = [n for n in adj[cur] if n != prev]
        if not nxt or nxt[0] == start:
            break
        prev, cur = cur, nxt[0]
        ordine.append(cur)
        if len(ordine) > len(adj):
            break
    P = np.array([me.vertices[i].co[:] for i in ordine])
    for _ in range(30):                                                        # leviga il contorno
        P = 0.5 * P + 0.25 * (np.roll(P, 1, 0) + np.roll(P, -1, 0))
    cen = P.mean(0)
    bm = bmesh.new()
    nsegc, nsec = len(P), 48
    anelli = []
    for k in range(nsegc):
        tg = Vector(P[(k + 1) % nsegc] - P[k - 1]).normalized()
        rad = Vector(P[k] - cen)
        rad.z = 0.0
        out = (rad - tg * rad.dot(tg)).normalized()                            # verso l'esterno, ortogonale al contorno
        up = Vector((0, 0, 1))
        up = (up - tg * up.dot(tg)).normalized()
        ring = []
        for s in range(nsec):
            a = 2 * math.pi * s / nsec
            c_, s_ = math.cos(a), math.sin(a)
            ro, rz = 0.0042 * math.copysign(abs(c_) ** 0.7, c_), 0.0125 * math.copysign(abs(s_) ** 0.7, s_)
            ro += 0.0009 * math.cos(2 * math.pi * 3.5 * (rz / 0.025 + 0.5)) * (math.copysign(1.0, c_) if abs(c_) > 0.2 else 0.0)      # nervature della costina, fuori e dentro lo scollo
            q = Vector(P[k]) + out * (ro + 0.0015) + up * (rz - 0.003)
            ring.append(tuple(q))
        anelli.append(ring)
    vs = [[bm.verts.new(p) for p in ring] for ring in anelli]
    for i in range(nsegc):
        for s in range(nsec):
            bm.faces.new((vs[i][s], vs[i][(s + 1) % nsec], vs[(i + 1) % nsegc][(s + 1) % nsec], vs[(i + 1) % nsegc][s]))
    ob = _mesh_da_bm(bm, "Collo")
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


# ------------------------------------------------------------------ materiali, luci, resa
def materiale(nome, colore, rough=0.90, sheen=0.60, bump=0.6, scala=800.0, interno_scuro=False, cuciture=False, fres=0.36, ao_dist=0.07, emiss=0.0, coste=False):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    pb = nt.nodes["Principled BSDF"]
    pb.inputs["Base Color"].default_value = colore
    pb.inputs["Roughness"].default_value = rough
    if "Sheen Weight" in pb.inputs:
        pb.inputs["Sheen Weight"].default_value = sheen
        pb.inputs["Sheen Roughness"].default_value = 0.55
    if emiss > 0 and "Emission Strength" in pb.inputs:
        pb.inputs["Emission Color"].default_value = (1, 1, 1, 1)
        pb.inputs["Emission Strength"].default_value = emiss
        if "Sheen Tint" in pb.inputs:
            pb.inputs["Sheen Tint"].default_value = (0.92, 0.94, 1.0, 1.0)
    if "Subsurface Weight" in pb.inputs:
        pb.inputs["Subsurface Weight"].default_value = 0.0
        pb.inputs["Subsurface Radius"].default_value = (0.01, 0.01, 0.01)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    ma = nt.nodes.new("ShaderNodeMapping")
    ma.inputs["Scale"].default_value = (scala, scala, scala)
    # trama del jersey: onde incrociate + rumore fine
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.wave_type = "BANDS"
    wv.inputs["Scale"].default_value = 1.0
    wv.inputs["Distortion"].default_value = 1.5
    no = nt.nodes.new("ShaderNodeTexNoise")
    no.inputs["Scale"].default_value = 1.0
    no.inputs["Detail"].default_value = 6.0
    mi = nt.nodes.new("ShaderNodeMath")
    mi.operation = "MULTIPLY_ADD"
    mi.inputs[1].default_value = 0.5
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.0012
    nt.links.new(tc.outputs["Object"], ma.inputs["Vector"])
    nt.links.new(ma.outputs["Vector"], wv.inputs["Vector"])
    nt.links.new(ma.outputs["Vector"], no.inputs["Vector"])
    nt.links.new(wv.outputs["Fac"], mi.inputs[0])
    nt.links.new(no.outputs["Fac"], mi.inputs[2])
    if coste:                               # nervature verticali del jersey (coste a maglia), visibili sul busto
        m2c = nt.nodes.new("ShaderNodeMapping")
        m2c.inputs["Scale"].default_value = (150.0, 14.0, 5.0)
        wv2 = nt.nodes.new("ShaderNodeTexWave")
        wv2.wave_type = "BANDS"
        wv2.bands_direction = "X"
        wv2.inputs["Scale"].default_value = 1.0
        wv2.inputs["Distortion"].default_value = 2.2
        wv2.inputs["Detail"].default_value = 3.0
        nt.links.new(tc.outputs["Object"], m2c.inputs["Vector"])
        nt.links.new(m2c.outputs["Vector"], wv2.inputs["Vector"])
        ad = nt.nodes.new("ShaderNodeMath")
        ad.operation = "MULTIPLY_ADD"
        ad.inputs[1].default_value = 1.0
        nt.links.new(wv2.outputs["Fac"], ad.inputs[0])
        nt.links.new(mi.outputs["Value"], ad.inputs[2])
        nt.links.new(ad.outputs["Value"], bp.inputs["Height"])
    else:
        nt.links.new(mi.outputs["Value"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], pb.inputs["Normal"])
    # leggera variazione di tono della maglia (maglia a punto jersey): moltiplica il colore di base
    mg = nt.nodes.new("ShaderNodeMath")
    mg.operation = "MULTIPLY_ADD"
    mg.inputs[1].default_value = 0.34
    mg.inputs[2].default_value = 0.80
    nt.links.new(mi.outputs["Value"], mg.inputs[0])
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.blend_type = "MULTIPLY"
    mx.inputs[0].default_value = 1.0
    mx.inputs[6].default_value = colore
    nt.links.new(mg.outputs["Value"], mx.inputs[7])
    # profondita': occlusione ambientale nelle pieghe + scurimento morbido verso il bordo della sagoma
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = ao_dist
    ao.samples = 16
    nt.links.new(mx.outputs[2], ao.inputs["Color"])
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.55
    fa = nt.nodes.new("ShaderNodeMath")
    fa.operation = "MULTIPLY_ADD"
    fa.inputs[1].default_value = -fres
    fa.inputs[2].default_value = 1.0
    nt.links.new(lw.outputs["Fresnel"], fa.inputs[0])
    m2 = nt.nodes.new("ShaderNodeMix")
    m2.data_type = "RGBA"
    m2.blend_type = "MULTIPLY"
    m2.inputs[0].default_value = 1.0
    nt.links.new(ao.outputs["Color"], m2.inputs[6])
    cb = nt.nodes.new("ShaderNodeCombineColor")           # le ombre sono lavanda/blu come nel riferimento: il rosso cala di piu' del blu
    for ch, (k, off) in zip(("Red", "Green", "Blue"), ((1.0, 0.0), (0.86, 0.14), (0.70, 0.30))):
        mk = nt.nodes.new("ShaderNodeMath")
        mk.operation = "MULTIPLY_ADD"
        mk.inputs[1].default_value = k
        mk.inputs[2].default_value = off
        nt.links.new(fa.outputs["Value"], mk.inputs[0])
        nt.links.new(mk.outputs["Value"], cb.inputs[ch])
    nt.links.new(cb.outputs["Color"], m2.inputs[7])
    ultimo = m2
    if interno_scuro:                       # dentro lo scollo il retro e' in ombra (sfumatura grigia come nel riferimento)
        gp = nt.nodes.new("ShaderNodeNewGeometry")
        sp = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(gp.outputs["Position"], sp.inputs["Vector"])
        my = nt.nodes.new("ShaderNodeMapRange")
        my.inputs["From Min"].default_value, my.inputs["From Max"].default_value = -0.02, -0.06
        mz = nt.nodes.new("ShaderNodeMapRange")
        mz.inputs["From Min"].default_value, mz.inputs["From Max"].default_value = -0.16, -0.04
        nt.links.new(sp.outputs["Y"], my.inputs["Value"])
        nt.links.new(sp.outputs["Z"], mz.inputs["Value"])
        mm = nt.nodes.new("ShaderNodeMath")
        mm.operation = "MULTIPLY"
        nt.links.new(my.outputs["Result"], mm.inputs[0])
        nt.links.new(mz.outputs["Result"], mm.inputs[1])
        mf = nt.nodes.new("ShaderNodeMath")
        mf.operation = "MULTIPLY_ADD"
        mf.inputs[1].default_value = -0.28
        mf.inputs[2].default_value = 1.0
        nt.links.new(mm.outputs["Value"], mf.inputs[0])
        m3 = nt.nodes.new("ShaderNodeMix")
        m3.data_type = "RGBA"
        m3.blend_type = "MULTIPLY"
        m3.inputs[0].default_value = 1.0
        nt.links.new(m2.outputs[2], m3.inputs[6])
        nt.links.new(mf.outputs["Value"], m3.inputs[7])
        ultimo = m3
    if cuciture:                            # riga del risvolto su orlo e polsini, calcolata dalla posizione (non dipende da attributi)
        def M(op, a_, b_=None, c_=None):
            n = nt.nodes.new("ShaderNodeMath")
            n.operation = op
            for k, v in enumerate((a_, b_, c_)):
                if v is None:
                    continue
                if isinstance(v, (int, float)):
                    n.inputs[k].default_value = v
                else:
                    nt.links.new(v, n.inputs[k])
            return n.outputs["Value"]

        def MR(v, a_, b_):
            n = nt.nodes.new("ShaderNodeMapRange")
            n.inputs["From Min"].default_value, n.inputs["From Max"].default_value = a_, b_
            nt.links.new(v, n.inputs["Value"])
            return n.outputs["Result"]

        gq = nt.nodes.new("ShaderNodeNewGeometry")
        sq = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(gq.outputs["Position"], sq.inputs["Vector"])
        ax = M("ABSOLUTE", sq.outputs["X"])
        zz = sq.outputs["Z"]
        # polsino: distanza lungo l'asse della manica dal piano di taglio (asse (0.309, -0.951) in (|x|, z))
        dc = M("ADD", M("MULTIPLY", M("SUBTRACT", ax, 0.258), 0.221), M("MULTIPLY", M("ADD", zz, 0.268), -0.961))
        lc = M("EXPONENT", M("MULTIPLY", M("POWER", M("DIVIDE", M("ADD", dc, 0.014), 0.0028), 2.0), -1.0))
        mc_ = M("MULTIPLY", MR(ax, 0.18, 0.20), MR(zz, -0.42, -0.38))
        lc2 = M("EXPONENT", M("MULTIPLY", M("POWER", M("DIVIDE", M("ADD", dc, 0.026), 0.0028), 2.0), -1.0))
        lc = M("MAXIMUM", lc, M("MULTIPLY", lc2, 0.7))
        lh = M("EXPONENT", M("MULTIPLY", M("POWER", M("DIVIDE", M("ADD", zz, 0.724), 0.0030), 2.0), -1.0))
        mh_ = M("MULTIPLY", MR(ax, 0.23, 0.20), MR(zz, -0.50, -0.55))
        # fianchi del busto piu' scuri (lavanda), luce a clessidra come nel riferimento
        fianco = M("MULTIPLY", M("MULTIPLY", MR(ax, 0.09, 0.17), MR(ax, 0.215, 0.185)), MR(zz, -0.12, -0.17))
        fianco = M("MULTIPLY", fianco, M("ADD", M("MULTIPLY", MR(sq.outputs["X"], 0.04, -0.04), 0.9), 0.85))    # lato destro dell'immagine (-x) piu' scuro
        fianco = M("MAXIMUM", fianco, M("MULTIPLY", MR(ax, 0.19, 0.23), M("MULTIPLY", M("ADD", M("MULTIPLY", MR(sq.outputs["X"], 0.05, -0.05), 1.5), 0.0), 0.62)))      # maniche piu' scure del busto, di piu' a destra dell'immagine (la luce arriva da sinistra)
        lw2 = nt.nodes.new("ShaderNodeLayerWeight")                  # bordo destro dell'immagine in ombra marcata (nel riferimento e' molto piu' scuro del sinistro)
        lw2.inputs["Blend"].default_value = 0.45
        bordo_d = M("MULTIPLY", lw2.outputs["Fresnel"], MR(sq.outputs["X"], 0.0, -0.06))
        cbe = nt.nodes.new("ShaderNodeCombineColor")
        for ch, kk in (("Red", 0.60), ("Green", 0.54), ("Blue", 0.36)):
            mk = nt.nodes.new("ShaderNodeMath")
            mk.operation = "MULTIPLY_ADD"
            mk.inputs[1].default_value = -kk
            mk.inputs[2].default_value = 1.0
            nt.links.new(bordo_d, mk.inputs[0])
            nt.links.new(mk.outputs["Value"], cbe.inputs[ch])
        cbs = nt.nodes.new("ShaderNodeCombineColor")
        for ch, kk in (("Red", 0.24), ("Green", 0.21), ("Blue", 0.14)):
            mk = nt.nodes.new("ShaderNodeMath")
            mk.operation = "MULTIPLY_ADD"
            mk.inputs[1].default_value = -kk
            mk.inputs[2].default_value = 1.0
            nt.links.new(fianco, mk.inputs[0])
            nt.links.new(mk.outputs["Value"], cbs.inputs[ch])
        riga = M("MAXIMUM", M("MULTIPLY", lc, mc_), M("MULTIPLY", lh, mh_))
        mc = nt.nodes.new("ShaderNodeMath")
        mc.operation = "MULTIPLY_ADD"
        mc.inputs[1].default_value = -0.24
        mc.inputs[2].default_value = 1.0
        nt.links.new(riga, mc.inputs[0])
        m4 = nt.nodes.new("ShaderNodeMix")
        m4.data_type = "RGBA"
        m4.blend_type = "MULTIPLY"
        m4.inputs[0].default_value = 1.0
        nt.links.new(ultimo.outputs[2], m4.inputs[6])
        nt.links.new(mc.outputs["Value"], m4.inputs[7])
        m5 = nt.nodes.new("ShaderNodeMix")
        m5.data_type = "RGBA"
        m5.blend_type = "MULTIPLY"
        m5.inputs[0].default_value = 1.0
        nt.links.new(m4.outputs[2], m5.inputs[6])
        nt.links.new(cbs.outputs["Color"], m5.inputs[7])
        m6 = nt.nodes.new("ShaderNodeMix")
        m6.data_type = "RGBA"
        m6.blend_type = "MULTIPLY"
        m6.inputs[0].default_value = 1.0
        nt.links.new(m5.outputs[2], m6.inputs[6])
        nt.links.new(cbe.outputs["Color"], m6.inputs[7])
        ultimo = m6
    nt.links.new(ultimo.outputs[2], pb.inputs["Base Color"])
    return m


def luci_e_camera(sc, bersaglio=(0.0, 0.0, -0.355)):
    w = sc.world or bpy.data.worlds.new("Mondo")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.475, 0.475, 0.475, 1.0)   # grigio sfondo come il riferimento
    bg.inputs["Strength"].default_value = 1.0
    nt = w.node_tree                                                    # sfondo visibile grigio chiaro, luce ambiente piu' scura (ombre morbide sul tessuto)
    amb = nt.nodes.new("ShaderNodeBackground")
    amb.inputs["Color"].default_value = (0.60, 0.62, 0.68, 1.0)
    amb.inputs["Strength"].default_value = 0.95
    lp = nt.nodes.new("ShaderNodeLightPath")
    mx = nt.nodes.new("ShaderNodeMixShader")
    outn = nt.nodes["World Output"]
    nt.links.new(lp.outputs["Is Camera Ray"], mx.inputs["Fac"])
    nt.links.new(amb.outputs["Background"], mx.inputs[1])
    nt.links.new(bg.outputs["Background"], mx.inputs[2])
    nt.links.new(mx.outputs["Shader"], outn.inputs["Surface"])

    def area(nome, loc, energia, size, col=(1, 1, 1)):
        ld = bpy.data.lights.new(nome, "AREA")
        ld.energy = energia
        ld.size = size
        ld.color = col
        lo = bpy.data.objects.new(nome, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
        d = Vector(bersaglio) - Vector(loc)
        lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

    area("Key", (-1.2, 3.1, 0.9), 120.0, 3.5, (1.0, 0.99, 0.98))
    area("Fill", (1.8, 2.8, -0.2), 24.0, 3.5, (0.90, 0.94, 1.0))
    area("Alto", (0.0, 1.2, 2.2), 20.0, 2.5, (0.96, 0.97, 1.0))
    area("Rim", (0.0, -2.2, 0.3), 14.0, 2.0)
    cd = bpy.data.cameras.new("Cam")
    cd.lens = 85
    co = bpy.data.objects.new("Cam", cd)
    sc.collection.objects.link(co)
    co.location = (0.0, 3.9, -0.10)
    d = Vector(bersaglio) - co.location
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = co


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.abspath(argv[0]) if argv else os.path.abspath("out_tshirt")
    px = int(argv[1]) if len(argv) > 1 else 1280
    camp = int(argv[2]) if len(argv) > 2 else 96
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    ob = unisci_e_taglia()
    pieghe_frontali(ob)
    pesi_orlo(ob)
    sol = ob.modifiers.new("Spessore", "SOLIDIFY")
    sol.thickness = 0.0070
    sol.offset = -1.0
    sol.use_rim = True
    sol.thickness_vertex_group = 0.0
    sol.vertex_group = "orlo"
    cu = ob.modifiers.new("Cucitura", "DISPLACE")
    cu.vertex_group = "cucitura"
    cu.mid_level = 0.0
    cu.strength = -0.011
    sub = ob.modifiers.new("Subdiv", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 2
    sub.boundary_smooth = "ALL"
    # grinze leggere
    tx = bpy.data.textures.new("Grinze", "CLOUDS")
    tx.noise_scale = 0.11
    tx.noise_depth = 3
    ds = ob.modifiers.new("Grinze", "DISPLACE")
    ds.texture = tx
    ds.strength = 0.0022
    ds.mid_level = 0.5
    tx2 = bpy.data.textures.new("Drappeggio", "CLOUDS")      # ondulazioni larghe del tessuto che cade
    tx2.noise_scale = 0.05
    tx2.noise_depth = 3
    d2 = ob.modifiers.new("Drappeggio", "DISPLACE")
    d2.texture = tx2
    d2.strength = 0.0050
    d2.vertex_group = "pieghe"
    d2.mid_level = 0.5
    for p in ob.data.polygons:
        p.use_smooth = True
    bianco = materiale("Cotone", (0.76, 0.79, 0.90, 1.0), interno_scuro=True, cuciture=True, coste=True)
    ob.data.materials.append(bianco)
    c = collo(ob)
    c.data.materials.append(materiale("Costine", (0.74, 0.80, 0.97, 1.0), bump=0.9, scala=1400.0, interno_scuro=True, fres=0.10, ao_dist=0.012, emiss=0.15))
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = camp
    sc.cycles.use_denoising = True
    sc.render.resolution_x = px
    sc.render.resolution_y = int(px * 9 / 16)
    sc.view_settings.view_transform = "Standard"
    luci_e_camera(sc)
    sc.render.filepath = os.path.join(out, "tshirt.png")
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "tshirt.blend"))
    # grana fine della stoffa (come nel rendering di riferimento): rumore di luminanza solo sulla maglia
    img = bpy.data.images.load(os.path.join(out, "tshirt.png"))
    w_, h_ = img.size
    px_ = np.array(img.pixels[:], dtype=np.float32).reshape(h_, w_, 4)
    maglia_ = ((px_[..., 2] - px_[..., 0]) > 0.04) | (px_[..., :3].mean(2) > 0.82)
    rng = np.random.default_rng(7)
    gr = rng.normal(0.0, 0.011, (h_, w_)).astype(np.float32)
    gr = 0.6 * gr + 0.4 * (np.roll(gr, 1, 0) + np.roll(gr, 1, 1)) / 2        # leggera correlazione: grana, non neve
    px_[..., :3] = np.clip(px_[..., :3] + (gr * maglia_)[..., None], 0.0, 1.0)
    img.pixels = px_.ravel()
    img.filepath_raw = os.path.join(out, "tshirt.png")
    img.file_format = "PNG"
    img.save()
    print("TSHIRT_OK", os.path.join(out, "tshirt.png"))


main()
