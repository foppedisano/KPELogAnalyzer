# Checkpoint — 4 ottobre 2026

Stato consolidato di codice e documentazione. Schema SQLite **12**; nessuna
nuova migrazione distruttiva. Python standard library, SQLite e frontend senza
dipendenze di rete obbligatorie. Pubblicazione senza licenza concessa.

## Funzioni incluse

- Perceptual Quality (`awt-occupancy-4`): occupazione degli underrun AWT su
  finestre di un secondo; estremi ritagliati e normalizzati sulla parte attiva.
  Durante la chiamata l’assenza di underrun registrati vale 100, assumendo il
  logging completo. Episodi aperti fino a termine/ricreazione; chiamate senza
  chiusura limitate all’ultima evidenza attribuita nella stessa sorgente.
- Mappa PQ e pannello **Percorso e qualità** della singola chiamata: celle da
  50 m per default nel dettaglio, selezione sorgente, posizioni in ordine,
  prove al clic e motivi delle esclusioni. Nessuna interpolazione di qualità.
- Posizioni da configurazioni locali X-Location: backfill additivo
  `ios-location-config-1`, deduplicazione delle copie entro un secondo,
  mantenimento degli aggiornamenti successivi anche a coordinate invariate.
- Analisi transitori e contatori: viste di confronto temporale, denominatori,
  prime osservazioni e copertura, API/MCP e inventario in sola lettura.
  Coincidenze temporali non interpretate come cause.
- Episodi audio separati per osservatore/input e lifecycle; riepilogo per
  chiamata; catalogo, unità e contesti dei grafici aggiornati.
- Registro chiamate: risoluzione condivisa delle prospettive e controllo rapido
  della telemetria vuota, evitando scansioni ripetute delle metriche legacy.

## Guide e contratto

- [PQ, percorso e aggiornamenti iOS](perceptual-quality.md)
- [Transitori](transients.md), [analisi e MCP](analytics.md)
- [API](api.md), [architettura](architecture.md), [catalogo](metrics.md)
- [Verifiche](validation.md), [limiti aperti](open-issues.md)

## Aggiornamento e recupero

1. Creare un backup SQLite consistente (Esporta database o API sqlite backup).
2. Eseguire `docker compose up --build -d`, mantenendo volume e binding loopback.
3. Attendere `/api/health`: all’avvio il backfill esamina tutti gli import.
4. Verificare il percorso di una chiamata con posizioni periodiche e il filtro
   **Includi posizioni SIP e aggiornamenti iOS** nella mappa PQ.

Il backfill conserva gli ID esistenti, gli eventi e le annotazioni; i marker
impediscono reinserimenti ai riavvii. Nessuna reimportazione ZIP richiesta.
Per rollback usare il backup in una nuova cartella/volume, mai sovrascrivere
un database aperto. Backup, log, ZIP e risultati su dati reali rimangono locali
ed esclusi dal repository.

## Verifiche e limiti

Suite completa: **210 test Python** superati. Verifiche browser su caricamento
ZIP sintetici in istanza isolata, dettaglio chiamata, cambio sorgente, metriche,
confronto e percorso aggiornato; controlli sintattici JavaScript e scale.
Backfill eseguito sull’intero archivio locale: confronto con backup senza
modifiche ai record geografici precedenti, chiamate, prospettive e annotazioni.

Le configurazioni X-Location sono dichiarazioni locali, non certificazioni
dell’età del fix. Alimentano PQ/percorso; il MOS geografico persistito mantiene
le fonti precedenti. I collegamenti visuali si interrompono oltre 30 s e non
ricostruiscono il tragitto reale. PQ non è un MOS percettivo validato. Ambiguità
fra chiamate, lettori o posizioni restano esplicite.

## Aggiornamento: tentativi utente e connettività

- Registro esteso alle richieste esplicite dell’utente, anche prima del SIP,
  con ragione osservata e riferimenti alle evidenze. Le copie identiche fra
  export della stessa sorgente sono deduplicate nella visualizzazione.
- Richieste e sessioni restano distinte senza una correlazione certa: non sono
  un conteggio di chiamate uniche. La pagina mostra chiamate ricostruite,
  tentativi elencati e totale voci, coerente con il badge laterale.
- Vista Rete e servizi e bande nei grafici, con livelli separati per dispositivo,
  STUN, CTI, SIP, media e applicazione. Interrogazione al secondo e provenienza
  evento/file/riga. Verde UP, giallo transiente, rosso DOWN, grigio sconosciuto.
- Le osservazioni scadono dopo 30 secondi. Un servizio raggiungibile non prova
  che tutti gli altri funzionino; un rifiuto SIP prova raggiungibilità, non
  assenza di problemi applicativi. Nessuna causalità di rete inventata.
- Schema 12: tabelle additive, backup automatico consistente pre-v12,
  arricchimento storico idempotente `connectivity-2`; ID e annotazioni preservati.
  Istruzioni e limiti in [Tentativi e connettività](connectivity.md).

Verifiche finali: 210 test Python superati, sintassi JavaScript e diff verificati;
importazione sintetica, dettaglio, metriche, confronto, diagnostica e MOS nel
browser. Persistenza del contenitore sintetico confermata dopo riavvio.
Applicazione locale verificata su http://127.0.0.1:8080/ con health positivo;
contenitore di collaudo arrestato. Database e backup restano esclusi da Git.

Nota operativa: Docker Desktop ha incontrato socket temporanei inaccessibili
all’avvio (`dockerInference` e `engine.sock`). Le sole cartelle runtime sono
state conservate con un nuovo nome e ricreate, senza reset o modifiche ai volumi.
Il servizio è ripartito ed è stato verificato healthy. Non è una correzione
permanente di Docker; in caso di ricorrenza verificare prima i suoi log.
