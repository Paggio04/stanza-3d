"""cielo.py - cielo equirettangolare per lo sfondo del sito (Sky Texture di Blender, sole nella stessa direzione della luce cotta).

Uso:  blender -b -P cielo.py -- CARTELLA_ASSOLUTA [LARGHEZZA]

Scrive CARTELLA/cielo.jpg (2:1, default 2048 px). Il sole sta dove lo mette `tunnel.SOLE` (stessa direzione della luce
cotta negli spalti): l'immagine si ruota in orizzontale finche' il punto piu' luminoso cade nell'azimut voluto.
Convenzione del sito (three.js, EquirectangularReflectionMapping): u = atan2(d.z, d.x)/2pi + 0.5, v dal basso = asin(d.y)/pi + 0.5,
con d = (x, su, u) = (SOLE[0], SOLE[2], SOLE[1]).
"""
import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tunnel  # noqa: E402


def _fbm(px, py, rng_seed=7):
    """Rumore frattale (valore, 6 ottave) su coordinate piane; reticolo 64x64 ripetuto."""
    g = np.random.default_rng(rng_seed).random((64, 64))
    tot = np.zeros_like(px)
    amp, fr, norm = 1.0, 1.0, 0.0
    for _ in range(6):
        x, y = px * fr, py * fr
        x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
        fx, fy = x - x0, y - y0
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        a00, a10 = g[y0 % 64, x0 % 64], g[y0 % 64, (x0 + 1) % 64]
        a01, a11 = g[(y0 + 1) % 64, x0 % 64], g[(y0 + 1) % 64, (x0 + 1) % 64]
        tot += amp * (a00 * (1 - fx) * (1 - fy) + a10 * fx * (1 - fy) + a01 * (1 - fx) * fy + a11 * fx * fy)
        norm += amp
        amp *= 0.5
        fr *= 2.07
    return tot / norm


def _nuvole(a, W, H):
    """Cumuli sparsi sulla cupola: densita' da rumore frattale proiettato su un piano; piu' scuri dal lato opposto al sole."""
    col, riga = np.meshgrid((np.arange(W) + 0.5) / W, (np.arange(H) + 0.5) / H)
    lon = (col - 0.5) * 2 * math.pi
    lat = (0.5 - riga) * math.pi
    dx, dy, dz = np.cos(lat) * np.cos(lon), np.sin(lat), np.cos(lat) * np.sin(lon)
    up = np.clip(dy, 0.0, 1.0)
    px = dx / (dy + 0.10) * 1.6 + 13.0
    py = dz / (dy + 0.10) * 1.6 + 7.0
    d0 = _fbm(px, py)
    sx, sz = tunnel.SOLE[0], tunnel.SOLE[1]
    d1 = _fbm(px + sx * 0.06, py + sz * 0.06)
    dens = np.clip((d0 - 0.52) / 0.16, 0.0, 1.0)
    dens = dens * dens * (3 - 2 * dens)
    dens *= np.clip((up - 0.03) / 0.22, 0.0, 1.0)                 # sfuma verso l'orizzonte
    luce = np.clip(0.80 + (d1 - d0) * 5.0, 0.55, 1.1)              # verso il sole piu' chiaro
    nuv = (1.35 * luce)[..., None] * np.array([1.0, 0.99, 0.97])[None, None, :]
    cop = (dens * 0.9)[..., None]
    return a * (1 - cop) + nuv * cop


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.abspath(argv[0]) if argv else os.path.abspath("out_tunnel")
    W = int(argv[1]) if len(argv) > 1 else 2048
    H = W // 2
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    mondo = bpy.data.worlds.new("Cielo")
    mondo.use_nodes = True
    nt = mondo.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    try:
        sky.sky_type = "MULTIPLE_SCATTERING"
    except TypeError:
        sky.sky_type = "NISHITA"
    sky.sun_elevation = tunnel.SOLE_EL
    sky.sun_rotation = 0.0
    sky.sun_size = math.radians(1.2)       # disco un po' piu' grande del vero: si vede nel cielo che resta dentro il tetto
    sky.sun_intensity = 1.0
    sky.air_density = 1.0
    for nome, val in (("aerosol_density", 1.2), ("ozone_density", 1.0)):
        if hasattr(sky, nome):
            setattr(sky, nome, val)
    sky.altitude = 0.0
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.0
    ou = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], ou.inputs["Surface"])
    sc.world = mondo
    cam = bpy.data.cameras.new("Pano")
    cam.type = "PANO"
    try:
        cam.panorama_type = "EQUIRECTANGULAR"
    except Exception:
        cam.cycles.panorama_type = "EQUIRECTANGULAR"
    co = bpy.data.objects.new("Pano", cam)
    sc.collection.objects.link(co)
    co.rotation_euler = (math.pi / 2, 0.0, 0.0)
    sc.camera = co
    tmp = os.path.join(out, "cielo_tmp.exr")
    sc.render.image_settings.file_format = "OPEN_EXR"
    sc.render.image_settings.color_depth = "16"
    sc.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(tmp)
    a = np.array(img.pixels[:], np.float32).reshape(H, W, 4)[..., :3][::-1]     # riga 0 = alto
    lum = a.sum(axis=2)
    ry, rx = np.unravel_index(np.argmax(lum), lum.shape)
    # azimut voluto: colonna della direzione del sole
    d = (tunnel.SOLE[0], tunnel.SOLE[2], tunnel.SOLE[1])
    col = (math.atan2(d[2], d[0]) / (2 * math.pi) + 0.5) * W
    riga = (0.5 - math.asin(d[1]) / math.pi) * H
    a = np.roll(a, int(round(col - rx)), axis=1)
    # sotto l'orizzonte: colore dell'orizzonte (la ciotola lo copre)
    h = int(H / 2)
    a[h:] = a[h - 3:h - 1].mean(axis=(0, 1))[None, None, :]
    # esposizione: il cielo fuori dal sole sta intorno a 0,35 (lineare); il disco solare resta bruciato
    cielo = a[: h - 4]
    med = float(np.median(cielo.mean(axis=2)))
    print("CIELO_MEDIANA_PRIMA", med)
    a = a * (0.25 / max(med, 1e-6))
    a = _nuvole(a, W, H)
    a = np.clip(a / (1.0 + a) * 1.5, 0, 1)            # spalla morbida: l'orizzonte resta velato, non bianco
    a[h:] = a[h - 6:h - 3].mean(axis=(0, 1))[None, None, :] * 0.92
    # sRGB (view_transform Standard: l'EXR e' lineare)
    srgb = np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(a, 1 / 2.4) - 0.055)
    res = bpy.data.images.new("cielo", W, H, alpha=False)
    rgba = np.concatenate([srgb, np.ones((H, W, 1))], axis=2).astype(np.float32)[::-1]
    res.pixels.foreach_set(rgba.ravel())
    res.filepath_raw = os.path.join(out, "cielo.jpg")
    res.file_format = "JPEG"
    res.save()
    os.remove(tmp)
    # media vicino all'orizzonte (per la nebbia) e posizione del sole
    print("CIELO_OK", res.filepath_raw, "sole riga/col attesi", int(riga), int(col), "trovato", int(ry), int(rx))
    hor = srgb[h - 40:h - 10].mean(axis=(0, 1))
    print("CIELO_ORIZZONTE", "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in hor))
    zen = srgb[:20].mean(axis=(0, 1))
    print("CIELO_ZENIT", "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in zen))


main()
