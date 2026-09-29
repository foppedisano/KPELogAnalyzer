# Catalogo delle metriche

Questa guida è generata da `app/catalog.py`, la stessa fonte usata da **Guida alle metriche** nell’interfaccia e da `GET /api/catalog`. Rigenerazione: `python scripts/build_metric_docs.py`.

Per una prima lettura: [capire le metriche](metric-reading.md),
[logica della piattaforma](platform-guide.md) e [grafico multimetriche](call-chart.md).
Le schede sotto sono il riferimento tecnico; il metodo MOS completo è in [mos.md](mos.md).

## Regole comuni

- **Prospettiva**: osservazione di una chiamata in una sorgente importata. Non identifica permanentemente un telefono: due export dello stesso dispositivo possono duplicarsi.
- **Downstream / upstream**: rispetto all’app. Incoming RTCP descrive la ricezione locale (downstream); VD non determina da solo una direzione; jitter/loss dei Receiver Report outgoing descrivono la ricezione del peer/GW (upstream). RTT e ping sono bidirezionali. Per xcoder o tratta ignota si mantengono ricezione locale/del peer, senza inversione automatica. Sorgenti senza ruolo dichiarato: app presunta, non identità verificata.
- **Flow / SSRC / device**: restano distinti; non aggregare flussi o destinatari diversi. Il device selezionato nella diagnostica filtra le metriche VD; RTT mostra separatamente tutti i flow/SSRC attribuiti alla prospettiva.
- **sample / gauge**: osservazione al timestamp. **event**: aggiornamento esplicito, senza interpolazione. **counter**: contatore cumulativo soggetto a reset. **interval**: valore riferito a un intervallo (delta oppure finestra esplicita). **step**: valore mantenuto fino a una scadenza dichiarata; il MOS legacy usa questa rappresentazione.
- **last / avg / min / max**: statistiche riportate da KPE, non calcolate dall’analizzatore. Non è nota automaticamente la loro finestra temporale. La media nelle tabelle RTCP è aritmetica sui campioni, non pesata per durata o pacchetti.
- **Unità**: µs ÷ 1000 = ms; ms ÷ 1000 = s. Il DB conserva le metriche VD in ms, compreso il contatore di silenzio; Diagnostica A/B consente di scegliere ms oppure secondi; il grafico della chiamata mantiene ms. `raw` significa unità non confermata.
- **Validità**: valori finiti negativi e percentuali fuori 0–100 restano con `valid=0`. Valori mancanti, non numerici, NaN e infinito non diventano zero. La diagnostica esclude i campioni invalidi.
- **Provenienza**: `metrics.event_id` porta a `events` e al file. `source_line` è la riga precisa del campo per il nuovo estrattore; se nulla usare `events.line_no`, inizio del record. `raw_value/raw_unit` preservano la conversione del nuovo estrattore; possono essere null per metriche precedenti.
- **Orologio**: timestamp originali invariati, senza fuso dedotto. L’offset della sorgente, in secondi, si somma solo per allineamento nei grafici e derivazioni diagnostiche. Un offset positivo sposta la sorgente in avanti.
- **Deduplicazione**: osservazioni nuove identiche per sorgente, timestamp, metrica, device, linea, flow, SSRC, valore e tipo sono contate una sola volta. Per i log tradizionali si ignorano le chiamate già presenti quando il produttore è riconosciuto con prove locali concordanti; le copie storiche restano consultabili. Vedi [identità della sorgente](source-dedup.md). La telemetria strutturata deduplica source_id/event_id tra ZIP; la mappa ha regole proprie di unione delle evidenze sovrapposte. Vedi [logica della piattaforma](platform-guide.md).

## Osservazioni periodiche recenti

Schema 11: osservatore, output, input e ciclo di vita sono dimensioni separate.
I contatori per VOD descrivono il rapporto lettore/input. `a_counter_intervals`
restituisce entrambi gli eventi, reset, invalidità, conflitti e gap oltre 30 s.
I delta non localizzano il silenzio dentro l’intervallo e non si sommano agli
Episodi. I clock e stati sono in `periodic_metadata`, non nelle curve numeriche.
I dati senza associazione univoca rimangono non attribuiti. Copertura e metadati
sono disponibili anche tramite API analitiche e MCP.

## Media plane VDK: device e interpretazione

Gerarchia e funzionamento confermati dal referente VDK; unità e campi specifici restano vincolati alle evidenze dei log.

