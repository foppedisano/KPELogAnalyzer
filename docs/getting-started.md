# Avvio locale con un coding agent

## Prompt da copiare nell'agente

> Scarica https://github.com/foppedisano/KPELogAnalyzer e segui AGENTS.md e
> docs/getting-started.md. Verifica Git, Docker Engine e Docker Compose v2.
> Avvia il progetto sulla mia macchina con Docker, attendi /api/health e
> mostrami l'URL locale. Se la porta 8080 è occupata scegli una porta libera
> tramite KPE_PORT, senza arrestare altri servizi. Non caricare log personali
> su GitHub o servizi esterni. Non eliminare volumi o database esistenti.
> Porta a termine installazione e verifica; non fermarti a proporre i comandi.
> Se trovi una copia esistente, ispeziona stato Git e servizio prima di aggiornarla.
> Non sovrascrivere .env, non resettare modifiche e non importare demo nei dati personali.
> Riporta URL, health, controlli eseguiti ed eventuali blocchi concreti.

## Prerequisiti

- Git.
- Docker Desktop avviato su Windows/macOS, oppure Docker Engine con plugin
  Compose v2 su Linux. Su Windows usare container Linux.
- Accesso a Internet per scaricare il repository e l'immagine base al primo
  avvio. Le analisi si svolgono successivamente sulla macchina locale.

Python e Node **non servono sul computer per avviare l'app con Docker**.
Non servono account applicativi, chiavi API, SDK Kalliope o servizi cloud.
Se Docker non è installato, installarlo dal fornitore prima di procedere;
il progetto non modifica WSL né reinstalla Docker automaticamente.

## Scaricare e avviare

Questi comandi funzionano in PowerShell, macOS e Linux:

```sh
git clone https://github.com/foppedisano/KPELogAnalyzer.git
cd KPELogAnalyzer
docker version
docker compose version
docker compose up --build -d
docker compose ps
docker compose exec -T analyzer python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/api/health').read().decode())"
```

Apri **http://127.0.0.1:8080/**. Il comando health deve restituire `ok: true`.
L'avvio iniziale può richiedere qualche minuto; in caso di errore consultare
`docker compose logs --tail=100 analyzer`.

Per scegliere una porta differente crea un file `.env` nella cartella del
progetto contenente `KPE_PORT=8081`, poi riesegui `docker compose up -d` e apri
http://127.0.0.1:8081/. La porta interna del container resta 8080. `.env` non
viene pubblicato su Git. Non cambiare il binding locale in `0.0.0.0`.

## Checklist operativa per il coding agent

1. Rilevare sistema operativo, cartella di lavoro e installazione esistente.
   In un clone esistente leggere `AGENTS.md`, `git status --short` e
   `docker compose ps`; non clonare sopra file o cambiare il nome del progetto
   Compose (determina anche il volume dei dati).
2. Controllare `git --version`, `docker version` (client **e server**) e
   `docker compose version`. Sono supportati Compose v2 e successivi con il
   comando `docker compose`. Nessun `pip install` o `npm install` necessario.
   Se manca Docker, usare il distributore ufficiale; eventuali permessi,
   riavvii o inizializzazione del motore vanno risolti prima dell'avvio.
3. Verificare la porta e `.env` senza esporne contenuti sensibili. Se 8080
   appartiene già a questa installazione, aggiornarla; se appartiene ad altro,
   scegliere una porta libera e modificare soltanto `KPE_PORT`, preservando
   le altre righe. Controllare il risultato con `docker compose config --quiet`.
4. Eseguire build/avvio come sopra e attendere health. Al primo avvio o dopo
   upgrade l'arricchimento può richiedere tempo: verificare i log, senza
   terminare il processo perché la prima richiesta non risponde subito.
5. Verificare anche l'URL **dal computer host**, non soltanto dentro il container:
   PowerShell `Invoke-RestMethod http://127.0.0.1:8080/api/health`; macOS/Linux
   `curl --fail http://127.0.0.1:8080/api/health`. Sostituire la porta scelta.
   Aprire la pagina nel browser e controllare la navigazione.
