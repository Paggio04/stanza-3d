"""tunnel.py - il tunnel dei giocatori, la facciata sotto gli spalti e il bordo campo.

Uso:  blender -b -P tunnel.py -- CARTELLA_ASSOLUTA

Scrive CARTELLA/tunnel.glb e CARTELLA/tunnel.json (percorso della camera, in coordinate glTF).
Sistema locale (u = distanza dalla porta della sala, verso il campo): x = lato, u, z = su.
Mondo Blender come la sala: la porta e' a (0, -RAGGIO, 0), il tunnel va verso -Y.

La luce del tunnel e' cotta nei colori dei vertici (strisce al soffitto, luce del giorno dalla bocca,
bagliore caldo della sala): nel sito niente luci in piu'.
"""
import bpy
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maglia  # noqa: E402
import sala    # noqa: E402

T0 = sala.RAGGIO + sala.SPESSORE_MURO     # |y| mondo del piano u = 0
W = 4.6                                   # larghezza interna del tunnel (Camp Nou: largo, con corrimano centrale)
H = 3.0                                   # altezza
L = 20.0                                  # lunghezza (u della bocca)
FASCIA = 0.95                             # fascia sopra la bocca
APRON = 4.0                               # asfalto fra la facciata e la linea di fondo
LARG_FACCIATA = 34.0                      # mezza larghezza di facciata e spalti
SPALTI_U = 10.0                           # profondita' degli spalti
SPALTI_ALT = 7.5
BLU = None                                # usato dal blu squadra (dati squadra.json), non fisso
FISSI = [(sx * 0.75, fu) for fu in (2.0, 5.0, 8.0, 11.0, 14.0, 17.0) for sx in (-1, 1)]
# ---- stadio (ciotola vera, stile Camp Nou): misure in metri
ST_RAGGIO = 50.0                          # raggio interno della ciotola (deve contenere il campo 68x70)
ST_CENTRO_U = L + 50.0                    # centro ciotola: il muro di base passa esattamente sulla facciata (u = L)
ST_ANELLI = ((9.0, 8.0), (8.0, 7.0), (7.0, 6.0))  # (profondita, alzata) dei 3 anelli di spalti
ST_ALTEZZA0 = 3.5                         # quota del primo anello sopra il campo
ST_TETTO_R0 = 66.0                        # raggio interno del tetto ad anello
ST_TETTO_R1 = 86.0                        # raggio esterno del tetto
ST_TETTO_Z = 34.0                         # quota del tetto
ST_VOMITORIO_HALF = 0.10                  # semi-ampiezza angolare del varco tunnel (rad ~5.7 gradi)
# ---- scalinata finale stile Camp Nou: ultimi 6 m in salita verso la luce (+90 cm)
ST_SCALA_U0 = 14.0                        # dove iniziano i gradini
ST_N_GRADINI = 12
ST_ALZATA = 0.075                         # 7,5 cm a gradino x 12 = +90 cm alla bocca
ST_QUOTA = ST_N_GRADINI * ST_ALZATA       # il campo e' 90 cm sopra il pavimento del tunnel: i gradini finiscono a filo del campo


def w(p):
    """locale (x, u, z) -> mondo Blender."""
    return np.array([p[0], -(T0 + p[1]), p[2]], float)


def wn(n):
    return np.array([n[0], -n[1], n[2]], float)


# ------------------------------------------------------------------ texture procedurali
def _img(nome, arr, cartella):
    h, wd = arr.shape[:2]
    if nome in bpy.data.images:
        return bpy.data.images[nome]
    img = bpy.data.images.new(nome, wd, h, alpha=False)
    rgba = np.concatenate([arr, np.ones((h, wd, 1))], axis=2).astype(np.float32)
    img.pixels.foreach_set(rgba[::-1].ravel())
    img.filepath_raw = os.path.join(cartella, nome + ".png")
    img.file_format = "PNG"
    img.save()
    img.pack()
    return img


def _scuro_hex(h, k):
    c = (_lin(h) * k * 255).round().astype(int)
    return "#%02x%02x%02x" % tuple(int(v) for v in c)


