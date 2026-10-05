# Perceptual Quality (AWT)

Indice operativo 0–100: **100 − percentuale del secondo occupata da underrun
AWT**. Non è un MOS o una metrica percettiva validata. Descrive la continuità
del percorso NART → AWT osservato nei log.

## Finestre e prove

Le finestre sono secondi interi dell'orologio scritto nel log, senza correzioni.
Un evento di 600 ms collocato fra `05.800` e `06.400` occupa 200 ms nel primo
secondo e 400 ms nel secondo: underrun 20% e 40%, qualità **80 e 60**.

Si ricostruisce lo stato dagli inizi e dalle fini degli episodi AWT. Con un
inizio osservato si usa il suo timestamp; se manca, la durata dichiarata
nel messaggio finale permette di ricavarlo all'indietro. Un episodio aperto
resta attivo fino a fine chiamata o ricreazione del device. Gli intervalli
sovrapposti dello stesso osservatore/input vengono uniti, non sommati.

**Si assume completo il log AWT della chiamata:** ogni secondo intero fuori
dagli episodi vale 100, ogni secondo interamente in underrun vale 0.
I contatori periodici non sono più un requisito e non vengono riconciliati.
Un 100 significa quindi assenza di underrun registrati, non completezza
verificata del logging. Non è richiesta alcuna evidenza periodica AWT o heartbeat: anche con
sola segnalazione della chiamata, in assenza di episodi il valore è 100.
La provenienza di questi campioni è la chiamata; il funzionamento AWT è
assunto, non verificato. Una linea sconosciuta non impedisce questo valore
predefinito. Eventuali underrun contemporanei non attribuibili non vengono
però ignorati: i secondi interessati restano ambigui, senza collegare chiamate
per sola coincidenza temporale. Le finestre ai bordi sono ritagliate sulla parte attiva della chiamata: la percentuale usa la durata effettiva come denominatore. Ad esempio, 200 ms di underrun su 500 ms di chiamata danno PQ 60; senza underrun danno 100.

La derivazione `awt-occupancy-4` è calcolata su richiesta, senza migrazione o
reimportazione. Ogni campione conserva eventi, metriche, file e righe di prova.
Limite 100.000 campioni. Senza fine registrata si usa l’ultimo evento attribuito alla stessa chiamata nella stessa sorgente (incluso con precisione di 1 µs), mai l’ora attuale o la fine di tutto l’archivio. La risposta espone `end_basis=last_call_evidence`.

## Mappa e movimento

La mappa parte da Perceptual Quality; MOS resta selezionabile. PQ usa soltanto
AWT locale di prospettive app (o non annotate), senza upstream dedotto da RTCP.
Le posizioni ammesse sono nuovi aggiornamenti locali oppure anche dichiarazioni
SIP locali, secondo il filtro. Cached e remote non sostengono campioni PQ.
La telemetria strutturata non è ancora una fonte di questa metrica AWT legacy.

Si prende solo il secondo che **contiene il timestamp della posizione** nella
stessa sorgente e in una chiamata attiva univoca. Nessun mantenimento della
posizione per 120 s per i dati diretti. Le celle stimate sono un livello separato, descritto sotto. Messaggi ripetuti
nella stessa cella/secondo/prospettiva contano una volta; più celle nello stesso
secondo o più lettori/input valutabili sono ambigui e vengono esclusi.
Le prospettive marcate duplicate sono escluse.

Ogni secondo distinto pesa uno nella media. A piedi si possono avere più
campioni, in treno meno: numero di campioni e giorni esprimono questa differenza
senza correggere arbitrariamente la qualità per velocità. La media riguarda
**i secondi campionati alle posizioni**, non tutta la permanenza nella zona.
La frequenza dei messaggi può influenzare il campionamento. La scala cromatica
continua 0–100 non introduce soglie percettive validate.

Quando disponibile si mostra la velocità media stimata fra fix dal modulo
mobilità, senza dedurre il mezzo di trasporto. Se lo spostamento stimato in 1 s
supera il lato della cella, viene segnalato. A 300 km/h si percorrono circa
83 m/s: una cella da 50 m non localizza precisamente tutto il secondo.
Accuratezza GPS e ritardo del messaggio restano limiti; le coordinate SIP hanno
età reale ignota anche usando il campione contemporaneo al messaggio.

