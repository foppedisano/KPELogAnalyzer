# Catalogo delle metriche

Questa guida è generata da `app/catalog.py`, la stessa fonte usata da **Guida alle metriche** nell’interfaccia e da `GET /api/catalog`. Rigenerazione: `python scripts/build_metric_docs.py`.

## Regole comuni

- **Prospettiva**: osservazione di una chiamata in una sorgente importata. Non identifica permanentemente un telefono: due export dello stesso dispositivo possono duplicarsi.
- **Downstream / upstream**: rispetto all’app. Incoming RTCP e VD descrivono la ricezione locale (downstream); jitter/loss dei Receiver Report outgoing descrivono la ricezione del peer/GW (upstream). RTT e ping sono bidirezionali. Per xcoder o tratta ignota si mantengono ricezione locale/del peer, senza inversione automatica. Sorgenti senza ruolo dichiarato: app presunta, non identità verificata.
- **Flow / SSRC / device**: restano distinti; non aggregare flussi o destinatari diversi. Il device selezionato nella diagnostica filtra le metriche VD; RTT mostra separatamente tutti i flow/SSRC attribuiti alla prospettiva.
- **sample / gauge**: osservazione al timestamp. **event**: aggiornamento esplicito, senza interpolazione. **counter**: contatore cumulativo soggetto a reset. **interval**: differenza sull’intervallo indicato.
- **last / avg / min / max**: statistiche riportate da KPE, non calcolate dall’analizzatore. Non è nota automaticamente la loro finestra temporale. La media nelle tabelle RTCP è aritmetica sui campioni, non pesata per durata o pacchetti.
- **Unità**: µs ÷ 1000 = ms; ms ÷ 1000 = s. Il DB conserva le metriche VD in ms, compreso il contatore di silenzio; la vista consente di scegliere ms oppure secondi. `raw` significa unità non confermata.
- **Validità**: valori finiti negativi e percentuali fuori 0–100 restano con `valid=0`. Valori mancanti, non numerici, NaN e infinito non diventano zero. La diagnostica esclude i campioni invalidi.
- **Provenienza**: `metrics.event_id` porta a `events` e al file. `source_line` è la riga precisa del campo per il nuovo estrattore; se nulla usare `events.line_no`, inizio del record. `raw_value/raw_unit` preservano la conversione del nuovo estrattore; possono essere null per metriche precedenti.
- **Orologio**: timestamp originali invariati, senza fuso dedotto. L’offset della sorgente, in secondi, si somma solo per allineamento nei grafici e derivazioni diagnostiche. Un offset positivo sposta la sorgente in avanti.
- **Deduplicazione**: osservazioni nuove identiche per sorgente, timestamp, metrica, device, linea, flow, SSRC, valore e tipo sono contate una sola volta. Nessuna deduplicazione tra sorgenti.

## Schede

### Pacchetti mancanti per evento NART — `vd.missing_packets`

**Unità:** packets. **Tipo:** event.

Numero esplicito di pacchetti segnalati come mancanti in un singolo salto della sequenza. Un punto isolato al timestamp del messaggio.

**Origine e calcolo:** [NARTn of Line m] Packet loss occurred … SN delta is … (N missing packets).

**Limiti:** Non è una percentuale RTCP, un contatore cumulativo o una perdita definitiva: riordino, arrivi tardivi e recupero possono modificare l’esito. Non sommare segnalazioni come pacchetti unici persi. Device, linea e sorgente restano separati; nessun SSRC viene inventato. Rotazioni con identico timestamp e identico messaggio sono deduplicate; numeri di sequenza diversi restano eventi distinti.

### RTT RTCP — `rtcp.rtt`

**Unità:** ms. **Tipo:** sample.

Tempo di andata e ritorno riportato per la sorgente RTP/RTCP.

**Origine e calcolo:** RTT to this source: … ms; RTT by this source: … microseconds (÷1000).

**Limiti:** Non è ritardo audio a senso unico. Può includere il percorso verso un relay/PBX. Un picco non localizza il guasto su un endpoint.

### Jitter RTCP — `rtcp.jitter`

**Unità:** ms. **Tipo:** sample.

Variabilità degli arrivi riportata localmente (incoming) o dal peer (outgoing).

**Origine e calcolo:** Jitter we perceive …; Receiver Report - jitter perceived by this remote peer ….