6. Consegnare URL effettivo, versione parser da health, nome del progetto
   Compose, conferma di persistenza e comandi di avvio/arresto. Nessun log
   personale o credenziale nel riepilogo. Il progetto non richiede chiavi API.

## Analizzare i propri log

Per l'accesso conversazionale seguire la [configurazione MCP stdio](analytics.md).
L'adattatore 1.4.0 usa il container già attivo, senza Python host o porte nuove:
`docker compose exec -T analyzer python -m app.mcp_server`.
Dopo il rebuild riconnettere il client e verificare `tools/list` (13 strumenti),
`analytics_catalog.current_analysis` e `analytics_coverage`. PQ, percorsi e
rete/servizi sono esposti insieme alle query; il client non viene configurato
automaticamente. Non eseguire import demo sull'archivio personale.

1. **Importa ZIP**: carica uno o più log set. Ogni archivio resta una sorgente.
2. **Sorgenti e copertura**: verifica chiamate distinte, nuove/già presenti e avvisi.
3. **Chiamate**: apri il MOS downstream, poi usa **Aggiungi metriche** o **Rete**.
   La × rimuove una metrica; legenda, cursore e CSV conservano i riferimenti ai log.
4. **Diagnostica A/B**: scegli prospettive/device, confronta metriche, episodi
   e somme esplicite; correggi gli orologi solo se hai elementi per farlo.
5. **App e xcoder**: associa sessione, partecipante e componente quando hai
   entrambi i punti di osservazione. Vedi [limiti xcoder](open-issues.md).

Se un formato non viene riconosciuto, usa File e finestre manuali oppure
Esplora log/SQL. La mancata attribuzione viene segnalata, non colmata con
associazioni arbitrarie. Parti da [come funziona](platform-guide.md) e [capire le metriche](metric-reading.md);
consulta [catalogo](metrics.md), [grafici](call-chart.md) e [diagnostica](diagnostics.md).
La [Mappa qualità](geography.md) richiede posizioni associabili: non deduce
coordinate dall’operatore o dagli interlocutori.

## Collaudo con dati sintetici (facoltativo)

Con Python 3.12+ sul computer:

```sh
python scripts/smoke_test.py
python scripts/smoke_test.py --demo
```

Il primo comando controlla soltanto lo stato del servizio. `--demo` importa
due archivi sintetici e verifica metriche e deduplicazione: aggiunge dati demo
al database selezionato, quindi usarlo su una nuova installazione o su un
servizio di prova. `--url http://127.0.0.1:8081` seleziona una porta diversa.
Puoi anche generare ZIP caricabili a mano con `python scripts/make_demo.py`.

## Verifiche senza Python/Node sul computer

L'immagine applicativa contiene `app`, non `tests` o `scripts`. Per la suite
montare il clone in sola lettura in un container Python temporaneo. Sostituire
`PERCORSO_ASSOLUTO_CLONE` con il percorso reale (per esempio quello restituito
da `Get-Location` su PowerShell o `pwd` su macOS/Linux):

```sh
docker run --rm --network none --mount "type=bind,source=PERCORSO_ASSOLUTO_CLONE,target=/workspace,readonly" -w /workspace -e PYTHONDONTWRITEBYTECODE=1 python:3.12-slim python -m unittest discover -v
```

L'immagine deve essere già disponibile; se manca, scaricarla prima con
`docker pull python:3.12-slim`. I test usano database temporanei nel container.
Node è facoltativo, soltanto per i controlli descritti in [Verifiche](validation.md).

Per uno smoke completo senza toccare dati personali, creare un'istanza dedicata.
I nomi seguenti e la porta 18080 devono essere liberi; se esistono già, scegliere
nuovi nomi coerenti in tutti i comandi, senza sostituire container/volumi esistenti.

