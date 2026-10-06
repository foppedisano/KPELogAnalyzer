# Analisi conversazionali, API e MCP

Per route audio, reset, silenzio iniziale e confronto contatori/transitori:
[query unica, denominatori, evidenze e limiti](transients.md).

[Indice](README.md) · [API](api.md) · [Metodo MOS](mos.md)

Il coding agent interpreta la domanda, scopre i dati disponibili e compone una
query. La piattaforma esegue la query e restituisce risultati, copertura e
provenienza. Non occorre aggiungere un endpoint per ogni nuova domanda.

La sezione **Analisi libere** permette di eseguire gli stessi esempi, modificare
SQL e parametri, salvare ricette e scaricare il risultato JSON. La conversazione
avviene nel client agent: questa sezione non contiene un modello linguistico.
L'agent può costruire tabelle e visualizzazioni usando i risultati restituiti;
la piattaforma non esegue codice Python o JavaScript generato dall'agent.

## Primo utilizzo con un coding agent

Avvia la piattaforma con `docker compose up --build -d`. Configura nel client
un server MCP **stdio** che esegua, dalla directory del progetto:

```sh
docker compose exec -T analyzer python -m app.mcp_server
```

Esempio di configurazione per client che accettano il formato `mcpServers`:

```json
{
  "mcpServers": {
    "kpe-analytics": {
      "command": "docker",
      "args": ["compose", "-f", "C:/percorso/KPELogAnalyzer/compose.yaml", "exec", "-T", "analyzer", "python", "-m", "app.mcp_server"]
    }
  }
}
```

Sostituire il percorso con quello della propria installazione. Il formato della
configurazione dipende dal client. Il container deve essere già avviato; al suo
interno l'API è sulla porta 8080 anche se la porta pubblicata sull'host è diversa.
Con Python installato si può invece usare `python -m app.mcp_server --url
http://127.0.0.1:8080` dalla directory del progetto. In questo caso specificare
la porta effettivamente pubblicata sull'host.

Non vengono aperte altre porte. L'adattatore accetta solo API HTTP su
`localhost`/`127.0.0.1`, non segue redirect e non usa proxy d'ambiente.
Parla JSON-RPC su stdin/stdout; EOF termina il processo. Protocollo MCP
implementato: `2025-11-25`. La configurazione del client non viene modificata
automaticamente dall'applicazione.

Prompt di partenza:

> Leggi catalogo e copertura di KPE. Trova le chiamate con almeno tre episodi
> di MOS sotto 3, ciascuno lungo almeno due secondi. Distingui i ricevitori e
> i flussi, indica la durata osservata e mostra le evidenze delle peggiori.
> Non trattare dati assenti come buona qualità e non dedurre cause dai soli log.

I dati restituiti entrano nel contesto del client agent scelto dall'utente:
valgono quindi le modalità di trattamento dati di quel client.

## Strumenti MCP e API

| Strumento | HTTP | Funzione |
|---|---|---|
| `analytics_geo_cells` | POST `/api/analytics/geo-cells` | Celle e confini con i filtri della mappa |
| `analytics_call_route` | POST `/api/analytics/call-route` | Percorso della chiamata, punti diretti e interpolati separati |
| `analytics_perceptual_quality` | POST `/api/analytics/perceptual-quality` | Campioni PQ correnti, durata ed evidenze AWT |
| `analytics_connectivity` | POST `/api/analytics/connectivity` | Timeline rete/servizi per chiamate o sorgente e periodo |
| `analytics_geo_temporal` | POST `/api/analytics/geo-temporal` | Profili temporali, copertura, contesti ed evidenze paginate |
| `analytics_catalog` | GET `/api/analytics/catalog` | Viste, colonne, regole, dizionario metriche, modello ed esempi |
| `analytics_coverage` | GET `/api/analytics/coverage` | Disponibilità grezza di sorgenti, reti, ruoli, posizioni |
| `analytics_query` | POST `/api/analytics/query` | Query parametrizzata, in sola lettura |
| `analytics_evidence` | POST `/api/analytics/evidence` | Eventi → file/riga e metriche strutturate |
| `analytics_list_recipes` | GET `/api/analytics/recipes` | Fino a 500 ricette, con indicatore `truncated` |
| `analytics_save_recipe` | POST/PATCH `/api/analytics/recipes` | Salva configurazione; non modifica log |
| `analytics_run_recipe` | POST `/api/analytics/run-recipe` | Riesegue sui dati attuali |

