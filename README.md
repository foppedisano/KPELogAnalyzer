# KPELogAnalyzer

Servizio web locale per analizzare gli ZIP di log delle app basate su **Kalliope Phone Engine**. Trasforma i log in un database SQLite interrogabile e conserva il riferimento al file e alla riga per ogni evidenza.

**Prima installazione:** [guida per utenti e coding agent](docs/getting-started.md), con prompt pronto da copiare, avvio su Windows/macOS/Linux e verifica del servizio.

```sh
git clone https://github.com/foppedisano/KPELogAnalyzer.git
cd KPELogAnalyzer
docker compose up --build -d
```

Apri http://127.0.0.1:8080/. Repository pubblico **senza licenza concessa per ora**: non è concessa una licenza generale di riuso, modifica o redistribuzione.

## Documentazione e primo percorso

Inizia da [come funziona la piattaforma](docs/platform-guide.md) e da
[capire le metriche](docs/metric-reading.md). L’[indice completo](docs/README.md)
separa guide operative, metodo MOS, mappa, API e contratto per gli sviluppatori app/GW.

1. Importa gli ZIP e controlla **Sorgenti e copertura**, incluse chiamate distinte, nuove e già presenti.
2. Ordina il registro per MOS medio/minimo e apri una chiamata.
3. Il dettaglio parte dal MOS downstream: **Aggiungi metriche** sovrappone i parametri scelti.
4. Verifica le evidenze, confronta i ricevitori e consulta la mappa dove esistono posizioni utilizzabili.

## Analisi conversazionali

La sezione **Analisi libere** e il server **MCP stdio** espongono un catalogo
semantico e query componibili: episodi MOS, medie pesate, copertura, ricevitori e
contesto rete, con evidenze e ricette versionate. [Configurazione e guida](docs/analytics.md).

## Android e conversazioni

Gli ZIP iOS e Android osservati usano lo stesso flusso di importazione. La vista **Conversazioni** collega le tratte tramite X-Call-UUID quando presente, mantiene visibili esiti e prove, e permette il confronto di app e gateway. [Guida, criteri e limiti](docs/conversations.md).

## Avvio con Docker

Prerequisiti: Docker Engine con Compose, oppure Docker Desktop **avviato** in modalità container Linux.

```sh
docker compose up --build -d
```

Apri **http://localhost:8080** e scegli **Importa ZIP**. Puoi caricare più archivi insieme. Non servono account, API key, Node.js, pacchetti Python o servizi cloud. Il primo build richiede la possibilità di scaricare l'immagine ufficiale Python.

```sh
docker compose ps
docker compose logs --tail=50 analyzer
docker compose down
```

I dati persistono nel volume `kpe-data`, anche dopo `down`. Per una porta diversa, imposta `KPE_PORT=8081` in un file `.env` prima dell'avvio. Il servizio è pubblicato esclusivamente su `127.0.0.1`.

## Cosa puoi fare

- Importare ZIP, anche con log ruotati, senza duplicare un archivio identico (SHA-256).
- Ignorare chiamate già importate dalla stessa app riconosciuta, mantenendo le altre prospettive ([identità e deduplicazione](docs/source-dedup.md)).
- Sfogliare le chiamate, cercare interlocutori e Call-ID, vedere connessione, terminazione, direzione e stato osservato.
- Confrontare più chiamate e più sorgenti con grafici interattivi, zoom, tooltip, selezione delle serie e CSV.
- Analizzare RTT, jitter, perdita pacchetti e contatori RTCP; statistiche KPE `last/avg/min/max`; ping ICMP.
- Consultare i log originali normalizzati, inclusi quelli non attribuiti a una chiamata.
- Correggere manualmente l'orologio di ogni sorgente nei grafici assoluti.
- Raggruppare più tratte in una conversazione/conferenza e indicare l'app host con una nota di evidenza.
- Eseguire SQL in sola lettura ed esportare una fotografia consistente del database.

## Tentativi utente e connettività

Il registro include anche richieste utente e blocchi prima del SIP, con ragioni ed
evidenze. **Rete e servizi** permette di esaminare ogni secondo, anche fuori call;
i grafici distinguono raggiungibilità, CTI, SIP e stato KPE.
[Metodo, limiti e aggiornamento](docs/connectivity.md).

## Grafici della chiamata e del confronto

[Aggiungi metriche](docs/call-chart.md) permette selezione multipla e ricerca,
con scorciatoie Qualità, Rete e Ricezione. RTT e jitter condividono il pannello ms;
unità diverse usano pannelli con tempo, cursore e zoom sincronizzati. Le metriche
raw restano separate. Le tacche dei conteggi di pacchetti sono intere; MOS usa
la scala 1–5. La × rimuove una metrica, la legenda nasconde una singola serie.
CSV e statistica last/avg/min/max rimangono specifici della metrica.

## Diagnostica e guida alle metriche

