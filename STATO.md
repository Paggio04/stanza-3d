# STATO.md

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

Nota: `scripts/maglia.py` non e' piu' congelato per Claude Code; ogni modifica aggiorna l'hash in `revisioni/v03.md` con `scripts/hash_maglia.py`.

## Stato del 17/11/2026 sera (lavoro Cline: HD + fluidita, NON collaudato nel browser 3D)

Fatto e pushato su `main`:
- **Pacchetto A (solo `web/sala.js` + `web/index.html`)**: pixel-ratio fino a 3 col composer HD, specchio pavimento 2048 meno lattiginoso (forza 0,20, sfocatura 3x3), ombre 4096, luce riequilibrata (exposure 1,0 / ambiente 0,38 in alta), anisotropia su tutte le texture, discesa automatica se fps <45 o un frame supera 120 ms (via SAO, specchio, ombre), `window.sala.ultimoControllo` in console.
- **Fluidita (fix freeze)**: in `auto` niente SAO, ombre 2048, specchio 1024, pixel-ratio max 2; il massimo (SAO + 4096 + specchio 2048 + pixel-ratio 3) solo con `?q=alta`.
- **Pacchetto B (`.glb` rigenerati)**: legno 1024 con venatura incisa (curva a S, contrasto), 21 trapezi luminosi separati 8 mm sotto l'anello (anti z-fighting), 12 faretti, stemma rialzato (8/11 mm), fughe scure fra pannelli, tunnel con texture 1024 e JPEG 90. Pesi: sala 5,57 MB / 404k tri, bassa 2,34 MB / 165k tri, tunnel 754 KB / 1051 facce — tutti nei budget, zero `SALA_ERRORE`.
- **Cartelli tunnel rimossi**: `SPOGLIATOIO`/`CAMPO` sfarfallavano dopo 2 fix (mesh condivisa, poi z-fighting) — pareti lisce, nota da mettere in `REGISTRO.md` dal revisore.
- **Render HD v04** (`scripts/sala.py`): tre inquadrature 1920/128 scritte (`v04_16x9`, `v04_9x16`, `v04_armadietto` in `render/`), MAI ESEGUITE — il render 1920/128 su CPU non ha prodotto output in ~1h, fermato. Da lanciare di notte o a 1280/64.

Da verificare nel browser (io non ho GPU, non li ho visti):
1. freeze spariti in `auto`, `window.sala.ultimoControllo` dopo ~10 s;
2. sfarfallio trapezi/fughe sparito, legno piu inciso (`?q=alta` per il confronto);
3. `window.sala.stat()` per triangoli e chiamate reali.

## Stato del 18/11/2026 (Claude Code, secondo giro: stadio, tunnel, animazione; collaudato nel browser)

