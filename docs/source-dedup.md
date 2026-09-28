# Identità della sorgente e chiamate ripetute

La chiave delle chiamate globali rimane il **SIP Call-ID esatto**. Per decidere
se una chiamata tradizionale è già stata importata usiamo anche l'identità del
produttore: app e gateway devono conservare prospettive distinte.

## Regola per i log tradizionali

Il metodo `source-identity-1` richiede contemporaneamente:

1. Un `+sip.instance` UUID non nullo nel **Contact di un REGISTER uscente**,
   dentro `sip_debug*`. Sono riconosciuti `urn:uid:` e `urn:uuid:`.
   Risposte SIP, messaggi entranti, altri header e corpo non sono prove.
2. Il `device ID` della riga locale `Sending auth to CTIServer` in `ctilib*`,
   con piattaforma iOS o Android coerente.
3. Un marker di piattaforma nell'archivio: `ios_hwwrapper.log` oppure file
   `kpe-android*`.

Tutti gli identificativi osservati devono concordare. L'impronta SHA-256 combina
namespace app, piattaforma e i due identificativi; l'interfaccia mostra una
versione abbreviata, ma il confronto usa tutti i 256 bit. Nome dello ZIP,
etichetta modificabile, account, numero telefonico, IP e modello del telefono
non partecipano alla chiave. Le credenziali CTI non vengono usate né riportate
nei metadati dell'identità.

Ogni prova conserva evento, file e riga normalizzata. È un'identificazione
operativa dell'installazione, non una garanzia hardware: reinstallazioni o
cambiamenti degli identificativi possono produrre una nuova sorgente.

## Decisione durante l'importazione

- ZIP identico: il controllo SHA-256 esistente evita l'intera reimportazione.
- Call-ID già presente **dallo stesso produttore riconosciuto**: prevale la
  prima importazione; la chiamata viene ignorata anche se il nuovo export
  potrebbe essere più completo. Non si crea un'altra prospettiva e non vengono
  reinseriti eventi e metriche attribuiti con certezza a quella chiamata.
- Stesso Call-ID da un'altra app o da un GW: la prospettiva viene conservata.
- Identità assente, multipla, malformata o ruolo esplicito discordante:
  nessuno scarto automatico. Le chiamate senza Call-ID non sono deduplicate
  mediante coincidenze temporali o di linea.

Il rilevamento legacy è validato sui formati iOS/Android osservati. Non esiste
ancora una regola validata per identificare i GW legacy: questi import vengono
conservati. Anche `xcoder` o `unknown` esplicitamente annotati disattivano la
deduplicazione app per l'import interessato.

Le finestre di linea servono soltanto ad attribuire i record alla chiamata già
identificata. Record ambigui o globali restano disponibili; un blocco VD con più
device mantiene l'evidenza condivisa e le metriche delle altre linee. Per questo
un archivio con tutte le chiamate ignorate può comunque aggiungere eventi globali
e osservazioni non attribuibili. `files.records` conta i record letti;
`imports.event_count` conta quelli effettivamente conservati.

La **telemetria strutturata** mantiene il proprio contratto più preciso:
`source_id/event_id`, verifica dei conflitti e conservazione delle copie come
evidenze. Il suo `source_id` con ruolo è mostrato come identità, ma non si salta
un'intera chiamata aggirando quei controlli. I due formati non sono deduplicati
tra loro senza una corrispondenza esplicita.

## Copie storiche e interfaccia

L'aggiornamento riconosce le prospettive tradizionali già ripetute e le collega
alla prima dello stesso produttore/Call-ID. Non cancella eventi, metriche, ID
o annotazioni già presenti. Nel grafico della chiamata e del confronto queste
copie sono escluse per default; **Mostra copie storiche della stessa sorgente**
le rende nuovamente visibili, anche nell'esportazione CSV selezionata.
Flussi e SSRC diversi restano serie diverse.

Il riepilogo MOS del registro usa la prospettiva più recente fra quelle non
riconosciute come copie. Le altre viste di evidenza, SQL, analisi salvate e
selezioni esplicite in Diagnostica/MOS continuano a permettere l'ispezione delle
prospettive storiche. I conteggi grezzi delle prospettive/metriche del registro
continuano a includerle; non rappresentano nuovi campioni indipendenti.
La mappa mantiene le proprie regole di deduplicazione geografica.

In **Sorgenti e copertura** compaiono impronta, criterio, chiamate ignorate nel
nuovo import e copie storiche riconosciute. Chiamate distinte/nuove/già presenti
descrivono le prospettive conservate: gli scarti sono contati separatamente.

## Schema 9 e API

La migrazione 8→9 aggiunge `import_producers`, `duplicate_perspectives`,
`import_call_skips` e la vista `effective_duplicates`. I ruoli manuali
discordanti disattivano dinamicamente i collegamenti storici interessati.
Il backfill delle identità è idempotente e non modifica i dati grezzi.

Prima dell'aggiornamento esportare il DB e conservarlo localmente. Su un DB
popolato viene creato anche `<database>.pre-v9.bak`; non viene sovrascritto.
Serve spazio per una copia completa. Per rollback usare il backup con il codice
precedente in una cartella/volume separato, senza sovrascrivere il DB aperto.

- `/api/imports`: campo `producer` con stato, impronta abbreviata, criterio,
  evidenze e conteggi `skipped_calls` / `historical_duplicates`.
- `/api/perspectives`: `duplicate_of`, ID della prospettiva canonica o `null`.
- `/api/metrics`: `duplicates=1` include anche le copie storiche; vale per JSON
  e CSV. Senza parametro vengono escluse.
- Risultato import: `skipped_calls` e `skipped_events` per un nuovo archivio.

I test sintetici coprono produttori distinti, identità incomplete/remote,
finestre riutilizzate, blocchi condivisi, rollback, filtri API e migrazione.
