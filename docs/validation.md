# Verifiche e stato della versione

[Indice](README.md) · [Limiti aperti](open-issues.md)

## Verifica corrente — 5 ottobre 2026, integrazione MCP

- **220 test Python superati** in locale e in Python 3.12 Docker, con repository
  montato in sola lettura, rete disabilitata e database sintetici temporanei.
- Verificato MCP stdio → HTTP per i 12 strumenti dichiarati e le nuove funzioni:
  PQ, percorso, connettività e scoperta celle PQ. Risposte confrontate con la UI/API,
  comprese celle dirette/stimate, campioni sotto 100 ed evidenze degli estremi.
- Verificati errori di input, scope delle nuove viste, esclusione del destinatario
  dei tentativi e del testo grezzo, authorizer SQL e limite di risposta 4 MiB
  con rollback. Nessuna modifica a frontend, formule, parser o schema.
- Aggiornate guide MCP, API, installazione autonoma, limiti e checkpoint.
- Immagine Docker ricostruita e servizio locale aggiornato il 5 ottobre;
  health host positivo su `http://127.0.0.1:8080/`, parser invariato `1.12.0`.
  Verificati handshake stdio reale, versione MCP `1.3.0`, 12 strumenti e
  nuovo catalogo via API. Backup consistente con `quick_check` positivo prima
  della ricreazione; stesso volume dati, nessuna importazione o migrazione.

## Verifica precedente — 4 ottobre 2026, mappa per zone

- **217 test Python superati** nell'ambiente locale; regressioni su qualità
  intermedia, minuti con 60 campioni, gap, cache, estremi discordanti, filtri,
  celle stimate, esclusione AWT e precedenza dei dati diretti senza mescolanza.
- Controlli `node --check` su frontend e test delle scale; catalogo generato
  dalla fonte e collegamenti locali verificati per la pubblicazione.
- Browser su DB sintetico isolato: importazione idempotente, dettaglio chiamata,
  cambio metriche, confronto, celle dirette/stimate, dettaglio prove,
  disattivazione delle stime e passaggio MOS. Percorso della singola chiamata
  conservato; nessun errore JavaScript osservato.
- Container applicativo aggiornato su `http://127.0.0.1:8080/`, health positivo
  e interrogazione geografica completata; backup consistente prima dell'upgrade.
  Nessun nuovo schema o reimportazione richiesti dalle stime.
- I 217 test sono passati anche in Python 3.12 Docker con repository in sola
  lettura. **6 test Node delle scale superati**. Lo smoke Docker-only ha
  verificato build, health, import, deduplicazione e persistenza dopo restart:
  2 import/2 chiamate/27 metriche sintetiche invariati; istanza di prova arrestata.
  Comandi nella [guida per coding agent](getting-started.md), dettagli nel
  [checkpoint corrente](checkpoint-2026-10-04.md).

La verifica non valida un modello percettivo, un tragitto stradale/ferroviario
né il valore predittivo delle stime. I dati sintetici non entrano nel DB personale.
Le sezioni successive sono cronologia, con conteggi e limiti della loro revisione.

## Verifica storica — 27 settembre 2026

- **115 test Python superati**, con database temporanei e fixture sintetiche:
  parser/API, attribuzione, migrazioni fino a schema 9, deduplicazione,
  MOS, geografia, mobilità e telemetria strutturata.
- Sintassi verificata per tutti gli script `app/static/*.js`.
- **3 test Node sulle scale superati**: conteggi interi piccoli/grandi/negativi,
  percentuali frazionarie e scala MOS con conservazione delle anomalie.
- Esempi telemetria v1 (9 record) e v1.1 (14 record) validati dalla CLI.
- Collegamenti Markdown locali verificati; catalogo rigenerato dalla fonte
  condivisa con UI/API, senza modificare a mano le schede generate.
- Nel collaudo browser del grafico: default MOS downstream, ricerca, aggiunta e
  rimozione di metriche, RTT/jitter sullo stesso pannello, perdita e pacchetti
  su scale distinte, zoom e cursore comuni, confronto chiamate e apertura import.
- Identificazione sorgenti e filtro copie storiche verificati via API e browser.
  Migrazione 8→9 provata due volte su copia del DB reale, preservando tutti
  i conteggi grezzi; backup automatico verificato prima dell’uso del nuovo schema.