**Limiti:** Separare direzioni, flow e SSRC. Non coincide con occupazione o target del buffer, né con il massimo VD.

### Perdita RTCP — `rtcp.loss`

**Unità:** %. **Tipo:** sample.

Percentuale di perdita riferita all’intervallo dichiarato dal report.

**Origine e calcolo:** Packet loss we perceive …; Receiver Report - remote peer pkt loss ….

**Limiti:** Valori validi da 0 a 100. La media semplice dei report non è la perdita totale ponderata per pacchetti.

### Pacchetti ricevuti — `rtcp.packets_received`

**Unità:** packets. **Tipo:** counter.

Contatore dei pacchetti ricevuti per sorgente.

**Origine e calcolo:** Packet we received from this source (total).

**Limiti:** Può ripartire dopo reset/sessione. Non sommare campioni cumulativi né esportazioni dello stesso dispositivo.

### Ping ICMP — `network.ping`

**Unità:** ms. **Tipo:** sample.

Tempo di andata e ritorno della sonda ICMP.

**Origine e calcolo:** received … bytes … time=… ms.

**Limiti:** La destinazione ICMP può differire dal peer multimediale. Non sostituisce RTT RTCP.

### Massimo ritardo di arrivo NART — `vd.max_arrival_delay`

**Unità:** ms. **Tipo:** event / gauge.

Valore dichiarato dal motore per il massimo ritardo di arrivo. Nei WARNING è un aggiornamento del massimo.

**Origine e calcolo:** m_maxPktArrivalTimeDelay to ms …; campo periodico m_maxPktArrivalTimeDelay (ms): ….

**Limiti:** Il massimo può scendere quando il motore cambia finestra o stato. WARNING rappresentati come punti isolati: non sono campioni periodici del jitter.

### Limite dinamico dejitter — `vd.dejitter_target`

**Unità:** ms. **Tipo:** gauge.

Limite corrente del ring buffer nel device NART selezionato.

**Origine e calcolo:** ring current max buffer usecs (for dynamic dejittering): … (÷1000).

**Limiti:** Non è l’audio effettivamente in coda. Si escludono gli altri device per sezione, non per valore: 20000 µs su NART è un valido campione di 20 ms.

### Audio nel buffer NART — `vd.buffer`

**Unità:** ms. **Tipo:** gauge.

Durata dell’audio presente nel buffer di ricezione NART al momento del campione.

**Origine e calcolo:** buffer len in usecs: … (÷1000); Audio currently in buffer (ms): ….

**Limiti:** È una misura locale, non il ritardo totale della chiamata. I due nomi sono alias empirici; il valore e l’unità originali restano nel DB.

### Silenzio saltato cumulativo — `vd.silence_skipped`

**Unità:** ms (grafico: ms o s). **Tipo:** counter.

Durata cumulativa del silenzio saltato dichiarata dal device. Nel grafico si può scegliere ms oppure dividere ancora per 1000 per mostrare secondi.

**Origine e calcolo:** silence usecs skipped so far: … (÷1000); silence msecs skipped so far: ….

**Limiti:** Non è perdita pacchetti né prova di voce persa. Può azzerarsi: non si presume continuità per tutta la chiamata.

### Incremento silenzio saltato — `derived.silence_delta`

**Unità:** ms. **Tipo:** interval.

Quantità aggiuntiva nel periodo fra i due campioni; mostrata al timestamp del secondo.

**Origine e calcolo:** Differenza tra due campioni consecutivi di vd.silence_skipped, stessa prospettiva e device..

**Limiti:** Il primo valore, un calo del contatore e un intervallo >30 s non producono delta. Non è un tasso al secondo. Entrambi gli eventi sono indicati come evidenza.

### Somma dei buffer A+B — `derived.buffer_sum`

**Unità:** ms. **Tipo:** derived gauge.

Indicatore del buffering combinato dei due punti di vista, utile per confrontare gli andamenti.

**Origine e calcolo:** Somma di vd.buffer dei due device scelti dopo correzione degli orologi; interpolazione lineare nei soli intervalli comuni..

**Limiti:** Non misura il ritardo end-to-end o conversazionale. Non include rete, codec o mixer; i due buffer ricevono direzioni diverse. Niente estrapolazione o interpolazione oltre 30 s. Servono due prospettive distinte, non due copie dello stesso dispositivo.

