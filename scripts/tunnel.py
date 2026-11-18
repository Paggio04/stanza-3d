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
ST_MURETTO = 2.2                          # parete verticale fra un anello e il successivo (vomitori)
ST_TETTO_SPESSORE = 1.8                   # il tetto e' una lastra fra Z-0.3 e Z+1.5
# ---- sole unico (stessa direzione nel cielo di Blender e nella luce cotta): locale (x, u, z)
SOLE_EL = math.radians(46.0)              # altezza sull'orizzonte
SOLE_ORIZZ = (0.6, 0.8)                   # direzione orizzontale (x, u) verso il sole: da +x e +u (alle spalle della camera di partenza)
SOLE = np.array([math.cos(SOLE_EL) * SOLE_ORIZZ[0], math.cos(SOLE_EL) * SOLE_ORIZZ[1], math.sin(SOLE_EL)])


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


def _rumore(rng, n, m, scala):
    """Rumore a blocchi interpolato (n x m), valori 0..1, con celle di `scala` pixel."""
    g = rng.random((n // scala + 2, m // scala + 2))
    yy = np.arange(n) / scala
    xx = np.arange(m) / scala
    y0, x0 = yy.astype(int), xx.astype(int)
    fy, fx = (yy - y0)[:, None], (xx - x0)[None, :]
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy


def tex_erba(cartella, n=1024):
    """Tile 8 x 8 m: strisce di taglio (2 da 4 m, una piu' chiara), fili d'erba come tratti verticali sottili,
    macchie larghe di colore. Il dettaglio fine in piu' lo aggiunge lo shader del sito."""
    rng = np.random.default_rng(3)
    V = np.arange(n)[:, None] / n
    fascia = (np.floor(V * 2.0) % 2)
    a, b = _lin("#2e7a27"), _lin("#4a9a38")
    base = a[None, None, :] * (1 - fascia[..., None]) + b[None, None, :] * fascia[..., None]
    base = np.broadcast_to(base, (n, n, 3)).copy()
    larga = 0.88 + 0.24 * (_rumore(rng, n, n, 128) * 0.6 + _rumore(rng, n, n, 48) * 0.4)    # macchie larghe
    medio = 0.90 + 0.20 * _rumore(rng, n, n, 8)
    fili = 0.84 + 0.30 * rng.random((n, n))                                                  # fili: un pixel ~ 0,8 cm
    fili = fili * (0.92 + 0.16 * _rumore(rng, n, n, 3))
    # il filo e' un po' verticale: stira il rumore lungo v
    stira = np.roll(fili, 1, axis=0) * 0.5 + fili * 0.5
    t = base * (larga * medio * stira)[..., None]
    t[..., 1] *= 1.02
    return _img("erba", np.clip(t, 0, 1), cartella)


def _seggiolino(cell):
    """Maschera di luminosita' di un seggiolino (cell x cell): fessura d'ombra, schienale, seduta, bordi."""
    c = cell
    riga = np.ones(c)
    k = c / 16.0
    for y in range(c):
        v = y / k
        if v < 1.5:
            riga[y] = 0.40 + 0.10 * v                # ombra della fila davanti
        elif v < 3.0:
            riga[y] = 1.16                           # bordo alto illuminato dello schienale
        elif v < 8.5:
            riga[y] = 1.04 - 0.12 * (v - 3.0) / 5.5  # schienale
        elif v < 10.0:
            riga[y] = 0.50                           # fessura fra schienale e seduta
        elif v < 11.0:
            riga[y] = 1.00                           # bordo anteriore seduta
        elif v < 15.0:
            riga[y] = 0.88 - 0.06 * (v - 11.0) / 4.0
        else:
            riga[y] = 0.52
    col = np.ones(c)
    for x in range(c):
        v = x / k
        col[x] = 0.50 if (v < 1.0 or v >= 15.0) else (0.84 if (v < 2.0 or v >= 14.0) else 1.0)
    return np.outer(riga, col)


def tex_spalti(cartella, blu="#1d3f96", rosso="#3a6fd0", nome="", w_=1536, h_=768, nomefile="spalti"):
    """Spalti: 128 x 64 seggiolini (cella = w_/128 px). Ogni seggiolino ha schienale, seduta, fessure e ombra per fila.
    Fasce blu / azzurro / blu con diagonali di cemento, corridoi a gradini fra gli spicchi e, sull'azzurro,
    una banda bianca col nome in mosaico. Si ripete 6 volte attorno alla ciotola."""
    rng = np.random.default_rng(5)
    cell = w_ // 128
    C, Rr = 128, h_ // cell
    b, r, bianco = _lin(blu), _lin(rosso), _lin("#e9edf3")
    scuro = b * 0.50
    grid = np.zeros((Rr, C, 3))
    kind = np.zeros((Rr, C), int)                           # 0 seggiolino, 1 gradino, 2 diagonale di cemento
    for rr in range(Rr):
        base = b if (rr < 22 or rr >= 42) else r
        for c in range(C):
            col = base * (0.88 + 0.12 * rng.random())
            x = rng.random()
            if x < 0.04:
                col = bianco * 0.92
            elif x < 0.07:
                col = base * 0.70
            if c % 16 == 0:
                kind[rr, c] = 1
            grid[rr, c] = col
    for rr in (21, 41, 0):
        kind[rr, :] = 2
    for rr in range(27, 36):                                  # banda bianca col nome
        grid[rr, :] = bianco * (0.94 + 0.06 * rng.random((C, 1)))
        kind[rr, [c for c in range(C) if c % 16 == 0]] = 1
    testo = (nome or "").upper()
    start = (C - 6 * len(testo)) // 2
    for i, ch in enumerate(testo):
        if ch == " ":
            continue
        gl = _lettera(ch)
        for ly in range(7):
            for lx in range(5):
                if gl[ly][lx]:
                    grid[28 + ly, start + 6 * i + lx] = scuro
    seg = _seggiolino(cell)
    img = np.zeros((h_, w_, 3))
    conc = _lin("#a9acb3")
    for rr in range(Rr):
        for c in range(C):
            ys, xs = slice(rr * cell, (rr + 1) * cell), slice(c * cell, (c + 1) * cell)
            k = kind[rr, c]
            if k == 0:
                img[ys, xs] = grid[rr, c][None, None, :] * seg[..., None]
            elif k == 1:                                       # gradino del corridoio: pedata chiara + alzata scura
                y = np.arange(cell)[:, None] / cell
                sh = np.where(y < 0.35, 0.62, np.where(y < 0.5, 0.95, 1.05))
                img[ys, xs] = conc[None, None, :] * 0.70 * sh[..., None] * np.ones((1, cell, 1))
            else:                                              # diagonale di cemento
                y = np.arange(cell)[:, None] / cell
                sh = np.where(y < 0.12, 0.55, 0.92 + 0.10 * (y > 0.8))
                img[ys, xs] = conc[None, None, :] * 0.85 * sh[..., None] * np.ones((1, cell, 1))
    return _img(nomefile, np.clip(img, 0, 1), cartella)


def tex_cartelloni(cartella, blu="#1d3f96", w_=2048, h_=128, nomefile="cartelloni"):
    """Cartelloni LED (16 m di fascia per tile): pannelli saturi con loghi a blocchi, griglia di pixel LED."""
    rng = np.random.default_rng(9)
    img = np.zeros((h_, w_, 3)) + _lin("#070a18")
    x = 0
    pal = [_lin(c) for c in (blu, "#f3f6fb", "#f2c30f", "#d93232", "#1f9d5c", "#f3f6fb", "#2d6bd6", "#e8571c")]
    while x < w_:
        bw = int(rng.integers(150, 300))
        col = pal[rng.integers(len(pal))]
        fondo = pal[rng.integers(len(pal))]
        sub = np.zeros((h_ - 20, max(1, min(w_, x + bw - 10) - (x + 10)), 3)) + col * 0.92
        yy = np.linspace(0, 1, sub.shape[0])[:, None, None]
        sub = sub * (0.86 + 0.14 * (1 - yy))
        # logo: un blocco di colore opposto + due righe di testo a blocchi
        lw = max(8, sub.shape[1] // 3)
        sub[8:-8, 10:10 + lw] = np.clip(fondo * 0.95, 0, 1)
        for k in range(int(rng.integers(2, 4))):
            tw = int(rng.integers(20, max(21, sub.shape[1] - lw - 40)))
            ty = 18 + k * 30
            if ty + 14 < sub.shape[0]:
                sub[ty:ty + 14, 22 + lw:22 + lw + tw] = np.clip(fondo * 0.95 + 0.04, 0, 1)
        img[10:h_ - 10, x + 10:x + 10 + sub.shape[1]] = sub
        x += bw
    yy, xx = np.mgrid[0:h_, 0:w_]
    led = np.where(((yy % 4) == 3) | ((xx % 4) == 3), 0.55, 1.0)         # pixel LED
    img = img * led[..., None]
    return _img(nomefile, np.clip(img, 0, 1), cartella)


def tex_cemento(cartella, n=256):
    """Cemento dei corridoi: grana, macchie e giunti ogni 2 m (tile 4 x 4 m)."""
    rng = np.random.default_rng(11)
    g = 0.86 + 0.14 * rng.random((n, n)) * 0.7 + 0.10 * _rumore(rng, n, n, 32)
    g[:, :2] *= 0.7
    g[:2, :] *= 0.7
    g[:, n // 2:n // 2 + 2] *= 0.75
    g[n // 2:n // 2 + 2, :] *= 0.75
    rgb = _lin("#b5b8bf")[None, None, :] * g[..., None]
    return _img("cemento", np.clip(rgb, 0, 1), cartella)


def tex_muro(cartella, scuro="#0f1a3d", w_=1024, h_=128):
    """Parete fra gli anelli (tile = 2 spicchi, 14,6 m, alta 2,2 m): pannelli di cemento con un vomitorio scuro al centro."""
    rng = np.random.default_rng(17)
    g = 0.80 + 0.14 * rng.random((h_, w_)) + 0.10 * _rumore(rng, h_, w_, 16)
    rgb = _lin("#9a9ea8")[None, None, :] * g[..., None]
    for x in range(0, w_, w_ // 4):                              # giunti dei pannelli
        rgb[:, x:x + 2] *= 0.6
    rgb[:6] *= 0.7                                               # cordolo in alto
    # vomitorio: 3 m su 7,3 -> 210 px; alto 1,5 m su 2,2 -> 87 px; da terra
    x0, x1 = (w_ - 210) // 2, (w_ + 210) // 2
    y1 = h_
    y0 = int(h_ * (1 - 1.55 / 2.2))
    yy = np.linspace(0, 1, y1 - y0)[:, None, None]
    buio = _lin("#06080f")[None, None, :] * (0.7 + 0.6 * yy)
    rgb[y0:y1, x0:x1] = buio
    rgb[y0 - 4:y0, x0 - 4:x1 + 4] *= 0.55                        # architrave
    return _img("muro", np.clip(rgb, 0, 1), cartella)


def tex_facciata(cartella, w_=1024, h_=256):
    """Facciata sopra l'ultimo anello (tile = 1 spicchio, 7,3 m, alta ~3,8 m): montanti di cemento e due fasce di
    finestre a nastro scure."""
    rng = np.random.default_rng(19)
    g = 0.78 + 0.16 * rng.random((h_, w_)) + 0.08 * _rumore(rng, h_, w_, 16)
    rgb = _lin("#a3a7b0")[None, None, :] * g[..., None]
    for (ya, yb) in ((0.12, 0.34), (0.50, 0.72)):
        y0, y1 = int(h_ * ya), int(h_ * yb)
        vetro = _lin("#1a2230")[None, None, :] * (0.8 + 0.4 * np.linspace(0, 1, y1 - y0)[:, None, None])
        rgb[y0:y1] = vetro
        for x in range(0, w_, w_ // 8):
            rgb[y0:y1, x:x + 4] = _lin("#8b8f99")                # montanti
        rgb[y0 - 3:y0] *= 0.6
    rgb[-14:] *= 0.65
    return _img("facciata", np.clip(rgb, 0, 1), cartella)


def tex_tetto(cartella, w_=256, h_=512):
    """Intradosso del tetto (tile = 1 spicchio di 64, 7,5 m; v = 20 m di raggio): membrana grigio chiaro con travi
    radiali bianche ai bordi dello spicchio e correnti circolari a 1/3 e 2/3."""
    rng = np.random.default_rng(23)
    g = 0.86 + 0.08 * rng.random((h_, w_)) + 0.06 * _rumore(rng, h_, w_, 16)
    rgb = _lin("#c9ced8")[None, None, :] * g[..., None]
    rgb[:, :6] = _lin("#f3f5f9")
    rgb[:, -6:] = _lin("#f3f5f9")
    rgb[:, 6:9] *= 0.55                                          # ombra della trave
    rgb[:, -9:-6] *= 0.55
    for y in (0, h_ // 3, 2 * h_ // 3, h_ - 8):
        rgb[y:y + 6] = _lin("#e9edf4")
        rgb[y + 6:y + 9] *= 0.6
    for x in range(0, w_, w_ // 4):                              # cuciture della membrana
        rgb[:, x:x + 1] *= 0.82
    return _img("tetto", np.clip(rgb, 0, 1), cartella)


def tex_schermo(cartella, nome, blu="#1d3f96", w_=1024, h_=640):
    """Maxischermo (un tile = tutto lo schermo): fondo blu a gradiente, nome a blocchi, fascia bassa, pixel LED."""
    rng = np.random.default_rng(29)
    yy, xx = np.mgrid[0:h_, 0:w_]
    b = _lin(blu)
    rgb = b[None, None, :] * (0.55 + 0.7 * (1 - yy / h_))[..., None]
    rgb = np.clip(rgb + 0.04 * rng.random((h_, w_, 1)), 0, 1)
    testo = (nome or "").upper()
    px = 10
    ln = 6 * len(testo) * px
    x0 = (w_ - ln) // 2
    y0 = h_ // 2 - 4 * px
    for i, ch in enumerate(testo):
        if ch == " ":
            continue
        gl = _lettera(ch)
        for ly in range(7):
            for lx in range(5):
                if gl[ly][lx]:
                    rgb[y0 + ly * px:y0 + (ly + 1) * px - 1, x0 + (6 * i + lx) * px:x0 + (6 * i + lx + 1) * px - 1] = _lin("#f4f7fb")
    rgb[int(h_ * 0.86):, :] = _lin("#f2c30f") * 0.9
    led = np.where(((yy % 4) == 3) | ((xx % 4) == 3), 0.6, 1.0)
    rgb = rgb * led[..., None]
    rgb[:12] = 0.03
    rgb[-12:] = 0.03
    rgb[:, :12] = 0.03
    rgb[:, -12:] = 0.03
    return _img("schermo", np.clip(rgb, 0, 1), cartella)


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


GAIN_ESTERNO = 1.35                       # la luce cotta esterna e' divisa per questo; lo stesso fattore la ripristina nel sito
SOLE_COL = np.array([1.0, 0.93, 0.80]) * 1.45
AMB_CIELO = np.array([0.34, 0.42, 0.60])
AMB_TERRA = np.array([0.20, 0.19, 0.17])
SOTTO_TETTO = np.array([0.62, 0.62, 0.60])   # intradosso del tetto: luce di rimbalzo da campo e spalti


def ciotola_livelli():
    """Anelli della ciotola: dict con la tribuna (r0,z0 -> r1,z1), il corridoio (-> pr1,pz1) e la parete che sale al
    livello successivo (fino a zmuro). L'ultima parete e' la facciata che chiude gli spalti sotto il tetto."""
    out = []
    r, z = ST_RAGGIO, ST_ALTEZZA0
    for i, (prof, alz) in enumerate(ST_ANELLI):
        t = {"r0": r, "z0": z, "r1": r + prof, "z1": z + alz, "pr1": r + prof + 1.2, "pz1": z + alz + 0.4}
        if i == len(ST_ANELLI) - 1:
            t["zmuro"] = ST_TETTO_Z - 0.3 + 0.3 * (t["pr1"] - ST_TETTO_R0) / (ST_TETTO_R1 - ST_TETTO_R0)
        else:
            t["zmuro"] = t["pz1"] + ST_MURETTO
        out.append(t)
        r, z = t["pr1"], t["zmuro"]
    return out


def _profilo():
    """Quota del terreno/spalti in funzione del raggio dal centro della ciotola (per le ombre)."""
    rr, zz = [0.0, ST_RAGGIO - 0.05, ST_RAGGIO - 0.049], [0.0, 0.0, ST_ALTEZZA0]
    for t in ciotola_livelli():
        rr += [t["r0"], t["r1"], t["pr1"], t["pr1"] + 1e-3]
        zz += [t["z0"], t["z1"], t["pz1"], t["zmuro"]]
    rr += [rr[-1] + 1e-3, 500.0]
    zz += [ST_TETTO_Z, ST_TETTO_Z]                     # oltre la facciata: edificio pieno fino al tetto
    return np.array(rr), np.array(zz)


_PROF = None


def _bloccato(P, D, passo=0.7, tmax=170.0):
    """P (N,3) punti, D (N,3) direzioni (locale x,u,z; z come la ciotola, senza ST_QUOTA). True = il raggio verso D
    incontra spalti o tetto."""
    global _PROF
    if _PROF is None:
        _PROF = _profilo()
    D = np.broadcast_to(D, P.shape)
    hit = np.zeros(len(P), bool)
    for t in np.arange(0.35, tmax, passo):
        Q = P + D * t
        r = np.hypot(Q[:, 0], Q[:, 1] - ST_CENTRO_U)
        zb = np.interp(r, _PROF[0], _PROF[1], right=ST_TETTO_Z)
        hit |= Q[:, 2] < zb - 0.02
    dz = D[:, 2]
    ok = dz > 0.02
    tm = np.where(ok, (ST_TETTO_Z + 0.6 - P[:, 2]) / np.where(ok, dz, 1.0), 0.0)
    Q = P + D * tm[:, None]
    r = np.hypot(Q[:, 0], Q[:, 1] - ST_CENTRO_U)
    hit |= ok & (tm > 0) & (P[:, 2] < ST_TETTO_Z - 0.3) & (r >= ST_TETTO_R0) & (r <= ST_TETTO_R1)
    return hit


def luce_esterna(P, N):
    """Luce cotta del sole + cielo per N punti P (locale, z della ciotola) con normali N (locale).
    Sole unico con ombra di spalti e tetto; cielo = emisfero (blu) occluso dal tetto e dagli spalti; terra = rimbalzo.
    Ritorna colori RGB (N,3) divisi per GAIN_ESTERNO (il sito li moltiplica di nuovo)."""
    P = np.asarray(P, float)
    N = np.asarray(N, float)
    nl = np.einsum("ij,j->i", N, SOLE)
    vis = ~_bloccato(P + N * 0.06, SOLE)
    sole = SOLE_COL[None, :] * (np.clip(nl, 0, None) * vis)[:, None]
    # occlusione ambiente: 8 raggi sull'emisfero della normale
    t1 = np.cross(N, np.array([0.0, 0.0, 1.0]))
    deg = np.linalg.norm(t1, axis=1) < 1e-3
    t1[deg] = np.cross(N[deg], np.array([1.0, 0.0, 0.0]))
    t1 /= np.linalg.norm(t1, axis=1)[:, None]
    t2 = np.cross(N, t1)
    liberi = 0.0
    for th in (math.radians(28), math.radians(62)):
        for ph in (0.4, 0.4 + math.pi / 2, 0.4 + math.pi, 0.4 + 3 * math.pi / 2):
            d = N * math.cos(th) + (t1 * math.cos(ph) + t2 * math.sin(ph)) * math.sin(th)
            liberi = liberi + (~_bloccato(P + N * 0.06, d, passo=1.2, tmax=150.0)) * (math.cos(th) / 4.0)
    ao = liberi / (math.cos(math.radians(28)) * 1.0 + math.cos(math.radians(62)) * 1.0)
    nz = N[:, 2]
    amb = (AMB_CIELO[None, :] * (0.5 + 0.5 * nz)[:, None] * ao[:, None]
           + AMB_TERRA[None, :] * (0.5 - 0.5 * nz)[:, None])
    return np.clip((sole + amb) / GAIN_ESTERNO, 0.0, 1.0)


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
            cols = np.ones((len(d["v"]), 3))
            ext = [i for i, md in enumerate(d["modo"]) if md == "ext"]
            if ext:
                V = np.array([d["v"][i] for i in ext], float)
                Nw = np.array([d["n"][i] for i in ext], float)
                Pl = np.stack([V[:, 0], -V[:, 1] - T0, V[:, 2] - (0.0 if zoff else ST_QUOTA)], axis=1)   # frame della ciotola (senza ST_QUOTA)
                Nl = np.stack([Nw[:, 0], -Nw[:, 1], Nw[:, 2]], axis=1)
                cols[ext] = luce_esterna(Pl, Nl)
            for i, md in enumerate(d["modo"]):
                if md == "int":
                    cols[i] = luce_interna(d["v"][i], d["n"][i])
                elif md == "sotto":
                    cols[i] = SOTTO_TETTO / GAIN_ESTERNO
            for i, c in enumerate(cols):
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


# ------------------------------------------------------------------ anelli della ciotola
def _anello_ciotola(R, m, r0, z0, r1, z1, n, uvscala=0.12, modo="ext", salta=None, doppia=False, uvm=None, sub=(1, 1), uvk=None):
    """Anello di spalti (ciotola): n spicchi, normale verso il campo, ognuno suddiviso in sub = (nu, nv) per la luce cotta.
    salta(a_medio) = True per saltare lo spicchio (varco tunnel). doppia = facce da entrambi i lati.
    uvm = (metri per ripetizione in u, quota di riferimento, metri per ripetizione in v): UV continue
    lungo l'anello. uvk = (spicchi per ripetizione in u, metri per ripetizione in v): v dalla lunghezza reale del lato.
    Trapezio vero (4 angoli), non parallelogramma (buchi a spicchio)."""
    nu, nv = sub
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
        e1, e2 = P[1] - P[0], P[3] - P[0]
        nrm = np.cross(e1, e2)            # normale = verso della faccia (mondo Blender: y specchiata rispetto al locale)
        nrm = nrm / (np.linalg.norm(nrm) + 1e-9)
        lseg = float(np.linalg.norm(e1))
        for lato in ((1, 2) if doppia else (1,)):
            base = len(d["v"])
            sg = 1.0 if lato == 1 else -1.0
            for j in range(nv + 1):
                for i in range(nu + 1):
                    s_, t_ = i / nu, j / nv
                    d["v"].append((P[0] * (1 - s_) + P[1] * s_) * (1 - t_) + (P[3] * (1 - s_) + P[2] * s_) * t_)
                    d["n"].append(nrm * sg)
                    if uvk is not None:
                        d["uv"].append(((k + s_) / uvk[0], t_ * float(np.linalg.norm(e2)) / uvk[1]))
                    elif uvm is None:
                        d["uv"].append(((k + s_) * uvscala, (z0 + (z1 - z0) * t_) * uvscala))
                    else:
                        d["uv"].append(((k + s_) * lseg / uvm[0], (z0 + (z1 - z0) * t_ - uvm[1]) / uvm[2]))
                    d["modo"].append(modo)
            for j in range(nv):
                for i in range(nu):
                    a = base + j * (nu + 1) + i
                    b_ = a + 1
                    c = b_ + (nu + 1)
                    dd = a + (nu + 1)
                    d["f"].append((a, b_, c, dd) if lato == 1 else (a, dd, c, b_))


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
    """Stadio: campo con righe, muro di base con cartelloni LED, ciotola a 3 anelli (corridoi, vomitori, facciata),
    tetto con travi, maxischermi, facciata attorno alla bocca del tunnel. Luce cotta: sole unico + cielo."""
    blu = dati["colori"]["dettagli"]
    m_erba = mat("Esterno_Erba", "#ffffff", erba_i, 0.95)
    m_linea = mat("Esterno_Linea", "#f4f4f4", None, 0.8)
    m_spalti = mat("Esterno_Spalti", "#ffffff", spalti_i, 0.85)
    m_cart = mat("Esterno_Cartelloni", "#ffffff", cart_i, 0.6)
    m_cem = mat("Esterno_Cemento", "#ffffff", tex_cemento(cartella), 0.9)
    m_vomi = mat("Esterno_Muro", "#ffffff", tex_muro(cartella), 0.9)
    m_faccia = mat("Esterno_Facciata", "#ffffff", tex_facciata(cartella), 0.9)
    m_basso = mat("Esterno_MuroBase", _scuro_hex(blu, 0.62), None, 0.8)
    m_tetto = mat("Esterno_Tetto", "#e6e9ef", None, 0.6)
    m_tetto_s = mat("Esterno_TettoSotto", "#ffffff", tex_tetto(cartella), 0.8)
    m_fascia = mat("Esterno_TettoFascia", "#eef1f6", None, 0.6)
    m_nastro = mat("Esterno_TettoLed", "#cfe6ff", None, 0.5)
    m_schermo = mat("Esterno_Schermo", "#ffffff", tex_schermo(cartella, dati["nome"], blu=blu), 0.4)
    m_telaio = mat("Esterno_Telaio", "#1a1d24", None, 0.6)
    m_fac = mat("Tunnel_Facciata", _scuro_hex(blu, 0.62), None, 0.8)
    m_testo = mat("Esterno_Testo", "#ffffff", None, 0.6)
    hw = W / 2
    uc = ST_CENTRO_U
    R_ = ST_RAGGIO
    # ---- campo: erba su tutto il disco della ciotola (celle di 2,5 m per l'ombra degli spalti)
    R.parete(m_erba, -R_, R_, L, uc + R_, 0.0, 0.0, (0, 0, 1), mx=2.5, modo="ext", uvs=(8.0, 8.0), uv0=(0.0, 0.0))
    cx, cl = 27.0, 36.0                                      # semi-larghezza e semi-lunghezza del campo
    LM = 2.5
    for (xa, xb, ua, ub) in ((-cx, cx, uc - cl, uc - cl + 0.15), (-cx, cx, uc + cl - 0.15, uc + cl),
                             (-cx, -cx + 0.15, uc - cl, uc + cl), (cx - 0.15, cx, uc - cl, uc + cl),
                             (-cx, cx, uc - 0.075, uc + 0.075)):
        R.parete(m_linea, xa, xb, ua, ub, 0.004, 0.004, (0, 0, 1), mx=LM, modo="ext")
    # aree di rigore e di porta, cerchio di centrocampo, porte
    for sgn in (-1, 1):
        ug = uc + sgn * cl                                   # linea di porta
        for (hx, prof) in ((20.0, 16.0), (9.0, 5.5)):
            ue = ug - sgn * prof
            ua, ub = min(ug, ue), max(ug, ue)
            R.parete(m_linea, -hx, hx, ue - 0.075, ue + 0.075, 0.004, 0.004, (0, 0, 1), mx=LM, modo="ext")
            for xx in (-hx, hx):
                R.parete(m_linea, xx - 0.075, xx + 0.075, ua, ub, 0.004, 0.004, (0, 0, 1), mx=LM, modo="ext")
        for xx in (-3.66, 3.66):                             # pali e traversa (7,32 x 2,44 m)
            R.scatola(m_linea, (xx, ug, 1.22), (0.12, 0.12, 2.44), modo="ext")
        R.scatola(m_linea, (0.0, ug, 2.44), (7.44, 0.12, 0.12), modo="ext")
    for q in range(48):
        a0, a1 = 2 * math.pi * q / 48, 2 * math.pi * (q + 1) / 48
        ri, re = 9.0, 9.15
        R.quad(m_linea, (ri * math.cos(a0), uc + ri * math.sin(a0), 0.004), (ri * math.cos(a1), uc + ri * math.sin(a1), 0.004),
               (re * math.cos(a1), uc + re * math.sin(a1), 0.004), (re * math.cos(a0), uc + re * math.sin(a0), 0.004),
               (0, 0, 1), modo="ext")
    # ---- muro di base (cartelloni LED in basso, blu notte sopra) con il varco del tunnel: arriva alla quota del primo anello
    ang_tunnel = -math.pi / 2                                # il tunnel e' dalla parte di u piccolo
    def varco(a):
        d = (a - ang_tunnel + math.pi) % (2 * math.pi) - math.pi
        return abs(d) < 0.056                                # 4 spicchi di 192: circa 6,5 m
    _anello_ciotola(R, m_cart, R_ - 0.05, 0.0, R_ - 0.05, 1.0, 192, modo="piena", salta=varco, uvm=(16.0, 0.0, 1.0))
    _anello_ciotola(R, m_basso, R_ - 0.05, 1.0, R_ - 0.05, ST_ALTEZZA0, 192, modo="ext", salta=varco, sub=(1, 2))
    # ---- facciata attorno alla bocca (u = L): chiude il varco, la bocca resta aperta (z da 0,9 a H)
    zb, zt = ST_QUOTA, ST_ALTEZZA0 + ST_QUOTA          # facciata alta come il muro di base
    R.parete(m_fac, -3.5, -hw, L, L, zb, zt, (0, 1, 0), mx=1.0, modo="ext")
    R.parete(m_fac, hw, 3.5, L, L, zb, zt, (0, 1, 0), mx=1.0, modo="ext")
    R.parete(m_fac, -hw, hw, L, L, H, zt, (0, 1, 0), mx=1.0, modo="ext")
    # ---- ciotola: 3 anelli con corridoio (cemento) e parete con vomitori; l'ultima parete e' la facciata sotto il tetto
    livelli = ciotola_livelli()
    for i, t in enumerate(livelli):
        lseg = 2 * math.pi * ((t["r0"] + t["r1"]) / 2) / 48
        lung = math.hypot(t["r1"] - t["r0"], t["z1"] - t["z0"])
        _anello_ciotola(R, m_spalti, t["r0"], t["z0"], t["r1"], t["z1"], 48, modo="ext",
                        uvm=(8 * lseg, ST_ALTEZZA0, 24.0), sub=(6, max(2, int(lung))))
        _anello_ciotola(R, m_cem, t["r1"], t["z1"], t["pr1"], t["pz1"], 48, modo="ext", uvk=(4.0, 1.2), sub=(6, 1))
        if i < len(livelli) - 1:
            _anello_ciotola(R, m_vomi, t["pr1"], t["pz1"], t["pr1"], t["zmuro"], 48, modo="ext", uvk=(2.0, ST_MURETTO), sub=(6, 2))
        else:
            _anello_ciotola(R, m_faccia, t["pr1"], t["pz1"], t["pr1"], t["zmuro"], 48, modo="ext", uvk=(2.0, t["zmuro"] - t["pz1"]), sub=(6, 4))
    # ---- tetto ad anello: estradosso bianco, intradosso con travi radiali, fascia interna con nastro LED
    _anello_ciotola(R, m_tetto, ST_TETTO_R0, ST_TETTO_Z, ST_TETTO_R1, ST_TETTO_Z + 1.5, 64, modo="ext", sub=(2, 2))
    _anello_ciotola(R, m_tetto_s, ST_TETTO_R0, ST_TETTO_Z - 0.3, ST_TETTO_R1, ST_TETTO_Z, 64, modo="sotto", uvk=(1.0, 20.0))
    _anello_ciotola(R, m_fascia, ST_TETTO_R0, ST_TETTO_Z - 0.3, ST_TETTO_R0, ST_TETTO_Z + 1.5, 64, modo="ext", sub=(2, 1))
    _anello_ciotola(R, m_nastro, ST_TETTO_R0 - 0.03, ST_TETTO_Z + 0.2, ST_TETTO_R0 - 0.03, ST_TETTO_Z + 0.55, 64, modo="piena")
    # ---- 4 maxischermi appesi al tetto: ai lati e in fondo, mai sopra la camera di ingresso
    for (sx, su, dim, sp) in ((-60.0, uc, (0.6, 10.0, 6.0), (0.5, 10.4, 6.4)), (60.0, uc, (0.6, 10.0, 6.0), (0.5, 10.4, 6.4)),
                              (-22.0, uc + 58.0, (10.0, 0.6, 6.0), (10.4, 0.5, 6.4)), (22.0, uc + 58.0, (10.0, 0.6, 6.0), (10.4, 0.5, 6.4))):
        R.scatola(m_telaio, (sx, su, 26.0), sp, modo="ext")
        R.scatola(m_schermo, (sx, su, 26.0), dim, modo="piena", uvs=(10.0, 6.0))
        for dd in (-3.0, 3.0):                                       # tiranti
            R.scatola(m_telaio, (sx + (dd if dim[0] > 1 else 0.0), su + (dd if dim[1] > 1 else 0.0), 31.5), (0.12, 0.12, 5.0), modo="ext")
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
        export_image_format="JPEG", export_image_quality=90,
        export_meshopt_compression_enable=True)
    man = {"u0": T0, "larghezza": W, "altezza": H, "lunghezza": L,
           "bocca": {"z": T0 + L}, "percorso": percorso(),
           "passo": 1.1, "ampiezza_bob": 0.012, "gain_esterno": GAIN_ESTERNO,
           "sole": [float(SOLE[0]), float(SOLE[2]), float(SOLE[1] + 0.0)]}
    json.dump(man, open(os.path.join(out, "tunnel.json"), "w", encoding="utf-8"), indent=1)
    print("TUNNEL_OK", glb, os.path.getsize(glb), "facce", tri)
    if err:
        sys.exit(1)
