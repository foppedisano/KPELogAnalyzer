# Architecture and parser contract

## Data model (schema version 5)

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

## Import pipeline

1. Hash the archive. If already imported, return the existing ID without changing labels or data.
2. Validate size, member count, paths, encryption and per-member size. Read `.txt`, `.log`, `.old`; other entries receive an import warning.
3. Normalize CRLF/CRCRLF and split timestamped multiline records. Both KPE/iOS and reSIProcate timestamps are recognized. Preserve leading un-timestamped fragments unassigned.
4. Collect SIP dialogs from `sip_debug*`: INVITE, ACK, BYE, CANCEL, REFER, PRACK, UPDATE. REGISTER/OPTIONS/NOTIFY do not become calls. SIP auth challenges are not terminal failures.
5. Reconstruct line windows from `kpelog*` additions, state transitions, removals, and terminated-call JSON summaries. Process rotations in timestamp order. A repeated exact record does not create new derived observations.
6. Join the terminal JSON's Call-ID to SIP evidence. SIP-only calls remain available without a guessed line. `CallInfo*` connected/terminated messages provide local-only fallback windows when no KPE window covers them.
7. Store calls and per-import perspectives. Attach events by exact Call-ID or a unique source-local line window. A 250 ms post-termination tolerance accommodates delayed final statistics; ambiguous overlapping boundaries remain unassigned. Unscoped `CallInfo` context uses a unique bounded call window. Other unscoped events remain unassigned.
8. Extract numeric metric observations; keep unassigned observations in the DB. Generate coverage/invalid-value warnings and commit the archive atomically.

## Supported extractors

| Input | Extraction |
|---|---|
| `sip_debug*.txt` | SIP Call-ID, parties, direction, response-based connection/failure, termination |
| `kpelog*.txt` | local line windows, call summaries, final media statistics |
| `CallInfo*.log` | periodic nested metric JSON, ICMP roundtrip, local lifecycle fallback |
| `rtplog*.txt` | RTCP receive/remote loss, jitter, RTT, received packet counter, SSRC, flow |
| `VDlog*.txt` | NART device sections, buffer occupancy/target, skipped silence, delay maxima |
| `PhoneEngine*.log` | timestamped events, explicit `lineId` context, app-version markers |
| other text logs including `resip*` | searchable multiline raw events; exact Call-ID association when available |

## Deliberate limits

The parser is empirical, based on an iOS export, not on the full proprietary KPE specification. No RTP packet capture decoding, measured perceptual MOS, Android format guarantees, automatic conference graph, SDP negotiation state machine, NAT root-cause diagnosis, or audio reconstruction. SIP forking is represented at Call-ID level, not separate From/To-tag dialogs. SIP 2xx evidence on re-INVITE may be the first observed connection when the initial dialog is truncated. Line windows cannot be recovered reliably from RTP timestamps alone.

A ZIP is a source snapshot, not a permanently identified device. Two snapshots of one device can duplicate observations across imports; the UI separates these series. Within a source a given Call-ID has one perspective; highly unusual Call-ID reuse or multiple line assignments for one Call-ID require a richer schema. Global call timestamps aggregate raw per-source timestamps; durations are not clock-corrected. Partial windows closed by line reuse are labelled incomplete.

## Adding a format

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
No schema changes or persisted scores. Explicit peer selection reuses the peer
local result without mixing evidence or changing call identities. See [MOS](mos.md).
