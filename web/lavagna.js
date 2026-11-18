// Stanza della formazione ufficiale: stessa sala circolare dello spogliatoio, con una lavagna tattica su un cavalletto.
// La formazione si cambia SOLO in `formazione.json` (modulo, 11 numeri di maglia, avversario, data): i nomi vengono da sala.json.
// Uso: const lav = creaLavagna(renderer, ambiente, dati, formazione); poi lav.passo(dt) e renderer.render(lav.scena, lav.cam).
import * as THREE from 'three';

const BLU = '#173f9a';

// Righe del modulo ("4-3-3" -> [4,3,3]); se non torna con i giocatori in campo si usa 4-4-2.
function righeModulo(modulo, n) {
  const r = String(modulo || '').split(/[-\s]+/).map(Number).filter((x) => x > 0);
  return r.reduce((a, b) => a + b, 0) === n - 1 ? r : [4, 4, 2].slice(0, 3);
}

// Posizioni normalizzate (x, y in 0..1, attacco in alto): portiere in basso, poi una riga per ogni numero del modulo.
export function posizioni(modulo, numeri) {
  const righe = righeModulo(modulo, numeri.length);
  const out = [{ numero: numeri[0], x: 0.5, y: 0.9 }];
  let i = 1;
  righe.forEach((k, r) => {
    const y = 0.9 - ((r + 1) / righe.length) * 0.76;
    for (let j = 0; j < k && i < numeri.length; j++, i++) out.push({ numero: numeri[i], x: (j + 1) / (k + 1), y });
  });
  return out;
}

