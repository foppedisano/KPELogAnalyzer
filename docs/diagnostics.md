# Uso della diagnostica e aggiornamento

## Chiamata con ZIP completi

1. Importa un archivio per ciascun punto di vista. Le chiamate con lo stesso SIP Call-ID condividono l’identità; le tratte con Call-ID diversi restano distinte.
2. In **Sorgenti e copertura** controlla i periodi disponibili e imposta eventuali offset di orologio. L’offset si somma all’orario nei grafici; non modifica i log.
3. In **Diagnostica A/B** scegli la prospettiva A, facoltativamente B, e il device NART di ciascuna. Il default è NART0 of Line 0 quando disponibile. Si possono confrontare anche tratte con Call-ID differenti, assumendosene esplicitamente la selezione.
4. Controlla versioni dell’app, metriche mancanti e flow/SSRC. Una sola sorgente produce un’analisi parziale, senza somma dei buffer.
5. Nascondi serie dalla legenda, usa Ctrl + rotella o i pulsanti − / + per ingrandire; la rotella normale scorre la pagina e leggi il tooltip. Gli aggiornamenti del massimo e i delta non vengono uniti in curve continue.
6. Consulta **Momenti da verificare**, poi ricerca gli eventi o il file:riga in **Esplora log** / SQL. **Esporta analisi JSON** conserva serie, derivazioni, copertura ed evidenze; le metriche originali restano esportabili in CSV dalla vista Confronta.
7. Consulta **Guida alle metriche** o [il catalogo](metrics.md) per unità, significato e limiti.

## Soltanto VDlog e rtplog

In **File e finestre manuali**, seleziona insieme i file dello stesso dispositivo e assegna un’etichetta. Ripeti per il secondo dispositivo. Mantieni i prefissi VDlog e rtplog, perché determinano il parser. Sono supportati anche ZIP contenenti solo questi file.

Senza eventi di ciclo chiamata i campioni restano correttamente non attribuiti. Crea una finestra manuale indicando sorgente, linea, inizio e fine negli orari originali dei log. La finestra assegna soltanto osservazioni non attribuite; sovrapposizioni sulla stessa linea sono rifiutate. Il titolo è un’annotazione, non identità SIP. Non viene inventato l’istante di connessione. Ripeti per B e scegli le due prospettive nella diagnostica.

In **File e finestre manuali → Modifica una finestra manuale**, seleziona la finestra e correggi titolo, linea o orari. Gli identificativi restano invariati; i campioni fuori dalla nuova finestra tornano non attribuiti e quelli compatibili entrano nella finestra. La cronologia conserva lo stato precedente. Le chiamate ricostruite automaticamente non sono modificabili da questo modulo.

## Upgrade storico dalla versione iniziale