- Docker aggiornato e health verificato su `http://127.0.0.1:8080/`.
  Il nuovo asset `call-chart.js` è servito correttamente.
- Smoke Docker isolato: due ZIP sintetici dello stesso produttore/Call-ID,
  prima chiamata importata e seconda ignorata; metadati e scarto persistono
  dopo il riavvio del processo. Nessun campione sintetico nel DB personale.

L'apertura del pannello import non equivale a un upload browser end-to-end.
Un precedente tentativo di upload nel browser incorporato aveva restituito
“Failed to fetch”; gli import sono coperti dai test HTTP e dallo smoke
Docker isolato, non da una nuova importazione sintetica nel DB personale.

Questi controlli non certificano semantiche proprietarie, accuratezza percettiva
MOS, copertura di ogni versione app/GW o previsioni di rete. I log reali, i DB e
le credenziali non fanno parte delle fixture pubblicate.

## Come ripetere i controlli

```sh
python -m unittest discover -v
python scripts/build_metric_docs.py
python -m app.telemetry docs/examples/telemetry-v1.jsonl docs/examples/telemetry-v1.1.jsonl
node --test tests/test_chart_scale.js
node --check app/static/app.js
node --check app/static/call-chart.js
node --check app/static/diagnostics.js
node --check app/static/analysis-ui.js
node --check app/static/geography.js
node --check app/static/mos.js
node --check app/static/topology.js
node --check app/static/conversations.js
```

Node serve soltanto alle verifiche frontend, non all'esecuzione della piattaforma.
Lo smoke `python scripts/smoke_test.py --demo` aggiunge import: usarlo soltanto
su un servizio di prova o su una nuova installazione. I test unitari creano DB
isolati. Non eseguire esperimenti sui dati personali per aggiornare questa pagina.

## Cronologia

Le sezioni datate sotto descrivono la versione provata **in quel momento**.
Frasi come “MOS non disponibile” o vecchi conteggi di test non rappresentano
la funzionalità corrente. I conteggi storici degli archivi non sono campioni
sintetici di riferimento né totali attesi su ogni installazione.

## Verifica iniziale — 24 settembre 2026

Verifica su Windows con il runtime Python locale, senza dipendenze del progetto:

- Suite `unittest`: parser e API HTTP in database temporanei; lifecycle, riuso linea, rotazioni, più dispositivi, ID diversi contemporanei, registrazioni escluse, sfide auth, chiamate fallite, statistiche raw, dati mancanti/anomali, ZIP non sicuri, SQL read-only, CSV, backup standalone, offset e conversazioni.
- Controllo sintassi JavaScript con `node --check app/static/app.js`.
- Validazione configurazione con `docker compose config --quiet`.
- Verifica browser: caricamento ZIP reale e deduplicazione, apertura chiamata, grafico RTCP, confronto di due chiamate, passaggio a metrica KPE con avviso unità raw, query SQL.

Un archivio privato locale di 24 file, escluso dal repository e dall'immagine Docker, produce:

| Voce | Risultato |
|---|---:|
| Chiamate identificate | 150 |
| Eventi indicizzati | 310.369 |
| Valori metrici estratti (incluse statistiche last/avg/min/max) | 32.717 |
| Metriche non attribuite a una chiamata | 16.018 |
| Valori finiti anomali conservati | 90 |

Questi conteggi sono una verifica di integrazione sul campione, non una prova di copertura di tutti i formati KPE. Molte chiamate più vecchie hanno solo segnalazione SIP: le rotazioni KPE coprono un periodo più ristretto. I report senza una finestra di linea dimostrabile rimangono non attribuiti.

Il primo tentativo era bloccato da socket AF_UNIX obsoleti di Docker Desktop (`dockerInference` e `engine.sock`, errore Windows 1920). Dopo aver arrestato Docker e la sola distribuzione WSL `docker-desktop`, le cartelle dei socket temporanei sono state rinominate come backup. Il motore Docker 29.5.3 è ripartito senza eliminare immagini o volumi.

