# API locale

[Indice](README.md) · [Modello dei dati](architecture.md)

Riferimento del servizio attuale, schema 12. Le sezioni con numeri di schema
indicano l’introduzione della funzione, non endpoint separati per versione.
Il servizio è per analisi locale: non espone ancora previsioni o piani operativi.

Base URL: `http://localhost:8080/api`. JSON unless noted. No credentials are needed on this loopback-only service. Foreign Host/Origin headers are rejected. Do not expose it publicly.

| Method / path | Input | Result |
|---|---|---|
| `GET /health` | — | status and parser version |
| `GET /overview` | — | archive/call/event/metric totals and quality counts |
| `POST /imports` | raw ZIP bytes; `Content-Type: application/octet-stream`; URL-encoded `X-Filename`, optional `X-Label` | import ID, counters, warnings or duplicate flag |
| `GET /imports` | — | archives and warning JSON strings |
| `PATCH /imports` | `{id,label,clock_offset}` | updates label and graph offset (±86400 seconds) |
| `GET /files` | — | member inventory and coverage |
| `GET /calls` | optional `search` | up to 2000 calls, latest first |
| `GET /perspectives` | — | all source observations |
| `GET /analysis` | `call=1` | descriptive RTCP summary, error/invalid counts, first 500 SIP messages with provenance |
| `GET /events` | `call`, `perspective`, `import`, `file`, `search`, `level`, `unassigned=1`, `offset` | 100 events + `more` and offset |
| `GET /metric-names` | — | available names/units/statistics |
| `GET /metrics` | `calls=1,2`, `name`, `statistic`, optional `invalid=1`, `format=csv` | up to 100000 metric rows with source context; larger selections fail explicitly |
| `POST /query` | `{sql:"SELECT ..."}` | column names, row arrays, `truncated` flag |
| `POST /conversations` | `{title,call_ids:[1,2],host_perspective_id:null,note:"..."}` | new conversation ID |
| `GET /conversations` | — | saved groupings with comma-separated call IDs |
| `GET /database` | — | consistent SQLite database download |

Example (POSIX shell):

```sh
curl --data-binary @device.zip \
  -H 'Content-Type: application/octet-stream' \
  -H 'X-Filename: device.zip' -H 'X-Label: Alice' \
  http://localhost:8080/api/imports

curl -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT name,COUNT(*) FROM metrics GROUP BY name"}' \
  http://localhost:8080/api/query
```

For portable agent workflows, prefer `python -m app.cli` to shell-specific quoting and HTTP upload details. Import errors use 400, invalid body sizes 413, rejected origins 403, missing API endpoints 404. Multiple-archive uploads are independent transactions.


## Diagnostic extension (schema 2 / parser 1.1)

- `GET /api/catalog`: all documented metrics, units, sources, formulas and interpretation limits; unknown imported KPE fields receive an explicit unknown-semantics entry.
- `GET /api/devices`: distinct assigned perspective/device pairs.
- `GET /api/diagnostics?a=1&b=2&device_a=NART0%20of%20Line%200&device_b=NART0%20of%20Line%200&rtt_threshold=200&buffer_threshold=500`: optional B; distinct perspectives required. Returns series, coverage, app version evidence, per-series peaks, threshold flags and provenance. Thresholds finite/nonnegative; at most 100,000 input samples per perspective. Offsets affect all diagnostic timestamps including derived metrics. No derived data are written to the DB. NART filters apply to VD; RTP flow/SSRC series remain separate.
- `GET /api/perspectives` additionally returns `app_version`, `version_event_id` (null when unknown).
- `GET /api/metrics` additionally includes schema-2 provenance columns. `source_line` is preferred to event `line_no` for the exact field location.
- `POST /api/text-import`: JSON `{"label":"Device A","files":[{"name":"VDlog.txt","text":"…"},{"name":"rtplog.txt","text":"…"}]}`. One device per request, 1–20 files, 40 MiB/file, 64 MiB total JSON body. Uses the same bounded/path-validated ZIP pipeline internally; deterministic file timestamps support duplicate detection.
- `POST /api/windows`: JSON `{"import_id":1,"line_id":0,"start":"2026-01-01 12:00:00","end":"2026-01-01 12:01:00","title":"Analyst window"}`. Timestamps without timezone, start < end. Returns `call_id,perspective_id`. Assigns unassigned line-specific observations; rejects overlap with any existing same-source/line perspective. No automatic merge with SIP calls.

