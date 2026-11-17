# Spogliatoio — regole generali

Leggere `revisioni/` all'inizio di ogni ciclo (valgono `DECISIONI.md` e
l'ultima revisione). Non modificare mai `revisioni/`.

- Lavorare solo in questa cartella (`C:\Progetti\stanza-3d`).
- Niente installazioni, niente download, niente internet: solo Blender
  e quello che c'e' gia' nella cartella.
- I dati della squadra stanno solo in `squadra.json`: nome, stagione,
  colori, stemma (null = segnaposto), reparti e i 20 giocatori
  (`GIOCATORE N` finche' il club non manda la rosa vera). Lo script non
  contiene dati della squadra, li legge.
- Un solo script riproducibile: `scripts/spogliatoio.py`. Ricostruisce
  da zero, salva `spogliatoio.blend` e i render in `render/`.
  I file di prova con percorsi fissi vanno in `scripts/prove/`.
- Testi segnaposto in grigio (`GIOCATORE N`, scudo `STEMMA`), mai nomi inventati.
- Maglia vera, niente parallelepipedi: sagoma piatta + cloth + rifinitura.
- A ogni ciclo, prima di chiudere: guardare davvero ogni render,
  correggere cio' che non torna, scrivere in `REGISTRO.md` cosa mostra
  ogni render.
- A fine ciclo: commit con il nome del ciclo (es. `Ciclo v02`) e push
  su main.

## Convenzioni scena v02 (unita in metri, Z su)

- Camera a +Y che guarda verso il muro (muro a y=0, barra a y=0.42, z=1.78).
- Geometria maglia (locale): petto = +Y (scudo + interno colletto davanti),
  schiena = -Y (nome + numero), maniche lungo X. Una sola mesh
  (`Maglia_Base`) condivisa dalle 20 copie (linked duplicate): nel sito
  si carica una volta sola. Portieri = stesso oggetto, materiale diverso
  assegnato per-copia (slot 0 sovrascritto sull'istanza).
- Nomi oggetti: `Maglia_01`...`Maglia_20`, `Gruccia_01`...`Gruccia_20`,
  `Barra` (un solo oggetto), `Maglia_Base` (originale nascosto, mai
  renderizzato). Maglia e gruccia condividono origine sul gancio:
  ruotano insieme.
- Sagoma piatta (metri): busto largo 0.52 e lungo 0.72, maniche corte
  di 0.20 con spalla inclinata di 12 gradi, girocollo. Due pannelli
  (fronte e retro) dalla stessa sagoma, a 6 cm di distanza, uniti su
  fianchi, spalle e maniche. Collo, fondo e polsi restano aperti.
  Griglia fitta: lato di circa 1.5 cm. UV = sagoma piatta pre-simulazione.
- Gruccia dentro le spalle; il gancio esce dal collo.
- Rotazione Z: riposo ~75 gradi dalla schiena (si vede una fetta di
  retro con un pezzo di numero), prima maglia di ogni reparto +20 gradi
  (~55 dalla schiena). Hover maglia 10: rot 0 (petto pieno) + 25 cm avanti.
- Passo calcolato sull'ingombro reale misurato della mesh simulata:
  semi-ampiezza = (larghezza*|cos| + profondita*|sin|)/2, aria 2 cm fra
  maglie strette, 35 cm fra reparti. Barra lunga al massimo 8 m.
  Le maglie NON si compenetrano (verifica via intervalli X).
- Maglia completa anche davanti: petto chiuso, scudo segnaposto grigio
  e piatto (~7 cm) sul petto a sinistra di chi la indossa, interno
  colletto scuro e visibile, riga `dettagli` su ogni manica.
- Retro: nome in alto (maiuscolo, ~6 cm) e numero grande sotto (~25 cm),
  colore `scritte`, da `squadra.json`. Testo convertito in mesh e
  suddiviso, con Shrinkwrap sul retro (offset 1 mm): segue le pieghe.
- Materiale maglia: opaco (roughness 0.7), sheen leggero, bump con
  trama di maglia fine. Niente plastica.
- Targhe: una per reparto sul muro sopra il gruppo, `Targa_*` + testo
  `"DIFENSORI 6"` (nome + quante maglie ha). Al centro sopra la barra:
  scudo segnaposto grigio ~60 cm con scritta `STEMMA`.
- Maglia 10 (CENTROCAMPISTI) = maglia demo: primo piano, fronte, retro e girata.

## Luce sera

- Armadietti a doghe verticali di legno scuro dietro la barra (`Parete_Doghe`).
- Striscia calda sul muro dietro/sopra le maglie + POINT caldi vicini alla barra.
- Striscia blu tenue in basso lungo il pavimento + punto luce blu.
- Wash SUN caldo + riempimento freddo; resto in penombra. Niente AREA: i loro
  quad finivano inquadrati dalla camera; solo SUN/POINT/SPOT.

## Render (cartella `render/`, Cycles 64 campioni, denoise)

- `v02_prova_maglia.png` 800x800, 32 campioni: maglia da sola. Guardarla
  prima di costruire la scena (se sembra una scatola, correggere).
- `v02_barra.png` 1920x1080: prospettiva lungo tutta la barra, camera a
  30 gradi rispetto al muro. Tutte e 20 le maglie visibili, nessuna tagliata.
- `v02_reparto.png` 1920x1080: frontale sui centrocampisti, le 6 maglie
  riempiono la larghezza. E' la vista principale del sito.
- `v02_9x16.png` 1080x1920: reparto difensori, verticale.
- `v02_retro.png` 1080x1080: maglia 10 da dietro, nome e numero leggibili
  sulle pieghe.
- `v02_fronte.png` 1080x1080: maglia 10 staccata, vista davanti, intera.
- `v02_girata.png` 1920x1080: come reparto, con la 10 girata verso camera
  e 25 cm piu' avanti.
- Rigenera con: `blender -b -P scripts\spogliatoio.py` (salta i render esistenti).
- File Blender salvato in `spogliatoio.blend` (stato base, senza varianti).

## Mappa interazioni per il sito

- Rest: rotazione reparto (~75 gradi dalla schiena, +20 per la prima a sinistra).
- Hover: animare rotazione Z verso ~0 gradi (petto alla camera).
- Click: +Y avanti e spin 360 gradi attorno a Z, poi rientro.
- Le targhe sopra i gruppi diventano le etichette di reparto del sito.

## TODO futuri (fuori v02)

Stemma reale al posto dello scudo, normal-map tessuto, panca e
armadietti laterali, turntable 360 per il click (v03 tunnel e percorso
camera, v04 export .glb, v05 pagina interattiva).