def _lin(h):
    """Colore come valori sRGB 0..1: le immagini 8 bit sono in sRGB, non in lineare."""
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def tex_erba(cartella, n=1024):  # HD: 1024 invece di 512
    rng = np.random.default_rng(3)
    V = np.arange(n)[:, None] / n
    fascia = (np.floor(V * 2.0) % 2)                     # 2 strisce per tile (4 m)
    a, b = _lin("#2f7a2b"), _lin("#3a8c33")
    base = a[None, None, :] * (1 - fascia[..., None]) + b[None, None, :] * fascia[..., None]
    fine = rng.random((n, n, 1)) * 0.10 + 0.95
    zolle = (rng.random((n // 8, n // 8, 1)).repeat(8, 0).repeat(8, 1)) * 0.07 + 0.965
    return _img("erba", np.clip(base * fine * zolle, 0, 1), cartella)


def tex_spalti(cartella, blu="#1d3f96", rosso="#3a6fd0", nome="", w_=1024, h_=512):
    """Spalti: griglia 128 x 64 seggiolini (8 px). Fasce blu / rosso / blu; sul rosso una banda bianca
    col nome a lettere blu (7 righe). Si ripete 6 volte attorno alla ciotola (8 spicchi su 48)."""
    rng = np.random.default_rng(5)
    cell = 8
    C, Rr = w_ // cell, h_ // cell
    b, r, bianco = _lin(blu), _lin(rosso), _lin("#e9edf3")
    scuro = b * 0.55
    grid = np.zeros((Rr, C, 3))
    for rr in range(Rr):
        base = b if (rr < 22 or rr >= 42) else r
        for c in range(C):
            col = base * (0.86 + 0.14 * rng.random())
            x = rng.random()
            if x < 0.05:
                col = bianco * 0.92
            elif x < 0.09:
                col = base * 0.6
            if c % 16 == 0:                                   # corridoio verticale
                col = base * 0.45
            grid[rr, c] = col
    for rr in range(27, 36):                                  # banda bianca
        grid[rr, :] = bianco * (0.94 + 0.06 * rng.random((C, 1)))
    testo = (nome or "").upper()
    start = (C - 6 * len(testo)) // 2
    for i, ch in enumerate(testo):
        if ch == " ":
            continue
        gl = _lettera(ch)
        for ly in range(7):
            for lx in range(5):
                if gl[ly][lx]:
                    grid[28 + ly, start + 6 * i + lx] = scuro   # riga 0 della matrice = in alto (riga 0 dell array = alto dell immagine)
    img = np.repeat(np.repeat(grid, cell, axis=0), cell, axis=1)
    yy, xx = np.mgrid[0:h_, 0:w_]
    img = img * np.where((yy % cell == 0) | (xx % cell == 0), 0.78, 1.0)[..., None]
    return _img("spalti", np.clip(img, 0, 1), cartella)


def _lettera(ch):
    """Matrice 7x5 per A-Z (font a blocchi). Sconosciute = blocco pieno."""
    F = {
        "A": [0, 1, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1],
        "B": [1, 1, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1, 1, 1, 0],
        "C": [0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1],
        "E": [1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1],
        "G": [0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0],
        "L": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1],
        "O": [0, 1, 1, 1, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 1, 0],
        "R": [1, 1, 1, 1, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 0, 1],
        "S": [0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0],
    }
    v = F.get(ch, [1] * 35)
    return [v[i * 5:(i + 1) * 5] for i in range(7)]


def tex_cartelloni(cartella, blu="#1d3f96", w_=1024, h_=128):
    rng = np.random.default_rng(9)
    img = np.zeros((h_, w_, 3)) + _lin("#0b1230")
    x = 0
    pal = [_lin(c) for c in (blu, "#ffffff", "#e8c11c", "#d93a3a", "#2fb86a", "#ffffff")]
    while x < w_:
        bw = int(rng.integers(90, 230))
        col = pal[rng.integers(len(pal))]
        img[10:h_ - 10, x + 6:min(w_, x + bw - 6)] = col * 0.9
        for k in range(int(rng.integers(2, 5))):                  # "scritte" a blocchi: stessa tinta scurita (niente inversione = niente moire da lontano)
            tw = int(rng.integers(14, 60))
            tx = x + 14 + int(rng.integers(0, max(1, bw - 80)))
            ty = int(rng.integers(30, h_ - 50))
            img[ty:ty + 10, tx:min(w_, tx + tw)] = np.clip(col * 0.55 + 0.08, 0.05, 1)
        x += bw
    return _img("cartelloni", img, cartella)


def tex_cemento(cartella, n=256):
    rng = np.random.default_rng(11)
    g = rng.random((n, n, 1)) * 0.10 + 0.90
    rgb = _lin("#33373d")[None, None, :] * g
    return _img("gomma", np.clip(rgb, 0, 1), cartella)


# ------------------------------------------------------------------ materiali
_MAT = {}


def mat(nome, colore="#ffffff", imm=None, rough=0.7, emis=0.0):
    if nome in _MAT:
        return _MAT[nome]
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    pb = nt.nodes["Principled BSDF"]
    pb.inputs["Base Color"].default_value = maglia._hex(colore)
    pb.inputs["Roughness"].default_value = rough
    if imm is not None:
        it = nt.nodes.new("ShaderNodeTexImage")
        it.image = imm
        it.interpolation = "Linear"
        nt.links.new(it.outputs["Color"], pb.inputs["Base Color"])
    if emis > 0:
        pb.inputs["Emission Color"].default_value = maglia._hex(colore)
        pb.inputs["Emission Strength"].default_value = emis
    _MAT[nome] = m
    return m


# ------------------------------------------------------------------ luce cotta
def _smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def luce_interna(pw, nw):
    """Luce cotta di un punto (mondo) con normale (mondo): ritorna un colore RGB lineare."""
    x, u, z = pw[0], -pw[1] - T0, pw[2]
    n = np.array([nw[0], -nw[1], nw[2]])
    tot = 0.0
    lato = 0.0  # luce che arriva dai fianchi (pareti blu): modella il volume
    for fx, fu in FISSI:
        l = np.array([fx - x, fu - u, H - 0.06 - z])
        d = float(np.linalg.norm(l)) + 1e-6
        cos = max(0.0, float(np.dot(n, l / d)))
        tot += cos / (1.0 + (d / 2.3) ** 2)
        lato += abs(float(np.dot(n, np.array([1.0, 0.0, 0.0])))) / (1.0 + (d / 3.0) ** 2)
    amb = 0.13 + 0.06 * max(0.0, n[2])
    day = 0.72 * math.exp(-(L - u) / 4.5) if u <= L else 0.0
    room = 0.55 * math.exp(-max(u, 0.0) / 3.2)
    c = (np.array([amb, amb, amb]) + 0.95 * tot * np.array([1.0, 0.97, 0.92])
         + 0.25 * lato * np.array([0.75, 0.82, 0.95])
         + day * np.array([0.88, 0.95, 1.05]) + room * np.array([1.0, 0.92, 0.80]))
    return np.clip(c, 0.0, 1.0)


def luce_esterna(nw):
    n = np.array([nw[0], -nw[1], nw[2]])
    return np.clip(np.array([0.62 + 0.30 * max(0, n[2])] * 3), 0, 1)


# ------------------------------------------------------------------ raccolta delle facce
class Raccolta:
    def __init__(self):
        self.d = {}

    def quad(self, m, p00, p10, p11, p01, n, nu=1, nv=1, uvs=(8.0, 8.0), uv0=(0.0, 0.0), modo="int"):
        """Quadrilatero a griglia nu x nv fra 4 angoli locali; `n` = normale voluta (locale)."""
        P = [w(p) for p in (p00, p10, p11, p01)]
        nw_ = wn(n)
        nw_ = nw_ / np.linalg.norm(nw_)
        e1, e2 = P[1] - P[0], P[3] - P[0]
        flip = float(np.dot(np.cross(e1, e2), nw_)) < 0
        L1, L2 = float(np.linalg.norm(e1)), float(np.linalg.norm(e2))
        d = self.d.setdefault(m, {"v": [], "n": [], "uv": [], "f": [], "modo": []})
        base = len(d["v"])
        for j in range(nv + 1):
            for i in range(nu + 1):
                s, t = i / nu, j / nv
                d["v"].append(P[0] + e1 * s + e2 * t)
                d["n"].append(nw_)
                d["uv"].append((uv0[0] + L1 * s / uvs[0], uv0[1] + L2 * t / uvs[1]))
                d["modo"].append(modo)
        for j in range(nv):
            for i in range(nu):
                a = base + j * (nu + 1) + i
                b = a + 1
                c = b + (nu + 1)
                dd = a + (nu + 1)
                d["f"].append((a, dd, c, b) if flip else (a, b, c, dd))

    def parete(self, m, x0, x1, u0, u1, z0, z1, n, mx=1.0, **kw):
        """Rettangolo allineato agli assi. Una sola fra (x, u, z) e' costante."""
        if abs(n[2]) > 0.5:
            z = z0
            self.quad(m, (x0, u0, z), (x1, u0, z), (x1, u1, z), (x0, u1, z), n,
                      nu=max(1, int((x1 - x0) / mx)), nv=max(1, int((u1 - u0) / mx)), **kw)
        elif abs(n[0]) > 0.5:
            x = x0
            self.quad(m, (x, u0, z0), (x, u1, z0), (x, u1, z1), (x, u0, z1), n,
                      nu=max(1, int((u1 - u0) / mx)), nv=max(1, int((z1 - z0) / mx)), **kw)
        else:
            u = u0
            self.quad(m, (x0, u, z0), (x1, u, z0), (x1, u, z1), (x0, u, z1), n,
                      nu=max(1, int((x1 - x0) / mx)), nv=max(1, int((z1 - z0) / mx)), **kw)

    def scatola(self, m, c, s, modo="int", **kw):
        """Parallelepipedo (centro locale c, dimensioni s) senza la faccia posteriore verso il muro."""
        x, u, z = c
        sx, su, sz = s[0] / 2, s[1] / 2, s[2] / 2
        self.parete(m, x - sx, x + sx, u - su, u + su, z + sz, z + sz, (0, 0, 1), modo=modo, **kw)
        self.parete(m, x - sx, x + sx, u - su, u + su, z - sz, z - sz, (0, 0, -1), modo=modo, **kw)
        self.parete(m, x - sx, x - sx, u - su, u + su, z - sz, z + sz, (-1, 0, 0), modo=modo, **kw)
        self.parete(m, x + sx, x + sx, u - su, u + su, z - sz, z + sz, (1, 0, 0), modo=modo, **kw)
        self.parete(m, x - sx, x + sx, u - su, u - su, z - sz, z + sz, (0, -1, 0), modo=modo, **kw)
        self.parete(m, x - sx, x + sx, u + su, u + su, z - sz, z + sz, (0, 1, 0), modo=modo, **kw)

    def costruisci(self):
        """Crea un oggetto per materiale, con UV e colore cotto. Ritorna {materiale: oggetto}."""
        out = {}
        for m, d in self.d.items():
            me = bpy.data.meshes.new("T_" + m.name)
            zoff = ST_QUOTA if m.name.startswith("Esterno_") else 0.0   # campo e stadio 90 cm sopra il tunnel
            me.from_pydata([(float(v[0]), float(v[1]), float(v[2]) + zoff) for v in d["v"]], [], [tuple(f) for f in d["f"]])
            me.update()
            uvl = me.uv_layers.new(name="UVMap")
            for lp in me.loops:
                uvl.data[lp.index].uv = d["uv"][lp.vertex_index]
            col = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
            for i, v in enumerate(d["v"]):
                if d["modo"][i] == "int":
                    c = luce_interna(v, d["n"][i])
                elif d["modo"][i] == "ext":
                    c = luce_esterna(d["n"][i])
                else:
                    c = np.array([1.0, 1.0, 1.0])
                col.data[i].color = (float(c[0]), float(c[1]), float(c[2]), 1.0)
            for p in me.polygons:
                p.use_smooth = False
            me.materials.append(m)
            ob = bpy.data.objects.new("T_" + m.name, me)
            bpy.context.scene.collection.objects.link(ob)
            out[m] = ob
        return out


# ------------------------------------------------------------------ testi e stemma piano
def _piano(me, rot, loc, m, nome):
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_euler = rot
    ob.location = loc
    ob.data.materials.append(m)
    # colore cotto bianco (nessuna luce): serve il layer anche qui perche' l'esportatore lo cerca
    col = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    for i in range(len(me.vertices)):
        col.data[i].color = (1.0, 1.0, 1.0, 1.0)
    return ob


def testo_facciata(txt, h, wmax, m, loc_local):
    me = maglia._mesh_testo(txt, h, wmax, bold=0.012, passo=1.0)
    return _piano(me, (math.pi / 2, 0.0, 0.0), tuple(w(loc_local)), m, "Testo_" + txt[:10])


def scudo_parete(k, m, loc_local, nome, rot):
    import bmesh
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, 0.0)) for x, y in sala._sagoma_scudo(k)]
    bm.faces.new(vs)
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    return _piano(me, rot, tuple(w(loc_local)), m, nome)


