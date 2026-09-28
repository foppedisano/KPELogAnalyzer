# Inventario recente e piano di implementazione

## Stato del lavoro

Inventario completato, implementazione dei campi mancanti **ancora da iniziare**.
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

## Risultati e limiti

- VD: 61 etichette distinte, di cui 52 con dati/stati e 9 intestazioni o
  segnaposto. Alcune righe contengono più valori: non sono 52 metriche scalari.
- Soltanto tre etichette periodiche VD vengono estratte: occupazione buffer,
  silenzio saltato e limite dinamico dejitter, nelle sole sezioni NART.
- RTCP: sei campi numerici supportati, cinque contatori pacchetti mancanti,
  oltre a clock e metadati non strutturati. SSRC è già una dimensione delle metriche.
- JSON KPE: otto famiglie osservate, incoming/outgoing e last/avg/min/max;
  tutti i percorsi numerici finiti osservati sono supportati. N/A non diventa zero.
- Heartbeat VD e monitor NART/NAWT contengono byte, cicli, stati e timestamp
  che oggi non vengono estratti come dati strutturati.
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
- app/parser.py: statistiche JSON KPE e RTCP; parser corrente 1.11.0.
- app/incidents.py: episodi per osservatore/input NART.
- app/analytics_incidents.py: finestre e unione intervalli, metodo incident-occupancy-1.
- app/analytics.py, app/analytics_mos.py, app/mcp_server.py: API analitiche e MCP.
- app/db.py: schema corrente 10, migrazioni con backup.
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
