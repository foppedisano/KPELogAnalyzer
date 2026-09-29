# Campi periodici del formato recente

Versioni e piano: [documento di passaggio](periodic-metrics-implementation.md).

Questa lista contiene nomi di campi del formato, non estratti dei log reali, valori osservati o identificativi personali. Evidenze e frequenze per contesto rimangono negli allegati locali esclusi da Git.

## VD

| Etichetta del campo | Estrazione corrente |
|---|---|
| ALL Pkts received so far | `vd.packets_all`; contesto osservatore/output/input |
| Audio Card Output data | Intestazione/segnaposto, non metrica |
| Audio Input data | Intestazione/segnaposto, non metrica |
| Audio Output data | Intestazione/segnaposto, non metrica |
| Audio card Input data | Intestazione/segnaposto, non metrica |
| Audio currently in buffer (ms) | `vd.buffer`; contesto osservatore/output/input |
| Audio file Output data | Intestazione/segnaposto, non metrica |
| Connected devices info | Intestazione/segnaposto, non metrica |
| Cumulative write rate is VALORE samples per second. | `vd.write_rate` |
| Current decoding error event duration (msecs) | `vd.decoding_error_duration`; contesto osservatore/output/input |
| Current encoding error event duration (msecs) | `vd.encoding_error_duration`; contesto osservatore/output/input |
| Current processing stage | `periodic_metadata`: stato/codice/timestamp osservato |
| Current read error event duration (msecs) | `vd.read_error_duration`; contesto osservatore/output/input |
| Current write error event duration (msecs) | `vd.write_error_duration`; contesto osservatore/output/input |
| Currently in buffer underrun on this VOD | `periodic_metadata`: stato booleano |
| Currently in decoding error event | `periodic_metadata`: stato booleano |
| Currently in encoding error event | `periodic_metadata`: stato booleano |
| Currently in partial buffer underrun | `periodic_metadata`: stato booleano |
| Currently in read error event | `periodic_metadata`: stato booleano |
| Currently in total buffer underrun | `periodic_metadata`: stato booleano |
| Currently in underrun for this VOD  since VALORE msecs. | `vd.underrun_duration` |
| Currently in write error event | `periodic_metadata`: stato booleano |
| Last read processing stage known | `periodic_metadata`: stato/codice/timestamp osservato |
| Last write processing stage known | `periodic_metadata`: stato/codice/timestamp osservato |
| Last written RTP SN | `periodic_metadata`: identificatore intero |
| Network Audio Input data | Intestazione/segnaposto, non metrica |
| Network Audio Output data | Intestazione/segnaposto, non metrica |
| Number of Decoding Errors | `vd.decoding_errors`; contesto osservatore/output/input |
| Number of Encoding Errors | `vd.encoding_errors`; contesto osservatore/output/input |
| Number of Read Errors | `vd.read_errors`; contesto osservatore/output/input |
| Number of Write Errors | `vd.write_errors`; contesto osservatore/output/input |
| Number of device reset for scheduling delay | `vd.scheduling_resets`; contesto osservatore/output/input |
| RTCP Pkts received so far | `vd.packets_rtcp`; contesto osservatore/output/input |
| RTP BAD Pkts received so far | `vd.packets_rtp_bad`; contesto osservatore/output/input |
| RTP GOOD Pkts received so far | `vd.packets_rtp_good`; contesto osservatore/output/input |
| RTP Pkts received so far | `vd.packets_rtp`; contesto osservatore/output/input |
| RTP first BAD pkt SN | `periodic_metadata`: identificatore intero |
| RTP first GOOD pkt SN | `periodic_metadata`: identificatore intero |
| RTP last BAD pkt SN | `periodic_metadata`: identificatore intero |
| RTP last GOOD pkt SN | `periodic_metadata`: identificatore intero |
| RTP last pkt GOOD ROC | `periodic_metadata`: identificatore intero |
| RTP last pkt ROC | `periodic_metadata`: identificatore intero |
| RTP last pkt SN | `periodic_metadata`: identificatore intero |
| RTP last streak of BAD Pkts received | `vd.streak_bad`; contesto osservatore/output/input |
| RTP last streak of GOOD Pkts received | `vd.streak_good`; contesto osservatore/output/input |
| Running cycles - Tbody Runs, Read, Decode, AdaptToMw, Append  - | `vd.cycles_*`, cinque campi per fase |
| Running cycles - Tbody Runs, ReadFromMW, AdaptToCodec, Encode, Write - | `vd.cycles_*`, cinque campi per fase |
| Total bytes read from source | `vd.bytes_read`; contesto osservatore/output/input |
| Total bytes sent to decoder | `vd.bytes_decoder`; contesto osservatore/output/input |
| Total media read from middleware | `vd.media_read`; contesto osservatore/output/input |
| Total media sent out | `vd.media_sent`; contesto osservatore/output/input |
| Total media sent to middleware | `vd.media_middleware`; contesto osservatore/output/input |
| Total packets/chunks sent to decoder | `vd.chunks_decoder`; contesto osservatore/output/input |
| Virtual device info | Intestazione/segnaposto, non metrica |
| audio samples skipped so far | `vd.samples_skipped`; contesto osservatore/output/input |
| number of buffer underruns occurred on this ring for this VOD | `vd.underruns`; contesto osservatore/output/input |
| ring current max buffer usecs (for dynamic dejittering) | `vd.dejitter_target`; contesto osservatore/output/input |
| ring hard max buffer usecs | `vd.buffer_hard_max`; contesto osservatore/output/input |
| ring min buffer usecs | `vd.buffer_min`; contesto osservatore/output/input |
| silence msecs played out for buffer underruns occurred on this ring for this VOD | `vd.silence_played`; contesto osservatore/output/input |
| silence msecs skipped so far | `vd.silence_skipped`; contesto osservatore/output/input |

