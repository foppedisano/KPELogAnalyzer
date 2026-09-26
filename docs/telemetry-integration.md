# Telemetria 1.1: integrazione, piani offline e upgrade schema 8

## Cosa è implementato

- Importazione v1 e v1.1, archivio canonico, deduplicazione tra ZIP e tutte le evidenze.
- Controlli di sequenza, orologio, ID, riferimenti a configurazioni, reti, piani e fix.
- MOS a profilo fisso da finestre RTP definite e da differenze RTCP SR/RR compatibili.
- Associazione posizione–MOS–rete e celle nella Mappa qualità; filtri rete/operatore.
- Audit degli eventi relativi a piani offline. Non vengono generati o eseguiti piani.

Restano futuri riconoscimento del percorso, previsione, API operativa e controllo
dell'audio nelle app. Gli emitter app/GW sono esterni a questo repository.

## Revisione 1.1 del contratto

`kpe.telemetry/1` rimane accettato senza reinterpretare i suoi campi. La revisione
`kpe.telemetry/1.1` aggiunge i tipi qui sotto e rende esplicito il motivo delle azioni.
Per esportare uno schema usare `python -m app.telemetry --schema --version kpe.telemetry/1.1`.
Gli esempi completi sono in `docs/examples/telemetry-v1.1.jsonl`.

| Evento | Dati da registrare |
|---|---|
| `api_request` | ID richiesta, fase started/succeeded/timeout/failed, inizio/fine monotoni, piano restituito se presente, motivo |
| `plan_received` | ID/revisione piano, richiesta, emissione/scadenza UTC, scadenza monotona locale, percorso, confidenza, orizzonte metri/ms, hash, documento originale e profilo di ripiego |
| `plan_state` | Attivazione, sostituzione, scadenza, deviazione, posizione incerta, fallback, ripresa o rifiuto obsoleto; segmento/profilo, motivo, riferimento posizione e incertezza |
| `action` | Campi v1 più riferimento piano nullable e trigger api/plan_progress/local_feedback/fallback/manual |

`document` conserva l'oggetto JSON della risposta. La semantica operativa dei suoi
segmenti/profili verrà definita con il protocollo dei piani; l'analizzatore non lo
esegue. `content_sha256` è l'hash della risposta originale secondo il protocollo
del produttore: il validatore controlla formato e conflitti, non ricalcola un hash
byte-per-byte da JSON serializzato nuovamente. Conservare nel documento anche
versione del protocollo, profili e relative condizioni. Non includere credenziali.

Una richiesta fallita non elimina il piano locale. L'app dovrà applicare la
scadenza e le condizioni ricevute e registrare fallback/deviazione; l'analizzatore
segnala un'attivazione osservata dopo la scadenza monotona. Registrare separatamente
comando richiesto e configurazione effettivamente applicata. Una risposta già
scaduta può essere conservata e seguita da `stale_rejected`.

## Contatori utilizzabili per il MOS

### `rtp-sequence-window/1`

Questa è una nuova semantica normativa per gli emitter v1.1, non un significato
attribuito ai contatori vendor esistenti. Si applica alla ricezione locale:

- `sequence_first` e `sequence_last`: estremi inclusivi, estesi oltre il wrap RTP,
  della stessa coorte di pacchetti originali.
- `expected_packets = sequence_last - sequence_first + 1`.
- `received_in_window_packets`: pacchetti originali unici di quella coorte ricevuti
  entro la chiusura della finestra, prima di ricostruzione FEC/PLC; duplicati esclusi.
- `start_mono_ms/end_mono_ms`: intervallo locale di osservazione di quella finestra;
  il campione aggregato caratterizza tale intervallo, non ogni istante individuale.
- `counter_epoch`: cambia a reset/riavvio del tracciamento della sequenza.
- `complete=true`, configurazione compatibile già osservata, durata massima 30 s.

La perdita è `100*(expected_packets-received_in_window_packets)/expected_packets`.
I campi generici `received_unique_packets` e `expected_packets` del v1 **non**
vengono sottratti automaticamente. Semantiche diverse rimangono grezze con
`loss_semantics_unverified`. La validazione dell'emitter con traffico a esito noto
rimane necessaria, incluse DTX, RED/FEC, arrivi tardivi, restart e cambio SSRC.
Scarti, silenzio saltato e PLC non diventano penalità aggiuntive.

### Report RTCP originali

Il parser controlla framing dei pacchetti compound, versione, padding e lunghezza
SR/RR; seleziona il report block con lo SSRC dichiarato. Più blocchi corrispondenti
restano ambigui. XR e altri pacchetti restano nel grezzo.

Due report compatibili dello stesso ricevitore e flusso permettono di calcolare
delta dei pacchetti attesi (extended highest sequence) e delta della perdita
cumulativa. Il primo report è solo baseline. Gap oltre 30 s, reset, progressione
nulla e delta negativi/incoerenti interrompono la derivazione. Non si azzerano
delta negativi, che possono derivare da recuperi o duplicati.