| Nome | Classe padre | Denominazione | Ruolo |
|---|---|---|---|
| VD | — | Virtual Device | Classe generale; ogni VD opera nel proprio thread. |
| VID | VD | Virtual Input Device | Introduce media nel grafo e lo distribuisce a tutti i VOD connessi. |
| VOD | VD | Virtual Output Device | Riceve media dai VID connessi, li miscela e scrive sulla propria destinazione. |
| VAID | VID | Virtual Audio Input Device | Ramo audio degli input virtuali. |
| VAOD | VOD | Virtual Audio Output Device | Ramo audio degli output virtuali. |
| VVID | VID | Virtual Video Input Device | Ramo video; non presente nei log KPE attuali. |
| VVOD | VOD | Virtual Video Output Device | Ramo video; non presente nei log KPE attuali. |
| NART | VAID | Network Audio Reader Thread | Legge il media ricevuto dalla rete RTP. |
| NAWT | VAOD | Network Audio Writer Thread | Scrive il media da trasmettere sulla rete RTP. |
| ART | VAID | Audio Reader Thread | Legge dalla scheda audio o equivalente: ruolo del microfono. |
| AWT | VAOD | Audio Writer Thread | Scrive sulla scheda audio o equivalente: ruolo degli speaker. |
| FileReaderThread | VAID | FileReaderThread | Legge media da file. |
| FileWriterThread | VAOD | FileWriterThread | Scrive media su file. |

- Input/output si riferiscono al grafo interno del media plane, non al chiamante/chiamato. KPE attualmente tratta solo audio.
- Le connessioni VID → VOD sono molti-a-molti: un VID distribuisce a più VOD; un VOD miscela più VID. ART → NAWT e NART → AWT sono percorsi elementari, non topologie da presumere nei log.
- Ogni VD ha un thread. Le statistiche comuni di scheduling descrivono la temporizzazione locale; non sono direttamente jitter o perdita di rete.
- Le statistiche specifiche NART descrivono la ricezione RTP osservata localmente. Il thread ricevente è soggetto allo scheduling: i soli sintomi non separano automaticamente rete e ritardi locali.
- RTP trasporta il media; SIP appartiene alla segnalazione. RTCP riporta statistiche del trasporto RTP.
- VD è una classe generale, non sinonimo di registrazione su file. Un nome VD generico non dimostra la destinazione; occorre il device specializzato o altra evidenza esplicita.
- Distinguere stato del thread, ricezione RTP, disponibilità del buffer e conseguenze sul media. Underrun e silenzio riprodotto non provano da soli perdita di rete o qualità percepita.
- Il prefisso storico vd. identifica una famiglia di metriche, non una classe concreta né una direzione. Anche un NART può esporre scheduling e buffer oltre alle statistiche RTP.

### Contesto delle osservazioni

- `observer`: Emittente/osservatore del messaggio: non automaticamente il device misurato.
- `output_device`: VOD della sezione di uscita; il suo output può essere un mix di più VID.
- `input_device`: VID collegato nella sezione corrente; mantenere distinta ogni relazione VID/VOD.
- `device`: Device cui appartiene il campo corrente; non dedurne la classe dal solo prefisso della metrica.
- `lifecycle`: Ciclo delimitato da creazioni osservate; unknown non dimostra continuità.
- `direction`: Direzione osservata del trasporto; distinta da VID/VOD. outgoing nei report RTCP descrive la ricezione del peer.

## Schede

### Perdita RTP su intervallo verificato — `telemetry.network_loss`

**Unità:** %. **Tipo:** interval.

Perdita riferita a una finestra esplicita, prima di PLC/FEC e scarti di playout. Timestamp UTC derivato dal tempo monotono; originali ed evidenze conservati.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Telemetria strutturata: rtp-sequence-window/1 oppure delta dei contatori RTCP SR/RR..

**Limiti:** Contatori di arrivo e attesi non sono sottratti senza una coorte comune. Reset, conflitti, finestre sovrapposte e gap RTCP oltre 30 s escludono la derivazione. Non è una misura di qualità percepita. Per i report remoti il tempo è quello locale di osservazione dei report, non una sincronizzazione con il peer.

### Pacchetti mancanti per evento NART — `vd.missing_packets`

**Unità:** packets. **Tipo:** event.

Numero esplicito di pacchetti segnalati come mancanti in un singolo salto della sequenza. Un punto isolato al timestamp del messaggio.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** [NARTn of Line m] Packet loss occurred … SN delta is … (N missing packets).

**Limiti:** Non è una percentuale RTCP, un contatore cumulativo o una perdita definitiva: riordino, arrivi tardivi e recupero possono modificare l’esito. Non sommare segnalazioni come pacchetti unici persi. Device, linea e sorgente restano separati; nessun SSRC viene inventato. Rotazioni con identico timestamp e identico messaggio sono deduplicate; numeri di sequenza diversi restano eventi distinti. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### RTT RTCP — `rtcp.rtt`

**Unità:** ms. **Tipo:** sample.

Tempo di andata e ritorno riportato per la sorgente RTP/RTCP.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** RTT to this source: … ms; RTT by this source: … microseconds (÷1000).

**Limiti:** Non è ritardo audio a senso unico. Può includere il percorso verso un relay/PBX. Un picco non localizza il guasto su un endpoint.

