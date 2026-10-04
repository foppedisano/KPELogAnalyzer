# Catalogo delle metriche

Questa guida è generata da `app/catalog.py`, la stessa fonte usata da **Guida alle metriche** nell’interfaccia e da `GET /api/catalog`. Rigenerazione: `python scripts/build_metric_docs.py`.

Per una prima lettura: [capire le metriche](metric-reading.md),
[logica della piattaforma](platform-guide.md) e [grafico multimetriche](call-chart.md).
Le schede sotto sono il riferimento tecnico; i metodi completi sono in [MOS](mos.md)
e [Perceptual Quality: celle dirette, stime e percorsi](perceptual-quality.md).

## Regole comuni

- **Prospettiva**: osservazione di una chiamata in una sorgente importata. Non identifica permanentemente un telefono: due export dello stesso dispositivo possono duplicarsi.
- **Downstream / upstream**: rispetto all’app. Incoming RTCP descrive la ricezione locale (downstream); VD non determina da solo una direzione; jitter/loss dei Receiver Report outgoing descrivono la ricezione del peer/GW (upstream). RTT e ping sono bidirezionali. Per xcoder o tratta ignota si mantengono ricezione locale/del peer, senza inversione automatica. Sorgenti senza ruolo dichiarato: app presunta, non identità verificata.
- **Flow / SSRC / device**: restano distinti; non aggregare flussi o destinatari diversi. Il device selezionato nella diagnostica filtra le metriche VD; RTT mostra separatamente tutti i flow/SSRC attribuiti alla prospettiva.
- **sample / gauge**: osservazione al timestamp. **event**: aggiornamento esplicito, senza interpolazione. **counter**: contatore cumulativo soggetto a reset. **interval**: valore riferito a un intervallo (delta oppure finestra esplicita). **step**: valore mantenuto fino a una scadenza dichiarata; il MOS legacy usa questa rappresentazione.
- **last / avg / min / max**: statistiche riportate da KPE, non calcolate dall’analizzatore. Non è nota automaticamente la loro finestra temporale. La media nelle tabelle RTCP è aritmetica sui campioni, non pesata per durata o pacchetti.
- **Unità**: µs ÷ 1000 = ms; ms ÷ 1000 = s. Le durate VD con unità esplicita sono normalizzate in ms; byte, pacchetti, campioni, chunk e conteggi mantengono le rispettive unità. Solo il silenzio saltato cumulativo può essere visualizzato in secondi in Diagnostica A/B; i delta restano in ms. `raw` significa unità non confermata. Lo stesso nome può avere valori ms e raw: le serie rimangono separate.
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

## Verifica delle unità, metrica per metrica

Inventario verificato sui campi riconosciuti da parser.py, enrichment.py e periodic.py,
sulle finestre di telemetria e sui calcoli derivati. L’unità dei campioni resta
la fonte per l’asse verticale; una voce di catalogo non converte dati raw.
Le sei statistiche KPE raw restano non confermate in assenza di evidenza del produttore.

`derived.silence_played_delta` è in **millisecondi (ms)**: il campo di partenza
contiene **msecs**, non usecs. Esempio: 100 → 125 ms produce un incremento di
25 ms tra i due campioni, non 25 µs, non 25 ms/s e non una percentuale.