Il salvataggio è l'unico strumento che scrive: memorizza una configurazione
validata, con revisione e storico. Il client deve usarlo quando richiesto
dall'utente. Tutti gli strumenti restituiscono JSON nel contenuto testuale MCP.

### Definizione di analisi

```json
{
  "sql": "SELECT series_key,call_id,perspective_id,direction,episode_count,bad_seconds,bad_percent,coverage_percent FROM a_mos_summary WHERE episode_count >= :episodes ORDER BY bad_percent DESC",
  "parameters": {"episodes": 3},
  "datasets": ["mos"],
  "scope": {},
  "threshold": 3,
  "min_episode_seconds": 2,
  "limit": 200,
  "semantic_version": "analytics-1"
}
```

- `scope.call_ids`: ID interni, fino a 2.000; assente o vuoto significa tutte.
- `scope.start`, `scope.end`: periodo semiaperto `[start,end)`, per esempio
  `2026-09-01 00:00:00`. I timestamp sono confrontati come osservati: nessuna
  conversione di fuso o correzione dell'orologio. Separare `time_basis` nelle
  analisi MOS; le coordinate UTC della telemetria non rendono UTC i log legacy.
- `scope.include_duplicates`: false predefinito. Esclude le prospettive
  riconosciute come copie storiche; un'identità sconosciuta non prova unicità.
- `datasets`: vuoto per sole osservazioni; `['mos']` prepara intervalli,
  episodi e contesto. Le tabelle MOS sono vuote se non richieste.
- `threshold`: episodio scarso se `value < threshold`, predefinito 3.
- `min_episode_seconds`: filtra gli episodi, non il totale di tutti i secondi
  sotto soglia in `bad_seconds`.
- `parameters`: oggetto di parametri nominati o array posizionale. Usarli per
  i valori invece di costruire SQL concatenando testo dei log.

La risposta include `columns`, `rows`, `truncated`, `coverage`, la definizione
normalizzata, versione semantica e modello, tempo impiegato, avvisi e
`analysis_hash`. `snapshot` riporta schema e massimi ID visibili nella
transazione: è una traccia della lettura, **non un archivio immutabile del DB**.
Il risultato esportato permette di conservare ciò che si era osservato.

### Ambito delle viste

| Viste | Contenuto e join |
|---|---|
| `a_calls` | Chiamate che intersecano lo scope; `id` è il call_id interno |
| `a_observations` | Prospettive selezionate; `call_id → a_calls.id`, `import_id → a_sources.id` |
| `a_sources`, `a_files` | Import e copertura file; con tutte le chiamate includono anche import senza chiamate |
| `a_events` | Metadati nel periodo; `id` è la chiave di evidenza; testo grezzo escluso |
| `a_metrics` | Metriche di quegli eventi, anche invalide; `event_id → a_events.id` |
| `a_positions`, `a_networks`, `a_movement` | Osservazioni degli import selezionati, incluse quelle fuori periodo utili al contesto; applicare filtri temporali SQL per analisi autonome |
| `a_telemetry` | Record canonici e JSON validato; controllare conflitti e domini temporali |
| `a_correlations`, `a_conversation_calls` | Evidenze di UUID e collegamenti manuali, senza fusione delle chiamate |
| `a_mos` | Intervalli validi tagliati al periodo; `id` locale alla singola richiesta |
| `a_mos_evidence` | Tutti i riferimenti: `interval_id → a_mos.id` |
| `a_mos_episodes`, `a_episode_intervals` | Episodi e appartenenza degli intervalli |
| `a_mos_summary` | Statistiche per `series_key`, mai fusione implicita di flussi |
| `a_mos_network` | Intervalli divisi ai cambi di rete/scadenze; `interval_id → a_mos.id` |

Senza call_ids espliciti sono inclusi anche eventi non assegnati a chiamate.
Con call_ids espliciti restano soltanto quelli attribuiti alle chiamate scelte.
Per ogni metrica controllare `valid`, `unit`, `statistic`, direzione e flusso.
Le unità `raw` rimangono tali.