# ------------------------------------------------------------------ seggiolini veri
def _seggiolini(R, m_seg, m_base, z, r, prof, alz, n, salta):
    """File di seggiolini veri (seduta + schienale + base) sui 3 anelli.
    I seggiolini riempiono la ciotola: non sembra piu vuota."""
    for k in range(n):
        a0 = 2 * math.pi * k / n
        a1 = 2 * math.pi * (k + 1) / n
        if salta is not None and salta((a0 + a1) / 2):
            continue
        am = (a0 + a1) / 2
        # 8 seggiolini per spicchio per fila (riempiono davvero la ciotola)
        # LOD stadio: 1 seggiolino ogni 4 spicchi, 2 file per anello, solo seduta+schienale
        if (k % 4) != 0:
            continue
        for f in (1, 3):
            t = (f + 0.5) / 4
            rr = r + prof * t
            zz = z + alz * t
            for q in (1, 4, 6):
                aq = a0 + (a1 - a0) * (q + 0.5) / 8
                cx = rr * math.cos(aq)
                cy = ST_CENTRO_U + rr * math.sin(aq)
                # seduta (la base e' la ciotola stessa: niente scatola sotto)
                R.scatola(m_seg, (cx, cy, zz + 0.25), (0.42, 0.40, 0.08), modo="ext")
                # schienale (verso l'esterno della ciotola)
                dx, dy = math.cos(aq), math.sin(aq)
                R.scatola(m_seg, (cx + dx * 0.20, cy + dy * 0.20, zz + 0.45), (0.42, 0.08, 0.40), modo="ext")