| Metrica | Unità nel grafico / CSV | Campo originale o derivazione |
|---|---|---|
| `telemetry.network_loss` | % · percentuale | Telemetria strutturata: rtp-sequence-window/1 oppure delta dei contatori RTCP SR/RR. |
| `vd.missing_packets` | pacchetti | [NARTn of Line m] Packet loss occurred … SN delta is … (N missing packets) |
| `rtcp.rtt` | ms · millisecondi | RTT to this source: … ms; RTT by this source: … microseconds (÷1000) |
| `rtcp.jitter` | ms · millisecondi | Jitter we perceive …; Receiver Report - jitter perceived by this remote peer … |
| `rtcp.loss` | % · percentuale | Packet loss we perceive …; Receiver Report - remote peer pkt loss … |
| `rtcp.packets_received` | pacchetti | Packet we received from this source (total) |
| `network.ping` | ms · millisecondi | received … bytes … time=… ms |
| `vd.max_arrival_delay` | ms · millisecondi | m_maxPktArrivalTimeDelay to ms …; campo periodico m_maxPktArrivalTimeDelay (ms): … |
| `vd.dejitter_target` | ms · millisecondi | ring current max buffer usecs (for dynamic dejittering): … (÷1000) |
| `vd.buffer` | ms · millisecondi | buffer len in usecs: … (÷1000); Audio currently in buffer (ms): … |
| `vd.silence_skipped` | ms · millisecondi | silence usecs skipped so far: … (÷1000); silence msecs skipped so far: … |
| `derived.silence_delta` | ms · millisecondi | Differenza tra campioni consecutivi di vd.silence_skipped, separati per prospettiva, observer, device, output, input, ciclo di vita, direzione, flow e SSRC; massimo 30 s e due eventi di evidenza. |
| `derived.buffer_sum` | ms · millisecondi | Somma di vd.buffer dei due device scelti dopo correzione degli orologi; interpolazione lineare nei soli intervalli comuni. |
| `derived.dejitter_sum` | ms · millisecondi | Somma di vd.dejitter_target di A e B con interpolazione lineare solo nella copertura comune e con intervalli al massimo di 30 s. |
| `incident.buffer_underrun` | ms · millisecondi | Buffer underrun occurred; Still in buffer underrun … Event is currently … msecs; Buffer underrun event terminated … Event was … msecs long. |
| `incident.media_missing` | ms · millisecondi | Line … reported that flow … has not received RTP media for more than … sec/ms; has re-started receiving RTP media / has started receiving RTP media again. |
| `kpe.audio.dtmf_rtt` | raw · unità non confermata | JSON incoming/outgoing → audio → dtmf_rtt → last/avg/min/max |
| `kpe.audio.jitter` | raw · unità non confermata | JSON incoming/outgoing → audio → jitter → last/avg/min/max |
| `kpe.audio.jitter_rfc3550` | raw · unità non confermata | JSON incoming/outgoing → audio → jitter_rfc3550 → last/avg/min/max |
| `kpe.audio.ploss_jitter` | raw · unità non confermata | JSON incoming/outgoing → audio → ploss_jitter → last/avg/min/max |
| `kpe.common.ploss` | raw · unità non confermata | JSON incoming/outgoing → common → ploss → last/avg/min/max |
| `kpe.common.rtt` | raw · unità non confermata | JSON incoming/outgoing → common → rtt → last/avg/min/max |
| `kpe.common.rtp_pkt_rx` | pacchetti | JSON incoming/outgoing → common → rtp_pkt_rx → last/avg/min/max |
| `kpe.common.rtp_pkt_tx` | pacchetti | JSON incoming/outgoing → common → rtp_pkt_tx → last/avg/min/max |
| `derived.mos_reference` | MOS · indice senza unità | Perdita RTCP (%) locale o dichiarata dal peer, oppure perdita da finestre strutturate verificate. Profilo loss-reference-1: G.711 10 ms, PLC Appendix I, Ie=0, Bpl=25.1, BurstR=1, R base=93.2. |
| `vd.samples_skipped` | campioni audio | audio samples skipped so far |
| `vd.buffer_hard_max` | ms · millisecondi | ring hard max buffer usecs (µs ÷ 1000; originali raw_value/raw_unit) |
| `vd.buffer_min` | ms · millisecondi | ring min buffer usecs (µs ÷ 1000; originali raw_value/raw_unit) |
| `vd.underruns` | conteggio | number of buffer underruns occurred on this ring for this VOD |
| `vd.silence_played` | ms · millisecondi | silence msecs played out for buffer underruns occurred on this ring for this VOD |
| `vd.bytes_read` | byte | Total bytes read from source |
| `vd.bytes_decoder` | byte | Total bytes sent to decoder |
| `vd.chunks_decoder` | chunk | Total packets/chunks sent to decoder |
| `vd.media_read` | ms · millisecondi / raw · unità non confermata | Total media read from middleware: … ms (senza suffisso: raw) |
| `vd.media_sent` | ms · millisecondi / raw · unità non confermata | Total media sent out: … ms (senza suffisso: raw) |
| `vd.media_middleware` | ms · millisecondi / raw · unità non confermata | Total media sent to middleware: … ms (senza suffisso: raw) |
| `vd.scheduling_resets` | conteggio | Number of device reset for scheduling delay |
| `vd.packets_all` | pacchetti | ALL Pkts received so far |
| `vd.packets_rtp` | pacchetti | RTP Pkts received so far |
| `vd.packets_rtcp` | pacchetti | RTCP Pkts received so far |
| `vd.packets_rtp_good` | pacchetti | RTP GOOD Pkts received so far |
| `vd.packets_rtp_bad` | pacchetti | RTP BAD Pkts received so far |
| `vd.read_errors` | conteggio | Number of Read Errors |
| `vd.read_error_duration` | ms · millisecondi | Current read error event duration (msecs) |
| `vd.write_errors` | conteggio | Number of Write Errors |
| `vd.write_error_duration` | ms · millisecondi | Current write error event duration (msecs) |
| `vd.encoding_errors` | conteggio | Number of Encoding Errors |
| `vd.encoding_error_duration` | ms · millisecondi | Current encoding error event duration (msecs) |
| `vd.decoding_errors` | conteggio | Number of Decoding Errors |
| `vd.decoding_error_duration` | ms · millisecondi | Current decoding error event duration (msecs) |
| `vd.streak_good` | pacchetti | RTP last streak of GOOD Pkts received |
| `vd.streak_bad` | pacchetti | RTP last streak of BAD Pkts received |
| `vd.write_rate` | campioni audio/s | Cumulative write rate is … samples per second |
| `vd.scheduling_delay` | ms · millisecondi | Accumulated delay is … ms |
| `vd.underrun_duration` | ms · millisecondi | Currently in underrun for this VOD since … msecs |
| `vd.heartbeat_bytes_read` | byte | read bytes: … (heartbeat; finestra dei byte non confermata) |
| `vd.heartbeat_bytes_written` | byte | written bytes … (heartbeat; finestra dei byte non confermata) |
| `vd.heartbeat_window` | ms · millisecondi | Running cycles (last … ms) |
| `vd.cycles_tbody_runs` | conteggio | Running cycles: conteggio della fase tbody_runs; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio. |
| `vd.cycles_read` | conteggio | Running cycles: conteggio della fase read; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio. |
| `vd.cycles_decode` | conteggio | Running cycles: conteggio della fase decode; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio. |
| `vd.cycles_adapttomw` | conteggio | Running cycles: conteggio della fase adapttomw; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio. |
| `vd.cycles_append` | conteggio | Running cycles: conteggio della fase append; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio. |
| `vd.cycles_readfrommw` | conteggio | Running cycles: conteggio della fase readfrommw; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio. |
| `vd.cycles_adapttocodec` | conteggio | Running cycles: conteggio della fase adapttocodec; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio. |
| `vd.cycles_encode` | conteggio | Running cycles: conteggio della fase encode; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio. |
| `vd.cycles_write` | conteggio | Running cycles: conteggio della fase write; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio. |
| `rtcp.packets_sent_total` | pacchetti | Sender Report - Number of packets sent by this remote peer (total) |
| `rtcp.packets_sent_interval` | pacchetti | Sender Report - Number of packets sent by this remote peer (since last report) |
| `rtcp.packets_received_interval` | pacchetti | Packet we received from this source (since last report) |
| `rtcp.packets_lost_total` | pacchetti | Receiver Report - pkt lost by this peer (total) |
| `rtcp.packets_lost_interval` | pacchetti | Receiver Report - pkt lost by this peer (since last report) |
| `derived.silence_played_delta` | ms · millisecondi | Differenza tra campioni consecutivi di vd.silence_played, separati per prospettiva, observer, device, output, input, ciclo di vita, direzione, flow e SSRC; massimo 30 s e due eventi di evidenza. |
| `derived.perceptual_quality` | PQ · indice 0–100 | AWT: Buffer underrun event terminated … Event was … msecs long; contatore silence msecs played out for buffer underruns. |

## Verifica di direzione e tipo, metrica per metrica

Le metriche di device e i delta conservano il contesto di origine. Un input
microfono verso NAWT è elaborazione locale in trasmissione; NART è ricezione.
Un percorso NART → NAWT coinvolge entrambe e non viene forzato in una sola
direzione. Il solo nome di un osservatore, microfono, speaker o file non prova
la tratta. Scheduling locale, I/O e fenomeni del buffer non sono misure di
perdita di rete. Un ruolo xcoder/unknown non diventa automaticamente app.

La selezione può raccogliere più contesti: il menu lo segnala e ogni serie
mantiene la propria interpretazione. In assenza di ruolo confermato le etichette
upstream/downstream indicano “app presunta”. La legenda distingue contatori,
valori istantanei, eventi, incrementi su intervallo e statistiche last/avg/min/max;
il valore tecnico statistic=sample resta compatibile nelle API.

