# Inventario recente e piano di implementazione

## Stato del lavoro

Inventario completato; le sei fasi sono implementate nello schema 11 e nel parser 1.12.0.
Questo documento permette di riprendere il lavoro in una nuova chat.
La piattaforma ha già API analitiche, MCP stdio, episodi audio e occupazione
temporale per finestre. Vedi [Analisi e MCP](analytics.md).

Il corpus locale verificato usa Kalliope **1.5.0**, VDK **4.14.0**, build
**8cb1a8d2**. La versione dell'app non è una versione dello schema dei log:
riconoscere anche la struttura osservata. Si tratta dei blocchi testuali con
sezioni Device name e unità esplicite, non del contratto JSONL di telemetria.
Non usare i vecchi formati per completare questo inventario; preservarne però
la compatibilità esistente quando si modifica il codice.

Gli allegati dettagliati sono locali, sotto `data/analysis/inventory-latest/`:
`inventario.md`, `fields.csv`, `inventory.json`, `audit.py`, `report.py`.
Contengono evidenze reali e devono rimanere esclusi da Git. L'inventario è stato
limitato al tratto dell'ultimo import successivo al primo avvio con versioni
verificate: anche uno ZIP recente può contenere record più vecchi.

## Risultati dell’inventario prima dell’implementazione

- VD: 61 etichette distinte, di cui 52 con dati/stati e 9 intestazioni o
  segnaposto. Alcune righe contengono più valori: non sono 52 metriche scalari.
- Soltanto tre etichette periodiche VD vengono estratte: occupazione buffer,
  silenzio saltato e limite dinamico dejitter, nelle sole sezioni NART.
- RTCP: sei campi numerici supportati, cinque contatori pacchetti mancanti,
  oltre a clock e metadati non strutturati. SSRC è già una dimensione delle metriche.
- JSON KPE: otto famiglie osservate, incoming/outgoing e last/avg/min/max;
  tutti i percorsi numerici finiti osservati sono supportati. N/A non diventa zero.
- Heartbeat VD e monitor NART/NAWT contengono byte, cicli, stati e timestamp
  che allora non venivano estratti come dati strutturati.
- Il parser numerico RTCP non riconosce alcuni valori in notazione scientifica:
  i valori finiti fuori range vanno conservati con valid=0, non scartati.

