# Avvio locale con un coding agent

## Prompt da copiare nell'agente

> Scarica https://github.com/foppedisano/KPELogAnalyzer e segui AGENTS.md e
> docs/getting-started.md. Verifica Git, Docker Engine e Docker Compose v2.
> Avvia il progetto sulla mia macchina con Docker, attendi /api/health e
> mostrami l'URL locale. Se la porta 8080 è occupata scegli una porta libera
> tramite KPE_PORT, senza arrestare altri servizi. Non caricare log personali
> su GitHub o servizi esterni. Non eliminare volumi o database esistenti.

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

## Analizzare i propri log

1. **Importa ZIP**: carica uno o più log set. Ogni archivio resta una sorgente.
2. **Chiamate**: apri una chiamata e scegli parametro e statistica. Tooltip e
   CSV mantengono i riferimenti ai log.
3. **Diagnostica A/B**: scegli prospettive/device, confronta metriche, episodi
   e somme esplicite; correggi gli orologi solo se hai elementi per farlo.
4. **App e xcoder**: associa sessione, partecipante e componente quando hai
   entrambi i punti di osservazione. Vedi [limiti xcoder](open-issues.md).

Se un formato non viene riconosciuto, usa File e finestre manuali oppure
Esplora log/SQL. La mancata attribuzione viene segnalata, non colmata con
associazioni arbitrarie. Consulta [metriche](metrics.md) e [diagnostica](diagnostics.md).

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

Non usare `docker compose down -v`: eliminerebbe il volume dati. Non usare
`git reset --hard` per risolvere modifiche locali. Le migrazioni documentate
creano backup aggiuntivi; vedi [architettura](architecture.md).

## Problemi comuni

- **Docker non raggiungibile:** avvia Docker Desktop o il daemon e riprova
  `docker version`. Non cancellare immagini/volumi per tentativi.
- **Porta occupata:** scegli `KPE_PORT` in `.env` come sopra.
- **Pagina vuota dopo un upgrade:** ricarica la pagina, controlla health e log.
- **Nessun punto nel grafico:** verifica metrica/statistica/device, copertura
  dei file e attribuzione della chiamata. Non significa automaticamente zero.

## Stato legale e del progetto

Il repository è pubblico **senza licenza concessa per ora**, per scelta del
proprietario: la disponibilità del sorgente non costituisce una licenza
generale di uso, modifica o redistribuzione. Le istruzioni descrivono il setup
tecnico; per autorizzazioni ulteriori contattare il proprietario.
Non è un prodotto ufficiale Kalliope e non contiene il suo SDK proprietario.
