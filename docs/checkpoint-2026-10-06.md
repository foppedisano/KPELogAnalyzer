# Checkpoint — 6 ottobre 2026

Stato consolidato per commit e push richiesti dal proprietario. Questa richiesta
supera la precedente sospensione della pubblicazione. Nessuna ulteriore evoluzione
del modello autorizzata. Dettagli precedenti: [Switch Network](checkpoint-2026-10-05-switch-network.md).

## Funzioni completate

- Switch Network espliciti evidenziati in eventi, timeline, grafici e mappe;
  MCP 1.4.0 con strumento dedicato, provenienza e limiti documentati.
- Log per famiglia, colori di provenienza e controlli compatti di visibilità e
  ambito. Tentativi con riferimento stabile e controlli uniformati.
- Nei tentativi, Tutto include da 60 secondi prima della richiesta fino alla
  prova del blocco inclusa, oppure alla richiesta se manca la prova. Default:
  soltanto richiesta e prova. Le sessioni SIP conservano il proprio intervallo.
- Indicatore condiviso di caricamento. Parser 1.12.1: riuso linea non estende
  sessioni locali già terminate; delimitazione in lettura per archivi precedenti.

## Verifica e servizio

232 test Python passati; sintassi JavaScript verificata. Controlli browser su
fixture sintetiche per famiglie, tentativi, visibilità e contesto, console pulita.
Ultima modifica della finestra temporale verificata tramite regressioni e API.
Docker locale ricostruito, health positivo: http://127.0.0.1:8080.
Nessuna migrazione o modifica dei dati personali per queste correzioni UI/API.

Verificata anche la segnalazione di importazione apparentemente ferma: il nuovo
import risultava salvato; il servizio rispondeva. CPU elevata osservata, causa
residua non accertata. Nessuna interruzione o riavvio durante la diagnosi.

## Limiti e prossime attività

- Esportazione database attuale tramite snapshot in memoria: per archivi di
  diversi GB può richiedere RAM eccessiva. Backup su disco/streaming da valutare;
  nessuna modifica all'esportazione effettuata e nessun database esportato.
- Stato/progresso delle fasi di importazione e aggiornamento registro da valutare.
- Riparazione completa delle associazioni storiche locali ancora da concordare.
- [TODO](todo.md) raccoglie le proposte, non autorizza sviluppi automatici.

ZIP, database, log reali e screenshot locali restano esclusi dal repository.
Installazione autonoma, backup e ripristino: [guida](getting-started.md).
