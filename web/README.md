# Spogliatoio 3D per il sito

Cartella pronta da copiare nel sito. Three.js r160 (importmap in `index.html`).

| File | Cosa |
|---|---|
| `sala.js` | modulo: `avviaSala(contenitore, opzioni)` |
| `sala.glb` / `sala_bassa.glb` | sala (5,3 MB, ~720k triangoli misurati con `sala.stat()` con tunnel) e versione per telefoni (2,2 MB, ~320k); meshopt |
| `sala.json` | rosa (numero, nome, reparto, slot, angolo), porta, parametri dei gesti (molle) |
| `tunnel.glb` / `tunnel.json` | tunnel dei giocatori, facciata sotto gli spalti, bordo campo; percorso della camera |
| `index.html` | pagina di prova (`?q=alta|bassa`, `?intro=1`, `?scroll=1`, `?video=URL`) |

```js
import { avviaSala } from './sala.js';
const sala = await avviaSala(document.getElementById('sala'), {
  glb: 'sala.glb', glbBassa: 'sala_bassa.glb', dati: 'sala.json',
  tunnel: 'tunnel.glb', percorso: 'tunnel.json',          // facoltativi
  qualita: 'auto',                                          // 'alta' | 'bassa' | 'auto'
  video: { src: 'drone.mp4', poster: 'drone.jpg' },        // facoltativo: il video del drone
  velocita: 2.6,                                            // m/s di crociera dell ingresso (default); oppure durataPercorso in ms
});
```

## Ingresso (video -> tunnel -> sala)
- `sala.percorso.introduzione()`: video del drone (se c'e'), dissolvenza, tunnel a tempo, arrivo nella sala interattiva.
- `sala.percorso.progresso(p)`: `p` da 0 (bordo campo) a 1 (sala). Pilotabile dallo scorrimento.
- `sala.percorso.collegaScorrimento(elemento)`: `p` = scorrimento dentro `elemento` (alto N viewport; il canvas sta in `position:sticky`). Vedi `index.html?scroll=1`.
- `sala.percorso.avvia({durata, da})` (Promise), `.ferma()`, `.salta()`, `.attivo`.
- La posa finale e' quella di `VISTE.sala`: i due pezzi combaciano per costruzione. Con "riduci movimento" salta direttamente alla sala.

## Sala
`sala.seleziona(numero)`, `sala.filtra('DIFENSORI')`, `sala.torna()`, `sala.prossimo(+1)`, `sala.distruggi()`. Hover, clic, trascinamento, Esc e frecce sono gia' collegati.
Formato 9:16: l'angolo orizzontale si stringe da solo e la scheda diventa un pannello in basso.

## Rigenerare i file (Blender 5.3)
```
blender -b -P scripts/sala.py   -- web <cartella assoluta>        # sala.glb + sala.json
blender -b -P scripts/sala.py   -- web <cartella assoluta> lod    # sala_bassa.glb
blender -b -P scripts/tunnel.py -- <cartella assoluta>            # tunnel.glb + tunnel.json
```
I dati della squadra stanno solo in `squadra.json`. Prova locale: `python -I -m http.server 8765 --bind 127.0.0.1` dentro `web/`.
