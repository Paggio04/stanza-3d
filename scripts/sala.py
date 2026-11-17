"""sala.py - spogliatoio circolare con 20 armadietti (uno per giocatore).

Uso:  blender -b -P sala.py -- RENDER_DIR [PIXEL_LARGHEZZA [CAMPIONI [salva.blend]]]

Legge squadra.json (cartella sopra scripts/) e costruisce la sala. Le maglie
sono di maglia.py (copie collegate: una mesh sola). Sistema locale di ogni
armadietto: parete a y = 0, stanza verso +y, x = sinistra di chi guarda.
"""
import bpy
import bmesh
import json
import math
import os
import sys

import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maglia  # noqa: E402

RAGGIO = 4.5          # parete interna
ALTEZZA = 3.0         # soffitto
N_BAIE = 20           # armadietti (uno per giocatore)
N_SLOT = 21           # armadietti + la porta del tunnel (slot 0, a phi = 180 gradi)
PASSO = 2 * math.pi / N_SLOT
BAIA_W = 1.10         # larghezza di un armadietto
PILASTRO_W = 0.22
PORTA_W = 1.20        # luce della porta
PORTA_H = 2.35
SPESSORE_MURO = 0.55  # imbotte della porta
Z_ASTA = 2.02
Y_ASTA = 0.20
SLOT_TITOLARI = list(range(5, 16))                  # 11 titolari: arco davanti alla camera
SLOT_RISERVE = [16, 17, 18, 19, 20, 1, 2, 3, 4]    # 9 riserve: il resto, a destra e sinistra della porta


def phi_slot(j):
    """Angolo (convenzione Blender: P = R*(sin, cos)) dello slot j; la porta (0) sta a phi = pi."""
    a = math.pi + j * PASSO
    return (a + math.pi) % (2 * math.pi) - math.pi if j else math.pi


WEB = False           # True = materiali e mesh adatti a glTF (sito)
LOD = False           # True = versione leggera per telefoni (sala_bassa.glb)
OUT_TEX = "."
FPS = 30
ESEMPLARI = {}


# ------------------------------------------------------------------ materiali
def _immagine_legno(cartella):
    """Venatura verticale del legno, ripetibile. Salvata e incorporata nel .glb (HD 1024)."""
    if "legno_tex" in bpy.data.images:
        return bpy.data.images["legno_tex"]
    n = 512 if LOD else 1024 # HD: 1024 in alta, 512 nella bassa per restare nel budget (su telefono non si vede)
    U, V = np.meshgrid(np.arange(n) / n, np.arange(n) / n)
    rng = np.random.default_rng(7)

    def fibra(nodi, peso, k):
        """Rumore 1D periodico lungo U, leggermente spostato lungo V: vene dritte."""
        val = rng.random(nodi)
        uu = (U + 0.012 * np.sin(2 * math.pi * (V * k + rng.random()))) % 1.0 * nodi
        i0 = np.floor(uu).astype(int) % nodi
        t = uu - np.floor(uu)
        t = t * t * (3 - 2 * t)
        return peso * (val[i0] * (1 - t) + val[(i0 + 1) % nodi] * t)

    grana = fibra(28, 0.34, 1) + fibra(120, 0.30, 2) + fibra(460, 0.18, 3) + fibra(60, 0.18, 5) + 0.05 * rng.random((n, n))
    grana = np.clip((grana - grana.min()) / (grana.max() - grana.min()), 0, 1)
    grana = grana * grana * (3 - 2 * grana)  # HD: curva a S = venatura piu incisa, si vede anche da lontano
    scuro = np.array([0.22, 0.095, 0.038])  # HD: scuro piu profondo (prima 0.27/0.125/0.052, troppo slavato)
    chiaro = np.array([0.62, 0.345, 0.15])  # HD: chiaro piu caldo
    rgb = scuro[None, None, :] * (1 - grana[..., None]) + chiaro[None, None, :] * grana[..., None]
    rgba = np.concatenate([rgb, np.ones((n, n, 1))], axis=2).astype(np.float32)
    img = bpy.data.images.new("legno_tex", n, n, alpha=False)
    img.pixels.foreach_set(rgba[::-1].ravel())
    img.filepath_raw = os.path.join(cartella, "legno.png")
    img.file_format = "PNG"
    img.save()
    img.pack()
    return img


def _hex(h):
    return maglia._hex(h)


_MAT = {}