### Jitter RTCP — `rtcp.jitter`

**Unità:** ms. **Tipo:** sample.

Variabilità degli arrivi riportata localmente (incoming) o dal peer (outgoing).

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Jitter we perceive …; Receiver Report - jitter perceived by this remote peer ….

**Limiti:** Separare direzioni, flow e SSRC. Non coincide con occupazione o target del buffer, né con il massimo VD.

### Perdita RTCP — `rtcp.loss`

**Unità:** %. **Tipo:** sample.

Percentuale di perdita riferita all’intervallo dichiarato dal report.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Packet loss we perceive …; Receiver Report - remote peer pkt loss ….

**Limiti:** Valori validi da 0 a 100. La media semplice dei report non è la perdita totale ponderata per pacchetti.

### Pacchetti ricevuti — `rtcp.packets_received`

**Unità:** packets. **Tipo:** counter.

Contatore dei pacchetti ricevuti per sorgente.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Packet we received from this source (total).

**Limiti:** Può ripartire dopo reset/sessione. Non sommare campioni cumulativi né esportazioni dello stesso dispositivo.

### Ping ICMP — `network.ping`

**Unità:** ms. **Tipo:** sample.

Tempo di andata e ritorno della sonda ICMP.

**Ambito:** Sonda di rete. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** received … bytes … time=… ms.

**Limiti:** La destinazione ICMP può differire dal peer multimediale. Non sostituisce RTT RTCP.

### Massimo ritardo di arrivo NART — `vd.max_arrival_delay`

**Unità:** ms. **Tipo:** event / gauge.

Valore dichiarato dal motore per il massimo ritardo di arrivo. Nei WARNING è un aggiornamento del massimo.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** m_maxPktArrivalTimeDelay to ms …; campo periodico m_maxPktArrivalTimeDelay (ms): ….

**Limiti:** Il massimo può scendere quando il motore cambia finestra o stato. WARNING rappresentati come punti isolati: non sono campioni periodici del jitter. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Limite dinamico dejitter — `vd.dejitter_target`

**Unità:** ms. **Tipo:** gauge.

Limite corrente del ring buffer nel device indicato nel contesto; su NART sostiene il dejittering della ricezione RTP.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** ring current max buffer usecs (for dynamic dejittering): … (÷1000).

**Limiti:** Non è l’audio effettivamente in coda. Si escludono gli altri device per sezione, non per valore: 20000 µs su NART è un valido campione di 20 ms. Nel formato recente sono conservate anche sezioni non NART, con contesto proprio. Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Audio nel buffer del device — `vd.buffer`

**Unità:** ms. **Tipo:** gauge.

Durata dell’audio presente nel buffer del device indicato nel contesto; su NART riguarda la ricezione RTP, sugli altri VID la rispettiva sorgente media.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** buffer len in usecs: … (÷1000); Audio currently in buffer (ms): ….

**Limiti:** È una misura locale, non il ritardo totale della chiamata. I due nomi sono alias empirici; il valore e l’unità originali restano nel DB. Nel formato recente sono conservate anche sezioni non NART, con contesto proprio. Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Silenzio saltato cumulativo — `vd.silence_skipped`

**Unità:** ms (grafico: ms o s). **Tipo:** counter.

Durata cumulativa del silenzio saltato dichiarata dal device. In Diagnostica A/B si può scegliere ms oppure dividere ancora per 1000 per mostrare secondi; nel dettaglio chiamata resta in ms.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** silence usecs skipped so far: … (÷1000); silence msecs skipped so far: ….

**Limiti:** Non è perdita pacchetti né prova di voce persa. Può azzerarsi: non si presume continuità per tutta la chiamata. Nel formato recente sono conservate anche sezioni non NART, con contesto proprio. Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Incremento silenzio saltato — `derived.silence_delta`

**Unità:** ms. **Tipo:** interval.

Quantità aggiuntiva nel periodo fra i due campioni; mostrata al timestamp del secondo.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Differenza tra due campioni consecutivi di vd.silence_skipped, stessa prospettiva e device..

**Limiti:** Il primo valore, un calo del contatore e un intervallo >30 s non producono delta. Non è un tasso al secondo. Entrambi gli eventi sono indicati come evidenza.

### Somma dei buffer A+B — `derived.buffer_sum`

**Unità:** ms. **Tipo:** derived gauge.

Indicatore del buffering combinato dei due punti di vista, utile per confrontare gli andamenti.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Somma di vd.buffer dei due device scelti dopo correzione degli orologi; interpolazione lineare nei soli intervalli comuni..

**Limiti:** Non misura il ritardo end-to-end o conversazionale. Non include rete, codec o mixer; i due buffer ricevono direzioni diverse. Niente estrapolazione o interpolazione oltre 30 s. Servono due prospettive distinte, non due copie dello stesso dispositivo.

