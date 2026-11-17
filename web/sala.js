/**
 * sala.js - spogliatoio 3D interattivo (Three.js).
 *
 * Carica sala.glb (esportato da scripts/sala.py) e sala.json (rosa e clip) e gestisce:
 *  - passaggio sopra una maglia: esce un poco dall'armadietto e si gira (clip `<Maglia>|hover`);
 *  - clic: la camera si avvicina, la maglia esce e resta appesa di 3/4 (clip `<Maglia>|selezione`),
 *    le altre si scuriscono; trascinando si gira; scheda del giocatore con precedente/successivo;
 *  - filtri a pillola con conteggio: la camera ruota attorno al centro fino al reparto;
 *  - Esc / «Torna alla sala»; frecce per scorrere i giocatori;
 *  - "riduci movimento": niente animazioni, solo passaggi diretti.
 *
 * Uso nel sito:
 *   import { avviaSala } from './sala.js';
 *   const sala = await avviaSala(document.getElementById('sala'), { glb: 'sala.glb', dati: 'sala.json', qualita: 'auto' });
 *   // qualita: 'alta' (ombre + occlusione ambientale), 'bassa' (telefoni) o 'auto'.
 *   sala.seleziona(10); sala.filtra('DIFENSORI'); sala.torna(); sala.distruggi();
 * Three.js va risolto dal bundler (o da un importmap): 'three' e 'three/addons/'.
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { SAOPass } from 'three/addons/postprocessing/SAOPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { Reflector } from 'three/addons/objects/Reflector.js';

const RIDUCI = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const gl = (r, a) => new THREE.Vector3(r * Math.sin(a), 0, -r * Math.cos(a)); // (raggio, angolo) di Blender -> glTF
const dAng = (a, b) => ((b - a + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI;

const CSS = `
.sala{position:relative;width:100%;height:100%;min-height:360px;overflow:hidden;background:#cfd3d8;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#fff;touch-action:none}
.sala canvas{display:block;width:100%;height:100%}
.sala .top{position:absolute;left:0;right:0;top:0;padding:14px 18px;display:flex;flex-direction:column;gap:10px;align-items:center;pointer-events:none;background:linear-gradient(#0009,#0000)}
.sala .titolo{font-weight:700;letter-spacing:.04em;font-size:18px;text-transform:uppercase}
.sala .sotto{font-size:12px;opacity:.85;letter-spacing:.08em;text-transform:uppercase}
.sala .pillole{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;pointer-events:auto}
.sala .pillole button{all:unset;cursor:pointer;padding:7px 14px;border-radius:999px;background:#0008;border:1px solid #fff4;font-size:13px;backdrop-filter:blur(6px)}
.sala .pillole button b{opacity:.7;font-weight:500;margin-left:6px}
.sala .pillole button.attiva{background:#fff;color:#111}
.sala .pillole button:focus-visible,.sala .scheda button:focus-visible{outline:2px solid #6cf;outline-offset:2px}
.sala .etichetta{position:absolute;pointer-events:none;transform:translate(-50%,-130%);padding:6px 10px;border-radius:8px;background:#000c;font-size:13px;white-space:nowrap;opacity:0;transition:opacity .15s}
.sala .etichetta b{font-size:15px;margin-right:6px}
.sala .scheda{position:absolute;right:0;top:0;bottom:0;width:min(340px,86%);padding:26px 24px;background:#0b0d10ee;transform:translateX(105%);transition:transform .45s cubic-bezier(.2,.8,.2,1);display:flex;flex-direction:column;gap:6px}
.sala .scheda.aperta{transform:none}
.sala .scheda .num{font-size:110px;font-weight:800;line-height:1;margin-top:34px}
.sala .scheda .nome{font-size:26px;font-weight:700;text-transform:uppercase}
.sala .scheda .ruolo{opacity:.8;text-transform:uppercase;letter-spacing:.08em;font-size:13px}
.sala .scheda .pos{opacity:.6;font-size:13px;margin-top:4px}
.sala .scheda .nav{display:flex;gap:8px;margin-top:22px}
.sala .scheda button{all:unset;cursor:pointer;padding:9px 14px;border-radius:10px;background:#fff1;border:1px solid #fff3;font-size:14px}
.sala .scheda .torna{margin-top:auto;text-align:center;background:#fff;color:#111;font-weight:600}
.sala .nastro{position:absolute;left:0;right:0;bottom:0;padding:9px 0;background:#000a;font-size:12px;letter-spacing:.14em;text-transform:uppercase;overflow:hidden;white-space:nowrap;pointer-events:none}
.sala .nastro span{display:inline-block;padding-left:100%;animation:sala-scorri 38s linear infinite}
@keyframes sala-scorri{to{transform:translateX(-100%)}}
@media (prefers-reduced-motion:reduce){.sala .nastro span{animation:none;padding-left:18px}.sala .scheda{transition:none}}
.sala .carico{position:absolute;inset:0;display:grid;place-items:center;background:#0b0d10;font-size:15px;letter-spacing:.1em;transition:opacity .5s}
.sala .top,.sala .nastro,.sala .etichetta{transition:opacity .7s}
.sala.intro .top,.sala.intro .nastro,.sala.intro .etichetta{opacity:0;pointer-events:none}
.sala .salta{all:unset;cursor:pointer;position:absolute;right:16px;bottom:48px;padding:8px 16px;border-radius:999px;background:#0009;border:1px solid #fff5;font-size:13px;opacity:0;pointer-events:none;transition:opacity .5s;backdrop-filter:blur(6px)}
.sala.intro.corre .salta{opacity:1;pointer-events:auto}
.sala .intro-video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;pointer-events:none;transition:opacity 1.2s;background:#000}
@media (max-aspect-ratio:1/1){.sala .scheda{top:auto;left:0;width:100%;max-height:46%;padding:18px 20px;transform:translateY(105%)}.sala .scheda.aperta{transform:none}.sala .scheda .num{font-size:64px;margin-top:0}.sala .scheda .nome{font-size:20px}}
`;

export async function avviaSala(host, opz = {}) {
  const urlGlb = opz.glb || 'sala.glb';
  const urlDati = opz.dati || 'sala.json';
  if (!document.getElementById('sala-css')) {
    const st = document.createElement('style');
    st.id = 'sala-css';
    st.textContent = CSS;
    document.head.appendChild(st);
  }
  host.classList.add('sala');
  host.innerHTML = `
    <div class="top"><div class="titolo"></div><div class="sotto"></div><div class="pillole" role="group" aria-label="Reparti"></div></div>
    <div class="etichetta"></div>
    <aside class="scheda" aria-live="polite">
      <div class="num"></div><div class="nome"></div><div class="ruolo"></div><div class="pos"></div>
      <div class="nav"><button class="prec" aria-label="Giocatore precedente">‹ Precedente</button><button class="succ" aria-label="Giocatore successivo">Successivo ›</button></div>
      <button class="torna">Torna alla sala (Esc)</button>
    </aside>
    <div class="nastro"><span></span></div>
    <button class="salta">Salta l'ingresso ›</button>
    <div class="carico">Carico la sala…</div>`;
  const q = (s) => host.querySelector(s);

  const dati = await (await fetch(urlDati)).json();
  const caricatore = new GLTFLoader();
  const [gltf, tunnelGltf, tunnelDati] = await Promise.all([
    caricatore.loadAsync(urlGlb),
    opz.tunnel ? caricatore.loadAsync(opz.tunnel).catch((e) => { console.warn('tunnel non caricato', e); return null; }) : null,
    opz.tunnel ? fetch(opz.percorso || 'tunnel.json').then((r) => r.json()).catch(() => null) : null,
  ]);

  // ---- scena
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.7;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  host.insertBefore(renderer.domElement, host.firstChild);
  const scena = new THREE.Scene();
  scena.background = new THREE.Color(0x9aa0a6);
  const pm = new THREE.PMREMGenerator(renderer);
  scena.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
  const debole = window.matchMedia('(pointer: coarse)').matches || (navigator.hardwareConcurrency || 8) <= 4;
  const alta = opz.qualita === 'alta' || ((opz.qualita || 'auto') === 'auto' && !debole);
  scena.environmentIntensity = alta ? 0.28 : 0.8;
  // luce dal centro del soffitto: la sala e' circolare, ogni armadietto la riceve dalla stessa parte
  const centro = new THREE.PointLight(0xfff3e6, alta ? 22 : 0, 16, 1.8);
  centro.position.set(0, 2.8, 0);
  if (alta) {
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    centro.castShadow = true;
    centro.shadow.mapSize.set(2048, 2048);
    centro.shadow.bias = -0.0008;
    centro.shadow.normalBias = 0.03;
    centro.shadow.radius = 4;
  }
  const dall = new THREE.DirectionalLight(0xffffff, alta ? 0.18 : 1.1);
  dall.position.set(0, 6, 8);
  scena.add(centro, dall, new THREE.HemisphereLight(0xffffff, 0xcfd3d8, alta ? 0.18 : 0.5));
  scena.add(gltf.scene);
  const SENZA_OMBRA = /^Fisso_(Soffitto|SoffittoC|Faretto|Parete|Pavimento)/;
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    o.castShadow = alta && !SENZA_OMBRA.test(o.name);
    o.receiveShadow = alta;
  });
  // pavimento lucido: il riflesso della sala (piano a specchio) si fonde sopra il pavimento del .glb
  let specchio = null;
  if (alta) {
    const sh = Reflector.ReflectorShader;
    specchio = new Reflector(new THREE.CircleGeometry(dati.raggio + 0.3, 64), {
      textureWidth: 1024, textureHeight: 1024, clipBias: 0.003,
      shader: {
        name: 'RiflessoPavimento',
        uniforms: { color: { value: null }, tDiffuse: { value: null }, textureMatrix: { value: null }, forza: { value: 0.30 } },
        vertexShader: sh.vertexShader,
        fragmentShader: `
          uniform sampler2D tDiffuse; uniform float forza; varying vec4 vUv;
          void main() {
            vec4 uv = vUv; vec2 p = uv.xy / uv.w;
            vec3 c = vec3(0.0); float w = 0.0;
            for (int i = -2; i <= 2; i++) for (int j = -2; j <= 2; j++) {
              float k = 1.0 / (1.0 + float(i*i + j*j));
              c += texture2D(tDiffuse, p + vec2(float(i), float(j)) * 0.0018).rgb * k; w += k;
            }
            gl_FragColor = vec4(c / w, forza);
          }`,
      },
    });
    specchio.material.transparent = true;
    specchio.material.depthWrite = false;
    specchio.rotation.x = -Math.PI / 2;
    specchio.position.y = 0.004;
    specchio.renderOrder = 1;
    scena.add(specchio);
  }
  const cam = new THREE.PerspectiveCamera(80, 16 / 9, 0.1, 60);
  let composer = null;
  if (alta) {
    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scena, cam));
    const sao = new SAOPass(scena, cam);
    sao.params.saoBias = 0.5;
    sao.params.saoIntensity = 0.018;
    sao.params.saoScale = 3;
    sao.params.saoKernelRadius = 24;
    sao.params.saoBlurRadius = 6;
    composer.addPass(sao);
    composer.addPass(new OutputPass());
  }
  const disegna = () => (composer ? composer.render() : renderer.render(scena, cam));

  // ---- maglie: gruppo che gira per il trascinamento, materiali propri per scurirle
  const maglie = new Map();
  const mixer = new THREE.AnimationMixer(gltf.scene);
  const clip = new Map(gltf.animations.map((c) => [c.name, c]));
  for (const g of dati.giocatori) {
    const nodo = gltf.scene.getObjectByName(g.maglia);
    const gira = new THREE.Group();
    gira.name = 'gira';
    [...nodo.children].forEach((c) => gira.add(c));
    nodo.add(gira);
    const mats = [];
    const meshes = [];
    gira.traverse((o) => {
      if (!o.isMesh) return;
      o.material = o.material.clone();
      if (o.material.normalMap) o.material.normalMap.anisotropy = renderer.capabilities.getMaxAnisotropy();
      o.material.userData.base = o.material.color.clone();
      mats.push(o.material);
      meshes.push(o);
      o.userData.maglia = g.numero;
    });
    const mk = (n) => {
      const a = mixer.clipAction(clip.get(n), nodo);
      a.setLoop(THREE.LoopOnce, 1);
      a.clampWhenFinished = true;
      return a;
    };
    maglie.set(g.numero, {
      g, nodo, gira, mats, meshes, hover: mk(g.clip.hover), sel: mk(g.clip.selezione),
      k: 1, kTarget: 1, spin: 0,
    });
  }
  mixer.addEventListener('finished', (e) => {
    if (e.direction < 0) e.action.stop(); // tornata a riposo
  });
  const tutteMesh = [...maglie.values()].flatMap((m) => m.meshes);

  // ---- camera: stato in coordinate polari attorno al centro della sala
  const R = dati.raggio;
  const mediaPhi = (lista) => Math.atan2(
    lista.reduce((s, g) => s + Math.sin(g.phi), 0), lista.reduce((s, g) => s + Math.cos(g.phi), 0));
  const VISTE = {
    // la camera sta sulla porta del tunnel (phi = 180) e guarda l'arco dei titolari
    sala: { a: Math.PI, r: 2.4, y: 1.5, ta: mediaPhi(dati.giocatori.filter((g) => g.titolare)), tr: R - 0.3, ty: 1.45, fov: 66 },
  };
  const vistaReparto = (nome) => {
    const lista = dati.giocatori.filter((g) => g.reparto === nome);
    const f = mediaPhi(lista);
    return { a: f + Math.PI, r: 2.1, y: 1.55, ta: f, tr: R - 0.5, ty: 1.5, fov: 62 };
  };
  const vistaMaglia = (numero) => {
    const f = maglie.get(numero).g.phi;
    return { a: f, r: 1.0, y: 1.5, ta: f, tr: R - 1.05, ty: 1.42, fov: 44 };
  };
  let vista = { ...VISTE.sala };
  let tween = null;
  let ora = performance.now();
  // fov verticale dichiarato per 16:9; in verticale (9:16) si stringe l'angolo orizzontale e si alza quello verticale
  const fovEff = (v) => {
    if (cam.aspect >= 1) return v.fov;
    const orizz = 2 * Math.atan(Math.tan((v.fov * Math.PI) / 360) * (16 / 9));
    return Math.min(100, (2 * Math.atan(Math.tan((orizz * 0.6) / 2) / cam.aspect) * 180) / Math.PI);
  };
  const applica = (v) => {
    const p = gl(v.r, v.a);
    cam.position.set(p.x, v.y, p.z);
    const t = gl(v.tr, v.ta);
    cam.lookAt(t.x, v.ty, t.z);
    const f = fovEff(v);
    if (cam.fov !== f) { cam.fov = f; cam.updateProjectionMatrix(); }
  };
  const vai = (a, ms = 1100) => {
    const da = { ...vista };
    if (RIDUCI() || ms <= 0) { vista = { ...a }; tween = null; applica(vista); return; }
    tween = { da, a, t0: ora, ms };
  };
  const passoTween = (now) => {
    if (!tween) return;
    const u = Math.min(1, (now - tween.t0) / tween.ms), e = ease(u);
    const { da, a } = tween;
    vista = {
      a: da.a + dAng(da.a, a.a) * e, r: da.r + (a.r - da.r) * e, y: da.y + (a.y - da.y) * e,
      ta: da.ta + dAng(da.ta, a.ta) * e, tr: da.tr + (a.tr - da.tr) * e, ty: da.ty + (a.ty - da.ty) * e,
      fov: da.fov + (a.fov - da.fov) * e,
    };
    applica(vista);
    if (u >= 1) tween = null;
  };

  // ---- percorso: dal bordo campo, lungo il tunnel, fino alla posa iniziale della sala
  // API: sala.percorso.progresso(p) (0..1, anche a scorrimento), .avvia({durata}), .collegaScorrimento(el),
  //      .introduzione() (video del drone se c'e', poi il tunnel), .ferma(), .attivo
  let perc = null;
  if (tunnelGltf && tunnelDati) {
    const V3 = THREE.Vector3;
    const GAIN = 1.3;
    tunnelGltf.scene.traverse((o) => {
      if (!o.isMesh) return;
      const m = o.material;
      const b = new THREE.MeshBasicMaterial({ map: m.map || null, vertexColors: !!o.geometry.attributes.color, side: m.side });
      b.color.copy(m.color).multiplyScalar(/Luce/.test(m.name) ? 3.2 : GAIN);
      o.material = b;
      o.castShadow = o.receiveShadow = false;
      if (m.map) m.map.anisotropy = renderer.capabilities.getMaxAnisotropy();
    });
    scena.add(tunnelGltf.scene);
    // cielo e foschia in lontananza (la sala sta entro 12 m: non ne risente)
    const cv = document.createElement('canvas');
    cv.width = 4; cv.height = 256;
    const cx = cv.getContext('2d'), gr = cx.createLinearGradient(0, 0, 0, 256);
    gr.addColorStop(0, '#5f93d1'); gr.addColorStop(0.55, '#a9c9e8'); gr.addColorStop(1, '#dfe9f2');
    cx.fillStyle = gr; cx.fillRect(0, 0, 4, 256);
    const cielo = new THREE.CanvasTexture(cv);
    cielo.colorSpace = THREE.SRGBColorSpace;
    scena.background = cielo;
    scena.fog = new THREE.Fog(0xcfdfee, 45, 120);
    const S = VISTE.sala;
    const fin = { p: gl(S.r, S.a), t: gl(S.tr, S.ta) };
    const pos = [...tunnelDati.percorso.map((k) => new V3(...k.p)), new V3(fin.p.x, S.y, fin.p.z)];
    const tgt = [...tunnelDati.percorso.map((k) => new V3(...k.t)), new V3(fin.t.x, S.ty, fin.t.z)];
    const fovs = [...tunnelDati.percorso.map((k) => k.fov), S.fov];
    const cp = new THREE.CatmullRomCurve3(pos, false, 'centripetal');
    const ct = new THREE.CatmullRomCurve3(tgt, false, 'centripetal');
    const lung = cp.getLength();
    const liscio = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
    const tmp = new V3(), tmpT = new V3();
    const bottone = q('.salta');
    let video = null;
    if (opz.video) {
      video = document.createElement('video');
      Object.assign(video, { className: 'intro-video', muted: true, playsInline: true, preload: 'auto', poster: opz.video.poster || '' });
      video.setAttribute('playsinline', '');
      video.src = opz.video.src;
      host.appendChild(video);
    }
    perc = {
      esiste: true, attivo: false, p: 1, anim: null, lunghezza: lung,
      applica() {
        const p = this.p;
        const t = cp.getUtoTmapping(p);
        cp.getPoint(t, tmp); ct.getPoint(t, tmpT);
        const env = RIDUCI() ? 0 : liscio(0, 0.03, p) * (1 - liscio(0.9, 0.995, p));
        const d = (p * lung) / (tunnelDati.passo || 0.75);
        tmp.y += env * (tunnelDati.ampiezza_bob || 0.014) * Math.sin(2 * Math.PI * d);
        tmp.x += env * 0.006 * Math.sin(Math.PI * d);
        cam.position.copy(tmp);
        cam.lookAt(tmpT);
        const k = t * (fovs.length - 1), i = Math.min(fovs.length - 2, Math.floor(k));
        const f = fovEff({ fov: fovs[i] + (fovs[i + 1] - fovs[i]) * (k - i) });
        if (cam.fov !== f) { cam.fov = f; cam.updateProjectionMatrix(); }
      },
      progresso(p) {
        p = Math.min(1, Math.max(0, p));
        this.p = p;
        if (p >= 1) {
          if (this.attivo) {
            this.attivo = false;
            host.classList.remove('intro', 'corre');
            vista = { ...VISTE.sala }; tween = null; applica(vista);
          }
          return;
        }
        if (!this.attivo) {
          if (scelta !== null) api.torna();
          sopra = null; etichetta.style.opacity = 0;
          this.attivo = true;
          host.classList.add('intro');
        }
        this.applica();
      },
      avvia(o = {}) {
        const durata = o.durata || 14000, da = o.da || 0;
        if (RIDUCI()) { this.progresso(1); return Promise.resolve(); }
        this.progresso(Math.min(da, 0.9999));
        host.classList.add('corre');
        return new Promise((res) => { this.anim = { t: 0, durata, da, res }; });
      },
      ferma() {
        if (this.anim) { const r = this.anim.res; this.anim = null; host.classList.remove('corre'); r(); }
      },
      salta() { this.ferma(); this.progresso(1); },
      async introduzione() {
        if (RIDUCI()) { this.progresso(1); return; }
        this.progresso(0);
        if (video) {
          video.style.opacity = 1;
          try { await video.play(); await new Promise((res) => { video.addEventListener('ended', res, { once: true }); video.addEventListener('error', res, { once: true }); this._saltaVideo = res; }); } catch (e) { /* senza video si parte dal tunnel */ }
          video.style.opacity = 0;
        }
        await this.avvia({ durata: opz.durataPercorso || 14000 });
      },
      collegaScorrimento(el = host.parentElement) {
        const f = () => {
          const r = el.getBoundingClientRect();
          const tot = r.height - window.innerHeight;
          this.ferma();
          this.progresso(tot > 0 ? -r.top / tot : 1);
        };
        window.addEventListener('scroll', f, { passive: true });
        f();
        return () => window.removeEventListener('scroll', f);
      },
      passo(dt) {
        if (!this.anim) return;
        const a = this.anim;
        a.t += dt * 1000;
        const u = Math.min(1, a.t / a.durata);
        this.progresso(a.da + (1 - a.da) * ease(u));
        if (u >= 1) { this.anim = null; host.classList.remove('corre'); a.res(); }
      },
    };
    bottone.addEventListener('click', () => { if (video && perc._saltaVideo) perc._saltaVideo(); perc.salta(); });
  }

  // ---- clip avanti / indietro
  const corri = (azione, dir, da = null) => {
    if (RIDUCI()) {
      azione.enabled = true; azione.play(); azione.paused = true;
      azione.time = dir > 0 ? azione.getClip().duration : 0;
      mixer.update(0);
      if (dir < 0) azione.stop();
      return;
    }
    azione.enabled = true; azione.paused = false;
    azione.setEffectiveWeight(1);
    azione.setEffectiveTimeScale(dir);
    if (da !== null) azione.time = da;
    else if (dir > 0 && !azione.isRunning()) azione.time = 0;
    azione.play();
  };
  const progresso = (azione) => (azione.isRunning() || azione.enabled
    ? Math.min(1, Math.max(0, azione.time / azione.getClip().duration)) : 0);

  // ---- stato
  let sopra = null;      // numero con il puntatore sopra
  let scelta = null;     // numero selezionato
  let filtro = null;     // nome del reparto o null
  const pill = q('.pillole');
  q('.titolo').textContent = dati.squadra;
  q('.sotto').textContent = 'Prima squadra · stagione ' + dati.stagione;
  q('.nastro span').textContent = ('Passa su una maglia · clicca per staccarla · ' + dati.squadra + ' ').repeat(3);

  const ruolo = (n) => n.charAt(0) + n.slice(1).toLowerCase();
  const aggiungiPill = (testo, n, valore) => {
    const b = document.createElement('button');
    b.innerHTML = `${testo}<b>${n}</b>`;
    b.addEventListener('click', () => { api.filtra(valore); });
    b.dataset.v = valore || '';
    pill.appendChild(b);
  };
  aggiungiPill('Tutti', dati.giocatori.length, null);
  for (const r of dati.reparti) aggiungiPill(ruolo(r), dati.giocatori.filter((g) => g.reparto === r).length, r);
  const segnaPill = () => [...pill.children].forEach((b) => b.classList.toggle('attiva', (b.dataset.v || null) === filtro));
  segnaPill();

  const scurisci = () => {
    for (const m of maglie.values()) {
      let k = 1;
      if (scelta !== null) k = m.g.numero === scelta ? 1 : 0.28;
      else if (filtro) k = m.g.reparto === filtro ? 1 : 0.55;
      m.kTarget = k;
    }
  };

  const scheda = q('.scheda');
  const mostraScheda = (n) => {
    const m = maglie.get(n);
    q('.num').textContent = n;
    q('.nome').textContent = m.g.nome;
    q('.ruolo').textContent = ruolo(m.g.reparto) + (m.g.titolare ? ' · titolare' : '');
    q('.pos').textContent = (dati.giocatori.indexOf(m.g) + 1) + ' / ' + dati.giocatori.length;
    scheda.classList.add('aperta');
  };

  const api = {
    seleziona(n) {
      if (!maglie.has(n)) return;
      if (scelta !== null && scelta !== n) this._chiudi(scelta, false);
      const m = maglie.get(n);
      if (scelta === n) return;
      let da = 0;
      if (sopra === n) { da = progresso(m.hover) * 0.25 * m.sel.getClip().duration; m.hover.stop(); }
      scelta = n; sopra = null;
      corri(m.sel, 1, da);
      vai(vistaMaglia(n), 1300);
      scurisci();
      mostraScheda(n);
      etichetta.style.opacity = 0;
    },
    _chiudi(n, camera = true) {
      const m = maglie.get(n);
      if (!m) return;
      corri(m.sel, -1, m.sel.isRunning() || m.sel.enabled ? undefined : m.sel.getClip().duration);
      m.gira.rotation.y = 0; m.spin = 0;
    },
    torna() {
      if (scelta === null) return;
      this._chiudi(scelta);
      scelta = null;
      scheda.classList.remove('aperta');
      vai(filtro ? vistaReparto(filtro) : VISTE.sala, 1100);
      scurisci();
    },
    filtra(nome) {
      if (scelta !== null) this.torna();
      filtro = nome || null;
      segnaPill();
      scurisci();
      vai(filtro ? vistaReparto(filtro) : VISTE.sala, 1100);
    },
    prossimo(d) {
      if (scelta === null) return;
      const l = dati.giocatori, i = l.findIndex((g) => g.numero === scelta);
      this.seleziona(l[(i + d + l.length) % l.length].numero);
    },
    distruggi() {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', ridim);
      window.removeEventListener('keydown', tasto);
      renderer.dispose();
      host.innerHTML = '';
    },
  };
  q('.torna').addEventListener('click', () => api.torna());
  q('.prec').addEventListener('click', () => api.prossimo(-1));
  q('.succ').addEventListener('click', () => api.prossimo(1));
  const tasto = (e) => {
    if (e.key === 'Escape') api.torna();
    else if (e.key === 'ArrowRight') api.prossimo(1);
    else if (e.key === 'ArrowLeft') api.prossimo(-1);
  };
  window.addEventListener('keydown', tasto);

  // ---- puntatore: hover, clic, trascinamento
  const etichetta = q('.etichetta');
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let px = 0, py = 0, sporco = false, giu = null;
  const cerca = () => {
    const h = ray.intersectObjects(tutteMesh, false)[0];
    return h ? h.object.userData.maglia : null;
  };
  renderer.domElement.addEventListener('pointermove', (e) => {
    const r = renderer.domElement.getBoundingClientRect();
    px = e.clientX - r.left; py = e.clientY - r.top;
    ndc.set((px / r.width) * 2 - 1, -(py / r.height) * 2 + 1);
    sporco = true;
    if (giu && scelta !== null) {
      const m = maglie.get(scelta);
      m.spin += (e.clientX - giu.x) * 0.012;
      giu.x = e.clientX;
      giu.mosso = true;
    }
  });
  renderer.domElement.addEventListener('pointerdown', (e) => { giu = { x: e.clientX, mosso: false }; });
  window.addEventListener('pointerup', () => { setTimeout(() => { giu = null; }, 0); });
  renderer.domElement.addEventListener('click', () => {
    if (perc && perc.attivo) return;
    if (giu && giu.mosso) return;
    scena.updateMatrixWorld();
    cam.updateMatrixWorld();
    ray.setFromCamera(ndc, cam);
    const n = cerca();
    if (n !== null && n !== scelta) api.seleziona(n);
  });
  const aggiornaHover = () => {
    if (!sporco || scelta !== null) return;
    sporco = false;
    scena.updateMatrixWorld();
    cam.updateMatrixWorld();
    ray.setFromCamera(ndc, cam);
    const n = cerca();
    if (n === sopra) {
      if (n !== null) { etichetta.style.left = px + 'px'; etichetta.style.top = py + 'px'; }
      return;
    }
    if (sopra !== null) corri(maglie.get(sopra).hover, -1);
    sopra = n;
    if (n !== null) {
      const m = maglie.get(n);
      corri(m.hover, 1);
      etichetta.innerHTML = `<b>${n}</b>${m.g.nome} · ${ruolo(m.g.reparto)}`;
      etichetta.style.left = px + 'px'; etichetta.style.top = py + 'px';
      etichetta.style.opacity = 1;
    } else {
      etichetta.style.opacity = 0;
    }
    renderer.domElement.style.cursor = n !== null ? 'pointer' : '';
  };

  // ---- ciclo
  const ridim = () => {
    const w = host.clientWidth || 800, h = host.clientHeight || 450;
    renderer.setSize(w, h, false);
    if (composer) composer.setSize(w, h);
    cam.aspect = w / h;
    cam.updateProjectionMatrix();
    if (perc && perc.attivo) perc.applica(); else applica(vista);
  };
  window.addEventListener('resize', ridim);
  let ultimo = performance.now();
  let raf = 0;
  const passo = (now, dt) => {
    ora = now;
    if (perc && perc.attivo) {
      perc.passo(dt);
    } else {
      passoTween(now);
      aggiornaHover();
    }
    mixer.update(dt);
    for (const m of maglie.values()) {
      if (Math.abs(m.k - m.kTarget) > 0.002) {
        m.k += (m.kTarget - m.k) * Math.min(1, dt * 8);
        for (const mt of m.mats) mt.color.copy(mt.userData.base).multiplyScalar(m.k);
      }
      if (m.g.numero === scelta) m.gira.rotation.y += (m.spin - m.gira.rotation.y) * Math.min(1, dt * 10);
    }
  };
  const giro = (now) => {
    raf = requestAnimationFrame(giro);
    const dt = Math.min(0.25, (now - ultimo) / 1000);
    ultimo = now;
    passo(now, dt);
    disegna();
  };
  applica(vista);
  ridim();
  raf = requestAnimationFrame(giro);
  const carico = q('.carico');
  carico.style.opacity = 0;
  setTimeout(() => carico.remove(), 600);
  const stat = () => {
    let tri = 0, mesh = 0;
    const per = {};
    scena.traverse((o) => {
      if (!o.isMesh) return;
      const t = (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3;
      tri += t; mesh++;
      const k = /^Maglia_/.test(o.parent && o.parent.parent ? o.parent.parent.name : '') ? 'maglie' : (o.name.split('_')[0] || 'altro');
      per[k] = (per[k] || 0) + t;
    });
    return { triangoli: Math.round(tri), mesh, per, chiamate: mesh };
  };
  Object.assign(api, { THREE, scena, cam, maglie, renderer, dati, stat, percorso: perc, // per i collaudi: avanza di `ms` millisecondi senza aspettare il disegno
    _avanza: (ms) => { passo(ora + ms, ms / 1000); disegna(); } });
  return api;
}