def mat(nome, colore, rough=0.5, metal=0.0, emis=0.0, bump=None, spec=0.5):
    if nome in _MAT:
        return _MAT[nome]
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    pb = nt.nodes["Principled BSDF"]
    pb.inputs["Base Color"].default_value = _hex(colore)
    pb.inputs["Roughness"].default_value = rough
    pb.inputs["Metallic"].default_value = metal
    if "Specular IOR Level" in pb.inputs:
        pb.inputs["Specular IOR Level"].default_value = spec
    if emis > 0:
        pb.inputs["Emission Color"].default_value = _hex(colore)
        pb.inputs["Emission Strength"].default_value = emis
    if bump == "legno" and WEB:
        it = nt.nodes.new("ShaderNodeTexImage")
        it.image = _immagine_legno(OUT_TEX)
        nt.links.new(it.outputs["Color"], pb.inputs["Base Color"])
        # HD: in glTF niente bump da nodi: si alza il contrasto via roughness bassa e speculare alto
        pb.inputs["Roughness"].default_value = 0.28
        if "Specular IOR Level" in pb.inputs:
            pb.inputs["Specular IOR Level"].default_value = 0.7
    elif bump == "legno":
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (30.0, 30.0, 2.0)   # venatura verticale
        wv = nt.nodes.new("ShaderNodeTexWave")
        wv.inputs["Scale"].default_value = 3.0
        wv.inputs["Distortion"].default_value = 6.0
        wv.inputs["Detail"].default_value = 2.0
        bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = 0.08
        bp.inputs["Distance"].default_value = 0.002
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
        nt.links.new(wv.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], pb.inputs["Normal"])
        # variazione di tono lungo la venatura
        cr = nt.nodes.new("ShaderNodeMix")
        cr.data_type = "RGBA"
        cr.inputs[6].default_value = _hex(colore)
        c2 = [min(1.0, v * 0.72) for v in _hex(colore)[:3]] + [1.0]
        cr.inputs[7].default_value = c2
        cr.inputs[0].default_value = 0.5
        nt.links.new(wv.outputs["Fac"], cr.inputs[0])
        nt.links.new(cr.outputs[2], pb.inputs["Base Color"])
    elif bump == "pavimento" and not WEB:
        no = nt.nodes.new("ShaderNodeTexNoise")
        no.inputs["Scale"].default_value = 120.0
        bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = 0.05
        bp.inputs["Distance"].default_value = 0.001
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(tc.outputs["Object"], no.inputs["Vector"])
        nt.links.new(no.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], pb.inputs["Normal"])
    _MAT[nome] = m
    return m


# ------------------------------------------------------------------ geometria
_MESH = {}


def _box_mesh(sx, sy, sz, m=None):
    k = (round(sx, 4), round(sy, 4), round(sz, 4), m.name if m else "")
    if k not in _MESH:
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x *= sx
            v.co.y *= sy
            v.co.z *= sz
        uvl = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            n = f.normal
            for lp in f.loops:
                c = lp.vert.co
                if abs(n.x) > 0.5:
                    lp[uvl].uv = (c.y * 1.6, c.z * 1.6)
                elif abs(n.y) > 0.5:
                    lp[uvl].uv = (c.x * 1.6, c.z * 1.6)
                else:
                    lp[uvl].uv = (c.x * 1.6, c.y * 1.6)
        me = bpy.data.meshes.new("box_%g_%g_%g" % k[:3])
        if m is not None:
            me.materials.append(m)
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = True
        _MESH[k] = me
    return _MESH[k]


def box(nome, size, loc, m, parent, bevel=0.006, seg=2, rot=None, subdiv=0):
    """Parallelepipedo con spigoli smussati. loc = centro, locale al genitore."""
    ob = bpy.data.objects.new(nome, _box_mesh(*size, m))
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    if rot:
        ob.rotation_euler = rot
    ob.parent = parent
    if bevel:
        bv = ob.modifiers.new("Smusso", "BEVEL")
        bv.width = bevel
        bv.segments = 1 if LOD else seg
        bv.limit_method = "ANGLE"
    if subdiv:
        sd = ob.modifiers.new("Subdiv", "SUBSURF")
        sd.levels = max(0, subdiv - 1) if LOD else subdiv
        sd.render_levels = sd.levels
    return ob