# ------------------------------------------------------------------ costruzione
def _anello_ciotola(R, m, r0, z0, r1, z1, n, uvscala=0.12, modo="ext", salta=None, doppia=True, uvm=None):
    """Anello di spalti inclinato (ciotola): n spicchi, normale verso il campo.
    salta(a_medio) = True per saltare lo spicchio (varco tunnel). doppia = facce da entrambi i lati.
    uvm = (metri per ripetizione in u, quota di riferimento, metri per ripetizione in v): UV continue
    lungo l'anello (prima ogni spicchio campionava una sola colonna di texture = strisce)."""
    for k in range(n):
        a0 = 2 * math.pi * k / n
        a1 = 2 * math.pi * (k + 1) / n
        if salta is not None and salta((a0 + a1) / 2):
            continue
        p00 = (r0 * math.cos(a0), r0 * math.sin(a0), z0)
        p10 = (r0 * math.cos(a1), r0 * math.sin(a1), z0)
        p11 = (r1 * math.cos(a1), r1 * math.sin(a1), z1)
        p01 = (r1 * math.cos(a0), r1 * math.sin(a0), z1)
        P = [w((p[0], ST_CENTRO_U + p[1], p[2])) for p in (p00, p10, p11, p01)]
        d = R.d.setdefault(m, {"v": [], "n": [], "uv": [], "f": [], "modo": []})
        base = len(d["v"])
        e1, e2 = P[1] - P[0], P[3] - P[0]
        nrm = np.cross(e2, e1)
        nrm = nrm / (np.linalg.norm(nrm) + 1e-9)
        lseg = float(np.linalg.norm(e1))

        def uv(i, j):
            if uvm is None:
                return (k * uvscala, (z0 + (z1 - z0) * j) * uvscala)
            return ((k + i) * lseg / uvm[0], (z0 + (z1 - z0) * j - uvm[1]) / uvm[2])

        ang = {(0, 0): P[0], (1, 0): P[1], (1, 1): P[2], (0, 1): P[3]}    # trapezio vero, non parallelogramma (buchi a spicchio)
        for j in range(2):
            for i in range(2):
                d["v"].append(ang[(i, j)])
                d["n"].append(nrm)
                d["uv"].append(uv(i, j))
                d["modo"].append(modo)
        d["f"].append((base, base + 1, base + 3, base + 2))
        if doppia:
            for q in range(4):
                i, j = int(q in (1, 2)), int(q >= 2)
                d["v"].append(ang[(i, j)])
                d["n"].append(-nrm)
                d["uv"].append(uv(i, j))
                d["modo"].append(modo)
            d["f"].append((base + 4, base + 7, base + 6, base + 5))