| Metrica | Tipo dichiarato | Regola di direzione / origine della misura |
|---|---|---|
| `telemetry.network_loss` | interval | Perdita su intervallo verificato del ricevitore locale (incoming) o del peer (outgoing). |
| `vd.missing_packets` | event | Ricezione RTP locale NART/flow; preservare device e flusso senza dedurre una causa di rete. |
| `rtcp.rtt` | sample | Andata e ritorno RTP/RTCP; non assegnare upstream o downstream. |
| `rtcp.jitter` | sample | Incoming: ricezione locale; outgoing: ricezione dichiarata dal peer. Il verso del report non è il verso del media misurato. |
| `rtcp.loss` | sample | Incoming: ricezione locale; outgoing: ricezione dichiarata dal peer. Il verso del report non è il verso del media misurato. |
| `rtcp.packets_received` | counter | Pacchetti ricevuti localmente; non confondere con quelli soltanto dichiarati come inviati dal peer. |
| `network.ping` | sample | Sonda ICMP verso la destinazione osservata; non identifica automaticamente il peer RTP. |
| `vd.max_arrival_delay` | event / gauge | Ricezione RTP locale NART/flow; preservare device e flusso senza dedurre una causa di rete. |
| `vd.dejitter_target` | gauge | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.buffer` | gauge | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.silence_skipped` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `derived.silence_delta` | interval | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `derived.buffer_sum` | derived gauge | Indicatore dei due device scelti A+B; non una direzione né una latenza end-to-end. |
| `derived.dejitter_sum` | derived gauge | Indicatore dei due device scelti A+B; non una direzione né una latenza end-to-end. |
| `incident.buffer_underrun` | episode | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `incident.media_missing` | episode | Ricezione RTP locale NART/flow; preservare device e flusso senza dedurre una causa di rete. |
| `kpe.audio.dtmf_rtt` | reported statistic | Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream. |
| `kpe.audio.jitter` | reported statistic | Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream. |
| `kpe.audio.jitter_rfc3550` | reported statistic | Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream. |
| `kpe.audio.ploss_jitter` | reported statistic | Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream. |
| `kpe.common.ploss` | reported statistic | Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream. |
| `kpe.common.rtt` | reported statistic | Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream. |
| `kpe.common.rtp_pkt_rx` | reported statistic | Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream. |
| `kpe.common.rtp_pkt_tx` | reported statistic | Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream. |
| `derived.mos_reference` | derived step | Stima sulla perdita del ricevitore locale (incoming) o del peer (outgoing), non qualità misurata. |
| `vd.samples_skipped` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.buffer_hard_max` | gauge | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.buffer_min` | gauge | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.underruns` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.silence_played` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.bytes_read` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.bytes_decoder` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.chunks_decoder` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.media_read` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.media_sent` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.media_middleware` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.scheduling_resets` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.packets_all` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.packets_rtp` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.packets_rtcp` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.packets_rtp_good` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.packets_rtp_bad` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.read_errors` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.read_error_duration` | gauge | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.write_errors` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.write_error_duration` | gauge | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.encoding_errors` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.encoding_error_duration` | gauge | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.decoding_errors` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.decoding_error_duration` | gauge | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.streak_good` | gauge | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.streak_bad` | gauge | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.write_rate` | gauge | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.scheduling_delay` | counter | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.underrun_duration` | gauge | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.heartbeat_bytes_read` | reported statistic | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.heartbeat_bytes_written` | reported statistic | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.heartbeat_window` | interval | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.cycles_tbody_runs` | counter / reported statistic | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.cycles_read` | counter / reported statistic | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.cycles_decode` | counter / reported statistic | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.cycles_adapttomw` | counter / reported statistic | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.cycles_append` | counter / reported statistic | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.cycles_readfrommw` | counter / reported statistic | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.cycles_adapttocodec` | counter / reported statistic | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.cycles_encode` | counter / reported statistic | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `vd.cycles_write` | counter / reported statistic | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `rtcp.packets_sent_total` | counter | Pacchetti inviati dal peer secondo il Sender Report; non prova che siano arrivati localmente. |
| `rtcp.packets_sent_interval` | interval | Pacchetti inviati dal peer secondo il Sender Report; non prova che siano arrivati localmente. |
| `rtcp.packets_received_interval` | interval | Pacchetti ricevuti localmente; non confondere con quelli soltanto dichiarati come inviati dal peer. |
| `rtcp.packets_lost_total` | counter | Pacchetti persi nella ricezione del peer secondo il Receiver Report; non perdita della ricezione locale. |
| `rtcp.packets_lost_interval` | interval | Pacchetti persi nella ricezione del peer secondo il Receiver Report; non perdita della ricezione locale. |
| `derived.silence_played_delta` | interval | Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream. |
| `derived.perceptual_quality` | interval | Continuità del percorso locale NART → AWT; sola ricezione locale, nessun report del peer. |

## Schede

### Perdita RTP su intervallo verificato — `telemetry.network_loss`

**Unità:** % · percentuale. **Tipo:** interval.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Telemetria strutturata: rtp-sequence-window/1 oppure delta dei contatori RTCP SR/RR.

Perdita riferita a una finestra esplicita, prima di PLC/FEC e scarti di playout. Timestamp UTC derivato dal tempo monotono; originali ed evidenze conservati.

**Direzione e contesto:** Perdita su intervallo verificato del ricevitore locale (incoming) o del peer (outgoing).

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Telemetria strutturata: rtp-sequence-window/1 oppure delta dei contatori RTCP SR/RR..

**Limiti:** Contatori di arrivo e attesi non sono sottratti senza una coorte comune. Reset, conflitti, finestre sovrapposte e gap RTCP oltre 30 s escludono la derivazione. Non è una misura di qualità percepita. Per i report remoti il tempo è quello locale di osservazione dei report, non una sincronizzazione con il peer.

### Pacchetti mancanti per evento NART — `vd.missing_packets`

**Unità:** pacchetti. **Tipo:** event.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: [NARTn of Line m] Packet loss occurred … SN delta is … (N missing packets)

Numero esplicito di pacchetti segnalati come mancanti in un singolo salto della sequenza. Un punto isolato al timestamp del messaggio.

**Direzione e contesto:** Ricezione RTP locale NART/flow; preservare device e flusso senza dedurre una causa di rete.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** [NARTn of Line m] Packet loss occurred … SN delta is … (N missing packets).

**Limiti:** Non è una percentuale RTCP, un contatore cumulativo o una perdita definitiva: riordino, arrivi tardivi e recupero possono modificare l’esito. Non sommare segnalazioni come pacchetti unici persi. Device, linea e sorgente restano separati; nessun SSRC viene inventato. Rotazioni con identico timestamp e identico messaggio sono deduplicate; numeri di sequenza diversi restano eventi distinti. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### RTT RTCP — `rtcp.rtt`

**Unità:** ms · millisecondi. **Tipo:** sample.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: RTT to this source: … ms; RTT by this source: … microseconds (÷1000)

Tempo di andata e ritorno riportato per la sorgente RTP/RTCP.

**Direzione e contesto:** Andata e ritorno RTP/RTCP; non assegnare upstream o downstream.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** RTT to this source: … ms; RTT by this source: … microseconds (÷1000).

**Limiti:** Non è ritardo audio a senso unico. Può includere il percorso verso un relay/PBX. Un picco non localizza il guasto su un endpoint.

### Jitter RTCP — `rtcp.jitter`

**Unità:** ms · millisecondi. **Tipo:** sample.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Jitter we perceive …; Receiver Report - jitter perceived by this remote peer …

Variabilità degli arrivi riportata localmente (incoming) o dal peer (outgoing).

**Direzione e contesto:** Incoming: ricezione locale; outgoing: ricezione dichiarata dal peer. Il verso del report non è il verso del media misurato.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Jitter we perceive …; Receiver Report - jitter perceived by this remote peer ….