**Collaudo Docker completato:** build dell'immagine Python 3.12-slim, avvio Compose, health API, importazione ZIP sintetico, deduplicazione e verifica dei dati dopo riavvio del container. Una copia consistente del database locale è stata poi trasferita nel volume persistente, verificando nuovamente i conteggi del campione. Il servizio containerizzato è pubblicato su `127.0.0.1:8080`; l'istanza Python diretta è stata arrestata e il database locale originale è stato conservato.


## Diagnostic extension — 2026-09-24

- 32 synthetic parser/API tests pass: version-1 migration and backup, preserved IDs/annotations, replay idempotency, NART section scoping, legitimate 20 ms, old/new explicit units, isolated warning events, counters/reset, interpolation/no-extrapolation/gaps, clock offsets, two sides, manual windows, overlaps and unsafe text-file paths.
- JavaScript syntax checks pass for both app.js and diagnostics.js.
- A consistent copy of the live database was migrated before deployment. Calls (150), events (310369), perspectives (150), and conversation count remained unchanged. Metric count increased from 32717 to 41593: 5232 VD observations plus 3644 legacy RTT observations. All 5232 VD observations mapped to source-local call windows; legacy RTT observations stayed unassigned because no matching reconstructed line windows were available. No correlation was invented to fill those gaps.
- Explicit app-version markers identify calls 17/18/19 as version 1.5.0; presence of a metric is not used as a version detector.
- Docker image rebuilt and deployed locally on port 8080, container healthy. Recreate/restart preserved all counts without duplicate enrichment. An isolated temporary database inside Docker passed text import, manual-window assignment, diagnostic extraction and reopen checks.
- Browser checks: recent-call diagnostic chart and evidence, A/B selection, missing/common coverage, interactive legend, metric-guide search, manual import/window form. No JavaScript console errors observed. Existing user data were not polluted with synthetic UI imports; upload/window submission is covered by isolated HTTP tests and Docker smoke instead.
- Remaining limits: proprietary fields with unconfirmed units stay raw; no automatic endpoint fault attribution, MOS, or end-to-end audio latency. Manual windows are additive and cannot yet be edited/deleted in the UI. The shared tooltip uses nearest observations within ±2.5 s and displays actual sample times. Raw timestamps are not rewritten.


## Configurable analyses — 2026-09-25

- 38 Python tests pass, including schema 2→3 migration/backup, saved configuration validation/revisions, filtered jitter/loss with separate directions and units, both buffer sums, manual-window edits/reassignment/audit, local SIP identity hints and confirmation, and HTTP integration.
- JavaScript syntax checks cover app.js, diagnostics.js and analysis-ui.js.
- Migration was first exercised on a fresh consistent copy of the current live database. It preserved 162 calls, 345 perspectives, 807041 events, 103003 metrics, and conversation count. New user imports since the previous validation were retained.
- Browser verification in a separate synthetic database: A/B series, dual axes, custom color, triangle symbol, visibility toggle, silence ms, saved analysis reopen after page reload, identity confirmation, manual-window creation and editing with visible revision history. No console errors observed. Live data were not given synthetic identity annotations or saved test analyses.
- The chart was visually inspected with distinct ms/% axes and temporal sample spacing. A/B buffer sums and filtered intervals are also covered by numeric tests. The metric guide is reachable from each legend entry.
- Saved analyses recalculate against current data; they do not freeze measurements. Temporary zoom is not persisted: use explicit start/end for a saved crop. Identity inference is conservative and cannot establish a human name when logs lack evidence. Buffer sums are not end-to-end audio latency.

Final Docker verification: container healthy on 127.0.0.1:8080, parser 1.2.0. An isolated Docker smoke test imported text, created a manual perspective, saved a configuration and reopened it successfully. Production counts remained 3 imports / 162 calls / 807041 events / 103003 metrics after recreate. The separate UI test server was stopped after verification.

## Audio incidents — 2026-09-25