def costruisci(dati, cartella):
    blu = dati["colori"]["dettagli"]
    R = Raccolta()
    erba_i = tex_erba(cartella)
    spalti_i = tex_spalti(cartella, blu=blu, nome=dati["nome"])
    cart_i = tex_cartelloni(cartella, blu=blu)
    # ---- tunnel stile Camp Nou: pareti blu squadra, pavimento chiaro, corrimano oro, LED a soffitto
    m_blu = mat("Tunnel_Muro", _scuro_hex(blu, 0.62), None, 0.55)
    m_pav = mat("Tunnel_Pavimento", "#8f9fba", None, 0.5)
    m_alzata = mat("Tunnel_Alzata", "#2b2e34", None, 0.85)
    m_corsia = mat("Tunnel_Corsia", "#838b96", None, 0.62)
    m_oro = mat("Tunnel_Oro", "#c9a227", None, 0.3)
    m_sof = mat("Tunnel_Soffitto", "#101318", None, 0.9)
    m_led = mat("Tunnel_Luce", "#fff3de", None, 0.5, emis=8.0)
    m_filo = mat("Tunnel_Filetto", "#ffffff", None, 0.5)
    m_sc_b = mat("Tunnel_ScudoBordo", "#f4f4f4", None, 0.4, emis=0.5)
    m_sc_c = mat("Tunnel_ScudoCampo", "#2f5fc4", None, 0.4, emis=0.7)
    hw = W / 2
    # pavimento chiaro con corsia e riga oro centrale (come la foto del Camp Nou)
    # NOTA: corsia/oro SOLO sul piano. Sulla scalinata niente righe che corrono:
    # pedate chiare + alzate scure = i gradini si leggono da costruzione, con profondita vera
    R.parete(m_pav, -hw, hw, 0.0, ST_SCALA_U0, 0.0, 0.0, (0, 0, 1), mx=0.8, uvs=(3.2, 3.2))
    # corrimano centrale dorato come nella foto, con montanti; si ferma prima della porta
    R.scatola(m_oro, (0.0, (4.5 + ST_SCALA_U0 - 0.3) / 2, 0.95), (0.05, ST_SCALA_U0 - 0.3 - 4.5, 0.05))
    for up in (4.5, 7.5, 10.5, ST_SCALA_U0 - 0.3):
        R.scatola(m_oro, (0.0, up, 0.47), (0.04, 0.04, 0.94))
    # scalinata finale: 12 gradini da 7,5 cm (sale di 90 cm verso la luce, come al Camp Nou)
    # NOTA: gradini PIENI (alzata da terra fino alla pedata): da nessun lato si vede il sotto
    du = (L - ST_SCALA_U0) / ST_N_GRADINI
    for g in range(ST_N_GRADINI):
        zg = (g + 1) * ST_ALZATA
        R.parete(m_pav, -hw, hw, ST_SCALA_U0 + g * du, ST_SCALA_U0 + (g + 1) * du, zg, zg,
                 (0, 0, 1), mx=0.8, uvs=(3.2, 3.2))
        R.parete(m_alzata, -hw, hw, ST_SCALA_U0 + g * du, ST_SCALA_U0 + g * du, 0.0, zg, (0, 1, 0), mx=0.8)
    # soffitto scuro con 5 lame di luce (come la foto: strisce LED sul blu)
    R.parete(m_sof, -hw, hw, 0.0, L, H, H, (0, 0, -1), mx=0.8)
    for fu in (2.5, 6.5, 10.5, 14.5, 17.5):
        # NOTA: sopra a H-0.02 (era a filo del soffitto = sfarfallio)
        R.scatola(m_led, (0, fu, H - 0.035), (W - 0.6, 0.10, 0.03), modo="piena")
    # pareti blu con scudi bianchi retroilluminati e corrimano oro (mesh vere, niente testi flottanti)
    for sg, nx in ((-1, 1), (1, -1)):
        x = sg * hw
        R.parete(m_blu, x, x, 0.0, L, 0.0, H, (nx, 0, 0), mx=0.8)
        R.parete(m_filo, x - sg * 0.006, x - sg * 0.006, 0.0, L, 1.10, 1.16, (nx, 0, 0), mx=1.0)   # 6 mm davanti alla parete: a filo faceva z-fighting (strisce bianche)
        R.scatola(m_oro, (sg * (hw - 0.12), L / 2, 0.95), (0.05, L - 2.0, 0.05))
        for u_scudo in (6.0, 12.5):
            for kk, mm, dx in ((0.62, m_sc_b, 0.012), (0.54, m_sc_c, 0.020)):
                scudo_parete(kk, mm, (x - sg * dx, u_scudo, 1.95), "ScudoMuro%d_%s_%d" % (sg, int(u_scudo), int(kk * 100)),
                             (math.pi / 2, 0.0, sg * -math.pi / 2))
    # parete di fondo (u = 0) con il varco della porta
    pw, ph = sala.PORTA_W / 2, sala.PORTA_H
    for (xa, xb) in ((-hw, -pw), (pw, hw)):
        R.parete(m_blu, xa, xb, 0.0, 0.0, 0.0, H, (0, 1, 0), mx=0.6)
    R.parete(m_blu, -pw, pw, 0.0, 0.0, ph, H, (0, 1, 0), mx=0.6)
    # bagliore del campo alla bocca (u = L): NIENTE parete, la bocca resta aperta
    # (la luce viene dal campo vero dietro: un muro qui coprirebbe l'entrata)
    return _costruisci_esterno(R, dati, cartella, erba_i, spalti_i, cart_i)