**Limiti:** Separare direzioni, flow e SSRC. Non coincide con occupazione o target del buffer, né con il massimo VD.

### Perdita RTCP — `rtcp.loss`

**Unità:** % · percentuale. **Tipo:** sample.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Packet loss we perceive …; Receiver Report - remote peer pkt loss …

Percentuale di perdita riferita all’intervallo dichiarato dal report.

**Direzione e contesto:** Incoming: ricezione locale; outgoing: ricezione dichiarata dal peer. Il verso del report non è il verso del media misurato.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Packet loss we perceive …; Receiver Report - remote peer pkt loss ….

**Limiti:** Valori validi da 0 a 100. La media semplice dei report non è la perdita totale ponderata per pacchetti.

### Pacchetti ricevuti — `rtcp.packets_received`

**Unità:** pacchetti. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Packet we received from this source (total)

Contatore dei pacchetti ricevuti per sorgente.

**Direzione e contesto:** Pacchetti ricevuti localmente; non confondere con quelli soltanto dichiarati come inviati dal peer.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Packet we received from this source (total).

**Limiti:** Può ripartire dopo reset/sessione. Non sommare campioni cumulativi né esportazioni dello stesso dispositivo.

### Ping ICMP — `network.ping`

**Unità:** ms · millisecondi. **Tipo:** sample.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: received … bytes … time=… ms

Tempo di andata e ritorno della sonda ICMP.

**Direzione e contesto:** Sonda ICMP verso la destinazione osservata; non identifica automaticamente il peer RTP.

**Ambito:** Sonda di rete. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** received … bytes … time=… ms.

**Limiti:** La destinazione ICMP può differire dal peer multimediale. Non sostituisce RTT RTCP.

### Massimo ritardo di arrivo NART — `vd.max_arrival_delay`

**Unità:** ms · millisecondi. **Tipo:** event / gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: m_maxPktArrivalTimeDelay to ms …; campo periodico m_maxPktArrivalTimeDelay (ms): …

Valore dichiarato dal motore per il massimo ritardo di arrivo. Nei WARNING è un aggiornamento del massimo.

**Direzione e contesto:** Ricezione RTP locale NART/flow; preservare device e flusso senza dedurre una causa di rete.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** m_maxPktArrivalTimeDelay to ms …; campo periodico m_maxPktArrivalTimeDelay (ms): ….

**Limiti:** Il massimo può scendere quando il motore cambia finestra o stato. WARNING rappresentati come punti isolati: non sono campioni periodici del jitter. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Limite dinamico dejitter — `vd.dejitter_target`

**Unità:** ms · millisecondi. **Tipo:** gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: ring current max buffer usecs (for dynamic dejittering): … (÷1000)

Limite corrente del ring buffer nel device indicato nel contesto; su NART sostiene il dejittering della ricezione RTP.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** ring current max buffer usecs (for dynamic dejittering): … (÷1000).

**Limiti:** Non è l’audio effettivamente in coda. Si escludono gli altri device per sezione, non per valore: 20000 µs su NART è un valido campione di 20 ms. Nel formato recente sono conservate anche sezioni non NART, con contesto proprio. Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Audio nel buffer del device — `vd.buffer`

**Unità:** ms · millisecondi. **Tipo:** gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: buffer len in usecs: … (÷1000); Audio currently in buffer (ms): …

Durata dell’audio presente nel buffer del device indicato nel contesto; su NART riguarda la ricezione RTP, sugli altri VID la rispettiva sorgente media.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** buffer len in usecs: … (÷1000); Audio currently in buffer (ms): ….

**Limiti:** È una misura locale, non il ritardo totale della chiamata. I due nomi sono alias empirici; il valore e l’unità originali restano nel DB. Nel formato recente sono conservate anche sezioni non NART, con contesto proprio. Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Silenzio saltato cumulativo — `vd.silence_skipped`

**Unità:** ms · millisecondi. **Tipo:** counter.

**Lettura dell’unità:** Durata cumulativa in ms; i campi usecs sono divisi per 1000, i campi msecs restano invariati. Solo Diagnostica A/B può visualizzare questo contatore in secondi (ms ÷ 1000); i delta restano in ms.

Durata cumulativa del silenzio saltato dichiarata dal device. In Diagnostica A/B si può scegliere ms oppure dividere ancora per 1000 per mostrare secondi; nel dettaglio chiamata resta in ms.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** silence usecs skipped so far: … (÷1000); silence msecs skipped so far: ….

**Limiti:** Non è perdita pacchetti né prova di voce persa. Può azzerarsi: non si presume continuità per tutta la chiamata. Nel formato recente sono conservate anche sezioni non NART, con contesto proprio. Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Incremento silenzio saltato — `derived.silence_delta`

**Unità:** ms · millisecondi. **Tipo:** interval.

**Lettura dell’unità:** Millisecondi: differenza di vd.silence_skipped dopo la normalizzazione µs ÷ 1000, quando necessaria. È una durata nell’intervallo, non un tasso ms/s.

Quantità aggiuntiva nel periodo fra i due campioni; mostrata al timestamp del secondo.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Differenza tra campioni consecutivi di vd.silence_skipped, separati per prospettiva, observer, device, output, input, ciclo di vita, direzione, flow e SSRC; massimo 30 s e due eventi di evidenza..

**Limiti:** Il primo valore, un calo del contatore e un intervallo >30 s non producono delta. Non è un tasso al secondo. Entrambi gli eventi sono indicati come evidenza. La direzione è quella del contesto originale: Default Audio Input → NAWT è elaborazione locale in trasmissione, non ricezione downstream. Il delta non prova silenzio del microfono, perdita RTP o audio effettivamente ascoltato dal peer.

### Somma dei buffer A+B — `derived.buffer_sum`

**Unità:** ms · millisecondi. **Tipo:** derived gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Somma di vd.buffer dei due device scelti dopo correzione degli orologi; interpolazione lineare nei soli intervalli comuni.

Indicatore del buffering combinato dei due punti di vista, utile per confrontare gli andamenti.

**Direzione e contesto:** Indicatore dei due device scelti A+B; non una direzione né una latenza end-to-end.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Somma di vd.buffer dei due device scelti dopo correzione degli orologi; interpolazione lineare nei soli intervalli comuni..

**Limiti:** Non misura il ritardo end-to-end o conversazionale. Non include rete, codec o mixer; i due buffer ricevono direzioni diverse. Niente estrapolazione o interpolazione oltre 30 s. Servono due prospettive distinte, non due copie dello stesso dispositivo.

### Somma dei limiti dinamici A+B — `derived.dejitter_sum`

**Unità:** ms · millisecondi. **Tipo:** derived gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Somma di vd.dejitter_target di A e B con interpolazione lineare solo nella copertura comune e con intervalli al massimo di 30 s.

Somma dei limiti dinamici dei buffer dei due device scelti. Su NART riguarda il dejittering di ricezione; la selezione di altri device non dimostra quel percorso. Distinta dalla somma dell’audio realmente in coda.