def prisma(nome, poly, z0, z1, m, parent, bevel=0.005, chiave=None):
    """Prisma verticale con base poligonale (x, y) locale al genitore, da z0 a z1."""
    k = chiave or nome
    if k not in _MESH:
        bm = bmesh.new()
        vb = [bm.verts.new((x, y, z0)) for x, y in poly]
        vt = [bm.verts.new((x, y, z1)) for x, y in poly]
        n = len(poly)
        bm.faces.new(vb)
        bm.faces.new(vt)
        for q in range(n):
            bm.faces.new((vb[q], vb[(q + 1) % n], vt[(q + 1) % n], vt[q]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        uvl = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            nn = f.normal
            for lp in f.loops:
                c = lp.vert.co
                if abs(nn.z) > 0.7:
                    lp[uvl].uv = (c.x * 1.6, c.y * 1.6)
                elif abs(nn.x) > abs(nn.y):
                    lp[uvl].uv = (c.y * 1.6, c.z * 1.6)
                else:
                    lp[uvl].uv = (c.x * 1.6, c.z * 1.6)
        me = bpy.data.meshes.new("prisma_" + k)
        me.materials.append(m)
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = True
        _MESH[k] = me
    ob = bpy.data.objects.new(nome, _MESH[k])
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    if bevel:
        bv = ob.modifiers.new("Smusso", "BEVEL")
        bv.width = bevel
        bv.segments = 2
        bv.limit_method = "ANGLE"
    return ob


def cilindro(nome, r, h, loc, m, parent, rot=None, vertici=24, bevel=0.002):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=vertici,
                          radius1=r, radius2=r, depth=h)
    me = bpy.data.meshes.new(nome + "_m")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    if rot:
        ob.rotation_euler = rot
    ob.parent = parent
    ob.data.materials.append(m)
    if bevel:
        bv = ob.modifiers.new("Smusso", "BEVEL")
        bv.width = bevel
        bv.segments = 2
    return ob


def testo_piano(txt, h, wmax, m, loc, parent, spessore=0.003):
    """Testo che guarda verso +y (la stanza), si legge da chi sta in sala."""
    me = maglia._mesh_testo(txt, h, wmax, bold=0.010, passo=(1.0 if WEB else 0.005))
    ob = bpy.data.objects.new("T_" + txt[:12], me)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_mode = "ZYX"
    ob.rotation_euler = (-math.pi / 2.0, 0.0, math.pi)
    ob.location = loc
    ob.parent = parent
    ob.data.materials.append(m)
    if not WEB:
        sl = ob.modifiers.new("Rilievo", "SOLIDIFY")
        sl.thickness = spessore
        sl.offset = 1.0
    return ob


# ------------------------------------------------------------------ armadietto
def baia(i, g, col_maglia, dettagli, scritte_col, base_m, phi, _non_usato):
    """Un armadietto (locale: parete y=0, stanza +y). Ritorna l'empty."""
    alpha = math.pi - phi
    P = (RAGGIO * math.sin(phi), RAGGIO * math.cos(phi), 0.0)
    em = bpy.data.objects.new("Armadietto_%02d" % g["numero"], None)
    bpy.context.scene.collection.objects.link(em)
    em.location = P
    em.rotation_euler = (0, 0, alpha)

    legno = mat("Legno", "#6a3d1e", 0.36, bump="legno")
    legno_s = mat("LegnoScuro", "#4a2c16", 0.5, bump="legno")
    nero = mat("Nicchia", "#0a0a0b", 0.85)
    bianco = mat("BiancoLucido", "#f3f3f4", 0.28)
    cuscino = mat("Cuscino", "#eeeff1", 0.5)
    targa = mat("Targa_" + dettagli, dettagli, 0.35)
    testo = mat("TestoBianco", "#ffffff", 0.5)
    foto = mat("Foto", "#9aa0a6", 0.8)
    cromo = mat("Cromo", "#c9ccd0", 0.15, metal=1.0)
    led = mat("LED", "#eaf4ff", 0.5, emis=5.0)
    w = BAIA_W

    # zoccolo e vano scarpe
    box("Zoccolo", (w, 0.46, 0.08), (0, 0.23, 0.04), nero, em, 0.004)
    box("VanoFondo", (w - 0.16, 0.02, 0.32), (0, 0.03, 0.24), mat("VanoLuce", "#dde7f2", 0.5, emis=1.25), em, 0)
    box("VanoSx", (0.08, 0.50, 0.34), (-(w / 2 - 0.04), 0.25, 0.25), legno, em, 0.005)
    box("VanoDx", (0.08, 0.50, 0.34), ((w / 2 - 0.04), 0.25, 0.25), legno, em, 0.005)
    box("Piano", (w, 0.56, 0.06), (0, 0.28, 0.43), legno, em, 0.006)
    box("Led", (w - 0.20, 0.012, 0.012), (0, 0.46, 0.395), led, em, 0)
    # scarpe (suola chiara + tomaia scura, smussate)
    accenti = ["#d9ea3c", "#2f6bd6", "#f2f2f2", "#e8742c", "#18191c", "#e23b3b"]
    scarpa_t = mat("Scarpa_" + accenti[i % 6], accenti[i % 6], 0.5)
    suola = mat("Suola", "#e8e8e8", 0.6)
    for sgn in (-1.0, 1.0):
        x = sgn * 0.20
        box("Suola", (0.095, 0.28, 0.014), (x, 0.28, 0.105), suola, em, 0.004)
        box("Tomaia", (0.088, 0.25, 0.06), (x, 0.275, 0.145), scarpa_t, em, 0.02, 3)
    # schienale e seduta imbottiti
    box("Schienale", (w - 0.22, 0.12, 0.52), (0, 0.07, 0.82), cuscino, em, 0.04, 4, subdiv=1)
    box("Seduta", (w - 0.22, 0.46, 0.12), (0, 0.27, 0.52), cuscino, em, 0.045, 4, subdiv=1)
    # completo piegato e borraccia
    col_a, col_b = _hex(col_maglia), _hex(dettagli)
    m_a = mat("Kit_maglia_" + col_maglia, col_maglia, 0.7)
    m_b = mat("Kit_dett_" + dettagli, dettagli, 0.7)
    m_n = mat("Kit_nero", "#17181b", 0.7)
    rj = ((i * 37) % 7 - 3) * 0.012
    box("Kit1", (0.34, 0.27, 0.035), (-0.08, 0.30, 0.595), m_n, em, 0.012, 3, rot=(0, 0, rj), subdiv=1)
    box("Kit2", (0.32, 0.25, 0.035), (-0.07, 0.30, 0.63), m_b, em, 0.012, 3, rot=(0, 0, -rj), subdiv=1)
    box("Kit3", (0.30, 0.24, 0.035), (-0.075, 0.30, 0.665), m_n, em, 0.012, 3, rot=(0, 0, rj * 0.5), subdiv=1)
    box("Calze", (0.16, 0.07, 0.04), (0.20, 0.34, 0.60), m_a, em, 0.015, 3, rot=(0, 0, 0.4 + rj), subdiv=1)
    bott = mat("Borraccia", "#9cc4e4", 0.2)
    cilindro("Borraccia", 0.032, 0.20, (-(w / 2 - 0.12), 0.20, 0.68), bott, em)
    cilindro("Tappo", 0.022, 0.03, (-(w / 2 - 0.12), 0.20, 0.795), mat("Tappo", "#2a2a2e", 0.5), em)
    # fianchi e testata in legno
    hw = w / 2        # guance a trapezio: la faccia interna si apre verso la stanza
    prisma("GuanciaSx", [(-hw, 0.0), (-hw + 0.17, 0.0), (-hw + 0.075, 0.56), (-hw, 0.56)],
           0.46, 2.12, legno, em, chiave="gsx")
    prisma("GuanciaDx", [(hw, 0.0), (hw, 0.56), (hw - 0.075, 0.56), (hw - 0.17, 0.0)],
           0.46, 2.12, legno, em, chiave="gdx")
    box("Pannello", (w, 0.52, 0.88), (0, 0.26, 2.56), legno, em, 0.006)
    fuga = mat("Fuga", "#1c1410", 0.9)  # HD: fuga scura 2 mm fra i pannelli, non sembra piu un blocco unico
    # NOTA: 1 mm fuori dal pannello su ogni lato, mai a filo (era z-fighting = sfarfallio)
    box("FugaSx", (0.002, 0.52, 0.88), (-w / 2 - 0.001, 0.26, 2.56), fuga, em, 0)
    box("FugaDx", (0.002, 0.52, 0.88), (w / 2 + 0.001, 0.26, 2.56), fuga, em, 0)
    # nicchia nera
    box("NicchiaFondo", (w - 0.26, 0.02, 1.08), (0, 0.02, 1.60), nero, em, 0)
    box("NicchiaSopra", (w - 0.26, 0.40, 0.02), (0, 0.22, 2.13), nero, em, 0)
    # cornice e foto
    box("Cornice", (0.34, 0.03, 0.44), (0, 0.535, 2.40), bianco, em, 0.004)
    box("Foto", (0.30, 0.012, 0.40), (0, 0.553, 2.40), foto, em, 0)
    silh = mat("Sagoma", "#68707a", 0.7)
    cilindro("Testa", 0.050, 0.004, (0, 0.5585, 2.445), silh, em, rot=(math.pi / 2, 0, 0), bevel=0)
    box("Spalle", (0.22, 0.004, 0.10), (0, 0.5585, 2.255), silh, em, 0.04, 4)
    # targa col nome
    box("Targa", (0.70, 0.03, 0.15), (0, 0.51, 2.84), targa, em, 0.006)
    testo_piano(g["nome"].upper(), 0.06, 0.60, testo, (0, 0.528, 2.84), em, 0.003)
    # asta
    cilindro("Asta", maglia.RAGGIO_ASTA, w - 0.28, (0, Y_ASTA, Z_ASTA), cromo, em, rot=(0, math.pi / 2, 0), bevel=0)

    # maglia (schiena verso la stanza)
    key = (col_maglia, dettagli)
    base = ESEMPLARI.get(key)
    if base is None:
        m = maglia.costruisci("Maglia_%02d" % g["numero"], g["nome"], g["numero"],
                              col_maglia, dettagli, scritte_col, coll=None, con_scudo=True)
        sh, gr = m.shirt, m.gruccia
        if WEB:
            maglia.prepara_web(sh, col_maglia, dettagli, OUT_TEX)
            gr = m.gruccia = _gruccia_mesh(m.gruccia)
        ESEMPLARI[key] = m
    else:
        mt = None if WEB else maglia.materiale_tessuto(
            "M_Tessuto_" + col_maglia.lstrip("#") + dettagli.lstrip("#"), col_maglia, dettagli)
        sh = maglia.duplica(base.shirt, "Maglia_%02d" % g["numero"], g["nome"], g["numero"],
                            scritte_col, materiale=mt)
        gr = bpy.data.objects.new("Gruccia_%02d" % g["numero"], base.gruccia.data)
        bpy.context.scene.collection.objects.link(gr)
        gr.parent = sh
        for c in base.shirt.children:
            suff = next((x for x in maglia.PARTI_FISSE if x in c.name), None)
            if suff:
                sc_ = bpy.data.objects.new("Maglia_%02d%s" % (g["numero"], c.name[c.name.index(suff):]), c.data)
                bpy.context.scene.collection.objects.link(sc_)
                sc_.parent = sh
                for mod in c.modifiers:
                    n = sc_.modifiers.new(mod.name, mod.type)
                    n.thickness = mod.thickness
                    n.offset = mod.offset
        if WEB:
            for c in sh.children:
                for mod in list(c.modifiers):
                    c.modifiers.remove(mod)
    jit = ((i * 53) % 9 - 4) * 0.0035
    sh.parent = em
    sh.location = (jit * 3, Y_ASTA, Z_ASTA - maglia.ALTEZZA_GANCIO)
    sh.rotation_mode = "XYZ"
    sh.rotation_euler = (0, 0, math.pi + jit)
    for o in (em, sh):
        o["numero"] = int(g["numero"])
        o["nome"] = g["nome"]
        o["reparto"] = g["reparto"]
    em["titolare"] = bool(g["titolare"])
    em["phi"] = float(phi)
    return em, base


def _gruccia_mesh(gr):
    """Curva con bevel -> mesh (glTF non esporta le curve con spessore)."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(gr.evaluated_get(dg))
    ob = bpy.data.objects.new(gr.name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = gr.parent
    for mt in gr.data.materials:
        me.materials.append(mt)
    for p in me.polygons:
        p.use_smooth = True
    bpy.data.objects.remove(gr)
    return ob


# clip di animazione di ogni maglia: (nome, [(frame, dy, d_rotZ, dz)])
CLIP = {
    "hover": [(1, 0.0, 0.0, 0.0), (14, 0.20, 0.16, 0.0)],
    "selezione": [(1, 0.0, 0.0, 0.0), (54, 0.85, 0.72, 0.04)],
}


def anima(sh):
    """Una clip per ogni gesto, come tracce NLA: `<Maglia>|hover`, `<Maglia>|selezione`.
    Il sito le suona avanti (entra) e indietro (esce)."""
    loc0 = Vector(sh.location)
    rz0 = sh.rotation_euler.z
    ad = sh.animation_data_create()
    for nome, chiavi in CLIP.items():
        act = bpy.data.actions.new("%s|%s" % (sh.name, nome))
        ad.action = act
        for (f, dy, dr, dz) in chiavi:
            sh.location = (loc0.x, loc0.y + dy, loc0.z + dz)
            sh.rotation_euler = (0.0, 0.0, rz0 + dr)
            sh.keyframe_insert("location", frame=f)
            sh.keyframe_insert("rotation_euler", frame=f)
        tr = ad.nla_tracks.new()
        tr.name = "%s|%s" % (sh.name, nome)
        tr.strips.new(tr.name, 1, act)
        ad.action = None
    sh.location = loc0
    sh.rotation_euler = (0.0, 0.0, rz0)


# ------------------------------------------------------------------ sala
def pilastro(phi):
    """Pilastro bianco lucido, dal pavimento al soffitto, con un incavo all'altezza delle maglie."""
    P = (RAGGIO * math.sin(phi), RAGGIO * math.cos(phi), 0.0)
    em = bpy.data.objects.new("Pilastro", None)
    bpy.context.scene.collection.objects.link(em)
    em.location = P
    em.rotation_euler = (0, 0, math.pi - phi)
    bianco = mat("BiancoLucido", "#f3f3f4", 0.28)
    incavo = mat("Incavo", "#dcdee2", 0.55)
    w, h = PILASTRO_W, ALTEZZA - 0.04
    box("PilBasso", (w, 0.64, 0.92), (0, 0.32, 0.46), bianco, em, 0.012, 3)
    box("PilAlto", (w, 0.64, h - 2.30), (0, 0.32, 2.30 + (h - 2.30) / 2), bianco, em, 0.012, 3)
    for sg in (-1.0, 1.0):
        box("PilAla", (0.05, 0.64, 1.38), (sg * (w / 2 - 0.025), 0.32, 1.61), bianco, em, 0.008, 2)
    box("PilFondo", (w - 0.10, 0.50, 1.38), (0, 0.25, 1.61), incavo, em, 0, 0)


def anello(nome, r_in, r_out, z, m, segm=96, spessore=0.0):
    bm = bmesh.new()
    vi, vo = [], []
    for k in range(segm):
        a = 2 * math.pi * k / segm
        vi.append(bm.verts.new((r_in * math.cos(a), r_in * math.sin(a), z)))
        vo.append(bm.verts.new((r_out * math.cos(a), r_out * math.sin(a), z)))
    for k in range(segm):
        k2 = (k + 1) % segm
        bm.faces.new((vi[k], vo[k], vo[k2], vi[k2]))
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(m)
    return ob


def cilindro_parete(nome, r, z0, z1, m, segm=120, buco=None):
    """Parete cilindrica (normali verso l'interno) da z0 a z1. `buco` = (phi, mezzo angolo, quota):
    nel varco della porta resta solo l'architrave sopra `quota`."""
    bm = bmesh.new()
    if buco is None:
        angoli = [2 * math.pi * k / segm for k in range(segm + 1)]
        spezzoni = [(angoli, z0, z1)]
    else:
        phi_b, mezzo, quota = buco
        a0 = math.pi / 2 - phi_b                      # angolo (da asse X) del centro del varco
        n_arco = segm - int(segm * 2 * mezzo / (2 * math.pi))
        arco = [a0 + mezzo + (2 * math.pi - 2 * mezzo) * k / n_arco for k in range(n_arco + 1)]
        trave = [a0 - mezzo + 2 * mezzo * k / 4 for k in range(5)]
        spezzoni = [(arco, z0, z1), (trave, quota, z1)]
    for angoli, za, zb in spezzoni:
        a_l = [bm.verts.new((r * math.cos(a), r * math.sin(a), za)) for a in angoli]
        b_l = [bm.verts.new((r * math.cos(a), r * math.sin(a), zb)) for a in angoli]
        for k in range(len(angoli) - 1):
            bm.faces.new((a_l[k + 1], a_l[k], b_l[k], b_l[k + 1]))   # normali verso l'interno
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(m)
    return ob


STEMMA_K = 1.15          # scala dello stemma a pavimento (segnaposto)


def _sagoma_scudo(k, dy=0.0):
    pts = [(-1.0, 1.1), (1.0, 1.1), (1.0, 0.0)]
    for q in range(1, 16):
        a = math.pi * q / 16 / 2
        pts.append((math.cos(a), -1.5 * math.sin(a)))
    pts.append((0.0, -1.5))
    for q in range(15, 0, -1):
        a = math.pi * q / 16 / 2
        pts.append((-math.cos(a), -1.5 * math.sin(a)))
    pts.append((-1.0, 0.0))
    return [(p[0] * k, p[1] * k + dy) for p in pts]


def scudo_pavimento(nome, k, z, m):
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z)) for x, y in _sagoma_scudo(k)]
    bm.faces.new(vs)
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(m)
    return ob