Questa sezione descrive il passaggio 1→2; la versione attuale arriva a schema 11
attraverso le migrazioni successive. Vedi [architettura](architecture.md) e
[aggiornamento e backup](getting-started.md#arresto-aggiornamento-e-backup).

Prima dell’aggiornamento scarica **Esporta database**, quindi esegui:

```sh
docker compose up --build -d
docker compose ps
docker compose logs --tail=50 analyzer
```

Al primo avvio lo schema 1 migra a 2. Se contiene importazioni, il sistema crea una copia SQLite consistente `kpe.sqlite3.pre-v2.bak` accanto al DB (nel volume `/data` in Docker). Se quel nome esiste già, l’aggiornamento si ferma per non sovrascriverlo: preservalo o rinominalo prima di riprovare. Servono spazio per backup e nuove metriche; un export ampio richiede qualche secondo prima che l’HTTP risponda.

La migrazione aggiunge colonne di provenienza/tipo alle metriche e `app_versions`. L’arricchimento legge gli eventi già conservati: non servono gli ZIP originali. Non cambia identificativi delle chiamate, prospettive o eventi, etichette, offset o conversazioni. Ogni importazione riceve un marker `enrichment:<id>` in `meta`; riavviare non duplica l’arricchimento. Le importazioni nuove lo eseguono nella stessa transazione dello ZIP. Le statistiche/avvisi storici di importazione descrivono l’importazione originale; per i conteggi correnti usare Panoramica o SQL.

Non usare il vecchio programma sul DB schema 2. Per tornare alla versione precedente, arresta il servizio, conserva il DB aggiornato e ripristina la copia schema 1 in una nuova cartella o volume come descritto nel README. Il backup non comprende annotazioni/importazioni successive alla migrazione.

## Esempi SQL con provenienza

```sql
SELECT m.name, m.ts, m.value, m.unit, m.device, m.raw_value, m.raw_unit,
       m.event_id, f.name AS filename, COALESCE(m.source_line,e.line_no) AS line
FROM metrics m JOIN events e ON e.id=m.event_id JOIN files f ON f.id=e.file_id
WHERE m.call_id=1 AND m.name LIKE 'vd.%'
ORDER BY m.ts;
```

I delta e le somme diagnostiche vengono calcolati al momento attraverso `/api/diagnostics`; i dati di partenza restano interrogabili in SQL. Vedi [API](api.md).


## Configurare e salvare un’analisi

La diagnostica permette di selezionare le metriche da sovrapporre, incluse perdita RTCP (%) e jitter RTCP (ms). Incoming/outgoing, flow e SSRC restano serie indipendenti. Le due somme sono denominate **Somma dei buffer A+B** (`derived.buffer_sum`, audio occupato) e **Somma dei limiti dinamici A+B** (`derived.dejitter_sum`, target); nessuna misura il ritardo end-to-end.

- Seleziona A/B, i device e gli offset di questa analisi. Gli offset iniziali provengono dalle sorgenti, ma qui modificarli non cambia la sorgente globale.
- Imposta **Inizio analisi / Fine analisi** nell’orario dopo l’offset. Campi vuoti significano copertura completa. Premi **Applica periodo e sorgenti**; **Intera chiamata** azzera il filtro. Tutte le serie e i picchi usano la stessa finestra. I dati esterni alla finestra non entrano in delta o interpolazioni.
- Seleziona le metriche con le caselle. Scegli ms/s per il silenzio cumulativo. Con due unità ci sono due assi; con tre unità vengono creati pannelli con la stessa scala temporale. Una perdita del 10% non viene mai trattata come 10 ms.
- Ogni voce della legenda permette di mostrare/nascondere la serie e cambiare colore e simbolo. A parte con cerchi e linea continua, B con quadrati e tratteggio, le somme con rombi. I WARNING restano punti isolati anche quando si cambia simbolo.
- Inserisci un titolo e premi **Salva**. **Salva come nuova** crea una configurazione distinta; **Apri** ripristina una configurazione esistente. Sono conservati prospettive, device, periodo, offset, metriche, unità, colori, simboli e visibilità. Lo zoom temporaneo non viene salvato: per un ritaglio persistente usa Inizio/Fine analisi.
- I salvataggi hanno revisione: un aggiornamento con una revisione obsoleta viene rifiutato per evitare sovrascritture involontarie. L’analisi viene ricalcolata sui dati attuali all’apertura; non è un congelamento dei campioni. Esporta JSON per una fotografia di dati ed evidenze insieme alla configurazione.

## Identità assistite

Apri **Identità delle sorgenti** e scegli l’importazione. Il sistema cerca l’account dichiarato nel From dei REGISTER uscenti; come indizio più debole usa From degli INVITE uscenti o To degli INVITE entranti. Le risposte SIP non sono interpretate come prove di identità locale. Vengono mostrati account, eventuale display name, criterio, conteggio ed eventi di evidenza. Non vengono restituiti header Authorization né il testo completo dei messaggi.

Non si presume che un account identifichi una persona. **Usa questo indizio nel modulo** prepara la proposta; soltanto **Conferma associazione e aggiorna etichetta** salva nome/account/nota/evidenze e rinomina la sorgente. In assenza di indizi puoi compilare un’associazione manuale con nota. Più candidati sono mantenuti distinti: niente selezione automatica di Rossi/Oppedisano. La ricerca è limitata a 50.000 eventi SIP e 100 candidati, con indicatore di troncamento.

## Upgrade schema 2 → 3

Il primo avvio crea `kpe.sqlite3.pre-v3.bak` nel volume dati, poi aggiunge le tabelle `saved_analyses`, `source_identities`, `window_revisions` in transazione. Un backup omonimo esistente interrompe l’upgrade: preservalo o rinominalo prima di riprovare. Chiamate, eventi, metriche, etichette, offset e conversazioni restano invariati. Il percorso 1 → 3 passa prima per la migrazione 1 → 2. Per rollback arresta il servizio e ripristina il backup in una nuova cartella/volume; i programmi vecchi non supportano lo schema 3.


## Underrun e media missing: fasce degli episodi

Sotto le curve della diagnostica sono disponibili fasce temporali con lo stesso asse X e lo stesso zoom. Arancio indica buffer underrun; rosso indica media missing. Le righe distinguono A/B e osservatore (uscita audio AWT, nome VD osservato, senza destinazione dedotta, flow RTP). Il tooltip mostra durata, stato ed eventi di prova. La tabella **Episodi di underrun e media missing** permette di consultare inizio/fine, durata e provenienza; i primi 300 episodi sono elencati, tutti sono inclusi nel JSON esportato.

- Underrun: la durata `Event was … msecs long` è riportata come **dichiarata**. Può differire dal tempo fra i messaggi di inizio e fine, che è mostrato separatamente. Se manca l’inizio ma la fine dichiara la durata, si ricava una posizione iniziale e la si etichetta come non osservata.
- `Still in buffer underrun … Event is currently …` consente di mostrare almeno la durata già trascorsa. Senza messaggio terminale l’episodio resta **senza chiusura**: la barra si ferma all’ultima evidenza, non alla fine della chiamata.
- Media missing: “più di 5 secondi” non è un istante esatto di inizio. La barra parte da `segnalazione − soglia`; se c’è una ripresa, la durata indicata con **≥** è `soglia + tempo fra segnalazione e ripresa`. È un limite inferiore stimato dalle notifiche, non una misura campione per campione. Ripresa isolata: durata non nota.
- Bordo tratteggiato: durata minima o episodio aperto. I fenomeni molto brevi hanno una larghezza visiva minima di 3 pixel per essere visibili; la durata precisa resta nel tooltip/tabella. Ingrandire per vedere la distanza temporale reale.
- Il filtro di periodo ritaglia le barre, mantenendo la durata complessiva dell’episodio ricostruito e segnalando il ritaglio. La ricostruzione usa il ciclo completo della prospettiva, per non perdere inizi precedenti al periodo selezionato. Gli offset A/B si applicano anche alle fasce.
- Contatori di underrun, stati periodici e `mutedReasons` finali non identificano singoli episodi con durata, quindi non vengono duplicati nelle fasce. La semplice notifica di coda `media_missing` senza linea/flow non viene attribuita per supposizione.
- Non sommare underrun di AWT e VD o underrun e media missing sovrapposti come durate indipendenti di audio perso. Il device selezionato filtra l’underrun di ricezione NART; non comprende automaticamente l’underrun di Default Audio Input verso NAWT.

Non serve reimportare gli ZIP né migrare lo schema: gli episodi sono ricostruiti su richiesta dagli eventi già nel DB. Per una prospettiva senza linea nota non si inventano associazioni.

## Calcoli nel grafico della singola chiamata

Il pannello **Aggiungi metriche** della chiamata e di Confronta comprende tutte le metriche
singole documentate, anche senza campioni. Le metriche calcolate sono generate
su richiesta, senza migrazione o reimportazione:

- `derived.silence_delta`: differenza tra campioni validi consecutivi in ms,
  separati per prospettiva, device, flow, SSRC e direzione. Primo campione,
  reset e intervallo oltre 30 s non producono punti. Le rotazioni di file non
  interrompono il calcolo; fonti diverse non vengono mescolate. Il punto è al
  timestamp del secondo campione ed è isolato, non una curva continua.
- `incident.buffer_underrun` e `incident.media_missing`: durata degli episodi
  come punti alla segnalazione, più tabella con stato, durata ed evidenze.
  I valori minimi restano etichettati come tali; le durate ignote restano in
  tabella e nel CSV ma non diventano punti a zero. AWT e VD restano separati.

Tooltip e CSV conservano gli eventi di origine, anche entrambi i campioni del
contatore. La selezione non garantisce che vi siano osservazioni nella chiamata:
quando mancano dati compare una spiegazione. Le metriche persistite (RTCP,
ping, VD e statistiche KPE) mantengono i propri valori e statistiche.

Le somme `derived.buffer_sum` e `derived.dejitter_sum` richiedono due prospettive
esplicitamente scelte: usare Diagnostica A/B, anche se le due prospettive sono
nella stessa chiamata. Nessun secondo lato è scelto automaticamente.

Per il grafico multimetriche della chiamata, con un pannello per unità e
zoom/cursore comuni, vedi [la guida dedicata](call-chart.md). Diagnostica A/B
mantiene i suoi controlli e le configurazioni salvabili.

## Missing packets

`vd.missing_packets` è disponibile in chiamata singola, Confronta, Diagnostica A/B e App e xcoder. Mostra un punto isolato per messaggio NART con il conteggio esplicito `(N missing packets)`, asse in pacchetti separato da ms e percentuali, con tacche intere in chiamata/Confronta e Diagnostica A/B. Il tooltip/CSV conserva file e riga del messaggio con i numeri di sequenza. Non è una misura di perdita definitiva: le segnalazioni possono sovrapporsi o precedere recupero/riordino. Nessun totale di pacchetti unici persi viene dedotto.

L’aggiornamento arricchisce gli eventi già importati una sola volta (marker `missing-packets-1:<import>`), senza ricreare altre metriche o cambiare schema. I record senza finestra di linea univoca rimangono non attribuiti e interrogabili via SQL. Per xcoder si mantiene l’assunzione di formato identico alle app, ancora da validare con campioni reali.

## Upstream e downstream rispetto all’app

Il pannello Aggiungi metriche della chiamata/Confronta raggruppa le metriche in Downstream (ricezione locale dell’app), Upstream (ricezione dichiarata dal peer/GW), Bidirezionale/combinati e Interpretazione da verificare. Jitter e perdita RTCP hanno due voci distinte che filtrano anche il CSV per incoming/outgoing. Gli identificativi tecnici nel database non cambiano. RTT e ping non sono assegnati a una singola direzione. Le metriche KPE non confermate restano nel gruppo da verificare.

In Diagnostica A/B e App e xcoder, legenda e tooltip indicano chi misura; il filtro Direzione delle curve limita curve e relativo tooltip. Gli episodi audio restano visibili come contesto separato. Il filtro è temporaneo e non modifica le metriche selezionate nelle analisi salvate né il JSON completo esportato.

Una sorgente senza ruolo dichiarato è trattata come app presunta, esplicitamente segnalata nell’interfaccia e con role_basis=app_assumed nell’API. Con ruolo app confermato la classificazione è confermata. Con ruolo xcoder/unknown (o confronti misti) il menu usa Ricezione locale / Ricezione del peer, senza assegnare upstream/downstream finché non è verificato il flusso della tratta app–xcoder. Il ruolo xcoder da solo non prova la tratta: il suo incoming può essere upstream dell’app oppure arrivare da un altro nodo. Il peer RTP può essere il GW, non il telefono dell’interlocutore. Questi indicatori distinguono le condizioni delle direzioni ma non localizzano da soli il guasto nella rete d’accesso.

## MOS e ricezione

Usare la vista dedicata **MOS e ricezione**, oppure il parametro MOS a profilo
fisso in chiamata e Confronta. [Metodo e selezione esplicita del GW](mos.md).

Aggiornamento periodico schema 11: [migrazione, backup e recupero](periodic-metrics-implementation.md#backup-e-ritorno-alla-versione-precedente).

## Scheduling, RTP e device

Consultare il [media plane VDK](media-plane.md) per la gerarchia. Ogni VD opera nel proprio thread: ritardi di scheduling e cicli descrivono la temporizzazione locale. Le statistiche NART specifiche dei pacchetti descrivono invece la ricezione RTP. Underrun e silenzio riprodotto sono conseguenze sulla disponibilità del media; da soli non distinguono una causa di rete da una locale. Conservare ciascuna relazione VID/VOD: un VOD può miscelare più input.
