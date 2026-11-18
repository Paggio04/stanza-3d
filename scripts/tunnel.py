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
SOLE_EL = math.radians(55.0)              # altezza sull'orizzonte
SOLE_ORIZZ = (0.9, -0.436)                # direzione orizzontale (x, u) verso il sole: da +x e un po' da -u (di lato, appena davanti alla camera di partenza)
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


_VESTITI = [_lin(c) for c in ("#e8ecf2", "#e8ecf2", "#e8ecf2", "#e8ecf2", "#e8ecf2", "#6fa4e6", "#6fa4e6", "#6fa4e6", "#14234f", "#14234f", "#1a1d24", "#1a1d24", "#7d838d", "#7d838d", "#9aa3b2", "#c8302f")]
_PELLI = [_lin(c) for c in ("#e0b293", "#c98f6b", "#a56a47", "#7a4a30", "#efc9a8")]


def _spettatore(cella, seg, cell, rng):
    """Sovrappone a un seggiolino un tifoso (testa + busto) nei colori della tifoseria; l'ombra di fila resta."""
    c = cell
    yy, xx = np.mgrid[0:c, 0:c]
    yy, xx = (yy + 0.5) / c, (xx + 0.5) / c
    busto = (xx > 0.17) & (xx < 0.83) & (yy > 0.45) & (yy < 0.93)
    busto |= (xx > 0.27) & (xx < 0.73) & (yy > 0.38) & (yy <= 0.45)          # collo/spalle
    testa = (xx - 0.5) ** 2 + (yy - 0.28) ** 2 < 0.17 ** 2
    capelli = testa & (yy < 0.26)
    vestito = _VESTITI[rng.integers(len(_VESTITI))] * (0.85 + 0.2 * rng.random())
    pelle = _PELLI[rng.integers(len(_PELLI))]
    capello = np.array([0.10, 0.08, 0.07]) if rng.random() < 0.6 else np.array([0.45, 0.33, 0.2])
    out = cella.copy()
    ombra = seg[:, c // 2][:, None] * 0.9 + 0.1                                # fessura/ombra della fila anche sul tifoso
    out[busto] = (vestito[None, :] * ombra.repeat(c, axis=1)[..., None][busto])
    out[testa] = (pelle[None, :] * ombra.repeat(c, axis=1)[..., None][testa])
    out[capelli] = (capello[None, :] * ombra.repeat(c, axis=1)[..., None][capelli])
    return out


def tex_spalti(cartella, blu="#1d3f96", rosso="#3a6fd0", nome="", w_=2048, h_=1024, nomefile="spalti"):
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
    con_nome = bool((nome or "").strip())
    if con_nome:                                              # banda bianca (righe 44-59: v=1 e' la riga 0, quindi il primo anello, v basso, sta in fondo all'immagine) con il nome su due righe
        for rr in range(44, 60):
            grid[rr, :] = bianco * (0.94 + 0.06 * rng.random((C, 1)))
            kind[rr, :] = 0                                       # nella banda niente corridoi: le lettere restano intere
        parole = (nome or "").upper().split()
        righe = [parole[0], " ".join(parole[1:])] if len(parole) > 1 else [parole[0]]
        for nr, testo in enumerate(righe):
            start = (C - 6 * len(testo) + 1) // 2
            y0 = 45 + nr * 8
            for i, ch in enumerate(testo):
                if ch == " ":
                    continue
                gl = _lettera(ch)
                for ly in range(7):
                    for lx in range(5):
                        if gl[ly][lx]:
                            grid[y0 + ly, start + 6 * i + lx] = scuro
                            kind[y0 + ly, start + 6 * i + lx] = 0     # la lettera vince sul gradino del corridoio
    seg = _seggiolino(cell)
    rng_f = np.random.default_rng(55)
    occ = _rumore(rng_f, Rr, C, 7)                            # gruppi di tifosi: zone piene e zone rade
    img = np.zeros((h_, w_, 3))
    conc = _lin("#a9acb3")
    for rr in range(Rr):
        for c in range(C):
            ys, xs = slice(rr * cell, (rr + 1) * cell), slice(c * cell, (c + 1) * cell)
            k = kind[rr, c]
            if k == 0:
                cella = grid[rr, c][None, None, :] * seg[..., None]
                if not (con_nome and 44 <= rr <= 59) and rng_f.random() < 0.06 + 0.50 * occ[rr, c]:
                    cella = _spettatore(cella, seg, cell, rng_f)
                img[ys, xs] = cella
            elif k == 1:                                       # gradino del corridoio: pedata chiara + alzata scura
                y = np.arange(cell)[:, None] / cell
                sh = np.where(y < 0.35, 0.62, np.where(y < 0.5, 0.95, 1.05))
                img[ys, xs] = conc[None, None, :] * 0.70 * sh[..., None] * np.ones((1, cell, 1))
            else:                                              # diagonale di cemento
                y = np.arange(cell)[:, None] / cell
                sh = np.where(y < 0.12, 0.55, 0.92 + 0.10 * (y > 0.8))
                img[ys, xs] = conc[None, None, :] * 0.85 * sh[..., None] * np.ones((1, cell, 1))
    return _img(nomefile, np.clip(img, 0, 1), cartella)


def tex_cartelloni(cartella, blu="#1d3f96", w_=4096, h_=128, nomefile="cartelloni", nome="RESCO REGGELLO"):
    """Cartelloni LED (16 m di fascia per tile): pannelli di sponsor locali con scritte vere (font a blocchi), tinte piene
    e filetto, griglia di pixel LED. Il tile e' continuo: il primo pannello riparte dove finisce l'ultimo."""
    rng = np.random.default_rng(9)
    img = np.zeros((h_, w_, 3)) + _lin("#070a18")
    spons = [("TOSCANA ENERGIA", "#ffffff", "#c8302f"), ("BANCA DEL VALDARNO", "#ffffff", blu),
             ("PIZZERIA DA MARIO", "#14234f", "#f2c30f"), ("EDILIZIA BIANCHI", "#ffffff", "#1f9d5c"),
             (nome, "#ffffff", "#14234f"), ("FARMACIA CENTRALE", "#14234f", "#e8ecf2"),
             ("CANTINA DEL BORGO", "#f2c30f", "#5b1a2a"), ("AUTO ROSSI 4.0", "#ffffff", "#2d6bd6"),
             ("MOBILI CHIANTI", "#14234f", "#e8571c"),
             ("BAR SPORT", "#ffffff", "#1f9d5c"), ("FORNO LUCA", "#14234f", "#f2c30f"), ("IDRAULICA", "#ffffff", "#c8302f"), ("ASD 1975", "#ffffff", "#2d6bd6")]
    x = 0
    i = 0
    while x < w_:
        scelto = None
        for dk in range(len(spons)):                              # il primo sponsor (a rotazione) che entra nello spazio rimasto
            testo, fg, bg = spons[(i + dk) % len(spons)]
            scala = min(8, 900 // (6 * len(testo)), (w_ - x - 60) // (6 * len(testo)))
            if scala >= 4:
                scelto = (testo, fg, bg, scala)
                i += dk + 1
                break
        if scelto is None:
            break
        testo, fg, bg, scala = scelto
        bw = 6 * len(testo) * scala + 60
        if w_ - x - bw < 6 * 4 * 4 + 60:                          # se il resto non basta per un altro pannello, questo lo assorbe
            bw = w_ - x
        pan = np.zeros((h_ - 16, bw - 8, 3)) + _lin(bg)
        yy = np.linspace(0, 1, pan.shape[0])[:, None, None]
        pan = pan * (0.82 + 0.28 * (1 - yy))
        pan[:3] = _lin(fg) * 0.9                                   # filetto in alto e in basso
        pan[-3:] = _lin(fg) * 0.9
        tx = (pan.shape[1] - 6 * len(testo) * scala + scala) // 2
        ty = (pan.shape[0] - 7 * scala) // 2
        for k, ch in enumerate(testo):
            if ch == " ":
                continue
            gl = _lettera(ch)
            for ly in range(7):
                for lx in range(5):
                    if gl[ly][lx]:
                        pan[ty + ly * scala:ty + (ly + 1) * scala, tx + (6 * k + lx) * scala:tx + (6 * k + lx + 1) * scala] = _lin(fg)
        img[8:h_ - 8, x + 4:x + 4 + pan.shape[1]] = pan
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


def tex_muro_tunnel(cartella, tinta, nome, w_=512, h_=384):
    """Parete del tunnel (tile 4 m x 3 m): pannelli verticali da 1 m con fughe, zoccolo scuro, fascia alta piu' chiara."""
    rng = np.random.default_rng(31)
    g = 0.92 + 0.08 * rng.random((h_, w_)) + 0.05 * _rumore(rng, h_, w_, 24)
    rgb = _lin(tinta)[None, None, :] * g[..., None]
    for x in range(0, w_, w_ // 4):
        rgb[:, x:x + 2] *= 0.55                                   # fughe dei pannelli
    rgb[int(h_ * 0.90):] *= 0.55                                  # zoccolo (z < 0,3 m)
    rgb[int(h_ * 0.895):int(h_ * 0.905)] *= 1.25
    rgb[:int(h_ * 0.08)] *= 1.12                                  # fascia alta
    return _img(nome, np.clip(rgb, 0, 1), cartella)


def tex_soffitto(cartella, n=512):
    """Soffitto del tunnel (tile 2,4 m): pannelli metallici scuri 0,6 m con fughe, feritoie di ventilazione e una trave centrale."""
    rng = np.random.default_rng(43)
    g = 0.88 + 0.12 * rng.random((n, n)) * 0.6 + 0.06 * _rumore(rng, n, n, 32)
    rgb = _lin("#5a6272")[None, None, :] * g[..., None]
    for k in range(0, n, n // 4):
        rgb[k:k + 3, :] *= 0.45
        rgb[:, k:k + 3] *= 0.45
    for ky in (1, 3):                                             # feritoie: tre tacche scure ogni due pannelli
        for kx in (0, 2):
            y0, x0 = ky * n // 4 + n // 16, kx * n // 4 + n // 16
            for j in range(3):
                rgb[y0 + j * 14:y0 + j * 14 + 5, x0:x0 + n // 8] *= 0.35
    return _img("tunnel_soffitto", np.clip(rgb, 0, 1), cartella)


def tex_pav_tunnel(cartella, tinta, n=512):
    """Pavimento del tunnel (tile 3,2 m): cemento lucidato con macchie e giunti ogni 1,6 m."""
    rng = np.random.default_rng(37)
    g = 0.90 + 0.10 * _rumore(rng, n, n, 64) + 0.05 * rng.random((n, n))
    rgb = _lin(tinta)[None, None, :] * g[..., None]
    rgb[:, :2] *= 0.6
    rgb[:2, :] *= 0.6
    rgb[:, n // 2:n // 2 + 2] *= 0.6
    rgb[n // 2:n // 2 + 2, :] *= 0.6
    return _img("tunnel_pav", np.clip(rgb, 0, 1), cartella)


def tex_basso(cartella, blu, w_=512, h_=160):
    """Muro di base e facciata (tile 8 m x 2,5 m): pannelli blu notte da 2 m con fughe, zoccolo scuro, filetto chiaro in alto."""
    rng = np.random.default_rng(41)
    g = 0.90 + 0.10 * rng.random((h_, w_)) + 0.06 * _rumore(rng, h_, w_, 20)
    rgb = _lin(_scuro_hex(blu, 1.0))[None, None, :] * g[..., None]
    for x in range(0, w_, w_ // 4):
        rgb[:, x:x + 2] *= 0.5
        rgb[:, x + 2:x + 4] *= 1.15
    rgb[int(h_ * 0.88):] *= 0.5                                   # zoccolo
    rgb[:5] = _lin("#aeb6c8") * 0.8                               # filetto in alto
    return _img("basso", np.clip(rgb, 0, 1), cartella)


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


_FONT = {
    "A": ".###.|#...#|#...#|#####|#...#|#...#|#...#", "B": "####.|#...#|#...#|####.|#...#|#...#|####.",
    "C": ".####|#....|#....|#....|#....|#....|.####", "D": "####.|#...#|#...#|#...#|#...#|#...#|####.",
    "E": "#####|#....|#....|####.|#....|#....|#####", "F": "#####|#....|#....|####.|#....|#....|#....",
    "G": ".####|#....|#....|#..##|#...#|#...#|.###.", "H": "#...#|#...#|#...#|#####|#...#|#...#|#...#",
    "I": "#####|..#..|..#..|..#..|..#..|..#..|#####", "J": "..###|...#.|...#.|...#.|...#.|#..#.|.##..",
    "K": "#...#|#..#.|#.#..|##...|#.#..|#..#.|#...#", "L": "#....|#....|#....|#....|#....|#....|#####",
    "M": "#...#|##.##|#.#.#|#.#.#|#...#|#...#|#...#", "N": "#...#|##..#|#.#.#|#..##|#...#|#...#|#...#",
    "O": ".###.|#...#|#...#|#...#|#...#|#...#|.###.", "P": "####.|#...#|#...#|####.|#....|#....|#....",
    "Q": ".###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#", "R": "####.|#...#|#...#|####.|#.#..|#..#.|#...#",
    "S": ".####|#....|#....|.###.|....#|....#|####.", "T": "#####|..#..|..#..|..#..|..#..|..#..|..#..",
    "U": "#...#|#...#|#...#|#...#|#...#|#...#|.###.", "V": "#...#|#...#|#...#|#...#|#...#|.#.#.|..#..",
    "W": "#...#|#...#|#...#|#.#.#|#.#.#|##.##|#...#", "X": "#...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#",
    "Y": "#...#|#...#|.#.#.|..#..|..#..|..#..|..#..", "Z": "#####|....#|...#.|..#..|.#...|#....|#####",
    "0": ".###.|#...#|#..##|#.#.#|##..#|#...#|.###.", "1": "..#..|.##..|..#..|..#..|..#..|..#..|.###.",
    "2": ".###.|#...#|....#|...#.|..#..|.#...|#####", "3": "####.|....#|....#|.###.|....#|....#|####.",
    "4": "...#.|..##.|.#.#.|#..#.|#####|...#.|...#.", "5": "#####|#....|####.|....#|....#|#...#|.###.",
    ".": ".....|.....|.....|.....|.....|.##..|.##..", "-": ".....|.....|.....|#####|.....|.....|.....",
    "&": ".##..|#..#.|.##..|.#.#.|#..##|#...#|.##.#",
}


def _lettera(ch):
    """Matrice 7x5 per A-Z, 0-5 e qualche segno (font a blocchi). Sconosciute = blocco pieno."""
    if ch in _FONT:
        return [[1 if c == "#" else 0 for c in riga] for riga in _FONT[ch].split("|")]
    v = [1] * 35
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
    return np.clip(c, 0.0, GAIN_INTERNO) / GAIN_INTERNO


GAIN_INTERNO = 1.8                        # idem per il tunnel: la luce cotta sta sotto 1 (niente piatto da saturazione), il sito la moltiplica
GAIN_ESTERNO = 1.35                       # la luce cotta esterna e' divisa per questo; lo stesso fattore la ripristina nel sito
SOLE_COL = np.array([1.0, 0.93, 0.80]) * 1.45
AMB_CIELO = np.array([0.34, 0.42, 0.60])
AMB_TERRA = np.array([0.34, 0.38, 0.28])     # rimbalzo dal campo al sole: le pareti all'ombra non restano nere
SOTTO_TETTO = np.array([0.62, 0.62, 0.60])   # intradosso del tetto: luce di rimbalzo da campo e spalti


def ciotola_livelli():
    """Anelli della ciotola: dict con la tribuna (r0,z0 -> r1,z1), il corridoio (-> pr1,pz1) e la parete che sale al
    livello successivo (fino a zmuro). L'ultima parete e' la facciata che chiude gli spalti sotto il tetto."""
    out = []
    r, z = ST_RAGGIO - 0.05, ST_ALTEZZA0           # il primo anello parte dove arriva il muro di base (r - 0,05): senza fessura
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
BASSA = False                             # versione per telefoni: texture dimezzate, meno suddivisioni (tunnel_bassa.glb)


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


# ------------------------------------------------------------------ cosa si vede davvero dal percorso
VIS_ORIZZ = math.radians(66.0)            # semi-apertura orizzontale (16:9 stringe, 9:16 allarga in verticale: copro entrambi + margine)
VIS_VERT = math.radians(60.0)
_CAMERE = None


def _camere_percorso(passo=0.5):
    """Camere (posizione, avanti, destra, su) campionate ogni `passo` m lungo il percorso, in coordinate locali (x, u, z)."""
    pts = percorso()
    pos = np.array([[k["p"][0], k["p"][2] - T0, k["p"][1]] for k in pts], float)
    tgt = np.array([[k["t"][0], k["t"][2] - T0, k["t"][1]] for k in pts], float)
    seg = np.linalg.norm(np.diff(pos, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    ss = np.arange(0.0, cum[-1] + 1e-6, passo)
    P = np.stack([np.interp(ss, cum, pos[:, i]) for i in range(3)], axis=1)
    T = np.stack([np.interp(ss, cum, tgt[:, i]) for i in range(3)], axis=1)
    f = T - P
    f /= np.linalg.norm(f, axis=1)[:, None]
    r = np.cross(f, np.array([0.0, 0.0, 1.0]))
    r /= np.linalg.norm(r, axis=1)[:, None]
    u = np.cross(r, f)
    return P, f, r, u


def _visibile(Q):
    """Q (N,3) locale (x, u, z finale): True se il punto cade in almeno una delle camere del percorso."""
    global _CAMERE
    if _CAMERE is None:
        _CAMERE = _camere_percorso()
    P, f, r, u = _CAMERE
    ok = np.zeros(len(Q), bool)
    th, tv = math.tan(VIS_ORIZZ), math.tan(VIS_VERT)
    for i in range(len(P)):
        v = Q - P[i]
        dep = v @ f[i]
        ok |= (dep > 0.05) & (np.abs(v @ r[i]) <= th * dep) & (np.abs(v @ u[i]) <= tv * dep)
    return ok


def _filtra_visibili(d, zoff):
    """Toglie da un gruppo di facce (dict di Raccolta) quelle che non entrano mai in campo: nove punti per faccia
    (angoli, metà lati, centro). I vertici non piu' usati si buttano."""
    V = np.array(d["v"], float)
    F = np.array(d["f"], int)
    if len(F) == 0:
        return 0
    Q = np.stack([V[:, 0], -V[:, 1] - T0, V[:, 2] + zoff], axis=1)
    c = Q[F]                                                    # (nf, 4, 3)
    pts = []
    for s_ in (0.0, 0.5, 1.0):
        for t_ in (0.0, 0.5, 1.0):
            pts.append((c[:, 0] * (1 - s_) + c[:, 1] * s_) * (1 - t_) + (c[:, 3] * (1 - s_) + c[:, 2] * s_) * t_)
    pts = np.stack(pts, axis=1)                                 # (nf, 9, 3)
    ok = _visibile(pts.reshape(-1, 3)).reshape(len(F), 9).any(axis=1)
    tolte = int((~ok).sum())
    keep = F[ok]
    usati = np.unique(keep.ravel())
    nuovo = -np.ones(len(V), int)
    nuovo[usati] = np.arange(len(usati))
    d["v"] = [d["v"][i] for i in usati]
    d["n"] = [d["n"][i] for i in usati]
    d["uv"] = [d["uv"][i] for i in usati]
    d["modo"] = [d["modo"][i] for i in usati]
    d["f"] = [tuple(int(nuovo[i]) for i in f) for f in keep]
    return tolte


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

    def sbarra(self, m, p0, p1, s, modo="int"):
        """Barra a sezione quadrata (lato s) fra due punti locali, anche inclinata."""
        p0, p1 = np.array(p0, float), np.array(p1, float)
        d = p1 - p0
        d /= np.linalg.norm(d)
        a = np.cross(d, np.array([0.0, 0.0, 1.0]))
        a /= np.linalg.norm(a)
        b = np.cross(a, d)
        h = s / 2
        co = lambda p, i, j: p + a * h * i + b * h * j  # noqa: E731
        for (n, i0, j0, i1, j1) in ((a, 1, -1, 1, 1), (-a, -1, 1, -1, -1), (b, -1, 1, 1, 1), (-b, 1, -1, -1, -1)):
            n = tuple(float(v) for v in n)
            self.quad(m, tuple(co(p0, i0, j0)), tuple(co(p1, i0, j0)), tuple(co(p1, i1, j1)), tuple(co(p0, i1, j1)), n, modo=modo)

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
            if zoff or m.name == "Tunnel_Facciata":
                tolte = _filtra_visibili(d, zoff)          # niente di cio' che la camera non vede mai (il video del drone copre il resto)
                print("TAGLIO", m.name, "facce tolte", tolte, "rimaste", len(d["f"]))
                if not d["f"]:
                    continue
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


def _anta(nome, m_anta, m_vetro, cx, u, larg, alt, colore):
    """Anta scorrevole come oggetto a se' (il sito la sposta): scatola in acciaio con finestra in vetro scuro sul lato del tunnel.
    Origine al centro dell'anta; due materiali (primitive diverse nel glb)."""
    hx, hy, hz = larg / 2, 0.025, alt / 2
    V = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz), (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    wx, wz0, wz1 = larg * 0.28, hz * 0.05, hz * 0.85                      # finestra: sul lato +u del tunnel = -y mondo
    off = len(V)
    V += [(-wx, -hy - 0.004, wz0), (wx, -hy - 0.004, wz0), (wx, -hy - 0.004, wz1), (-wx, -hy - 0.004, wz1)]
    F += [(off, off + 1, off + 2, off + 3)]
    me = bpy.data.meshes.new(nome)
    me.from_pydata(V, [], F)
    me.update()
    me.materials.append(m_anta)
    me.materials.append(m_vetro)
    for i, pl in enumerate(me.polygons):
        pl.material_index = 1 if i == len(F) - 1 else 0
        pl.use_smooth = False
    uvl = me.uv_layers.new(name="UVMap")
    col = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    for i in range(len(me.vertices)):
        col.data[i].color = (colore[0], colore[1], colore[2], 1.0)
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = tuple(w((cx, u, alt / 2)))
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
def _anello_ciotola(R, m, r0, z0, r1, z1, n, uvscala=0.12, modo="ext", salta=None, doppia=False, uvm=None, sub=(1, 1), uvk=None, poli=None, ks=None, uspic=None):
    """Anello di spalti (ciotola): n spicchi, normale verso il campo, ognuno suddiviso in sub = (nu, nv) per la luce cotta.
    salta(a_medio) = True per saltare lo spicchio (varco tunnel). doppia = facce da entrambi i lati.
    uvm = (metri per ripetizione in u, quota di riferimento, metri per ripetizione in v): UV continue
    lungo l'anello. uvk = (spicchi per ripetizione in u, metri per ripetizione in v): v dalla lunghezza reale del lato.
    Trapezio vero (4 angoli), non parallelogramma (buchi a spicchio)."""
    nu, nv = sub
    if BASSA:
        nu, nv = max(2, nu // 2), max(1, (nv + 1) // 2)
    for k in (range(n) if ks is None else ks):
        a0 = 2 * math.pi * k / n
        a1 = 2 * math.pi * (k + 1) / n
        if salta is not None and salta((a0 + a1) / 2):
            continue
        if poli:     # i punti stanno sulle corde di un poligono di `poli` lati: coincidono con l'anello di spalti (niente fessura)
            def pt(r, a, am=(a0 + a1) / 2):
                kk = int(am / (2 * math.pi / poli))
                ak, ak1 = kk * 2 * math.pi / poli, (kk + 1) * 2 * math.pi / poli
                t = (a - ak) / (ak1 - ak)
                return (r * ((1 - t) * math.cos(ak) + t * math.cos(ak1)), r * ((1 - t) * math.sin(ak) + t * math.sin(ak1)))
        else:
            def pt(r, a, am=0.0):
                return (r * math.cos(a), r * math.sin(a))
        p00 = pt(r0, a0) + (z0,)
        p10 = pt(r0, a1) + (z0,)
        p11 = pt(r1, a1) + (z1,)
        p01 = pt(r1, a0) + (z1,)
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
                        d["uv"].append((((k + s_) / uspic) if uspic else ((k + s_) * lseg / uvm[0]), (z0 + (z1 - z0) * t_ - uvm[1]) / uvm[2]))
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
    spalti_i = (tex_spalti(cartella, blu=blu, nomefile="spalti"), tex_spalti(cartella, blu=blu, nome=dati["nome"], nomefile="spalti_nome"))
    cart_i = tex_cartelloni(cartella, blu=blu, nome=dati["nome"].upper())
    # ---- tunnel stile Camp Nou: pareti blu squadra, pavimento chiaro, corrimano oro, LED a soffitto
    m_blu = mat("Tunnel_Muro", "#ffffff", tex_muro_tunnel(cartella, _scuro_hex(blu, 0.62), "tunnel_muro"), 0.55)
    m_scala = mat("Tunnel_MuroScala", "#ffffff", tex_muro_tunnel(cartella, "#2a5ec0", "tunnel_scala"), 0.5)
    m_pav = mat("Tunnel_Pavimento", "#ffffff", tex_pav_tunnel(cartella, "#8f9fba"), 0.5)
    m_alzata = mat("Tunnel_Alzata", "#2b2e34", None, 0.85)
    m_corsia = mat("Tunnel_Corsia", "#838b96", None, 0.62)
    m_oro = mat("Tunnel_Oro", "#c9a227", None, 0.3)
    m_sof = mat("Tunnel_Soffitto", "#ffffff", tex_soffitto(cartella), 0.9)
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
    # scalinata: pareti laterali nel colore squadra (come le pareti rosse del Camp Nou) e corrimani che salgono coi gradini
    for sg, nx in ((-1, 1), (1, -1)):
        x = sg * hw
        R.quad(m_scala, (x - sg * 0.02, ST_SCALA_U0, 0.0), (x - sg * 0.02, L, 0.0), (x - sg * 0.02, L, H), (x - sg * 0.02, ST_SCALA_U0, H),
               (nx, 0, 0), nu=6, nv=3, uvs=(4.0, 3.0))
        R.sbarra(m_oro, (sg * (hw - 0.12), ST_SCALA_U0 - 0.3, 0.95), (sg * (hw - 0.12), L - 0.1, 0.95 + ST_QUOTA), 0.05)
    R.sbarra(m_oro, (0.0, ST_SCALA_U0 - 0.3, 0.95), (0.0, L - 0.4, 0.95 + ST_QUOTA * 0.93), 0.05)
    # montanti dei corrimani laterali: dal gradino al corrimano, ogni 1,4 m (prima i corrimani sembravano sospesi)
    for sg in (-1, 1):
        for up in (ST_SCALA_U0 + 0.4, ST_SCALA_U0 + 1.8, ST_SCALA_U0 + 3.2, ST_SCALA_U0 + 4.6, ST_SCALA_U0 + 5.8):
            zr = 0.95 + (up - (ST_SCALA_U0 - 0.3)) / (L - 0.1 - (ST_SCALA_U0 - 0.3)) * ST_QUOTA
            zg = (int((up - ST_SCALA_U0) / du) + 1) * ST_ALZATA
            R.scatola(m_oro, (sg * (hw - 0.12), up, (zg + zr) / 2), (0.035, 0.035, zr - zg), modo="int")
    for up in (ST_SCALA_U0 + 1.5, ST_SCALA_U0 + 3.5, ST_SCALA_U0 + 5.5):
        zg = 0.95 + (up - ST_SCALA_U0 + 0.3) / (L - ST_SCALA_U0) * ST_QUOTA * 0.93
        R.scatola(m_oro, (0.0, up, zg / 2), (0.04, 0.04, zg))
    # LED lineari lungo le pareti (come la foto) e scritta sopra la porta in fondo
    for sg in (-1, 1):
        R.scatola(m_led, (sg * (hw - 0.02), (ST_SCALA_U0 + 0.5) / 2, 2.62), (0.03, ST_SCALA_U0 - 0.5, 0.05), modo="piena")
    m_tt = mat("Tunnel_Testo", "#ffffff", None, 0.6)
    testo_porta = maglia._mesh_testo("SPOGLIATOIO", 0.20, 1.9, bold=0.006, passo=1.0)
    _piano(testo_porta, (math.pi / 2, 0.0, 0.0), tuple(w((0.0, 0.03, 2.68))), m_tt, "Testo_Porta")
    # soffitto scuro con 5 lame di luce (come la foto: strisce LED sul blu)
    R.parete(m_sof, -hw, hw, 0.0, L, H, H, (0, 0, -1), mx=0.8, uvs=(2.4, 2.4))
    for fu in (2.5, 6.5, 10.5, 14.5, 17.5):
        # NOTA: sopra a H-0.02 (era a filo del soffitto = sfarfallio)
        R.scatola(m_led, (0, fu, H - 0.035), (W - 0.6, 0.10, 0.03), modo="piena")
    # pareti blu con scudi bianchi retroilluminati e corrimano oro (mesh vere, niente testi flottanti)
    for sg, nx in ((-1, 1), (1, -1)):
        x = sg * hw
        R.parete(m_blu, x, x, 0.0, L, 0.0, H, (nx, 0, 0), mx=0.8, uvs=(4.0, 3.0))
        R.parete(m_filo, x - sg * 0.006, x - sg * 0.006, 0.0, L, 1.10, 1.16, (nx, 0, 0), mx=1.0)   # 6 mm davanti alla parete: a filo faceva z-fighting (strisce bianche)
        R.scatola(m_oro, (sg * (hw - 0.12), L / 2, 0.95), (0.05, L - 2.0, 0.05))
        for u_scudo in (6.0, 12.5):
            for kk, mm, dx in ((0.62, m_sc_b, 0.012), (0.54, m_sc_c, 0.020)):
                scudo_parete(kk, mm, (x - sg * dx, u_scudo, 1.95), "ScudoMuro%d_%s_%d" % (sg, int(u_scudo), int(kk * 100)),
                             (math.pi / 2, 0.0, sg * -math.pi / 2))
    # ---- dettagli del tunnel (come in un vero tunnel dei giocatori)
    m_giallo = mat("Tunnel_Giallo", "#e0b81c", None, 0.6)
    m_metallo = mat("Tunnel_Metallo", "#6c7482", None, 0.45)
    m_rosso = mat("Tunnel_Rosso", "#c8302f", None, 0.5)
    m_uscita = mat("Tunnel_Uscita", "#17c15a", None, 0.5, emis=1.2)
    m_tt = mat("Tunnel_Testo", "#ffffff", None, 0.6)
    for g in range(ST_N_GRADINI):                                    # bordo giallo antiscivolo su ogni gradino
        zg = (g + 1) * ST_ALZATA
        R.parete(m_giallo, -hw + 0.1, hw - 0.1, ST_SCALA_U0 + g * du, ST_SCALA_U0 + g * du + 0.07, zg + 0.003, zg + 0.003,
                 (0, 0, 1), mx=2.5)
    for sg in (-1, 1):                                                # passerelle portacavi e tubazione sul soffitto
        R.scatola(m_metallo, (sg * 1.55, L / 2, H - 0.10), (0.30, L - 1.0, 0.04))
        for up in (2.5, 6.5, 10.5, 14.5, 18.0):
            R.scatola(m_metallo, (sg * 1.55, up, H - 0.05), (0.04, 0.05, 0.10))
    R.scatola(m_metallo, (-2.05, L / 2, H - 0.22), (0.09, L - 1.0, 0.09))
    R.scatola(m_giallo, (-2.05, 4.0, H - 0.22), (0.095, 0.25, 0.095))
    R.scatola(m_rosso, (hw - 0.09, 8.0, 1.30), (0.16, 0.16, 0.52))     # estintore e staffa
    R.scatola(m_metallo, (hw - 0.04, 8.0, 1.62), (0.05, 0.12, 0.08))
    for sg, scritta in ((-1, "ORGOGLIO DI RESCO"), (1, "UNA SOLA MAGLIA")):   # frasi sulle pareti, fra uno scudo e l'altro
        me_t = maglia._mesh_testo(scritta, 0.26, 3.4, bold=0.008, passo=1.0)
        _piano(me_t, (math.pi / 2, 0.0, sg * -math.pi / 2), tuple(w((sg * (hw - 0.015), 9.25, 1.95))), m_tt, "Testo_Parete%d" % sg)
    R.scatola(m_uscita, (0.0, 11.0, 2.78), (0.62, 0.06, 0.20), modo="piena")        # segnale di uscita appeso
    me_u = maglia._mesh_testo("USCITA", 0.13, 0.54, bold=0.004, passo=1.0)
    _piano(me_u, (math.pi / 2, 0.0, 0.0), tuple(w((0.0, 11.04, 2.78))), m_tt, "Testo_Uscita")
    R.scatola(m_metallo, (0.0, 11.0, 2.92), (0.04, 0.04, 0.16))
    # parete di fondo (u = 0) con il varco della porta
    pw, ph = sala.PORTA_W / 2, sala.PORTA_H
    for (xa, xb) in ((-hw, -pw), (pw, hw)):
        R.parete(m_blu, xa, xb, 0.0, 0.0, 0.0, H, (0, 1, 0), mx=0.6)
    R.parete(m_blu, -pw, pw, 0.0, 0.0, ph, H, (0, 1, 0), mx=0.6)
    # porta a due ante in acciaio e vetro (si aprono quando ci si avvicina: lo fa il sito) con telaio
    m_anta = mat("Tunnel_Anta", "#8c95a6", None, 0.35)
    m_vetro = mat("Tunnel_Vetro", "#0c1a33", None, 0.15)
    ci = luce_interna(w((0.0, 0.07, 1.2)), wn((0.0, 1.0, 0.0)))
    col_a = tuple(float(v) for v in np.clip(ci * 0.95, 0, 1))
    _anta("Anta_L", m_anta, m_vetro, -pw / 2 - 0.005, 0.07, pw + 0.01, ph, col_a)
    _anta("Anta_R", m_anta, m_vetro, pw / 2 + 0.005, 0.07, pw + 0.01, ph, col_a)
    for sg in (-1, 1):
        R.scatola(m_metallo, (sg * (pw + 0.05), 0.02, ph / 2 + 0.02), (0.10, 0.12, ph + 0.04))
    R.scatola(m_metallo, (0.0, 0.02, ph + 0.05), (2 * pw + 0.2, 0.12, 0.10))
    R.scatola(m_giallo, (0.0, 0.085, 0.03), (2 * pw, 0.01, 0.03))                   # soglia gialla
    # bagliore del campo alla bocca (u = L): NIENTE parete, la bocca resta aperta
    # (la luce viene dal campo vero dietro: un muro qui coprirebbe l'entrata)
    return _costruisci_esterno(R, dati, cartella, erba_i, spalti_i, cart_i)


def _costruisci_esterno(R, dati, cartella, erba_i, spalti_i, cart_i):
    """Stadio: campo con righe, muro di base con cartelloni LED, ciotola a 3 anelli (corridoi, vomitori, facciata),
    tetto con travi, maxischermi, facciata attorno alla bocca del tunnel. Luce cotta: sole unico + cielo."""
    blu = dati["colori"]["dettagli"]
    m_erba = mat("Esterno_Erba", "#ffffff", erba_i, 0.95)
    m_linea = mat("Esterno_Linea", "#f4f4f4", None, 0.8)
    m_spalti = mat("Esterno_Spalti", "#ffffff", spalti_i[0], 0.85)
    m_spalti_nome = mat("Esterno_SpaltiNome", "#ffffff", spalti_i[1], 0.85)
    m_cart = mat("Esterno_Cartelloni", "#ffffff", cart_i, 0.6)
    m_cem = mat("Esterno_Cemento", "#ffffff", tex_cemento(cartella), 0.9)
    m_vomi = mat("Esterno_Muro", "#ffffff", tex_muro(cartella), 0.9)
    m_faccia = mat("Esterno_Facciata", "#ffffff", tex_facciata(cartella), 0.9)
    m_basso = mat("Esterno_MuroBase", "#ffffff", tex_basso(cartella, blu), 0.8)
    m_tetto = mat("Esterno_Tetto", "#e6e9ef", None, 0.6)
    m_tetto_s = mat("Esterno_TettoSotto", "#ffffff", tex_tetto(cartella), 0.8)
    m_fascia = mat("Esterno_TettoFascia", "#eef1f6", None, 0.6)
    m_nastro = mat("Esterno_TettoLed", "#cfe6ff", None, 0.5)
    m_schermo = mat("Esterno_Schermo", "#ffffff", tex_schermo(cartella, dati["nome"], blu=blu), 0.4)
    m_telaio = mat("Esterno_Telaio", "#1a1d24", None, 0.6)
    m_fac = mat("Tunnel_Facciata", "#ffffff", tex_basso(cartella, blu), 0.8)
    m_testo = mat("Esterno_Testo", "#ffffff", None, 0.6)
    hw = W / 2
    uc = ST_CENTRO_U
    R_ = ST_RAGGIO
    # ---- campo: erba su tutto il disco della ciotola (celle di 2,5 m per l'ombra degli spalti)
    R.parete(m_erba, -R_, R_, L, uc + R_, 0.0, 0.0, (0, 0, 1), mx=4.0 if BASSA else 2.5, modo="ext", uvs=(8.0, 8.0), uv0=(0.0, 0.0))
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
    # dischetti (rigore e centrocampo), archi delle aree, bandierine d'angolo, panchine delle riserve
    m_panca = mat("Esterno_Panchina", "#1c2230", None, 0.7)
    m_tettoia = mat("Esterno_Tettoia", "#c4cad6", None, 0.5)
    m_rosso = mat("Esterno_Bandierina", "#d93232", None, 0.6)
    for (uu, xx0) in ((uc, 0.0),) + tuple((uc + sg_ * cl - sg_ * 11.0, 0.0) for sg_ in (-1, 1)):
        R.parete(m_linea, xx0 - 0.11, xx0 + 0.11, uu - 0.11, uu + 0.11, 0.004, 0.004, (0, 0, 1), mx=40.0, modo="ext")
    for sgn in (-1, 1):
        ug = uc + sgn * cl
        cu = ug - sgn * 11.0
        n_arc = 40
        for q in range(n_arc):
            a0 = -math.pi / 2 + math.pi * q / n_arc
            a1 = -math.pi / 2 + math.pi * (q + 1) / n_arc
            pts = []
            for ang in (a0, a1):
                pts.append((9.15 * math.sin(ang), cu - sgn * 9.15 * math.cos(ang)))
            # solo il tratto fuori dall'area (distanza dalla linea di porta > 16 m)
            if all(abs(pt[1] - ug) > 16.0 for pt in pts):
                (x0_, u0_), (x1_, u1_) = pts
                R.quad(m_linea, (x0_ - 0.075, u0_, 0.004), (x1_ - 0.075, u1_, 0.004), (x1_ + 0.075, u1_, 0.004), (x0_ + 0.075, u0_, 0.004), (0, 0, 1), modo="ext")
        for sx in (-1, 1):                                   # bandierine d'angolo
            R.scatola(m_linea, (sx * cx, ug, 0.75), (0.04, 0.04, 1.5), modo="ext")
            R.scatola(m_rosso, (sx * cx - sx * 0.19, ug, 1.35), (0.34, 0.02, 0.26), modo="ext")
    for sx in (-1, 1):                                       # panchine: due aree tecniche ai lati, a meta' campo
        for du in (-9.0, 9.0):
            xp = sx * (cx + 3.0)
            R.scatola(m_panca, (xp, uc + du, 0.45), (0.6, 7.0, 0.1), modo="ext")                      # seduta
            R.scatola(m_panca, (xp + sx * 0.35, uc + du, 0.9), (0.08, 7.0, 0.9), modo="ext")          # schienale
            R.scatola(m_tettoia, (xp + sx * 0.1, uc + du, 2.15), (1.7, 7.4, 0.08), modo="ext")        # tettoia
            for dd in (-3.4, 3.4):
                R.scatola(m_panca, (xp + sx * 0.8, uc + du + dd, 1.1), (0.08, 0.08, 2.2), modo="ext")
    # ---- imbocco del tunnel sul campo: cappa di 3,2 m (pareti a pannelli, soffitto con LED, tappeto di gomma), cornice e scudi
    m_cappa = mat("Esterno_Cappa", "#ffffff", tex_basso(cartella, blu), 0.7)
    m_cappa_t = mat("Esterno_CappaTetto", "#59627a", None, 0.7)
    m_gomma = mat("Esterno_Gomma", "#202328", None, 0.95)
    m_cornice = mat("Esterno_Cornice", "#b4bccb", None, 0.4)
    m_led2 = mat("Tunnel_Luce", "#fff3de", None, 0.5, emis=8.0)
    HU, HZ = 3.2, H - ST_QUOTA
    for sg in (-1, 1):
        R.parete(m_cappa, sg * hw, sg * hw, L, L + HU, 0.0, HZ, (-sg, 0, 0), mx=0.8, modo="ext", uvs=(8.0, 2.5))
    R.parete(m_cappa_t, -hw, hw, L, L + HU, HZ, HZ, (0, 0, -1), mx=0.8, modo="ext")
    R.parete(m_gomma, -hw, hw, L, L + HU, 0.004, 0.004, (0, 0, 1), mx=0.8, modo="ext")
    for sg in (-1, 1):
        R.scatola(m_cornice, (sg * (hw + 0.13), L + HU, HZ / 2 + 0.1), (0.26, 0.32, HZ + 0.2), modo="ext")
    R.scatola(m_cornice, (0.0, L + HU, HZ + 0.13), (2 * hw + 0.52, 0.32, 0.26), modo="ext")
    R.scatola(m_led2, (0.0, L + HU - 0.17, HZ - 0.03 + ST_QUOTA), (2 * hw - 0.3, 0.05, 0.04), modo="piena")   # Tunnel_*: quote finali
    for xx in (-1.2, 1.2):
        R.scatola(m_led2, (xx, L + HU / 2, HZ - 0.02 + ST_QUOTA), (0.08, HU - 0.5, 0.03), modo="piena")
    m_scb = mat("Tunnel_ScudoBordo", "#f4f4f4", None, 0.4, emis=0.5)
    m_scc = mat("Tunnel_ScudoCampo", "#2f5fc4", None, 0.4, emis=0.7)
    for sg in (-1, 1):
        for kk, mm, dx in ((0.55, m_scb, 0.012), (0.47, m_scc, 0.020)):
            scudo_parete(kk, mm, (sg * hw - sg * dx, L + 1.6, 1.95), "CappaScudo%d_%d" % (sg, int(kk * 100)), (math.pi / 2, 0.0, sg * -math.pi / 2))
    # ---- muro di base (cartelloni LED in basso, blu notte sopra) con il varco del tunnel: arriva alla quota del primo anello
    ang_tunnel = -math.pi / 2                                # il tunnel e' dalla parte di u piccolo
    def varco(a):
        d = (a - ang_tunnel + math.pi) % (2 * math.pi) - math.pi
        return abs(d) < 0.056                                # 4 spicchi di 192: circa 6,5 m
    _anello_ciotola(R, m_cart, R_ - 0.05, 0.0, R_ - 0.05, 1.0, 192, modo="piena", salta=varco, uvm=(32.0, 0.0, 1.0), poli=48)
    _anello_ciotola(R, m_basso, R_ - 0.05, 1.0, R_ - 0.05, ST_ALTEZZA0, 192, modo="ext", salta=varco, sub=(1, 2), uvm=(8.0, 1.0, 2.5), poli=48)
    # ---- facciata attorno alla bocca (u = L): chiude il varco, la bocca resta aperta (z da 0,9 a H)
    zb, zt = ST_QUOTA, ST_ALTEZZA0 + ST_QUOTA          # facciata alta come il muro di base
    R.parete(m_fac, -3.5, -hw, L, L, zb, zt, (0, 1, 0), mx=1.0, modo="ext", uvs=(8.0, 3.5), uv0=(0.0, 0.0))
    R.parete(m_fac, hw, 3.5, L, L, zb, zt, (0, 1, 0), mx=1.0, modo="ext", uvs=(8.0, 3.5), uv0=(0.0, 0.0))
    R.parete(m_fac, -hw, hw, L, L, H, zt, (0, 1, 0), mx=1.0, modo="ext", uvs=(8.0, 3.5), uv0=(0.0, (H - zb) / 3.5))
    # cappello sopra la facciata: chiude la fessura di 5 cm fra il bordo della facciata (u = L) e l'inizio del primo anello (r - 0,05)
    R.parete(m_fac, -3.6, 3.6, L - 0.01, L + 0.20, zt, zt, (0, 0, 1), mx=1.0, modo="ext", uvs=(8.0, 2.5), uv0=(0.0, 0.0))
    # ---- ciotola: 3 anelli con corridoio (cemento) e parete con vomitori; l'ultima parete e' la facciata sotto il tetto
    livelli = ciotola_livelli()
    for i, t in enumerate(livelli):
        lseg = 2 * math.pi * ((t["r0"] + t["r1"]) / 2) / 48
        lung = math.hypot(t["r1"] - t["r0"], t["z1"] - t["z0"])
        # il nome della squadra sta una sola volta, nel primo anello, nel tile di 8 spicchi centrato sul tunnel (k 32-39:
        # l'asse del tunnel e' a 270 gradi = confine fra gli spicchi 35 e 36, centro del tile); tutto il resto usa la texture senza nome
        kn = range(32, 40) if i == 0 else range(0)
        resto = [k for k in range(48) if k not in kn]
        kw = dict(modo="ext", uvm=(8 * lseg, ST_ALTEZZA0, 24.0), uspic=8, sub=(14, max(4, int(lung * 2.0))))
        _anello_ciotola(R, m_spalti, t["r0"], t["z0"], t["r1"], t["z1"], 48, ks=resto, **kw)
        if len(kn):
            _anello_ciotola(R, m_spalti_nome, t["r0"], t["z0"], t["r1"], t["z1"], 48, ks=kn, **kw)
        _anello_ciotola(R, m_cem, t["r1"], t["z1"], t["pr1"], t["pz1"], 48, modo="ext", uvk=(4.0, 1.2), sub=(6, 1))
        if i < len(livelli) - 1:
            _anello_ciotola(R, m_vomi, t["pr1"], t["pz1"], t["pr1"], t["zmuro"], 48, modo="ext", uvk=(2.0, ST_MURETTO), sub=(6, 2))
        else:
            _anello_ciotola(R, m_faccia, t["pr1"], t["pz1"], t["pr1"], t["zmuro"], 48, modo="ext", uvk=(2.0, t["zmuro"] - t["pz1"]), sub=(6, 4))
    # ---- tetto ad anello: estradosso bianco, intradosso con travi radiali, fascia interna con nastro LED
    _anello_ciotola(R, m_tetto_s, ST_TETTO_R0, ST_TETTO_Z - 0.3, ST_TETTO_R1, ST_TETTO_Z, 64, modo="sotto", uvk=(1.0, 20.0), sub=(2, 4))
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
    BASSA = "bassa" in argv
    ob = costruisci(dati, out)
    err, tri = verifica(ob)
    for e in err:
        print("TUNNEL_ERRORE", e)
    glb = os.path.join(out, "tunnel_bassa.glb" if BASSA else "tunnel.glb")
    if BASSA:
        for im in bpy.data.images:
            if im.size[0] >= 512 and im.users:
                im.scale(im.size[0] // 2, im.size[1] // 2)
    bpy.ops.export_scene.gltf(
        filepath=glb, export_format="GLB", export_apply=True, export_yup=True, export_animations=False,
        export_cameras=False, export_lights=False, export_materials="EXPORT", export_vertex_color="ACTIVE",
        export_image_format="JPEG", export_image_quality=90,
        export_meshopt_compression_enable=True)
    man = {"u0": T0, "larghezza": W, "altezza": H, "lunghezza": L,
           "bocca": {"z": T0 + L}, "percorso": percorso(),
           "passo": 1.1, "ampiezza_bob": 0.012, "gain_esterno": GAIN_ESTERNO, "gain_interno": GAIN_INTERNO,
           "sole": [float(SOLE[0]), float(SOLE[2]), float(SOLE[1] + 0.0)]}
    if not BASSA:
        json.dump(man, open(os.path.join(out, "tunnel.json"), "w", encoding="utf-8"), indent=1)
    print("TUNNEL_OK", glb, os.path.getsize(glb), "facce", tri)
    if err:
        sys.exit(1)