**Direzione e contesto:** Indicatore dei due device scelti A+B; non una direzione né una latenza end-to-end.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Somma di vd.dejitter_target di A e B con interpolazione lineare solo nella copertura comune e con intervalli al massimo di 30 s..

**Limiti:** Non è occupazione effettiva né misura di ritardo conversazionale. Nessuna estrapolazione; la selezione del periodo viene applicata prima della derivazione. Ogni punto conserva le evidenze dei campioni originali.

### Episodio di buffer underrun — `incident.buffer_underrun`

**Unità:** ms · millisecondi. **Tipo:** episode.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Buffer underrun occurred; Still in buffer underrun … Event is currently … msecs; Buffer underrun event terminated … Event was … msecs long.

Periodo in cui l’osservatore non ottiene audio dal device NART selezionato. La durata dichiarata dal motore resta distinta dalla distanza fra timestamp dei messaggi.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Buffer underrun occurred; Still in buffer underrun … Event is currently … msecs; Buffer underrun event terminated … Event was … msecs long..

**Limiti:** AWT (uscita audio) e gli altri VD osservati restano separati; VD generico non identifica una registrazione su file: non sommare le loro durate. Senza inizio, un messaggio di fine con durata consente solo di ricavare l’inizio; senza fine l’episodio resta aperto. Contatori periodici e mutedReasons non vengono trasformati in episodi. Derivato su richiesta dagli eventi, non memorizzato in metrics.

### Episodio di media missing — `incident.media_missing`

**Unità:** ms · millisecondi. **Tipo:** episode.

**Lettura dell’unità:** Durata in ms, con limite inferiore stimato dalle notifiche. “Minimo stimato” descrive la stima, non una diversa unità.

Assenza RTP segnalata su una linea e un flow. La soglia prima della segnalazione si aggiunge al tempo fino alla ripresa per stimare un limite inferiore della durata.

**Direzione e contesto:** Ricezione RTP locale NART/flow; preservare device e flusso senza dedurre una causa di rete.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Line … reported that flow … has not received RTP media for more than … sec/ms; has re-started receiving RTP media / has started receiving RTP media again..

**Limiti:** L’inizio effettivo non è misurato: la barra parte dalla segnalazione meno la soglia. Il limite è ricavato dai messaggi e dipende dai tempi di notifica. Ripresa senza segnalazione precedente: durata sconosciuta. Nessuna chiusura viene inventata alla fine della chiamata. Eventi di coda media_missing e riepiloghi non duplicano gli episodi.

### RTT DTMF KPE — `kpe.audio.dtmf_rtt`

**Unità:** raw · unità non confermata. **Tipo:** reported statistic.

**Lettura dell’unità:** Unità non confermata dal log: nessuna conversione in ms, µs o percentuale. Il nome della metrica non dimostra l’unità.

Statistica KPE denominata dtmf_rtt; semantica dettagliata da confermare col produttore.

**Direzione e contesto:** Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → audio → dtmf_rtt → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Jitter KPE — `kpe.audio.jitter`

**Unità:** raw · unità non confermata. **Tipo:** reported statistic.

**Lettura dell’unità:** Unità non confermata dal log: nessuna conversione in ms, µs o percentuale. Il nome della metrica non dimostra l’unità.

Statistica del motore denominata jitter.

**Direzione e contesto:** Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → audio → jitter → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Jitter RFC3550 KPE — `kpe.audio.jitter_rfc3550`

**Unità:** raw · unità non confermata. **Tipo:** reported statistic.

**Lettura dell’unità:** Unità non confermata dal log: nessuna conversione in ms, µs o percentuale. Il nome della metrica non dimostra l’unità.

Statistica del motore etichettata jitter_rfc3550.

**Direzione e contesto:** Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → audio → jitter_rfc3550 → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Perdita jitter KPE — `kpe.audio.ploss_jitter`

**Unità:** raw · unità non confermata. **Tipo:** reported statistic.

**Lettura dell’unità:** Unità non confermata dal log: nessuna conversione in ms, µs o percentuale. Il nome della metrica non dimostra l’unità.

Statistica del motore denominata ploss_jitter; non equiparata automaticamente alla perdita RTCP.

**Direzione e contesto:** Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → audio → ploss_jitter → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Perdita KPE — `kpe.common.ploss`

**Unità:** raw · unità non confermata. **Tipo:** reported statistic.

**Lettura dell’unità:** Unità non confermata dal log: nessuna conversione in ms, µs o percentuale. Il nome della metrica non dimostra l’unità.

Statistica del motore denominata ploss.

**Direzione e contesto:** Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → common → ploss → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### RTT KPE — `kpe.common.rtt`

**Unità:** raw · unità non confermata. **Tipo:** reported statistic.

**Lettura dell’unità:** Unità non confermata dal log: nessuna conversione in ms, µs o percentuale. Il nome della metrica non dimostra l’unità.

Statistica del motore denominata rtt.

**Direzione e contesto:** Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → common → rtt → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Pacchetti RX KPE — `kpe.common.rtp_pkt_rx`

**Unità:** pacchetti. **Tipo:** reported statistic.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: JSON incoming/outgoing → common → rtp_pkt_rx → last/avg/min/max

Conteggio RTP ricevuto dichiarato dal motore.

**Direzione e contesto:** Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → common → rtp_pkt_rx → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### Pacchetti TX KPE — `kpe.common.rtp_pkt_tx`

**Unità:** pacchetti. **Tipo:** reported statistic.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: JSON incoming/outgoing → common → rtp_pkt_tx → last/avg/min/max

Conteggio RTP trasmesso dichiarato dal motore.

**Direzione e contesto:** Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream.

**Ambito:** Semantica specifica non confermata. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** JSON incoming/outgoing → common → rtp_pkt_tx → last/avg/min/max.

**Limiti:** last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.

### MOS a profilo fisso · sola perdita — `derived.mos_reference`

**Unità:** MOS · indice senza unità. **Tipo:** derived step.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Perdita RTCP (%) locale o dichiarata dal peer, oppure perdita da finestre strutturate verificate. Profilo loss-reference-1: G.711 10 ms, PLC Appendix I, Ie=0, Bpl=25.1, BurstR=1, R base=93.2.

Indice stimato a profilo costante per confrontare la perdita nelle due direzioni. R=93.2−95p/(p+25.1), limitato a 0–100; MOS=1+0.035R+0.000007R(R−60)(100−R).

**Direzione e contesto:** Stima sulla perdita del ricevitore locale (incoming) o del peer (outgoing), non qualità misurata.

**Ambito:** Modello di qualità derivato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Perdita RTCP (%) locale o dichiarata dal peer, oppure perdita da finestre strutturate verificate. Profilo loss-reference-1: G.711 10 ms, PLC Appendix I, Ie=0, Bpl=25.1, BurstR=1, R base=93.2..