```sh
docker build -t kpe-validation-image .
docker volume create kpe-validation-data
docker run -d --name kpe-validation --publish 127.0.0.1:18080:8080 --mount type=volume,source=kpe-validation-data,target=/data kpe-validation-image
docker run --rm --network container:kpe-validation --mount "type=bind,source=PERCORSO_ASSOLUTO_CLONE,target=/workspace,readonly" -w /workspace -e PYTHONDONTWRITEBYTECODE=1 python:3.12-slim python scripts/smoke_test.py --demo
docker restart kpe-validation
docker run --rm --network container:kpe-validation --mount "type=bind,source=PERCORSO_ASSOLUTO_CLONE,target=/workspace,readonly" -w /workspace -e PYTHONDONTWRITEBYTECODE=1 python:3.12-slim python scripts/smoke_test.py --demo
docker stop kpe-validation
```

Il secondo smoke verifica deduplicazione e metriche dopo il riavvio. URL di prova:
`http://127.0.0.1:18080/`. I nomi dedicati consentono una pulizia successiva mirata;
non usare comandi globali di prune e non eliminare volumi per fare spazio.
I dati demo restano confinati al volume di prova, mai a `kpe-data`.

## Arresto, aggiornamento e backup

```sh
docker compose stop
docker compose start
```

I dati sono nel volume Docker `kpe-data`, non nel repository. Prima di aggiornare
usa **Esporta database** nell'interfaccia e conserva il backup localmente.

```sh
git pull --ff-only
docker compose up --build -d
```

Prima di `git pull` controllare lo stato: con modifiche locali non resettare o
fare stash automaticamente; preservarle e gestire esplicitamente gli eventuali
conflitti. `pull --ff-only` fallisce se il ramo diverge: non forzare il pull/push.
Dopo il rebuild verificare health e premere **Ctrl+F5** nel browser: il semplice
`docker compose restart` non incorpora codice nuovo nell'immagine.
L'aggiornamento delle celle stimate PQ non richiede migrazioni né reimportazione.

Per ripristinare: arrestare la sola istanza interessata, conservare i dati
attuali e usare una **nuova cartella o volume** contenente la copia coerente
come `kpe.sqlite3`; configurare il mount o `KPE_DATA_DIR` e avviare una versione
compatibile con lo schema. Non ripristinare sopra un DB aperto.

Non usare `docker compose down -v`: eliminerebbe il volume dati. Non usare
`git reset --hard` per risolvere modifiche locali. Le migrazioni documentate
creano backup aggiuntivi; vedi [architettura](architecture.md).

## Problemi comuni

- **Docker non raggiungibile:** avvia Docker Desktop o il daemon e riprova
  `docker version`. Non cancellare immagini/volumi per tentativi.
- **Porta occupata:** scegli `KPE_PORT` in `.env` come sopra.
- **Pagina vecchia dopo un upgrade:** eseguire `docker compose up --build -d`,
  poi Ctrl+F5. Verificare di aprire la porta dell'istanza aggiornata.
- **Nessuna linea nella mappa generale:** previsto; PQ mostra celle dirette e
  stimate. Le linee sono nel dettaglio chiamata, pannello Percorso e qualità.
- **Nessuna zona stimata:** verificare metrica PQ, opzione Mostra zone stimate,
  periodo e filtro posizioni. Servono estremi della stessa chiamata/sorgente
  entro 120 s e qualità AWT valutabile. Una cella diretta nasconde la stima
  soltanto nel colore, mantenendola nel dettaglio.
- **Limite geografico superato:** restringere il periodo. Aumentare la cella
  riduce il numero di celle ma non il numero di secondi da calcolare.
- **Nessun punto nel grafico:** verifica metrica/statistica/device, copertura
  dei file e attribuzione della chiamata. Non significa automaticamente zero.

## Stato legale e del progetto

Il repository è pubblico **senza licenza concessa per ora**, per scelta del
proprietario: la disponibilità del sorgente non costituisce una licenza
generale di uso, modifica o redistribuzione. Le istruzioni descrivono il setup
tecnico; per autorizzazioni ulteriori contattare il proprietario.
Non è un prodotto ufficiale Kalliope e non contiene il suo SDK proprietario.


Il parser 1.12.1 e i [controlli log per famiglia](call-events.md) si installano
con lo stesso rebuild Docker. Non richiedono dipendenze, migrazioni o import
sintetici sul database personale. Dopo l’aggiornamento ricaricare la pagina
per usare il nuovo endpoint e i controlli del dettaglio chiamata.