def _costruisci_esterno(R, dati, cartella, erba_i, spalti_i, cart_i):
    """Stadio: campo con righe, muro di base coi cartelloni, ciotola a 3 anelli (UV continue, nome a mosaico),
    seggiolini, tetto, maxischermi, facciata attorno alla bocca del tunnel."""
    m_erba = mat("Esterno_Erba", "#ffffff", erba_i, 0.95)
    m_linea = mat("Esterno_Linea", "#f4f4f4", None, 0.8)
    m_spalti = mat("Esterno_Spalti", "#ffffff", spalti_i, 0.85)
    m_seg = mat("Esterno_Seggiolini", dati["colori"]["dettagli"], None, 0.55)
    m_cart = mat("Esterno_Cartelloni", "#ffffff", cart_i, 0.6, emis=0.0)
    m_cem = mat("Esterno_Cemento", "#c9ccd2", None, 0.9)
    m_muro = mat("Esterno_Muro", _scuro_hex(dati["colori"]["dettagli"], 0.62), None, 0.8)
    m_tetto = mat("Esterno_Tetto", "#c8ccd4", None, 0.6)
    m_tetto_s = mat("Esterno_TettoSotto", "#8a8f99", None, 0.8)
    m_schermo = mat("Esterno_Schermo", "#0a0e1a", None, 0.4, emis=0.8)
    m_fac = mat("Tunnel_Facciata", _scuro_hex(dati["colori"]["dettagli"], 0.62), None, 0.8)
    m_testo = mat("Esterno_Testo", "#ffffff", None, 0.6)
    hw = W / 2
    uc = ST_CENTRO_U
    R_ = ST_RAGGIO
    # ---- campo: erba su tutto il disco della ciotola, righe del campo centrate
    R.parete(m_erba, -R_, R_, L, uc + R_, 0.0, 0.0, (0, 0, 1), mx=10.0, modo="ext", uvs=(8.0, 8.0), uv0=(0.0, 0.0))
    cx, cl = 27.0, 36.0                                      # semi-larghezza e semi-lunghezza del campo
    for (xa, xb, ua, ub) in ((-cx, cx, uc - cl, uc - cl + 0.15), (-cx, cx, uc + cl - 0.15, uc + cl),
                             (-cx, -cx + 0.15, uc - cl, uc + cl), (cx - 0.15, cx, uc - cl, uc + cl),
                             (-cx, cx, uc - 0.075, uc + 0.075)):
        R.parete(m_linea, xa, xb, ua, ub, 0.004, 0.004, (0, 0, 1), mx=40.0, modo="ext")
    # ---- muro di base (cartelloni in basso, cemento sopra) con il varco del tunnel: arriva alla quota del primo anello
    ang_tunnel = -math.pi / 2                                # il tunnel e' dalla parte di u piccolo
    def varco(a):
        d = (a - ang_tunnel + math.pi) % (2 * math.pi) - math.pi
        return abs(d) < 0.056                                # 4 spicchi di 192: circa 6,5 m
    _anello_ciotola(R, m_cart, R_ - 0.05, 0.0, R_ - 0.05, 1.0, 192, modo="ext", salta=varco, uvm=(8.0, 0.0, 1.0))
    _anello_ciotola(R, m_muro, R_ - 0.05, 1.0, R_ - 0.05, ST_ALTEZZA0, 192, modo="ext", salta=varco)
    # ---- facciata attorno alla bocca (u = L): chiude il varco, la bocca resta aperta (z da 0,9 a H)
    zb, zt = ST_QUOTA, ST_ALTEZZA0 + ST_QUOTA          # facciata alta come il muro di base
    R.parete(m_fac, -3.5, -hw, L, L, zb, zt, (0, 1, 0), mx=1.0, modo="ext")
    R.parete(m_fac, hw, 3.5, L, L, zb, zt, (0, 1, 0), mx=1.0, modo="ext")
    R.parete(m_fac, -hw, hw, L, L, H, zt, (0, 1, 0), mx=1.0, modo="ext")
    # ---- ciotola: 3 anelli, UV continue (u: 48 m = 8 spicchi, v: 24 m dalla quota del primo anello)
    z = ST_ALTEZZA0
    r = ST_RAGGIO
    for (prof, alz) in ST_ANELLI:
        lseg = 2 * math.pi * (r + prof / 2) / 48
        _anello_ciotola(R, m_spalti, r, z, r + prof, z + alz, 48, modo="ext", uvm=(8 * lseg, ST_ALTEZZA0, 24.0))
        _anello_ciotola(R, m_cem, r + prof, z + alz, r + prof + 1.2, z + alz + 0.4, 48, modo="ext")
        _seggiolini(R, m_seg, None, z, r, prof, alz, 48, None)
        r += prof + 1.2
        z += alz + 0.4
    # tetto ad anello con intradosso
    _anello_ciotola(R, m_tetto, ST_TETTO_R0, ST_TETTO_Z, ST_TETTO_R1, ST_TETTO_Z + 1.5, 64, modo="ext")
    _anello_ciotola(R, m_tetto_s, ST_TETTO_R0, ST_TETTO_Z - 0.3, ST_TETTO_R1, ST_TETTO_Z, 64, modo="ext")
    # 4 maxischermi appesi al tetto: ai lati e in fondo, mai sopra la camera di ingresso
    for (sx, su, dim) in ((-60.0, uc, (0.6, 10.0, 6.0)), (60.0, uc, (0.6, 10.0, 6.0)),
                          (-22.0, uc + 58.0, (10.0, 0.6, 6.0)), (22.0, uc + 58.0, (10.0, 0.6, 6.0))):
        R.scatola(m_schermo, (sx, su, 26.0), dim, modo="ext")
    # nome della squadra sulla facciata sopra la bocca
    testo_facciata(dati["nome"].upper(), 0.60, 6.0, m_testo, (0.0, L + 0.01, H + (ST_ALTEZZA0 + ST_QUOTA - H) / 2))
    ob = R.costruisci()
    m_sc_b = mat("Tunnel_StemmaBordo", "#f4f4f4", None, 0.4)
    m_sc_c = mat("Tunnel_StemmaCampo", dati["colori"]["dettagli"], None, 0.4)
    for sg in (-1, 1):
        x = sg * 1.18
        scudo_parete(0.20, m_sc_b, (x, 0.012, 1.95), "StemmaB%d" % sg, (math.pi / 2, 0.0, 0.0))
        scudo_parete(0.17, m_sc_c, (x, 0.020, 1.95), "StemmaC%d" % sg, (math.pi / 2, 0.0, 0.0))
    return ob


