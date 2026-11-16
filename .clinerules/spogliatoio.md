# Spogliatoio — regole del ciclo v01 (CORREZIONE, sostituisce l'aggiunta precedente)

Concept: spogliatoio interattivo la sera. Le maglie stanno strette sulla barra,
girate di sbieco come su una barra vera: di ognuna si vede una fetta del retro
e la manica. Hover = la maglia si gira verso chi guarda; click = si stacca,
viene avanti e gira a 360 gradi.

## Dati squadra

- `squadra.json`: 20 giocatori, reparti PORTIERI 2 / DIFENSORI 6 /
  CENTROCAMPISTI 7 / ATTACCANTI 5. Numeri 1-20 in ordine per reparto.
- `colori.maglia` = rossa, `colori.dettagli` = panna (riga sulle maniche),
  `colori.portieri` = `#24262b` (segnaposto, maglie portieri di altro colore).
- `stemma: null` su ogni giocatore = usa lo scudo segnaposto sul petto.
  Quando arriva lo stemma vero, sostituire il segnaposto (copri-stemma a sinistra).
- Nomi giocatori segnaposto.

## Convenzioni scena (unita in metri, Z su)

- Camera a +Y che guarda verso il muro (muro a y=0, barra a y=0.42, z=1.78).
- Geometria maglia (locale): petto = +Y (scudo + interno colletto davanti),
  schiena = -Y, maniche lungo X. Rotazione Z: 0 = petto alla camera,
  115 = tre quarti di schiena, 160 = quasi di schiena (prima maglia a sinistra
  di ogni reparto), hover maglia 10 rot 0 (petto pieno) + 25 cm avanti.
- Passo calcolato da ingombro reale: semi-ampiezza =
  (0.76*|cos| + 0.11*|sin|)/2, aria 2 cm fra maglie strette, 35 cm fra reparti.
  Le maglie NON si compenetrano (verifica via intervalli X).
- Nomi oggetti: `Maglia_01`...`Maglia_20`, `Gruccia_01`...`Gruccia_20`, `Barra`
  (un solo oggetto: tubo + piega a gomito a destra verso il muro + piastre).
  Maglia e gruccia condividono origine sul gancio: ruotano insieme.
- Maglia completa anche davanti: petto chiuso, stemma-segnaposto sul petto
  a sinistra di chi la indossa, interno colletto scuro visibile, riga
  `dettagli` su ogni manica. Dietro liscia (numeri NON richiesti in v01).
- Targhe: una per reparto sul muro sopra il gruppo, `Targa_*` + testo
  `"DIFENSORI 6"` (nome + quante maglie ha).
- Maglia 10 (CENTROCAMPISTI) = maglia demo: primo piano, fronte e girata.

## Luce sera

- Armadietti a doghe verticali di legno scuro dietro la barra (`Parete_Doghe`).
- Striscia calda sul muro dietro/sopra le maglie + POINT caldi vicini alla barra.
- Striscia blu tenue in basso lungo il pavimento + punto luce blu.
- Wash SUN caldo + riempimento freddo; resto in penombra. Niente AREA: i loro
  quad finivano inquadrati dalla camera; solo SUN/POINT/SPOT.

## Render (cartella `render/`)

- `v01_16x9.png` 1920x1080: tutta la barra.
- `v01_primo_piano.png` 1920x1080: dettaglio sulla maglia 10 in sede.
- `v01_maglia_fronte.png` 1080x1080: maglia 10 staccata, vista davanti.
- `v01_maglia_girata.png` 1920x1080: come 16x9 ma maglia 10 verso camera e 25 cm avanti.
- Rigenera con: `blender -b -P scripts\spogliatoio_v01.py` (salta i render esistenti).
- File Blender salvato in `spogliatoio_v01.blend` (stato base, senza varianti).

## Mappa interazioni per il sito

- Rest: rotazione reparto (115 / 160 per la prima a sinistra).
- Hover: animare rotazione Z verso ~0 gradi (petto alla camera).
- Click: +Y avanti e spin 360 gradi attorno a Z, poi rientro.
- Le targhe sopra i gruppi diventano le etichette di reparto del sito.

## TODO futuri (fuori v01)

Numeri dietro la schiena, stemma reale al posto dello scudo, normal-map
tessuto, panca e armadietti laterali, turntable 360 per il click.

## Pubblicazione

A fine di ogni ciclo: commit con il numero del ciclo (es. 'Ciclo v02') e push
su main, così il revisore vede tutto.