Diagnostic points carry `t` (neutral-axis epoch seconds, not a declaration of UTC timezone), `value` (nell’unità della serie), and `evidence` containing event/metric IDs, file and normalized line. Derived points reference each input event. Silence counters remain ms in JSON; the UI right axis displays seconds. `derived.silence_delta` includes `interval_seconds`. Event updates and interval deltas should not be interpolated as continuous measurements.


## Workspace extension (schema 3 / parser 1.2)

- `/api/diagnostics` also accepts optional `start`, `end` (naive log-axis timestamps after correction) and `offset_a`, `offset_b` (seconds, ±86400). Filters precede interpolation/deltas. Series now include `direction`, `unit`, `rtcp.loss`, `rtcp.jitter`, and `derived.dejitter_sum`. Response `window` contains requested neutral-axis seconds bounds or null.
- `GET /api/saved-analyses`: stored configurations with id/title/config JSON/revision.
- `POST /api/saved-analyses`: `{title, config}`; `PATCH` additionally requires `{id, revision}`. Config keys: `a,b,device_a,device_b,offset_a,offset_b,start,end,rtt_threshold,buffer_threshold,silence_unit,metrics,styles`. Only supported metric names accepted. Styles map stable JSON series keys to `{color: '#rrggbb',symbol: 'circle|square|triangle|diamond',visible: bool}`. A/B perspective IDs must exist. Stored config schema is 1; unknown fields are discarded. Missing/stale revision returns 400.
- `GET /api/identities?import=1`: bounded local-account candidates, safe extracted fields and event evidence, optional analyst confirmation, truncation flag.
- `POST /api/identities`: `{import_id,name,account,note,event_ids}` confirms or corrects identity and source label. At most 10 evidence IDs, each belonging to that import.
- `GET /api/windows`: manual perspectives and titles. `PATCH /api/windows`: `{perspective_id,line_id,start,end,title}` corrects a manual window atomically and preserves IDs, rejects overlap and auto-reconstructed calls.
- `GET /api/window-history?perspective=1`: previous window snapshots with revision timestamps.

Saved analyses contain configurations, not immutable metric snapshots; reopen recalculates against current data. Window history is retained for audit. There is no public DELETE endpoint.


## Audio incidents

`GET /api/diagnostics` additionally returns `incidents` and `incident_warnings`. Each episode includes kind, side, perspective_id, device, observer, flow, start/end (end null if open), last_observed, detected_at, duration_ms (nullable), duration_basis (reported/minimum/timestamps/unknown), start_basis, status, evidence, plot_start/plot_end and clipped. Times use the same corrected neutral axis as series. Underrun reported duration is not replaced by wall-clock span; wall_span_ms is separately returned when available. Reconstruction uses the whole perspective before applying the display window; the duration is not truncated with the bar. Input is bounded to 100,000 matching records per perspective. Incidents are computed from raw events without schema changes or destructive backfill.

## App / xcoder topology

`GET /api/topology` lists perspectives with nullable session, participant, role, node, note and revision. `POST /api/topology` requires perspective_id, session, participant, role (`app`, `xcoder`, `unknown`); node and note are optional. Revision is 0/omitted for a new association and must match the current revision for updates. Invalid or stale writes return 400. GET /api/perspectives adds observation metadata and a display label; raw import labels and call identities are unchanged. Topology rows are queryable through read-only SQL and included in database exports.

GET /api/metric-names includes documented single-source metrics even without persisted samples. GET /api/metrics supports derived.silence_delta and incident.buffer_underrun/media_missing (statistic=sample), including CSV. Calculations carry evidence arrays; deltas include interval_seconds; incidents include episode metadata and nullable value when duration is unknown. No DB schema change.

