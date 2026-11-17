# Spogliatoio — regole generali

Valgono in ogni ciclo. Se la revisione più recente in `revisioni/` dice altro, vale la revisione.

## Lavoro

- All'inizio di ogni ciclo leggi `revisioni/DECISIONI.md` e l'ultima revisione. Non modificare mai `revisioni/` né `riferimenti/`.
- Lavora solo in questa cartella (`C:\Progetti\stanza-3d`). Niente file fuori, nemmeno di prova. Niente installazioni, download, internet: solo Blender e quello che c'è qui.
- I dati della squadra stanno solo in `squadra.json` (nome, colori, reparti, giocatori). Lo script non contiene dati della squadra, li legge. Testi segnaposto in grigio (`GIOCATORE N`, scudo, `FOTO`), mai nomi inventati.
- Due script: `scripts/spogliatoio.py` (la scena: salva `spogliatoio.blend` e i render) e `scripts/maglia.py` (la maglia). I file di prova vanno in `scripts/prove/`.
- I percorsi dei render sono sempre assoluti (`os.path.abspath`): un percorso relativo finisce in `C:\`.
- Blender si lancia staccato e con l'uscita su file: `Start-Process -FilePath 'C:\Program Files\Blender Foundation\Blender 5.3\blender.exe' -ArgumentList '-b -P <script>' -RedirectStandardOutput <log> -RedirectStandardError <log_err>`. Prima di rilanciare controlla che non ci siano Blender appesi (`Get-Process blender`).

## La maglia

- Si costruisce solo con `scripts/maglia.py`. È congelata: non si modifica, non si copia, non si «migliora».
- Vietati: Cloth o qualunque simulazione di stoffa; maglie fatte con parallelepipedi; maglie costruite a mano nello script della scena.
- Se `maglia.py` esce con errore o `maglia.verifica()` dà errori: fermati, scrivi l'errore in `REGISTRO.md`, fai commit e push. Non aggirarlo.

## Come si riferisce

- In `REGISTRO.md` si scrivono solo fatti: le misure stampate dallo script, una descrizione di cosa si vede in ogni render, l'elenco delle differenze dalla foto di riferimento. Niente «sì/no», «passa», «ok», «perfetto»: il giudizio lo dà il revisore.
- Se non riesci a sistemare lo stesso difetto dopo 2 tentativi, scrivilo in `REGISTRO.md` e vai avanti. Non girare a vuoto.
- A fine ciclo: commit col nome del ciclo scritto nella revisione e push su main.

## Scena dell'armadietto (metri, Z su)

- Camera principale a +Y che guarda verso −Y. La maglia ha la schiena verso la camera: `rotation_euler.z = pi`.
- Vano 0,95 x 2,6 x 0,55 in legno caldo; pilastri bianchi di 12 cm ai lati, più profondi del vano.
- Targa 0,60 x 0,12 nel colore «dettagli» con il nome in bianco; cornice 0,32 x 0,42 con segnaposto `FOTO`.
- Nicchia scura 0,80 x 1,10; asta cromata a z = 1,72 (raggio 0,012) lungo X; la maglia pende dal suo gancio.
- Seduta imbottita bianca a 0,45 m da terra; sopra completo piegato e borraccia; sotto zoccolo in legno con due vani e le scarpe.
- Luce chiara e uniforme dall'alto, niente penombra. Pavimento chiaro e lucido.
