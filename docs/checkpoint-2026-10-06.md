# Checkpoint — 6 ottobre 2026

Stato consolidato per commit e push richiesti dal proprietario. Questa richiesta
supera la precedente sospensione della pubblicazione. Nessuna ulteriore evoluzione
del modello autorizzata. Dettagli precedenti: [Switch Network](checkpoint-2026-10-05-switch-network.md).

## Funzioni completate

- Switch Network espliciti evidenziati in eventi, timeline, grafici e mappe;
  MCP 1.4.0 con strumento dedicato, provenienza e limiti documentati.
- Log per famiglia, colori di provenienza e controlli compatti di visibilità e
  ambito. Tentativi con riferimento stabile e controlli uniformati.
- Nei tentativi, Tutto include da 60 secondi prima della richiesta fino alla
  prova del blocco inclusa, oppure alla richiesta se manca la prova. Default:
  soltanto richiesta e prova. Le sessioni SIP conservano il proprio intervallo.
- Indicatore condiviso di caricamento. Parser 1.12.1: riuso linea non estende
  sessioni locali già terminate; delimitazione in lettura per archivi precedenti.

## Verifica e servizio

232 test Python passati; sintassi JavaScript verificata. Controlli browser su
fixture sintetiche per famiglie, tentativi, visibilità e contesto, console pulita.
Ultima modifica della finestra temporale verificata tramite regressioni e API.
Docker locale ricostruito, health positivo: http://127.0.0.1:8080.
Nessuna migrazione o modifica dei dati personali per queste correzioni UI/API.

Verificata anche la segnalazione di importazione apparentemente ferma: il nuovo
import risultava salvato; il servizio rispondeva. CPU elevata osservata, causa
residua non accertata. Nessuna interruzione o riavvio durante la diagnosi.

## Limiti e prossime attività

- Esportazione database attuale tramite snapshot in memoria: per archivi di
  diversi GB può richiedere RAM eccessiva. Backup su disco/streaming da valutare;
  nessuna modifica all'esportazione effettuata e nessun database esportato.
- Stato/progresso delle fasi di importazione e aggiornamento registro da valutare.
- Riparazione completa delle associazioni storiche locali ancora da concordare.
- [TODO](todo.md) raccoglie le proposte, non autorizza sviluppi automatici.

ZIP, database, log reali e screenshot locali restano esclusi dal repository.
Installazione autonoma, backup e ripristino: [guida](getting-started.md).


## Ottimizzazioni successive richieste dal proprietario

Schema 13: indice `events(import_id,ts)` con migrazione versionata e backup
consistente su disco `.pre-v13.bak`. Nessuna riscrittura degli eventi o delle
metriche. La ricerca Switch Network limita i candidati ai file KPE e, per la
chiamata, alla sua finestra con margine per le richieste vicine ambigue.
PQ prepara le evidenze una volta per prospettiva nella richiesta; un integrale
degli intervalli uniti evita riordino e scansione completa per ogni secondo.
Le finestre delle altre prospettive vengono lette una volta per verificare le
ambiguità. Nessuna cache condivisa o modifica al metodo `awt-occupancy-4`.

234 test Python superati, incluse equivalenza dell'integrale con il riferimento,
backup/migrazione e conservazione di eventi e annotazioni. Smoke Docker su volume
sintetico separato: import iOS/Android, deduplicazione, metriche e persistenza dopo
riavvio positivi. Istanza di prova fermata, volume conservato.
Benchmark riproducibile: `python scripts/benchmark_import.py`, solo DB temporanei
con 150.000 eventi storici sintetici e ZIP da 10.008 eventi. Confronta risultati
identici con/senza indice; i tempi dipendono da cache e carico della macchina.


Misure locali finali (archivio circa 5 GB, tempi indicativi dipendenti da cache e
carico; non SLA): lista eventi della chiamata di prova 4,16 → 0,024 s; opzioni
metriche 53,87 → 0,015 s; timeline rete 0,082 s nella verifica HTTP finale.
Il benchmark con profiler della mappa PQ completa superava il limite di 90 s;
versione finale 57,8 s, risultato identico alle revisioni intermedie verificato
tramite digest. Richiesta HTTP senza profiler: 40,0 s, circa 4.800 celle e
97.500 campioni intermedi. La vista globale non è istantanea: restringere il
periodo riduce il lavoro. Non sono stati ridotti copertura, campioni o limiti.
Import sintetico: 2,91 → 2,24 s nella prima prova, 6,55 → 2,73 s sotto carico;
nessuno ZIP personale reimportato per misurare le prestazioni.

Le query di primo/ultimo evento e gli eventi strettamente attribuiti usano
l'indice esatto per chiamata: il nuovo indice per sorgente non deve indurre
scansioni dell'intero import. Test di regressione con 15.000 eventi estranei e
limite sul lavoro SQLite. Il selettore metriche legge le unità della selezione,
non di tutto l'archivio. Le intestazioni AWT sono lette senza trasferire i corpi
multilinea inutilizzati, conservando prove e log originali.

Migrazione locale completata, backup `/data/kpe.sqlite3.pre-v13.bak` conservato.
Confronto con il backup: importazioni, chiamate, prospettive e annotazioni
identiche. Servizio http://127.0.0.1:8080 attivo e health positivo.
