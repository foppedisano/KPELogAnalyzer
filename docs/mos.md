# MOS a profilo fisso e ricezione

Aprire **MOS e ricezione** dal menu o dalla chiamata. Selezionare la prospettiva
dell'app. Senza GW, upstream usa la perdita dichiarata dal peer nei Receiver
Report dell'app. Selezionare esplicitamente la prospettiva del GW solo quando
è il ricevitore opposto della stessa tratta: il suo calcolo incoming viene
riutilizzato come upstream, con gli stessi valori, intervalli ed eventi.
Non si uniscono Call-ID, non si deducono identità e non si riempiono le lacune
del GW con la stima RTCP. La selezione vale per l'analisi corrente; esportare
JSON per conservarla insieme ai risultati. Gli offset delle sorgenti allineano
gli assi delle due direzioni; le evidenze conservano gli orari originali.

## Profilo loss-reference-1

Indice sulla scala MOS derivato dalla sola perdita RTCP, con riferimento fisso:
G.711, pacchetti 10 ms, PLC Appendix I, Ie=0, Bpl=25.1, BurstR=1, R base=93.2.
I 10 ms descrivono il profilo del modello, non i pacchetti reali e non una
conversione dei log. Perdita p espressa in percento:

```
R = clamp(93.2 - 95*p/(p+25.1), 0, 100)
MOS = 1 + 0.035*R + 0.000007*R*(R-60)*(100-R)
```

È una stima a ipotesi fisse, non un E-model completo o una misura della qualità
percepita. Non include ritardo, jitter, burst, scarti di playout o il PLC reale.
Applicare perdita RTCP al posto della perdita al playout è una limitazione
esplicita. Perdita nulla dà circa 4.41 anche quando jitter o RTT sono elevati:
consultare gli indicatori di contesto. Non localizza un guasto nella rete.

Riferimenti:

- [ITU-T G.107 (2015)](https://www.itu.int/rec/T-REC-G.107): impairment e conversione R/MOS.
- [ITU-T G.113 (2024), tabella I.4](https://www.itu.int/rec/T-REC-G.113): profilo G.711, limiti delle perdite casuali e del jitter buffer.
- [RFC 3550 §6.4.1](https://www.rfc-editor.org/rfc/rfc3550.html#section-6.4.1): semantica dei report.

## Tempo e provenienza

Ogni serie separa prospettiva, direzione, flow e SSRC. Il valore inizia al
report e termina al prossimo report della serie, a fine chiamata o dopo 30 s,
qualunque venga prima. Nessun valore prima della prima osservazione. Il report
descrive il passato; il mantenimento nel futuro è un'ipotesi. `report_ts` e
`observation_start` conservano il timestamp del report corrente e del precedente
disponibile (non la prova dell'inizio effettivo della finestra remota).
Report invalidi, unità errate e valori discordanti allo stesso timestamp
interrompono la stima. Valori mancanti non diventano zero.

La vista mostra la media pesata solo sugli intervalli coperti di ciascuna serie.
JSON e CSV conservano modello, perdita in ingresso, scadenza, eventi e file:riga.
Il selettore Parametro di chiamata e Confronta contiene `derived.mos_reference`
nelle due direzioni. Il pannello dedicato aggiunge la selezione del GW e il
contesto. I calcoli sono su richiesta: nessuna migrazione o reimportazione.

## Silenzio saltato e missing packets

Il delta del silenzio saltato è mostrato in ms e come percentuale del tempo
fra due campioni. Reset, primo valore e gap oltre 30 s non producono delta.
Questa percentuale non è automaticamente voce persa. Missing packets sono
segnalazioni che possono sovrapporsi o precedere recupero: non sono sommati
alla perdita RTCP. Nessuno di questi indicatori modifica arbitrariamente il MOS.
RTT resta bidirezionale; jitter conserva la direzione di misura.

API: `GET /api/mos?local=<perspective_id>&peer=<optional_peer_id>`.
`upstream_basis` distingue `remote_rtcp` da `peer_local_reused`.
Input e contesto sono limitati a 100.000 osservazioni per richiesta di calcolo;
un eccesso restituisce un errore, senza troncamento silenzioso del JSON.

Con soli log GW, scegliere ruolo locale **GW**: la ricezione locale diventa
upstream rispetto all’app, e il report remoto stima il downstream.
API: `local_role=gw` (default `app`). `downstream_basis` descrive anche la
provenienza del downstream. Il ruolo è esplicito per la singola analisi.

## Riepilogo nel registro chiamate

`GET /api/calls` include `mos`: prospettiva dell'import più recente, sorgente,
ruolo assunto/confermato e downstream/upstream. Non fonde export sovrapposti.
Per ogni direzione: minimo, massimo, media `sum(MOS × secondi) / sum(secondi)`,
secondi coperti, percentuale della finestra locale connessione–fine (o inizio
osservato–fine), eventi degli estremi. La copertura è ignota senza fine nota.
I gap non pesano come zero. Si riusano gli stessi intervalli del dettaglio,
con scadenza di 30 secondi. Più flow/SSRC nella stessa direzione impediscono
un riepilogo unico; ruoli non app richiedono verifica nel pannello MOS.
Il ruolo app non dichiarato resta esplicitamente presunto. La selezione temporanea
di un GW nel pannello non configura il registro: upstream qui usa RTCP remoto.
Il tooltip identifica la prospettiva con cui verificare intervalli ed evidenze.

Il registro ordina le massimo 2.000 chiamate caricate per data, durata, stato,
metriche o minimo/media/massimo MOS di ciascuna direzione; assenti sempre in fondo.
Colori indicativi: rosso sotto 3, arancio da 3 a meno di 4, verde da 4.
Queste soglie non sono una classificazione certificata della rete.
