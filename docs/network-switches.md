# Switch Network espliciti

La funzione `network-switch-1` evidenzia le richieste esplicite al KPE di gestire
uno Switch Network. Non crea eventi da un cambio di interfaccia, da una perdita
di connettività o dalla presenza di un re-INVITE SIP.

## Dove trovarli

- **Eventi della chiamata / Esplora log**: bordo e badge viola, orario, transizione
  e riferimenti all'evento originale. Il testo originale rimane consultabile.
- **Rete e servizi**: riga dedicata e linea verticale tratteggiata attraverso
  rete, dispositivo, STUN, CTI, SIP, media e app. L'elenco espandibile conserva
  ogni evento, anche se i marker sono vicini.
- **Grafici chiamata, confronto e Diagnostica A/B**: rombo viola e linea
  tratteggiata sulle fasce della rispettiva sorgente; dettagli al puntatore.
  Correzioni temporali e allineamento relativo valgono anche per i marker,
  senza cambiare gli orari originali mostrati nelle evidenze.
- **Mappa generale e percorso chiamata**: livello separato `◆ Switch Network`,
  con elenco selezionabile, istante e dettaglio della transizione. Il rombo con
  bordo tratteggiato indica una posizione interpolata. Gli eventi senza
  coordinate restano nell'elenco con il motivo della mancata localizzazione.

Il viola identifica un evento puntuale: non significa rete UP/DOWN o qualità
bassa. Non modifica MOS, PQ, medie geografiche o precedenza delle celle dirette.

## Riconoscimento e transizione

Il messaggio riconosciuto è `KPE was requested to handle a switchNetworkEvent`,
come prima riga di un evento KPECORE INFO/DEBUG/WARNING in un file `kpelog*`,
con intestazione temporale. Occorrenze in indirizzi SIP, corpi e altri messaggi
sono escluse. Questo marker prova una **richiesta**, non il completamento dello
switch né il legame causale con un re-INVITE.

Il suffisso opzionale `from <rete> to <rete>` viene conservato quando contiene
nomi riconosciuti (Wi-Fi, cellular, Ethernet, EDGE, LTE, GPRS, UMTS, HSPA/HSPA+,
NR/NRNSA). Il supporto di questo suffisso è verificato con dati sintetici;
non implica che i log di ogni versione lo contengano.

In assenza di campi da/a, si esaminano le dichiarazioni di interfaccia della
stessa importazione entro ±3 secondi. Una sola sequenza di due stati distinti,
senza conflitti allo stesso istante e senza altre richieste vicine (±6 s),
permette di descrivere il contesto Wi-Fi → rete mobile o viceversa. Le due
osservazioni possono precedere il marker: non sono una misura dell'esatto
istante del cambio. La UI e l'API dichiarano sempre questa origine contestuale.
L'elenco delle osservazioni riporta gli eventi e le righe a supporto.

`cellular` da solo non identifica EDGE/LTE/5G. Stati uguali, multipli, mancanti
o ambigui lasciano la transizione non determinata. Non si indovina la tecnologia.
Copie identiche nella stessa sorgente/istante sono raggruppate conservando tutte
le evidenze. Le copie storiche delle prospettive restano escluse.

## Attribuzione e posizione

Si conserva l'attribuzione all'evento, oppure si usa una finestra univoca della
stessa sorgente. Con chiamate sovrapposte il marker resta contesto della sorgente,
visibile nella finestra ma esplicitamente non attribuito; non fonde chiamate.

La posizione richiede una prospettiva univoca e osservazioni locali compatibili:
un fix allo stesso istante oppure due estremi della stessa chiamata/sorgente
distanti al massimo 120 s. L'interpolazione è lineare, dichiarata come stima,
con riferimenti a entrambi gli estremi. Posizioni remote/cache, conflitti,
osservatori non app e passaggi attraverso altre chiamate non vengono usati.
Il filtro `fresh` esclude le posizioni dichiarate; `declared` le ammette senza
attribuire loro una freschezza non dimostrata. Non si aggancia l'evento alla
posizione semplicemente più vicina né a una strada.

## API e MCP

`POST /api/analytics/network-switches` e lo strumento MCP
`analytics_network_switches` condividono la stessa implementazione in sola lettura.

```json
{"call_id": 1, "quality": "declared", "locate": true}
```

Filtri opzionali: `call_id`, `perspective_id` (richiede la chiamata corretta),
`import_id`, `start`, `end`, `quality` (`fresh`/`declared`), `locate` (default true),
`platform`, `access`, `upstream`, `operator`. Gli orari sono quelli osservati,
senza fuso; intervallo `[start,end)`. I filtri di rete usano il contesto all'istante
del marker. Non indicare offset corretti come se fossero timestamp sorgente.

Risposta: `version`, `events`, `count`, `unlocated`, `rules`. Ogni evento contiene
`ts`, `stage=requested`, `previous`, `next`, `transition_basis`, `association`,
`evidence`, `network_context` e `location`. La posizione include `basis`,
`gap_seconds` ed evidenze geografiche; quando manca, `location_reason` spiega il
motivo. Con `locate=false` tutte le posizioni restano null e `unlocated` le conta.

Limiti espliciti: 10.000 candidati, 5.000 richieste, 100 osservazioni di contesto
per evento (troncamento dichiarato, senza dedurre una transizione), 1.000 posizioni
vicine e risposta dedicata massima 4 MiB. Restringere sorgente o periodo in caso
di errore; non esiste paginazione. Le timeline espongono `network_switches` e
`/api/events` annota le righe con `network_switch`.

Il calcolo avviene sui dati esistenti: nessuna migrazione, reimportazione,
modifica del parser o scrittura di nuove associazioni persistenti.
