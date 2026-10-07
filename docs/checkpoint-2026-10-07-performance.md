# Checkpoint — 7 ottobre 2026: prestazioni

Ripresa e chiusura delle ottimizzazioni richieste per dettaglio chiamata,
importazione ZIP e mappa qualità. [Misure e migrazione](checkpoint-2026-10-06.md).

- Schema 13, indice eventi per sorgente/orario; backup consistente su disco
  `/data/kpe.sqlite3.pre-v13.bak` creato e conservato. Nessuna riscrittura dei log.
- Query esatte per chiamata vincolate all'indice dedicato, evitando scansioni
  della sorgente intera. Selettore metriche limitato alle chiamate selezionate,
  mantenendo tutte le metriche note del catalogo.
- PQ: evidenze preparate una volta per prospettiva nella richiesta, intestazioni
  necessarie senza interi corpi dei log, integrale degli intervalli uniti.
  Formule, prove, ambiguità, celle dirette prioritarie e stime nei vuoti invariati.
- La mappa e il percorso vengono disegnati appena disponibili: Switch Network
  caricati separatamente, con indicatore proprio e protezione da risposte obsolete.
  Un errore della ricerca Switch Network non nasconde le celle qualità.

## Verifiche

234 test Python passati; controlli sintattici app/geography/diagnostics/analysis-ui
positivi. Smoke Docker su volume dedicato: import, deduplicazione e persistenza
dopo restart. Browser su istanza sintetica: upload ZIP, confronto, cambio metrica,
dettaglio chiamata e mappa visibile con ricerca Switch Network ritardata di 20 s;
console senza errori. Nessun import sintetico nel database personale.

Misure HTTP sull'archivio locale di circa 5 GB, indicative e dipendenti da cache:
- Eventi della chiamata di prova: 4,16 → 0,024 s.
- Opzioni metriche: 53,87 → 0,015 s; timeline rete finale: 0,082 s.
- Mappa completa: circa 40 s per 4.849 celle e 97.555 campioni intermedi;
  i circa 10,6 s della ricerca Switch Network non bloccano più la visualizzazione.
  Il benchmark con profiler prima superava 90 s; versione finale circa 58 s.
- Import sintetico: prima prova 2,91 → 2,24 s. Benchmark riproducibile con
  `python scripts/benchmark_import.py`; risultati prima/dopo identici.

La mappa globale resta costosa sui periodi estesi; restringere il periodo aiuta.
Nessuna cache persistente o riduzione nascosta dei campioni. Ulteriori aggregati
sono da concordare. Il progresso dettagliato degli import e il download del DB
in streaming restano proposte, non implementate in questo intervento.

Servizio locale: http://127.0.0.1:8080. Installazione/upgrade autonomi e rollback
nella [guida](getting-started.md). Questo checkpoint accompagna il commit delle ottimizzazioni successive a
233c114, con pubblicazione su origin/main richiesta dal proprietario il 7 ottobre.
Verificati 234 test Python, 3 test JavaScript e sintassi frontend. ZIP, database,
backup, screenshot e risultati locali sono esclusi dalla pubblicazione.