Le righe reset/scheduling contengono due campi (conteggio e ritardo); le righe Running cycles cinque conteggi. Current processing stage include stato/codice e timestamp. Total bytes read from source può ripetersi nel blocco. Non equiparare il numero di etichette al numero di metriche scalari.

## RTCP

| Etichetta del campo | Estrazione corrente |
|---|---|
| RTCP Message n. | `periodic_metadata`: clock o identificatore osservato |
| SSRC of this source | Dimensione SSRC delle metriche |
| Sender Report - ntp timestamp received from this source | `periodic_metadata`: clock o identificatore osservato |
| Sender Report -  rtp timestamp corresponding to ntp time | `periodic_metadata`: clock o identificatore osservato |
| Sender Report - Number of packets sent by this remote peer (total) | `rtcp.packets_sent_total` |
| Sender Report - Number of packets sent by this remote peer (since last report) | `rtcp.packets_sent_interval` |
| Packet we received from this source (total) | rtcp.packets_received |
| Packet we received from this source (since last report) | `rtcp.packets_received_interval` |
| Packet loss we perceive from this source (since last report) | `rtcp.loss`, esponenti supportati; fuori range `valid=0` |
| Jitter we perceive from this source (since last report) | rtcp.jitter |
| RTT to this source | rtcp.rtt |
| Receiver Report - pkt lost by this peer (total) | `rtcp.packets_lost_total` |
| Receiver Report - pkt lost by this peer (since last report) | `rtcp.packets_lost_interval` |
| Receiver Report - remote peer pkt loss (since last RR) | rtcp.loss |
| Receiver Report - jitter perceived by this remote peer(since last report) | rtcp.jitter |

## JSON KPE

Famiglie osservate: audio.dtmf_rtt, audio.jitter, audio.jitter_rfc3550, audio.ploss_jitter, common.ploss, common.rtt, common.rtp_pkt_rx, common.rtp_pkt_tx.

Per ciascuna: incoming/outgoing, last/avg/min/max. Valori numerici finiti estratti genericamente; N/A non trasformato in zero. Unità raw salvo i conteggi pacchetti.

## Altri messaggi periodici

- Heartbeat alive and kicking: byte letti/scritti, durata della finestra e cicli per fase; estratti in metriche e `periodic_metadata`.
- Monitor NART/NAWT: fase/codice e timestamp di avanzamento; estratti in metriche e `periodic_metadata`.

Gli episodi di underrun, i missing packets e gli aggiornamenti del massimo ritardo sono eventi distinti; non fanno parte delle righe periodiche censite sopra.

Implementazione: schema 11, parser 1.12.0, recupero `periodic-1`.
La copertura riguarda la struttura testuale osservata Kalliope 1.5.0 / VDK 4.14.0
build 8cb1a8d2; il riconoscimento non presume che il numero versione definisca
il formato. I pattern precedenti rimangono supportati. Intestazioni/NYI non
producono metriche. Le righe ripetute nello stesso contesto non sono campioni
indipendenti. I valori di durata media senza `ms` esplicito rimangono `raw`.