### Somma dei limiti dinamici A+B — `derived.dejitter_sum`

**Unità:** ms. **Tipo:** derived gauge.

Limiti dinamici combinati dei buffer di ricezione NART; distinto dalla somma dell’audio realmente in coda.

**Origine e calcolo:** Somma di vd.dejitter_target di A e B con interpolazione lineare solo nella copertura comune e con intervalli al massimo di 30 s..

**Limiti:** Non è occupazione effettiva né misura di ritardo conversazionale. Nessuna estrapolazione; la selezione del periodo viene applicata prima della derivazione. Ogni punto conserva le evidenze dei campioni originali.

### Episodio di buffer underrun — `incident.buffer_underrun`

**Unità:** ms. **Tipo:** episode.

Periodo in cui l’osservatore non ottiene audio dal device NART selezionato. La durata dichiarata dal motore resta distinta dalla distanza fra timestamp dei messaggi.

**Origine e calcolo:** Buffer underrun occurred; Still in buffer underrun … Event is currently … msecs; Buffer underrun event terminated … Event was … msecs long..

**Limiti:** AWT (uscita audio) e VD (registrazione) sono osservatori separati: non sommare le loro durate. Senza inizio, un messaggio di fine con durata consente solo di ricavare l’inizio; senza fine l’episodio resta aperto. Contatori periodici e mutedReasons non vengono trasformati in episodi. Derivato su richiesta dagli eventi, non memorizzato in metrics.

### Episodio di media missing — `incident.media_missing`

**Unità:** ms (minimo stimato). **Tipo:** episode.

Assenza RTP segnalata su una linea e un flow. La soglia prima della segnalazione si aggiunge al tempo fino alla ripresa per stimare un limite inferiore della durata.

**Origine e calcolo:** Line … reported that flow … has not received RTP media for more than … sec/ms; has re-started receiving RTP media / has started receiving RTP media again..

**Limiti:** L’inizio effettivo non è misurato: la barra parte dalla segnalazione meno la soglia. Il limite è ricavato dai messaggi e dipende dai tempi di notifica. Ripresa senza segnalazione precedente: durata sconosciuta. Nessuna chiusura viene inventata alla fine della chiamata. Eventi di coda media_missing e riepiloghi non duplicano gli episodi.

### RTT DTMF KPE — `kpe.audio.dtmf_rtt`

**Unità:** raw. **Tipo:** reported statistic.

Statistica KPE denominata dtmf_rtt; semantica dettagliata da confermare col produttore.

**Origine e calcolo:** JSON incoming/outgoing → audio → dtmf_rtt → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Jitter KPE — `kpe.audio.jitter`

**Unità:** raw. **Tipo:** reported statistic.

Statistica del motore denominata jitter.

**Origine e calcolo:** JSON incoming/outgoing → audio → jitter → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Jitter RFC3550 KPE — `kpe.audio.jitter_rfc3550`

**Unità:** raw. **Tipo:** reported statistic.

Statistica del motore etichettata jitter_rfc3550.

**Origine e calcolo:** JSON incoming/outgoing → audio → jitter_rfc3550 → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Perdita jitter KPE — `kpe.audio.ploss_jitter`

**Unità:** raw. **Tipo:** reported statistic.

Statistica del motore denominata ploss_jitter; non equiparata automaticamente alla perdita RTCP.

**Origine e calcolo:** JSON incoming/outgoing → audio → ploss_jitter → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Perdita KPE — `kpe.common.ploss`

**Unità:** raw. **Tipo:** reported statistic.

Statistica del motore denominata ploss.

**Origine e calcolo:** JSON incoming/outgoing → common → ploss → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### RTT KPE — `kpe.common.rtt`

**Unità:** raw. **Tipo:** reported statistic.

Statistica del motore denominata rtt.

**Origine e calcolo:** JSON incoming/outgoing → common → rtt → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Pacchetti RX KPE — `kpe.common.rtp_pkt_rx`

**Unità:** packets. **Tipo:** reported statistic.

Conteggio RTP ricevuto dichiarato dal motore.

**Origine e calcolo:** JSON incoming/outgoing → common → rtp_pkt_rx → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Pacchetti TX KPE — `kpe.common.rtp_pkt_tx`

**Unità:** packets. **Tipo:** reported statistic.

