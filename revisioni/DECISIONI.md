# Decisioni

## Il prodotto

Uno spogliatoio 3D per il sito di una squadra di calcio. È pensato per essere **venduto a qualsiasi squadra**:
cambiano solo stemma, colori, nomi e numeri, tutti presi da `squadra.json`. Il primo cliente è il Resco Reggello.

## Il percorso (scorrendo la pagina)

1. Video vero con il drone: discesa dall'alto sullo stadio.
2. Vicino al campo, si entra nel tunnel dei giocatori (3D).
3. Dal tunnel si arriva nello spogliatoio: una sala circolare con un armadietto per giocatore e la sua maglia appesa di schiena, con nome e numero.
4. Lì lo spogliatoio diventa interattivo.

Formati: orizzontale (16:9) e verticale (9:16).
Stile: realistico, come la foto di riferimento.

## Il riferimento

Dal 17/11/2026 i riferimenti sono due foto di spogliatoi di una squadra professionistica, in `riferimenti/`:
- `spogliatoio_circolare.png`: **il riferimento principale**, per armadietti, targhe, sedute, soffitto e luce;
- `spogliatoio_vista_larga.png`: solo per come appare la sala intera vista da un capo: l'arco degli armadietti che si chiude, lo stemma grande in primo piano sul pavimento, il lettino da massaggi al centro. Pannelli neri, panca continua e striscia di luce a pavimento di questa foto **non** si prendono.

Le foto sono solo in locale: sono di terzi, quindi non vanno nel repository.

**Lo spogliatoio deve venire così.** Della foto si prendono forma, disposizione, materiali e luce. Non si copiano stemma, sponsor, nomi e foto di quella squadra: al loro posto vanno i dati di `squadra.json` e i segnaposto.

Cosa c'è nella foto:
- **Sala circolare.** Gli armadietti corrono lungo tutta la parete curva; dalla camera se ne vedono una decina insieme.
- **Armadietto**, uno per giocatore, in legno caldo, separato dal vicino da un pilastro bianco. Dall'alto in basso:
  - targa con il nome, nel colore della squadra, con la scritta bianca;
  - cornice con la foto del giocatore;
  - nicchia con il fondo scuro, dove la maglia pende da una gruccia, di schiena: nome sopra e numero grande sotto, centrati;
  - seduta imbottita bianca, con sopra il completo piegato e una borraccia;
  - zoccolo in legno con un vano per le scarpe.
- **Pavimento** chiaro e lucido, con lo stemma della squadra grande al centro. Al centro della sala un lettino da massaggi (dalla seconda foto).
- **Soffitto** bianco: travi scure a raggiera che convergono su un anello centrale con faretti; fra le travi, pannelli luminosi.
- **Luce** chiara e uniforme, dal soffitto. I colori vivi stanno solo su targhe, maglie e stemma.

## Lo spogliatoio

- 20 armadietti in cerchio, uno per giocatore della rosa.
- Gli 11 titolari stanno nell'arco davanti alla camera principale: nella vista 16:9 si vedono tutti. Le 9 riserve stanno nel resto del cerchio.
- Ordine per reparto (portieri, difensori, centrocampisti, attaccanti): prima i titolari, poi le riserve.
- Portieri in un colore diverso.
- Una sola mesh di maglia condivisa dalle 20 copie: nel sito va caricata una volta sola.

## L'interazione (riferimento: un video TikTok di uno spogliatoio interattivo)

Restano tutte le animazioni del video, portate nella sala circolare. Si costruisce tutto da zero, senza codice o materiale di altri.

- **In alto:** nome della squadra e «Prima squadra · stagione».
- **Filtri a pillola con il conteggio** (Tutti 20, Portieri 3…): con un clic la camera ruota veloce attorno al centro della sala fino al reparto.
- **Passaggio sopra una maglia:** la maglia esce un poco dall'armadietto e si gira verso chi guarda, mostrando nome e numero. Sotto compare un'etichetta con numero, nome e ruolo.
- **Clic:** la camera si avvicina, la maglia esce dall'armadietto e resta appesa davanti, di 3/4; le altre si scuriscono. Si può girare trascinando.
- **Scheda del giocatore** (pannello scuro a destra): numero grande, nome e cognome, ruolo, posizione nella rosa (es. 10/20), pulsanti giocatore precedente e successivo, «Torna alla sala» (anche con Esc).
- **In basso:** scritta che scorre e il suggerimento «passa su una maglia · clicca per staccarla».
- **Con «riduci movimento» attivo:** niente animazioni, solo passaggi diretti.

## I cicli