function disegnaLavagna(form, rosa) {
  const W = 1024, H = 1400;
  const c = document.createElement('canvas');
  c.width = W; c.height = H;
  const g = c.getContext('2d');
  // fondo bianco da lavagna con intestazione
  g.fillStyle = '#f4f6f8'; g.fillRect(0, 0, W, H);
  g.fillStyle = BLU; g.fillRect(0, 0, W, 150);
  g.fillStyle = '#fff'; g.textAlign = 'center';
  g.font = '700 54px system-ui, Segoe UI, sans-serif';
  g.fillText('FORMAZIONE UFFICIALE', W / 2, 74);
  const p = form.partita || {};
  const riga = [p.casa === false ? 'in trasferta' : 'in casa', p.avversario ? 'vs ' + p.avversario : '', p.data || ''].filter(Boolean).join(' · ');
  g.font = '500 34px system-ui, Segoe UI, sans-serif';
  g.fillText(riga || (form.modulo || ''), W / 2, 121);
  // campo
  const cx = 60, cy = 190, cw = W - 120, ch = 1000;
  for (let i = 0; i < 10; i++) { g.fillStyle = i % 2 ? '#2f7d3a' : '#348a40'; g.fillRect(cx, cy + (ch / 10) * i, cw, ch / 10); }
  g.strokeStyle = '#ffffffcc'; g.lineWidth = 5;
  g.strokeRect(cx, cy, cw, ch);
  g.beginPath(); g.moveTo(cx, cy + ch / 2); g.lineTo(cx + cw, cy + ch / 2); g.stroke();
  g.beginPath(); g.arc(cx + cw / 2, cy + ch / 2, 90, 0, Math.PI * 2); g.stroke();
  g.strokeRect(cx + cw * 0.22, cy, cw * 0.56, 150); g.strokeRect(cx + cw * 0.22, cy + ch - 150, cw * 0.56, 150);
  g.strokeRect(cx + cw * 0.36, cy, cw * 0.28, 60); g.strokeRect(cx + cw * 0.36, cy + ch - 60, cw * 0.28, 60);
  // giocatori
  const pos = posizioni(form.modulo, form.titolari || []);
  for (const q of pos) {
    const x = cx + q.x * cw, y = cy + q.y * ch;
    const nome = (form.nomi && form.nomi[q.numero]) || (rosa.get(q.numero) || {}).nome || '';
    g.fillStyle = '#0006'; g.beginPath(); g.arc(x + 4, y + 6, 46, 0, Math.PI * 2); g.fill();
    g.fillStyle = q.numero === (form.titolari || [])[0] ? '#24262b' : '#fff';
    g.beginPath(); g.arc(x, y, 44, 0, Math.PI * 2); g.fill();
    g.lineWidth = 7; g.strokeStyle = BLU; g.stroke();
    g.fillStyle = q.numero === (form.titolari || [])[0] ? '#fff' : BLU;
    g.font = '800 46px system-ui, Segoe UI, sans-serif'; g.fillText(String(q.numero), x, y + 16);
    g.font = '700 25px system-ui, Segoe UI, sans-serif';
    const t = nome.length > 14 ? nome.slice(0, 13) + '.' : nome;
    g.lineWidth = 5; g.strokeStyle = '#0a2a10'; g.strokeText(t, x, y + 82); g.fillStyle = '#fff'; g.fillText(t, x, y + 82);
  }
  // modulo e panchina
  g.fillStyle = BLU; g.font = '800 44px system-ui, Segoe UI, sans-serif'; g.textAlign = 'left';
  g.fillText(form.modulo || '', 60, 1262);
  g.font = '600 26px system-ui, Segoe UI, sans-serif'; g.fillStyle = '#44505c';
  const pan = (form.panchina || []).map((n) => n + (rosa.get(n) ? ' ' + rosa.get(n).nome.split(' ').pop() : '')).join('   ');
  g.fillText('PANCHINA', 60, 1316);
  g.font = '500 26px system-ui, Segoe UI, sans-serif';
  g.fillText(pan.length > 62 ? pan.slice(0, 61) + '…' : pan, 60, 1356);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

export function creaLavagna(renderer, ambiente, dati, form) {
  const rosa = new Map(dati.giocatori.map((g) => [g.numero, g]));
  const scena = new THREE.Scene();
  scena.background = new THREE.Color(0x9aa0a6);
  scena.environment = ambiente;
  scena.environmentIntensity = 0.7;
  const R = dati.raggio || 4.5, A = dati.altezza || 3.0;
  const mat = (colore, rough = 0.7, metal = 0) => new THREE.MeshStandardMaterial({ color: colore, roughness: rough, metalness: metal });

  // sala: pavimento in legno, parete circolare, soffitto, zoccolo e panche, come lo spogliatoio
  const pav = new THREE.Mesh(new THREE.CircleGeometry(R, 72), mat(0x8c6b4b, 0.45));
  pav.rotation.x = -Math.PI / 2; pav.receiveShadow = true;
  const parete = new THREE.Mesh(new THREE.CylinderGeometry(R, R, A, 72, 1, true), new THREE.MeshStandardMaterial({ color: 0xe6e9ec, roughness: 0.85, side: THREE.BackSide }));
  parete.position.y = A / 2;
  const sof = new THREE.Mesh(new THREE.CircleGeometry(R, 72), mat(0xf2f3f4, 0.9));
  sof.rotation.x = Math.PI / 2; sof.position.y = A;
  const zoccolo = new THREE.Mesh(new THREE.CylinderGeometry(R - 0.01, R - 0.01, 0.18, 72, 1, true), new THREE.MeshStandardMaterial({ color: 0x173f9a, roughness: 0.6, side: THREE.BackSide }));
  zoccolo.position.y = 0.09;
  scena.add(pav, parete, sof, zoccolo);
  for (let i = 0; i < 6; i++) { // panche lungo la parete
    const a = (i / 6) * Math.PI * 2 + 0.26;
    const b = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.06, 0.38), mat(0xb08a62, 0.5));
    b.position.set(Math.sin(a) * (R - 0.45), 0.42, -Math.cos(a) * (R - 0.45)); b.rotation.y = -a;
    const base = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.4, 0.3), mat(0x2b2f36, 0.7));
    base.position.set(b.position.x, 0.2, b.position.z); base.rotation.y = -a;
    scena.add(b, base);
  }

  // cavalletto con la lavagna al centro, rivolta verso +z (la camera guarda da li)
  const cav = new THREE.Group();
  const legno = mat(0x6b4a2f, 0.5);
  const gamba = (x, z, rz, rx, h = 2.15) => {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, h, 12), legno);
    m.position.set(x, h / 2 * 0.96, z); m.rotation.z = rz; m.rotation.x = rx; m.castShadow = true; return m;
  };
  cav.add(gamba(-0.62, -0.03, -0.06, -0.1), gamba(0.62, -0.03, 0.06, -0.1), gamba(0, -0.6, 0, -0.32, 2.25));
  const cornice = new THREE.Mesh(new THREE.BoxGeometry(1.68, 2.24, 0.07), mat(0x2b2f36, 0.5, 0.3));
  cornice.position.set(0, 1.5, 0.12); cornice.rotation.x = -0.1; cornice.castShadow = true;
  const tela = new THREE.Mesh(new THREE.PlaneGeometry(1.56, 2.12), new THREE.MeshStandardMaterial({ map: disegnaLavagna(form, rosa), roughness: 0.35, metalness: 0 }));
  tela.position.set(0, 1.5, 0.158); tela.rotation.x = -0.1;
  const vassoio = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.05, 0.14), legno);
  vassoio.position.set(0, 0.36, 0.2);
  cav.add(cornice, tela, vassoio);
  cav.position.set(0, 0, -0.4);
  scena.add(cav);

  // luci: soffitto caldo + faro sulla lavagna
  scena.add(new THREE.HemisphereLight(0xffffff, 0xcfd3d8, 0.55));
  const centro = new THREE.PointLight(0xfff3e6, 9, 14, 1.8); centro.position.set(0, A - 0.25, 1.2); scena.add(centro);
  const faro = new THREE.SpotLight(0xffffff, 26, 9, 0.5, 0.6, 1.4);
  faro.position.set(0.6, 2.9, 2.2); faro.target.position.set(0, 1.5, -0.3); scena.add(faro, faro.target);

  const cam = new THREE.PerspectiveCamera(46, 16 / 9, 0.1, 40);
  const st = { az: 0, tAz: 0, dist: 3.5, ora: 0, trascina: false, x0: 0, az0: 0, fermo: false };
  const posa = () => {
    const a = st.az;
    cam.position.set(Math.sin(a) * st.dist, 1.5, -0.4 + Math.cos(a) * st.dist);
    cam.lookAt(0, 1.45, -0.4);
  };
  const dom = renderer.domElement;
  const giu = (e) => { st.trascina = true; st.x0 = e.clientX; st.az0 = st.tAz; };
  const muovi = (e) => { if (st.trascina) st.tAz = Math.max(-1.0, Math.min(1.0, st.az0 - (e.clientX - st.x0) * 0.004)); };
  const su = () => { st.trascina = false; };
  const attiva = (on) => {
    const f = on ? 'addEventListener' : 'removeEventListener';
    dom[f]('pointerdown', giu); window[f]('pointermove', muovi); window[f]('pointerup', su);
  };
  posa();
  return {
    scena, cam, attiva,
    ridim(w, h) { cam.aspect = w / h; cam.fov = w / h < 1 ? 64 : 46; cam.updateProjectionMatrix(); },
    passo(dt) {
      st.ora += dt;
      if (!st.trascina) st.tAz = Math.sin(st.ora * 0.35) * 0.32;   // ondeggia piano finche' non si trascina
      st.az += (st.tAz - st.az) * Math.min(1, dt * 4);
      posa();
    },
    ripristina() { st.az = st.tAz = 0; posa(); },
    // distanza della camera dal cavalletto (il passaggio dallo spogliatoio la fa avanzare dalla parete); senza argomento la legge
    distanza(d) { if (d !== undefined) { st.dist = d; posa(); } return st.dist; },
  };
}