- 43 Python tests pass. Incident coverage includes separate audio/recording observers, declared duration versus timestamp span, duplicate media notifications, recovery, open episodes, unknown starts, ignored counters, line selection, clock offsets and episodes crossing the selected interval.
- JavaScript syntax check passes for analysis-ui.js. Browser inspection confirms orange underrun and red media-missing lanes beneath the metrics, sharing their time axis, plus a duration/evidence table. A real imported perspective returns 11 episodes including both phenomena.
- Docker rebuilt with parser 1.3.0; container healthy and the deployed diagnostics API returns the same 11 episodes. Reconstruction is read-only and requires neither database migration nor reimport.
- A media-missing threshold provides a minimum duration, not an exact onset. Missing recovery does not imply recovery at call end. Audio-output and recording observers remain separate and must not be summed as independent audible outages.

## App and xcoder observations — 2026-09-25

- 47 Python tests pass; JavaScript syntax checks pass for app.js, diagnostics.js, analysis-ui.js and topology.js.
- Synthetic tests cover four SIP legs across two app archives and one shared xcoder archive, per-line VD metrics, explicit participant/component associations, stale revision rejection, API labels and unknown/unclassified observations.
- Schema 3→4 was tested first on a consistent copy of the live database. Repeated initialization preserved 3 imports, 162 calls, 345 perspectives, 807041 events and 103003 metrics, along with identity/analysis tables. Automatic pre-v4 backup is present; no reimport or metric rebuild is required.
- Browser verification on an isolated synthetic database: association edit/save, reload persistence, four observations in one chart, separate devices for the shared xcoder, temporal spacing, per-source symbols and evidence tooltips. No JavaScript console errors observed. ZIP upload through the embedded browser returned “Failed to fetch”; this browser upload check is inconclusive. ZIP import is covered by passing HTTP tests and isolated Docker smoke, without adding synthetic data to the live database.
- Docker 1.4.0 deployed locally. Isolated container smoke imported a synthetic ZIP, created a manual perspective, assigned xcoder and reopened the DB successfully. Restart preserved production schema/counts.
- The xcoder log format is an explicit assumption, not validated vendor coverage. See XCODER-001 in open-issues.md. Multi-component graph configuration currently exports to JSON; persistent saved configurations remain the A/B workflow.

## Single-call calculated metrics — 2026-09-25

- 51 Python tests pass, plus syntax checks on all four JavaScript files.
- New HTTP regressions cover catalog visibility, delta/diagnostic parity, CSV evidence, file rotations, source/device isolation, first sample/reset/long gaps, and incident durations including unknown values.
- Docker 1.5.0 deployed without schema changes or reimport. Live single-call API and browser both show 332 silence-delta samples (0–260 ms) for the user-selected call. Visual inspection confirms isolated points at actual sample times; no JavaScript errors.
- All documented single-source metrics are selectable; missing inputs produce no fabricated samples. Two-source sums remain explicitly configured in A/B. Incident duration charts retain unknown episodes in the evidence table/CSV.

## Missing-packet event counts — 2026-09-25

- 54 tests pass. Regressions cover explicit count versus SN delta, malformed/negative/truncated counts, exact rotation deduplication, distinct sequence notifications at the same timestamp, unknown lines, idempotent backfill and diagnostic units.
- Backfill was exercised twice on a database copy before deployment: 1347 new events (1–470 packets), 44 unassigned; all pre-existing metrics preserved. Live Docker re-initialization also creates no duplicates. A pre-missing-packets backup is retained in the data volume.
- Docker 1.6.0 deployed. Browser call chart verified 84 isolated event points, range 1–4 packets, with source file/line tooltips and no console errors. Diagnostic API also returns 84 event points with unit packets.
- Counts describe sequence-gap notifications, not unique or final packet loss. xcoder format coverage remains unverified as documented in XCODER-001.

## Upstream/downstream selection — 2026-09-25

- 56 tests pass; syntax checks cover all browser scripts. Context tests verify local versus peer reception, bidirectional RTT, unconfirmed KPE semantics, xcoder non-inversion, option groups and HTTP/CSV direction filtering.
- Live browser checks: separate upstream/downstream jitter options, upstream-only legends and CSV URL, diagnostic upstream filter with only peer-report values in the shared tooltip. Local audio episodes remain explicitly labelled as unfiltered context.
- Docker 1.7.0 deployed without schema migration or reimport. Original direction and numeric values remain unchanged; context metadata is response-only. Unlabelled sources are explicitly app-assumed; role xcoder alone never proves an app-facing RTP leg.


## Android and conversation discovery — 2026-09-25

