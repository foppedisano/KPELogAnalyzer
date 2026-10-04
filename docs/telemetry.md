# Contratto di telemetria grezza per app e GW — base v1

## Stato e utilizzo

Base compatibile del formato per app e KalliopeGW: `kpe.telemetry/1`.
Per nuovi emitter usare la [revisione kpe.telemetry/1.1](telemetry-integration.md),
in particolare la semantica esplicita delle finestre di perdita.
Questo repository implementa validazione e conservazione degli eventi; non contiene
il codice dei produttori. Occorre implementare gli emitter nelle app/GW e verificare
le semantiche con i responsabili del motore media prima del rilascio.

La base v1 resta compatibile. La revisione 1.1 e lo schema DB 8 aggiungono
deduplicazione, controlli tra eventi e integrazione selettiva in MOS e mappa.
Vedi [contratto 1.1, semantiche accettate e upgrade](telemetry-integration.md).
Gli algoritmi legacy conservano il loro comportamento; nessuna previsione è ancora generata.

Comandi, senza dipendenze esterne e senza aprire il database:

```sh
python -m app.telemetry docs/examples/telemetry-v1.jsonl
python -m app.telemetry --schema --version kpe.telemetry/1 > telemetry-v1.schema.json
```

Il comando restituisce exit code 1 per dati non conformi; i messaggi mostrano campo
e riga, non i valori. Lo schema JSON è generato dallo stesso contratto del validatore.
Il validatore controlla inoltre relazioni temporali e campi condizionali.
La validazione CLI è per record. L’importazione applica anche i controlli tra eventi descritti nella guida 1.1.

Inserire `telemetry*.jsonl` nello ZIP normalmente importato dalla piattaforma,
anche in sottocartelle. Un oggetto UTF-8 per riga, massimo 64 KiB per record e
40 MiB per file, entro i limiti ZIP già applicati. Le righe vuote sono ignorate.
Versioni ignote e record invalidi sono conservati come `telemetry.invalid`, con
avviso nell'importazione. Non vengono corretti o trasformati in zeri.

## Identità, tempo e qualità del dato

Ogni evento deve contenere tutti i campi comuni dello schema:

| Campo | Contratto |
|---|---|
| `schema`, `type` | Versione e tipo di evento; modifiche incompatibili richiedono una nuova versione |
| `event_id` | ID casuale univoco assegnato alla raccolta, invariato nelle rotazioni e nei successivi export |
| `source_id` | ID pseudonimo dell'installazione produttrice, persistente tra export; niente numeri telefonici |
| `session_id` | Nuovo ID a ogni avvio del processo; non identifica un treno |
| `boot_id` | Dominio dell'orologio monotono; cambia al reset di tale orologio |
| `seq` | Sequenza crescente per sessione, assegnata prima di un eventuale scarto nel logger |
| `role` | `app` oppure `gw`, punto effettivo di osservazione |
| `observed_utc` | Istante di osservazione UTC con `Z`, fino a microsecondi; non ora di flush su disco |
| `mono_ms` | Millisecondi monotoni nello stesso dominio `boot_id`, includendo sospensione quando supportato |
| `validity`, `invalid_reason` | Misura dichiarata valida/invalida e motivo; conformità al formato non prova accuratezza |
| `extensions` | Oggetto facoltativo per estensioni vendor documentate, non interpretate automaticamente |

Ogni sessione descrive piattaforma, versione OS/app/motore, capacità e incertezza
dell'orologio UTC (`null` se ignota). Se manca una misura, usare `null` dove ammesso;
altrimenti emettere un evento `collection` che spieghi l'indisponibilità. Non usare
zero come sentinella. Valori finiti fuori range sono conservati ma non conformi;
NaN/Infinity non sono JSON valido.

Il timestamp monotono deve essere confrontabile con quello dei fix. Se il sistema
usa domini diversi, l'emitter deve convertirli con una relazione documentata oppure
segnalare la funzione indisponibile. Il tempo UTC non sincronizza automaticamente
app e GW: senza incertezza di sincronizzazione accettabile non calcolare latenza
unidirezionale. Un cambio di orologio produce un evento `collection/clock_change`.

`stream` contiene call ID locale, SIP Call-ID esatto o null, ID del flusso, SSRC e
`local_receive`/`local_send`. Il GW riceve l'upstream dell'app sulla stessa tratta;
registrare sempre la prospettiva locale. Relay/B2BUA con Call-ID diversi richiedono
un collegamento esplicito separato. L’integrazione associa soltanto un SIP Call-ID esplicito ed esatto e può creare
la corrispondente chiamata se non esiste. Un ID locale da solo non crea una
correlazione globale. Non crea chiamate da semplici posizioni e non associa
per vicinanza temporale o identità personale.

## Eventi da emettere