def percorso():
    """Percorso della camera in coordinate glTF: [posizione, bersaglio, fov]. L'ultimo punto (la posa
    della sala) lo aggiunge il sito da `VISTE.sala`, cosi' i due pezzi combaciano."""
    # il campo e' 90 cm sopra il pavimento del tunnel (ST_QUOTA): occhi a ~1,7 m dal piano che si calpesta
    q = ST_QUOTA
    punti = [
        ((0.70, 34.0, q + 1.75), (0.0, 16.0, q + 1.35), 70),
        ((0.45, 27.0, q + 1.72), (0.0, 12.0, q + 1.25), 68),
        ((0.20, 22.0, q + 1.68), (0.0, 8.0, 1.60), 67),
        ((0.60, 17.5, 0.60 + 1.62), (0.0, 5.0, 1.60), 66),    # a meta' scalinata
        ((0.90, 12.5, 1.66), (0.0, 0.0, 1.60), 66),
        ((0.35, 3.5, 1.62), (0.0, -6.0, 1.55), 66),
        ((0.00, -1.0, 1.60), (0.0, -9.0, 1.50), 66),
    ]
    out = []
    for p, t, f in punti:
        a, b = w(p), w(t)
        out.append({"p": [float(a[0]), float(a[2]), float(-a[1])],
                    "t": [float(b[0]), float(b[2]), float(-b[1])], "fov": f})
    return out


