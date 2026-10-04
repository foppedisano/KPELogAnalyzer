# Silenzio, underrun e transitori

Il dataset `transients` confronta contatori ed eventi della stessa prospettiva.
**Coincidenza temporale non significa causa.** Nessun transitorio riconosciuto
non significa nessuna causa: il segnale può mancare nei log.

## Query unica per piattaforma

Inviare a `analytics_query` o POST `/api/analytics/query`:

```json
{
  "datasets": ["transients"],
  "transient_tolerance_seconds": 0,
  "parameters": {"metric": "vd.silence_played", "observer": "NAWT%"},
  "limit": 100,
  "sql": "SELECT platform,type,SUM(positive_intervals_with_transient) AS silence_intervals_with_transient,SUM(intervals_with_transient) AS all_intervals_with_transient,SUM(positive_intervals_without_any_transient) AS silence_intervals_without_any_transient,SUM(total_intervals) AS total_evaluable_intervals FROM a_counter_transient_summary WHERE name=:metric AND observer LIKE :observer GROUP BY platform,type ORDER BY platform,type"
}
```

Per ricezione usare `observer: "AWT%"`; per il numero di underrun usare
`metric: "vd.underruns"`. Aggiungere `"scope":{"call_ids":[1,2]}` per
le chiamate da analizzare (ID di esempio). La tolleranza, tra 0 e 30 secondi,
si applica a entrambi i lati dell'intervallo. Sono inclusi anche i tipi con zero
coincidenze, quando esistono intervalli valutabili.

Il denominatore comprende soltanto intervalli `status=ok`: esclude prima
lettura, reset, gap oltre 30 s, invalidità e conflitti. Una riga rappresenta un
intervallo di una serie, non un secondo di chiamata o un dispositivo indipendente.
Le serie conservano prospettiva, osservatore, output, input, device, ciclo,
flow, SSRC, direzione e unità. I tipi possono sovrapporsi: non sommare le righe
tra tipi. Il conteggio senza alcun transitorio è ripetuto per confronto.

## Viste ed evidenze

| Vista | Contenuto |
|---|---|
| `a_transients` | Notifiche/operazioni normalizzate, stati disponibili, piattaforma, base osservata/dedotta, attribuzione, evento/file/riga |
| `a_transient_evidence` | Tutte le copie delle prove, incluse rotazioni deduplicate nello stesso import |
| `a_transient_counter_intervals` | Intervalli `vd.silence_played` e `vd.underruns`, materializzati una volta con il dataset transients |
| `a_counter_transient_matches` | Coppie intervallo/transitorio entro la tolleranza |
| `a_counter_transient_context` | Transitorio più vicino e distanze dalla connessione/fine |
| `a_counter_transient_summary` | Denominatori per chiamata, prospettiva, serie e tipo |
| `a_counter_initial_observations` | Quantità alla prima lettura, finestra e prova della creazione quando disponibile |
| `a_transient_coverage` | Disponibilità dei file di controllo e transitori attribuiti |

Le distanze sono non negative, dall'intervallo chiuso `[interval_start, ts]`:
zero all'interno, compresi i bordi. Un evento sul bordo comune può coincidere
con due intervalli adiacenti. Non localizzano l'incremento. Il transitorio più
vicino può essere fuori tolleranza; `matches` contiene solo coincidenze.
Connessione/fine ignote producono distanze `NULL`.

```sql
SELECT c.call_id,c.observer,c.input_device,c.lifecycle,
       c.interval_start,c.ts,c.delta,c.unit,c.previous_event_id,c.event_id,
       t.type,t.ts AS transient_ts,t.event_id AS transient_event_id,
       t.filename,t.line_no,m.distance_seconds
FROM a_counter_transient_matches m
JOIN a_transient_counter_intervals c ON c.id=m.metric_id
JOIN a_transients t ON t.id=m.transient_id
WHERE c.name=:metric AND c.delta>0
ORDER BY c.call_id,c.ts,t.ts
```

I confini chiamata riusano il tempo della prospettiva e un evento a quel tempo;
sono `inferred/perspective_boundary`, perché possono derivare dalla ricostruzione
SIP. Le notifiche sono `observed`. L'attribuzione di eventi globali è separatamente
`unique_source_window` solo per una singola prospettiva compatibile dello stesso
import, controllando anche quelle fuori scope. Ambiguità e mancata attribuzione
restano esplicite. Non si collegano export differenti per coincidenza temporale.
I transitori mantengono il contesto dei file selezionati anche fuori periodo;
il periodo seleziona i timestamp finali degli intervalli da confrontare.

Gli stati precedenti assenti restano `NULL`. `Default Audio Input` non identifica
le cuffie. Si espongono classi Android autorizzate, non nomi personali.
Per record Android storici con millisecondi separati da `:`, il transitorio
legge la precisione scritta nella riga (`log_android_milliseconds`), senza
modificare gli eventi persistiti o applicare correzioni di orologio.

## Indagine riproducibile e formati

```sh
python scripts/inventory_transients.py /percorso/kpe.sqlite3
```

Il DB è aperto in sola lettura. L'inventario restituisce piattaforma, file,
formato normalizzato, conteggio e riferimento evento/riga, senza testo grezzo.
Include export ripetuti e rotazioni: non conta eventi indipendenti.