Un RR inviato descrive la ricezione locale; uno ricevuto la ricezione del peer.
I report remoti sono collocati tra i due istanti locali di ricezione: il ritardo
del report limita l'esattezza della mappatura temporale e geografica upstream.
Non si presume sincronizzazione degli orologi tra app e GW.

Finestre RTP locali esplicite hanno precedenza sugli intervalli RTCP locali
sovrapposti. Altre sovrapposizioni della stessa serie e finestre di sequenza riusate
sono escluse con avviso. Il modello numerico rimane `loss-reference-1`.

## Identità, deduplicazione e riferimenti

`telemetry_records` ha una chiave `(source_id,event_id)`. L'oggetto JSON canonico
ignora ordine dei campi/spazi; tutti gli eventi originali restano in
`telemetry_evidence`. Reimportare lo stesso evento non aggiunge misure.
Stesso ID con contenuti diversi produce un conflitto permanente: le derivazioni
della sorgente vengono ricalcolate e quelle dipendenti escluse. Nessun overwrite
dell'evidenza. Le righe malformate/versioni ignote restano in `events`.

I riferimenti vengono risolti nella stessa sorgente, sessione e boot. Configurazioni
future, ID configurazione riusati con contenuti diversi e fix discordanti non sono
utilizzati. Una rete mancante diventa unknown, senza inferenza dal tipo di app.
Per la rete si usa solo `scope=media_path` dello stream, con limite 30 s e separazione
ai cambi. Il default del sistema non dimostra il percorso del socket media.

Le chiamate si collegano esclusivamente tramite SIP Call-ID esplicito. Gli ID locali
restano osservabili ma non creano correlazioni tra sorgenti. Ogni ZIP dovrebbe
descrivere un solo produttore. Più produttori nello stesso ZIP non producono una
prospettiva unica attribuita automaticamente. Le misure canoniche appartengono alla
prima evidenza importata; gli export sovrapposti aggiungono provenienza, non nuove
prospettive metriche. Gli ID delle derivazioni possono cambiare al ricalcolo;
gli ID degli eventi originali e le annotazioni esistenti vengono conservati.

## Associazione geografica e orologi

La telemetria usa i tempi monotoni per l'associazione e UTC per la visualizzazione.
Si accettano solo fix app già consegnati, non cached, entro 30 s dall'istante del fix;
nessuna posizione futura o di un'altra sorgente/sessione/boot. Gli intervalli sono
spezzati ai nuovi fix, ai cambi rete e alle scadenze. Mancanze di raccolta posizione
interrompono l'associazione. Un GW non localizza automaticamente l'app.

Reset monotoni, conflitti di sequenza o cambi UTC oltre 1 s nel dominio osservato
impediscono le derivazioni coinvolte; un salto nell'ordine `seq` è segnalato come
copertura incompleta. La soglia UTC è una guardia tecnica, non una stima della
precisione GPS. Velocità/direzione/accuratezze restano nel JSON originale per gli
algoritmi successivi. Non si deduce un percorso dal fatto che due fix siano vicini.

La mappa esistente mantiene gli orari originali legacy; quelli strutturati sono
UTC. Un filtro orario non corregge automaticamente il fuso dei log legacy. Le due
pipeline rimangono separate: nessuna somma o deduplicazione implicita tra un log
testuale e una telemetria che potrebbero descrivere lo stesso media.

## Controlli e API

`GET /api/telemetry` restituisce contatori di record/evidenze/conflitti/intervalli
e fino a 200 segnalazioni con evento e file:riga. `issue_count` e
`issues_truncated` indicano la copertura del riepilogo. Il validatore CLI verifica
il singolo record; i controlli di riferimento si eseguono nell'importazione.

Limiti: 100.000 record canonici per sorgente, 1.000 intervalli simultanei per serie,
100.000 intervalli MOS per richiesta e 1.000 evidenze per intervallo. Gli eccessi
producono errori espliciti; l'import ZIP rimane atomico. Questa implementazione
locale non è ancora un servizio distribuito per milioni di dispositivi.

```sql
SELECT r.id,r.source_id,r.event_key,r.conflict,r.issues,x.event_id,f.name,e.line_no
FROM telemetry_records r JOIN telemetry_evidence x ON x.record_id=r.id
JOIN events e ON e.id=x.event_id JOIN files f ON f.id=e.file_id
ORDER BY r.id LIMIT 100;
```

## Upgrade e ripristino

La migrazione 7→8 crea `kpe.sqlite3.pre-v8.bak` prima di modificare un DB popolato.
Non sovrascrive un backup esistente. Aggiunge le tabelle del livello canonico,
evidenze, intervalli e contesto geografico; gli eventi già archiviati vengono
elaborati una volta mediante marker `telemetry-2:<import_id>`.

Prima dell'upgrade esportare il database dalla UI, poi eseguire
`docker compose up --build -d` e verificare `/api/health`. Conservare i backup
localmente. Per tornare alla versione precedente fermare il servizio e ripristinare
il backup in una nuova cartella/volume, secondo il README. Non usare il vecchio
programma sul DB schema 8 e non sovrascrivere un database aperto.