GET /api/metric-options?calls=ID restituisce opzioni raggruppate con name, direction, category, group, title, value. GET /api/metrics accetta direction=incoming|outgoing|roundtrip|combined e applica lo stesso filtro al CSV. Le misure e le serie diagnostiche includono measurement_context (category, label, role_basis); direction originale rimane invariata.


### Conversation discovery (schema 5)

`GET /api/conversation-groups` returns derived groups with stable `key`, `kind`
(`uuid`, `sip`, `manual`, `session`), `review`, `call_ids`, `source_count`,
`perspectives` and `evidence`. Perspectives include export `profile`, attributed
metric count, raw `status` and `display_status` (including `answered_elsewhere`).
Evidence identifies the event, import, Call-ID and exact header line. Groups are
not persisted call merges. `GET /api/imports` and `/api/perspectives` expose
`source_profile`; version metadata has explicit export scope.

## Conteggi per sorgente

`GET /api/imports` aggiunge `call_count` (chiamate distinte nella sorgente),
`new_call_count` (prima comparsa nella sorgente) ed `existing_call_count`
(già presenti in una sorgente con ID di importazione inferiore). Ogni chiamata
conta una volta per ZIP; conversazioni e file ruotati non moltiplicano il totale.
Il conteggio è ricostruito dalle prospettive attuali, incluse eventuali finestre
manuali; non è una fotografia immutabile del momento dell’upload. Le sessioni
senza Call-ID restano separate secondo le regole di attribuzione esistenti.
Uno ZIP senza chiamate restituisce tre zeri; reimportare lo stesso ZIP non crea
una nuova sorgente. Nessuna migrazione o modifica ai log.

## Mappa qualità

`GET /api/geography` accepts `cell` (50,100,250,500,1000,5000,10000 metres),
`direction` (downstream/upstream), `quality` (fresh/declared), optional `start`
and exclusive `end` in original legacy log time or UTC for structured telemetry.
No implicit timezone conversion reconciles these clocks. Aggregates contain no source identities.
`GET /api/map-tile?z=...&x=...&y=...` serves optional OSM background tiles with
a local cache. [Method, limits, privacy and schema upgrade](geography.md).

`/api/geography` also accepts `platform=all|android|ios|desktop|unknown`,
`access=all|cellular|wifi|ethernet|other|unknown`,
`upstream=all|mobile_direct|tethering|onboard_wifi|fixed|unknown`, and
`operator=all|unknown|<explicit operator>`. Network context is intersected with
MOS intervals before weighted aggregation. [Schema 7 and semantics](mobility.md).

## Structured telemetry

`GET /api/telemetry`: canonical record/evidence/conflict/interval counts and bounded issues with file/line evidence. See [schema 8 and telemetry 1.1](telemetry-integration.md). Validated intervals also appear in `/api/mos`, `/api/metrics` and `/api/geography`. No prediction/plan delivery endpoint exists yet.

## MOS e grafico multimetriche

`GET /api/mos?local=1&peer=2&local_role=app` restituisce `model`, serie
`downstream` e `upstream`, provenienza delle due direzioni e contesto. `peer` è
facoltativo e deve appartenere a una sorgente distinta; `local_role` ammette
`app` (default) e `gw`. Scegliere il peer dichiara esplicitamente la tratta:
la sua ricezione locale sostituisce il fallback RTCP senza colmarne le lacune.
[Metodo e campi temporali](mos.md).

`GET /api/calls` include `mos` con prospettiva di riferimento, fonte e riepiloghi
downstream/upstream: `minimum`, `maximum`, `mean`, `covered_seconds`,
`coverage_percent` ed eventi degli estremi, quando calcolabili. `mean` pesa il
MOS sulla durata, non sul numero di report. `null` non equivale a zero.
Il frontend ordina le righe restituite; non è una paginazione ordinata dell'intero DB.

Il grafico multimetriche riusa una richiesta `/api/metrics` per nome, direzione
e statistica. Non introduce una nuova API né somma metriche di unità diverse.
Le richieste sono concorrenti ma limitate a quattro per caricamento; il limite
di 100.000 campioni resta per richiesta. Una metrica selezionabile può non avere
campioni nella chiamata. I CSV rimangono separati e indipendenti da zoom/visibilità.