Fatto (commit 3209408, 3029aa2, 66b21ab):
- **Stadio rifatto** (`scripts/tunnel.py`): ciotola a 3 anelli con trapezi veri (prima parallelogrammi = buchi a spicchio), UV continue, texture spalti 128x64 seggiolini con nome a mosaico leggibile (verso: u positivo, righe dell'array dall'alto), muro di base blu notte con cartelloni e varco del tunnel, facciata attorno alla bocca, campo su tutto il disco con aree, cerchio, porte, 4 maxischermi ai lati/in fondo, `far` camera 220.
- **Campo 90 cm sopra il pavimento del tunnel** (`ST_QUOTA`): i gradini (ora PIENI) finiscono a filo del campo; tutti i materiali `Esterno_*` sono rialzati in `Raccolta.costruisci`.
- **Tunnel** come nella foto Camp Nou: blu notte, pavimento grigio-azzurro, corrimano dorato centrale con montanti + laterali, scudi grandi, LED. Filetto staccato di 6 mm (z-fighting).
- **Animazione**: ingresso a 2,6 m/s con rampe coseno (era ease cubico: 8 m/s a meta', accel max 66 m/s2 -> 3,4); durata automatica ~15,8 s; bob legato al passo (1,1 m, 12 mm). Calo qualita' automatico: mediana su 2 s, 4 s di riscaldamento, 2 finestre di fila (`sala._valuta` testabile; con la mediana sostituita dal massimo il test diventa rosso). Shader e texture compilati prima della partenza (non misurato: niente GPU nel pannello).

Sostituito/rimosso: bagliore piano alla bocca, spalti a strisce, muro grigio liscio, pannelli bianchi sulle pareti (ora scudi), corsia centrale del pavimento (ora corrimano), anelli con gap sul lato +x, maxischermi fuori posizione, `bump="pavimento HD"` (resta da correggere in `sala.py`).

Ancora diverso dalle foto (lavoro per la prossima sessione, vedi nota di passaggio):
- Stadio: seggiolini a mosaico piatto, niente luce cotta/ombre del tetto/cielo vero, erba senza fili, tetto senza raggi, cartelloni senza LED, niente vomitori/fasce di cemento, nessuna scritta gigante.
- Tunnel: materiali tutti `MeshBasicMaterial` (sala.js li sostituisce): niente riflessi su corrimano/pavimento; mancano pareti rosse accanto ai gradini e corrimano inclinati.
- Barre grigie viste una volta all'arrivo nella sala: NON riprodotte (canvas 1024x768, aspect e fov costanti per tutto il percorso): probabile artefatto dello screenshot.
- Maglia, spogliatoio, gesti: invariati in questo giro.

## Stato del 18/11/2026 (Claude Code, terzo giro: luce, cielo, materiali; collaudato nel browser)

Fatto (commit 4e58915, c7734a6, 7c48287):
- **Luce cotta con sole unico** (`tunnel.py`: `SOLE`, `luce_esterna`, `_bloccato`): direzione sole fissa (da +x e un po' da -u, 55 gradi: di lato, appena davanti alla camera di partenza; con 38 gradi il tetto metteva in ombra quasi tutto il campo), ombra di spalti e tetto per raggio contro il profilo della ciotola (`_profilo`), occlusione del cielo a 8 raggi, cielo/terra emisferici. Ciotola, campo e tetto suddivisi (6 x ~10 per spicchio, campo a 2,5 m) per portare l'ombra nei vertici. **Bug trovato**: le normali degli anelli erano capovolte (`cross(e2,e1)` in un mondo con y specchiata): prima la luce "esterna" era piatta 0,62-0,92 e dipendeva solo da n.z; ora `cross(e1,e2)`.
- **Cielo**: `scripts/cielo.py` (Sky Texture a scattering multiplo, equirettangolare 2048x1024, sole ruotato nell'azimut di `SOLE`, spalla morbida) -> `web/cielo.jpg` come `scena.background`; nebbia color orizzonte 90-260 m.
- **Texture**: seggiolini 128x64 con schienale/seduta/fessure/ombra per fila (1536x768), corridoi a gradini fra gli spicchi, diagonali di cemento, nome a mosaico; erba con fili + macchie + strisce e shader di dettaglio in `sala.js` (sfuma oltre 20-80 m); cartelloni LED a pixel (modo `piena`, x1,7); cemento dei corridoi, pareti con vomitori (tile 2 spicchi), facciata a finestre a nastro che chiude gli spalti sotto il tetto, intradosso con travi radiali e fascia con nastro LED, maxischermi con telaio, tiranti e nome della squadra.
- **Tunnel**: pareti a pannelli con zoccolo, pavimento a giunti, luce cotta divisa per `GAIN_INTERNO` (1,8, prima saturava a 1 e dava pareti piatte), pareti della scalinata blu squadra, corrimani oro inclinati sui gradini (`Raccolta.sbarra`). `sala.js`: oro/pavimento/pareti in `MeshStandardMaterial` con la luce cotta come emissione (`onBeforeCompile`) e riflessi dell'ambiente; stadio resta `MeshBasicMaterial` cotto.
- **Peso**: `tunnel.glb` 2,0 MB (17,4k facce, meshopt), `tunnel_bassa.glb` 0,73 MB (7,8k facce, texture dimezzate; scelto da `?q=bassa`/auto debole via `opz.tunnelBassa`). `sala.stat()` con `?q=bassa`: 324k triangoli (di cui tunnel 15,7k); alta 721k come prima. Nessun errore nuovo in console.
- Percorso e animazione NON toccati (2,6 m/s).

Sostituito/rimosso: seggiolini 3D sparsi (`_seggiolini`), texture spalti 8 px, erba a macchie, gradiente di cielo canvas (resta solo come fallback), colori piatti dell'esterno, pannelli chiari/corsia del tunnel, `Esterno_Muro/Cemento` a tinta unita.

Ancora diverso dalle foto:
- Ombra del tetto: si vede come fascia scura sui due anelli alti delle tribune (verificato da camera libera sopra il campo, non e' netta come in foto: celle da ~1 m); il campo e' in sole. Lato +x le tribune sono in ombra intera.
- Seggiolini = texture piatta (nessuna geometria), niente spettatori, niente scritta gigante a tutto spicchio, tetto senza struttura a vista, maxischermi senza contenuto animato.
- Il tunnel non ha pareti rosse (le ho fatte blu squadra), niente LED lineari a parete, nessuna ombra nel tunnel dal sole.
- Fps non misurabili (pannello senza GPU).
- Screenshot del pannello: dopo qualche `__v` la scena compare rimpicciolita nell'angolo; ricaricare la pagina prima di catturare.

