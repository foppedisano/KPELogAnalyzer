# Profilo temporale di una zona

[Indice](README.md) · [Mappa](geography.md) · [API](api.md) · [MCP](analytics.md)

Fare clic su una cella della mappa, oppure su una voce di **Zone da osservare**.
Si apre una schermata con i confini esatti della cella, anche a 50 o 500 metri.
La risoluzione non viene ampliata automaticamente per ottenere più dati.
Le celle grigie possono avere misure locali anche senza MOS; l'assenza di dati
non viene convertita in buona qualità.

## Letture disponibili

- **Storico** per giorno, settimana (da lunedì), mese o anno: punti dei periodi
  osservati, senza interpolazione nei vuoti, e tabella dei valori.
- **Ricorrenza settimanale**: griglia dei sette giorni per le 24 ore.
- **Profilo giornaliero**, confronto dei giorni della settimana e dei mesi
  dell'anno. I mesi di anni diversi sono combinati solo nella vista ricorrente;
  lo storico mantiene distinti gli anni.
- **Copertura**: giorni, chiamate, sorgenti, osservazioni, tempo osservato e
  accuratezza peggiore del fix. Le soglie 7 giorni / 10 chiamate / 3 sorgenti
  sono filtri esplorativi: non sono intervalli di confidenza o garanzie predittive.
- **Contesto rete**: piattaforma, accesso locale, connessione a monte e operatore.
  I filtri sono ereditati dalla mappa; il periodo è modificabile nel dettaglio.
- **Esportazione** JSON del profilo e della pagina di evidenze, CSV di tutte
  le aggregazioni. Il JSON indica le ulteriori pagine di evidenze.

Il blu indica valori crescenti, non una diagnosi automatica di qualità. Per il
MOS i valori bassi sono peggiori; per buffer o scheduling l'interpretazione
richiede il catalogo delle metriche e il contesto.

## Misure e denominatori

MOS e perdita usano gli intervalli geografici versionati già archiviati.
`mean` è pesata sui secondi-osservazione, non sul tempo civile: chiamate
simultanee possono contribuire secondi distinti. La perdita media temporale
non è una percentuale complessiva ponderata per pacchetti.

Jitter/RTT RTCP, buffer e target dejitter, durata corrente di underrun sono
campioni puntuali: media per campioni, nessuna durata inventata. Scheduling
accumulato, reset, numero di underrun, silenzio riprodotto/saltato e campioni
saltati usano delta di contatori, non somme dei valori cumulativi.

I delta richiedono contesto identico (prospettiva, osservatore, device, input,
output, ciclo, flow, SSRC, direzione, statistica e unità), campioni validi,
incremento non negativo e distanza massima di 30 secondi. Invalidità e conflitti
interrompono la catena. I delta che attraversano un'ora, una nuova posizione o
un cambiamento osservato del contesto rete sono esclusi: non si distribuisce
arbitrariamente l'incremento fra ore o celle. Entrambi gli eventi restano prove.
`total_delta` somma gli incrementi ammessi; `rate_per_second` divide per i soli
secondi degli intervalli ammessi, non per l'intera ora o chiamata. `mean` resta
null per questi contatori.

`day_balanced_mean` calcola prima la media di ciascun giorno nel gruppo e poi
la media dei giorni con uguale peso. Riduce il dominio di una giornata molto
osservata, ma non corregge differenze di popolazione o dipendenze fra chiamate.
Per i contatori non viene calcolata; il grafico mostra il tasso osservato.

I campioni puntuali offrono anche un confronto statistico esplicito fra serie con uguali osservatore, device, input/output, flow, direzione, statistica e unità. Prospettive, cicli e SSRC restano distinti in `series_breakdown`; le identità non sono fuse. Questo confronto non è disponibile per i delta dei contatori.

Le metriche locali mantengono serie separate: se ne esiste più di una, occorre
scegliere il contesto. Non si fondono automaticamente prospettive, SSRC o cicli.
Le aggregazioni MOS/perdita sono invece statistiche di popolazione esplicite
della zona. Nessuna inferenza del modello fisico del device o delle versioni
app/VDK viene introdotta: piattaforma e rete sono i filtri attualmente disponibili.

## Posizione, orologi ed evidenze

