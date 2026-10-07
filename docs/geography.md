# Mappa qualità e archivio geografico

La metrica iniziale della mappa è ora **Perceptual Quality (AWT), 0–100**:
[finestre da un secondo, copertura e associazione puntuale](perceptual-quality.md).
MOS rimane selezionabile. Le regole di mantenimento della posizione e media
MOS descritte sotto riguardano esclusivamente il percorso MOS.

[Indice](README.md) · [Come leggere il MOS](mos.md) · [Logica della piattaforma](platform-guide.md)

## Uso e lettura dei colori

Aprire **Mappa qualità**. La metrica iniziale è **Perceptual Quality** (PQ),
mentre MOS è selezionabile. Trascinare, usare rotella o +/−; frecce e +/− sono
utilizzabili anche da tastiera. **Inquadra dati** inquadra le celle valutabili,
oppure le posizioni se non ci sono celle. Celle da 50 m a 10 km; default 250 m.

Con PQ la mappa generale privilegia le zone, senza sovrapporre tutti i percorsi:

- **Pieno: dato diretto**, associato al secondo di una posizione registrata.
- **Trasparente e tratteggiato: stima**, solo dove non c'è un dato diretto.
  **Mostra zone stimate** è attivo di default e disattivabile.
- **Grigio: dati insufficienti**, coordinate note senza qualità valutabile.
  Le zone senza elementi restano vuote; non sono automaticamente buone o cattive.

Le stime usano qualità AWT dei secondi intermedi e coordinate interpolate nel
tempo fra posizioni della stessa chiamata/sorgente entro 120 s. Non seguono
strade o ferrovie, non si estendono alle zone vicine mai attraversate e non
sostituiscono dati diretti. Il clic mostra media, minimo/massimo, disturbi,
secondi, giorni, passaggi e prove. Se una cella diretta contiene anche stime,
queste restano consultabili separatamente e non influenzano il colore.
La media generale PQ considera soltanto dati diretti; non mescola le due origini.

Per vedere **linee e puntini per secondo**, aprire una chiamata e scorrere fino
al pannello **Percorso e qualità**, scegliendo il device/sorgente. La qualità
non viene interpolata dai valori agli estremi: si ricalcola dagli eventi AWT.
[Metodo completo, copertura e limiti](perceptual-quality.md).

Con **MOS** restano valide le regole distinte sotto: downstream locale o upstream
RTCP, media pesata sul tempo, rosso <3/arancio 3–4/verde ≥4; bordo tratteggiato
per copertura inferiore a 60 s o un solo giorno. Il clic apre i profili temporali.

La time machine offre 30, 365 o 3652 giorni fino alla data scelta, intero archivio
o date personalizzate. La fine è esclusa; l'ultimo timestamp viene dall'archivio,
non dal computer. Periodo, rete e filtro posizioni si applicano anche alle stime.
Per un archivio esteso restringere il periodo se si supera il limite di calcolo.

La base Natural Earth è inclusa e funziona offline. È una cartografia di contesto
(1:50 milioni, non stradale); lo zoom non ne aumenta il dettaglio. **Strade online
OSM** è disattivato inizialmente e si attiva solo con un gesto dell'utente. Richiede
Internet e comunica a OpenStreetMap l'area dei tasselli visualizzati, mai eventi,
coordinate campione, MOS o identificativi. Il backend richiede solo i tasselli
della vista, con User-Agent identificativo, Referer, cache locale minima di sette
giorni e richieste condizionali. Nessun prefetch o download massivo. I tasselli
sono in `data/map-cache` (nel volume Docker), non nel repository. Se il servizio
non risponde, rimane visibile la base offline. Analisi e JavaScript non dipendono
da servizi o librerie esterni.

## Dati e metodo geo-mos-1

Schema 6 conserva tre tabelle:

- `geo_positions`: coordinate estratte, timestamp del messaggio, accuratezza
  Android hAcc in metri se presente, et monotono grezzo, tipo, validità,
  evento e riga. Il timestamp Android `HH:MM:SS:mmm` viene letto dal testo
  originale senza riscrivere `events.ts`. Coordinate finite fuori intervallo
  e accuratezze negative sono conservate con valid=0. I log grezzi conservano
  anche i messaggi non riconosciuti/malformati.
