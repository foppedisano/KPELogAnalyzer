# Checkpoint — 5 ottobre 2026 · Switch Network e log per famiglia

Leggere AGENTS.md, [installazione](getting-started.md), [Switch Network](network-switches.md)
e [log della chiamata](call-events.md). Il precedente checkpoint MCP resta storico.

## Implementazione

- Switch Network: marker KPE espliciti, transizioni contestuali dichiarate,
  evidenze, eventi/timeline/grafici/mappe. Posizioni osservate o interpolate con
  estremi; nessuna inferenza EDGE/LTE dalla sola interfaccia cellular.
- MCP 1.4.0, 13 strumenti, incluso `analytics_network_switches`.
- Elenco chiamata con famiglie generiche, sfondi distinti, visibilità e modalità
  call/intervallo indipendenti. Default visibile e solo attribuito alla chiamata.
- Parser 1.12.1: una linea riutilizzata non estende una sessione già terminata.
  Finestre locali storiche delimitate in lettura nell'elenco e nelle timeline/
  attribuzioni Switch. Nessuna riscrittura dell'archivio o riparazione completa
  delle derivazioni storiche: il limite è documentato nella guida.
- Modelli PQ/MOS e precedenza celle dirette invariati; nessun cambio schema.

## Verifiche

231 test Python superati in locale e in Docker Python 3.12; 9 test JavaScript
superati. Dopo l'ottimizzazione delle query, ripetuti con successo gli 11 test
mirati di elenchi e Switch Network. Sintassi JS verificata.
Browser su archivio sintetico separato: upload, dettaglio, raggruppamento rotazioni,
modalità miste, contesto, testo HTML escapato e palette compatibile con CSP.
Test Switch precedenti: 228 Python in locale/Docker, marker nelle mappe, confronto,
diagnostica, import e persistenza dopo restart in un container isolato.

## Dati e pubblicazione

Il servizio principale è aggiornato, health positivo (parser 1.12.1) su
`http://127.0.0.1:8080/`, volume Compose esistente. Verificati API famiglie, modalità
miste e limite corretto per una sessione locale storica. Smoke Docker isolato:
import sintetici iOS/Android, deduplicazione e persistenza dopo restart positivi.
Backup locale pre-Switch `pre-network-switch-20261005-130148.sqlite3` conservato,
`quick_check` verificato positivo. Nessuna migrazione o reimportazione personale.
Non importare fixture sull'archivio personale. I file `test-results/` sono ignorati.
Commit/push richiesti in precedenza sono stati sospesi dal proprietario; non sono
stati eseguiti. Il TODO resta in [todo.md](todo.md); non avviare altre evoluzioni.


## Indicatore di caricamento

Aggiunto indicatore condiviso alle richieste API e al caricamento della base
cartografica, con conteggio delle richieste concorrenti, cleanup anche su errore,
aria-busy e rispetto di prefers-reduced-motion. Upload: barre esistenti conservate.

6 ottobre 2026: indicatore verificato nel browser con richieste rallentate su
fixture sintetica, visibile durante attesa e nascosto alla fine, console senza
errori. 231 test Python passati, controlli sintattici JS positivi. Servizio locale
ricostruito e health verificato; nessuna modifica ai dati personali.


6 ottobre 2026: corretti i dettagli dei tentativi bloccati. Riferimento stabile
«Tentativo #ID evento» visibile e ricercabile; palette per famiglia estesa agli
eventi generici e al contesto del tentativo. Nessun ID o dato personale riscritto.
Verifica browser su tentativo sintetico: import, ricerca ID, dettaglio, provenienza
e colori App/VDKLog, console senza errori.

Correzione tentativi attivata su localhost:8080: health positivo, 231 test passati.
Commit e push restano sospesi.

6 ottobre 2026: controlli log compattati. Checkbox di visibilita e checkbox Tutto
affiancate; criteri temporali espandibili. Verificati in browser default, cambio
ambito e conservazione delle scelte nascondendo/riattivando una famiglia, console
pulita. Guida aggiornata; servizio locale ricostruito e health positivo.

6 ottobre 2026: controlli compatti uniformati anche ai tentativi. Default limitato
a richiesta e prova esplicita del blocco; Tutto include il contesto per famiglia
da -5 a +10 secondi nella stessa sorgente. API /api/attempt-events in sola
lettura, senza nuove associazioni SIP. 232 test passati, sintassi JS positiva,
browser sintetico verificato (contesto, visibilità e conservazione delle scelte),
console pulita. Servizio http://127.0.0.1:8080 ricostruito, health positivo;
verificato il tentativo #4840333 con le due prove attese e 18 famiglie disponibili.
Nessuna modifica ai dati personali. Commit e push restano sospesi.

6 ottobre 2026: contesto dei log dei tentativi orientato agli antecedenti: da
60 secondi prima della richiesta fino al timestamp della prova esplicita del
blocco inclusa, oppure alla richiesta se la prova manca. Nessun evento successivo
alla fine della finestra; intervalli delle sessioni SIP invariati. Guide e API
aggiornate. Verificati fallback senza blocco, blocco successivo alla richiesta,
esclusione degli eventi successivi e paginazione su fixture sintetiche.
Servizio locale ricostruito e health positivo; verifica API sul tentativo #4840333.
Nessuna modifica ai dati personali; commit/push restano sospesi.