### Somma dei limiti dinamici A+B — `derived.dejitter_sum`

**Unità:** ms. **Tipo:** derived gauge.

Limiti dinamici combinati dei buffer di ricezione NART; distinto dalla somma dell’audio realmente in coda.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Somma di vd.dejitter_target di A e B con interpolazione lineare solo nella copertura comune e con intervalli al massimo di 30 s..

**Limiti:** Non è occupazione effettiva né misura di ritardo conversazionale. Nessuna estrapolazione; la selezione del periodo viene applicata prima della derivazione. Ogni punto conserva le evidenze dei campioni originali.

### Episodio di buffer underrun — `incident.buffer_underrun`

**Unità:** ms. **Tipo:** episode.

Periodo in cui l’osservatore non ottiene audio dal device NART selezionato. La durata dichiarata dal motore resta distinta dalla distanza fra timestamp dei messaggi.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Buffer underrun occurred; Still in buffer underrun … Event is currently … msecs; Buffer underrun event terminated … Event was … msecs long..

**Limiti:** AWT (uscita audio) e gli altri VD osservati restano separati; VD generico non identifica una registrazione su file: non sommare le loro durate. Senza inizio, un messaggio di fine con durata consente solo di ricavare l’inizio; senza fine l’episodio resta aperto. Contatori periodici e mutedReasons non vengono trasformati in episodi. Derivato su richiesta dagli eventi, non memorizzato in metrics.

### Episodio di media missing — `incident.media_missing`

**Unità:** ms (minimo stimato). **Tipo:** episode.

Assenza RTP segnalata su una linea e un flow. La soglia prima della segnalazione si aggiunge al tempo fino alla ripresa per stimare un limite inferiore della durata.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Line … reported that flow … has not received RTP media for more than … sec/ms; has re-started receiving RTP media / has started receiving RTP media again..

**Limiti:** L’inizio effettivo non è misurato: la barra parte dalla segnalazione meno la soglia. Il limite è ricavato dai messaggi e dipende dai tempi di notifica. Ripresa senza segnalazione precedente: durata sconosciuta. Nessuna chiusura viene inventata alla fine della chiamata. Eventi di coda media_missing e riepiloghi non duplicano gli episodi.

### RTT DTMF KPE — `kpe.audio.dtmf_rtt`

**Unità:** raw. **Tipo:** reported statistic.

Statistica KPE denominata dtmf_rtt; semantica dettagliata da confermare col produttore.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → audio → dtmf_rtt → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Jitter KPE — `kpe.audio.jitter`

**Unità:** raw. **Tipo:** reported statistic.

Statistica del motore denominata jitter.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → audio → jitter → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Jitter RFC3550 KPE — `kpe.audio.jitter_rfc3550`

**Unità:** raw. **Tipo:** reported statistic.

Statistica del motore etichettata jitter_rfc3550.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → audio → jitter_rfc3550 → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Perdita jitter KPE — `kpe.audio.ploss_jitter`

**Unità:** raw. **Tipo:** reported statistic.

Statistica del motore denominata ploss_jitter; non equiparata automaticamente alla perdita RTCP.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → audio → ploss_jitter → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Perdita KPE — `kpe.common.ploss`

**Unità:** raw. **Tipo:** reported statistic.

Statistica del motore denominata ploss.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → common → ploss → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### RTT KPE — `kpe.common.rtt`

**Unità:** raw. **Tipo:** reported statistic.

Statistica del motore denominata rtt.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → common → rtt → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Pacchetti RX KPE — `kpe.common.rtp_pkt_rx`

**Unità:** packets. **Tipo:** reported statistic.

Conteggio RTP ricevuto dichiarato dal motore.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → common → rtp_pkt_rx → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Pacchetti TX KPE — `kpe.common.rtp_pkt_tx`

**Unità:** packets. **Tipo:** reported statistic.

Conteggio RTP trasmesso dichiarato dal motore.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → common → rtp_pkt_tx → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### MOS a profilo fisso · sola perdita — `derived.mos_reference`

**Unità:** MOS. **Tipo:** derived step.

Indice stimato a profilo costante per confrontare la perdita nelle due direzioni. R=93.2−95p/(p+25.1), limitato a 0–100; MOS=1+0.035R+0.000007R(R−60)(100−R).

**Ambito:** Modello di qualità derivato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Perdita RTCP (%) locale o dichiarata dal peer, oppure perdita da finestre strutturate verificate. Profilo loss-reference-1: G.711 10 ms, PLC Appendix I, Ie=0, Bpl=25.1, BurstR=1, R base=93.2..

