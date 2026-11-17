# Decisioni

## Il prodotto

Uno spogliatoio 3D per il sito di una squadra di calcio. È pensato per essere **venduto a qualsiasi squadra**:
cambiano solo stemma, colori, nomi e numeri, tutti presi da `squadra.json`. Il primo cliente è il Resco Reggello.

## Il percorso (scorrendo la pagina)

1. Video vero con il drone: discesa dall'alto sullo stadio.
2. Vicino al campo, si entra nel tunnel dei giocatori (3D).
3. Dal tunnel si arriva nello spogliatoio: 20 maglie in fila su una sola barra, di schiena, con nome e numero.
4. Lì lo spogliatoio diventa interattivo.

Formati: orizzontale (16:9) e verticale (9:16).
Stile: realistico, la sera prima della partita (luce bassa e calda, una nota blu in basso).

## Lo spogliatoio

- 20 maglie, una per giocatore della rosa, divise per reparto: portieri, difensori, centrocampisti, attaccanti.
- Una sola barra. Le maglie sono strette e girate di sbieco, come su una barra vera: di ognuna si vede una fetta di retro.
- Sul muro: una targa per reparto con il conteggio (es. «DIFENSORI 6») e lo stemma della squadra al centro.
- Portieri in un colore diverso.
- Una sola mesh di maglia condivisa dalle 20 copie: nel sito va caricata una volta sola.

## L'interazione (riferimento: un video TikTok di uno spogliatoio interattivo)

Si costruisce tutto da zero, senza codice o materiale di altri.

- **In alto:** nome della squadra e «Prima squadra · stagione».
- **Filtri a pillola con il conteggio** (Tutti 20, Portieri 3…): con un clic la camera scorre veloce lungo la barra fino al reparto.
- **Passaggio sopra una maglia:** la maglia si gira verso chi guarda e mostra nome e numero. Sotto la barra compare un'etichetta con numero, nome e ruolo.
- **Clic:** la camera si avvicina, la maglia esce dalla fila e resta appesa davanti, di 3/4; le altre si scuriscono. Si può girare trascinando.
- **Scheda del giocatore** (pannello scuro a destra): numero grande, nome e cognome, ruolo, posizione nella rosa (es. 10/20), pulsanti giocatore precedente e successivo, «Torna alla barra» (anche con Esc).
- **In basso:** scritta che scorre e il suggerimento «passa su una maglia · clicca per staccarla».
- **Con «riduci movimento» attivo:** niente animazioni, solo passaggi diretti.

## I cicli

| Ciclo | Cosa | Stato |
|---|---|---|
| v01 | Spogliatoio in Blender: stanza, barra, 20 maglie | Fatto, da rifare la maglia (vedi v01.md) |
| v02 | La maglia vera (stoffa, pieghe, nome e numero) | Da fare |
| v03 | Tunnel e percorso della camera: video 16:9 e 9:16 | Dopo |
| v04 | Esportazione per il sito (.glb leggeri, texture) | Dopo |
| v05 | Pagina interattiva nel sito (Three.js), dati dalla rosa | Dopo |

## Regole fisse

- Dati della squadra solo in `squadra.json`, mai nello script.
- Testi segnaposto («GIOCATORE N», scudo grigio «STEMMA») finché il club non manda i dati veri. Niente nomi inventati.
- Uno script unico e riproducibile, che salva il `.blend` e i render.
- Niente installazioni né download: solo Blender e quello che c'è nella cartella.
- A ogni ciclo, prima di chiudere: guardare ogni render, correggere, scrivere in `REGISTRO.md`.

## Ancora aperto

- Dal club: stemma ufficiale, colori ufficiali, i 20 giocatori con nome e numero di maglia.
- Scheda del giocatore: i dati in più (nazionalità, data e luogo di nascita, squadra precedente, altezza) non ci sono ancora nella rosa del sito. Vanno aggiunti e ci vuole il consenso dei giocatori. Se ne parla al v05.