**Limiti:** Non è qualità vocale misurata né E-model completo. Non valuta jitter, ritardo, scarti, burst o PLC reale. Nei log tradizionali il report riguarda il passato; il valore viene mantenuto al massimo 30 s fino al report successivo o alla fine chiamata. La telemetria verificata descrive invece la sua finestra esplicita già osservata. Report invalidi o discordanti interrompono la curva. Nel pannello MOS il peer è scelto esplicitamente e la sua ricezione locale è riutilizzata. Riferimenti: ITU-T G.107 (2015), G.113 (2024) tabella I.4.

### audio samples skipped so far — `vd.samples_skipped`

**Unità:** campioni audio. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: audio samples skipped so far

Numero cumulativo di campioni audio saltati dal device. Campioni audio e pacchetti RTP sono grandezze diverse.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** audio samples skipped so far.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### ring hard max buffer usecs — `vd.buffer_hard_max`

**Unità:** ms · millisecondi. **Tipo:** gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: ring hard max buffer usecs (µs ÷ 1000; originali raw_value/raw_unit)

Limite massimo rigido del ring buffer dichiarato dal device; non occupazione effettiva.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** ring hard max buffer usecs (µs ÷ 1000; originali raw_value/raw_unit).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### ring min buffer usecs — `vd.buffer_min`

**Unità:** ms · millisecondi. **Tipo:** gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: ring min buffer usecs (µs ÷ 1000; originali raw_value/raw_unit)

Limite minimo del ring buffer dichiarato dal device; non minimo misurato sull’intera chiamata.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** ring min buffer usecs (µs ÷ 1000; originali raw_value/raw_unit).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Numero cumulativo di underrun del lettore — `vd.underruns`

**Unità:** conteggio. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: number of buffer underruns occurred on this ring for this VOD

Numero cumulativo di underrun del ring per lo specifico VOD lettore e VID collegato. Non è il conteggio complessivo di guasti della chiamata.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** number of buffer underruns occurred on this ring for this VOD.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Silenzio riprodotto per underrun, cumulativo — `vd.silence_played`

**Unità:** ms · millisecondi. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: silence msecs played out for buffer underruns occurred on this ring for this VOD

Durata cumulativa del silenzio riprodotto per compensare underrun del ring per lo specifico VOD e VID. Non prova silenzio della sorgente o perdita RTP.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** silence msecs played out for buffer underruns occurred on this ring for this VOD.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Total bytes read from source — `vd.bytes_read`

**Unità:** byte. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Total bytes read from source

Byte cumulativi letti dalla sorgente del device: rete, scheda audio o file secondo la specializzazione osservata. Non automaticamente traffico RTP.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Total bytes read from source.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Total bytes sent to decoder — `vd.bytes_decoder`

**Unità:** byte. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Total bytes sent to decoder

Byte cumulativi inviati al decoder, non necessariamente byte ricevuti sulla rete.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Total bytes sent to decoder.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Total packets/chunks sent to decoder — `vd.chunks_decoder`

**Unità:** chunk. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Total packets/chunks sent to decoder

Pacchetti/chunk cumulativi inviati al decoder. Chunk non equivale automaticamente a datagramma RTP.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Total packets/chunks sent to decoder.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Total media read from middleware — `vd.media_read`

**Unità:** ms · millisecondi / raw · unità non confermata. **Tipo:** counter.

**Lettura dell’unità:** ms solo con suffisso esplicito nel campo originale; senza suffisso il valore resta raw. Le due unità non si convertono né si sovrappongono.

Durata cumulativa del media letto dal middleware. Non è tempo CPU, latenza o durata della chiamata. Usare ms solo con suffisso esplicito, altrimenti raw.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Total media read from middleware: … ms (senza suffisso: raw).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Total media sent out — `vd.media_sent`

**Unità:** ms · millisecondi / raw · unità non confermata. **Tipo:** counter.

**Lettura dell’unità:** ms solo con suffisso esplicito nel campo originale; senza suffisso il valore resta raw. Le due unità non si convertono né si sovrappongono.

Durata cumulativa del media inviato in uscita. Non è tempo CPU, latenza o durata della chiamata. Usare ms solo con suffisso esplicito, altrimenti raw.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Total media sent out: … ms (senza suffisso: raw).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Total media sent to middleware — `vd.media_middleware`

**Unità:** ms · millisecondi / raw · unità non confermata. **Tipo:** counter.

**Lettura dell’unità:** ms solo con suffisso esplicito nel campo originale; senza suffisso il valore resta raw. Le due unità non si convertono né si sovrappongono.

Durata cumulativa del media inviato al middleware. Non è tempo CPU, latenza o durata della chiamata. Usare ms solo con suffisso esplicito, altrimenti raw.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Total media sent to middleware: … ms (senza suffisso: raw).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Number of device reset for scheduling delay — `vd.scheduling_resets`

**Unità:** conteggio. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Number of device reset for scheduling delay

Numero di reset che il device attribuisce a ritardo di scheduling. Non è un conteggio di pacchetti persi o di reset della rete.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Number of device reset for scheduling delay.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### ALL Pkts received so far — `vd.packets_all`

**Unità:** pacchetti. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: ALL Pkts received so far

Conteggio di ricezione dichiarato per la categoria del campo sorgente; mantenere separati totale, RTP, RTCP e sequenze GOOD/BAD. GOOD/BAD è una classificazione del motore, non una definizione confermata di perdita o qualità vocale.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** ALL Pkts received so far.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### RTP Pkts received so far — `vd.packets_rtp`

**Unità:** pacchetti. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: RTP Pkts received so far

Conteggio di ricezione dichiarato per la categoria del campo sorgente; mantenere separati totale, RTP, RTCP e sequenze GOOD/BAD. GOOD/BAD è una classificazione del motore, non una definizione confermata di perdita o qualità vocale.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** RTP Pkts received so far.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### RTCP Pkts received so far — `vd.packets_rtcp`

**Unità:** pacchetti. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: RTCP Pkts received so far

Conteggio di ricezione dichiarato per la categoria del campo sorgente; mantenere separati totale, RTP, RTCP e sequenze GOOD/BAD. GOOD/BAD è una classificazione del motore, non una definizione confermata di perdita o qualità vocale.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** RTCP Pkts received so far.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### RTP GOOD Pkts received so far — `vd.packets_rtp_good`

**Unità:** pacchetti. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: RTP GOOD Pkts received so far

Conteggio di ricezione dichiarato per la categoria del campo sorgente; mantenere separati totale, RTP, RTCP e sequenze GOOD/BAD. GOOD/BAD è una classificazione del motore, non una definizione confermata di perdita o qualità vocale.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** RTP GOOD Pkts received so far.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### RTP BAD Pkts received so far — `vd.packets_rtp_bad`

**Unità:** pacchetti. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: RTP BAD Pkts received so far

Conteggio di ricezione dichiarato per la categoria del campo sorgente; mantenere separati totale, RTP, RTCP e sequenze GOOD/BAD. GOOD/BAD è una classificazione del motore, non una definizione confermata di perdita o qualità vocale.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** RTP BAD Pkts received so far.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Number of Read Errors — `vd.read_errors`