- `geo_mos`: intervalli posizione–MOS con lat/lon, accuratezza, perdita RTCP,
  direzione, timestamp della posizione, modello e versione di associazione.
  Nessuna retention o cancellazione automatica.
- `geo_mos_evidence`: legame separato agli input metrici e geografici. Non è
  restituito dalla mappa, ma rende ogni osservazione verificabile nel DB.

Il recupero storico parte al primo avvio; ogni ZIP successivo viene elaborato
nella stessa transazione atomica dell'import. Marker `geo-mos-1:<import>` per
idempotenza. Nessuna reimportazione richiesta. Una futura revisione del metodo
può conservare risultati nuovi e vecchi distinguendoli per versione; gli input
originali restano disponibili. Il metodo corrente non rivaluta automaticamente
le finestre manuali modificate dopo l'importazione. L'archivio è una derivazione
versionata, non un log di tutte le future modifiche dell'analista.

Si localizzano soltanto prospettive app confermate o app presunte senza ruolo;
una successiva annotazione non-app le esclude dalla mappa. Non si deducono tratte
GW da un ruolo xcoder e non si applicano selezioni temporanee del pannello MOS.

**Nuovi aggiornamenti locali** accetta solo `New location received: Location[...]`.
Le posizioni cached sono conservate ma non alimentano MOS. **Includi dichiarazioni
SIP locali** ammette anche X-Location nei veri header di messaggi esplicitamente
OUTGOING, solo per la medesima chiamata e importazione. Body, header di autenticazione,
configurazioni extraHeaders e messaggi entranti non localizzano l'app. Le coordinate
SIP entranti sono conservate come remote ma escluse anche dai punti grigi locali.
L'incertezza `u` degli URI non viene interpretata come hAcc.

Nessun utilizzo prima del messaggio di posizione; al massimo 120 secondi dopo,
spezzando al messaggio successivo. Posizioni discordanti allo stesso timestamp
interrompono l'associazione. Non si interpola un percorso. 120 s è una soglia
operativa versionata, non una misura della freschezza reale: persino una callback
può consegnare una posizione preesistente. `et` non viene trasformato in ora civile
senza un riferimento affidabile al boot. Le dichiarazioni SIP hanno età ignota.

Gli intervalli MOS sono quelli di `loss-reference-1`, con scadenza 30 s; si
intersecano con gli intervalli di posizione e con il periodo richiesto. Nessun
valore nei gap. Il peso è tempo-osservazione: più chiamate contemporanee possono
contribuire più secondi del tempo civile. Le celle usano bande di latitudine e
larghezze di longitudine corrette al centro della banda: metri approssimati,
non quadrati geodetici esatti. Per dimensioni inferiori all'accuratezza disponibile,
il dettaglio segnala l'accuratezza ma non redistribuisce arbitrariamente il dato.

Deduplicazione: stessa identità esatta di chiamata, testo RTCP, report, direzione,
flow e SSRC costituiscono una firma di evidenza. Osservazioni identiche non vengono
reinserite; intervalli parzialmente sovrapposti della stessa firma vengono uniti
al calcolo, senza moltiplicarne il peso. Attribuzioni geografiche discordanti
sullo stesso intervallo sono escluse e conteggiate. Nessuna deduzione di identità
del dispositivo da numeri o somiglianza geografica; formati di log differenti
senza identità esatta possono conservare osservazioni distinte.

API: `GET /api/geography?cell=250&direction=downstream&quality=fresh&start=...&end=...`.
Restituisce celle, punti di sola posizione, copertura, estremi dell'archivio e
contatori. Massimo 200.000 intervalli per interrogazione e 10.000 celle MOS:
errore esplicito con richiesta di restringere i filtri. Le posizioni grigie sono
limitate a 100.000 evidenze/10.000 celle con indicatore di troncamento. Gli indici
coprono tempo/direzione e coordinate; per archivi maggiori si potranno aggiungere
aggregati ricostruibili senza eliminare l'archivio.

## Upgrade e backup