**Limiti:** Non è qualità vocale misurata né E-model completo. Non valuta jitter, ritardo, scarti, burst o PLC reale. Nei log tradizionali il report riguarda il passato; il valore viene mantenuto al massimo 30 s fino al report successivo o alla fine chiamata. La telemetria verificata descrive invece la sua finestra esplicita già osservata. Report invalidi o discordanti interrompono la curva. Nel pannello MOS il peer è scelto esplicitamente e la sua ricezione locale è riutilizzata. Riferimenti: ITU-T G.107 (2015), G.113 (2024) tabella I.4.

### audio samples skipped so far — `vd.samples_skipped`

**Unità:** samples. **Tipo:** counter.

Numero cumulativo di campioni audio saltati dal device. Campioni audio e pacchetti RTP sono grandezze diverse.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** audio samples skipped so far.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### ring hard max buffer usecs — `vd.buffer_hard_max`

**Unità:** ms. **Tipo:** gauge.

Limite massimo rigido del ring buffer dichiarato dal device; non occupazione effettiva.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** ring hard max buffer usecs (µs ÷ 1000; originali raw_value/raw_unit).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### ring min buffer usecs — `vd.buffer_min`

**Unità:** ms. **Tipo:** gauge.

Limite minimo del ring buffer dichiarato dal device; non minimo misurato sull’intera chiamata.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** ring min buffer usecs (µs ÷ 1000; originali raw_value/raw_unit).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Numero cumulativo di underrun del lettore — `vd.underruns`

**Unità:** count. **Tipo:** counter.

Numero cumulativo di underrun del ring per lo specifico VOD lettore e VID collegato. Non è il conteggio complessivo di guasti della chiamata.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** number of buffer underruns occurred on this ring for this VOD.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Silenzio riprodotto per underrun, cumulativo — `vd.silence_played`

**Unità:** ms. **Tipo:** counter.

Durata cumulativa del silenzio riprodotto per compensare underrun del ring per lo specifico VOD e VID. Non prova silenzio della sorgente o perdita RTP.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** silence msecs played out for buffer underruns occurred on this ring for this VOD.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Total bytes read from source — `vd.bytes_read`

**Unità:** bytes. **Tipo:** counter.

Byte cumulativi letti dalla sorgente del device: rete, scheda audio o file secondo la specializzazione osservata. Non automaticamente traffico RTP.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Total bytes read from source.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Total bytes sent to decoder — `vd.bytes_decoder`

**Unità:** bytes. **Tipo:** counter.

Byte cumulativi inviati al decoder, non necessariamente byte ricevuti sulla rete.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Total bytes sent to decoder.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Total packets/chunks sent to decoder — `vd.chunks_decoder`

**Unità:** chunks. **Tipo:** counter.

Pacchetti/chunk cumulativi inviati al decoder. Chunk non equivale automaticamente a datagramma RTP.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Total packets/chunks sent to decoder.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Total media read from middleware — `vd.media_read`

**Unità:** ms. **Tipo:** counter.

Durata cumulativa del media letto dal middleware. Non è tempo CPU, latenza o durata della chiamata. Usare ms solo con suffisso esplicito, altrimenti raw.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Total media read from middleware.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Total media sent out — `vd.media_sent`

**Unità:** ms. **Tipo:** counter.

Durata cumulativa del media inviato in uscita. Non è tempo CPU, latenza o durata della chiamata. Usare ms solo con suffisso esplicito, altrimenti raw.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Total media sent out.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Total media sent to middleware — `vd.media_middleware`

**Unità:** ms. **Tipo:** counter.

Durata cumulativa del media inviato al middleware. Non è tempo CPU, latenza o durata della chiamata. Usare ms solo con suffisso esplicito, altrimenti raw.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Total media sent to middleware.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Number of device reset for scheduling delay — `vd.scheduling_resets`

**Unità:** count. **Tipo:** counter.

Numero di reset che il device attribuisce a ritardo di scheduling. Non è un conteggio di pacchetti persi o di reset della rete.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Number of device reset for scheduling delay.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### ALL Pkts received so far — `vd.packets_all`

**Unità:** packets. **Tipo:** counter.

Conteggio di ricezione dichiarato per la categoria del campo sorgente; mantenere separati totale, RTP, RTCP e sequenze GOOD/BAD. GOOD/BAD è una classificazione del motore, non una definizione confermata di perdita o qualità vocale.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** ALL Pkts received so far.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### RTP Pkts received so far — `vd.packets_rtp`

**Unità:** packets. **Tipo:** counter.

Conteggio di ricezione dichiarato per la categoria del campo sorgente; mantenere separati totale, RTP, RTCP e sequenze GOOD/BAD. GOOD/BAD è una classificazione del motore, non una definizione confermata di perdita o qualità vocale.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** RTP Pkts received so far.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### RTCP Pkts received so far — `vd.packets_rtcp`

**Unità:** packets. **Tipo:** counter.