## Accesso

MCP 1.3.0 espone gli stessi calcoli tramite `analytics_perceptual_quality`,
`analytics_geo_cells` con `metric=perceptual` e `analytics_call_route`.
Il catalogo riporta esplicitamente l'assunzione di logging AWT completo e la
precedenza dei dati diretti. [Parametri, evidenze e limiti MCP](analytics.md).

- Chiamata e Confronta → Aggiungi metriche → **Perceptual Quality**, anche CSV.
- `/api/metrics?calls=1&name=derived.perceptual_quality`.
- `/api/geography?metric=perceptual&cell=50&quality=fresh`.
- `quality=declared` include le dichiarazioni SIP locali.

L'API geografica include `exclusions` (conteggi di messaggi, non celle) e fino
a 20 campioni di prova per cella, con indicatore di troncamento. Il clic sulla
cella PQ mostra il dettaglio aggregato; i profili temporali MOS non vengono
riutilizzati per descrivere una metrica diversa.


## Percorso della singola chiamata

Nel dettaglio chiamata, sotto il grafico, **Percorso e qualità** mostra una sola
prospettiva app per volta, selezionabile in **Device / sorgente**. Celle da 50 m
per default, scala modificabile, zoom, trascinamento, inquadratura e strade OSM
opzionali riusano la mappa generale. Nessun caricamento remoto automatico.

Il percorso collega cronologicamente le posizioni locali non cached; le linee
sono indicative, con frecce, e si interrompono oltre 120 s o su estremi simultanei con coordinate discordanti. Inizio/fine indicano
il primo e ultimo messaggio non cached, non necessariamente gli estremi fisici
del viaggio. Coordinate cached restano visibili con cerchio vuoto e motivo,
ma non prolungano il percorso. Nessuno snapping a strade o ferrovie.

Il percorso aggiunge un punto piccolo al centro di ogni secondo intero compreso
fra due posizioni, interpolando linearmente le coordinate nel tempo (velocità
costante). Fra 12:01:00 e 12:02:00 compaiono 60 punti. La qualità di ciascuno
viene ricalcolata dagli episodi AWT di quel secondo, **non interpolata dai
valori agli estremi**. Secondi ambigui restano grigi; non si estrapola fuori
dagli estremi o dalla chiamata connessa. Le frazioni di secondo agli estremi
non producono punti intermedi. Coordinate SIP possono essere datate: il
percorso è una stima, non un viaggio verificato. Nessuna richiesta di rete.

Media pesata sulla durata e minimo del tratto sono separati dalle statistiche
puntuali e dalle celle, che continuano a usare soltanto posizioni registrate.
I punti intermedi espongono prove di entrambi gli estremi e della qualità AWT.
Non vengono salvati nel database né sommati alle celle aggregate.
Un 100 mantiene l'assunzione di completezza del logging descritta sopra.
L'API aggiunge `interpolation` con `points`, `links`, `mean`, `minimum`,
`evaluated_seconds` e `max_gap_seconds`; limite di 100.000 punti intermedi.

Ogni punto conserva qualità, durata osservata, underrun in ms e prove file:riga.
Il selettore dei punti permette di consultare separatamente messaggi ripetuti
nello stesso luogo. Le celle fanno la media di finestre distinte nella cella,
non di messaggi duplicati. Le posizioni senza valore espongono il motivo.
Posizioni senza Call-ID richiedono una finestra univoca nella stessa sorgente;
quelle con Call-ID diverso, remote e prospettive duplicate sono escluse.

API: `/api/call-route?call=1&perspective=1&cell=50` (`perspective` facoltativa).
Limite 10.000 posizioni per chiamata/sorgente; risposta con `sources`, `points`,
`cells`, `locations`, prove e segmenti. Sorgenti diverse non vengono unite.


## Aggiornamenti periodici iOS degli header

