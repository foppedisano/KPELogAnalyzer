# Checkpoint — 4 ottobre 2026 · mappa per zone

Questo è il punto di ripartenza per una nuova chat nel repository
`KPELogAnalyzer`. Leggere prima `AGENTS.md`, [installazione autonoma](getting-started.md)
e questo documento. Ramo di lavoro: `main`; remoto previsto:
`https://github.com/foppedisano/KPELogAnalyzer.git`. Individuare il commit che
contiene questo checkpoint con `git log -1 -- docs/checkpoint-2026-10-04.md`.
Verificare sempre `git status --short` e `git log -1` prima di modificare file:
lo stato di una chat successiva può essere cambiato.

## Decisioni dell'utente da preservare

- Nella **Mappa qualità generale** servono informazioni per zona, non la
  sovrapposizione confusa di tutti i tragitti.
- Il dato diretto valutabile ha sempre precedenza, anche se scarso: colore e
  media della cella non vanno miscelati alle stime. Stime disponibili nella
  stessa cella restano consultabili separatamente nel dettaglio.
- Le zone attraversate senza dati diretti possono usare coordinate interpolate
  e qualità AWT del secondo. Non propagare valori alle zone soltanto vicine.
- Nella **singola chiamata** mantenere linee e puntini; l'utente intende ancora
  valutarne nel dettaglio la resa. Non trasformarla automaticamente nella vista
  generale per celle e non aggiungere snapping stradale/ferroviario implicito.
- L'intero progetto deve essere installabile e verificabile da un coding agent
  su una nuova macchina. Docker è il percorso principale; Python/Node host
  non sono requisiti per l'uso Docker. Nessuna dipendenza Python esterna.
- Il proprietario non ha concesso una licenza generale: non aggiungerne una.

## Stato implementato

- Schema SQLite **12**, parser **1.12.0**; questa modifica non cambia schema.
- PQ `awt-occupancy-4`: 100 meno occupazione degli underrun AWT su finestre di
  un secondo, ritagliate sui confini della chiamata. 100 assume logging AWT
  completo; non è una qualità percettiva certificata.
- `app/call_route.py`: `linear-time-1`, un punto al centro di ogni secondo intero
  compreso fra posizioni della stessa chiamata/sorgente, gap massimo 120 s,
  nessuna estrapolazione. Qualità ricalcolata dagli episodi, non dai valori
  agli estremi. Cache e ambiguità escluse; prove degli estremi e dell'audio.
- `app/perceptual_geo.py`: aggregazione `linear-time-cells-1`. Celle `direct`
  piene; celle `estimated` trasparenti/tratteggiate solo nei vuoti. Riepiloghi
  separati in `estimate` se esiste un dato diretto. Nessuna persistenza delle
  stime, propagazione alle celle vicine o fusione fra chiamate/sorgenti.
- Generale: opzione **Mostra zone stimate**, attiva di default solo per PQ;
  dettagli con media, minimo/massimo, secondi interessati da underrun, durata
  underrun, passaggi, giorni, divario fra estremi e prime 20 prove per cella.
  La media generale continua a usare soltanto dati diretti.
- Singola chiamata: **Percorso e qualità**, selettore sorgente, linee e punti,
  media/minimo degli intervalli interpolati separati dalle celle dirette.
- API generale invia celle compatte, non la vecchia lista di `routes` grezzi.
  `route_samples` conta gli intermedi prima delle esclusioni AWT. Limiti:
  100.000 intermedi e 10.000 celle, con errore esplicito oltre soglia.
- Backfill iOS `ios-location-config-1`, tentativi utente/connettività schema 12,
  transitori e analisi precedenti restano disponibili; vedere le guide collegate.

## Dove leggere e intervenire

- [Metodo PQ e geometria](perceptual-quality.md), [guida mappa](geography.md).
- [API](api.md), [architettura](architecture.md), [limiti aperti](open-issues.md).
- UI: `app/static/geography.js`, stile in `app/static/style.css`.
- Regressioni sintetiche: `tests/test_call_route.py`, `tests/test_perceptual.py`.
- [Verifiche e cronologia](validation.md), [catalogo generato](metrics.md).
- Per cambiare metrica/semantica leggere prima `docs/metrics.md` e
  `docs/diagnostics.md`; rigenerare il catalogo tramite il suo script.

## Ambiente e aggiornamento

