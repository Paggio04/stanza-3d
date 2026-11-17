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
