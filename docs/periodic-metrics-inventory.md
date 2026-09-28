# Campi periodici del formato recente

Versioni e piano: [documento di passaggio](periodic-metrics-implementation.md).

Questa lista contiene nomi di campi del formato, non estratti dei log reali, valori osservati o identificativi personali. Evidenze e frequenze per contesto rimangono negli allegati locali esclusi da Git.

## VD

| Etichetta del campo | Estrazione corrente |
|---|---|
| ALL Pkts received so far | Non strutturato |
| Audio Card Output data | Intestazione/segnaposto, non metrica |
| Audio Input data | Intestazione/segnaposto, non metrica |
| Audio Output data | Intestazione/segnaposto, non metrica |
| Audio card Input data | Intestazione/segnaposto, non metrica |
| Audio currently in buffer (ms) | vd.buffer (solo NART) |
| Audio file Output data | Intestazione/segnaposto, non metrica |
| Connected devices info | Intestazione/segnaposto, non metrica |
| Cumulative write rate is VALORE samples per second. | Non strutturato |
| Current decoding error event duration (msecs) | Non strutturato |
| Current encoding error event duration (msecs) | Non strutturato |
| Current processing stage | Non strutturato |
| Current read error event duration (msecs) | Non strutturato |
| Current write error event duration (msecs) | Non strutturato |
| Currently in buffer underrun on this VOD | Non strutturato |
| Currently in decoding error event | Non strutturato |
| Currently in encoding error event | Non strutturato |
| Currently in partial buffer underrun | Non strutturato |
| Currently in read error event | Non strutturato |
| Currently in total buffer underrun | Non strutturato |
| Currently in underrun for this VOD  since VALORE msecs. | Non strutturato |
| Currently in write error event | Non strutturato |
| Last read processing stage known | Non strutturato |
| Last write processing stage known | Non strutturato |
| Last written RTP SN | Non strutturato |
| Network Audio Input data | Intestazione/segnaposto, non metrica |
| Network Audio Output data | Intestazione/segnaposto, non metrica |
| Number of Decoding Errors | Non strutturato |
| Number of Encoding Errors | Non strutturato |
| Number of Read Errors | Non strutturato |
| Number of Write Errors | Non strutturato |
| Number of device reset for scheduling delay | Non strutturato |
| RTCP Pkts received so far | Non strutturato |
| RTP BAD Pkts received so far | Non strutturato |
| RTP GOOD Pkts received so far | Non strutturato |
| RTP Pkts received so far | Non strutturato |
| RTP first BAD pkt SN | Non strutturato |
| RTP first GOOD pkt SN | Non strutturato |
| RTP last BAD pkt SN | Non strutturato |
| RTP last GOOD pkt SN | Non strutturato |
| RTP last pkt GOOD ROC | Non strutturato |
| RTP last pkt ROC | Non strutturato |
| RTP last pkt SN | Non strutturato |
| RTP last streak of BAD Pkts received | Non strutturato |
| RTP last streak of GOOD Pkts received | Non strutturato |
| Running cycles - Tbody Runs, Read, Decode, AdaptToMw, Append  - | Non strutturato |
| Running cycles - Tbody Runs, ReadFromMW, AdaptToCodec, Encode, Write - | Non strutturato |
| Total bytes read from source | Non strutturato |
| Total bytes sent to decoder | Non strutturato |
| Total media read from middleware | Non strutturato |
| Total media sent out | Non strutturato |
| Total media sent to middleware | Non strutturato |
| Total packets/chunks sent to decoder | Non strutturato |
| Virtual device info | Intestazione/segnaposto, non metrica |
| audio samples skipped so far | Non strutturato |
| number of buffer underruns occurred on this ring for this VOD | Non strutturato |
| ring current max buffer usecs (for dynamic dejittering) | vd.dejitter_target (solo NART) |
| ring hard max buffer usecs | Non strutturato |
| ring min buffer usecs | Non strutturato |
| silence msecs played out for buffer underruns occurred on this ring for this VOD | Non strutturato |
| silence msecs skipped so far | vd.silence_skipped (solo NART) |

Le righe reset/scheduling contengono due campi (conteggio e ritardo); le righe Running cycles cinque conteggi. Current processing stage include stato/codice e timestamp. Total bytes read from source può ripetersi nel blocco. Non equiparare il numero di etichette al numero di metriche scalari.

## RTCP

| Etichetta del campo | Estrazione corrente |
|---|---|
| RTCP Message n. | Non strutturato |
| SSRC of this source | Dimensione SSRC delle metriche |
| Sender Report - ntp timestamp received from this source | Non strutturato |
| Sender Report -  rtp timestamp corresponding to ntp time | Non strutturato |
| Sender Report - Number of packets sent by this remote peer (total) | Non strutturato |
| Sender Report - Number of packets sent by this remote peer (since last report) | Non strutturato |
| Packet we received from this source (total) | rtcp.packets_received |
| Packet we received from this source (since last report) | Non strutturato |
| Packet loss we perceive from this source (since last report) | rtcp.loss; manca supporto alla notazione scientifica |
| Jitter we perceive from this source (since last report) | rtcp.jitter |
| RTT to this source | rtcp.rtt |
| Receiver Report - pkt lost by this peer (total) | Non strutturato |
| Receiver Report - pkt lost by this peer (since last report) | Non strutturato |
| Receiver Report - remote peer pkt loss (since last RR) | rtcp.loss |
| Receiver Report - jitter perceived by this remote peer(since last report) | rtcp.jitter |

## JSON KPE

Famiglie osservate: audio.dtmf_rtt, audio.jitter, audio.jitter_rfc3550, audio.ploss_jitter, common.ploss, common.rtt, common.rtp_pkt_rx, common.rtp_pkt_tx.

Per ciascuna: incoming/outgoing, last/avg/min/max. Valori numerici finiti estratti genericamente; N/A non trasformato in zero. Unità raw salvo i conteggi pacchetti.

## Altri messaggi periodici

- Heartbeat alive and kicking: byte letti/scritti, durata della finestra e cicli per fase; non strutturati.
- Monitor NART/NAWT: fase/codice e timestamp di avanzamento; non strutturati.

Gli episodi di underrun, i missing packets e gli aggiornamenti del massimo ritardo sono eventi distinti; non fanno parte delle righe periodiche censite sopra.