L'istanza personale Docker è su **http://127.0.0.1:8080/**, progetto Compose
`kpeloganalyzer`, servizio `analyzer`, volume persistente `kpe-data` nel Compose
(il nome Docker è prefissato dal progetto). Non modificarne il nome per errore.
Prima degli aggiornamenti sono stati creati backup consistenti nel volume:
`pre-map-routes-20261004-154740.sqlite3` e `pre-zone-map-20261004-194516.sqlite3`.
Questi nomi sono locali, non file distribuiti nel repository.

Le prove browser hanno usato DB sintetico separato in `test-results/route-preview`
e porte 8097–8099. Verificare quali processi siano ancora attivi prima di
riutilizzare quelle porte. Non confondere queste istanze con i dati personali.
ZIP, database, backup, screenshot e risultati locali sono ignorati da Git.

Per una nuova macchina seguire la guida d'installazione. Per aggiornare una
copia esistente: controllare modifiche locali, backup consistente, pull
fast-forward solo se appropriato, `docker compose up --build -d`, health e
Ctrl+F5. Un semplice restart non incorpora il codice nuovo. Ripristini sempre
in una nuova cartella/volume, mai sopra un database aperto.

## Verifiche e lavoro residuo

217 test Python locali superati e ripetuti con successo in Python 3.12 Docker,
repository montato in sola lettura e nessuna rete nel container di test.
6 test Node delle scale superati, sintassi di tutti gli script JavaScript e
collegamenti Markdown locali verificati; catalogo rigenerato dalla sua fonte.
Prove browser completate come indicato nel registro.

Smoke Docker-only: build, health, importazioni sintetiche, deduplicazione e
riavvio riusciti. Conteggi invariati prima/dopo: 2 import, 2 chiamate, 27 metriche
(sono dati sintetici, non conteggi dell'archivio personale). Il container
`kpe-doccheck-20261004` sulla porta di prova 18087 è stato arrestato; immagine e
volume `kpe-doccheck-20261004-data` restano locali per eventuale ispezione. Il servizio personale è stato ricostruito e la
risposta geografica aggiornata verificata. Nessuna pubblicazione di dati reali.

Restano limiti dichiarati, non attività autorizzate da eseguire automaticamente:
map matching stradale/ferroviario, stima calibrata dell'incertezza geografica,
cache per archivi estesi e validazione percettiva. Non abbassare arbitrariamente
PQ 100 per rendere la mappa più varia. Aspettare il riscontro dell'utente sulla
resa delle celle e del percorso singolo prima di cambiare il modello.

## Prompt per riprendere

> Riprendi KPELogAnalyzer. Leggi AGENTS.md e docs/checkpoint-2026-10-04.md,
> controlla stato Git e servizio locale. La mappa generale usa celle dirette
> prioritarie e celle stimate nei vuoti; il dettaglio chiamata conserva il
> percorso. Non modificare dati personali né pubblicare log. Il progetto deve
> restare installabile autonomamente da un coding agent. Attendi la mia nuova
> richiesta prima di avviare ulteriori evoluzioni del modello.

## Integrazione MCP — 5 ottobre 2026

MCP 1.3.0 espone 12 strumenti: aggiunti percorso chiamata, campioni PQ e
timeline rete/servizi; `analytics_geo_cells` accetta PQ con precedenza diretta
e stime separate. Catalogo e copertura includono il contratto corrente e le
viste `a_connectivity` / `a_user_attempts`. Nessun cambio al modello, schema o
parser; nessuna associazione dei tentativi per numero/tempo. Le viste contano
osservazioni grezze e non riproducono la deduplicazione del registro UI.
Configurazione Docker-only e riconnessione in [analisi MCP](analytics.md).
Restano distinti profili temporali MOS e celle PQ; limite 4 MiB per i nuovi
adattatori, senza paginazione PQ/percorso. Vedere il registro delle verifiche
per gli esiti di questa integrazione. Il punto di ripartenza successivo è
[checkpoint MCP del 5 ottobre](checkpoint-2026-10-05.md).

Validazione: 220 test passati in locale e in Python 3.12 Docker isolato.
Servizio locale ricostruito e aggiornato il 5 ottobre, health positivo sullo
stesso `http://127.0.0.1:8080/`. Handshake MCP stdio reale verificato: versione
1.3.0, 12 strumenti e catalogo aggiornato. Backup consistente locale
`pre-mcp-130-20261005-043502.sqlite3` nel volume dati, verificato con quick_check;
nessun import demo sull'istanza personale. Riconnettere il client MCP per
ricaricare gli strumenti. Commit e push autorizzati dall'utente il 5 ottobre;
verificare il commit e lo stato remoto come indicato nel checkpoint successivo.
