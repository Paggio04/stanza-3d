"""maglia.py - maglia da calcio appesa a una gruccia. COSTRUITA, NON SIMULATA.

Si usa cosi':

    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import maglia
    m = maglia.costruisci("Maglia_10", "GIOCATORE 10", 10,
                          "#ffffff", "#173f9a", "#173f9a")
    # m.shirt (oggetto), m.gruccia, m.figli, m.info (misure)

Sistema di coordinate locale della maglia: metri, Z su, petto +Y, schiena -Y,
maniche lungo X. L'origine e' l'apice della gruccia (dove sale il gancio).
Il gancio avvolge un'asta lungo X il cui asse sta a Z = +ALTEZZA_GANCIO sopra
l'origine (raggio asta al massimo RAGGIO_ASTA): per appendere la maglia, metti
l'origine a (x, y_asta, z_asta - ALTEZZA_GANCIO).

Forma: due pannelli (petto e schiena) con lo stesso contorno, riempiti di
triangoli, saldati sulle cuciture (spalle, sotto manica, fianchi). Lo spessore
nasce da una funzione analitica (sezione a tubo), le pieghe da onde verticali
che partono morbide dalle spalle. Nome, numero e scudo sono proiettati sulla
STESSA funzione: seguono le pieghe e non possono galleggiare, specchiarsi o
vedersi dal lato sbagliato.

Eseguito da solo (`blender -b -P maglia.py -- prova CARTELLA [PIXEL [CAMPIONI]]`)
costruisce la prova, la misura e scrive 4 render (maglia_fronte, _retro, _lato,
_tre_quarti). Esce con codice 1 se una misura non torna. `prova()` azzera la
scena: va lanciato SEMPRE come processo a parte, mai dentro lo script della scena.
"""
import bpy
import bmesh
import math
import os
import sys

import numpy as np
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt

# ------------------------------------------------------------------ misure (m)
TAN12 = math.tan(math.radians(12.0))      # pendenza delle spalle
NECK_X = 0.095                            # mezza apertura del collo
NECK_Z = -NECK_X * TAN12
SH_X = 0.230                              # punto spalla
SH_Z = -SH_X * TAN12
NECK_DROP_F = 0.135                       # scollo davanti: a V (>= 0,10 = V, altrimenti girocollo)
NECK_DROP_B = 0.030                       # scollo dietro: tondo
SLEEVE_LEN = 0.20
SLEEVE_ANG = math.radians(46.0)           # manica sotto l'orizzontale
CUFF_W = 0.135                            # larghezza del polsino da piatto
ARMPIT = (0.262, -0.270)                  # ascella
HEM_Z = -0.74
HEM_X = 0.275
STEP = 0.010                              # lato dei triangoli (1 cm)
ALTEZZA_GANCIO = 0.060                    # asse asta sopra l'origine
RAGGIO_ASTA = 0.0125
COLL_W = 0.036                            # altezza del bordo del colletto
CUFF_RIB = 0.030                          # altezza costine polsino
POLSINI = False                           # True = polsini a costine nel colore dettagli
SVASATURA = 0.026                         # quanto la bocca della manica si stacca dal busto (m)
PARTI_FISSE = ("_Scudo", "_Colletto", "_Filetto", "_Sponsor")   # figli uguali per tutte le copie

_CT = (SH_X + SLEEVE_LEN * math.cos(SLEEVE_ANG),
       SH_Z - SLEEVE_LEN * math.sin(SLEEVE_ANG))           # polsino, bordo alto
_CB = (_CT[0] - CUFF_W * math.sin(SLEEVE_ANG),
       _CT[1] - CUFF_W * math.cos(SLEEVE_ANG))             # polsino, bordo basso