## Come rispondere correttamente

**Eventi ed episodi sono domande diverse.** Dieci campioni consecutivi sotto
soglia possono formare un solo episodio. Un buco o un campione invalido interrompe
la continuità. Le finestre legacy mantengono il limite di validità del metodo
MOS; non si estende il valore all'intera chiamata.

**Il MOS è quello della piattaforma.** Profilo fisso G.711/PLC di riferimento,
perdita RTCP o finestre RTP validate; non una misura percettiva completa.
Questa funzione non aggiunge jitter o silenzio skippato alla formula. Tali
metriche restano interrogabili separatamente.

**Le medie sono pesate per durata osservata.** `covered_seconds` è la somma
delle durate della singola serie; `mean = Σ(MOS × secondi) / Σ(secondi)`.
`coverage_percent` usa la finestra della prospettiva, tagliata allo scope;
se i confini non sono noti è NULL. Non usare le chiamate prive di MOS come
chiamate senza problemi. Non sommare flussi sovrapposti chiamandoli secondi di
chiamata: gli esempi aggregati indicano esplicitamente *stream seconds*.

**Il ricevitore non è automaticamente il chiamato.** `incoming` descrive
ricezione locale; `outgoing` deriva da una misura del peer. `app_direction`
dipende dal ruolo, con `role_basis` che esplicita conferma o assunzione.
`receiver_basis=source_only` indica una sorgente, non una persona identificata;
`remote_unidentified` non identifica l'interlocutore. Il catalogo separa queste
condizioni. Per collegare app/GW usare ruoli e associazioni esplicite.

**La rete è quella dell'osservatore.** Il contesto legacy scade dopo 30 secondi;
conflitti e assenza diventano `unknown`. Il contesto della telemetria è quello
già validato in fase di importazione. Per questa prima versione l'identità Wi-Fi
strutturata non è proiettata in `a_mos_network`; rimane nel JSON canonico quando
presente. Senza identità Wi-Fi non si può classificare le singole reti. Non
attribuire automaticamente al peer remoto la rete dell'app che scrive il log.

**Una classifica richiede un denominatore.** Presentare percentuale del tempo
osservato sotto soglia, chiamate valutabili, secondi e copertura, oltre ai conteggi.
Segmentare per flusso e base temporale quando necessario. Una correlazione
fra rete e MOS non dimostra causalità.

## Ricette, limiti e aggiornamento

Salvataggio: `{title, question, interpretation, definition}`. Per aggiornare
aggiungere `id` e `revision`: una revisione vecchia viene rifiutata. La query
viene eseguita e validata prima di salvarla. `run-recipe` accetta `{id, overrides}`;
gli override ammessi sono parameters, scope, threshold, min_episode_seconds,
limit. Sostituiscono l'intero campo, non modificano la ricetta originale.

SQL massimo 20.000 caratteri, 100 parametri, 1.000 righe restituite, 4 MiB di
dati tabellari, 3 secondi per query dopo la preparazione. Preparazione MOS:
30 secondi, 2.000 chiamate, 100.000 intervalli. Il contesto è limitato a
10.000 prospettive e 100.000 osservazioni rete degli import selezionati. Se necessario suddividere per
periodo/chiamate e combinare somme e denominatori, non medie di medie.
I limiti provocano un errore esplicito; il limite di righe produce `truncated`.
Le chiamate HTTP/MCP accettano richieste fino a 64 KiB.

Le query usano viste temporanee e un authorizer SQLite. Non sono ammesse
scritture, ATTACH, PRAGMA, estensioni, schema interno o nomi delle tabelle fisiche.
Anche un alias o una costante uguale a un nome riservato viene rifiutato: scegliere
un alias diverso o passare il valore come parametro. Il testo dei log resta
consultabile nella UI locale; gli strumenti analitici restituiscono riferimenti
e metriche strutturate, non credenziali eventualmente presenti nei messaggi.

