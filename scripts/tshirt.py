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
TORSO = [  # z, rx, ry   (misurati sul riferimento: altezza 0,74 m, corpo largo 0,37 m, collo 0,155 m)
    (0.000, 0.0775, 0.066), (-0.010, 0.110, 0.075), (-0.024, 0.150, 0.084), (-0.040, 0.176, 0.092),
    (-0.070, 0.186, 0.099), (-0.130, 0.186, 0.105), (-0.220, 0.183, 0.106), (-0.330, 0.181, 0.102),
    (-0.460, 0.181, 0.098), (-0.600, 0.185, 0.095), (-0.740, 0.192, 0.093)]
Z_ORLO = -0.740
NECK_RX, NECK_RY, NECK_Z = 0.0775, 0.062, -0.006
SLEEVE = {  # manica "set-in": parte quasi orizzontale sulla spalla e poi cade, svasata verso il polsino
    "pts": [(0.120, -0.090), (0.170, -0.098), (0.205, -0.130), (0.230, -0.200), (0.248, -0.285)],
    "ru": [0.045, 0.052, 0.058, 0.062, 0.065], "rv": [0.058, 0.056, 0.055, 0.055, 0.056]}


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
        fs = [f for f in bm.faces if lato * f.calc_center_median().x > 0.262]          # solo la manica: il piano non deve toccare il busto
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
    # niente vertici sciolti; poi il peso dell'orlo (distanza dai bordi liberi)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    return ob


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
    bp2 = np.array([p for p in bp if not (p[2] > -0.09 and abs(p[0]) < 0.1)])     # bordi liberi tranne il collo
    for i in range(n):
        d = float(np.sqrt(((bp - pos[i]) ** 2).sum(1)).min()) if len(bp) else 1.0
        w = 0.42 + 0.58 * (1.0 - float(_smooth(0.012, 0.034, d)))
        vg.add([i], w, "REPLACE")
        d2 = float(np.sqrt(((bp2 - pos[i]) ** 2).sum(1)).min()) if len(bp2) else 1.0
        vc.add([i], math.exp(-(((d2 - 0.020) / 0.0055) ** 2)), "REPLACE")          # riga di cucitura del risvolto a 2 cm dal bordo
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
    for _ in range(6):                                                         # leviga il contorno
        P = 0.5 * P + 0.25 * (np.roll(P, 1, 0) + np.roll(P, -1, 0))
    cen = P.mean(0)
    bm = bmesh.new()
    nsegc, nsec = len(P), 14
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
            ro, rz = 0.0078 * math.cos(a), 0.0115 * math.sin(a)
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
def materiale(nome, colore, rough=0.85, sheen=0.55, bump=0.35, scala=900.0):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    pb = nt.nodes["Principled BSDF"]
    pb.inputs["Base Color"].default_value = colore
    pb.inputs["Roughness"].default_value = rough
    if "Sheen Weight" in pb.inputs:
        pb.inputs["Sheen Weight"].default_value = sheen
        pb.inputs["Sheen Roughness"].default_value = 0.5
    if "Subsurface Weight" in pb.inputs:
        pb.inputs["Subsurface Weight"].default_value = 0.12
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
    bp.inputs["Distance"].default_value = 0.0004
    nt.links.new(tc.outputs["Object"], ma.inputs["Vector"])
    nt.links.new(ma.outputs["Vector"], wv.inputs["Vector"])
    nt.links.new(ma.outputs["Vector"], no.inputs["Vector"])
    nt.links.new(wv.outputs["Fac"], mi.inputs[0])
    nt.links.new(no.outputs["Fac"], mi.inputs[2])
    nt.links.new(mi.outputs["Value"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], pb.inputs["Normal"])
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
    amb.inputs["Strength"].default_value = 0.70
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

    area("Key", (-1.6, 3.0, 1.0), 66.0, 3.5, (1.0, 0.99, 0.98))
    area("Fill", (2.8, 2.4, -0.4), 24.0, 3.5, (0.90, 0.94, 1.0))
    area("Alto", (0.0, 1.2, 2.2), 14.0, 2.5, (0.96, 0.97, 1.0))
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
    pesi_orlo(ob)
    sol = ob.modifiers.new("Spessore", "SOLIDIFY")
    sol.thickness = 0.0085
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
    ds.strength = 0.0042
    ds.mid_level = 0.5
    for p in ob.data.polygons:
        p.use_smooth = True
    bianco = materiale("Cotone", (0.80, 0.81, 0.86, 1.0))
    ob.data.materials.append(bianco)
    c = collo(ob)
    c.data.materials.append(materiale("Costine", (0.78, 0.79, 0.84, 1.0), bump=0.6, scala=1400.0))
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
    print("TSHIRT_OK", os.path.join(out, "tshirt.png"))


main()
