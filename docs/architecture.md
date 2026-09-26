# Architettura e contratto dei parser

[Indice](README.md) · [Guida alla logica della piattaforma](platform-guide.md)

## Quadro attuale

Un processo HTTP Python serve API e interfaccia statica. SQLite in modalità WAL
conserva dati ed evidenze; gli import sono serializzati e atomici per archivio.
Il frontend è JavaScript senza dipendenze o CDN. Il servizio resta sul loopback.
L'unica cartografia remota opzionale è richiesta esplicitamente dall'utente;
la base offline è inclusa.

### Due percorsi di elaborazione

| Fase | Log tradizionali | Telemetria strutturata |
|---|---|---|
| Identità evento | Evidenza testuale e chiavi degli estrattori per import | source_id/event_id stabili fra export |
| Tempo | Timestamp osservato, nessun fuso inventato | UTC e dominio monotono sessione/boot |
| Attribuzione | Call-ID esatto o finestra di linea univoca | SIP Call-ID esplicito; riferimenti nello stesso dominio sorgente/sessione/boot |
| Perdita/MOS | Report RTCP, mantenimento MOS con scadenza | Finestre RTP verificate o delta RTCP compatibili |
| Posizione | Nuovo aggiornamento o dichiarazione SIP locale ammessa | Fix app già consegnato, non cached, età verificabile |
| Geografia | Associazione con limite di 120 s dalla consegna legacy | Associazione monotona con limite di 30 s dal fix |

I due percorsi condividono il modello numerico MOS e la vista geografica, ma non
si deduplicano genericamente fra loro. Gli input originali restano archiviati.
Le derivazioni sono escluse quando mancano unità, identità o riferimenti affidabili.

### Cosa viene salvato e cosa si ricalcola

- File/eventi/metriche estratte: persistiti con provenienza.
- Delta e somme diagnostiche, episodi e MOS ordinario: calcolati su richiesta.
- Posizioni, osservazioni posizione–MOS e contesto: persistiti con metodo/versione;
  le celle sono aggregazioni ricalcolate per filtro e dimensione.
- Telemetria canonica e perdita su intervallo verificato: persistite. Un conflitto
  può rimuovere e ricostruire i prodotti dipendenti; gli ID delle derivazioni non
  sono identità stabili degli eventi grezzi.
- Analisi salvate: configurazioni revisionate, non fotografie immutabili dei dati.
- Piani offline: eventi archiviati per audit, senza motore di previsione/esecuzione.

### Tabelle delle estensioni

| Tabelle | Responsabilità |
|---|---|
| saved_analyses, source_identities, window_revisions | Configurazioni, identità confermate e cronologia finestre manuali |
| observation_roles | Associazione esplicita sessione/partecipante/componente |
| source_profiles, call_correlations, leg_outcomes | Metadati export, correlazioni UUID e risposte su altre tratte |
| geo_positions, geo_mos, geo_mos_evidence | Posizioni, intervalli georeferenziati e prove separate |
| network_observations, movement_sequences, movement_samples | Contesto rete e sequenze locali senza identificazione del viaggio |
| telemetry_records, telemetry_evidence | Eventi canonici e tutte le copie originali |
| telemetry_intervals, telemetry_geo_context | Finestre verificate e contesto delle osservazioni strutturate |
| meta | Versione schema e marker idempotenti di elaborazione |

### Migrazioni

Lo schema corrente è **8**. Le migrazioni successive preservano ID grezzi e
annotazioni. Su DB popolati producono backup consistenti pre-vN; un backup
omonimo non viene sovrascritto. Servono spazio per backup e arricchimenti.
Le istruzioni sotto sulle singole versioni descrivono la storia dello schema;
non vanno interpretate come versioni alternative oggi supportate dal frontend.

| Passaggio | Aggiunta |
|---|---|
| 1→2 | Provenienza metrica, device, unità grezze, tipi e versioni app |
| 2→3 | Analisi salvate, identità confermate, modifiche finestre auditate |
| 3→4 | Ruoli e associazioni app/xcoder |
| 4→5 | Metadati piattaforma, UUID conversazioni, esiti delle tratte |
| 5→6 | Archivio geografico posizione–MOS |
| 6→7 | Rete e sequenze di movimento |
| 7→8 | Archivio canonico telemetria e intervalli verificati |

Prima di aggiornare: **Esporta database**, conserva la copia localmente,
ricostruisci il container e controlla `/api/health`. Per rollback usa una nuova
cartella o un nuovo volume con il backup e il codice compatibile: mai sovrascrivere
un DB aperto. [Procedura operativa](getting-started.md).

## Riferimento tecnico dettagliato

## Modello base dei dati (schema 8)