Il marker `ios-location-config-1:<import>` aggiunge, anche agli archivi storici,
le coordinate nei messaggi KPE/CORE `Adding extra headers to sip messages:`.
Si decodifica soltanto il JSON `extraHeaders` e la voce `X-Location`: configurare
un header non equivale a trasmettere SIP né a ottenere un nuovo fix GPS.
Questi punti hanno tipo `sip_config`, visibile nel dettaglio, e sono inclusi
nella mappa PQ con il filtro dichiarazioni locali e nel percorso chiamata.
I messaggi generici `New location received` senza coordinate non creano punti.

Le copie con coordinate e Call-ID uguali nello stesso import, entro un secondo
ancorato alla prima copia, contano una volta. Aggiornamenti successivi, anche
con coordinate identiche, restano distinti. La prova conservata è il primo
evento, con file e riga; tutte le copie restano negli eventi originali.
Conflitti di coordinate e sovrapposizioni ambigue di chiamate non vengono risolti
arbitrariamente. Non si fondono import o identità di chiamata.

Il backfill è additivo e atomico, senza cambio schema o eliminazione dei marker
precedenti; il riavvio ripetuto non aggiunge duplicati. Prima di applicarlo a
un archivio esistente creare un backup SQLite consistente. In questa revisione
le nuove posizioni alimentano PQ e percorso; le derivazioni MOS persistite
mantengono le precedenti fonti e il precedente metodo.


## Zone sulla Mappa qualità generale

Con Perceptual Quality la vista generale mostra celle, senza sovrapporre
linee o puntini. **Mostra zone stimate** è attivo di default e si può disattivare.

- **Dato diretto**: colore pieno. Qualità associata al secondo di una posizione
  registrata; le dichiarazioni SIP ammesse mantengono il limite di età ignota.
- **Zona stimata**: colore trasparente, bordo e riempimento tratteggiati. Compare
  solo se manca un dato diretto valutabile nella cella, nei filtri selezionati.
- **Dati insufficienti**: nessuna qualità attribuita. Posizioni note senza un
  valore valutabile restano grigie; zone mai osservate o attraversate restano vuote.

La qualità AWT di ogni secondo viene localizzata tramite la posizione stimata
al centro di quel secondo. Si aggregano esclusivamente i secondi valutabili,
con media pesata sulla durata, senza propagare valori alle celle vicine.
Se nella stessa cella esiste anche un solo dato diretto valutabile, ha precedenza:
la sua media e il colore non incorporano stime. Queste restano nel dettaglio,
marcate come escluse dal colore. La media generale e i secondi campionati nel
riepilogo restano riferiti ai soli dati diretti; i conteggi delle zone sono separati.

Il dettaglio mostra media, minimo/massimo, secondi interessati da underrun,
durata complessiva degli underrun, secondi campionati, giorni e passaggi.
“Secondi interessati” è la durata delle finestre con almeno un underrun, non
la sola durata del disturbo. I passaggi sono sequenze nella stessa cella e
prospettiva: secondi consecutivi nelle stime, osservazioni distanti al massimo
120 s nei dati diretti. Non sono viaggi indipendenti verificati. Per le stime
sono riportati anche divario minimo/massimo fra estremi e prove di posizioni
e qualità (prime 20 finestre per cella, troncamento esplicito).

Periodo, tipo di posizione e filtri rete si applicano anche alle stime.
Posizioni escluse interrompono il collegamento; un cambiamento di contesto
non compatibile con i filtri nell'intervallo esclude il tratto. Servono almeno
due posizioni ammesse nella stessa chiamata/sorgente entro 120 s. Non si usano
cache, sorgenti duplicate, secondi ambigui o posizioni fuori dal periodo.
La posizione è interpolata linearmente, non adattata a strade o ferrovie.

L'API `/api/geography?metric=perceptual` restituisce `cells` con `origin`
(`direct` o `estimated`), `direct_cells`, `estimated_cells` e `estimation_method`.
Una cella diretta può avere `estimate`, riepilogo separato delle stime ignorate
per il colore. I campioni intermedi non sono più inviati come `routes`:
`route_samples` ne indica il conteggio prima dell'aggregazione e delle esclusioni
AWT. Limiti: 100.000 campioni intermedi e 10.000 celle. Nessun cambio schema.
Il percorso della singola chiamata conserva invece linee, puntini e API precedenti.