Prima di aggiornare usare **Esporta database**. Lo schema 5→6 crea automaticamente
`kpe.sqlite3.pre-v6.bak` prima della migrazione di un database popolato. Non sovrascrive
un backup esistente; in quel caso interrompe l'avvio e richiede di preservarlo o
rinominarlo. La migrazione è transazionale e conserva ID, log e annotazioni.
Il backfill è idempotente e transazionale. Per rollback arrestare il servizio e
ripristinare il backup in una nuova cartella/volume, mai sopra un DB aperto.
Il programma precedente non supporta schema 6. Non pubblicare DB, backup o log.

## Cartografia e riferimenti

`app/static/basemap.json` deriva dai dataset Natural Earth
`ne_50m_admin_0_countries` e `ne_10m_populated_places_simple` (città ≥100.000 abitanti),
distribuiti in pubblico dominio: https://www.naturalearthdata.com/about/terms-of-use/.
Origine: https://github.com/nvkelso/natural-earth-vector/tree/master/geojson.
Questa attribuzione riguarda solo i dati cartografici, non la licenza del progetto.

- Android Location: https://developer.android.com/reference/android/location/Location
- Policy tasselli OSM: https://operations.osmfoundation.org/policies/tiles/
- Attribuzione OSM: https://www.openstreetmap.org/copyright

Le stime PQ localizzano approssimativamente qualità ricavata dai log; non
inventano qualità mancante. Gallerie senza estremi utilizzabili o senza
qualità valutabile restano vuote anche in presenza di un problema reale.

## Contesto di rete e sequenze

Schema 7 aggiunge filtri per piattaforma, accesso, connessione a monte e operatore,
con percentuale di tempo ad accesso noto. [Regole, sequenze e upgrade](mobility.md).

## Telemetria strutturata: metodo distinto

Le regole legacy sopra (in particolare il limite di 120 s dalla consegna) non
si applicano indistintamente alla telemetria. Con schema 8, `telemetry-2` associa
finestre verificate a fix app non cached, già consegnati e con età dal fix non
superiore a 30 s, nello stesso dominio sorgente/sessione/boot. La posizione del GW
non viene usata come posizione dell'app. [Regole complete](telemetry-integration.md).

Le finestre strutturate sono in UTC; i log legacy conservano gli orari scritti.
Non esiste una correzione automatica del fuso tra i due. Non c'è deduplicazione
generale tra telemetria e log testuali dello stesso media: evitarne la doppia
lettura come misure indipendenti. I punti grigi di sola posizione della vista
attuale provengono dai metodi legacy; la telemetria contribuisce alle celle MOS
quando esiste un'associazione valida.

## Riservatezza e conservazione

La vista MOS aggregata omette utenti, sorgenti e Call-ID. Il dettaglio PQ
include riferimenti a file, righe, eventi e prospettive: i nomi dei file possono
contenere informazioni personali. Non considerare la risposta PQ anonima. Anche la vista MOS senza identità
non offre una garanzia matematica di anonimato delle coordinate precise. Non esportare il DB come se
contenesse soltanto celle anonime. Le coppie posizione–MOS e gli input sono
conservati senza retention automatica, per poter cambiare aggregazioni in futuro.

## Profili temporali delle zone

Con MOS, il clic su una cella apre storico giornaliero/settimanale/mensile/annuale, ricorrenze orarie, copertura ed evidenze. Gli stessi calcoli sono disponibili tramite `POST /api/analytics/geo-temporal` e `analytics_geo_temporal`; `POST /api/analytics/geo-cells` e `analytics_geo_cells` scoprono le celle. [Guida, denominatori e contratto completo](geo-temporal.md). Il catalogo MCP espone gli schemi in `geo_temporal`. Riconnettere il client MCP per rileggere i nuovi strumenti.


## Switch Network espliciti

Eventi, timeline, grafici e mappe evidenziano le richieste Switch Network con
un marker viola e prove file:riga. Transizioni contestuali e posizioni stimate
sono dichiarate separatamente. API `POST /api/analytics/network-switches` e MCP
1.4.0 (13 strumenti), `analytics_network_switches`, usano lo stesso calcolo.
Vedi [regole, campi e limiti](network-switches.md). Nessuna reimportazione richiesta.

7 ottobre 2026: mappa e percorso disegnati prima della risposta Switch Network.
Verifica browser con ritardo sintetico di 20 s, navigazione fra viste, import,
confronto e cambio metrica positivi; console pulita. [Checkpoint prestazioni](checkpoint-2026-10-07-performance.md).