Questa è copertura del corpus osservato, non garanzia di tutte le varianti che
la release potrebbe emettere su altre piattaforme. I campi completi sono nel
[catalogo dell'inventario](periodic-metrics-inventory.md).

## Ordine consigliato per la successiva implementazione

### 1. Contesto e identità

Distinguere osservatore (AWT, VD, NAWT), device di output, input collegato,
linea/flow e sessione o ciclo di vita del device. I contatori del ring per un
VOD descrivono il rapporto lettore/input, non genericamente tutto il device.
Le metriche attuali mantengono NART ma non una colonna dedicata all'osservatore;
la chiave di deduplica dell'arricchimento non lo include. Correggere il modello
prima di aggiungere contatori per osservatore. Non inventare SSRC o associazioni.
Resettare lo scope a ogni Device name. Conservare le prove file/evento/riga.

### 2. Underrun e silenzio riprodotto

Estrarre il contatore di silenzio riprodotto per underrun, numero degli episodi,
stato e durata corrente, distinguendo totale/parziale e lettore/input.
Confrontare gli incrementi con gli episodi già ricostruiti; non sommare due
misure dello stesso fenomeno. Segnalare reset e discontinuità.
Il contatore non localizza il silenzio all'interno dell'intervallo tra campioni:
non attribuire precisione di un secondo senza evidenze aggiuntive.

### 3. Parsing RTCP

Supportare notazione scientifica e validazione finita/range. Conservare valori
finiti invalidi con valid=0 e provenienza. Niente zero sostitutivo per NaN/N/A.
Verificare regressioni per le due direzioni e per i formati già supportati.

### 4. Contatori e misure periodiche mancanti

Aggiungere campioni saltati, limiti buffer, errori/reset, contatori pacchetti,
byte e durata media elaborata. Conservare valori/unità originali. Unità non
confermate restano raw. GOOD/BAD non significa automaticamente persi; conteggi
cumulativi non vanno sommati lungo il tempo. Le ripetizioni della stessa riga
nello stesso blocco non sono campioni indipendenti.

### 5. Stati e metadati

Strutturare stati/codici dei thread, timestamp di avanzamento, cicli per fase,
SN/ROC e clock RTCP. Non forzare categorie o timestamp nell'attuale tabella
numerica se ciò ne perde il significato. Esporre copertura, unità, reset e limiti
nel catalogo condiviso, nelle API/MCP e nei grafici pertinenti.

### 6. Recupero storico e validazione

Backfill versionato e idempotente dagli eventi già conservati, senza reimport,
senza cancellare il DB e senza cambiare ID o annotazioni. Prima progettare
migrazione e backup; provare su DB temporaneo/copia coerente. Aggiornare i marker
senza reinserire le vecchie metriche: il semplice bump di vd-1 con riesecuzione
dell'intero estrattore non basta a garantire idempotenza.

Test sintetici minimi: osservatori diversi sullo stesso NART e timestamp,
più input nello stesso blocco, linee riutilizzate, sezioni non NART, reset,
campi ripetuti, blocchi troncati, unità, numeri esponenziali e invalidi,
backfill ripetuto e conservazione degli ID. Verificare authorizer e limiti MCP.
Aggiornare app/catalog.py e rigenerare docs/metrics.md tramite lo script dedicato.
Eseguire unittest completo e controlli JavaScript; verificare UI se modificata.

## Punti di ingresso nel codice

- app/enrichment.py: estrazione VD, scope device, deduplica, marker vd-1.
- app/parser.py: statistiche JSON KPE e RTCP; parser corrente 1.12.0.
- app/incidents.py: episodi per osservatore/input NART.
- app/analytics_incidents.py: finestre e unione intervalli, metodo incident-occupancy-1.
- app/analytics.py, app/analytics_mos.py, app/mcp_server.py: API analitiche e MCP.
- app/db.py: schema corrente 11, migrazioni con backup.
- app/source_dedup.py: identità della sorgente e import ripetuti.
- tests/test_enrichment.py, tests/test_analytics_incidents.py, tests/test_parser.py.

## Stato operativo per il passaggio di chat

Istanza Docker locale su http://127.0.0.1:8080/, volume kpe-data.
MCP di Claude Code già configurato e funzionante; dopo modifiche a schema tools
o riavvio container, riconnettere il client. Il server è un adapter stdio verso
l'API loopback; non aprire accesso remoto al DB.
Gli artefatti dell'analisi AWT precedente sono in data/analysis/call-419-awt/.
La collocazione reported_end ancora la durata dichiarata al messaggio finale;
è stimata, distinta dalla distanza tra messaggi. L'inventario non ha cambiato
il calcolo MOS né implementato i nuovi contatori.

Non committare DB, ZIP, log, allegati con dati reali o configurazioni personali
dei client. Per riprodurre l'inventario usare gli allegati locali in sola lettura.

## Implementazione delle sei fasi

1. Colonne `observer`, `output_device`, `input_device`, `lifecycle` sulle metriche;
   contesto identico nei metadati. Creazioni osservate delimitano il ciclo; `unknown`
   resta esplicito. Nessun SSRC inventato. Scope aggiornato a ogni Device name.
2. `vd.silence_played`, `vd.underruns`, durata corrente e stati distinti;
   `derived.silence_played_delta` nei grafici. Intervalli con reset/invalidità,
   conflitti o distanza >30 s non producono delta. Confronto senza somma in
   `a_counter_incident_matches`, con identità esatta dell’osservatore e input.
3. RTCP accetta esponenti e conserva finiti invalidi (percentuali, negativi,
   conteggi frazionari); NaN/N/A/infinito non producono zeri.
4. Campioni saltati, limiti, errori/reset, pacchetti, byte e durate dichiarate;
   µs normalizzati a ms con originali conservati; media senza unità resta raw.
5. `periodic_metadata` conserva booleani, oggetti stato/codice/timestamp,
   SN/ROC e clock RTCP. Cicli separati per fase, heartbeat distinto dai cumulativi.
   API/MCP/catalogo espongono contesto, copertura e limiti; grafici e CSV mantengono
   le dimensioni senza fondere osservatori o cicli.
6. Backup consistente `.pre-v11.bak` prima della migrazione, ledger
   `periodic_evidence` e marker per importazione `periodic-1:<id>`. Il recupero
   adotta le metriche preesistenti conservando ID/valori e integra soltanto ciò
   che manca. Il ledger rende idempotente anche la riesecuzione senza marker.
   Il vecchio marker `vd-1` resta invariato. Tutto avviene dagli eventi, senza ZIP.

### Backup e ritorno alla versione precedente

Prima dell’avvio aggiornato esportare il database. La migrazione crea anche
`/data/kpe.sqlite3.pre-v11.bak` per database con importazioni: un file omonimo
esistente interrompe l’upgrade e non viene sovrascritto. Servono spazio per una
copia completa e per gli indici/osservazioni aggiunti. Lo schema viene migrato
in transazione; recupero e marker sono atomici. Se il recupero fallisce, l’avvio
successivo riprende senza duplicazioni. Non avviare il vecchio codice sullo
schema 11: per rollback arrestare il servizio e usare una copia del backup in
un volume nuovo, conservando il database aggiornato. Annotazioni successive
al backup non sono nel backup.

Le ricette analytics-1 restano leggibili; il risultato espone analytics-2 e
la selezione viene rivalutata sui dati correnti. Riconnettere il client MCP
per rileggere istruzioni e catalogo dopo l’aggiornamento.

Le somme diagnostiche A+B vengono omesse se uno dei lati ha più osservatori/cicli candidati: nessuna scelta implicita di una serie.

### Validazione eseguita

Test sintetici includono tutte le etichette numeriche VD censite, famiglie di
stati, heartbeat/monitor, cinque nuovi contatori RTCP, esponenti/non finiti,
più osservatori/input, rotazioni, righe ripetute, cicli, reset/conflitti/gap,
finestre manuali, confronto episodi e protezioni SQL/MCP. Upgrade provato su
una copia SQLite coerente del database locale, confrontando ID, valori originali
e annotazioni; il secondo avvio non aggiunge osservazioni. Gli allegati del
collaudo completo sono locali in `data/analysis/`, esclusi da Git.