def _smooth(a, b, x):
    t = np.clip((np.asarray(x, dtype=float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _hash(ix, iz, seed):
    n = np.sin(ix * 127.1 + iz * 311.7 + seed * 74.7) * 43758.5453
    return n - np.floor(n)


def _vn(x, z, seed=0.0):
    """Rumore di valore 2D in [-1, 1], deterministico, vettoriale."""
    x = np.asarray(x, float)
    z = np.asarray(z, float)
    ix, iz = np.floor(x), np.floor(z)
    fx, fz = x - ix, z - iz
    ux, uz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    a, b = _hash(ix, iz, seed), _hash(ix + 1, iz, seed)
    c, d = _hash(ix, iz + 1, seed), _hash(ix + 1, iz + 1, seed)
    return (a + (b - a) * ux + (c - a) * uz + (a - b - c + d) * ux * uz) * 2.0 - 1.0


def _hem_z(x):
    s = np.asarray(x, dtype=float) / HEM_X
    env = 1.0 - s * s
    return (HEM_Z - 0.022 * env
            + 0.009 * np.sin(2 * math.pi * np.asarray(x) / 0.53 * 1.3 + 0.5) * env)


def _seg(p0, p1, n=None, step=STEP):
    """Punti da p0 a p1 (p1 escluso). Stessi argomenti = stessi punti."""
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    n = n or max(1, int(round(L / step)))
    return [(p0[0] + (p1[0] - p0[0]) * k / n, p0[1] + (p1[1] - p0[1]) * k / n)
            for k in range(n)]


def _mirror(p):
    return (-p[0], p[1])


class _Geom:
    """Contorni, cuciture e funzione di superficie (tutta vettoriale)."""

    def __init__(self):
        S = (SH_X, SH_Z)
        N = (NECK_X, NECK_Z)
        A = ARMPIT
        H = (HEM_X, float(_hem_z(HEM_X)))
        # tratti destri, percorsi dal collo verso il fondo
        self.seg_cucitura = [  # (p0, p1) chiusi (y=0)
            (N, S), (S, _CT), (_CB, A), (A, H)]
        self.seg_polsino = [(_CT, _CB)]
        # cuciture dense (4x i punti del contorno: li contengono tutti)
        dense = []
        for (p0, p1) in self.seg_cucitura:
            for q0, q1 in ((p0, p1), (_mirror(p0), _mirror(p1))):
                n = max(1, int(round(math.hypot(q1[0] - q0[0], q1[1] - q0[1]) / STEP)))
                dense += _seg(q0, q1, n * 4) + [q1]
        self.seam = np.array(dense)
        cuff = []
        for q0, q1 in ((_CT, _CB), (_mirror(_CT), _mirror(_CB))):
            n = max(1, int(round(math.hypot(q1[0] - q0[0], q1[1] - q0[1]) / STEP)))
            cuff += _seg(q0, q1, n * 4) + [q1]
        self.cuff = np.array(cuff)
        xs = np.linspace(-HEM_X, HEM_X, int(2 * HEM_X / 0.0025) + 1)
        self.hem = np.stack([xs, _hem_z(xs)], 1)
        self.neck = {+1: self._neck_dense(NECK_DROP_F), -1: self._neck_dense(NECK_DROP_B)}
        self.outline = {+1: self._outline(NECK_DROP_F), -1: self._outline(NECK_DROP_B)}

    # --- collo
    @staticmethod
    def _neck_curve(drop, m=2000):
        t = np.linspace(0.0, 1.0, m)
        x = -NECK_X * np.cos(math.pi * t)
        if drop >= 0.10:                      # scollo a V, apice arrotondato
            e = 0.012
            u = (np.sqrt(x * x + e * e) - e) / (math.sqrt(NECK_X ** 2 + e * e) - e)
            z = NECK_Z - drop * (1.0 - u)
        else:                                 # girocollo
            z = NECK_Z - drop * np.sin(math.pi * t)
        P = np.stack([x, z], 1)
        seg = np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1]))
        return P, np.concatenate([[0.0], np.cumsum(seg)])

    def _neck_pts(self, drop, n):
        P, cum = self._neck_curve(drop)
        s = np.linspace(0.0, cum[-1], n, endpoint=False)
        return list(zip(np.interp(s, cum, P[:, 0]).tolist(), np.interp(s, cum, P[:, 1]).tolist()))

    def _neck_n(self, drop):
        return max(6, int(round(self._neck_curve(drop)[1][-1] / STEP)))

    def _neck_dense(self, drop):
        n = self._neck_n(drop)
        return np.array(self._neck_pts(drop, n * 4) + [(NECK_X, NECK_Z)])

    # --- contorno (senso orario), con segno "angolo vero"
    def _outline(self, drop):
        S = (SH_X, SH_Z)
        N = (NECK_X, NECK_Z)
        A = ARMPIT
        H = (HEM_X, float(_hem_z(HEM_X)))
        pts, corner = [], []

        def add(lst, first_is_corner=True):
            for i, p in enumerate(lst):
                pts.append(p)
                corner.append(i == 0 and first_is_corner)

        add(self._neck_pts(drop, self._neck_n(drop)))                 # collo (sx->dx)
        n_neck = len(pts)
        add(_seg(N, S))
        add(_seg(S, _CT))
        add(_seg(_CT, _CB))
        add(_seg(_CB, A))
        add(_seg(A, H))
        nh = max(1, int(round(2 * HEM_X / STEP)))                     # fondo (dx->sx)
        hem = [(HEM_X - 2 * HEM_X * k / nh, 0.0) for k in range(nh)]
        add([(x, float(_hem_z(x))) for x, _ in hem])
        add(_seg(_mirror(H), _mirror(A)))
        add(_seg(_mirror(A), _mirror(_CB)))
        add(_seg(_mirror(_CB), _mirror(_CT)))
        add(_seg(_mirror(_CT), _mirror(S)))
        add(_seg(_mirror(S), _mirror(N)))
        return {"pts": np.array(pts), "corner": corner, "n_neck": n_neck}

    # --- distanze
    @staticmethod
    def _mindist(P, Q):
        out = np.empty(len(P))
        for i in range(0, len(P), 400):
            d = P[i:i + 400, None, :] - Q[None, :, :]
            out[i:i + 400] = np.sqrt((d * d).sum(2)).min(1)
        return out

    def d_cucitura(self, X, Z):
        return self._mindist(np.stack([np.ravel(X), np.ravel(Z)], 1), self.seam).reshape(np.shape(X))

    # --- superficie
    @staticmethod
    def _sleeve_blend(X, Z):
        d = (ARMPIT[0] - SH_X, ARMPIT[1] - SH_Z)
        nx, nz = -d[1], d[0]
        nn = math.hypot(nx, nz)
        sd = (np.abs(X) - SH_X) * nx / nn + (Z - SH_Z) * nz / nn
        return _smooth(-0.015, 0.025, sd)

    def mezzo_spessore(self, X, Z, dcut=None):
        X = np.asarray(X, float)
        Z = np.asarray(Z, float)
        d = self.d_cucitura(X, Z) if dcut is None else dcut
        b = self._sleeve_blend(X, Z)
        R = 0.115 * (1 - b) + 0.075 * b
        t = np.clip(d / R, 0.0, 1.0)
        prof = np.sqrt(1.0 - (1.0 - t) ** 2)
        zz = -Z
        Dt = 0.032 * (0.35 + 0.65 * _smooth(0.0, 0.22, zz)) * (1 - 0.35 * _smooth(0.30, 0.74, zz))
        D = Dt * (1 - b) + 0.030 * b
        return D * prof

    def piega(self, X, Z, lato, dcut=None):
        """Pieghe: cadute verticali irregolari, ventagli dalle punte della
        gruccia e dalle ascelle, grinze a cresta, onde dell'orlo. Tutto zero
        sulle cuciture."""
        X = np.asarray(X, float)
        Z = np.asarray(Z, float)
        d = self.d_cucitura(X, Z) if dcut is None else dcut
        zz = -Z
        seed = 1.0 if lato > 0 else 7.0
        ph = 0.35 if lato > 0 else 2.05
        b = self._sleeve_blend(X, Z)
        env = _smooth(0.03, 0.28, zz) * (0.6 + 0.4 * _smooth(0.30, 0.70, zz))
        # 1) cadute verticali, con frequenza e ampiezza irregolari
        hw = 0.20 + 0.06 * _smooth(0.0, 0.30, zz)
        s = X / hw + 0.10 * _vn(Z * 2.6, X * 3.1, seed)
        am = 0.65 + 0.35 * (_vn(X * 4.0, Z * 1.7, seed + 3) * 0.5 + 0.5)
        f = am * (0.0110 * np.sin(2 * math.pi * 1.45 * s + ph)
                  + 0.0060 * np.sin(2 * math.pi * 3.2 * s + ph * 1.7 + 1.3 * zz)
                  + 0.0080 * np.sin(2 * math.pi * 0.75 * s + ph + 0.5))
        ft = f * env
        # 2) ventagli dalle punte della gruccia (spalle)
        for sx in (+1.0, -1.0):
            px, pz = sx * 0.215, -0.215 * TAN12 - 0.01
            dx, dz = X - px, Z - pz
            r = np.hypot(dx, dz)
            th = np.arctan2(dx, -dz)
            ft = ft + (0.0070 * np.exp(-r / 0.17) * _smooth(0.015, 0.06, r)
                       * _smooth(0.0, 0.05, -dz)
                       * np.sin(9.0 * th + ph * sx + 1.6 * _vn(dx * 9, dz * 9, seed + 2)))
        # 3) grinze a cresta (creste morbide, non onde regolari)
        rn = 1.0 - np.abs(_vn(X * 9.0 + Z * 2.0, Z * 5.5 - X * 1.5, seed + 11))
        ft = ft + 0.0040 * (rn ** 3 - 0.30) * _smooth(0.05, 0.35, zz)
        # 4) onde dell'orlo
        ft = ft + 0.0075 * _smooth(0.56, 0.74, zz) * _vn(X * 11.0, Z * 0.5, seed + 5)
        # maniche: pieghe di traverso e grinze
        ax = np.abs(X)
        px_ = -math.sin(SLEEVE_ANG)
        pz_ = -math.cos(SLEEVE_ANG)
        u = ((ax - SH_X) * px_ + (Z - SH_Z) * pz_) / CUFF_W
        v = (ax - SH_X) * math.cos(SLEEVE_ANG) - (Z - SH_Z) * math.sin(SLEEVE_ANG)
        fs = (0.0080 * np.sin(2 * math.pi * 1.6 * u + ph + 0.7 + 0.8 * _vn(v * 8, u * 3, seed + 4))
              + 0.0045 * np.sin(2 * math.pi * 3.4 * u + 2.0 * ph))
        fs = fs + 0.0035 * (rn ** 3 - 0.30)
        fs = fs * _smooth(0.01, 0.09, v)
        tot = (1 - b) * ft + b * fs
        # 5) ventaglio dall'ascella (su torso e manica)
        for sx in (+1.0, -1.0):
            ax_, az_ = sx * ARMPIT[0], ARMPIT[1]
            dx, dz = X - ax_, Z - az_
            r = np.hypot(dx, dz)
            th = np.arctan2(dz, dx)
            tot = tot + (0.0060 * np.exp(-r / 0.11) * _smooth(0.012, 0.05, r)
                         * np.sin(7.0 * th + ph + 1.4 * _vn(dx * 12, dz * 12, seed + 6)))
        w = _smooth(0.0, 0.040, d)
        return 1.2 * tot * w

    def superficie(self, X, Z, lato):
        """Quota Y dell'esterno della maglia (lato +1 petto, -1 schiena)."""
        X = np.asarray(X, float)
        Z = np.asarray(Z, float)
        d = self.d_cucitura(X, Z)
        return lato * (self.mezzo_spessore(X, Z, d) + self.piega(X, Z, lato, d))