Lo **schema 10** aggiunge `analysis_recipes` e `analysis_recipe_revisions`.
All'aggiornamento di un DB popolato viene creato `kpe.sqlite3.pre-v10.bak` prima
della migrazione. Un backup omonimo esistente non viene sovrascritto: conservarlo
o rinominarlo prima di riprovare. Nessun reimport o cancellazione delle evidenze.
Per tornare indietro fermare il servizio e ripristinare una copia coerente del
backup insieme alla versione precedente del codice; non abbassare manualmente
il numero di schema. Le nuove ricette non sono presenti nel backup precedente.

Riferimenti del protocollo: [ciclo di vita MCP](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle),
[trasporto stdio](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports),
[strumenti](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

## Episodi audio e percentuale temporale di underrun

Richiedere `datasets: ["incidents"]`, con le chiamate in `scope.call_ids`.
Il dataset viene ricostruito dagli eventi senza esporre il testo dei log e senza
modificare il database. Non richiede reimport o migrazione.

- `a_incidents`: episodi completi delle prospettive selezionate, anche fuori dal
  periodo richiesto; osservatore, device di ingresso, durata dichiarata,
  intervallo dei messaggi, stato e convenzione di collocazione temporale.
- `a_incident_evidence`: eventi e riferimenti file/riga di ogni episodio.
- `a_incident_windows`: occupazione nelle finestre, ritagliate sul periodo richiesto.
- `a_incident_window_members`: collegamento tra finestre ed episodi.
- `a_incident_coverage`: copertura di ogni prospettiva, incluse quelle senza episodi.

AWT è un osservatore dell'uscita audio; `NART0 of Line 0` può essere il suo
**device di ingresso**. Non cercare AWT soltanto nelle metriche periodiche.
AWT, VD, device e prospettive restano serie distinte.

`incident_window_seconds` vale 1 per default (ammessi 0,001–3.600 secondi).
Le finestre partono dalla connessione della prospettiva, oppure dal suo inizio
se manca la connessione. L'ultima finestra e quelle ritagliate usano la propria
durata effettiva come denominatore. Si calcola l'unione degli intervalli chiusi:
600 ms ripartiti in 200 e 400 ms su due finestre intere danno 20% e 40%; episodi
sovrapposti non vengono sommati due volte.

`incident_time_basis` può essere:

- `reported_end` (default): durata dichiarata dal motore, collocata a ritroso
  dal timestamp di fine. È una **stima della collocazione**, non una misura
  precisa dell'istante iniziale. La durata può differire dai timestamp dei messaggi.
- `log_span`: intervallo ricostruito usando i timestamp dei messaggi; consultare
  `start_basis` per distinguere inizi osservati e ricostruiti.

Episodi aperti o non collocabili rendono `percent` NULL nelle finestre interessate;
`incomplete=1` li segnala e `known_percent` conserva la sola occupazione chiusa
ricostruita. Zero non certifica audio sano: significa assenza di episodi ricostruiti.
Se un osservatore non compare, non vengono inventate finestre a zero.

Esempio SQL, con parametro `observer` uguale a `AWT%`:

```sql
SELECT series_key, window_index, start, end, window_ms,
       underrun_ms, percent, incomplete
FROM a_incident_windows
WHERE observer LIKE :observer
ORDER BY series_key, window_index
```

Per la percentuale complessiva usare `100 * SUM(underrun_ms) / SUM(window_ms)`
su una serie completa, senza finestre incomplete: non fare una media semplice
quando le finestre hanno durate diverse. Il metodo è `incident-occupancy-1`.
Limiti: 100 prospettive, 100.000 episodi/finestre, 200.000 associazioni
fra episodi e finestre. Restano attivi i limiti di query e risposta.

Oltre 1.000 righe paginare con ordine stabile, `LIMIT 1001 OFFSET :page_offset`
e `limit: 1000`, controllando `truncated` e che lo snapshot non cambi fra pagine.
Lo script seguente esporta CSV, episodi, evidenze e metadati JSON:

```powershell
python scripts/export_incident_windows.py --call-id 'CALL-ID' --output data/analysis/example
python scripts/plot_incident_windows.py data/analysis/example/analysis.json
```

Il secondo script richiede Matplotlib solo per produrre PNG/SVG; non è una
dipendenza della piattaforma. Accetta una singola serie completa. Nella UI
Analisi attivare «Calcola episodi audio e finestre» e selezionare la chiamata.
Dopo l'aggiornamento del server riaprire la sessione MCP del client perché
ricarichi il catalogo e lo schema degli strumenti.


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

## PQ, percorsi, tentativi e connettività — MCP 1.3.0

Il server corrente (1.4.0) espone 13 strumenti. `analytics_catalog.current_analysis` descrive
schemi, limiti e regole dei nuovi adattatori; i calcoli sono quelli della UI,
senza formule replicate, migrazioni o scritture sui log.

- `analytics_geo_cells`: aggiungere `"metric":"perceptual"` per le celle PQ;
  `mos` rimane il default compatibile. `origin`, `estimate`, `direct_cells`,
  `estimated_cells` ed evidenze distinguono dati diretti e stime. Il dato diretto
  prevale e la media generale non incorpora le stime. I profili
  `analytics_geo_temporal` restano MOS/perdita/metriche osservate: non supportano PQ.
- `analytics_call_route`: `{"call_id":1,"perspective_id":1,"cell":50}`;
  solo `call_id` è obbligatorio. Una sorgente per volta, scelta come nella UI.
  Posizioni dirette e `interpolation` restano separate con prove degli estremi
  e dell'audio. Limiti: 10.000 posizioni, 100.000 intermedi, gap 120 s.
- `analytics_perceptual_quality`: `{"call_ids":[1]}`, da 1 a 20 ID SIP interni;
  restituisce `method`, `samples`, `rules`, massimo 100.000 campioni.
  Riusa la derivazione del grafico, conservando le prospettive; non esclude
  automaticamente le copie storiche come fa la mappa. PQ 100 assume completo
  il logging AWT, anche senza heartbeat; non equivale a MOS o qualità certificata.
- `analytics_connectivity`: `{"call_ids":[1]}` oppure
  `{"import_id":1,"start":"2026-01-01 12:00:00","end":"2026-01-01 13:00:00"}`.
  Non combinare le due modalità. Timestamp osservati senza fuso, massimo 24 ore
  e 50.000 evidenze per sorgente; da 1 a 20 chiamate e massimo 40 prospettive.
  Le sette fasce restano separate, con scadenza 30 s e prove file:riga.

I tre nuovi endpoint leggono uno snapshot coerente e rifiutano risposte oltre
4 MiB con errore esplicito: restringere chiamate/periodo quando disponibile.
PQ e percorso non hanno paginazione o filtro temporale; una singola chiamata
oltre il limite richiede la UI/API ordinaria o una futura estensione del contratto.
Non si troncano silenziosamente i punti né si pubblicano i log originali.

Le query SQL scoprono inoltre `a_connectivity` e `a_user_attempts`, con ID evento,
file/riga, stato e ragione. Sono osservazioni grezze: le richieste non sono
deduplicate come il registro UI e non rappresentano chiamate uniche. Il
destinatario della richiesta e il testo grezzo sono esclusi. Con `scope.call_ids`
i tentativi rimangono vuoti; la connettività include solo attribuzioni esatte
al Call-ID. Per il contesto sorgente anche fuori call usare lo strumento timeline.
`analytics_coverage` include conteggi grezzi per stato e livello.

Esempio senza attribuzioni causali:

```sql
SELECT status, COUNT(*) AS observations FROM a_user_attempts GROUP BY status
```

Aggiornare il container seguendo la [guida di installazione](getting-started.md),
poi riconnettere il client MCP per rileggere elenco strumenti e istruzioni.
Nessun cambio di schema, parser o modello PQ. Le ricette SQL restano compatibili;
i nuovi strumenti dedicati non sono definizioni salvabili in `analytics_save_recipe`.


## Switch Network espliciti

Eventi, timeline, grafici e mappe evidenziano le richieste Switch Network con
un marker viola e prove file:riga. Transizioni contestuali e posizioni stimate
sono dichiarate separatamente. API `POST /api/analytics/network-switches` e MCP
1.4.0 (13 strumenti), `analytics_network_switches`, usano lo stesso calcolo.
Vedi [regole, campi e limiti](network-switches.md). Nessuna reimportazione richiesta.
