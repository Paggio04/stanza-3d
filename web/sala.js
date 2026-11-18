/**
 * sala.js - spogliatoio 3D interattivo (Three.js).
 *
 * Carica sala.glb (esportato da scripts/sala.py) e sala.json (rosa e clip) e gestisce:
 *  - passaggio sopra una maglia: esce un poco dall'armadietto e si gira (molla `hover` di sala.json);
 *  - clic: la camera si avvicina, la maglia esce e resta appesa di 3/4 (molla `selezione`, oscillazione della gruccia, ondeggio del tessuto),
 *    le altre si scuriscono; trascinando si gira; scheda del giocatore con precedente/successivo;
 *  - filtri a pillola con conteggio: la camera ruota attorno al centro fino al reparto;
 *  - Esc / «Torna alla sala»; frecce per scorrere i giocatori;
 *  - "riduci movimento": niente animazioni, solo passaggi diretti.
 *
 * Uso nel sito:
 *   import { avviaSala } from './sala.js';
 *   const sala = await avviaSala(document.getElementById('sala'), { glb: 'sala.glb', glbBassa: 'sala_bassa.glb', dati: 'sala.json', qualita: 'auto',
 *     tunnel: 'tunnel.glb', percorso: 'tunnel.json' });   // tunnel e percorso: facoltativi
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
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

const RIDUCI = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
// Spazio percorso (0..S) al tempo t (s): rampa coseno in partenza e in arrivo (accelerazione continua), crociera costante in mezzo.
// Prima: ease cubico su tutta la durata = 8 m/s a meta' (corsa), ora crociera a passo svelto.
const PROFILO = (t, T, S, ta) => {
  t = Math.min(T, Math.max(0, t));
  const vc = S / (T - ta), ramp = (x) => vc * (x / 2 - (ta / (2 * Math.PI)) * Math.sin((Math.PI * x) / ta));
  if (t < ta) return ramp(t);
  if (t > T - ta) return S - ramp(T - t);
  return (vc * ta) / 2 + vc * (t - ta);
};
const gl = (r, a) => new THREE.Vector3(r * Math.sin(a), 0, -r * Math.cos(a)); // (raggio, angolo) di Blender -> glTF
const dAng = (a, b) => ((b - a + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI;

const CSS = `
.sala{position:relative;width:100%;height:100%;min-height:360px;overflow:hidden;background:#cfd3d8;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#fff;touch-action:pan-y}
.sala canvas{display:block;width:100%;height:100%} /* HD: il ridimensionamento usa clientWidth/Height * pixelRatio */
.sala .top{position:absolute;left:0;right:0;top:0;padding:14px 18px;display:flex;flex-direction:column;gap:10px;align-items:center;pointer-events:none;background:linear-gradient(#0009,#0000);z-index:3}
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
.sala.intro::after{content:'';position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse at center,transparent 58%,rgba(0,0,0,.30) 100%)}
.sala .intro-video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;pointer-events:none;transition:opacity 1.2s;background:#000}
@media (max-aspect-ratio:1/1){.sala .scheda{top:auto;bottom:32px;left:0;width:100%;max-height:46%;padding:18px 20px;transform:translateY(105%)}.sala .scheda.aperta{transform:none}.sala .scheda .num{font-size:64px;margin-top:0}.sala .scheda .nome{font-size:20px}}
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

  const debole = window.matchMedia('(pointer: coarse)').matches || (navigator.hardwareConcurrency || 8) <= 4;
  const esplicita = opz.qualita === 'alta'; // ?q=alta: l'utente chiede il massimo e accetta il costo
  const alta = esplicita || ((opz.qualita || 'auto') === 'auto' && !debole);
  // In auto si parte leggeri (niente freeze): ombre 1024, specchio 1024, niente SAO. Il massimo solo con ?q=alta.
  const dati = await (await fetch(urlDati)).json();
  const caricatore = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  const [gltf, tunnelGltf, tunnelDati] = await Promise.all([
    caricatore.loadAsync(!alta && opz.glbBassa ? opz.glbBassa : urlGlb),
    opz.tunnel ? caricatore.loadAsync(!alta && opz.tunnelBassa ? opz.tunnelBassa : opz.tunnel).catch((e) => { console.warn('tunnel non caricato', e); return null; }) : null,
    opz.tunnel ? fetch(opz.percorso || 'tunnel.json').then((r) => r.json()).catch(() => null) : null,
  ]);

  // ---- scena
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, esplicita ? 3 : alta ? 2 : 1.5)); // fluidita: in auto mai sopra 2
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = alta ? 0.9 : 0.9; // realismo: 1.0 bruciava i bianchi (era tutto slavato)
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  host.insertBefore(renderer.domElement, host.firstChild);
  const scena = new THREE.Scene();
  scena.background = new THREE.Color(0x9aa0a6);
  const pm = new THREE.PMREMGenerator(renderer);
  scena.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
  scena.environmentIntensity = alta ? 0.30 : 0.8; // realismo: 0.38 appiattiva i bianchi in alta
  // luce dal centro del soffitto: la sala e' circolare, ogni armadietto la riceve dalla stessa parte
  const centro = new THREE.PointLight(0xfff3e6, alta ? 18 : 0, 16, 1.8);
  centro.position.set(0, 2.8, 0);
  if (alta) {
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    centro.castShadow = true;
    const lato = esplicita ? 4096 : 2048; // fluidita: 4096 solo con ?q=alta, in auto 2048 bastano
    centro.shadow.mapSize.set(lato, lato);
    centro.shadow.bias = -0.0005;
    centro.shadow.normalBias = 0.02;
    centro.shadow.radius = esplicita ? 2 : 4; // HD: raggio piu stretto in alta = bordi piu definiti
  }
  const dall = new THREE.DirectionalLight(0xffffff, alta ? 0.18 : 1.1);
  dall.position.set(0, 6, 8);
  scena.add(centro, dall, new THREE.HemisphereLight(0xffffff, 0xcfd3d8, alta ? 0.18 : 0.5));
  const faro = new THREE.PointLight(0xfff0dd, 0, 3.2, 2);       // si accende sulla maglia scelta
  scena.add(faro);
  const nodoLuce = (m) => {
    const p = m.nodo.getWorldPosition(new THREE.Vector3());
    const dentro = new THREE.Vector3(-p.x, 0, -p.z).normalize();
    faro.position.set(p.x + dentro.x * 0.9, p.y + 0.35, p.z + dentro.z * 0.9);
  };
  scena.add(gltf.scene);
  const SENZA_OMBRA = /^Fisso_(Soffitto|SoffittoC|Faretto|Parete|Pavimento)/;
  // HD: anisotropia massima su tutte le texture della sala (non solo maglie): legno e pavimento restano nitidi di sbieco
  const maxAniso = renderer.capabilities.getMaxAnisotropy();
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    const ms = Array.isArray(o.material) ? o.material : [o.material];
    for (const mm of ms) {
      const maps = [mm.map, mm.roughnessMap, mm.metalnessMap, mm.normalMap, mm.emissiveMap];
      for (const t of maps) if (t && t.isTexture) t.anisotropy = maxAniso;
    }
  });
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    o.castShadow = alta && !SENZA_OMBRA.test(o.name);
    o.receiveShadow = alta;
  });
  // pavimento lucido: il riflesso della sala (piano a specchio) si fonde sopra il pavimento del .glb
  let specchio = null;
  if (alta) {
    const sh = Reflector.ReflectorShader;
    const latoSp = esplicita ? 2048 : 1024; // fluidita: specchio 2048 solo con ?q=alta, in auto 1024 (era il freeze)
    specchio = new Reflector(new THREE.CircleGeometry(dati.raggio + 0.3, 96), { // HD: 96 segmenti = bordo piu liscio
      textureWidth: latoSp, textureHeight: latoSp, clipBias: 0.003,
      shader: {
        name: 'RiflessoPavimento',
        uniforms: { color: { value: null }, tDiffuse: { value: null }, textureMatrix: { value: null }, forza: { value: 0.20 } }, // HD: 0.20, prima 0.30 troppo lattiginoso
        vertexShader: sh.vertexShader,
        fragmentShader: `
          uniform sampler2D tDiffuse; uniform float forza; varying vec4 vUv;
          void main() {
            vec4 uv = vUv; vec2 p = uv.xy / uv.w;
            vec3 c = vec3(0.0); float w = 0.0;
            for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++) { // HD: sfocatura 3x3 (prima 5x5) = riflesso piu nitido
              float k = 1.0 / (1.0 + float(i*i + j*j));
              c += texture2D(tDiffuse, p + vec2(float(i), float(j)) * 0.0012).rgb * k; w += k;
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
  const cam = new THREE.PerspectiveCamera(80, 16 / 9, 0.1, 220);
  let composer = null;
  const SAO_INTENSITA = 0.022;
  let saoPass = null; // HD: serve per la discesa automatica (spegni SAO se il telefono non regge)
  if (esplicita) { // fluidita: SAO solo con ?q=alta, in auto niente (era il freeze ogni secondo)
    composer = new EffectComposer(renderer);
    composer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 3)); // HD: anche il composer in alta (altrimenti SAO resta a 1x)
    composer.addPass(new RenderPass(scena, cam));
    saoPass = new SAOPass(scena, cam);
    saoPass.params.saoBias = 0.5;
    saoPass.params.saoIntensity = SAO_INTENSITA; // HD: occlusione un filo piu presente (prima 0.018, troppo leggera)
    saoPass.params.saoScale = 3;
    saoPass.params.saoKernelRadius = 24;
    saoPass.params.saoBlurRadius = 6;
    composer.addPass(saoPass);
    composer.addPass(new OutputPass());
  }
  const disegna = () => (composer ? composer.render() : renderer.render(scena, cam));

  // ---- maglie: gruppo che gira per il trascinamento, materiali propri (scurimento, ondeggio del tessuto)
  // I gesti (hover, selezione) sono molle pilotate da sala.json: niente clip da riavvolgere, tutto interrompibile.
  const GESTI = dati.gesti || {
    hover: { dy: 0.2, dr: 0.16, dz: 0 }, selezione: { dy: 0.85, dr: 0.72, dz: 0.04 },
    molle: { hover: { w: 16, z: 0.55 }, selezione: { w: 10, z: 0.62 }, oscillazione: { w: 5.4, z: 0.14, k: 0.35 } },
    altezza_gancio: 0.06,
  };
  const tempo = { t: 0 };
  const ondeggia = (mat) => {
    mat.onBeforeCompile = (sh) => {
      sh.uniforms.uOnda = { value: 0 };
      sh.uniforms.uT = { value: 0 };
      mat.userData.sh = sh;
      sh.vertexShader = sh.vertexShader
        .replace('#include <common>', '#include <common>\nuniform float uOnda;\nuniform float uT;')
        .replace('#include <begin_vertex>', `#include <begin_vertex>
          float prof = clamp(-position.y / 0.72, 0.0, 1.0);
          float f = prof * prof * uOnda;
          transformed.z += f * 0.016 * sin(uT * 5.2 + position.x * 11.0 + position.y * 5.0);
          transformed.x += f * 0.010 * sin(uT * 3.1 + position.y * 7.0 + position.x * 2.0);`);
    };
    mat.customProgramCacheKey = () => 'ondeggia';
  };
  const maglie = new Map();
  for (const g of dati.giocatori) {
    // `corpo` e' la mesh della maglia (con le scritte e la gruccia come figli); `nodo` e' il gruppo che la porta
    // (posa, molle) e `gira` quello che ruota col trascinamento: tutto il corpo, non solo i figli.
    const corpo = gltf.scene.getObjectByName(g.maglia);
    const nodo = new THREE.Group();
    nodo.name = g.maglia + '_posa';
    nodo.position.copy(corpo.position);
    nodo.quaternion.copy(corpo.quaternion);
    nodo.scale.copy(corpo.scale);
    corpo.parent.add(nodo);
    corpo.position.set(0, 0, 0); corpo.quaternion.identity(); corpo.scale.set(1, 1, 1);
    const gira = new THREE.Group();
    gira.name = 'gira';
    nodo.add(gira);
    gira.add(corpo);
    const mats = [];
    const meshes = [];
    gira.traverse((o) => {
      if (!o.isMesh) return;
      o.material = o.material.clone();
      ondeggia(o.material);
      if (o.material.normalMap) o.material.normalMap.anisotropy = renderer.capabilities.getMaxAnisotropy();
      o.material.userData.base = o.material.color.clone();
      mats.push(o.material);
      meshes.push(o);
      o.userData.maglia = g.numero;
    });
    maglie.set(g.numero, {
      g, nodo, gira, mats, meshes, k: 1, kTarget: 1, spin: 0,
      p0: nodo.position.clone(), q0: nodo.quaternion.clone(),
      h: { x: 0, v: 0, t: 0 }, s: { x: 0, v: 0, t: 0 }, osc: { x: 0, v: 0 }, vPrec: 0, onda: 0,
    });
  }
  const tutteMesh = [...maglie.values()].flatMap((m) => m.meshes);
  const molla = (m, w, z, dt) => {         // oscillatore smorzato verso m.t (integrazione a passetti)
    const n = Math.max(1, Math.ceil(dt / 0.008)), h = dt / n;
    for (let i = 0; i < n; i++) { m.v += (-w * w * (m.x - m.t) - 2 * z * w * m.v) * h; m.x += m.v * h; }
  };
  const ASSE_X = new THREE.Vector3(1, 0, 0), ASSE_Y = new THREE.Vector3(0, 1, 0);
  const qa = new THREE.Quaternion(), qb = new THREE.Quaternion();
  const va = new THREE.Vector3(), vp = new THREE.Vector3();
  const aggiornaMaglia = (m, dt) => {
    const H = GESTI.hover, S = GESTI.selezione, M = GESTI.molle;
    const quieto = Math.abs(m.h.x - m.h.t) < 1e-4 && Math.abs(m.s.x - m.s.t) < 1e-4 && Math.abs(m.h.v) + Math.abs(m.s.v) < 1e-3
      && Math.abs(m.osc.x) < 1e-4 && Math.abs(m.osc.v) < 1e-3 && m.onda < 0.01;
    if (quieto && !m.sporca) return;
    let vel = 0;
    if (RIDUCI()) {
      m.h.x = m.h.t; m.s.x = m.s.t; m.h.v = m.s.v = 0; m.osc.x = m.osc.v = 0; m.onda = 0; m.vPrec = 0;
    } else if (quieto) {
      m.h.x = m.h.t; m.s.x = m.s.t; m.h.v = m.s.v = 0; m.osc.x = m.osc.v = 0; m.onda = 0; m.vPrec = 0;
    } else {
      molla(m.h, M.hover.w, M.hover.z, dt);
      molla(m.s, M.selezione.w, M.selezione.z, dt);
      vel = m.h.v * H.dy + m.s.v * S.dy;                         // velocita' verso la stanza (m/s)
      const acc = (vel - m.vPrec) / Math.max(dt, 1e-3);
      m.vPrec = vel;
      // la gruccia oscilla attorno all'asta quando la maglia accelera in avanti
      const O = M.oscillazione;
      m.osc.v += (-O.w * O.w * m.osc.x - 2 * O.z * O.w * m.osc.v - O.k * acc) * dt;
      m.osc.x = Math.max(-0.22, Math.min(0.22, m.osc.x + m.osc.v * dt));
      m.onda = Math.max(m.onda * Math.exp(-dt * 0.8), Math.min(1, Math.abs(vel) * 0.7 + Math.abs(m.osc.v) * 0.4));
    }
    m.sporca = false;
    const dy = m.h.x * H.dy + m.s.x * S.dy, dr = m.h.x * H.dr + m.s.x * S.dr, dz = m.h.x * H.dz + m.s.x * S.dz;
    m.nodo.position.copy(m.p0).add(va.set(0, dz, -dy));       // glTF: avanti verso la stanza = -z
    m.nodo.quaternion.copy(qa.setFromAxisAngle(ASSE_Y, dr)).multiply(m.q0);
    if (Math.abs(m.osc.x) > 1e-5) {
      vp.copy(m.nodo.position).y += GESTI.altezza_gancio;
      va.copy(m.nodo.position).sub(vp).applyAxisAngle(ASSE_X, m.osc.x).add(vp);
      m.nodo.position.copy(va);
      m.nodo.quaternion.premultiply(qb.setFromAxisAngle(ASSE_X, m.osc.x));
    }
    for (const mt of m.mats) {
      const sh = mt.userData.sh;
      if (sh) { sh.uniforms.uOnda.value = m.onda; sh.uniforms.uT.value = tempo.t; }
    }
  };

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
    // in orizzontale la scheda copre la destra: si guarda un po' a destra della maglia per tenerla nella parte libera;
    // in verticale la scheda e' un pannello in basso: si guarda un po' sotto
    const oriz = cam.aspect >= 1;
    return { a: f, r: 1.7, y: 1.62, ta: oriz ? f + 0.06 : f, tr: R - 1.0, ty: oriz ? 1.58 : 1.3, fov: 36 };
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
  const vai = (a, ms = 1100, punch = 0) => {
    const da = { ...vista };
    if (RIDUCI() || ms <= 0) { vista = { ...a }; tween = null; applica(vista); return; }
    tween = { da, a, t0: ora, ms, punch };
  };
  const passoTween = (now) => {
    if (!tween) return;
    const u = Math.min(1, (now - tween.t0) / tween.ms), e = ease(u);
    const { da, a } = tween;
    vista = {
      a: da.a + dAng(da.a, a.a) * e, r: da.r + (a.r - da.r) * e, y: da.y + (a.y - da.y) * e,
      ta: da.ta + dAng(da.ta, a.ta) * e, tr: da.tr + (a.tr - da.tr) * e, ty: da.ty + (a.ty - da.ty) * e,
      fov: da.fov + (a.fov - da.fov) * e - (tween.punch || 0) * Math.sin(Math.PI * e),
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
    const GAIN = tunnelDati.gain_interno || 1.0; // la luce cotta interna e' divisa per questo in tunnel.py
    // [nome, {metal, rough, env, k}]: k = quanta luce cotta resta come emissione (il resto lo mette l'ambiente)
    const LUCIDI = [
      [/Tunnel_Oro/, { metal: 1, rough: 0.28, env: 2.2, k: 0.35 }],
      [/Tunnel_(Pavimento|Corsia)/, { metal: 0, rough: 0.22, env: 3.0, k: 0.9 }],
      [/Tunnel_Muro/, { metal: 0, rough: 0.42, env: 1.4, k: 0.95 }],
    ];
    // erba: dettaglio fine (fili) sovrapposto alla texture della ciotola, sfumato con la distanza (niente moire')
    const dettErba = (() => {
      const n = 256, d = new Uint8Array(n * n * 4);
      for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
        const r = Math.random(), up = y ? d[((y - 1) * n + x) * 4] / 255 : 0.5;
        const v = Math.min(1, Math.max(0, 0.45 * r + 0.55 * (0.5 * up + 0.25 * (x ? d[(y * n + x - 1) * 4] / 255 : 0.5) + 0.25 * r)));
        const b = Math.round(255 * Math.min(1, Math.max(0, 0.5 + (v - 0.5) * 1.6)));
        d.set([b, b, b, 255], (y * n + x) * 4);
      }
      const t = new THREE.DataTexture(d, n, n, THREE.RGBAFormat);
      t.wrapS = t.wrapT = THREE.RepeatWrapping; t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearMipmapLinearFilter;
      t.generateMipmaps = true; t.anisotropy = renderer.capabilities.getMaxAnisotropy(); t.needsUpdate = true;
      return t;
    })();
    const erba = (b) => {
      b.onBeforeCompile = (sh) => {
        sh.uniforms.uDet = { value: dettErba };
        sh.vertexShader = sh.vertexShader.replace('#include <common>', ['#include <common>', 'varying float vDist;'].join('\n'))
          .replace('#include <project_vertex>', ['#include <project_vertex>', 'vDist = length(mvPosition.xyz);'].join('\n'));
        sh.fragmentShader = sh.fragmentShader.replace('#include <common>', ['#include <common>', 'uniform sampler2D uDet;', 'varying float vDist;'].join('\n'))
          .replace('#include <map_fragment>', [
            '#include <map_fragment>',
            '#ifdef USE_MAP',
            ' float fd = 1.0 - smoothstep(20.0, 80.0, vDist);',
            ' float d1 = texture2D(uDet, vMapUv * 36.0).r;',
            ' float d2 = texture2D(uDet, vMapUv * 7.3 + vec2(0.37, 0.11)).r;',
            ' diffuseColor.rgb *= mix(1.0, (0.55 + 0.9 * d1) * (0.82 + 0.36 * d2), fd);',
            '#endif'].join('\n'));
      };
    };
    const lucido = (m, conCol, p) => {
      const s = new THREE.MeshStandardMaterial({
        color: p.metal ? m.color.clone() : new THREE.Color(0x000000), metalness: p.metal, roughness: p.rough,
        vertexColors: conCol, side: THREE.DoubleSide, envMapIntensity: p.env,
        emissive: m.color.clone().multiplyScalar(p.k * GAIN), emissiveMap: m.map || null,
      });
      s.onBeforeCompile = (sh) => {
        sh.fragmentShader = sh.fragmentShader.replace('#include <emissivemap_fragment>',
          ['#include <emissivemap_fragment>', '#ifdef USE_COLOR', ' totalEmissiveRadiance *= vColor.rgb;', '#endif'].join('\n'));
      };
      return s;
    };
    tunnelGltf.scene.traverse((o) => {
      if (!o.isMesh) return;
      const m = o.material;
      // realismo: doppia faccia (le ciotole viste da sotto perdevano pezzi = triangoli neri) e niente piu guadagno
      const b = new THREE.MeshBasicMaterial({ map: m.map || null, vertexColors: !!o.geometry.attributes.color, side: THREE.DoubleSide });
      const ext = /^(Esterno_|Tunnel_Facciata)/.test(m.name);
      const led = /Cartelloni|Schermo|TettoLed/.test(m.name);
      b.color.copy(m.color).multiplyScalar(/Luce/.test(m.name) ? 2.0 : led ? 1.7 : ext ? (tunnelDati.gain_esterno || 1.0) : GAIN);
      o.material = b;
      // corrimano e pavimento: riflessi veri (Standard con la luce cotta come emissione: nessuna luce di scena)
      if (/Erba/.test(m.name)) erba(b);
      const lu = LUCIDI.find(([re]) => re.test(m.name));
      if (lu) o.material = lucido(m, !!o.geometry.attributes.color, lu[1]);
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
    // cielo vero (Sky Texture di Blender, `scripts/cielo.py`): sole nella stessa direzione della luce cotta degli spalti
    new THREE.TextureLoader().load(opz.cielo || 'cielo.jpg', (t) => {
      t.mapping = THREE.EquirectangularReflectionMapping;
      t.colorSpace = THREE.SRGBColorSpace;
      scena.background = t;
    });
    scena.fog = new THREE.Fog(0xc7d7df, 90, 260);
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
    // Prestazioni: finche' la camera e' nello stadio (p < 0.08, oltre ~30 m dalla porta) la sala, lo specchio e le sue ombre non
    // si disegnano (400k triangoli + un secondo passaggio dello specchio + la mappa d'ombra). Dalla porta si vede solo un
    // riquadro caldo al loro posto, della stessa tinta della luce della sala.
    const SOGLIA_SALA = 0.08;
    const portaSala = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 2.35),
      new THREE.MeshBasicMaterial({ color: 0xa8957c, fog: false, toneMapped: true }));
    portaSala.position.set(0, 1.175, 5.05 - 0.35);
    portaSala.visible = false;
    scena.add(portaSala);
    let salaVisibile = true;
    const mostraSala = (si) => {
      if (si === salaVisibile) return;
      salaVisibile = si;
      gltf.scene.visible = si;
      portaSala.visible = !si;
      if (si) renderer.shadowMap.needsUpdate = true;        // la mappa d'ombra si rifa' una volta quando la sala ricompare
    };
    // la sala e' ferma durante l'ingresso: mappa d'ombra congelata (a ogni fotogramma costava tutta la sala) e specchio
    // acceso solo nelle ultime decine di metri, con dissolvenza (si vede solo dal pavimento della sala)
    const aggiornaCostose = (p) => {
      const dentro = p >= 1;
      renderer.shadowMap.autoUpdate = dentro;
      if (dentro) renderer.shadowMap.needsUpdate = true;
      if (saoPass) {   // l'occlusione ambiente serve solo nella sala: costa un secondo passaggio dell'intera scena
        const fa = dentro ? 1 : liscio(0.92, 1.0, p);
        saoPass.enabled = fa > 0.001;
        saoPass.params.saoIntensity = SAO_INTENSITA * fa;
      }
      if (specchio) {
        const fs = dentro ? 1 : liscio(0.86, 0.95, p);
        specchio.visible = fs > 0.001;
        if (specchio.material.uniforms && specchio.material.uniforms.forza) specchio.material.uniforms.forza.value = 0.20 * fs;
      }
    };
    const ESP0 = renderer.toneMappingExposure, ADATT_FUORI = 0.88;
    const adatt = { m: ADATT_FUORI, t: performance.now() };
    perc = {
      esiste: true, attivo: false, p: 1, anim: null, lunghezza: lung,
      applica() {
        const p = this.p;
        const t = cp.getUtoTmapping(p);
        cp.getPoint(t, tmp); ct.getPoint(t, tmpT);
        const env = RIDUCI() ? 0 : liscio(0, 0.06, p) * (1 - liscio(0.92, 0.995, p));
        const d = (p * lung) / (tunnelDati.passo || 0.75);
        tmp.y += env * (tunnelDati.ampiezza_bob || 0.014) * Math.sin(2 * Math.PI * d);
        tmp.x += env * 0.006 * Math.sin(Math.PI * d);
        cam.position.copy(tmp);
        cam.lookAt(tmpT);
        // adattamento dell'occhio: nello stadio al sole l'esposizione e' un po' piu' bassa; entrando nel tunnel risale piano
        // (si parte "abbagliati" e il tunnel si apre), uscendo dal tunnel (scorrimento all'indietro) si richiude in fretta
        const adesso = performance.now(), dtA = Math.min(0.1, (adesso - adatt.t) / 1000);
        adatt.t = adesso;
        const dentro = tmp.z - 5.05 < 21.5;
        adatt.m += ((dentro ? 1.0 : ADATT_FUORI) - adatt.m) * (1 - Math.exp(-dtA / (dentro ? 1.2 : 0.4)));
        renderer.toneMappingExposure = ESP0 * (RIDUCI() ? 1 : adatt.m);
        const k = t * (fovs.length - 1), i = Math.min(fovs.length - 2, Math.floor(k));
        const f = fovEff({ fov: fovs[i] + (fovs[i + 1] - fovs[i]) * (k - i) });
        if (cam.fov !== f) { cam.fov = f; cam.updateProjectionMatrix(); }
      },
      progresso(p) {
        p = Math.min(1, Math.max(0, p));
        this.p = p;
        mostraSala(p >= SOGLIA_SALA);
        aggiornaCostose(p);
        if (p >= 1) {
          adatt.m = 1; renderer.toneMappingExposure = ESP0;
          if (this.attivo) {
            this.attivo = false;
            host.classList.remove('intro', 'corre');
            vista = { ...VISTE.sala }; tween = null; applica(vista);
          }
          return;
        }
        if (!this.attivo) {
          if (scelta !== null) api.torna();
          if (filtro) { filtro = null; segnaPill(); scurisci(); }      // tornando indietro la sala riparte "Tutti"
          sopra = null; etichetta.style.opacity = 0;
          this.attivo = true;
          host.classList.add('intro');
        }
        this.applica();
      },
      avvia(o = {}) {
        const da = o.da || 0, Sm = (1 - da) * lung;                       // metri da percorrere
        const TA = 1.6, vel = o.velocita || opz.velocita || 2.6;           // rampa (s) e velocita' di crociera (m/s)
        const durata = o.durata || (Sm / vel + TA) * 1000;                  // senza durata esplicita: passo svelto, non corsa
        if (RIDUCI()) { this.progresso(1); return Promise.resolve(); }
        this.progresso(Math.min(da, 0.9999));
        host.classList.add('corre');
        return new Promise((res) => { this.anim = { t: 0, durata, da, Sm, ta: Math.min(TA, durata / 4000), res }; });
      },
      ferma() {
        if (this.anim) { const r = this.anim.res; this.anim = null; host.classList.remove('corre'); r(); }
      },
      salta() { this.ferma(); this.progresso(1); },
      async introduzione() {
        if (RIDUCI()) { this.progresso(1); return; }
        this.progresso(0);
        if (video) {
          video.style.transition = 'none';          // il video entra di colpo: la dissolvenza serve solo all'uscita
          video.style.opacity = 1;
          void video.offsetWidth;
          video.style.transition = '';
          try { await video.play(); await new Promise((res) => { video.addEventListener('ended', res, { once: true }); video.addEventListener('error', res, { once: true }); this._saltaVideo = res; }); } catch (e) { /* senza video si parte dal tunnel */ }
          video.style.opacity = 0;
        }
        await this.avvia({ durata: opz.durataPercorso });
      },
      collegaScorrimento(el = host.parentElement) {
        let tS = 0;
        const f = () => {
          const r = el.getBoundingClientRect();
          const tot = r.height - window.innerHeight;
          const tgt = Math.min(1, Math.max(0, tot > 0 ? -r.top / tot : 1));
          const adesso = performance.now(), dtS = Math.min(0.1, (adesso - tS) / 1000);
          const primo = tS === 0;
          tS = adesso;
          // la rotella da' scatti: la camera insegue lo scorrimento con una molla morbida (0,12 s) invece di saltare
          const nuovo = primo || Math.abs(tgt - this.p) < 1e-4 ? tgt : this.p + (tgt - this.p) * (1 - Math.exp(-dtS / 0.12));
          this.ferma();
          this.progresso(nuovo);
        };
        window.addEventListener('scroll', f, { passive: true });
        f();
        this._f = f;                       // riletto anche a ogni fotogramma: non dipende dal momento dell'evento
        this._scorrimento = () => { window.removeEventListener('scroll', f); this._f = null; };
        return this._scorrimento;
      },
      passo(dt) {
        if (!this.anim) return;
        const a = this.anim;
        a.t += dt * 1000;
        const u = Math.min(1, a.t / a.durata);
        this.progresso(a.da + (1 - a.da) * (PROFILO(a.t / 1000, a.durata / 1000, a.Sm, a.ta) / a.Sm));
        if (u >= 1) { this.anim = null; host.classList.remove('corre'); a.res(); }
      },
    };
    bottone.addEventListener('click', () => { if (video && perc._saltaVideo) perc._saltaVideo(); perc.salta(); });
  }

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
      if (sopra === n) m.h.t = 0;
      scelta = n; sopra = null;
      m.s.t = 1; m.sporca = true;
      nodoLuce(m);
      vai(vistaMaglia(n), 1300);
      scurisci();
      mostraScheda(n);
      etichetta.style.opacity = 0;
    },
    _chiudi(n, camera = true) {
      const m = maglie.get(n);
      if (!m) return;
      m.s.t = 0; m.sporca = true;
      m.spin = 0;
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
      vai(filtro ? vistaReparto(filtro) : VISTE.sala, 1500, 7);
    },
    prossimo(d) {
      if (scelta === null) return;
      const l = dati.giocatori, i = l.findIndex((g) => g.numero === scelta);
      this.seleziona(l[(i + d + l.length) % l.length].numero);
    },
    distruggi() {
      cancelAnimationFrame(raf);
      if (perc) { perc.ferma(); if (perc._scorrimento) perc._scorrimento(); }
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
    if (perc && perc.attivo) return; // HD: niente raycast mentre la camera del tunnel si muove
    scena.updateMatrixWorld();
    cam.updateMatrixWorld();
    ray.setFromCamera(ndc, cam);
    const n = cerca();
    if (n === sopra) {
      if (n !== null) { etichetta.style.left = px + 'px'; etichetta.style.top = py + 'px'; }
      return;
    }
    if (sopra !== null) { const mm = maglie.get(sopra); mm.h.t = 0; mm.sporca = true; }
    sopra = n;
    if (n !== null) {
      const m = maglie.get(n);
      m.h.t = 1; m.sporca = true;
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
  // HD: discesa automatica se il telefono non regge: prima via la SAO, poi lo specchio, poi le ombre. Niente ricarica.
  // Decisione pura (testabile da console con `sala._valuta`): niente calo per i primi 4 s validi, mai per un singolo scatto
  // (compilazione shader, scheda nascosta, dt tagliato): conta la mediana su 2 s, e servono 2 finestre lente di fila.
  let cali = 0;
  const valutatore = () => {
    const st = { caldo: 0, buf: [], tempo: 0, lente: 0 };
    return (dtMs, nascosta) => {
      if (nascosta || dtMs >= 250) { st.buf.length = 0; st.tempo = 0; return null; }
      st.caldo += dtMs;
      if (st.caldo < 4000) return null;
      st.buf.push(dtMs); st.tempo += dtMs;
      if (st.tempo < 2000) return null;
      const ord = [...st.buf].sort((x, y) => x - y), med = ord[Math.floor(ord.length / 2)];
      st.buf.length = 0; st.tempo = 0;
      const fps = 1000 / med;
      api.ultimoControllo = { fps: Math.round(fps * 10) / 10, medianaMs: Math.round(med * 10) / 10, cali };
      if (fps >= 42) { st.lente = 0; return null; }
      if (++st.lente < 2) return null;
      st.lente = 0;
      return 'calo';
    };
  };
  const valuta = valutatore();
  const segnaFps = (dt) => {
    if (!alta || RIDUCI() || cali >= 3) return;
    if (valuta(dt * 1000, document.hidden) !== 'calo') return;
    if (cali >= 2 && perc && perc.attivo) return;   // spegnere le ombre ricompila gli shader: mai durante l'ingresso, a fine percorso
    cali++;
    if (cali === 1 && composer) {
      const senzaSao = composer.passes.filter((p) => p !== saoPass);
      composer.passes.length = 0;
      for (const p of senzaSao) composer.addPass(p);
    } else if (cali === 2 && specchio) {
      scena.remove(specchio);
    } else if (cali === 3) {
      centro.castShadow = false;
      gltf.scene.traverse((o) => { if (o.isMesh) { o.castShadow = false; o.receiveShadow = false; } });
    }
  };
  let dtAnim = 1 / 60;
  const passo = (now, dt) => {
    ora = now;
    if (perc && perc._f) perc._f();
    if (perc && perc.attivo) {
      // dt filtrato: un fotogramma lento o irregolare (vsync, GC, GPU occupata) non diventa un salto in avanti ma un
      // incremento quasi uniforme; la durata totale cambia di pochi decimi
      dtAnim += (Math.min(dt, 0.05) - dtAnim) * 0.2;
      perc.passo(dtAnim);
    } else {
      passoTween(now);
      aggiornaHover();
    }
    tempo.t += dt;
    for (const m of maglie.values()) {
      aggiornaMaglia(m, dt);
      if (Math.abs(m.k - m.kTarget) > 0.002) {
        m.k += (m.kTarget - m.k) * Math.min(1, dt * 8);
        for (const mt of m.mats) mt.color.copy(mt.userData.base).multiplyScalar(m.k);
      }
      if (Math.abs(m.spin - m.gira.rotation.y) > 1e-4) {
        m.gira.rotation.y += (m.spin - m.gira.rotation.y) * Math.min(1, dt * 10);
      }
    }
    // faro di scena sulla maglia scelta
    const target = scelta !== null ? 2.6 : 0;
    faro.intensity += (target - faro.intensity) * Math.min(1, dt * 4);
  };
  const dbg = opz.fps ? Object.assign(document.createElement('div'), { className: 'dbg-fps' }) : null;
  const dbgAcc = { n: 0, t: 0, max: 0 };
  if (dbg) {
    dbg.style.cssText = 'position:absolute;left:8px;bottom:8px;z-index:9;font:12px/1.3 monospace;color:#9f9;background:#000a;padding:4px 8px;border-radius:4px;pointer-events:none';
    host.appendChild(dbg);
  }
  const giro = (now) => {
    raf = requestAnimationFrame(giro);
    const dt = Math.min(0.25, (now - ultimo) / 1000);
    ultimo = now;
    passo(now, dt);
    segnaFps(dt); // HD: calo di qualita automatico se fps < 45
    disegna();
    if (dbg) {                     // ?fps=1: fps, fotogramma piu' lungo, triangoli e chiamate, posizione sul percorso
      dbgAcc.n++; dbgAcc.t += dt; dbgAcc.max = Math.max(dbgAcc.max, dt);
      if (dt > 0.06) console.warn('fotogramma lento', Math.round(dt * 1000) + ' ms', 'p=' + (perc ? perc.p.toFixed(3) : '-'));
      if (dbgAcc.t >= 1) {
        dbg.textContent = Math.round(dbgAcc.n / dbgAcc.t) + ' fps · max ' + Math.round(dbgAcc.max * 1000) + ' ms · '
          + renderer.info.render.triangles + ' tri · ' + renderer.info.render.calls + ' call · p ' + (perc ? perc.p.toFixed(2) : '-') + ' · calo ' + cali;
        dbgAcc.n = 0; dbgAcc.t = 0; dbgAcc.max = 0;
      }
    }
  };
  // riscaldamento: tutti gli shader e le texture (tunnel, stadio, sala) pronti prima di muovere la camera, senza scatti al primo ingresso
  renderer.compile(scena, cam);
  scena.traverse((o) => {
    if (!o.isMesh) return;
    for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
      for (const k of ['map', 'emissiveMap', 'roughnessMap', 'metalnessMap', 'normalMap', 'aoMap']) if (m[k] && m[k].isTexture) renderer.initTexture(m[k]);
    }
  });
  // upload di TUTTE le geometrie e delle ombre prima di muovere la camera: senza, ogni mesh fuori campo si carica sulla GPU
  // la prima volta che entra nell'inquadratura (scatti durante l'ingresso)
  {
    const cull = [];
    scena.traverse((o) => { if (o.isMesh && o.frustumCulled) { cull.push(o); o.frustumCulled = false; } });
    try { renderer.render(scena, cam); } catch (e) { /* il riscaldamento non deve mai bloccare l'avvio */ }
    for (const o of cull) o.frustumCulled = true;
  }
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
  Object.assign(api, { THREE, scena, cam, maglie, renderer, dati, stat, percorso: perc, ultimoControllo: null, _valuta: valutatore, // fluidita: ultimo controllo fps (ogni 2s) — in console: window.sala.ultimoControllo
    _avanza: (ms) => { passo(ora + ms, ms / 1000); disegna(); } });
  return api;
}