`measurement_context` esprime l'interpretazione della direzione; `direction`
conserva quella del dato. Nei dati strutturati `clock_domain=UTC` distingue
l'orologio dichiarato dal tempo legacy senza fuso. Non applicare arbitrariamente
conversioni locali ai timestamp originali.

## Identità e deduplicazione per sorgente

[Contratto completo e migrazione schema 9](source-dedup.md). `/api/imports`
include `producer`; `/api/perspectives` include `duplicate_of`. Il grafico e
`/api/metrics` escludono le copie storiche riconosciute: `duplicates=1` le
include, anche in CSV. Il risultato di un nuovo import distingue `skipped_calls`
e `skipped_events` dai record conservati.

## API analitiche e MCP

`GET /api/analytics/catalog`, `/coverage`, `/recipes`; `POST /api/analytics/query`,
`/evidence`, `/run-recipe`; `POST/PATCH /api/analytics/recipes`.
Le query generali operano sulle viste `a_*`, con parametri, scope, MOS opzionale,
limiti e provenienza. Il server MCP usa queste stesse API.
[Contratto completo, esempi e semantica](analytics.md).


## Metriche periodiche: schema 11 / analytics-2

`a_metrics` e `/api/metrics` includono `observer`, `output_device`,
`input_device`, `lifecycle`, originali `raw_value/raw_unit` e riga esatta.
`a_periodic_metadata` conserva `value_json` tipizzato e provenienza. Le
osservazioni non attribuite sono incluse nella copertura globale; una selezione
per chiamata usa l’associazione della singola misura, anche nei blocchi multi-input.
`analytics_catalog`, `analytics_coverage`, `analytics_query` e
`analytics_evidence` espongono gli stessi dati tramite MCP, con i limiti e
l’authorizer esistenti. Il testo integrale dei log resta escluso.

Esempio SQL, con parametro `metric = vd.silence_played` e scope esplicito:

```sql
SELECT observer, output_device, input_device, lifecycle, interval_start,
       ts, status, delta, unit, previous_event_id, event_id,
       previous_line_no, line_no
FROM a_counter_intervals WHERE name=:metric ORDER BY ts,id
```

Gli stati initial/reset/invalid/conflict/gap producono delta NULL. Non sommare
contatori cumulativi né attribuire i delta a secondi specifici. Con
`datasets: ["incidents"]`, `a_counter_incident_matches` espone ciascun episodio
sovrapposto al periodo del contatore con osservatore/input esatti e ID delle
prove; non somma durate e non dichiara equivalenza. Gli episodi aperti senza
collocazione non generano match. Un match temporale non prova causalità.
Le vecchie ricette analytics-1 sono accettate senza modificare le revisioni;
il risultato dichiara la versione corrente. Riconnettere il client MCP.

## Contratto semantico del media plane

`GET /api/media-semantics` restituisce `version`, `basis`, `devices` (nome, classe padre, denominazione, ruolo), `rules` e `context`. Lo stesso oggetto è `media_plane` in `/api/analytics/catalog` e nello strumento MCP `analytics_catalog`. Il catalogo `/api/catalog` mantiene la forma di lista e aggiunge `semantics` a ogni metrica: `domain`, `domain_label`, `scope`, `interpretation`.

Gli ambiti distinguono scheduling, trasporto RTP, buffer/media, elaborazione/I/O, sonde di rete e modelli di qualità; `unspecified` segnala semantica non confermata. Non sono classificazioni della causa di un guasto né tipi del device. Leggere anche `meaning`, `source`, `kind`, `unit`, `limits` e il contesto della singola osservazione. [Gerarchia completa](media-plane.md). Gli episodi conservano il nome osservato del VD: non viene più sostituito con «Registrazione VD», che deduceva una destinazione non garantita. Non cambiano dati archiviati o ID.

Esempio di richiesta MCP: «Distingui per questa chiamata scheduling dei thread, ricezione RTP e conseguenze sul media; separa VID/VOD e osservatori, indicando copertura ed evidenze, senza attribuire automaticamente gli underrun alla rete». Riconnettere il client per rileggere le istruzioni e il catalogo.

