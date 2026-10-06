# Log nel dettaglio chiamata

La sezione **Eventi della chiamata** raggruppa i file per famiglia: per esempio
`VDLog_1.txt`, `VDLog-2.txt` e `VDLog.txt.3` sono **VDLog**. Ogni riga mostra il
nome generico; espandendola trovi nome originale, riga normalizzata, sorgente,
ID evento, attribuzione archiviata e testo completo, anche multilinea.

Ogni famiglia ha due controlli indipendenti:

- Casella di visibilità, attiva per impostazione predefinita.
- Casella **Tutto**: disattivata = solo questa chiamata (default), attivata =
  tutte le righe nell’intervallo. I due controlli sono affiancati in una riga
  compatta; intervalli e criteri sono consultabili in un dettaglio espandibile.

Le scelte possono essere mescolate: per esempio tutti gli eventi App, solo quelli
RTPLog attribuiti alla chiamata e SIP Debug nascosto. Restano attive durante
ricerche, filtri di livello e paginazione; riaprire la chiamata ripristina i default.
Nascondere una famiglia conserva la modalità selezionata per quando la riattivi.

Gli sfondi pastello identificano la famiglia, non INFO/WARNING/ERROR. La severità
rimane nel badge separato e gli Switch Network mantengono il proprio contrassegno.
Il nome testuale resta sempre presente, senza affidarsi soltanto al colore.

**Tutte nell’intervallo** usa separatamente la finestra di ogni prospettiva nelle
sole importazioni della chiamata, senza correzioni d'orologio. Include eventi non
attribuiti e di altre chiamate con badge **Contesto**; non cambia le associazioni
nel database. Non include righe prive di timestamp. Gli eventi già attribuiti ma
senza timestamp restano invece visibili in **Solo questa chiamata**.

L'ordine è timestamp/ID; pagine da 100 eventi. Ricerca testuale e livello vengono
applicati prima della paginazione, insieme alle scelte per famiglia. Le famiglie
sono disponibili anche se la pagina corrente non contiene loro eventi.

## Sessioni locali incomplete

Il parser 1.12.1 conserva una terminazione già osservata quando la linea viene
riutilizzata: il nuovo inizio non prolunga più la vecchia sessione priva di
riepilogo SIP. Per archivi precedenti, questo elenco delimita in sola lettura le
finestre locali mediante la prima terminazione KPE attribuita alla prospettiva,
mostrando il riferimento alla prova. Lo stesso limite viene usato per le timeline
di connettività della chiamata e l'attribuzione degli Switch Network.

Non viene eseguito un backfill dei dati personali: la durata archiviata e le
associazioni storiche usate da altre analisi possono ancora riflettere il vecchio
errore. Una riparazione completa di metriche/derivazioni esistenti è un'attività
separata, da concordare. Nessun Call-ID o interlocutore viene inventato.

## API

`GET /api/call-events?call=1` restituisce `events`, `families`, `windows`, `offset`,
`more`. Parametri aggiuntivi: `search`, `level`, `offset` non negativo e `families`,
un oggetto JSON codificato nell'URL, per esempio:

```json
{"vdlog":"interval","sip_debug":"hide","kpelog":"call"}
```

Le famiglie omesse usano `call`; valori ammessi `call`, `interval`, `hide`.
ID famiglia sconosciuti e input malformati sono rifiutati. Ogni evento aggiunge
`log_family`, `log_label`, `source_label`, `is_context`. Le finestre riportano
`stored_end`, fine effettiva e `window_evidence` quando delimitate in lettura.
È un endpoint UI locale: non aggiunge strumenti MCP di esportazione dei log.


## Dettaglio dei tentativi utente

I tentativi hanno un riferimento stabile «Tentativo #N», con N pari all’ID
dell’evento di richiesta. Compare nel registro, nel breadcrumb e nel dettaglio;
si può cercare N o il riferimento nel registro. Non è una nuova identità SIP
é un numero di riga dipendente dall’ordinamento. Gli ID API restano invariati.
Anche i log dei tentativi e di Esplora log mostrano famiglia e sfondo di provenienza.
Il dettaglio usa gli stessi controlli compatti delle chiamate: visibilità per
famiglia e checkbox **Tutto**. Per default mostra soltanto la richiesta e la
prova esplicita del blocco, quando presente. Attivando **Tutto** per una famiglia
include anche il contesto della stessa importazione da 60 s prima della richiesta fino alla prova del blocco inclusa
(o alla richiesta stessa se manca una prova conclusiva),
con badge **Contesto**. Non crea associazioni SIP. Nascondere una famiglia
conserva la modalità scelta. La severità resta un badge separato.


`GET /api/attempt-events?attempt=4840333` usa l’ID positivo dell’evento del
tentativo e restituisce la stessa struttura dell’elenco chiamata. Supporta
`search`, `level`, `offset`, `families`; modalità `evidence` (default),
`interval`, `hide`. La finestra viene calcolata dal server. Le famiglie
comprendono tutti i file della sorgente, anche senza prove del tentativo.
Solo richiesta e prova esplicita hanno `is_context=false`; il contesto temporale
non è una prova di appartenenza. Nessuna modifica al database.