def porta(dettagli):
    """La porta del tunnel (slot 0, phi = 180): imbotte, cornice di legno, insegna di uscita."""
    em = bpy.data.objects.new("Porta", None)
    bpy.context.scene.collection.objects.link(em)
    em.location = (0.0, -RAGGIO, 0.0)
    em.rotation_euler = (0, 0, 0.0)
    bianco = mat("BiancoLucido", "#f3f3f4", 0.28)
    legno = mat("Legno", "#6a3d1e", 0.36, bump="legno")
    cromo = mat("Cromo", "#c9ccd0", 0.15, metal=1.0)
    verde = mat("Uscita", "#19c45a", 0.5, emis=3.0)
    nero = mat("Nicchia", "#0a0a0b", 0.85)
    hw = PORTA_W / 2
    L = SPESSORE_MURO
    for sg in (-1.0, 1.0):                      # stipiti
        box("Stipite", (0.30, L + 0.10, ALTEZZA - 0.04), (sg * (hw + 0.15), (0.10 - L) / 2, (ALTEZZA - 0.04) / 2), bianco, em, 0.01, 3)
        box("CorniceLat", (0.07, 0.04, PORTA_H + 0.07), (sg * (hw + 0.035), 0.12, (PORTA_H + 0.07) / 2), legno, em, 0.005)
    box("Architrave", (PORTA_W + 0.60, L + 0.10, ALTEZZA - 0.04 - PORTA_H), (0, (0.10 - L) / 2, PORTA_H + (ALTEZZA - 0.04 - PORTA_H) / 2), bianco, em, 0.01, 3)
    box("CorniceAlta", (PORTA_W + 0.14, 0.04, 0.07), (0, 0.12, PORTA_H + 0.035), legno, em, 0.005)
    box("InsegnaUscita", (0.46, 0.04, 0.16), (0, 0.13, PORTA_H + 0.20), nero, em, 0.006)
    box("InsegnaLuce", (0.40, 0.01, 0.10), (0, 0.155, PORTA_H + 0.20), verde, em, 0)
    box("Soglia", (PORTA_W, L + 0.1, 0.01), (0, (0.10 - L) / 2, 0.005), cromo, em, 0.002)
    return em