La vista **Diagnostica A/B** sovrappone RTT, massimo ritardo di arrivo NART, target dejitter, audio nel buffer e silenzio saltato. Include selezione di metriche (anche jitter e perdita), assi per unità, legenda con colori/simboli personalizzabili, tooltip condiviso, delta dei contatori e due somme distinte dei buffer con evidenze. Le fasce temporali mostrano anche underrun e media missing con durata, stato ed evidenze. Puoi salvare e riaprire configurazioni complete, correggere finestre manuali e confermare identità locali proposte con evidenze SIP. Supporta i formati VD/RTP vecchi e nuovi riconosciuti, anche nello stesso archivio; le versioni dell’app sono mostrate quando esiste un marker esplicito.

Per VDlog/rtplog sciolti usa **File e finestre manuali**. Per capire ogni parametro apri **Guida alle metriche**, il [catalogo completo](docs/metrics.md) e la [guida operativa e upgrade](docs/diagnostics.md). Le soglie segnalano momenti da verificare: non individuano automaticamente una rete guasta e non misurano il ritardo audio end-to-end.

## MOS a profilo fisso

La vista **MOS e ricezione** mostra due stime basate sulla perdita RTCP o su finestre di telemetria verificate,
con codec e PLC di riferimento costanti. È un indice della componente di perdita,
non una misura completa della rete o della qualità percepita. Selezionando il GW della tratta, la sua
ricezione locale è riutilizzata come upstream dell’app. Silenzio saltato e missing
packets restano evidenze separate. [Metodo, limiti e API](docs/mos.md).

## Mappa qualità

La mappa propone **Perceptual Quality**, indice 0–100 ricavato dagli underrun
AWT su finestre di un secondo, ritagliate ai confini della chiamata e associate puntualmente ai messaggi di posizione.
Nel dettaglio della singola chiamata, **Percorso e qualità** mostra le posizioni
in ordine temporale, separate per sorgente, con celle da 50 m e prove al clic.
MOS resta selezionabile. [Metodo, copertura e movimento](docs/perceptual-quality.md).

La **Mappa qualità** associa posizioni locali e intervalli MOS, con zoom, celle
regolabili e time machine. Conserva le osservazioni nel DB; aggrega per periodo
senza mostrare identità. Base offline e strade OSM opzionali.
[Metodo e limiti](docs/geography.md). Filtri di rete e sequenze temporali
preparano le analisi future: [contesto e upgrade schema 7](docs/mobility.md).

## Telemetria per le prossime versioni di app e GW

[Contratto di raccolta v1](docs/telemetry.md): tempi, posizione, rete, media,
configurazioni e interventi. Include esempi sintetici, validatore senza dipendenze
(`python -m app.telemetry file.jsonl`) e importazione di `telemetry*.jsonl` negli ZIP.
La [revisione 1.1 e lo schema DB 8](docs/telemetry-integration.md) aggiungono deduplicazione, audit dei piani offline e integrazione in MOS/mappa quando le semantiche sono verificate.

## App e xcoder

La vista **App e xcoder** collega, per singola sessione e partecipante, le osservazioni dell’app e del transcoder. Confronta anche quattro o più sorgenti con metriche ed episodi sullo stesso asse temporale. Il collegamento è esplicito e non fonde i Call-ID. [Guida e upgrade](docs/xcoder.md). Il formato xcoder è assunto uguale a quello delle app, **senza validazione su log reali**: [open issue](docs/open-issues.md).

## Modello e attribuzione

Una **chiamata** è identificata da un SIP Call-ID. Un **punto di vista** è l'osservazione della chiamata in un singolo ZIP. I file dello stesso ZIP sono sorgenti complementari, non partecipanti distinti. Il riuso della linea `0` non identifica una nuova chiamata come quella precedente.

Le finestre di linea sono ricostruite dagli eventi KPE e dai riepiloghi `callInfo.call-id`; i report RTCP sono associati solo quando la linea e il tempo individuano una finestra univoca. In assenza di KPE, `CallInfo` può ricostruire sessioni locali senza identità SIP. Queste sessioni rimangono distinte dalle chiamate SIP non collegabili con un identificatore esplicito.

Più ZIP con lo stesso Call-ID condividono la chiamata e conservano metriche e sorgenti separate. Un PBX/B2BUA può cambiare Call-ID tra le tratte: in questo caso seleziona le chiamate e crea una **Conversazione**. L'host della conferenza è una dichiarazione dell'analista, non una deduzione automatica. Nessuna chiamata viene unita solo perché contemporanea.

## Interpretare i risultati

- `completed` significa che nei log sono state osservate connessione e terminazione, **non** che la qualità audio sia buona.
- `partial` indica evidenza incompleta; la prima evidenza disponibile può non coincidere con l'inizio reale. La durata è l'intervallo osservato connessione–terminazione; con più sorgenti gli orologi possono alterarlo.
- Gli orari sono quelli scritti nel log: nessun fuso viene inventato. L'offset manuale modifica soltanto il grafico assoluto.
- I report RTCP dichiarano `ms`, `%` e conteggi. Valori negativi o percentuali fuori 0–100 restano nel DB con `valid=0` e sono esclusi dai grafici per default.
- Le metriche JSON KPE, tranne i contatori di pacchetti, hanno unità **raw**: non vengono convertite senza documentazione del produttore. Non confrontare numericamente RTT `raw` e RTT `ms` come se fossero equivalenti.
- Il ping è relativo all'endpoint ICMP scritto nei log, non necessariamente al peer RTP. `N/A`, NaN e infinito non sono trasformati in zero.
- Nel registro il MOS medio è pesato sulla durata degli intervalli coperti; minimo, massimo e copertura sono separati. Le statistiche dei campioni nel grafico sono invece aritmetiche, per serie. Il CSV di ciascuna metrica include anche serie nascoste e punti fuori dallo zoom.
- Le linee dei grafici si interrompono su intervalli oltre 30 secondi. Controlla i singoli campioni e la copertura dei file.
- I file non interpretati vengono conservati come eventi ricercabili (`raw`). Il supporto iniziale deriva da un export iOS KPE; altri formati/versioni possono richiedere nuovi parser.