def verifica(ob):
    err = []
    tri = 0
    for m, o in ob.items():
        tri += len(o.data.polygons)
    mx = max(max(abs(v.co.x) for v in o.data.vertices) for o in ob.values())
    ok = lambda c, msg: err.append(msg) if not c else None  # noqa: E731
    ok(tri < 60000, "troppe facce %d" % tri)  # stadio: la ciotola vera ha piu facce del corridoio vecchio
    ok(abs(mx - ST_TETTO_R1) < 2.0, "larghezza stadio %.1f" % mx)
    # il varco della parete di fondo combacia con la porta della sala
    ok(abs(sala.PORTA_H - 2.35) < 1e-6 and sala.PORTA_H < H, "porta piu' alta del tunnel")
    ok(abs(T0 - sala.RAGGIO - sala.SPESSORE_MURO) < 1e-9, "u = 0 non coincide con l'imbotte")
    pts = percorso()
    ok(all(abs(p["p"][0]) < W / 2 for p in pts), "camera fuori dal tunnel (x)")
    ok(pts[-1]["p"][2] < T0 + 0.1, "il percorso non arriva alla porta")
    return err, tri


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.abspath(argv[0]) if argv else os.path.abspath("out_tunnel")
    os.makedirs(out, exist_ok=True)
    radice = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dati = json.load(open(os.path.join(radice, "squadra.json"), encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ob = costruisci(dati, out)
    err, tri = verifica(ob)
    for e in err:
        print("TUNNEL_ERRORE", e)
    glb = os.path.join(out, "tunnel.glb")
    bpy.ops.export_scene.gltf(
        filepath=glb, export_format="GLB", export_apply=True, export_yup=True, export_animations=False,
        export_cameras=False, export_lights=False, export_materials="EXPORT", export_vertex_color="ACTIVE",
        export_image_format="JPEG", export_image_quality=90)  # HD: 90 invece di 82
    man = {"u0": T0, "larghezza": W, "altezza": H, "lunghezza": L,
           "bocca": {"z": T0 + L}, "percorso": percorso(),
           "passo": 0.75, "ampiezza_bob": 0.014}
    json.dump(man, open(os.path.join(out, "tunnel.json"), "w", encoding="utf-8"), indent=1)
    print("TUNNEL_OK", glb, os.path.getsize(glb), "facce", tri)
    if err:
        sys.exit(1)
