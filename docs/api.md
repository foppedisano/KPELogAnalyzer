# Local API

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

Diagnostic points carry `t` (neutral-axis epoch seconds, not a declaration of UTC timezone), `value` (ms), and `evidence` containing event/metric IDs, file and normalized line. Derived points reference each input event. Silence counters remain ms in JSON; the UI right axis displays seconds. `derived.silence_delta` includes `interval_seconds`. Event updates and interval deltas should not be interpolated as continuous measurements.


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