Conteggio di ricezione dichiarato per la categoria del campo sorgente; mantenere separati totale, RTP, RTCP e sequenze GOOD/BAD. GOOD/BAD è una classificazione del motore, non una definizione confermata di perdita o qualità vocale.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** RTCP Pkts received so far.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### RTP GOOD Pkts received so far — `vd.packets_rtp_good`

**Unità:** packets. **Tipo:** counter.

Conteggio di ricezione dichiarato per la categoria del campo sorgente; mantenere separati totale, RTP, RTCP e sequenze GOOD/BAD. GOOD/BAD è una classificazione del motore, non una definizione confermata di perdita o qualità vocale.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** RTP GOOD Pkts received so far.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### RTP BAD Pkts received so far — `vd.packets_rtp_bad`

**Unità:** packets. **Tipo:** counter.

Conteggio di ricezione dichiarato per la categoria del campo sorgente; mantenere separati totale, RTP, RTCP e sequenze GOOD/BAD. GOOD/BAD è una classificazione del motore, non una definizione confermata di perdita o qualità vocale.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** RTP BAD Pkts received so far.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Number of Read Errors — `vd.read_errors`

**Unità:** count. **Tipo:** counter.

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Numero cumulativo di errori dichiarati. La fase e il device non identificano automaticamente la causa di rete.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Number of Read Errors.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Current read error event duration (msecs) — `vd.read_error_duration`

**Unità:** ms. **Tipo:** gauge.

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Durata dell’evento di errore corrente, non totale cumulativo. La fase e il device non identificano automaticamente la causa di rete.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Current read error event duration (msecs).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Number of Write Errors — `vd.write_errors`

**Unità:** count. **Tipo:** counter.

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Numero cumulativo di errori dichiarati. La fase e il device non identificano automaticamente la causa di rete.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Number of Write Errors.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Current write error event duration (msecs) — `vd.write_error_duration`

**Unità:** ms. **Tipo:** gauge.

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Durata dell’evento di errore corrente, non totale cumulativo. La fase e il device non identificano automaticamente la causa di rete.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Current write error event duration (msecs).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Number of Encoding Errors — `vd.encoding_errors`

**Unità:** count. **Tipo:** counter.

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Numero cumulativo di errori dichiarati. La fase e il device non identificano automaticamente la causa di rete.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Number of Encoding Errors.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Current encoding error event duration (msecs) — `vd.encoding_error_duration`

**Unità:** ms. **Tipo:** gauge.

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Durata dell’evento di errore corrente, non totale cumulativo. La fase e il device non identificano automaticamente la causa di rete.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Current encoding error event duration (msecs).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Number of Decoding Errors — `vd.decoding_errors`

**Unità:** count. **Tipo:** counter.

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Numero cumulativo di errori dichiarati. La fase e il device non identificano automaticamente la causa di rete.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Number of Decoding Errors.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Current decoding error event duration (msecs) — `vd.decoding_error_duration`

**Unità:** ms. **Tipo:** gauge.

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Durata dell’evento di errore corrente, non totale cumulativo. La fase e il device non identificano automaticamente la causa di rete.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Current decoding error event duration (msecs).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### RTP last streak of GOOD Pkts received — `vd.streak_good`

**Unità:** packets. **Tipo:** gauge.

Conteggio di ricezione dichiarato per la categoria del campo sorgente; mantenere separati totale, RTP, RTCP e sequenze GOOD/BAD. GOOD/BAD è una classificazione del motore, non una definizione confermata di perdita o qualità vocale.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** RTP last streak of GOOD Pkts received.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### RTP last streak of BAD Pkts received — `vd.streak_bad`

**Unità:** packets. **Tipo:** gauge.

Conteggio di ricezione dichiarato per la categoria del campo sorgente; mantenere separati totale, RTP, RTCP e sequenze GOOD/BAD. GOOD/BAD è una classificazione del motore, non una definizione confermata di perdita o qualità vocale.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** RTP last streak of BAD Pkts received.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Frequenza cumulativa di scrittura — `vd.write_rate`

**Unità:** samples/s. **Tipo:** gauge.

Frequenza di scrittura riportata dal device in campioni/s. Non è bitrate di rete e non dimostra da sola regolarità dello scheduling.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Frequenza cumulativa di scrittura.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Ritardo accumulato di scheduling — `vd.scheduling_delay`

**Unità:** ms. **Tipo:** counter.

Ritardo accumulato di scheduling dichiarato dal thread del VD. Descrive la temporizzazione locale, non il tempo di transito RTP.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Ritardo accumulato di scheduling.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Durata corrente underrun del lettore — `vd.underrun_duration`

**Unità:** ms. **Tipo:** gauge.

Durata dichiarata dell’underrun attualmente in corso per il lettore/input osservato; non contatore cumulativo né durata totale della chiamata.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Durata corrente underrun del lettore.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Byte letti heartbeat — `vd.heartbeat_bytes_read`