| Table | Meaning | Relations |
|---|---|---|
| `imports` | One ZIP, SHA-256, label, warnings, clock correction in seconds | source root |
| `files` | ZIP member, byte size, parser, observed coverage | `import_id` |
| `calls` | Exact SIP Call-ID or source-scoped synthetic identity | shared across sources |
| `perspectives` | Source-local lifecycle, line, direction, evidence | `call_id`, `import_id` |
| `events` | Multiline record with original normalized text | `file_id`, optional call/perspective |
| `metrics` | One numeric value and reported statistic | `event_id`, optional call/perspective |
| `app_versions` | Explicit app name/version markers with event evidence | `event_id`, `import_id` |
| `conversations` | Analyst-created grouping, optional declared host and note | `host_perspective_id` |
| `conversation_calls` | Conversation membership | conversation + call |

`metrics` also carries direction, flow, SSRC, unit and validity. Keep `sample`, `last`, `avg`, `min`, `max` distinct. The same metric name in incoming/outgoing directions represents different measurements. KPE's “first media flow” is represented as flow `0`; this is not a reconstruction of every negotiated media stream.

## Pipeline di importazione legacy

1. Hash the archive. If already imported, return the existing ID without changing labels or data.
2. Validate size, member count, paths, encryption and per-member size. Read `.txt`, `.log`, `.old` and recognized `telemetry*.jsonl`; other entries receive an import warning. Structured JSONL follows its own per-record validation path.
3. Normalize CRLF/CRCRLF and split timestamped multiline records. Both KPE/iOS and reSIProcate timestamps are recognized. Preserve leading un-timestamped fragments unassigned.
4. Collect SIP dialogs from `sip_debug*`: INVITE, ACK, BYE, CANCEL, REFER, PRACK, UPDATE. REGISTER/OPTIONS/NOTIFY do not become calls. SIP auth challenges are not terminal failures.
5. Reconstruct line windows from `kpelog*` additions, state transitions, removals, and terminated-call JSON summaries. Process rotations in timestamp order. A repeated exact record does not create new derived observations.
6. Join the terminal JSON's Call-ID to SIP evidence. SIP-only calls remain available without a guessed line. `CallInfo*` connected/terminated messages provide local-only fallback windows when no KPE window covers them.
7. Store calls and per-import perspectives. Attach events by exact Call-ID or a unique source-local line window. A 250 ms post-termination tolerance accommodates delayed final statistics; ambiguous overlapping boundaries remain unassigned. Unscoped `CallInfo` context uses a unique bounded call window. Other unscoped events remain unassigned.
8. Extract numeric metric observations; keep unassigned observations in the DB. Generate coverage/invalid-value warnings and commit the archive atomically.

## Estrattori supportati

| Input | Extraction |
|---|---|
| `sip_debug*.txt` | SIP Call-ID, parties, direction, response-based connection/failure, termination |
| `kpelog*.txt` | local line windows, call summaries, final media statistics |
| `CallInfo*.log` | periodic nested metric JSON, ICMP roundtrip, local lifecycle fallback |
| `rtplog*.txt` | RTCP receive/remote loss, jitter, RTT, received packet counter, SSRC, flow |
| `VDlog*.txt` | NART device sections, buffer occupancy/target, skipped silence, delay maxima |
| `PhoneEngine*.log` | timestamped events, explicit `lineId` context, app-version markers |
| `telemetry*.jsonl` | v1/v1.1 validation, canonical records, chronology/references and verified interval derivation |
| other text logs including `resip*` | searchable multiline raw events; exact Call-ID association when available |

## Limiti di attribuzione

The parser is empirical, based on an iOS export, not on the full proprietary KPE specification. No RTP packet capture decoding, measured perceptual MOS, Android format guarantees, automatic conference graph, SDP negotiation state machine, NAT root-cause diagnosis, or audio reconstruction. SIP forking is represented at Call-ID level, not separate From/To-tag dialogs. SIP 2xx evidence on re-INVITE may be the first observed connection when the initial dialog is truncated. Line windows cannot be recovered reliably from RTP timestamps alone.

A ZIP is a source snapshot, not a permanently identified device. Two snapshots of one device can duplicate observations across imports; the UI separates these series. Within a source a given Call-ID has one perspective; highly unusual Call-ID reuse or multiple line assignments for one Call-ID require a richer schema. Global call timestamps aggregate raw per-source timestamps; durations are not clock-corrected. Partial windows closed by line reuse are labelled incomplete.

## Aggiungere un formato

Add a synthetic sample in `tests/fixtures.py` or an additional fixture module, characterize timestamps and identifiers, then add classification/extraction code. Retain provenance. Document units and source evidence explicitly. Add regression tests for absent IDs, malformed JSON, rotations and simultaneous calls. Use real private archives only for local verification, with aggregate reports kept out of public fixtures.

