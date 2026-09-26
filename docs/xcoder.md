# App e nodo transcoder

Una persona può avere due punti di osservazione della stessa telefonata:
la propria app e il nodo transcoder (xcoder) del Kalliope GW. Non sono due
partecipanti. Uno stesso server può produrre osservazioni di persone diverse.

## Direzioni e MOS

Per l'analisi MOS della stessa tratta, usare **MOS e ricezione** e scegliere
esplicitamente il ricevitore opposto: il suo risultato locale viene riutilizzato.
L'associazione app/xcoder qui non configura automaticamente quel selettore né
il MOS del registro. Un xcoder può servire più tratte: il ruolo da solo non basta
per invertire incoming/outgoing. [Metodo MOS](mos.md) e [direzioni](metric-reading.md).

Il grafico multimetriche del dettaglio chiamata ha controlli distinti dal
confronto multicomponente: [aggiunta, rimozione e scale](call-chart.md).

## Procedura

1. Importa separatamente i log set delle app e degli xcoder con **Importa ZIP**.
   Un archivio deve rappresentare un singolo componente/processo, non un insieme
   di nodi indipendenti. Lo stesso xcoder può contenere più chiamate o linee.
2. Apri **App e xcoder**. Per ogni prospettiva scegli una **Sessione** (identificativo
   della conversazione analizzata), **Partecipante**, **Componente**, nome del nodo
   e una nota sulle evidenze usate per l'associazione.
3. Usa esattamente gli stessi nomi di sessione e partecipante per app e xcoder
   della stessa persona. Il collegamento è manuale, modificabile e non unisce
   Call-ID diversi. La revisione protegge da salvataggi su dati obsoleti.
4. Seleziona la sessione nel confronto. Scegli le osservazioni e il device VD per
   ciascuna, quindi **Grafica osservazioni selezionate**. Sono ammesse fino a 16
   osservazioni nello stesso grafico: anche quattro sorgenti per due persone.
5. Confronta le curve sul tempo reale, usa zoom e legenda per nasconderle o
   cambiarne colore/simbolo. Le fasce degli episodi audio condividono l'asse.
   L'esportazione JSON conserva configurazione, associazioni ed evidenze.

Se mancano finestre KPE riconosciute, usa **File e finestre manuali** indicando
linea e intervallo. I dati ambigui rimangono non assegnati. Un Call-ID identico
permette la correlazione già supportata; orari vicini o linea 0 non provano
che due tratte appartengano alla stessa chiamata.

## Direzioni e interpretazione

`incoming` e `outgoing` sono sempre relativi al componente che scrive il log.
Il ricevitore nell'app può misurare il downstream, mentre un ricevitore nello
xcoder può misurare l'upstream dell'app: questa corrispondenza va verificata
per flow/SSRC e tratta, non viene dedotta dalla sola etichetta xcoder.

Buffer, target dejitter, RTT, jitter, perdita, silenzio saltato e relativi episodi
mantengono le definizioni della [guida alle metriche](metrics.md). Le etichette
app/xcoder descrivono il punto di osservazione, non cambiano unità o valori.
Il confronto multicomponente non somma automaticamente buffer di stadi diversi:
la somma non misura il ritardo audio end-to-end. Codec, ridondanza e operazioni
specifiche di transcoding non hanno nuovi estrattori senza esempi verificati.

Gli offset si configurano in **Sorgenti e copertura**, uno per log set: valgono
per tutte le prospettive dello stesso import e correggono solo l'asse del grafico.
App e server possono avere orologi diversi. Il periodo del confronto è espresso
sull'asse corretto. Nessuna correzione modifica i timestamp grezzi.

Le associazioni persistono; la configurazione del grafico multicomponente si
esporta in JSON ma non si riapre ancora come analisi salvata. **Diagnostica A/B**
resta disponibile per confronti salvabili tra due osservazioni qualsiasi.

## Upgrade e stato della validazione

Schema 3 → 4 aggiunge `observation_roles`, una riga per prospettiva. Prima della
migrazione di un DB non vuoto viene creata una copia consistente
`kpe.sqlite3.pre-v4.bak` accanto al database (in Docker: `/data/`). Conservare la
copia; se esiste già, il sistema si ferma per non sovrascriverla. Non eliminare
il volume Docker per aggiornare. La migrazione non ricostruisce metriche,
chiamate o annotazioni precedenti. Non serve reimportare gli ZIP.

**Il formato xcoder è assunto uguale a quello delle app e non è stato validato
su log reali.** Vedi [XCODER-001 e le altre open issue](open-issues.md).