**Unità:** bytes. **Tipo:** reported statistic.

Byte letti riportati dal thread nel messaggio heartbeat; finestra dei byte non confermata. Non derivare un bitrate dividendo per la finestra dei cicli.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Byte letti heartbeat.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Byte scritti heartbeat — `vd.heartbeat_bytes_written`

**Unità:** bytes. **Tipo:** reported statistic.

Byte scritti riportati dal thread nel messaggio heartbeat; finestra dei byte non confermata. Non derivare un bitrate dividendo per la finestra dei cicli.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Byte scritti heartbeat.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Finestra cicli heartbeat — `vd.heartbeat_window`

**Unità:** ms. **Tipo:** interval.

Finestra last ms dichiarata per i conteggi dei cicli heartbeat. Non è ritardo di scheduling né intervallo confermato per i byte.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Finestra cicli heartbeat.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli Tbody Runs — `vd.cycles_tbody_runs`

**Unità:** count. **Tipo:** counter / reported statistic.

Conteggio riportato per la fase tbody_runs. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Cicli Tbody Runs.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli Read — `vd.cycles_read`

**Unità:** count. **Tipo:** counter / reported statistic.

Conteggio riportato per la fase read. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Cicli Read.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli Decode — `vd.cycles_decode`

**Unità:** count. **Tipo:** counter / reported statistic.

Conteggio riportato per la fase decode. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Cicli Decode.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli AdaptToMw — `vd.cycles_adapttomw`

**Unità:** count. **Tipo:** counter / reported statistic.

Conteggio riportato per la fase adapttomw. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Cicli AdaptToMw.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli Append — `vd.cycles_append`

**Unità:** count. **Tipo:** counter / reported statistic.

Conteggio riportato per la fase append. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Cicli Append.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli ReadFromMW — `vd.cycles_readfrommw`

**Unità:** count. **Tipo:** counter / reported statistic.

Conteggio riportato per la fase readfrommw. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Cicli ReadFromMW.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli AdaptToCodec — `vd.cycles_adapttocodec`

**Unità:** count. **Tipo:** counter / reported statistic.

Conteggio riportato per la fase adapttocodec. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Cicli AdaptToCodec.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli Encode — `vd.cycles_encode`

**Unità:** count. **Tipo:** counter / reported statistic.

Conteggio riportato per la fase encode. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Cicli Encode.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli Write — `vd.cycles_write`

**Unità:** count. **Tipo:** counter / reported statistic.

Conteggio riportato per la fase write. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running Info / alive and kicking: Cicli Write.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Pacchetti inviati dal peer, totale — `rtcp.packets_sent_total`

**Unità:** packets. **Tipo:** counter.

Pacchetti inviati dal peer, totale. Numeri esponenziali accettati; conteggi finiti negativi o non interi restano invalidi.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Campo numerico esplicito Sender/Receiver Report RTCP.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Non derivare perdita da contatori senza coorte comune.

### Pacchetti inviati dal peer, intervallo — `rtcp.packets_sent_interval`

**Unità:** packets. **Tipo:** interval.

Pacchetti inviati dal peer, intervallo. Numeri esponenziali accettati; conteggi finiti negativi o non interi restano invalidi.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Campo numerico esplicito Sender/Receiver Report RTCP.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Non derivare perdita da contatori senza coorte comune.

### Pacchetti ricevuti, intervallo — `rtcp.packets_received_interval`

**Unità:** packets. **Tipo:** interval.

Pacchetti ricevuti, intervallo. Numeri esponenziali accettati; conteggi finiti negativi o non interi restano invalidi.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Campo numerico esplicito Sender/Receiver Report RTCP.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Non derivare perdita da contatori senza coorte comune.

### Pacchetti persi dal peer, totale — `rtcp.packets_lost_total`

**Unità:** packets. **Tipo:** counter.

Pacchetti persi dal peer, totale. Numeri esponenziali accettati; conteggi finiti negativi o non interi restano invalidi.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Campo numerico esplicito Sender/Receiver Report RTCP.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Non derivare perdita da contatori senza coorte comune.

### Pacchetti persi dal peer, intervallo — `rtcp.packets_lost_interval`

**Unità:** packets. **Tipo:** interval.

Pacchetti persi dal peer, intervallo. Numeri esponenziali accettati; conteggi finiti negativi o non interi restano invalidi.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Campo numerico esplicito Sender/Receiver Report RTCP.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Non derivare perdita da contatori senza coorte comune.

### Incremento silenzio riprodotto per underrun — `derived.silence_played_delta`

**Unità:** ms. **Tipo:** interval.

Silenzio aggiunto al ring per quello specifico lettore/input tra due osservazioni.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Differenza consecutiva di vd.silence_played nello stesso contesto, massimo 30 s, evidenze dei due campioni..

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Confrontare con episodi, senza sommare le due misure. Non è occupazione a precisione di un secondo.

