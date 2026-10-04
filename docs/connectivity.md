# Tentativi utente e rete/servizi

Il registro mostra sessioni SIP e richieste utente come categorie distinte.
I filtri **Tentativi bloccati**, **Richieste utente** e **Sessioni SIP** permettono
di distinguere le voci. Non sommare le righe come chiamate uniche: un tentativo
accettato può comparire sia come richiesta utente sia come sessione SIP.

Le richieste sono estratte dai messaggi espliciti `Calling number:` di App.log.
Il successivo messaggio di KPE non pronto viene associato soltanto se è il record
immediatamente seguente nello stesso file, entro un secondo. Senza tale richiesta
il blocco resta visibile come tentativo con destinatario non disponibile. Eventi
interposti, input troncato e tentativi ravvicinati non vengono uniti arbitrariamente.
Azioni mai registrate nei log e formati non riconosciuti non sono ricostruibili.
Le copie con testo originale identico (timestamp incluso) sono raggruppate solo
fra export con lo stesso produttore riconosciuto senza conflitti di ruolo. Le
ricorrenze ripetute nello stesso export restano distinte. È mostrata la copia più
recente con il numero di copie; tutte le prove originali rimangono nel database.

Non si generano Call-ID SIP artificiali e non si uniscono chiamate per numero o
prossimità temporale. Gli ID negativi dell'API del registro identificano richieste
utente (`-event_id`), non chiamate nel database. I rifiuti delle sessioni SIP sono
associati mediante il Call-ID esatto della risposta; `403` prova una risposta del
servizio, non rete down. `401`/`407` non sono etichettati come fallimento definitivo.
L'assenza di un rifiuto esplicito non determina automaticamente la causa.

## Lettura delle fasce

La pagina **Rete e servizi** funziona anche fuori chiamata: scegliere sorgente e
periodo (massimo 24 ore). Il dettaglio del tentativo mostra un minuto prima e due
dopo. Dettaglio chiamata/confronto e Diagnostica A/B colorano lo sfondo delle curve;
MOS e ricezione include la timeline separata. Nessuno stato è mediato fra dispositivi.

- Verde: risposta osservata (probe STUN, CTI oppure SIP).
- Giallo scuro: transiente, discordanza o disponibilità parziale.
- Giallo chiaro: sola interfaccia disponibile, non verifica di Internet.
- Rosso: indisponibilità riportata dal dispositivo/probe o dal singolo servizio.
- Grigio: dati insufficienti o controllo arrestato.

Sette fasce separano sintesi rete, dispositivo, STUN, CTI, SIP, ricezione media e stato dell'app/KPE.
La sintesi è UP se un percorso risponde; non garantisce il funzionamento degli altri.
È DOWN se dispositivo/probe riportano indisponibilità senza risposte recenti
contrarie. Risposte e indisponibilità contemporaneamente valide danno transiente.
Il solo errore CTI/SIP non rende DOWN l'intera rete. L'interfaccia disponibile non
basta per dichiarare UP. Un rifiuto SIP resta verde sulla raggiungibilità e riporta
il codice di rifiuto nella reason.

Ogni evidenza è valida al massimo **30 secondi**, salvo una nuova osservazione che
la sostituisce. È una politica conservativa dell'analizzatore, non una frequenza
garantita del dispositivo. Non si prolunga UP per tutta la call, né DOWN all'infinito.
STUN stop cancella subito lo stato STUN precedente. Se i log contengono soltanto
cambi di stato, possono restare intervalli grigi: non significa rete guasta.
I segmenti conservano i confini precisi (anche subsecondo); il cursore permette
di interrogare ogni secondo e mostra evento, file, riga e orario delle evidenze.
Nel confronto, gli offset correggono solo il disegno; in Diagnostica si applicano
gli offset della specifica analisi. Gli orari archiviati rimangono invariati.

## API e dati

- `GET /api/calls?attempts=1`: sessioni e richieste, tipo, reason ed evidenze.
  Senza il parametro conserva il registro delle sole sessioni. Limite 2.000 per tipo.
- `GET /api/connectivity?calls=1,2`: finestre per prospettiva non duplicata.
- `GET /api/connectivity?import=1&start=...&end=...`: intervalli originali della sorgente.
  Massimo 50.000 osservazioni/24 ore per richiesta; restringere in caso di errore.
- `GET /api/events?import=1&start=...&end=...`: esplorazione dei log nel periodo.

`connectivity_events` e `user_attempts` conservano riferimenti agli eventi originali.
L'arricchimento è atomico per importazione e idempotente; eseguito anche sui vecchi
export al primo avvio. Non modifica le associazioni, gli ID o le annotazioni esistenti.

## Aggiornamento allo schema 12

Esportare una copia del database prima dell'aggiornamento. Con Docker ricostruire
con `docker compose up --build -d` e attendere `/api/health`: il primo avvio esegue
backup consistente automatico `kpe.sqlite3.pre-v12.bak`, migrazione e backfill.
Serve spazio per una copia completa del DB. Un backup omonimo non viene sovrascritto.
Per tornare indietro usare il backup e la versione precedente in un volume nuovo;
non sovrascrivere il database aperto e non eliminare il volume corrente.

La ricezione media usa soltanto conteggi positivi espliciti di pacchetti ricevuti
nell’intervallo RTCP; un contatore cumulativo fermo o un heartbeat audio non bastano.
La ricezione prova il percorso media, non la registrazione SIP né il login CTI.

Il riepilogo del registro distingue chiamate ricostruite, tentativi utente elencati
e totale delle voci. Il totale usa le stesse righe del badge laterale, prima dei
filtri; non rappresenta chiamate uniche.
