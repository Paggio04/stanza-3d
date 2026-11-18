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
import { creaLavagna } from './lavagna.js';

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
.sala .formazione,.sala .indietro{all:unset;cursor:pointer;padding:9px 18px;border-radius:999px;background:#173f9a;color:#fff;border:1px solid #fff6;font-size:14px;font-weight:600;letter-spacing:.03em;pointer-events:auto;box-shadow:0 4px 14px #0006}
.sala .formazione:hover,.sala .indietro:hover{background:#1f4fc0}
.sala .formazione:focus-visible,.sala .indietro:focus-visible{outline:2px solid #6cf;outline-offset:2px}
.sala .indietro{position:absolute;left:16px;top:16px;z-index:4;display:none}
.sala.lavagna .indietro{display:block}
.sala.lavagna .top,.sala.lavagna .nastro,.sala.lavagna .scheda,.sala.lavagna .etichetta{opacity:0;pointer-events:none}
.sala.transita .top,.sala.transita .nastro,.sala.transita .scheda,.sala.transita .etichetta{opacity:0;pointer-events:none}
.sala.transita canvas{pointer-events:none}
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
.sala .intro-titolo{position:absolute;left:0;right:0;top:34%;display:flex;flex-direction:column;align-items:center;gap:8px;text-align:center;pointer-events:none;opacity:0;z-index:2;text-shadow:0 2px 18px #000a}
.sala .intro-titolo b{font-size:clamp(28px,6vw,64px);font-weight:800;letter-spacing:.14em;text-transform:uppercase}
.sala .intro-titolo span{font-size:clamp(12px,1.6vw,17px);letter-spacing:.28em;text-transform:uppercase;opacity:.9}
.sala.corre .intro-titolo{animation:sala-titolo 5.2s ease both}
@keyframes sala-titolo{0%{opacity:0;transform:translateY(14px)}18%{opacity:1;transform:none}70%{opacity:1}100%{opacity:0;transform:translateY(-8px)}}
.sala .nero{position:absolute;inset:0;background:#000;opacity:0;pointer-events:none;z-index:2}
.sala.corre .nero{animation:sala-nero 1.6s ease-out both}
@keyframes sala-nero{from{opacity:1}to{opacity:0}}
@media (prefers-reduced-motion:reduce){.sala.corre .intro-titolo,.sala.corre .nero{animation:none}}
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
    <div class="top"><div class="titolo"></div><div class="sotto"></div><div class="pillole" role="group" aria-label="Reparti"></div><button class="formazione">Guarda la formazione ufficiale</button></div>
    <button class="indietro">‹ Torna allo spogliatoio</button>
    <div class="etichetta"></div>
    <aside class="scheda" aria-live="polite">
      <div class="num"></div><div class="nome"></div><div class="ruolo"></div><div class="pos"></div>
      <div class="nav"><button class="prec" aria-label="Giocatore precedente">‹ Precedente</button><button class="succ" aria-label="Giocatore successivo">Successivo ›</button></div>
      <button class="torna">Torna alla sala (Esc)</button>
    </aside>
    <div class="nastro"><span></span></div>
    <button class="salta">Salta l'ingresso ›</button>
    <div class="intro-titolo"><b></b><span></span></div><div class="nero"></div>
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
  // le luci devono valere anche nel passaggio dello specchio (strato 1): stesse luci = stessi shader, niente ricompilazioni
  for (const l of [centro, dall, faro]) l.layers.enable(1);
  scena.children.forEach((o) => { if (o.isLight) o.layers.enable(1); });
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
    // strato 1 = cio' che il pavimento riflette (solo la sala: stadio e tunnel no). Il pavimento stesso no: e' a doppia
    // faccia, 4 mm sotto lo specchio, e nel passaggio del riflesso copriva tutto oltre un paio di metri (riflesso solo
    // vicino alla camera, poi pavimento grigio fino agli armadietti)
    if (o.name !== 'Fisso_Pavimento') o.layers.enable(1);
    if (!o.isMesh) return;
    o.castShadow = alta && !SENZA_OMBRA.test(o.name);
    o.receiveShadow = alta;
    // il pavimento lucido: il riflesso vero lo da' lo specchio; l'ambiente finto (stanza grigia) lo velava di sbieco
    if (o.name === 'Fisso_Pavimento' && alta) o.material.envMapIntensity = 0.4;
  });
  // pavimento lucido: il riflesso della sala (piano a specchio) si fonde sopra il pavimento del .glb
  let specchio = null;
  if (alta) {
    const latoSp = esplicita ? 2048 : 1024; // fluidita: specchio 2048 solo con ?q=alta, in auto 1024 (era il freeze)
    specchio = new Reflector(new THREE.CircleGeometry(dati.raggio + 0.3, 96), { // HD: 96 segmenti = bordo piu liscio
      textureWidth: latoSp, textureHeight: latoSp, clipBias: 0.003,
      multisample: 0,                     // la sfocatura 3x3 fa gia' da antialias: il MSAA 4x costava senza vedersi
      shader: {
        name: 'RiflessoPavimento',
        uniforms: { color: { value: null }, tDiffuse: { value: null }, textureMatrix: { value: null }, forza: { value: 0.20 } }, // HD: 0.20, prima 0.30 troppo lattiginoso
        vertexShader: `
          uniform mat4 textureMatrix; varying vec4 vUv; varying vec3 vPos;
          #include <common>
          #include <logdepthbuf_pars_vertex>
          void main() {
            vUv = textureMatrix * vec4(position, 1.0);
            vec4 w = modelMatrix * vec4(position, 1.0);
            vPos = w.xyz;
            gl_Position = projectionMatrix * viewMatrix * w;
            #include <logdepthbuf_vertex>
          }`,
        // Fresnel: guardando di sbieco (il pavimento lontano, sotto gli armadietti) un pavimento lucido riflette molto di piu'
        // che guardando in basso; con una forza costante il riflesso restava solo vicino alla camera e il resto era grigio.
        fragmentShader: `
          uniform sampler2D tDiffuse; uniform float forza; varying vec4 vUv; varying vec3 vPos;
          #include <logdepthbuf_pars_fragment>
          void main() {
            #include <logdepthbuf_fragment>
            vec4 uv = vUv; vec2 p = uv.xy / uv.w;
            vec3 c = vec3(0.0); float w = 0.0;
            for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++) { // HD: sfocatura 3x3 (prima 5x5) = riflesso piu nitido
              float k = 1.0 / (1.0 + float(i*i + j*j));
              c += texture2D(tDiffuse, p + vec2(float(i), float(j)) * 0.0012).rgb * k; w += k;
            }
            float cosT = clamp(normalize(cameraPosition - vPos).y, 0.0, 1.0);
            float fr = pow(1.0 - cosT, 3.0);
            gl_FragColor = vec4(c / w, clamp(forza * (1.0 + 2.6 * fr), 0.0, 0.75));
          }`,
      },
    });
    specchio.material.transparent = true;
    specchio.material.depthWrite = false;
    specchio.rotation.x = -Math.PI / 2;
    specchio.position.y = 0.004;
    specchio.renderOrder = 1;
    specchio.camera.layers.set(1);          // nel riflesso solo la sala: lo stadio dietro la porta non serve e costava
    // il riflesso si ridisegna solo quando cambia qualcosa (camera, maglie, luci): a sala ferma costava un secondo
    // disegno dell'intera sala a ogni fotogramma, ed era quello che faceva scattare il calo automatico (e lo spariva)
    const disegnaRiflesso = specchio.onBeforeRender;
    const mPrec = new THREE.Matrix4(), pPrec = new THREE.Matrix4();
    specchio.sporco = true;
    specchio.onBeforeRender = function (r, s, c, ...resto) {
      if (!this.sporco && c.matrixWorld.equals(mPrec) && c.projectionMatrix.equals(pPrec)) return;
      mPrec.copy(c.matrixWorld); pPrec.copy(c.projectionMatrix);
      this.sporco = false;
      disegnaRiflesso.call(this, r, s, c, ...resto);
    };
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
  let lav = null, inLav = false, trans = null;   // trans: passaggio in corso fra spogliatoio e lavagna
  const disegna = () => {
    if (inLav && lav) { renderer.render(lav.scena, lav.cam); return; }
    if (trans && trans.mix > 0.001) {           // la lavagna nel suo target, poi la sala, poi la lavagna sopra in dissolvenza
      renderer.setRenderTarget(rtLav);
      renderer.render(lav.scena, lav.cam);
      renderer.setRenderTarget(null);
    }
    if (composer) composer.render(); else renderer.render(scena, cam);
    if (trans && trans.mix > 0.001) {
      quadLav.material.opacity = trans.mix;
      const ac = renderer.autoClear;
      renderer.autoClear = false;
      renderer.render(scenaQuad, camQuad);
      renderer.autoClear = ac;
    }
  };

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
    if (quieto && !m.sporca) return false;          // ferma: niente da ridisegnare (ombre e riflesso restano quelli)
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
    return true;
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
    scena.fog = new THREE.Fog(0xc7d7df, 45, 230);   // prospettiva aerea: le tribune lontane (40-70 m) schiariscono appena
    const S = VISTE.sala;
    const fin = { p: gl(S.r, S.a), t: gl(S.tr, S.ta) };
    // apertura "dall'alto": si parte sopra il campo, di fronte alla bocca del tunnel, e si scende fino all'altezza degli occhi
    // la stessa di tunnel.py (tunnel.json "apertura"): lo stadio e' tagliato a cio' che si vede da qui in poi
    const ap = tunnelDati.apertura || { p: [-6.0, 12.5, 66.0], t: [0.0, 2.6, 27.0], fov: 56 };
    const APERTURA = { p: new V3(...ap.p), t: new V3(...ap.t), fov: ap.fov };
    const pos = [APERTURA.p, ...tunnelDati.percorso.map((k) => new V3(...k.p)), new V3(fin.p.x, S.y, fin.p.z)];
    const tgt = [APERTURA.t, ...tunnelDati.percorso.map((k) => new V3(...k.t)), new V3(fin.t.x, S.ty, fin.t.z)];
    const fovs = [APERTURA.fov, ...tunnelDati.percorso.map((k) => k.fov), S.fov];
    const cp = new THREE.CatmullRomCurve3(pos, false, 'centripetal');
    const ct = new THREE.CatmullRomCurve3(tgt, false, 'centripetal');
    const lung = cp.getLength();
    const liscio = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
    // ritmo: veloce nella discesa e sul campo, a passo normale nel tunnel. c(p) = tempo "pesato" per arrivare a p; cinv e' l'inverso
    const velF = (p) => 1 + 1.3 * (1 - liscio(0.12, 0.40, p));
    const NT = 400, cTab = new Float32Array(NT + 1);
    for (let i = 1; i <= NT; i++) cTab[i] = cTab[i - 1] + (1 / NT) / velF((i - 0.5) / NT);
    const cTot = cTab[NT];
    const cDi = (p) => { const x = Math.min(1, Math.max(0, p)) * NT, i = Math.min(NT - 1, Math.floor(x)); return cTab[i] + (cTab[i + 1] - cTab[i]) * (x - i); };
    const cInv = (c) => { let a = 0, b = NT; c = Math.min(cTot, Math.max(0, c)); while (b - a > 1) { const m = (a + b) >> 1; if (cTab[m] <= c) a = m; else b = m; } return (a + (c - cTab[a]) / Math.max(1e-9, cTab[b] - cTab[a])) / NT; };
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
    const extra = APERTURA.p.distanceTo(new V3(...tunnelDati.percorso[0].p));   // il tratto di apertura non conta per la sala
    const SOGLIA_SALA = (extra + 0.08 * (lung - extra)) / lung;
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
      // niente nuova mappa d'ombra: quella del riscaldamento resta valida (la sala e' ferma) e rifarla a meta' tunnel
      // era un fotogramma lungo (6 facce della luce puntiforme per tutta la sala)
      if (specchio) specchio.sporco = true;
    };
    // Dal tunnel la sala si vede solo attraverso la porta: si disegnano solo i pezzi che stanno nel cuneo fra la camera e
    // gli stipiti (due piani verticali, validi anche per il riflesso, che specchia solo in altezza). Prima: tutta la sala,
    // ~740k triangoli, per un riquadro di 1,2 m. Mai durante un aggiornamento d'ombra: le ombre si rifanno solo nella sala.
    const ZP = R + ((dati.porta && dati.porta.spessore) || 0.55), XP = ((dati.porta && dati.porta.larghezza) || 1.2) / 2;
    const pezzi = [];
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse((o) => {
      if (!o.isMesh) return;
      if (!o.geometry.boundingSphere) o.geometry.computeBoundingSphere();
      const s = o.geometry.boundingSphere.clone().applyMatrix4(o.matrixWorld);
      pezzi.push({ o, c: s.center, r: s.radius + 0.15 });   // margine: maglie e ante si muovono di qualche cm
    });
    let ritagliata = false;
    const nL = new V3(), nR = new V3(), dC = new V3();
    const ritaglia = (attivo) => {
      const C = cam.position;
      if (!attivo || C.z <= ZP + 0.02) {
        if (ritagliata) { for (const k of pezzi) k.o.visible = true; ritagliata = false; if (specchio) specchio.sporco = true; }
        return;
      }
      // normali dei due piani (in xz, per camera e stipite) rivolte verso l'interno del cuneo
      const piano = (n, ex) => {
        const dx = ex - C.x, dz = ZP - C.z;
        n.set(-dz, 0, dx).normalize();
        if (n.x * (0 - C.x) + n.z * (ZP - 1 - C.z) < 0) n.multiplyScalar(-1);   // verso il centro della sala
      };
      piano(nL, -XP); piano(nR, XP);
      for (const k of pezzi) {
        dC.subVectors(k.c, C);
        k.o.visible = dC.x * nL.x + dC.z * nL.z > -k.r && dC.x * nR.x + dC.z * nR.z > -k.r;
      }
      ritagliata = true;
    };
    // specchio acceso solo nelle ultime decine di metri, con dissolvenza (si vede solo dal pavimento della sala)
    const aggiornaCostose = (p) => {
      const dentro = p >= 1;
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
    // porta a due ante in fondo al tunnel: si apre scorrendo di lato mentre ci si avvicina (p 0,84 -> 0,935)
    const antaL = tunnelGltf.scene.getObjectByName('Anta_L'), antaR = tunnelGltf.scene.getObjectByName('Anta_R');
    const baseL = antaL ? antaL.position.x : 0, baseR = antaR ? antaR.position.x : 0;
    const apriPorta = (f) => {
      if (antaL) antaL.position.x = baseL - 0.62 * f;      // glTF: x = x del mondo
      if (antaR) antaR.position.x = baseR + 0.62 * f;
    };
    apriPorta(1);          // senza ingresso (sala aperta direttamente) la porta e' gia' aperta: ci si passa per la lavagna
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
        // la testa di chi cammina: rollio e beccheggio piccolissimi legati al passo, piu' una deriva lenta dello sguardo
        if (env > 0) {
          const tt = performance.now() / 1000;
          cam.rotateY(env * (0.0035 * Math.sin(Math.PI * d + 0.7) + 0.0025 * Math.sin(tt * 0.63)));
          cam.rotateX(env * (0.0030 * Math.sin(2 * Math.PI * d + 1.1) + 0.0020 * Math.sin(tt * 0.41 + 2.0)));
        }
        // lo sguardo: si alza un attimo verso le tribune uscendo sul campo, poi cerca la bocca del tunnel (destra, poi sinistra)
        if (!RIDUCI()) {
          cam.rotateX(0.07 * Math.sin(Math.PI * liscio(0.02, 0.24, p)));
          cam.rotateY(-0.05 * Math.sin(2 * Math.PI * liscio(0.08, 0.42, p)));
        }
        apriPorta(RIDUCI() ? 1 : liscio(0.84, 0.935, p));
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
        ritaglia(p < 1);
      },
      progresso(p) {
        p = Math.min(1, Math.max(0, p));
        this.p = p;
        mostraSala(p >= SOGLIA_SALA);
        aggiornaCostose(p);
        if (p >= 1) {
          adatt.m = 1; renderer.toneMappingExposure = ESP0; apriPorta(1);
          ritaglia(false);
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
        const da = o.da || 0, cda = cDi(da), Sm = (cTot - cda) * lung;     // 'metri pesati' da percorrere
        const TA = 1.6, vel = o.velocita || opz.velocita || 2.6;           // rampa (s) e velocita' di crociera (m/s)
        const durata = o.durata || (Sm / vel + TA) * 1000;                  // senza durata esplicita: passo svelto, non corsa
        if (RIDUCI()) { this.progresso(1); return Promise.resolve(); }
        this.progresso(Math.min(da, 0.9999));
        host.classList.add('corre');
        return new Promise((res) => { this.anim = { t: 0, durata, da, cda, Sm, ta: Math.min(TA, durata / 4000), res }; });
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
        this.progresso(cInv(a.cda + PROFILO(a.t / 1000, a.durata / 1000, a.Sm, a.ta) / lung));
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
  q('.intro-titolo b').textContent = dati.squadra;
  q('.intro-titolo span').textContent = 'Dal campo allo spogliatoio';
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
      if (rtLav) rtLav.dispose();
      renderer.dispose();
      host.innerHTML = '';
    },
  };
  q('.torna').addEventListener('click', () => api.torna());
  q('.prec').addEventListener('click', () => api.prossimo(-1));
  q('.succ').addEventListener('click', () => api.prossimo(1));
  const tasto = (e) => {
    if (trans || inLav) return;
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
    if ((perc && perc.attivo) || trans || inLav) return;   // nella lavagna il clic non deve scegliere una maglia nascosta
    if (giu && giu.mosso) return;
    scena.updateMatrixWorld();
    cam.updateMatrixWorld();
    ray.setFromCamera(ndc, cam);
    const n = cerca();
    if (n !== null && n !== scelta) api.seleziona(n);
  });
  const aggiornaHover = () => {
    if (!sporco || scelta !== null || inLav || trans) return;
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

  // ---- stanza della formazione ufficiale (lavagna tattica); formazione.json e' l'unico file che l'allenatore cambia
  const bFormazione = q('.formazione'), bIndietro = q('.indietro');
  try {
    const form = await (await fetch(opz.formazione || 'formazione.json')).json();
    lav = creaLavagna(renderer, scena.environment, dati, form);
  } catch (e) { console.warn('formazione non caricata', e); bFormazione.remove(); }
  // Passaggio fra le due stanze in movimento, mai a schermo nero:
  //  - andata: ci si gira verso la porta e si esce camminando; sulla soglia la stanza della lavagna sfuma dentro mentre
  //    la sua camera avanza dalla parete verso il cavalletto;
  //  - ritorno: la camera della lavagna arretra e sfuma nel tunnel, poi si rientra nello spogliatoio a piedi, dalla porta,
  //    con lo stesso percorso (e la stessa posa d'arrivo) dell'ingresso.
  // La lavagna in dissolvenza si disegna in un target e si sovrappone alla sala con un quadrato a tutto schermo (il tone
  // mapping si applica solo all'uscita a schermo: il quadrato lo riceve come il disegno diretto).
  let rtLav = null, quadLav = null, scenaQuad = null, camQuad = null;
  const preparaVelo = () => {
    if (!lav) return;
    if (!rtLav) {
      rtLav = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: 4 });
      quadLav = new THREE.Mesh(new THREE.PlaneGeometry(2, 2),
        new THREE.MeshBasicMaterial({ map: rtLav.texture, transparent: true, depthTest: false, depthWrite: false }));
      quadLav.frustumCulled = false;
      scenaQuad = new THREE.Scene();
      scenaQuad.add(quadLav);
      camQuad = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
      camQuad.position.z = 0.5;
    }
    const s = renderer.getDrawingBufferSize(new THREE.Vector2());
    rtLav.setSize(s.x, s.y);
  };
  const DIST_PARETE = 4.4, DIST_LAV = 3.5;            // camera della lavagna: dalla parete al cavalletto
  const SOGLIA = new THREE.Vector3(0, 1.6, R + 0.35);   // nel vano della porta della sala (la porta e' a phi = 180: +z)
  const sguardo = (yaw, pitch, da, out) => out.set(da.x + Math.sin(yaw) * Math.cos(pitch), da.y + Math.sin(pitch), da.z + Math.cos(yaw) * Math.cos(pitch));
  const fra = (a, b, x) => Math.min(1, Math.max(0, (x - a) / (b - a)));
  const sfuma = (a, b, x) => { const t = fra(a, b, x); return t * t * (3 - 2 * t); };
  const vT = new THREE.Vector3(), vF = new THREE.Vector3();
  const finisciLav = (dentro) => {
    trans = null;
    inLav = dentro;
    host.classList.remove('transita');
    host.classList.toggle('lavagna', dentro);
    if (lav) { lav.attiva(dentro); if (dentro) lav.distanza(DIST_LAV); }
    if (!dentro && !(perc && perc.attivo)) { vista = { ...VISTE.sala }; tween = null; applica(vista); }
    ridim();
  };
  const entraLav = (dentro) => {
    if (!lav || trans || dentro === inLav) return;
    if (dentro) {          // si lascia la sala com'e': scheda chiusa, niente maglia sollevata, niente etichetta
      if (scelta !== null) api.torna();
      tween = null;
      if (sopra !== null) { const mm = maglie.get(sopra); mm.h.t = 0; mm.sporca = true; sopra = null; }
      etichetta.style.opacity = 0;
      renderer.domElement.style.cursor = '';
      lav.ripristina();
    }
    if (RIDUCI()) { finisciLav(dentro); return; }
    preparaVelo();
    host.classList.add('transita');
    if (dentro) {
      cam.getWorldDirection(vF);
      trans = {
        t: 0, dur: 2.7, mix: 0, p0: cam.position.clone(), fov0: cam.fov,
        yaw0: Math.atan2(vF.x, vF.z), pitch0: Math.asin(Math.max(-1, Math.min(1, vF.y))),
        passo(dt) {
          this.t += dt;
          const u = Math.min(1, this.t / this.dur);
          const giro = ease(fra(0, 0.55, u)), cammino = ease(fra(0.12, 1, u));
          cam.position.lerpVectors(this.p0, SOGLIA, cammino);
          cam.position.y += 0.011 * Math.sin(Math.PI * cammino) * Math.sin(2 * Math.PI * cammino * 2.2);   // il passo
          const yaw = this.yaw0 + dAng(this.yaw0, 0) * giro, pitch = this.pitch0 + (-0.03 - this.pitch0) * giro;
          cam.lookAt(sguardo(yaw, pitch, cam.position, vT));
          const f = fovEff({ fov: this.fov0 + (66 - this.fov0) * giro });
          if (cam.fov !== f) { cam.fov = f; cam.updateProjectionMatrix(); }
          this.mix = sfuma(0.55, 0.92, u);
          lav.distanza(DIST_PARETE - (DIST_PARETE - DIST_LAV) * ease(fra(0.45, 1, u)));
          if (u >= 1) finisciLav(true);
        },
      };
    } else {
      lav.attiva(false);
      host.classList.remove('lavagna');
      inLav = false;
      const l = perc ? perc.lunghezza : 1, P0 = perc ? Math.max(0.5, 1 - 6.5 / l) : 1;
      if (perc) perc.progresso(P0);                      // si riparte nel tunnel, a 6,5 m dalla porta (ante socchiuse)
      trans = {
        t: 0, dur: perc ? 3.4 : 1.4, mix: 1, d0: lav.distanza(),
        passo(dt) {
          this.t += dt;
          const u = Math.min(1, this.t / this.dur);
          this.mix = 1 - sfuma(0.06, 0.42, u);
          lav.distanza(this.d0 + (DIST_PARETE - this.d0) * ease(fra(0, 0.45, u)));
          if (perc) perc.progresso(u >= 1 ? 1 : P0 + (1 - P0) * PROFILO(u * this.dur, this.dur, 1, 0.9));
          if (u >= 1) finisciLav(false);
        },
      };
    }
  };
  bFormazione.addEventListener('click', () => entraLav(true));
  bIndietro.addEventListener('click', () => entraLav(false));
  window.addEventListener('keydown', (e) => { if (e.key === 'Escape' && inLav && !trans) entraLav(false); });

  // ---- ciclo
  const ridim = () => {
    const w = host.clientWidth || 800, h = host.clientHeight || 450;
    renderer.setSize(w, h, false);
    if (composer) composer.setSize(w, h);
    cam.aspect = w / h;
    cam.updateProjectionMatrix();
    if (lav) lav.ridim(w, h);
    if (rtLav) preparaVelo();
    if (trans) return;                    // la camera la guida il passaggio
    if (perc && perc.attivo) perc.applica(); else applica(vista);
  };
  window.addEventListener('resize', ridim);
  let ultimo = performance.now();
  let raf = 0;
  // HD: discesa automatica se il telefono non regge: prima via la SAO, poi lo specchio a meta' risoluzione, poi le ombre. Niente ricarica.
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
  // Ordine del calo: SAO (se c'e'), specchio a meta' risoluzione, ombre. Lo specchio non sparisce mai: prima, sui PC con
  // scheda video modesta, dopo una decina di secondi restava il pavimento grigio. Ogni passo conta solo se cambia qualcosa.
  let specchioRidotto = false;
  const segnaFps = (dt) => {
    if (!alta || RIDUCI() || cali >= 3 || trans) return;
    if (valuta(dt * 1000, document.hidden) !== 'calo') return;
    if (composer && composer.passes.includes(saoPass)) {
      const senzaSao = composer.passes.filter((p) => p !== saoPass);
      composer.passes.length = 0;
      for (const p of senzaSao) composer.addPass(p);
    } else if (specchio && !specchioRidotto) {
      specchio.getRenderTarget().setSize(512, 512);
      specchioRidotto = true;
      specchio.sporco = true;
    } else if (centro.castShadow) {
      if (perc && perc.attivo) return;   // spegnere le ombre ricompila gli shader: mai durante l'ingresso, a fine percorso
      centro.castShadow = false;
      gltf.scene.traverse((o) => { if (o.isMesh) { o.castShadow = false; o.receiveShadow = false; } });
    } else return;
    cali++;
  };
  let ombreDaRifare = false;
  let dtAnim = 1 / 60;
  const passo = (now, dt) => {
    ora = now;
    if (perc && perc._f && !trans) perc._f();
    if (trans) {
      trans.passo(Math.min(dt, 0.05));
    } else if (perc && perc.attivo) {
      // dt filtrato: un fotogramma lento o irregolare (vsync, GC, GPU occupata) non diventa un salto in avanti ma un
      // incremento quasi uniforme; la durata totale cambia di pochi decimi
      dtAnim += (Math.min(dt, 0.05) - dtAnim) * 0.2;
      perc.passo(dtAnim);
    } else {
      passoTween(now);
      aggiornaHover();
    }
    tempo.t += dt;
    if ((inLav || trans) && lav) lav.passo(dt);
    // ombre e riflesso si ridisegnano solo quando qualcosa si muove (la luce e' ferma): a sala ferma costavano ~20 ms
    // a fotogramma su una scheda video modesta, ed era questo a far partire il calo automatico
    let mosse = false, cambia = false;
    for (const m of maglie.values()) {
      if (aggiornaMaglia(m, dt)) mosse = true;
      if (Math.abs(m.k - m.kTarget) > 0.002) {
        m.k += (m.kTarget - m.k) * Math.min(1, dt * 8);
        for (const mt of m.mats) mt.color.copy(mt.userData.base).multiplyScalar(m.k);
        cambia = true;
      }
      if (Math.abs(m.spin - m.gira.rotation.y) > 1e-4) {
        m.gira.rotation.y += (m.spin - m.gira.rotation.y) * Math.min(1, dt * 10);
        mosse = true;
      }
    }
    // faro di scena sulla maglia scelta
    const target = scelta !== null ? 2.6 : 0;
    if (Math.abs(target - faro.intensity) > 1e-3) { faro.intensity += (target - faro.intensity) * Math.min(1, dt * 4); cambia = true; }
    if (mosse) ombreDaRifare = true;
    // mai con la sala ritagliata dalla porta (percorso in corso): la mappa d'ombra perderebbe i pezzi nascosti
    if (ombreDaRifare && !(perc && perc.attivo)) { renderer.shadowMap.needsUpdate = true; ombreDaRifare = false; }
    if ((mosse || cambia) && specchio) specchio.sporco = true;
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
  // la mappa d'ombra fatta qui resta valida finche' non si muove una maglia (vedi `passo`); la lavagna pronta per il passaggio
  renderer.shadowMap.autoUpdate = false;
  if (lav) renderer.compile(lav.scena, lav.cam);
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