## Profili temporali delle zone

Il clic su una cella apre storico giornaliero/settimanale/mensile/annuale, ricorrenze orarie, copertura ed evidenze. Gli stessi calcoli sono disponibili tramite `POST /api/analytics/geo-temporal` e `analytics_geo_temporal`; `POST /api/analytics/geo-cells` e `analytics_geo_cells` scoprono le celle. [Guida, denominatori e contratto completo](geo-temporal.md). Il catalogo MCP espone gli schemi in `geo_temporal`. Riconnettere il client MCP per rileggere i nuovi strumenti.


## Perceptual Quality e percorso chiamata

- `GET /api/metrics?calls=1&name=derived.perceptual_quality`: finestre AWT 0–100,
  con `window_ts`, `ts`, `valid_until`, `observed_ms`, `underrun_ms`,
  `underrun_percent`, `end_basis` e prove; anche `format=csv`.
- `GET /api/geography?metric=perceptual&cell=50&quality=declared`: celle PQ;
  `quality=fresh` esclude dichiarazioni SIP e configurazioni locali iOS.
  La metrica MOS resta disponibile con `metric=mos` (default dell’API).
  PQ restituisce `cells` con `origin=direct|estimated`, `direct_cells`,
  `estimated_cells`, `estimation_method=linear-time-cells-1` e `route_samples`
  (campioni intermedi prima delle esclusioni AWT). Le celle dirette prevalgono;
  `estimate`, quando presente, è un riepilogo separato escluso dalla loro media.
  Media e secondi nel riepilogo generale restano riferiti ai dati diretti.
  Ogni cella include `passes`, `affected_seconds`, `underrun_ms` e prime 20
  finestre di `evidence`, con `evidence_truncated`; le stime includono anche
  `gap_min_seconds` e `gap_max_seconds`. Evidenze con posizioni agli estremi e
  AWT conservano evento/file/riga. Non vengono più restituiti `routes` grezzi.
  Limiti PQ: 100.000 posizioni, 100.000 intermedi, 200.000 campioni AWT diretti,
  10.000 celle. Errori espliciti: restringere il periodo, non trattarli come zero.
- `GET /api/call-route?call=1&perspective=1&cell=50`: selezione sorgente,
  punti cronologici, segmenti, celle e prove. `perspective` è facoltativa e deve
  appartenere alla chiamata ed essere una prospettiva app non duplicata.
  Massimo 10.000 posizioni. `sip_config` identifica gli aggiornamenti locali
  degli header, con età del fix non verificata. Nessuna fusione dei percorsi.
  `interpolation` include `points`, `links` (ID degli estremi), `mean`, `minimum`,
  `evaluated_seconds`, `max_gap_seconds=120` e metodo `linear-time-1` quando
  calcolato. Massimo 100.000 intermedi. Ogni punto ha `window_ts`, timestamp
  centrale, posizione stimata, qualità AWT del secondo, prove degli estremi e
  dell'audio. `value=null` indica secondo non valutabile/ambiguo. I vecchi
  `segment`/`gap_seconds=30` dei punti registrati restano compatibili, ma per
  disegnare l'interpolazione usare `interpolation.links` e il suo limite 120 s.

[Metodo, denominatori e limiti](perceptual-quality.md).

## Aggiornamento MCP 1.3.0

Gli endpoint analitici aggiungono `POST /api/analytics/call-route`,
`POST /api/analytics/perceptual-quality` e `POST /api/analytics/connectivity`.
Accettano rispettivamente `{call_id, perspective_id?, cell?}`, `{call_ids}` e
`{call_ids}` oppure `{import_id, start, end}`; riusano i calcoli delle API UI.
Sono in sola lettura, con validazione stretta, snapshot coerente e limite di
risposta 4 MiB. `POST /api/analytics/geo-cells` accetta ora
`metric: "perceptual"` oppure `"mos"` (default). Il profilo `geo-temporal`
non cambia metrica o semantica. Catalogo e copertura espongono anche tentativi
utente e connettività. [Contratto, esempi e limiti MCP](analytics.md#pq-percorsi-tentativi-e-connettività--mcp-130).