| Fenomeno | File e formato riconosciuto | Limite |
|---|---|---|
| Route iOS | `PhoneEngine.log`: `Received route change notification: AVAudioSessionRouteChangeReason(rawValue: N)` | Codice conservato senza inventarne il significato |
| Route Android | `application*.log`: `AudioState[communicationDeviceChanged -> ...]` | Classe del device quando disponibile |
| Sessione Android | `AudioState[startAudioSession]` / `stopAudioSession` | Operazione, non interruzione OS |
| Vivavoce iOS | `ios_hwwrapper.log`: `Set isSpeakerphoneActive [TRUE/FALSE]` | Impostazione, non necessariamente cambio di stato |
| Muto | `kpelog*`: `Setting audio input N mute status to true/false` | Operazione, non prova di silenzio effettivo |
| Attesa/ripresa | `kpelog*`: richiesta hold, blocking resume, accettazione on-hold | Richiesta e accettazione distinte; direzione dell'accettazione ignota |
| Re-INVITE | `sip_debug*`: INVITE con To-tag nei veri header | Richiesta in-dialog; risposte e body esclusi |
| Rete iOS | `PhoneEngine.log`: network connection changed; `App.log`: differenza SSID/IP | Non dimostra cambio d'interfaccia fisica; ripetizioni con campi identici escluse |
| Rete Android | `application*.log`: callback NetworkMonitor/ConnectionChangeMonitor available/lost | Disponibilità, non identità d'interfaccia |
| Creazione device | `VDlog*`: Creating device con nomi audio/NART/NAWT autorizzati | Creazione, non automaticamente reset/cambio cuffie |
| Reset scheduling | `VDlog*`: reset del VOD timing | Notifica puntuale, distinta dal contatore periodico |
| Reset audio Android | `application*.log`: AudioRoute resetAudio | Operazione, non prova di ricreazione hardware |

I marker cercati per audio focus e interruzioni AVAudioSession non sono stati
trovati nel corpus esaminato. Il generico “interruption filter” Android non è
un'interruzione audio. Le enumerazioni di device disponibili e gli snapshot
Headphones non provano da soli connessione/disconnessione o selezione della route.
Per colmare questi buchi serve logging nell'app: timestamp preciso, sessione/linea,
motivo, stato prima/dopo, route effettiva, focus/interruzione iniziata e terminata.

## Prima lettura ed episodi NAWT

La quantità iniziale non è un delta; `localizable=0` la distingue dagli incrementi
misurati. La creazione del VOD, quando nota, delimita la finestra. Altrimenti la
connessione è solo un riferimento (`connection_context_only`): parte della
quantità potrebbe precederla. Senza un confine compatibile la finestra resta
aperta a sinistra. Non sommare prima lettura e delta senza dichiarare le due
componenti. Si usa la storia completa del ciclo prima del filtro temporale,
quindi un ritaglio non crea un falso initial.

Esistono messaggi NAWT di inizio/prosecuzione/termine underrun con durata dichiarata.
La ricostruzione scopre `Default Audio Input` solo con NAWT, linea esplicita e
finestra non ambigua. Creazioni successive separano i cicli; osservatori/input
restano distinti. Durata dichiarata e posizione ricostruita non sono equivalenti:
un timestamp al millisecondo non prova precisione campione per campione.

`datasets:["incident_summary"]` abilita `a_incident_call_summary` fino a 2.000
prospettive senza finestre per secondo. `series_key` distingue i cicli; conteggi
chiusi/non risolti e unione dei soli intervalli collocabili restano separati.
Una prospettiva senza episodi ha conteggio zero e durata `NULL`.
`a_incident_coverage.evaluability` distingue osservazioni del lettore presenti
da nessuna evidenza riconosciuta, senza promettere copertura continua.
`incidents` conserva il limite di 100 prospettive per le finestre dettagliate.

## Ostacoli e aggiornamento

- Campioni dell'import successivo dentro una chiamata di un altro import:
  non si riassegnano usando soltanto linea e tempo. I non attribuiti rimangono
  visibili in copertura; occorrono prove d'identità e una prospettiva compatibile.
- Chiamate senza Call-ID, anche di durata identica: non vengono fuse
  automaticamente. Vedi [identità e deduplicazione](source-dedup.md).
- `a_metrics` resta indipendente dagli episodi: buffer e dejitter sono accessibili
  se presenti nello scope. Per unirli agli episodi verificare device, osservatore
  e copertura; non interpolare.
- `a_counter_intervals` su tutti i contatori può superare 3 s. Per questa analisi
  usare `a_transient_counter_intervals` con `transients`: materializza solo i due
  contatori necessari nella preparazione limitata a 30 s. L'authorizer e i limiti
  SQL restano attivi.
- Lo schema MCP pubblica mos, incidents, incident_summary e transients. Un client
  che mostra soltanto mos deve aggiornare la discovery degli strumenti.

Nessuna migrazione o reimportazione: le nuove tabelle sono temporanee e scompaiono
con il rollback della lettura. ID e annotazioni restano invariati. Aggiornare il
container seguendo la [guida di avvio e backup](getting-started.md).