La scelta **legacy_observed** usa gli orari scritti nei log, senza fuso dedotto;
**utc** usa solo la telemetria strutturata. L'ora UTC non è automaticamente
l'ora locale della zona. I due domini non vengono combinati. Le metriche locali
VD/RTCP puntuali sono disponibili qui solo per il percorso legacy; per UTC sono
disponibili MOS/perdita delle finestre georeferenziate strutturate.

Le misure legacy puntuali richiedono una posizione della stessa importazione
già osservata, entro 120 secondi; le dichiarazioni SIP locali, quando abilitate,
devono appartenere alla stessa chiamata. Posizioni future, cached, remote,
invalide o discordanti non localizzano una misura. I delta richiedono lo stesso
fix ai due estremi. Ruoli non-app e copie storiche riconosciute sono esclusi.
La selezione non corregge retroattivamente associazioni geografiche persistite.

Upstream è un report del peer associato alla **posizione locale dell'app**:
non localizza il peer né dimostra una causa nella zona. I dati VD descrivono
il device locale e non vengono filtrati come report RTP in base alla direzione.

Le evidenze includono ID metrici/geografici, eventi, file e righe disponibili;
`analytics_evidence` risolve gli eventi anche nei nomi dei file. Nessun testo
integrale dei log viene restituito. La pagina ha un massimo di 200 osservazioni
e ogni osservazione restituisce al massimo 100 riferimenti, con flag esplicito.
Le coordinate precise e le evidenze non costituiscono dati anonimi.

## API e MCP

`POST /api/analytics/geo-cells` / `analytics_geo_cells` scopre gli ID delle
celle usando gli stessi filtri di `GET /api/geography`. La panoramica può
contenere entrambi i domini temporali; il profilo ne seleziona uno.

`POST /api/analytics/geo-temporal` / `analytics_geo_temporal` usa lo stesso
calcolo della schermata. Il catalogo `analytics_catalog.geo_temporal` restituisce
metriche, schema dei parametri, regole e limiti. Esempio (sostituire `cell_id`
con un ID ricevuto dalla ricerca delle celle per la stessa dimensione):

```json
{
  "cell": 250,
  "cell_id": "60045:59441",
  "metric": "mos",
  "time_basis": "legacy_observed",
  "grain": "month",
  "direction": "downstream",
  "quality": "fresh",
  "access": "cellular",
  "evidence_limit": 50,
  "evidence_offset": 0
}
```

`start`/`end` definiscono un intervallo semiaperto `[start,end)`; per i delta
entrambi i campioni devono essere nel periodo. `series_id` seleziona una delle
serie restituite; `selection_required` segnala che non sono state aggregate.
La risposta include `definition`, cella/confini, metrica/denominatore, `summary`,
`profiles` (history/hour/weekday/week_hour/month), `network_breakdown`,
`exclusions`, `evidence`, paginazione, `snapshot` e regole. Nei profili ricorrenti
i bin senza dati hanno valori null; nello storico compaiono i periodi osservati.
Le esclusioni contano il perimetro di ricerca, anche campioni non localizzabili
fuori dalla cella: non sono un tasso di errore della zona.

Per paginare mantenere fissi i parametri e incrementare `evidence_offset`;
verificare lo stesso `snapshot`. Gli endpoint sono in sola lettura. Limiti:
100.000 righe di input, 100 serie, 5.000 bin storici, 300.000 segmenti orari,
20 secondi, risposta massima 4 MiB. Gli eccessi generano un errore esplicito:
ridurre periodo o filtri; non vengono presentati aggregati silenziosamente parziali.

Prompt MCP: «Trova le celle da 500 metri con osservazioni cellulari. Per la
cella scelta confronta MOS alle 02 e alle 13 nei log tradizionali, distinguendo
giorni della settimana, media temporale e media dei giorni. Riporta copertura,
contesto rete e prove. Non presentare una ricorrenza osservata come previsione».

## Passo successivo: previsione

Questa fase è descrittiva. `forecast.status=not_implemented` evita di presentare
una media storica come previsione. Prima di adattare l'app servono un evento
obiettivo, validazione temporale su periodi successivi, confronto con una base
semplice, analisi degli errori e una regola di astensione per dati insufficienti.
Non cambiano schema, database, log o configurazioni dell'app: nessuna migrazione
o reimportazione è richiesta per il profilo temporale.