Conteggio RTP trasmesso dichiarato dal motore.

**Origine e calcolo:** JSON incoming/outgoing → common → rtp_pkt_tx → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### MOS a profilo fisso · sola perdita — `derived.mos_reference`

**Unità:** MOS. **Tipo:** derived step.

Indice stimato a profilo costante per confrontare la perdita nelle due direzioni. R=93.2−95p/(p+25.1), limitato a 0–100; MOS=1+0.035R+0.000007R(R−60)(100−R).

**Origine e calcolo:** Perdita RTCP (%) locale o dichiarata dal peer. Profilo loss-reference-1: G.711 10 ms, PLC Appendix I, Ie=0, Bpl=25.1, BurstR=1, R base=93.2..

**Limiti:** Non è qualità vocale misurata né E-model completo. Non valuta jitter, ritardo, scarti, burst o PLC reale. Il report riguarda il passato; il valore viene mantenuto al massimo 30 s fino al report successivo o alla fine chiamata. Report invalidi o discordanti interrompono la curva. Nel pannello MOS il peer è scelto esplicitamente e la sua ricezione locale è riutilizzata. Riferimenti: ITU-T G.107 (2015), G.113 (2024) tabella I.4.

## Lettura del grafico e dei momenti critici

La diagnostica mostra A continuo, B tratteggiato, WARNING come punti isolati; anche i delta sono punti riferiti a intervalli. Le linee si interrompono per distanze superiori a 30 secondi. Il tooltip condiviso mostra per ciascuna serie il campione più vicino entro ±2,5 secondi, con il suo orario effettivo: valori visualizzati insieme non sono necessariamente simultanei. Dove manca un campione compare una lacuna esplicita. Le metriche derivate sono riconoscibili dal prefisso `derived.`.

Le somme A+B (audio occupato e limiti dinamici, mantenute distinte) usano l’unione dei timestamp dei buffer, solo dove entrambi hanno un valore esatto o due campioni distanti al massimo 30 secondi. Fra i due campioni si usa `a + (b-a) × (t-ta)/(tb-ta)`. Non si estrapola. Il JSON esportato conserva tutte le evidenze, incluse le coppie usate nell’interpolazione. Senza copertura comune non si genera una somma. Le metriche derivate sono calcolate su richiesta, non persistite nella tabella `metrics`. Il periodo di analisi filtra i campioni prima delle derivazioni, quindi non si usano campioni fuori finestra. Colori, simboli e visibilità sono configurabili e salvabili. Loss (%) e durate (ms) hanno assi distinti; con silenzio in secondi e tre unità visibili si usano pannelli temporalmente allineati.

I momenti critici riportano il massimo osservato di ciascuna serie con timestamp, evento e file:riga. Le soglie iniziali RTT 200 ms e somma buffer 500 ms sono filtri esplorativi modificabili, non soglie certificate o diagnosi. Il massimo della singola serie non prova correlazione temporale con altri massimi. Occorre verificare contemporaneità, peer effettivo, instradamento e copertura. La piattaforma non assegna automaticamente la responsabilità della rete e non stima MOS o ritardo vocale end-to-end.

## Versione dell’app

Si usa l’ultimo evento `KPE setAppInfo configured with name=…, version=…` della stessa sorgente non successivo all’inizio della prospettiva. Si conserva l’evento di evidenza. Senza marker precedente, la versione è sconosciuta: la presenza di CallInfo o di una particolare metrica non viene usata per indovinarla. Il parser applica i pattern osservati e le unità esplicite, non un’associazione rigida formato/versione. Un marker troppo vecchio in un export incompleto può essere solo un’indicazione: verificare la copertura.

## Riferimenti tecnici

- [RFC 3550, sezione 6.4.1](https://www.rfc-editor.org/rfc/rfc3550.html#section-6.4.1): report RTCP e calcolo RTT.
- [RFC 3611, sezione 4.7.3](https://www.rfc-editor.org/rfc/rfc3611.html#section-4.7.3): distinzione fra ritardo di rete e ritardo degli endpoint.

I nomi interni VD/KPE sono interpretati empiricamente dai log disponibili, senza una specifica proprietaria completa. Una metrica KPE non ancora descritta riceve nella UI una scheda esplicitamente non confermata; non si inventano unità o diagnosi.