**Unità:** conteggio. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Number of Read Errors

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Numero cumulativo di errori dichiarati. La fase e il device non identificano automaticamente la causa di rete.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Number of Read Errors.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Current read error event duration (msecs) — `vd.read_error_duration`

**Unità:** ms · millisecondi. **Tipo:** gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Current read error event duration (msecs)

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Durata dell’evento di errore corrente, non totale cumulativo. La fase e il device non identificano automaticamente la causa di rete.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Current read error event duration (msecs).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Number of Write Errors — `vd.write_errors`

**Unità:** conteggio. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Number of Write Errors

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Numero cumulativo di errori dichiarati. La fase e il device non identificano automaticamente la causa di rete.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Number of Write Errors.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Current write error event duration (msecs) — `vd.write_error_duration`

**Unità:** ms · millisecondi. **Tipo:** gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Current write error event duration (msecs)

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Durata dell’evento di errore corrente, non totale cumulativo. La fase e il device non identificano automaticamente la causa di rete.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Current write error event duration (msecs).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Number of Encoding Errors — `vd.encoding_errors`

**Unità:** conteggio. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Number of Encoding Errors

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Numero cumulativo di errori dichiarati. La fase e il device non identificano automaticamente la causa di rete.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Number of Encoding Errors.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Current encoding error event duration (msecs) — `vd.encoding_error_duration`

**Unità:** ms · millisecondi. **Tipo:** gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Current encoding error event duration (msecs)

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Durata dell’evento di errore corrente, non totale cumulativo. La fase e il device non identificano automaticamente la causa di rete.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Current encoding error event duration (msecs).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Number of Decoding Errors — `vd.decoding_errors`

**Unità:** conteggio. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Number of Decoding Errors

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Numero cumulativo di errori dichiarati. La fase e il device non identificano automaticamente la causa di rete.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Number of Decoding Errors.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Current decoding error event duration (msecs) — `vd.decoding_error_duration`

**Unità:** ms · millisecondi. **Tipo:** gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Current decoding error event duration (msecs)

Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). Durata dell’evento di errore corrente, non totale cumulativo. La fase e il device non identificano automaticamente la causa di rete.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Current decoding error event duration (msecs).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Lunghezza dell’ultima sequenza RTP GOOD — `vd.streak_good`

**Unità:** pacchetti. **Tipo:** gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: RTP last streak of GOOD Pkts received

Numero di pacchetti nell’ultima sequenza GOOD dichiarata dal motore. È la lunghezza di una sequenza, non il totale cumulativo dei pacchetti e non una percentuale di perdita. GOOD/BAD non dimostra qualità vocale.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** RTP last streak of GOOD Pkts received.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Lunghezza dell’ultima sequenza RTP BAD — `vd.streak_bad`

**Unità:** pacchetti. **Tipo:** gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: RTP last streak of BAD Pkts received

Numero di pacchetti nell’ultima sequenza BAD dichiarata dal motore. È la lunghezza di una sequenza, non il totale cumulativo dei pacchetti e non una percentuale di perdita. GOOD/BAD non dimostra qualità vocale.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** RTP last streak of BAD Pkts received.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Frequenza di scrittura dichiarata — `vd.write_rate`

**Unità:** campioni audio/s. **Tipo:** gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Cumulative write rate is … samples per second

Frequenza di scrittura riportata dal device in campioni/s. Non è bitrate di rete e non dimostra da sola regolarità dello scheduling. Il campo si chiama Cumulative write rate, ma il valore è una frequenza (campioni/s), non un contatore da sommare.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Cumulative write rate is … samples per second.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Ritardo accumulato di scheduling — `vd.scheduling_delay`

**Unità:** ms · millisecondi. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Accumulated delay is … ms

Ritardo accumulato di scheduling dichiarato dal thread del VD. Descrive la temporizzazione locale, non il tempo di transito RTP.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Accumulated delay is … ms.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Durata corrente underrun del lettore — `vd.underrun_duration`

**Unità:** ms · millisecondi. **Tipo:** gauge.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Currently in underrun for this VOD since … msecs

Durata dichiarata dell’underrun attualmente in corso per il lettore/input osservato; non contatore cumulativo né durata totale della chiamata.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Currently in underrun for this VOD since … msecs.

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Byte letti heartbeat — `vd.heartbeat_bytes_read`

**Unità:** byte. **Tipo:** reported statistic.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: read bytes: … (heartbeat; finestra dei byte non confermata)

Byte letti riportati dal thread nel messaggio heartbeat; finestra dei byte non confermata. Non derivare un bitrate dividendo per la finestra dei cicli.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** read bytes: … (heartbeat; finestra dei byte non confermata).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Byte scritti heartbeat — `vd.heartbeat_bytes_written`

**Unità:** byte. **Tipo:** reported statistic.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: written bytes … (heartbeat; finestra dei byte non confermata)

Byte scritti riportati dal thread nel messaggio heartbeat; finestra dei byte non confermata. Non derivare un bitrate dividendo per la finestra dei cicli.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Elaborazione e I/O del device. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** written bytes … (heartbeat; finestra dei byte non confermata).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Finestra cicli heartbeat — `vd.heartbeat_window`

**Unità:** ms · millisecondi. **Tipo:** interval.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Running cycles (last … ms)

Finestra last ms dichiarata per i conteggi dei cicli heartbeat. Non è ritardo di scheduling né intervallo confermato per i byte.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running cycles (last … ms).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli Tbody Runs — `vd.cycles_tbody_runs`

**Unità:** conteggio. **Tipo:** counter / reported statistic.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Running cycles: conteggio della fase tbody_runs; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio.

Conteggio riportato per la fase tbody_runs. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running cycles: conteggio della fase tbody_runs; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio..

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli Read — `vd.cycles_read`

**Unità:** conteggio. **Tipo:** counter / reported statistic.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Running cycles: conteggio della fase read; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio.

Conteggio riportato per la fase read. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running cycles: conteggio della fase read; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio..

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli Decode — `vd.cycles_decode`

**Unità:** conteggio. **Tipo:** counter / reported statistic.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Running cycles: conteggio della fase decode; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio.

Conteggio riportato per la fase decode. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running cycles: conteggio della fase decode; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio..

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli AdaptToMw — `vd.cycles_adapttomw`

**Unità:** conteggio. **Tipo:** counter / reported statistic.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Running cycles: conteggio della fase adapttomw; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio.

Conteggio riportato per la fase adapttomw. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running cycles: conteggio della fase adapttomw; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio..

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli Append — `vd.cycles_append`

**Unità:** conteggio. **Tipo:** counter / reported statistic.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Running cycles: conteggio della fase append; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio.

Conteggio riportato per la fase append. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running cycles: conteggio della fase append; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio..

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli ReadFromMW — `vd.cycles_readfrommw`

**Unità:** conteggio. **Tipo:** counter / reported statistic.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Running cycles: conteggio della fase readfrommw; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio.

Conteggio riportato per la fase readfrommw. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running cycles: conteggio della fase readfrommw; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio..

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli AdaptToCodec — `vd.cycles_adapttocodec`