Schema 1 → 2 migrates transactionally after a consistent pre-upgrade backup when data exists. It adds `device`, `source_line`, `raw_value`, `raw_unit`, `sample_kind`, `extractor` to metrics and `app_versions`. `enrichment:<import_id>` markers make stored-event backfill idempotent. Calls, perspectives, annotations and legacy metrics are preserved. See [upgrade instructions](diagnostics.md). New metrics can be assigned independently of their parent VD event, because a single event may contain multiple device/line sections. The same unique source-local line-window rule applies. Manual windows assign only unassigned observations and reject overlaps; they never create SIP identity. Derived diagnostics are response data with references to all input events, not persisted metrics.

## Operations

One threaded HTTP process, SQLite WAL and serialized imports. Read requests can continue while imports run. The frontend sends one ZIP per HTTP request sequentially. No external packages or CDN runtime assets. This is a local analyst tool, not a multi-tenant server. SQLite authorizer permits SELECT/READ/functions/recursive CTE only; external file/extension operations are denied. Query execution is bounded by a progress handler, row limit and string length limit.

## Workspace schema 3

Version 2 → 3 backs up before adding saved_analyses (validated configuration JSON, optimistic revision), source_identities (analyst confirmation and event references), window_revisions (pre-edit snapshot). Manual edits preserve IDs, clear only that manual perspective’s attribution, and reassign compatible free observations transactionally. Identity hints read only selected SIP request header fields; never infer people from remote parties or expose authentication headers. Diagnostic filters apply after the per-analysis clock offset and before derivation; incoming/outgoing remain distinct series.

## Observation roles (schema 4)

`observation_roles` attaches session, participant, role (app/xcoder/unknown), node, analyst note and optimistic revision to a perspective. The composite session/participant value groups observation points; it never changes SIP identity or metric attribution. An import may contain multiple perspectives belonging to different participants. Unannotated observations keep their previous labels. The multicomponent chart requests each perspective independently, applies its source clock offset and preserves device/flow/SSRC and event provenance. See [xcoder workflow and limits](xcoder.md).


## Schema 5: platform metadata and conversation discovery

The v4→v5 migration creates a consistent SQLite backup (`kpe.sqlite3.pre-v5.bak`)
before changing a populated database. An existing backup is never overwritten.
Keep it locally; to retry a failed migration preserve/rename the backup first.
The migration does not change calls, perspectives, raw outcomes, metrics or analyst
annotations. Existing imports are backfilled once using `conversation-discovery-1:<id>`.

- `source_profiles`: whitelisted export metadata, platform, file-presence flags,
  and source event/line evidence. Android `info.log` version applies to the export,
  not automatically to every historical call in it.
- `call_correlations`: validated non-nil X-Call-UUID from actual SIP INVITE request
  headers, with exact event and header line. Bodies and responses are excluded.
- `leg_outcomes`: explicit CANCEL Reason cause=200 / Call completed elsewhere,
  preserving the original lifecycle status separately.

`GET /api/conversation-groups` derives stable-key groups without merging Call-IDs:
shared UUID, repeated exact SIP Call-ID, manual conversations, and explicit
App/xcoder sessions. A shared UUID describes a signaling attempt and may include
forked or unanswered legs. Several UUIDs for one Call-ID or reuse over more than
24 hours marks a candidate as requiring review. This guard is not a guarantee
against vendor identifier reuse. No matching by telephone number or time proximity.
Repeated exports may yield multiple perspectives of one physical device. The UI
selects the richest perspective per Call-ID initially, with explicit selection of
additional observations. This is a convenience, not participant identification.
See [the user guide](conversations.md) for Android coverage and interpretation.

## Fixed-reference loss score

`app/mos.py` computes bounded, on-demand step intervals from RTCP loss.
Ordinary MOS responses are calculated on demand, while geography persists versioned scores and structured telemetry persists input intervals. Explicit peer selection reuses the peer
local result without mixing evidence or changing call identities. See [MOS](mos.md).

## Schema 6: geographic observations

Version 5→6 backs up the populated database before adding geo_positions, geo_mos
and geo_mos_evidence. Import-time derivation and historical backfill preserve
source evidence and use versioned markers. Aggregation is independent of stored
observations. See [geography](geography.md) for association, deduplication, bounds,
optional tile cache and recovery instructions. Ordinary MOS charts remain
on-demand; only geographic observations persist their model version and inputs.

## Schema 7: movement and network context

Version 6→7 preserves geography and adds network_observations, movement_sequences
and movement_samples with evidence links. Backfill is versioned and idempotent.
[Method, limitations and backup](mobility.md). No prediction is exposed yet.

## Structured telemetry v1/v1.1 and schema 8

`app/telemetry.py` validates the producer contract. `app/telemetry_store.py` stores
canonical source/event identities and all raw evidence, validates chronology and
references, and derives explicit interval loss/MOS plus geographic associations.
Conflicting stable IDs retract dependent products. Legacy extractors remain separate.
Schema 8 adds telemetry_records, telemetry_evidence, telemetry_intervals and
telemetry_geo_context with a pre-upgrade backup. See [rules, bounds and upgrade](telemetry-integration.md).