### `session`: inventario delle capacità

All'avvio, poi dopo cambi di capacità: piattaforma, versioni OS/app/motore,
modello dispositivo opzionale, incertezza UTC e lista delle capacità. Per ciascuna:
`available`, `unsupported`, `permission_denied` o `disabled`. Usare nomi di campo
come `position.speed_mps` o `network.serving_operator`. La disponibilità effettiva
Android/iOS/desktop deve essere verificata dagli emitter, senza assumere parità.

### `position`: osservazione del movimento sull'app

Coordinate WGS84 in gradi, accuratezza orizzontale in metri, provider, `fix_id`,
`trajectory_id`, ora UTC del fix se disponibile e `fix_mono_ms` obbligatorio.
Velocità in m/s, direzione in gradi da nord e accuratezze restano nullable.
Altitudine in metri è facoltativa: specificare il riferimento verticale nelle
extensions se raccolta. Non mischiare quota ellissoidale e sul livello del mare.

Registrare separatamente fix e ricezione (`mono_ms` dell'envelope). Una posizione
cached mantiene ID e timestamp del fix originale. Non fabbricare nuovi fix a ogni
tick. `trajectory_id` collega campioni contigui, anche tra chiamate, senza indicare
un utente; cambiarlo dopo discontinuità non ricostruibili. La raccolta tra chiamate
è un'opzione distinta da concordare nel prodotto, non abilitata da questa specifica.

Obiettivo iniziale: 1 Hz durante la chiamata, alla cadenza realmente disponibile,
da validare per consumo, background e accuratezza. Segnalare sospensione e perdita
del segnale. In galleria non scrivere coordinate interpolate come misure: le
stime del percorso devono restare derivate e separate. La mappa PQ legacy
implementa già questa separazione; non è un nuovo tipo di fix dell’emitter.

### `network`: contesto effettivo del traffico

Snapshot iniziale, a ogni cambio e heartbeat indicativamente ogni 5 secondi;
la cadenza è una proposta operativa da misurare. `network_id` identifica una
connessione locale; `scope=media_path` richiede `stream_id`. Una rete di default
del sistema non dimostra quale rete stia usando il socket media.

Accesso, rete a monte e sua evidenza (`observed`, `declared`, `unknown`), subscription
dati attiva, operatore SIM e operatore servente separati, tecnologia radio, VPN,
identificativi Wi-Fi e misure radio con nome e unità espliciti. Operatori: preferire
PLMN MCC-MNC in stringa, conservando gli zeri, distinguendo roaming e dual SIM.
Una misura `raw` non è automaticamente confrontabile tra piattaforme.

Gli ID Wi-Fi sono opachi: l'emitter deve documentarne stabilità e dominio. Per
correlare installazioni serve una politica comune; hash con sali indipendenti non
sono confrontabili. L'SSID non identifica univocamente access point o convoglio.
Non registrare credenziali. Non inferire tethering da desktop o nome della rete.
L'upstream ignoto rimane `unknown`; le analisi potranno includerlo separatamente.

### `media_interval`: ricezione e temporizzazione su app e GW

Obiettivo: intervalli consecutivi di un secondo `[start_mono_ms,end_mono_ms)`,
con durata reale e `complete=false` se la raccolta è parziale. Tutti i contatori
sono **incrementi dell'intervallo**, non totali della chiamata. `counter_epoch`
cambia a ogni reset. `config_id` e `network_id` collegano il contesto osservato.
Spezzare l'intervallo quando cambia configurazione, SSRC o rete media.

Campi di base obbligatori: pacchetti attesi e ricevuti unici. L'emitter deve
documentare esattamente in `semantics_id` come assegna i pacchetti agli intervalli:
arrivi nell'intervallo e pacchetti attesi nell'intervallo possono appartenere a
coorti diverse. **Non calcolare loss come differenza dei due senza questa prova.**

Campi nullable/facoltativi da implementare se osservabili:

- Duplicati, riordino, mancanti alla scadenza di playout, arrivi tardivi.
- Scarti per ritardo e overflow, separati dai mancanti e dai duplicati.
- Segnalazioni di salto sequenza, che possono risolversi con un arrivo successivo.
- Media saltato, silenzio saltato, media ricostruito/inserito, in millisecondi.
- Pacchetti recuperati con FEC; occupazione e target buffer alla fine dell'intervallo.
- Lunghezze delle sequenze di perdita (`loss_runs_packets`), secondo semantica
  documentata e gestione esplicita delle sequenze che attraversano i confini.

Prima di implementare l'emitter, il responsabile media deve definire un
`semantics_id` versionato e allegare unità, trigger, popolazione di riferimento,
rapporti di inclusione tra contatori, criteri di deadline, DTX, recupero, reset e
regole di completamento dei burst. Il validatore controlla la presenza dell'ID,
non può certificare queste definizioni. In particolare non sommare skipped silence,
missing e discard senza sapere se rappresentano gli stessi campioni.

### `media_config`, `action`: configurazioni e adattamenti

Configurazione iniziale e a ogni cambio: codec, clock RTP in Hz (può differire dalla
frequenza audio), packetizzazione in ms, canali, PLC, FEC, ridondanza, DTX, modalità
e target del jitter buffer. I campi testuali devono identificare anche la versione
dell'algoritmo e i parametri necessari a riprodurlo, usando extensions documentate.

L'evento `action` distingue richiesta, applicazione, fallimento e ripristino,
collega configurazione precedente/successiva, motivo e previsione responsabile
se presente. Il modello deve poter distinguere qualità osservata prima e dopo
un intervento; registrare il solo comando richiesto sarebbe insufficiente.

### `rtcp`: evidenza originale

Ogni pacchetto RTCP emesso o ricevuto viene conservato come esadecimale, dopo
decifratura SRTCP quando applicabile, senza chiavi. Conservare tutti i report
block e SR/RR/XR con gli SSRC originali, non solo una percentuale loss estratta.
`transport_direction` è invio/ricezione del report, distinto dalla direzione del
flusso descritto. Il validatore per record verifica la codifica; l’importazione schema 8 decodifica
SR/RR compatibili secondo le regole della guida 1.1. XR resta grezzo.
Massimo 16 KiB di pacchetto nel profilo v1; segnalare esplicitamente un superamento
con `collection`, non troncare il pacchetto facendolo apparire completo.

### `collection` e `packet`

`collection` registra avvio/arresto, sospensione/ripresa, permessi, cambi di
orologio, perdita di eventi e motivi. Obbligatorio un riepilogo degli eventi persi
dal logger quando può rilevarli; non dichiarare copertura completa dopo un overflow.

`packet` è una modalità diagnostica opzionale: sequenza RTP, timestamp RTP,
dimensione, istante monotono, evento ricezione/invio/scarto/playout/mancanza,
deadline e motivo. Non contiene audio. Gli aggregati a 1 Hz non permettono di
ricostruire ogni distribuzione di ritardo o simulare arbitrariamente un altro
jitter buffer: per questo servono tracce per pacchetto e regole del motore.

## Conservazione, duplicati e uso futuro

L'archivio mantiene il testo normalizzato di ogni riga, anche invalida o duplicata.
Lo stesso ZIP è idempotente; due ZIP diversi mantengono evidenze separate. Le
derivazioni strutturate usano `(source_id,event_id)` e confrontare i contenuti: stesso
ID con payload diverso è un conflitto, non una nuova misura né un overwrite.
Lo schema DB 8 implementa questa deduplicazione nel livello canonico; i duplicati grezzi restano consultabili.

Le sequenze e il contesto serviranno a inferire percorsi/corse; tali etichette
rimangono risultati versionati e probabilistici. Nessun `train_id` inventato
dall'app. Conservare osservazioni e configurazioni oltre alle future previsioni.

## Accettazione degli emitter

1. Validare esempi sintetici per tutte le capacità dichiarate, su ciascuna piattaforma.
2. Verificare cambi rete/SSRC/configurazione, dual SIM, roaming, DTX e reset.
3. Provare GPS cached, galleria, permessi negati, background e salto dell'orologio.
4. Importare export sovrapposti: gli stessi eventi devono mantenere gli stessi ID.
5. Misurare costo CPU, batteria e spazio della raccolta a 1 Hz e della diagnostica.
6. Verificare sul ricevitore le semantiche di perdita, scarto, skipped e recupero
   con traffico sintetico a esito noto; poi valutare la precisione delle derivazioni.

Fonti per il contratto media: [RTP/RTCP RFC 3550](https://www.rfc-editor.org/rfc/rfc3550),
[RTCP XR RFC 3611](https://www.rfc-editor.org/rfc/rfc3611),
[burst loss RFC 6958](https://www.rfc-editor.org/rfc/rfc6958),
[burst discard RFC 8015](https://www.rfc-editor.org/rfc/rfc8015).

## Consultazione nella piattaforma

```sql
SELECT e.id, f.name, e.line_no, e.kind, e.ts, e.text
FROM events e JOIN files f ON f.id=e.file_id
WHERE f.parser='telemetry'
ORDER BY e.import_id, e.file_id, e.line_no
LIMIT 100;
```

`telemetry.<tipo>.valid` indica formato conforme e misura dichiarata valida;
`telemetry.<tipo>.invalid` una misura dichiarata invalida ma strutturalmente
conforme; `telemetry.invalid` un record non conforme. Il testo conserva timestamp
e valori originali. Le derivazioni seguono esclusivamente le semantiche e le condizioni della guida 1.1.
