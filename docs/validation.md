# Verifica iniziale — 24 settembre 2026

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