## Stati e metadati periodici

- `vd.currently_in_*` (boolean): Stati total/partial/VOD underrun e read/write/encoding/decoding error; scope del device corrente.
- `vd.current_processing_stage / vd.last_read_processing_stage_known / vd.last_write_processing_stage_known / vd.monitor_stage` (object): state, code e timestamp osservato; nessuna conversione di fuso o latenza. Monitor: flow ignoto, non quello hardcoded.
- `vd.last_written_rtp_sn / vd.rtp_*_sn / vd.rtp_*_roc` (integer): SN e ROC riportati, non perdite; conservare separati e considerare wrap.
- `vd.heartbeat_device_id` (string): Identificatore VD osservato nel messaggio, non SSRC.
- `rtcp.message_number / rtcp.rtp_timestamp` (integer or string): Identificatore/clock osservato; testo preservato se non intero.
- `rtcp.ntp_timestamp` (string): Clock remoto come scritto, senza fuso dedotto o conversione in latenza.

## Lettura del grafico e dei momenti critici

Nel dettaglio chiamata e in Confronta, **Aggiungi metriche** seleziona più parametri.
Stessa unità: stesso pannello; unità diverse: pannelli temporalmente sincronizzati.
Le metriche raw rimangono separate. I conteggi hanno tacche intere, le percentuali
possono avere decimali. Il MOS normale usa scala 1–5. Le etichette × rimuovono
metriche; la legenda nasconde serie. Le statistiche sono per serie, senza mescolare
unità, sorgenti o flussi. MOS e finestre esplicite usano l’intervallo di validità
nel tooltip; gli altri punti usano la tolleranza indicata. [Guida](call-chart.md).


La diagnostica mostra A continuo, B tratteggiato, WARNING come punti isolati; anche i delta sono punti riferiti a intervalli. Le linee si interrompono per distanze superiori a 30 secondi. Il tooltip condiviso mostra per ciascuna serie il campione più vicino entro ±2,5 secondi, con il suo orario effettivo: valori visualizzati insieme non sono necessariamente simultanei. Dove manca un campione compare una lacuna esplicita. Le metriche derivate sono riconoscibili dal prefisso `derived.`.

Le somme A+B (audio occupato e limiti dinamici, mantenute distinte) usano l’unione dei timestamp dei buffer, solo dove entrambi hanno un valore esatto o due campioni distanti al massimo 30 secondi. Fra i due campioni si usa `a + (b-a) × (t-ta)/(tb-ta)`. Non si estrapola. Il JSON esportato conserva tutte le evidenze, incluse le coppie usate nell’interpolazione. Senza copertura comune non si genera una somma. Le metriche derivate sono calcolate su richiesta, non persistite nella tabella `metrics`. Il periodo di analisi filtra i campioni prima delle derivazioni, quindi non si usano campioni fuori finestra. Colori, simboli e visibilità sono configurabili e salvabili. Loss (%) e durate (ms) hanno assi distinti; con silenzio in secondi e tre unità visibili si usano pannelli temporalmente allineati.

I momenti critici riportano il massimo osservato di ciascuna serie con timestamp, evento e file:riga. Le soglie iniziali RTT 200 ms e somma buffer 500 ms sono filtri esplorativi modificabili, non soglie certificate o diagnosi. Il massimo della singola serie non prova correlazione temporale con altri massimi. Occorre verificare contemporaneità, peer effettivo, instradamento e copertura. La piattaforma non assegna automaticamente la responsabilità della rete. Il MOS a profilo fisso valuta solo la perdita; il ritardo vocale end-to-end non è misurato.

## Versione dell’app

Si usa l’ultimo evento `KPE setAppInfo configured with name=…, version=…` della stessa sorgente non successivo all’inizio della prospettiva. Si conserva l’evento di evidenza. Senza marker precedente, la versione è sconosciuta: la presenza di CallInfo o di una particolare metrica non viene usata per indovinarla. Il parser applica i pattern osservati e le unità esplicite, non un’associazione rigida formato/versione. Un marker troppo vecchio in un export incompleto può essere solo un’indicazione: verificare la copertura.

## Riferimenti tecnici

- [RFC 3550, sezione 6.4.1](https://www.rfc-editor.org/rfc/rfc3550.html#section-6.4.1): report RTCP e calcolo RTT.
- [RFC 3611, sezione 4.7.3](https://www.rfc-editor.org/rfc/rfc3611.html#section-4.7.3): distinzione fra ritardo di rete e ritardo degli endpoint.

La gerarchia VD è confermata dal referente VDK. I singoli campi e le unità restano interpretati secondo le evidenze disponibili, senza una specifica proprietaria completa. Una metrica KPE non ancora descritta riceve nella UI una scheda esplicitamente non confermata; non si inventano unità o diagnosi.