_GEO = None


def geom():
    global _GEO
    if _GEO is None:
        _GEO = _Geom()
    return _GEO


# ------------------------------------------------------------------ triangolazione
def _dentro(poly, P):
    x = P[:, 0]
    z = P[:, 1]
    ins = np.zeros(len(P), bool)
    n = len(poly)
    for i in range(n):
        x1, z1 = poly[i]
        x2, z2 = poly[(i + 1) % n]
        cond = (z1 > z) != (z2 > z)
        xin = (x2 - x1) * (z - z1) / (z2 - z1 + 1e-30) + x1
        ins ^= cond & (x < xin)
    return ins


def riempi(poly, step=STEP, bbox=None):
    """Triangola un poligono (lista di (x,z)) con punti interni a reticolo
    esagonale. Ritorna (punti Nx2, triangoli Mx3)."""
    poly = np.asarray(poly, float)
    n = len(poly)
    dense = []
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        for k in range(4):
            dense.append(a + (b - a) * k / 4.0)
    dense = np.array(dense)
    if bbox is None:
        bbox = (poly[:, 0].min(), poly[:, 0].max(), poly[:, 1].min(), poly[:, 1].max())
    x0, x1, z0, z1 = bbox
    pts = []
    j = 0
    z = z0
    while z <= z1:
        x = x0 + (step / 2 if j % 2 else 0.0)
        while x <= x1:
            pts.append((x, z))
            x += step
        z += step * 0.8660254
        j += 1
    pts = np.array(pts)
    pts = pts[_dentro(poly, pts)]
    dist = _Geom._mindist(pts, dense)
    pts = pts[dist >= 0.6 * step]
    allp = np.vstack([poly, pts])
    area = 0.0
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        area += a[0] * b[1] - b[0] * a[1]
    loop = list(range(n))
    if area < 0:
        loop = loop[::-1]
    r = delaunay_2d_cdt([Vector((float(p[0]), float(p[1]))) for p in allp], [], [loop], 1, 1e-7)
    verts = np.array([(v[0], v[1]) for v in r[0]])
    return verts, r[2]


