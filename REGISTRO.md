# REGISTRO.md — Realismo sito (video 18/11/2026, fotogrammi campo + tunnel + sala)

Fotogrammi dal video `Videos/Registrazione 2026-11-18 091754.mp4` (503 fotogrammi, Blender VSE):
f0 = nero "Carico la sala...", f1 = tunnel, f2 = sala; `render/video_campo_*.png` (campo subito
dopo il nero). Piu `render/prova_realismo_campo.png`, `render/prova_realismo_tunnel.png`,
`render/prova_sala_34.png` (Cycles, stessa scena con sole + mondo chiaro, per separare
geometria vera da difetti del viewer).

Confronto col riferimento Getty (spogliatoio Man Utd femminile, 10 baie rosse, sedute bianche,
stemma grande chiaro sul pavimento chiaro) e col tunnel vero (Camp Nou: pareti blu, corrimano oro,
LED a soffitto).

Misure: TUNNEL_OK out_prova/tunnel.glb 515420 facce 2395; WEB_OK out_prova/sala.glb 5565532;
SALA_MISURE triangoli_stimati 403994 figli_maglia 180 peso 5565532 (budget 6.0 MB / 900k tri).
Nessun SALA_ERRORE, nessun TUNNEL_ERRORE.

Cosa si vede nei fotogrammi del sito (fatti, niente giudizi).
- video_campo f003-f010: nero con scritta "Carico la sala..." al centro.
- video_campo f016-f150: campo dall'uscita del tunnel: erba verde con macchie scure, righe
  bianche sottili, cartelloni a blocchi colorati ai lati, spalti a mosaico blu/rossi con
  scritte a blocchi, tetto con facce chiare e macchie nere sui bordi, facciata grigia con
  scritta blu "RESCO REGGELLO" sopra la bocca nera del tunnel.
- video_frame f1: interno tunnel: pareti blu uniformi, strisce LED bianche a soffitto, pavimento
  grigio con righe bianche longitudinali, riga oro centrale, figure scure sullo sfondo.
- video_frame f2: sala circolare: pareti/pilastri/sedute/pavimento bianchi senza ombre,
  legno chiaro uniforme, maglie bianche piatte appese, targhe blu, stemma blu piatto a terra.
- prova_realismo_campo (Cycles): erba con macchie scure, cartelloni a blocchi, spalti a mosaico,
  facciata grigia piatta con scritta blu, cielo grigio uniforme.
- prova_realismo_tunnel (Cycles): pareti blu con filetto bianco e corrimano oro, pavimento grigio
  con corsia chiara e riga oro, LED a soffitto, fondo con porta e armadietti.
- prova_sala_34 (Cycles): 11 titolari in arco leggibili, pilastri bianchi, sedute bianche,
  legno chiaro, maglie bianche appese di schiena, stemma blu a pavimento.

Differenze dai riferimenti.
- Campo: erba con rumore forte e strisce poco visibili; mosaico spalti con moire da lontano;
  tetto con buchi neri sui bordi; cartelloni a blocchi invece di scritte vere.
- Tunnel: pareti blu piatte nel sito (luce cotta + materiale piatto); scalinata tagliata
  a fette bianche dalla corsia; LED a filo del soffitto.
- Sala: bianchi bruciati e appiattiti (pareti/pilastri/sedute/pavimento stessa luce); legno
  slavato; maglie piatte; soffitto troppo emissivo.

Correzioni di questo giro (fatti, nei file indicati).
- scripts/tunnel.py: faccia posteriore ciotole (A,D,C,B) invece di (A,C,B,D) che era
  autointersecata; erba con meno rumore; cartelloni con scritte stessa tinta scurita;
  corsia/oro anche sui gradini mai sulle alzate; LED 15 mm sotto il soffitto.
- web/sala.js: tunnel a doppia faccia, guadagno 1.3 -> 1.0, LED 3.2 -> 2.0,
  esposizione 1.0 -> 0.9, ambiente 0.38 -> 0.30, luce centrale 22 -> 18.
- scripts/sala.py: parete/pavimento/bianchi/cuscino/legno/nicchia/soffitto scuriti
  e resi meno emissivi (vedi diff git).
- web/tunnel.glb + web/sala.glb + web/tunnel.json + web/sala.json rigenerati da
  scripts/tunnel.py e scripts/sala.py -- web e copiati in web/.

Rimane diverso (secondo giro, dopo verifica nel browser).
- Campo: strisce erba con piu tile, mosaico spalti meno grossolano, cielo sfumato.
- Tunnel: pareti blu meno piatte nel sito, figure scure sullo sfondo da controllare.
- Sala: bianchi ancora vicini fra loro, legno procedurale, maglie poco modellate.
- maglia.py NON toccata (congelata).


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

