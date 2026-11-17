# Revisioni

Qui il revisore scrive, a ogni ciclo, cosa va e cosa no, e le istruzioni per il ciclo dopo.
Cline legge questi file e non li modifica.

## Come si usa con Cline

Ogni ciclo parte da una **chat nuova** di Cline. La chat del ciclo prima, piena di render, è troppo pesante (quella di v01 era di 100 MB): se la si riapre, Cline si ferma con «Hub connection closed (code=1006)».

All'inizio di ogni ciclo basta scrivere a Cline:

> Fai `git pull`, leggi `revisioni/DECISIONI.md` e l'ultima revisione in `revisioni/`, poi esegui il ciclo che chiede. Alla fine commit con il nome del ciclo e push su main.

## Indice

| File | Cosa |
|---|---|
| [DECISIONI.md](DECISIONI.md) | Cosa stiamo costruendo e le scelte già prese |
| [v01.md](v01.md) | Audit del ciclo v01 e istruzioni per il ciclo v02 |
| [v02.md](v02.md) | Audit del ciclo v02 e istruzioni per il ciclo v03 |