| Ciclo | Cosa | Stato |
|---|---|---|
| v01 | Spogliatoio con la barra in Blender | Superato dal cambio di riferimento |
| v02 | La maglia vera (stoffa, pieghe, nome e numero) | Fatto, inaccettabile: da rifare (vedi v02.md) |
| v03 | Un armadietto come nel riferimento, con la maglia vera | Fatto, non accettato (maglia simulata, armadietto a scatole) |
| v03b | Lo stesso armadietto, con la maglia costruita da `scripts/maglia.py` (v03.md) | Superato: la sala intera è già fatta (`scripts/sala.py`) |
| v04 | La sala circolare: 20 armadietti, soffitto, pavimento con stemma, luci, render 16:9 e 9:16 | Prima versione fatta (`scripts/sala.py`); da rifinire |
| v04b | Sala a 21 slot (20 armadietti + porta del tunnel), soffitto con anello, guance a trapezio, pilastri con incavo, pavimento a specchio; maglia con colletto a nastro, ombre a vertici, maniche svasate | Fatto (17/11), da rifinire |
| v05 | Tunnel (`scripts/tunnel.py`, `web/tunnel.glb`), percorso di camera (`tunnel.json`) con API `sala.percorso` (tempo, scorrimento, video del drone) | Prima versione fatta e collaudata in 16:9 e 9:16 (17/11); da rifinire |
| v06 | Esportazione per il sito (.glb leggeri, texture) | Prima versione fatta (`web/sala.glb`, 8 MB) |
| v07 | Pagina interattiva nel sito (Three.js), dati dalla rosa | Prima versione fatta (`web/sala.js`); da collaudare sul sito |

## Regole fisse

- Dati della squadra solo in `squadra.json`, mai nello script.
- Testi segnaposto («GIOCATORE N», scudo grigio «STEMMA», «FOTO») finché il club non manda i dati veri. Niente nomi inventati.
- Uno script unico e riproducibile, che salva il `.blend` e i render.
- La maglia si costruisce con `scripts/maglia.py` (dal 17/11 non piu' congelato: lo migliora Claude Code; ogni modifica aggiorna l'hash con `scripts/hash_maglia.py`). Niente simulazione di stoffa.
- Niente installazioni né download: solo Blender e quello che c'è nella cartella.
- A ogni ciclo, prima di chiudere: mettere ogni render accanto alla foto di riferimento, correggere, scrivere in `REGISTRO.md` cosa manca.

## Ancora aperto

- Dal club: stemma ufficiale, colori ufficiali, i 20 giocatori con nome, numero e titolari, le foto per le cornici.
- Scheda del giocatore: i dati in più (nazionalità, data e luogo di nascita, squadra precedente, altezza) non ci sono ancora nella rosa del sito. Vanno aggiunti e ci vuole il consenso dei giocatori. Se ne parla al v07.

## Stato del 17/11/2026 (lavoro di Claude Code, collaudato nel browser)

Fatto: sala a 21 slot (20 armadietti + porta), tunnel con percorso a tempo e a scorrimento (16:9 e 9:16), gesti a molla, versione leggera per telefoni, glb compresso (`web/README.md`).

Scelte e alternative scartate:
- **Porta nella sala**: 21 slot a 17,1 gradi, raggio 4,5 m; porta allo slot 0 (phi = 180) dove prima c'era una riserva. Scartato 22 slot con pannello di riempimento (asimmetrico) e il varco di una baia (le riserve scendevano a 19).
- **Gesti**: molle in JS con parametri in `sala.json`, al posto dei 40 clip NLA (non interrompibili, raccordo hover -> selezione approssimato). Il tessuto ondeggia con uno shader sui vertici (stesso per maglia, scritte e scudo), la gruccia oscilla come un pendolo attorno all'asta.
- **Luce cotta (AO su UV di un armadietto)**: non fatta. `unisci_statico()` fonde le 20 baie per materiale e servirebbe un secondo set di UV identico per ogni copia prima del join; il guadagno sopra ombre in tempo reale + SAO non e' valso la complessita'. Il tunnel invece ha la luce cotta nei colori dei vertici (analitica).
- **LOD**: la decimazione di Blender schiaccia la maglia (due fogli quasi piani a 6 cm): per i telefoni la maglia si ricostruisce con triangoli di 1,7 cm (`maglia.STEP`) e il testo piu' rado.
- **Maglia**: colletto a nastro vero (V davanti, tondo dietro, filetto bianco), ombreggiatura a vertici (valli, ascelle), svasatura delle maniche, sponsor segnaposto, trama senza righe (le righe regolari davano moire' da vicino). Lo sponsor sul petto era specchiato: corretto.

Ancora diverso dalle foto:
- Manca la foto della maglia di riferimento (`riferimenti/maglia_riferimento.png`): la maglia e' fatta dalla descrizione; le maniche non si sovrappongono al busto (stesso strato, solo svasate).
- Soffitto: anello centrale e travi, ma i pannelli luminosi sono un'unica fascia, non trapezi separati; niente gradiente di luce.
- Legno senza venatura fine in primo piano, targhe e cornici piatte, pavimento a specchio finto (un piano riflesso, non fisico), stemma e sponsor segnaposto.
- Tunnel: pareti lisce, niente cartelli, spalti ripetitivi; il cielo si vede poco.
- Fps reali non misurabili dal pannello del browser (senza GPU): non dichiarati.