## Uso senza Docker

Python **3.12 o superiore**, solo libreria standard:

```sh
python -m app.server
```

Il DB viene creato in `data/kpe.sqlite3`. Variabili: `KPE_DATA_DIR` (cartella dati), `KPE_HOST` (default `127.0.0.1`), `KPE_PORT` (default `8080`). Su Windows puoi usare `py -3.12` al posto di `python`.

Per lavorare con un coding agent o una shell:

```sh
python -m app.cli import /percorso/device-a.zip /percorso/device-b.zip --label "Caso test"
python -m app.cli query "SELECT id, start, end FROM calls ORDER BY start DESC LIMIT 20"
python scripts/make_demo.py
python -m app.cli import data/demo/alice.zip data/demo/bob.zip
python -m unittest discover -v
```

Il generatore demo contiene solo identità sintetiche `example.test`: i due ZIP mostrano la stessa chiamata da due punti di vista.

## Dati, limiti e backup

Lo ZIP viene letto in memoria e non estratto sul filesystem. Limiti: **64 MiB ZIP**, **256 MiB decompressi**, **40 MiB/file**, **200 elementi**. Importazione sincrona e atomica per archivio; nell'upload multiplo un errore non annulla gli archivi già riusciti. La UI elenca al massimo 2.000 chiamate; SQL consente di interrogare l'intero DB. Grafici/CSV: massimo 100.000 campioni per richiesta di metrica, con errore esplicito oltre il limite. SQL: massimo 1.000 righe, 3 secondi e 4 MiB per risultato.

Il contenuto testuale è conservato in UTF-8 con newline normalizzati; `file:linea` si riferisce a questo testo. Caratteri non UTF-8 vengono sostituiti con avviso. Conserva lo ZIP originale se serve una copia byte-per-byte. Gli eventi duplicati nelle rotazioni restano consultabili, mentre le metriche identiche dello stesso parser vengono contate una sola volta nello stesso archivio. Due export diversi dello stesso dispositivo rimangono due prospettive: non sommare i loro contatori come se fossero dispositivi distinti.

La voce **Esporta database** scarica un backup SQLite consistente anche a servizio avviato. Il database contiene numeri, indirizzi e possibili credenziali presenti nei log: non pubblicarlo su Git. `.gitignore` e `.dockerignore` escludono ZIP e dati locali; non usare `git add -f` su questi file. Il servizio non ha autenticazione e va usato solo sulla macchina locale. Non esporlo su Internet.

Per ripristinare un backup, arresta il servizio e colloca la copia come `kpe.sqlite3` in una **nuova cartella dati** (oppure in un nuovo volume Docker), quindi configura `KPE_DATA_DIR`/il mount. Non sovrascrivere un DB aperto o mescolare i file `-wal`/`-shm` di un'altra copia.

## Sviluppo e struttura

```text
app/parser.py       ZIP, record multilinea, chiamate e metriche
app/db.py           schema SQLite, migrazione e backup
app/enrichment.py   VD/NART, RTT legacy e marker versione
app/diagnostics.py  allineamento, derivazioni e picchi con evidenze
app/catalog.py      dizionario condiviso UI/API/documentazione
app/mos.py          MOS a profilo fisso e riepiloghi temporali
app/geography.py    associazione posizione–MOS e aggregazione in celle
app/mobility.py     contesto di rete e sequenze locali
app/telemetry.py    contratto e validatore app/GW
app/telemetry_store.py  deduplicazione, controlli e derivazioni strutturate
app/manual.py       file testuali e finestre dichiarate
app/server.py       API HTTP, frontend statico, query read-only
app/cli.py          import/query/serve per agenti e automazioni
app/static/         UI senza dipendenze, CDN o build JavaScript
tests/              fixture sintetiche e regressioni parser/API
scripts/            generatore di export demo
docs/               schema, API e guida per aggiungere parser
AGENTS.md           istruzioni operative per coding agent
```

Vedi [architettura e parser](docs/architecture.md), [API](docs/api.md) e [guida per gli agenti](AGENTS.md). Il repository non include log reali né un SDK proprietario. Non è un prodotto ufficiale Kalliope.

Il [registro delle verifiche](docs/validation.md) distingue controlli recenti e storici.
I [limiti aperti](docs/open-issues.md) includono validazione GW, dati geografici,
scalabilità e algoritmi predittivi ancora da implementare.