def costruisci_sala(dati):
    C = dati["colori"]
    col_maglia, dettagli, scritte = C["maglia"], C["dettagli"], C["scritte"]
    reparti = dati["reparti"]
    col_rep = {r["nome"]: r["colore"] for r in reparti}
    ordine_rep = {r["nome"]: k for k, r in enumerate(reparti)}
    gioc = sorted(dati["giocatori"], key=lambda g: (not g["titolare"], ordine_rep[g["reparto"]], g["numero"]))
    tit = [g for g in gioc if g["titolare"]]
    ris = [g for g in gioc if not g["titolare"]]
    assert len(tit) == len(SLOT_TITOLARI) and len(ris) == len(SLOT_RISERVE), "rosa diversa da 11 + 9"
    # pavimento lucido con lo stemma (segnaposto: scudo nel colore della squadra con bordo bianco)
    pav = mat("Pavimento", "#cdd0d5", 0.07, bump="pavimento HD")
    anello("Pavimento", 0.0001, RAGGIO + 0.3, 0.0, pav)
    scudo_pavimento("StemmaBordo", STEMMA_K * 0.95, 0.008, mat("StemmaBordo", "#f4f4f4", 0.10))  # HD: bordo rialzato 8 mm, piu lucido
    scudo_pavimento("StemmaCampo", STEMMA_K * 0.86, 0.011, mat("StemmaCampo", dettagli, 0.10))   # HD: campo rialzato 11 mm
    tp = maglia._mesh_testo("STEMMA", 0.42, 1.9, bold=0.02, passo=(1.0 if WEB else 0.005))
    to = bpy.data.objects.new("StemmaTesto", tp)
    bpy.context.scene.collection.objects.link(to)
    to.location = (0.0, 0.3, 0.012)  # HD: sopra il campo rialzato
    to.data.materials.append(mat("TestoBianco", "#ffffff", 0.5))
    # pareti (con il varco della porta), soffitto con anello centrale rialzato e pannelli luminosi a trapezi separati
    hw = math.asin((PORTA_W / 2) / (RAGGIO + 0.02))
    cilindro_parete("Parete", RAGGIO + 0.02, 0.0, ALTEZZA, mat("Parete", "#f1f1f2", 0.7),
                    segm=126, buco=(math.pi, hw, PORTA_H))
    R_C, Z_C = 2.0, 0.24
    anello("Soffitto", R_C, RAGGIO + 0.3, ALTEZZA, mat("Soffitto", "#ffffff", 0.5, emis=0.85))  # HD: anello meno abbagliante dei trapezi
    anello("SoffittoCentro", 0.0001, R_C, ALTEZZA + Z_C, mat("SoffittoC", "#fff6ee", 0.5, emis=0.65))
    cilindro_parete("Tamburo", R_C, ALTEZZA, ALTEZZA + Z_C, mat("Tamburo", "#f4f1ec", 0.6, emis=0.35))
    # HD: 21 trapezi luminosi separati fra le travi (prima una fascia unica), con gradiente centro-bordo
    # NOTA: faccia alta a ALTEZZA-8mm, mai a filo con l'anello (era z-fighting = sfarfallio)
    m_trap_c = mat("TrapezioC", "#fffdf8", 0.5, emis=1.2)
    m_trap_b = mat("TrapezioB", "#f2ede6", 0.5, emis=0.8)
    for j in range(N_SLOT):
        pp = phi_slot(j) + PASSO / 2
        em = bpy.data.objects.new("Trapezio%d" % j, None)
        bpy.context.scene.collection.objects.link(em)
        em.rotation_euler = (0, 0, math.pi / 2 - pp)
        Lc = R_C + 0.10
        Lb = RAGGIO + 0.05 - R_C - 0.20
        poly_c = [(Lc, -0.055), (Lc, 0.055), (Lc + Lb / 2, 0.075), (Lc + Lb / 2, -0.075)]
        poly_b = [(Lc + Lb / 2, -0.075), (Lc + Lb / 2, 0.075), (Lc + Lb, 0.10), (Lc + Lb, -0.10)]
        prisma("TrapC", poly_c, ALTEZZA - 0.013, ALTEZZA - 0.008, m_trap_c, em, bevel=0.002, chiave="TrapC%d" % j)
        prisma("TrapB", poly_b, ALTEZZA - 0.013, ALTEZZA - 0.008, m_trap_b, em, bevel=0.002, chiave="TrapB%d" % j)
    faretto = mat("Faretto", "#fff2e0", 0.5, emis=14.0)
    for k in range(12):  # HD: 12 faretti invece di 8
        a = 2 * math.pi * k / 12 + math.pi / 12
        cilindro("Faretto%d" % k, 0.07, 0.01, (1.2 * math.cos(a), 1.2 * math.sin(a), ALTEZZA + Z_C - 0.01), faretto, None, bevel=0)
    trave = mat("Trave", "#2b2320", 0.5)
    for j in range(N_SLOT):
        pp = phi_slot(j) + PASSO / 2
        em = bpy.data.objects.new("Trave%d" % j, None)
        bpy.context.scene.collection.objects.link(em)
        em.rotation_euler = (0, 0, math.pi / 2 - pp)
        L = RAGGIO + 0.05 - R_C
        box("Tr", (L, 0.07, 0.14), (R_C + L / 2, 0, ALTEZZA - 0.07), trave, em, 0.005)
    anello("AnelloCentro", R_C - 0.02, R_C + 0.06, ALTEZZA - 0.02, trave)
    # armadietti e porta; un pilastro fra ogni coppia di slot
    porta(dettagli)
    slot_di = {}
    for g, j in zip(tit, SLOT_TITOLARI):
        slot_di[g["numero"]] = j
    for g, j in zip(ris, SLOT_RISERVE):
        slot_di[g["numero"]] = j
    lista = []
    for k, g in enumerate(tit + ris):
        j = slot_di[g["numero"]]
        phi = phi_slot(j)
        cm = C["portieri"] if col_rep[g["reparto"]] == "portieri" else col_maglia
        det = dettagli if cm == col_maglia else "#9aa0a6"
        baia(k, g, cm, det, scritte if cm == col_maglia else "#f2f3f5", None, phi, None)   # portiere: scritte chiare
        lista.append((g, j, phi))
    for j in range(N_SLOT):
        pilastro(phi_slot(j) + PASSO / 2)
    return lista