# ------------------------------------------------------------------ materiali
def _hex(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c]
    return (lin[0], lin[1], lin[2], 1.0)


def materiale_tessuto(nome, colore, dettagli):
    m = bpy.data.materials.get(nome)
    if m:
        return m
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    L = nt.links.new

    def attr(nm):
        a = N("ShaderNodeAttribute")
        a.attribute_name = nm
        return a

    def mth(op, a=None, b=None):
        n = N("ShaderNodeMath")
        n.operation = op
        if a is not None:
            n.inputs[0].default_value = a
        if b is not None:
            n.inputs[1].default_value = b
        return n

    out = N("ShaderNodeOutputMaterial")
    pb = N("ShaderNodeBsdfPrincipled")
    # costine: rib < 0 -> colore dettagli, piu' opache
    lt = mth("LESS_THAN", None, 0.0)
    L(attr("rib").outputs["Fac"], lt.inputs[0])
    mix = N("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[6].default_value = _hex(colore)
    mix.inputs[7].default_value = _hex(dettagli)
    L(lt.outputs["Value"], mix.inputs[0])
    L(mix.outputs[2], pb.inputs["Base Color"])
    rg = N("ShaderNodeMix")
    rg.data_type = "FLOAT"
    rg.inputs[2].default_value = 0.44
    rg.inputs[3].default_value = 0.80
    L(lt.outputs["Value"], rg.inputs[0])
    L(rg.outputs[0], pb.inputs["Roughness"])
    # microtrama
    tc = N("ShaderNodeTexCoord")
    noi = N("ShaderNodeTexNoise")
    noi.inputs["Scale"].default_value = 520.0
    noi.inputs["Detail"].default_value = 3.0
    L(tc.outputs["Object"], noi.inputs["Vector"])
    b1 = N("ShaderNodeBump")
    b1.inputs["Strength"].default_value = 0.10
    b1.inputs["Distance"].default_value = 0.002
    L(noi.outputs["Fac"], b1.inputs["Height"])
    # cuciture: cresta a 6 mm dalla cucitura; orlo: cucitura a 22 mm dal bordo
    def cresta(nm, centro, larg):
        sub = mth("SUBTRACT", None, centro)
        L(attr(nm).outputs["Fac"], sub.inputs[0])
        ab = mth("ABSOLUTE")
        L(sub.outputs["Value"], ab.inputs[0])
        dv = mth("DIVIDE", None, larg)
        L(ab.outputs["Value"], dv.inputs[0])
        inv = mth("SUBTRACT", 1.0, None)
        L(dv.outputs["Value"], inv.inputs[1])
        mx = mth("MAXIMUM", None, 0.0)
        L(inv.outputs["Value"], mx.inputs[0])
        return mx
    c1 = cresta("dseam", 0.006, 0.0022)
    c2 = cresta("dhem", 0.022, 0.0016)
    hm = mth("MAXIMUM")
    L(c1.outputs["Value"], hm.inputs[0])
    L(c2.outputs["Value"], hm.inputs[1])
    b2 = N("ShaderNodeBump")
    b2.inputs["Strength"].default_value = 0.35
    b2.inputs["Distance"].default_value = 0.0012
    L(hm.outputs["Value"], b2.inputs["Height"])
    L(b1.outputs["Normal"], b2.inputs["Normal"])
    L(b2.outputs["Normal"], pb.inputs["Normal"])
    for k, v in (("Sheen Weight", 0.5), ("Sheen Roughness", 0.45),
                 ("Subsurface Weight", 0.05), ("Subsurface Scale", 0.004)):
        if k in pb.inputs:
            pb.inputs[k].default_value = v
    L(pb.outputs["BSDF"], out.inputs["Surface"])
    return m


def _materiale_semplice(nome, colore, rough=0.5, metal=0.0):
    m = bpy.data.materials.get(nome)
    if m:
        return m
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    pb = m.node_tree.nodes["Principled BSDF"]
    pb.inputs["Base Color"].default_value = _hex(colore)
    pb.inputs["Roughness"].default_value = rough
    pb.inputs["Metallic"].default_value = metal
    return m


# ------------------------------------------------------------------ costruzione
class Maglia:
    pass


def _collezione(coll):
    return coll if coll is not None else bpy.context.scene.collection


def mesh_maglia(nome, coll=None, colore="#ffffff", dettagli="#173f9a"):
    """Costruisce la mesh della maglia (senza scritte). Ritorna l'oggetto."""
    G = geom()
    bm = bmesh.new()
    rib = bm.verts.layers.float.new("rib")
    lseam = bm.verts.layers.float.new("dseam")
    lhem = bm.verts.layers.float.new("dhem")
    lao = bm.verts.layers.float.new("ao")
    for lato in (+1, -1):
        ol = G.outline[lato]["pts"]
        P, T = riempi(ol)
        X = P[:, 0]
        Z = P[:, 1]
        d = G._mindist(P, G.seam)
        pf = G.piega(X, Z, lato, d)
        b = G._sleeve_blend(X, Z)
        v_man = (np.abs(X) - SH_X) * math.cos(SLEEVE_ANG) - (Z - SH_Z) * math.sin(SLEEVE_ANG)
        svasa = SVASATURA * b * _smooth(0.02, 0.20, v_man)       # la bocca della manica si apre verso chi guarda
        y = lato * (G.mezzo_spessore(X, Z, d) + pf + svasa)
        # ombreggiatura "cotta" nei vertici: valli delle pieghe, ascelle, interno manica
        ao = 0.20 * np.clip(-pf / 0.010, 0.0, 1.0)
        for sx in (+1.0, -1.0):
            ao = ao + 0.22 * np.exp(-np.hypot(X - sx * ARMPIT[0], Z - ARMPIT[1]) / 0.045)
        ao = ao + 0.10 * b * _smooth(0.06, 0.20, v_man)
        ao = np.clip(ao, 0.0, 0.45)
        dn = G._mindist(P, G.neck[lato])
        dc = G._mindist(P, G.cuff)
        dh = G._mindist(P, G.hem)
        rv = np.minimum(dn - COLL_W, dc - CUFF_RIB) if POLSINI else dn - COLL_W
        dh = np.minimum(dh, dc)               # orlo di fondo e orlo dei polsini: stessa cucitura
        vs = []
        for i in range(len(P)):
            v = bm.verts.new((float(X[i]), float(y[i]), float(Z[i])))
            v[rib] = float(rv[i])
            v[lseam] = float(d[i])
            v[lhem] = float(dh[i])
            v[lao] = float(ao[i])
            vs.append(v)
        for t in T:
            a, b, c = vs[t[0]], vs[t[1]], vs[t[2]]
            ny = (b.co.z - a.co.z) * (c.co.x - a.co.x) - (b.co.x - a.co.x) * (c.co.z - a.co.z)
            tri = (a, b, c) if (ny > 0) == (lato > 0) else (a, c, b)
            try:
                bm.faces.new(tri)
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    me = bpy.data.meshes.new(nome + "_mesh")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(nome, me)
    _collezione(coll).objects.link(ob)
    me.materials.append(materiale_tessuto("M_Tessuto_" + colore.lstrip("#") + dettagli.lstrip("#"),
                                          colore, dettagli))
    rv = np.array([a.value for a in me.attributes["rib"].data])
    vg = ob.vertex_groups.new(name="costine")
    for i, val in enumerate(rv):
        w = float(1.0 - _smooth(-0.004, 0.003, val))
        if w > 0.001:
            vg.add([i], w, "REPLACE")
    sol = ob.modifiers.new("Spessore", "SOLIDIFY")   # PRIMA lo spessore, poi la suddivisione:
    sol.thickness = 0.0045                           # al contrario il bordo esce a denti di sega
    sol.thickness_vertex_group = 0.45                # tessuto 2 mm, costine 4,5 mm
    sol.vertex_group = "costine"
    sol.offset = -1.0
    sol.use_rim = True
    sub = ob.modifiers.new("Subdiv", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 1
    sub.boundary_smooth = "PRESERVE_CORNERS"
    return ob


def _mesh_testo(testo, altezza, larghezza_max, bold=0.012, passo=0.005):
    """Mesh piatta del testo, centrata in (0,0), nel piano XY (z=0)."""
    cu = bpy.data.curves.new("tmp_testo", "FONT")
    cu.body = testo
    cu.size = altezza
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.offset = bold * altezza
    cu.fill_mode = "FRONT"
    ob = bpy.data.objects.new("tmp_testo", cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    w = max(xs) - min(xs)
    s = min(1.0, larghezza_max / w) if w > 0 else 1.0
    bm = bmesh.new()
    bm.from_mesh(me)
    for v in bm.verts:
        v.co.x = (v.co.x - cx) * s
        v.co.y = (v.co.y - cy) * s
        v.co.z = 0.0
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    for _ in range(6):
        lunghi = [e for e in bm.edges if e.calc_length() > passo]
        if not lunghi:
            break
        bmesh.ops.subdivide_edges(bm, edges=lunghi, cuts=1, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    return me


def _proietta(me, lato, cx, cz, mat, nome, padre, coll):
    """Appoggia una mesh piatta (piano XY) sulla superficie, senza specchi."""
    G = geom()
    X = np.array([cx + v.co.x for v in me.vertices])
    Z = np.array([cz + v.co.y for v in me.vertices])
    Y = G.superficie(X, Z, lato) + lato * 0.0015
    bm = bmesh.new()
    bm.from_mesh(me)
    for i, v in enumerate(bm.verts):
        v.co = (float(X[i]), float(Y[i]), float(Z[i]))
    if lato > 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.name = nome + "_mesh"
    ob = bpy.data.objects.new(nome, me)
    _collezione(coll).objects.link(ob)
    ob.parent = padre
    ob.data.materials.append(mat)
    sol = ob.modifiers.new("Rilievo", "SOLIDIFY")
    sol.thickness = 0.0007
    sol.offset = 1.0
    return ob


PASSO_TESTO = 0.005      # lato dei triangoli delle scritte (m); per il web 0,009


def scritte(shirt, nome, numero, colore, coll=None):
    """Nome (alto) e numero (grande) centrati sulla schiena, figli di `shirt`."""
    mat = _materiale_semplice("M_Scritte_" + colore.lstrip("#"), colore, 0.72)
    out = []
    me = _mesh_testo(nome.upper(), 0.065, 0.42, passo=PASSO_TESTO)
    out.append(_proietta(me, -1, 0.0, -0.150, mat, shirt.name + "_Nome", shirt, coll))
    me = _mesh_testo(str(numero), 0.36, 0.40, passo=PASSO_TESTO)
    out.append(_proietta(me, -1, 0.0, -0.335, mat, shirt.name + "_Numero", shirt, coll))
    return out


def scudo(shirt, coll=None, colore="#9aa0a6"):
    """Scudo segnaposto 7 cm sul petto, a sinistra di chi indossa (x negativo)."""
    mat = _materiale_semplice("M_Scudo", colore, 0.5)
    w, h = 0.035, 0.0425
    poly = [(-w, h), (w, h), (w, 0.0)]
    for k in range(1, 12):
        a = math.pi * k / 12 / 2
        poly.append((w * math.cos(a), -h * math.sin(a)))
    poly.append((0.0, -h))
    for k in range(11, 0, -1):
        a = math.pi * k / 12 / 2
        poly.append((-w * math.cos(a), -h * math.sin(a)))
    poly.append((-w, 0.0))
    P, T = riempi(poly, step=0.006)
    me = bpy.data.meshes.new("tmp_scudo")
    me.from_pydata([(float(p[0]), float(p[1]), 0.0) for p in P], [], [tuple(int(i) for i in t) for t in T])
    me.update()
    return _proietta(me, +1, -0.115, -0.150, mat, shirt.name + "_Scudo", shirt, coll)


def _nastro_curva(shirt, lato, curva, normali, d0, d1, sollevo, mat, nome, coll):
    """Nastro che segue una curva del piano (x, z), da d0 a d1 di distanza lungo la normale,
    appoggiato sulla superficie con un piccolo rilievo a cupola."""
    G = geom()
    nc = max(3, int(round((d1 - d0) / 0.004)) + 1)
    dd = np.linspace(d0, d1, nc)
    X = curva[:, 0, None] + normali[:, 0, None] * dd[None, :]
    Z = curva[:, 1, None] + normali[:, 1, None] * dd[None, :]
    ext = np.abs(X) > NECK_X - 0.002                       # sulla spalla il nastro non sale oltre il bordo
    Z = np.where(ext, np.minimum(Z, -np.abs(X) * TAN12 - 0.0012), Z)
    t = (dd - d0) / (d1 - d0)
    lift = sollevo * (0.40 + 0.60 * np.sqrt(np.clip(1.0 - (2.0 * t - 1.0) ** 2, 0.0, 1.0)))
    Y = G.superficie(X, Z, lato) + lato * lift[None, :]
    n = len(curva)
    bm = bmesh.new()
    vs = [[bm.verts.new((float(X[i, j]), float(Y[i, j]), float(Z[i, j]))) for j in range(nc)] for i in range(n)]
    for i in range(n - 1):
        for j in range(nc - 1):
            a, b, c, d = vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1]
            ny = (b.co.z - a.co.z) * (d.co.x - a.co.x) - (b.co.x - a.co.x) * (d.co.z - a.co.z)
            bm.faces.new((a, b, c, d) if (ny > 0) == (lato > 0) else (a, d, c, b))
    me = bpy.data.meshes.new(nome + "_mesh")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(nome, me)
    _collezione(coll).objects.link(ob)
    ob.parent = shirt
    ob.data.materials.append(mat)
    return ob


def _curva_collo(drop, passo=0.004):
    """Collo ricampionato a passo costante: punti e normali che guardano verso il busto."""
    P, cum = _Geom._neck_curve(drop)
    n = max(8, int(round(cum[-1] / passo)))
    s = np.linspace(0.0, cum[-1], n)
    pts = np.stack([np.interp(s, cum, P[:, 0]), np.interp(s, cum, P[:, 1])], 1)
    tg = np.gradient(pts, axis=0)
    tg /= np.linalg.norm(tg, axis=1)[:, None] + 1e-12
    nor = np.stack([tg[:, 1], -tg[:, 0]], 1)
    C = np.array([0.0, NECK_Z + 0.03])
    gira = ((pts - C) * nor).sum(1) < 0
    nor[gira] *= -1.0
    return pts, nor


def colletto(shirt, colore, filetto="#ffffff", coll=None):
    """Bordo del colletto: nastro nel colore dettagli (davanti a V, dietro tondo) con un filetto
    bianco sul bordo esterno. Ritorna i figli creati."""
    mc = _materiale_semplice("M_Colletto_" + colore.lstrip("#"), colore, 0.72)
    mf = _materiale_semplice("M_Filetto_" + filetto.lstrip("#"), filetto, 0.6)
    out = []
    for lato, drop, nm in ((+1, NECK_DROP_F, "Davanti"), (-1, NECK_DROP_B, "Dietro")):
        pts, nor = _curva_collo(drop)
        out.append(_nastro_curva(shirt, lato, pts, nor, -0.0015, COLL_W, 0.0032, mc, shirt.name + "_Colletto" + nm, coll))
        out.append(_nastro_curva(shirt, lato, pts, nor, COLL_W, COLL_W + 0.0036, 0.0036, mf, shirt.name + "_Filetto" + nm, coll))
    return out


def sponsor(shirt, coll=None, colore="#8c929a"):
    """Sponsor segnaposto: scritta grande al centro del petto, piccola in basso dietro."""
    mt = _materiale_semplice("M_Sponsor", colore, 0.7)
    out = []
    me = _mesh_testo("SPONSOR", 0.050, 0.26, passo=PASSO_TESTO)
    out.append(_proietta(me, +1, 0.0, -0.285, mt, shirt.name + "_SponsorPetto", shirt, coll))
    me = _mesh_testo("SPONSOR", 0.022, 0.12, passo=PASSO_TESTO)
    out.append(_proietta(me, -1, 0.0, -0.585, mt, shirt.name + "_SponsorDietro", shirt, coll))
    return out


def gruccia(nome, coll=None):
    """Gruccia: due bracci a 12 gradi sotto le spalle, gancio che avvolge l'asta."""
    cu = bpy.data.curves.new(nome + "_curva", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.0035
    cu.bevel_resolution = 3
    cu.resolution_u = 6
    z0 = -0.012

    def spline(pts):
        s = cu.splines.new("POLY")
        s.points.add(len(pts) - 1)
        for p, q in zip(s.points, pts):
            p.co = (q[0], q[1], q[2], 1.0)

    for sg in (+1, -1):
        spline([(0.0, 0.0, z0), (sg * 0.11, 0.0, z0 - 0.11 * TAN12), (sg * 0.215, 0.0, z0 - 0.215 * TAN12)])
    rh = 0.0175
    pts = [(0.0, 0.0, z0), (0.0, 0.0, ALTEZZA_GANCIO - rh)]
    for k in range(0, 21):
        a = math.radians(-90 + 280.0 * k / 20)
        pts.append((0.0, rh * math.cos(a), ALTEZZA_GANCIO + rh * math.sin(a)))
    spline(pts)
    ob = bpy.data.objects.new(nome, cu)
    _collezione(coll).objects.link(ob)
    ob.data.materials.append(_materiale_semplice("M_Gruccia", "#3a3b3d", 0.45, 0.2))
    return ob


def costruisci(nome, nome_giocatore, numero, colore, dettagli, colore_scritte,
               coll=None, con_scudo=True):
    """Maglia completa con gruccia, scritte e scudo. Ritorna un oggetto Maglia."""
    m = Maglia()
    m.shirt = mesh_maglia(nome, coll, colore, dettagli)
    m.gruccia = gruccia(nome.replace("Maglia", "Gruccia"), coll)
    m.gruccia.parent = m.shirt
    m.figli = scritte(m.shirt, nome_giocatore, numero, colore_scritte, coll)
    if con_scudo:
        m.figli.append(scudo(m.shirt, coll))
    m.figli += colletto(m.shirt, dettagli, coll=coll)
    m.figli += sponsor(m.shirt, coll)
    m.info = misure(m.shirt)
    return m


def duplica(base, nome, nome_giocatore, numero, colore_scritte, coll=None, materiale=None):
    """Copia collegata: stessa mesh della maglia (si carica una volta sola),
    scritte proprie. `materiale` (opzionale) sostituisce il tessuto della copia."""
    ob = bpy.data.objects.new(nome, base.data)
    _collezione(coll).objects.link(ob)
    for mod in base.modifiers:
        n = ob.modifiers.new(mod.name, mod.type)
        for k in ("levels", "render_levels", "boundary_smooth", "thickness", "offset", "use_rim",
                  "thickness_vertex_group", "vertex_group"):
            if hasattr(mod, k):
                setattr(n, k, getattr(mod, k))
    if materiale is not None:
        ob.material_slots[0].link = "OBJECT"
        ob.material_slots[0].material = materiale
    scritte(ob, nome_giocatore, numero, colore_scritte, coll)
    return ob


# ------------------------------------------------------------------ per il sito
def _immagine_trama(cartella):
    """Normal map di un jersey (maglie in fila di punti a V), ripetibile."""
    if "trama_jersey" in bpy.data.images:
        return bpy.data.images["trama_jersey"]
    n = 512
    U, V = np.meshgrid(np.arange(n) / n, np.arange(n) / n)
    col, riga = 24, 24
    cu, cv = U * col, V * riga
    fu = cu - np.floor(cu)
    h = np.sin(2 * math.pi * (cv + 0.9 * np.abs(fu - 0.5))) * 0.5 + 0.5
    h = h * (0.55 + 0.45 * np.cos(math.pi * (fu - 0.5)))
    gy, gx = np.gradient(h)
    k = 6.0
    nx, ny = -gx * k * 25, -gy * k * 25
    nz = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.stack([nx / ln, ny / ln, nz / ln], 2) * 0.5 + 0.5
    rgba = np.concatenate([rgb, np.ones((n, n, 1))], axis=2).astype(np.float32)
    img = bpy.data.images.new("trama_jersey", n, n, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(rgba[::-1].ravel())
    img.filepath_raw = os.path.join(cartella, "trama.png")
    img.file_format = "PNG"
    img.save()
    img.pack()
    return img


def prepara_web(shirt, colore, dettagli, cartella="."):
    """Versione leggera per glTF: niente modificatori (la mesh e' gia' fitta), colore a vertici
    con l'ombreggiatura cotta (valli delle pieghe, ascelle), materiale semplice, doppia faccia."""
    me = shirt.data
    for m in list(shirt.modifiers):
        shirt.modifiers.remove(m)
    shirt.vertex_groups.clear()
    ao = np.array([a.value for a in me.attributes["ao"].data])
    c0 = np.array(_hex(colore)[:3])
    col = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    for i in range(len(me.vertices)):
        c = c0 * (1.0 - float(ao[i]))
        col.data[i].color = (float(c[0]), float(c[1]), float(c[2]), 1.0)
    for nm in ("rib", "dseam", "dhem", "ao"):
        if nm in me.attributes:
            me.attributes.remove(me.attributes[nm])
    uvl = me.uv_layers.new(name="UVMap")
    for lp in me.loops:
        v = me.vertices[lp.vertex_index].co
        uvl.data[lp.index].uv = (v.x * 10.0, v.z * 10.0)       # una trama ogni 10 cm
    nm = "W_Maglia_" + colore.lstrip("#")
    m = bpy.data.materials.get(nm)
    if m is None:
        m = bpy.data.materials.new(nm)
        m.use_nodes = True
        nt = m.node_tree
        pb = nt.nodes["Principled BSDF"]
        ca = nt.nodes.new("ShaderNodeVertexColor")
        ca.layer_name = "Col"
        nt.links.new(ca.outputs["Color"], pb.inputs["Base Color"])
        it = nt.nodes.new("ShaderNodeTexImage")
        it.image = _immagine_trama(cartella)
        nm_ = nt.nodes.new("ShaderNodeNormalMap")
        nm_.inputs["Strength"].default_value = 0.09
        nt.links.new(it.outputs["Color"], nm_.inputs["Color"])
        nt.links.new(nm_.outputs["Normal"], pb.inputs["Normal"])
        pb.inputs["Roughness"].default_value = 0.5
        if "Sheen Weight" in pb.inputs:
            pb.inputs["Sheen Weight"].default_value = 0.4
        m.use_backface_culling = False
    me.materials.clear()
    me.materials.append(m)
    for c in shirt.children:
        for mod in list(c.modifiers):
            c.modifiers.remove(mod)


# ------------------------------------------------------------------ misure e controlli
def misure(shirt):
    me = shirt.data
    co = np.array([(v.co.x, v.co.y, v.co.z) for v in me.vertices])
    G = geom()
    info = {}
    info["altezza"] = float(co[:, 2].max() - co[:, 2].min())
    info["larghezza_spalle"] = 2 * SH_X
    info["larghezza_totale"] = float(co[:, 0].max() - co[:, 0].min())
    busto = co[(np.abs(co[:, 0]) < 0.20) & (co[:, 2] < -0.10) & (co[:, 2] > -0.60)]
    info["spessore_busto"] = float(busto[:, 1].max() - busto[:, 1].min())
    k = int(np.argmax(co[:, 0]))
    info["angolo_manica_gradi"] = math.degrees(math.atan2(SH_Z - co[k, 2], co[k, 0] - SH_X))
    sup = G.mezzo_spessore(busto[:, 0], busto[:, 2])
    info["ampiezza_pieghe_mm"] = float(np.std(np.abs(busto[:, 1]) - sup) * 1000)
    info["vertici"] = len(me.vertices)
    info["facce"] = len(me.polygons)
    mx = 0.0
    for lato in (+1, -1):
        o = G.outline[lato]
        pts = o["pts"]
        n = len(pts)
        ang = []
        for i in range(n):
            a = pts[i] - pts[i - 1]
            b = pts[(i + 1) % n] - pts[i]
            sg = a[0] * b[1] - a[1] * b[0]
            c = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
            ang.append(math.copysign(math.degrees(math.acos(max(-1.0, min(1.0, c)))), sg))
        for i in range(n):
            if o["corner"][i] or o["corner"][(i + 1) % n] or i < o["n_neck"]:
                continue                                   # angoli veri e scollo (apice del V)
            mx = max(mx, abs(ang[(i + 1) % n] - ang[i]))   # un dente = curvatura che salta
    info["dente_max_gradi"] = mx
    info["modificatori"] = [m.type for m in shirt.modifiers]
    return info


def verifica(info):
    """Lista di errori (vuota = tutto ok)."""
    err = []

    def ok(cond, msg):
        if not cond:
            err.append(msg)

    ok(0.70 <= info["altezza"] <= 0.80, "altezza %.3f fuori 0.70-0.80" % info["altezza"])
    ok(0.43 <= info["larghezza_spalle"] <= 0.48, "spalle %.3f" % info["larghezza_spalle"])
    ok(0.70 <= info["larghezza_totale"] <= 0.82, "larghezza totale %.3f" % info["larghezza_totale"])
    ok(0.04 <= info["spessore_busto"] <= 0.12, "spessore busto %.3f fuori 0.04-0.12" % info["spessore_busto"])
    ok(35.0 <= info["angolo_manica_gradi"] <= 50.0, "manica %.1f gradi" % info["angolo_manica_gradi"])
    ok(3.0 <= info["ampiezza_pieghe_mm"] <= 16.0, "pieghe %.1f mm" % info["ampiezza_pieghe_mm"])
    ok(info["dente_max_gradi"] <= 20.0, "dente %.1f gradi" % info["dente_max_gradi"])
    ok("CLOTH" not in info["modificatori"], "c'e' un Cloth: vietato")
    return err


# ------------------------------------------------------------------ prova
def _scena_prova():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = True
    sc.render.resolution_percentage = 100
    w = bpy.data.worlds.new("W")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.40, 0.40, 0.40, 1.0)
    bg.inputs[1].default_value = 1.0
    sc.world = w
    sc.view_settings.view_transform = "Standard"
    return sc


def _camera(sc, nome, loc, tgt, lens=50):
    cd = bpy.data.cameras.new(nome)
    cd.lens = lens
    co = bpy.data.objects.new(nome, cd)
    sc.collection.objects.link(co)
    co.location = loc
    d = Vector(tgt) - Vector(loc)
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return co


def _luce(sc, nome, tipo, loc, tgt, energia):
    ld = bpy.data.lights.new(nome, tipo)
    ld.energy = energia
    lo = bpy.data.objects.new(nome, ld)
    sc.collection.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return lo


def prova(cartella, colore="#ffffff", dettagli="#173f9a", px=800, campioni=32):
    cartella = os.path.abspath(cartella)
    os.makedirs(cartella, exist_ok=True)
    sc = _scena_prova()
    m = costruisci("Maglia_10", "GIOCATORE 10", 10, colore, dettagli, dettagli)
    for nm, loc, en, sz in (("Chiave", (-1.9, 1.7, 0.9), 80.0, 1.2),
                            ("Chiave_dietro", (1.9, -1.7, 0.9), 80.0, 1.2),
                            ("Riempimento", (1.6, 1.8, 0.1), 18.0, 3.0),
                            ("Riempimento_dietro", (-1.6, -1.8, 0.1), 18.0, 3.0)):
        lo = _luce(sc, nm, "AREA", loc, (0, 0, -0.35), en)
        lo.data.size = sz
    sc.render.resolution_x = px
    sc.render.resolution_y = px
    sc.cycles.samples = campioni
    viste = {
        "fronte": ((0.0, 2.2, -0.36), (0, 0, -0.36)),
        "retro": ((0.0, -2.2, -0.36), (0, 0, -0.36)),
        "lato": ((2.2, 0.0, -0.36), (0, 0, -0.36)),
        "tre_quarti": ((1.1, 1.9, -0.30), (0, 0, -0.36)),
    }
    for nome, (loc, tgt) in viste.items():
        cam = _camera(sc, "Cam_" + nome, loc, tgt, lens=62)
        sc.camera = cam
        sc.render.filepath = os.path.join(cartella, "maglia_%s.png" % nome)
        bpy.ops.render.render(write_still=True)
    return m


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if argv and argv[0] == "prova":
        cartella = argv[1] if len(argv) > 1 else os.path.join(os.getcwd(), "prova_maglia")
        pxl = int(argv[2]) if len(argv) > 2 else 800
        camp = int(argv[3]) if len(argv) > 3 else 32
        mm = prova(cartella, px=pxl, campioni=camp)
        for k, v in mm.info.items():
            print("MAGLIA_MISURA", k, v)
        errori = verifica(mm.info)
        for e in errori:
            print("MAGLIA_ERRORE", e)
        if errori:
            sys.exit(1)
        print("MAGLIA_OK")
