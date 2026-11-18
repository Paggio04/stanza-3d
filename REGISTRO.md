# REGISTRO.md — Realismo sito v2 (video 18/11/2026 09:54, 10 fotogrammi + 2 utente)

Fotogrammi dal video `Videos/Registrazione 2026-11-18 095402.mp4` (10 scatti Blender VSE,
`render/video2_*.png`) + 2 fotogrammi utente: tunnel (interno con scalinata) e sala (arco titolari).

Misure: TUNNEL_OK out_prova/tunnel.glb 512488 facce 2371; WEB_OK out_prova/sala.glb 5565532;
SALA_MISURE triangoli_stimati 403994 figli_maglia 180 peso 5565532 (budget 6.0 MB / 900k tri).
Nessun SALA_ERRORE, nessun TUNNEL_ERRORE.

Cosa si vede nei 12 fotogrammi del sito (fatti, niente giudizi).
- video2 f047: nero con scritta "Carico la sala..." al centro.
- video2 f094-f188: campo dall'uscita del tunnel: erba verde con macchie, righe bianche,
  cartelloni a blocchi ai lati, spalti a mosaico blu/rossi, scritte a blocchi, tetto chiaro,
  facciata grigia con scritta blu "RESCO REGGELLO" sopra la bocca buia del tunnel.
- video2 f235-f283 (tunnel dritto): pareti blu uniformi, strisce LED bianche a soffitto
  e lungo le pareti, pavimento grigio con 2 righe bianche che corrono e riga oro centrale,
  scalinata finale grigia senza stacchi fra pedate e alzate, fondo scuro con porta.
- video2 f330 (curva tunnel): parete blu che curva verso la porta, porta azzurra con armadietti
  e maglie sullo sfondo, quadretti neri sulle pareti (aliasing delle strisce LED lontane).
- video2 f377-f471 (sala): arco degli 11 titolari, pareti/pilastri/sedute/pavimento bianchi
  senza ombre, legno chiaro uniforme, maglie bianche piatte appese, targhe blu, stemma blu
  piatto a terra.
- foto utente tunnel: scalinata grigia con riga chiara che corre al centro fino in fondo,
  senza profondita fra un gradino e l'altro.
- foto utente sala: 10 armadietti, bianchi tutti uguali, legno chiaro, maglie piatte,
  stemma blu piatto.

Differenze dai riferimenti.
- Scalinata: riga chiara che corre al centro senza stacchi (sembra una strada, non gradini);
  pedate e alzate stesso grigio = niente profondita.
- Tunnel: pareti blu piatte (luce cotta senza volume); strisce LED sulle pareti fanno
  quadretti neri da lontano; corsia grigia troppo vicina al pavimento.
- Sala: bianchi tutti uguali (pareti/pilastri/sedute/pavimento); legno chiaro slavato;
  maglie bianche piatte; soffitto ancora emissivo.

Correzioni di questo giro (fatti, nei file indicati).
- scripts/tunnel.py: tolta ogni riga che corre sulla scalinata (corsia/oro solo sul piano);
  alzate scure #2b2e34 contro pedate chiare = i 12 gradini si leggono da costruzione;
  luce cotta con componente laterale (le pareti blu prendono volume); luce esterna
  0.80 -> 0.62 (niente piu bruciato); corsia scurita #8f97a3 -> #838b96.
- scripts/sala.py: parete #e4e5e6 -> #d5d7da (staccata dai pilastri); pilastri/cuscino
  scuriti (#dedfe2/#cfd1d4); pavimento #b9bdc4 -> #a9adb6; soffitto emis 0.55 -> 0.35,
  centro 0.40 -> 0.25, tamburo 0.35 -> 0.20.
- web/tunnel.glb + web/sala.glb + json rigenerati (vedi Misure) e copiati in web/.
- maglia.py NON toccata (congelata).

Rimane diverso (terzo giro, dopo verifica nel browser).
- Strisce LED sulle pareti del tunnel: da valutare se toglierle (fanno quadretti neri).
- Legno procedurale invece di foto vera; maglie poco modellate dalla luce.
- video2 + render di prova cancellati da render/ prima del commit (solo web/ + script).


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