def luci_e_mondo(sc):
    w = bpy.data.worlds.new("Sala")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.9, 0.92, 0.95, 1.0)
    bg.inputs[1].default_value = 0.15
    sc.world = w


def camera(sc, nome, loc, tgt, lens, shift_y=0.0):
    cd = bpy.data.cameras.new(nome)
    cd.lens = lens
    cd.shift_y = shift_y
    cd.clip_end = 60.0
    co = bpy.data.objects.new(nome, cd)
    sc.collection.objects.link(co)
    co.location = loc
    co.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return co


def _e_maglia(ob):
    while ob is not None:
        if ob.name.startswith("Maglia_"):
            return True
        ob = ob.parent
    return False


def unisci_statico():
    """Tutta la parte che non si muove, una mesh per materiale: poche chiamate
    di disegno nel browser. Le maglie restano separate (si animano)."""
    gruppi = {}
    for ob in list(bpy.data.objects):
        if ob.type != "MESH" or _e_maglia(ob):
            continue
        k = ob.data.materials[0].name if ob.data.materials else "_"
        gruppi.setdefault(k, []).append(ob)
    for k, lista in gruppi.items():
        bpy.ops.object.select_all(action="DESELECT")
        for ob in lista:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = lista[0]
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
        bpy.ops.object.convert(target="MESH")
        bpy.context.view_layer.objects.active = lista[0]
        bpy.ops.object.join()
        lista[0].name = "Fisso_" + k
    return list(gruppi)