**Unità:** conteggio. **Tipo:** counter / reported statistic.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Running cycles: conteggio della fase adapttocodec; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio.

Conteggio riportato per la fase adapttocodec. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running cycles: conteggio della fase adapttocodec; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio..

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli Encode — `vd.cycles_encode`

**Unità:** conteggio. **Tipo:** counter / reported statistic.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Running cycles: conteggio della fase encode; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio.

Conteggio riportato per la fase encode. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running cycles: conteggio della fase encode; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio..

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Cicli Write — `vd.cycles_write`

**Unità:** conteggio. **Tipo:** counter / reported statistic.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Running cycles: conteggio della fase write; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio.

Conteggio riportato per la fase write. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Scheduling del thread locale. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Running cycles: conteggio della fase write; nel heartbeat la finestra è indicata da last … ms, ma il valore dei cicli è un conteggio..

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.

### Pacchetti inviati dal peer, totale — `rtcp.packets_sent_total`

**Unità:** pacchetti. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Sender Report - Number of packets sent by this remote peer (total)

Pacchetti inviati dal peer, totale. Numeri esponenziali accettati; conteggi finiti negativi o non interi restano invalidi. Il mittente del dato è il peer remoto (Sender Report): pacchetti trasmessi non significa pacchetti ricevuti localmente.

**Direzione e contesto:** Pacchetti inviati dal peer secondo il Sender Report; non prova che siano arrivati localmente.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Sender Report - Number of packets sent by this remote peer (total).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Non derivare perdita da contatori senza coorte comune.

### Pacchetti inviati dal peer, intervallo — `rtcp.packets_sent_interval`

**Unità:** pacchetti. **Tipo:** interval.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Sender Report - Number of packets sent by this remote peer (since last report)

Pacchetti inviati dal peer, intervallo. Numeri esponenziali accettati; conteggi finiti negativi o non interi restano invalidi. Il mittente del dato è il peer remoto (Sender Report): pacchetti trasmessi non significa pacchetti ricevuti localmente.

**Direzione e contesto:** Pacchetti inviati dal peer secondo il Sender Report; non prova che siano arrivati localmente.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Sender Report - Number of packets sent by this remote peer (since last report).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Non derivare perdita da contatori senza coorte comune.

### Pacchetti ricevuti, intervallo — `rtcp.packets_received_interval`

**Unità:** pacchetti. **Tipo:** interval.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Packet we received from this source (since last report)

Pacchetti ricevuti, intervallo. Numeri esponenziali accettati; conteggi finiti negativi o non interi restano invalidi.

**Direzione e contesto:** Pacchetti ricevuti localmente; non confondere con quelli soltanto dichiarati come inviati dal peer.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Packet we received from this source (since last report).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Non derivare perdita da contatori senza coorte comune.

### Pacchetti persi dal peer, totale — `rtcp.packets_lost_total`

**Unità:** pacchetti. **Tipo:** counter.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Receiver Report - pkt lost by this peer (total)

Pacchetti persi dal peer, totale. Numeri esponenziali accettati; conteggi finiti negativi o non interi restano invalidi. Il ricevitore è il peer remoto (Receiver Report): non è un conteggio della perdita osservata localmente.

**Direzione e contesto:** Pacchetti persi nella ricezione del peer secondo il Receiver Report; non perdita della ricezione locale.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Receiver Report - pkt lost by this peer (total).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Non derivare perdita da contatori senza coorte comune.

### Pacchetti persi dal peer, intervallo — `rtcp.packets_lost_interval`

**Unità:** pacchetti. **Tipo:** interval.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: Receiver Report - pkt lost by this peer (since last report)

Pacchetti persi dal peer, intervallo. Numeri esponenziali accettati; conteggi finiti negativi o non interi restano invalidi. Il ricevitore è il peer remoto (Receiver Report): non è un conteggio della perdita osservata localmente.

**Direzione e contesto:** Pacchetti persi nella ricezione del peer secondo il Receiver Report; non perdita della ricezione locale.

**Ambito:** Trasporto RTP osservato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Receiver Report - pkt lost by this peer (since last report).

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Non derivare perdita da contatori senza coorte comune.

### Incremento silenzio riprodotto per underrun — `derived.silence_played_delta`

**Unità:** ms · millisecondi. **Tipo:** interval.

**Lettura dell’unità:** Millisecondi (ms), non microsecondi: il contatore originale è “silence msecs played out for buffer underruns occurred on this ring for this VOD”. Differenza tra due osservazioni; non ms/s né percentuale. Esempio: 100 → 125 ms produce 25 ms.

Silenzio aggiunto al ring per quello specifico lettore/input tra due osservazioni.

**Direzione e contesto:** Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.

**Ambito:** Buffer e disponibilità del media. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** Differenza tra campioni consecutivi di vd.silence_played, separati per prospettiva, observer, device, output, input, ciclo di vita, direzione, flow e SSRC; massimo 30 s e due eventi di evidenza..

**Limiti:** Osservatore, output, input, device e ciclo di vita restano distinti. Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero. Confrontare con episodi, senza sommare le due misure. Non è occupazione a precisione di un secondo. La direzione è quella del contesto originale: Default Audio Input → NAWT è elaborazione locale in trasmissione, non ricezione downstream. Il delta non prova silenzio del microfono, perdita RTP o audio effettivamente ascoltato dal peer.

### Perceptual Quality — `derived.perceptual_quality`

**Unità:** PQ · indice 0–100. **Tipo:** interval.

**Lettura dell’unità:** Unità del valore nel grafico e nel CSV; origine: AWT: Buffer underrun event terminated … Event was … msecs long; contatore silence msecs played out for buffer underruns.

100 meno la percentuale di tempo in underrun AWT in finestre di un secondo, allineate all’orologio del log e ritagliate sulla parte attiva della chiamata ai confini. La percentuale usa la durata effettiva della finestra. 100 = nessun underrun ricostruito, 0 = tutta la finestra in underrun.

**Direzione e contesto:** Continuità del percorso locale NART → AWT; sola ricezione locale, nessun report del peer.

**Ambito:** Modello di qualità derivato. Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.

**Origine e calcolo:** AWT: Buffer underrun event terminated … Event was … msecs long; contatore silence msecs played out for buffer underruns..

**Limiti:** Indice operativo di continuità audio, non MOS né misura percettiva validata. Inizio/fine osservati; durata dichiarata come fallback. Log AWT assunto completo: fuori dagli episodi vale 100; episodi aperti attivi fino a fine chiamata o ricreazione. Senza chiusura registrata, copertura fino all’ultima evidenza attribuita alla stessa chiamata nella sorgente. Nessuna verifica dei contatori periodici. Durante la chiamata, nessun episodio registrato significa 100 anche senza heartbeat o contatori AWT. Eventuali episodi presenti ma non attribuibili restano ambigui. Posizione associata soltanto al secondo che contiene il suo timestamp; nessuna propagazione spaziale.

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
