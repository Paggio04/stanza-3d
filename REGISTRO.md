# REGISTRO.md — Seggiolini + scale chiuse (18/11/2026, 2 render Cycles)

2 render di verifica da `scripts/prove/render_seggiolini.py` (stessa scena del sito):
`render/stadio_seggiolini.png` (campo dall'uscita del tunnel), `render/tunnel_scale_chiuse.png`
(interno tunnel verso la scalinata).

Misure: TUNNEL_OK out_prova/tunnel.glb 941560 facce 4903. Nessun TUNNEL_ERRORE (budget 60000 facce).

Cosa si vede nei 2 render (fatti, niente giudizi).
- stadio_seggiolini: campo dall'uscita del tunnel: erba, cartelloni a blocchi, spalti blu
  con seggiolini veri (seduta + schienale) in 2 file per anello, fascia bianca col nome,
  tetto chiaro sopra, facciata grigia con scritta blu sopra la bocca.
- tunnel_scale_chiuse: interno tunnel: pareti blu, LED a soffitto, pavimento grigio con
  corsia e riga oro solo sul piano, scalinata con pedate chiare e alzate scure senza buchi.

Correzioni di questo giro (fatti, nei file indicati).
- scripts/tunnel.py: ogni gradino della scalinata e una scatola chiusa (non si vede
  il sotto); `_seggiolini` con seduta + schienale nei colori della squadra (LOD: 1 spicchio
  ogni 4, 2 file per anello, 3 seggiolini per spicchio); budget facce resta 60000.
- web/tunnel.glb + web/tunnel.json rigenerati (vedi Misure) e copiati in web/.
- maglia.py NON toccata (congelata).

Rimane diverso (giro dopo, dopo verifica nel browser).
- Cartelloni ancora a blocchi invece di scritte vere; erba con macchie; cielo piatto.
- Sala: da rivedere dopo lo stadio (bianchi, legno, maglie).
- render di prova cancellati da render/ prima del commit (solo web/ + script).


Dati: bake_all ok 100f; mesh 7429V/8863F sald=157; pin spalla 120;
alt=0.763 larg=0.776 prof=0.064 (spessore vero 6.4 cm, nel range 4-12).

8 giri fatti, nessuno passa tutti e 5 i punti della prova maglia.
L'armadietto non si costruisce sopra una maglia non accettata:
fermo qui come da revisione. Script unico
`scripts/spogliatoio.py`, dati da `squadra.json`
(titolari 1 4 5 6 7 10 11 12 16 17 18, colori reparto maglia/portieri).

## v03_prova_maglia.png (800x800)

Maglia bianca intera dalla testa al fondo, in asse, pieghe verticali
morbide, fondo curvo, bordi lisci senza denti, nessun lembo
accartocciato. Gronde: gruccia grigia dentro le spalle con gancio che
sale verso l'asta (ma il tubo scende troppo e buca la schiena al
centro), colletto ad anello ma in tinta maglia (doveva essere blu
dettagli) e troppo spesso (ciambella azzurra appoggiata sopra).

Punti: 1 si (spalle/gancio ok) — 2 problema (manica sx gonfia sul
fianco, non scende) — 3 si (bordi lisci) — 4 si (pieghe + fondo
curvo) — 5 no (non si giudica qui, vedi lato). NON passa.

## v03_prova_maglia_lato.png (800x800, camera a +X)

Lama bianca verticale alta il giusto, spessore misurato 6.4 cm:
nella norma 4-12, ma solo perche' il pannello resta quasi piatto.
Difetti bloccanti: la manica destra si piega all'indietro a 90 gradi
e resta orizzontale (braccio spezzato); un lembo di stoffa penzola
dalla manica fino al fianco; il busto e' girato di taglio con le
braccia a croce invece di scendere lungo i fianchi come nella foto.

Punti: 5 NO (lama da tavoletta con manica rotta, non volume vero).

## v03_maglia_retro.png (1080x1080, da -Y)

Nome GIOCATORE 10 in alto centrato e numero 10 sotto, blu, corti
(w=0.308, niente ritaglio) — ma illeggibili nel render: controluce,
la stoffa resta scura con alone. Lo scudo grigio e' finito dietro.
Numero 25 cm ok come misura, non come vista.

Punti (scritte): no — si' solo per misura, no per leggibilita'.

## v03_maglia_fronte.png (1080x1080, da +Y)

Petto bianco col scudo grigio visibile, colletto ad anello troppo in
vista, riga di scritte del retro in trasparenza sul petto (si vede
a specchio). Numero e nome non devono vedersi dal davanti: NO.

## v03_armadietto.png (1200x1800) e v03_armadietto_34.png (1600x1200)

Armadietto leggibile: vano legno chiaro, pilastri bianchi, targa blu
con scritta (specchiata, da girare), cornice legno con FOTO grigia
(specchiata), nicchia scura, seduta bianca, kit piegato blu/bianco,
borraccia, scarpe nere nei vani. Maglia appesa all'asta di schiena
ma: pende dal tubo che esce dalle spalle (la gruccia vera resta
dentro e non si vede), scritte del retro assenti nel vano,
colletto azzurro fuori scala. Confronto foto: manca la caduta
naturale, gancio esile, niente spessore maniche; nel complesso
sembra una scatola con maglietta stampata, non il riferimento.

## Cosa blocca (al ciclo dopo)

1. Lato: manica a 90 gradi + stoffa piatta = rifare caduta maniche
   (spalla 40 gradi, bending 0.4, niente pressione oltre 0.02).
2. Scritte: nome/numero sulla schiena restano ombra — servono luci
   dietro (-Y) piu' forti e materiale emissive leggero, oppure scritte
   come mesh piana sopra stoffa con offset 5 mm invece di shrinkwrap.
3. Fronte pulito: il retro non deve vedersi — scritte solo su un
   lato, materiale stoffa double-side off o spessore che copre.
4. Targa/FOTO specchiate (rot Z 180 di troppo).
5. Colletto/polsini a costine blu vere, non torus azzurro: tubo
   sottile (r=6 mm) lungo il bordo scollo e polsi, colore dettagli.
6. Gruccia: un solo oggetto dentro le spalle, gancio corto che esce
   dal collo e abbraccia l'asta; niente tubi che bucano la stoffa.
7. Scarpe e borraccia: solo forme semplici, ma sopra il pavimento.