def controlla_scena(lista):
    """Controlli numerici prima di esportare: rosa, slot, budget di triangoli."""
    err = []
    nomi = [o.name for o in bpy.data.objects]
    maglie = [n for n in nomi if n.startswith("Maglia_") and n.count("_") == 1]
    armadietti = [n for n in nomi if n.startswith("Armadietto_")]
    if len(maglie) != N_BAIE:
        err.append("maglie %d invece di %d" % (len(maglie), N_BAIE))
    if len(armadietti) != N_BAIE:
        err.append("armadietti %d invece di %d" % (len(armadietti), N_BAIE))
    slot = [j for _, j, _ in lista]
    if len(set(slot)) != len(slot) or 0 in slot or any(not (0 < j < N_SLOT) for j in slot):
        err.append("slot duplicati o sulla porta: %s" % sorted(slot))
    tri = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in bpy.data.objects
              if o.type == "MESH" and (not o.name.startswith("Maglia_") or o.name.count("_") == 1))
    n_figli = sum(1 for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("Maglia_") and o.name.count("_") > 1)
    return err, tri, n_figli


def esporta_web(out, dati, lista):
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 60
    sc.render.fps = FPS
    glb = os.path.join(out, "sala_bassa.glb" if LOD else "sala.glb")
    bpy.ops.export_scene.gltf(
        filepath=glb, export_format="GLB", export_apply=True, export_yup=True,
        export_animations=False, export_extras=True,
        export_cameras=False, export_lights=False, export_materials="EXPORT",
        export_meshopt_compression_enable=True)
    man = {
        "squadra": dati["nome"], "stagione": dati["stagione"], "colori": dati["colori"],
        "reparti": [r["nome"] for r in dati["reparti"]],
        "raggio": RAGGIO, "altezza": ALTEZZA, "fps": FPS, "baie": N_BAIE, "slot": N_SLOT,
        "porta": {"phi": math.pi, "larghezza": PORTA_W, "altezza": PORTA_H, "spessore": SPESSORE_MURO},
        "giocatori": [
            {"numero": g["numero"], "nome": g["nome"], "reparto": g["reparto"],
             "titolare": g["titolare"], "slot": j, "phi": phi,
             "nodo": "Armadietto_%02d" % g["numero"], "maglia": "Maglia_%02d" % g["numero"]}
            for g, j, phi in lista],
        # gesti: spostamento (m), rotazione (rad) e alzata raggiunti a molla completamente chiusa;
        # molle: pulsazione w (rad/s) e smorzamento z (z < 1 = piccolo rimbalzo); oscillazione = pendolo della gruccia
        "gesti": {
            "hover": {"dy": CLIP["hover"][-1][1], "dr": CLIP["hover"][-1][2], "dz": CLIP["hover"][-1][3]},
            "selezione": {"dy": CLIP["selezione"][-1][1], "dr": CLIP["selezione"][-1][2], "dz": CLIP["selezione"][-1][3]},
            "molle": {"hover": {"w": 16.0, "z": 0.55}, "selezione": {"w": 10.0, "z": 0.62},
                      "oscillazione": {"w": 5.4, "z": 0.14, "k": 0.35}},
            "altezza_gancio": maglia.ALTEZZA_GANCIO,
        },
    }
    if not LOD:
        json.dump(man, open(os.path.join(out, "sala.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("WEB_OK", glb, os.path.getsize(glb))


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    modo = "render"
    if argv and argv[0] in ("render", "web"):
        modo = argv[0]
        argv = argv[1:]
    out = os.path.abspath(argv[0]) if argv else os.path.abspath("render_sala")
    os.makedirs(out, exist_ok=True)
    radice = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dati = json.load(open(os.path.join(radice, "squadra.json"), encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    if modo == "web":
        WEB = True
        LOD = "lod" in argv[1:]
        OUT_TEX = out
        maglia.PASSO_TESTO = 0.030 if LOD else 0.014
        if LOD:
            maglia.STEP = 0.017          # maglia con triangoli di 1,7 cm invece di 1 cm: circa un terzo
        lista = costruisci_sala(dati)
        err_sala, tri_scena, n_figli = controlla_scena(lista)
        for e in err_sala:
            print("SALA_ERRORE", e)
        unisci_statico()
        esporta_web(out, dati, lista)
        peso = os.path.getsize(os.path.join(out, "sala_bassa.glb" if LOD else "sala.glb"))
        budget_peso, budget_tri = (3.2e6, 450000) if LOD else (6.0e6, 900000)
        print("SALA_MISURE triangoli_stimati", tri_scena, "figli_maglia", n_figli, "peso", peso)
        if peso > budget_peso:
            print("SALA_ERRORE peso %d oltre il budget %d" % (peso, budget_peso))
            err_sala.append("peso")
        if err_sala:
            sys.exit(1)
        sys.exit(0)
    px = int(argv[1]) if len(argv) > 1 else 1920  # HD: 1920 di base per il confronto con le foto
    camp = int(argv[2]) if len(argv) > 2 else 128  # HD: 128 campioni col denoise
    salva = os.path.abspath(argv[3]) if len(argv) > 3 else None
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = -0.35
    luci_e_mondo(sc)
    costruisci_sala(dati)
    sc.cycles.samples = camp
    # HD v04: tre inquadrature fisse per il confronto con le foto (niente nomi vecchi sovrascritti)
    for nome, larg, pos, tgt, foc in (
            ("v04_16x9", px, (0.0, -3.3, 1.55), (0.0, 4.0, 1.45), 12.0),
            ("v04_9x16", int(round(px * 9 / 16)), (0.0, -3.3, 1.55), (0.0, 4.0, 1.45), 20.0),
            ("v04_armadietto", px, (0.0, 0.6, 1.55), (0.0, 4.4, 1.45), 28.0)):
        sc.render.resolution_x = larg
        sc.render.resolution_y = int(round(larg * (16 / 9 if nome == "v04_9x16" else 9 / 16)))
        sc.camera = camera(sc, "Cam_" + nome, pos, tgt, foc)
        sc.render.filepath = os.path.join(out, nome + ".png")
        bpy.ops.render.render(write_still=True)
    if salva:
        bpy.ops.wm.save_as_mainfile(filepath=salva)
    print("SALA_OK")
