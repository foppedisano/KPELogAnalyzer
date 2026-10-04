# Sequenze di movimento e contesto di rete

## Scopo

Schema 7 prepara l'archivio per successive analisi predittive. Non esegue ancora
map matching, previsione del percorso o adattamenti audio. La mappa distingue
piattaforma, accesso locale, connessione a monte e operatore dati. Tutti i filtri
ammettono **Sconosciuto**; il filtro **Solo mobile diretta** esclude Wi-Fi,
tethering, reti di bordo e connessioni non documentate senza cancellare dati.
Un desktop non viene escluso per la sola piattaforma: vale il contesto osservato.

## Informazioni estratte oggi

- iOS `App.log`: `Current network interface: cellular|wifi|other`.
- Android `application*.log`: `ProcessCallLogger... : DeviceStatus: {...}`,
  campo esplicito `connectionType`.
- `cellular` diventa accesso cellular e connessione a monte mobile_direct:
  questa seconda classificazione è una regola del metodo basata sull'interfaccia,
  non una misura separata dell'operatore. Wi-Fi/Ethernet non determinano la rete
  a monte. Nessun SSID viene usato per indovinare tethering o servizio ferroviario.
- Operatore dati e identità Wi-Fi hanno campi opzionali; questi parser non li
  estraggono da nomi di rete, provisioning, numero telefonico o elenco delle SIM.
  Rimangono NULL finché un formato esplicito e validato non li fornisce.
- La piattaforma viene dal profilo della sorgente; desktop può essere filtrato
  ma non viene dedotto dall'assenza di marker iOS/Android.

`network_observations` conserva timestamp, evento, riga, metodo e origine della
misura. Android mantiene i millisecondi del messaggio originale. Il contesto vale
solo dallo stato osservato al successivo, al massimo 30 secondi. Prima del primo
stato e dopo la scadenza è sconosciuto. Stati discordanti allo stesso timestamp
non producono un contesto certo. I report sono fotografie, non una prova che la
rete non cambi nei secondi successivi.

Il calcolo geografico interseca gli intervalli MOS anche con cambi/scadenze di
rete. La deduplicazione avviene prima dei filtri; se copie della medesima evidenza
hanno contesti diversi, il campo discordante resta sconosciuto. Questo evita che
un filtro selezioni solo la copia favorevole. Anche le posizioni grigie rispettano
i filtri, valutati al loro timestamp. La percentuale di accesso noto riguarda
soltanto il tempo MOS selezionato, non la disponibilità di operatore o tethering.

## Sequenze

`movement_sequences` identifica con UUID casuale una sequenza locale a un import,
con inizio/fine, versione e motivo di interruzione. Non è identità di persona o
viaggio fra export. `movement_samples` conserva:

- riferimento alla posizione originale e ordine nella sequenza;
- orario del messaggio, eventuale orario reale del fix, tempo monotono grezzo;
- velocità e direzione opzionali con unità esplicite;
- riferimento all'osservazione di rete valida al timestamp del campione.

Il metodo `mobility-1` usa soltanto nuovi aggiornamenti locali (`fresh`), non
posizioni cached o dichiarazioni SIP. Rompe le sequenze su gap oltre 30 secondi,
posizioni simultanee discordanti/invalide, regressione del tempo monotono o salti
oltre 150 m/s più i raggi di accuratezza dichiarati. Il limite è un controllo di
plausibilità, non una classificazione del mezzo di trasporto. Consegne consecutive
dello stesso fix monotono non diventano nuovi campioni di movimento. Coordinate
diverse con lo stesso fix interrompono la sequenza. Posizioni originali, incluse
quelle escluse, restano nell'archivio geografico.

Non si deducono velocità, direzione o timestamp reale del fix dai soli tempi di
stampa del log: i campi restano NULL nei formati attualmente supportati. Campioni
singoli sono conservati; non provano un percorso utilizzabile per previsioni.
Export distinti mantengono sequenze distinte: un successivo dataset di training
dovrà controllare le copie degli stessi eventi per evitare contaminazione fra
training e test. Il MOS cartografico mantiene la propria deduplicazione.

Le prove metriche sono raggiungibili con
`movement_samples.position_id → geo_mos_evidence.position_id → metrics`.
Le risposte della mappa espongono solo conteggi, non UUID delle sequenze o utenti.

## Importazione e upgrade

Migrazione transazionale 6→7, backup consistente automatico
`kpe.sqlite3.pre-v7.bak` prima di modificare un DB popolato. Un backup omonimo
interrompe l'upgrade senza sovrascriverlo. Il recupero storico e i nuovi import
usano il marker idempotente `mobility-1:<import>`. Nessuna reimportazione richiesta;
nessuna retention automatica. Sono preservati log, ID, MOS, posizioni e annotazioni.
Prima dell'upgrade è disponibile anche **Esporta database**. Per rollback arrestare
il servizio e ripristinare il backup in un nuovo volume/cartella; la versione
precedente non può aprire schema 7.

API `GET /api/geography` aggiunge `platform`, `access`, `upstream`, `operator`:
`all` è il default. `mobility` contiene conteggi globali e soglie del metodo;
`network_known_seconds`, `network_known_percent` e `network_breakdown` descrivono
il periodo e i filtri correnti. La risposta non sostiene di essere una previsione.

## Telemetria disponibile e prossimo passo

Il [contratto v1.1](telemetry-integration.md) ora definisce tempi UTC e monotoni,
ID stabili, accuratezza, velocità/direzione quando misurate, percorso media,
operatore attivo e rete a monte solo se nota. Il validatore e l’importazione
sono implementati; gli emitter nelle app/GW restano da realizzare e validare.
Velocità e direzione strutturate sono conservate nel JSON originale; il metodo
legacy `mobility-1` non le trasforma ancora in un modello di percorso.

Restano da implementare grafo stradale/ferroviario, map matching, previsione
dei rami ai bivi, riconoscimento di percorsi ricorrenti, replay causale dei viaggi
e valutazione a 1/3/5/10 secondi. Un percorso ricorrente non identifica da solo
il treno fisico. I piani offline sono oggi oggetto di audit, non prodotti dall’API.


## Relazione con le celle stimate PQ

Le sequenze persistite `mobility-1` e il loro contesto non sono un modello
stradale. L'interpolazione PQ è una derivazione distinta, in lettura, fra
posizioni della stessa chiamata/sorgente entro 120 s. Alimenta punti nel
dettaglio chiamata e celle stimate nella mappa generale; i dati diretti
prevalgono. Non predice il percorso futuro o il mezzo di trasporto e non
modifica le osservazioni originali. [Metodo e limiti](perceptual-quality.md).