- 62 Python tests pass, plus syntax checks for all five browser scripts. New
  synthetic regressions cover Android metadata scope, shared metric extractors,
  different Call-IDs with a shared UUID, invalid/body UUID rejection, explicit
  answered-elsewhere reason, reused/conflicting identifiers, manual sessions and
  v4→v5 backup/preservation.
- An isolated Docker instance imports synthetic iOS/Android ZIPs through HTTP,
  verifies correlation, deduplication and derived metrics, then repeats after
  restart to verify persistence. No synthetic imports enter the production DB.
- The current database was migrated on a consistent copy before deployment. All
  6 imports, 318 calls, 826 perspectives, 1772730 events and 221290 metrics were
  preserved. Five multiple-Call-ID groups were found, four across iOS/Android.
- Docker 1.8.0 deployed locally with automatic pre-v5 backup. Browser checks
  cover discovery cards, Android export metadata, per-observation selection,
  the shared temporal chart, direction filter and evidence tooltip. No console
  errors observed in these flows. Wrapper-only Android events remain raw; KPE
  metric coverage is not fabricated when CallInfo is absent.


## Analisi generali e MCP — 27 settembre 2026

- Suite completa: 126 test superati, inclusa la regressione sul cambio/scadenza
  rete. Sintassi JavaScript e tre test delle scale dei grafici verificati.
- Query: catalogo, parametri, scope, authorizer, tentativi di impersonare le
  viste con CTE, limiti di righe/dimensione, episodi, pesatura temporale,
  dati invalidi, deduplicazione e provenienza verificati su fixture sintetiche.
- MCP stdio: initialize, tools/list, chiamata HTTP reale, rifiuto scritture,
  restrizione all'API loopback e ciclo di vita verificati.
- Migrazione 9→10 ripetuta su copia del DB locale: invariati import, chiamate,
  prospettive, eventi, metriche e annotazioni. Backup pre-v10 creato.
- Docker isolato: import di ZIP sintetico, due intervalli MOS, salvataggio di
  ricetta e riesecuzione dopo riavvio del processo sul medesimo DB temporaneo.
- Istanza locale aggiornata su http://127.0.0.1:8080/; conteggi originali
  preservati. Nessun import sintetico aggiunto al database dell'utente.
- Browser: pagina Analisi libere, caricamento esempi ed esecuzione MOS con
  copertura visibile; query delle metriche, dettaglio chiamata, cambio metriche,
  confronto e apertura del dialogo ZIP verificati. Collegamento MCP al container
  verificato separatamente.

## Episodi audio, inventario e checkpoint — 28 settembre 2026

- Suite completa finale: 132 test Python superati; sintassi di tutti gli script
  JavaScript verificata. Fixture aggiunte esclusivamente sintetiche.
- Finestre underrun: caso 200/400 ms, unione sovrapposizioni, osservatori separati,
  finestre ritagliate, episodi aperti e assenza di evidenze verificati.
- API locale e schermata Analisi libere verificate sul dataset incidents;
  export completo paginato con controllo dello snapshot.
- Inventario del formato recente completato in sola lettura. Piano dei campi
  mancanti in periodic-metrics-implementation.md; implementazione ancora da fare.
- Dati, grafici ed evidenze locali restano in data/ e non sono pubblicati.


## PQ, percorsi, transitori e recupero posizioni — 4 ottobre 2026

- 201 test Python superati: finestre parziali, episodi aperti, assenza AWT,
  chiamate senza chiusura, conflitti, isolamento sorgenti, pattern iOS malformati,
  deduplicazione e backfill storico idempotente con conservazione degli ID.
- Browser: import ZIP sintetici in istanza separata, cambio sorgente, dettaglio,
  metriche e confronto; percorso reale verificato con nuovi punti periodici e
  riferimenti agli eventi. Nessun errore console nei flussi verificati.
- Docker aggiornato e health verificato. Backup SQLite consistente prima del
  backfill dell’intero archivio; chiamate, prospettive, eventi, metriche,
  annotazioni e record geografici preesistenti preservati.
- Risultati e materiale reale esclusi da Git. Guide, API, architettura e limiti
  consolidati nel [checkpoint](checkpoint-2026-10-04.md).
