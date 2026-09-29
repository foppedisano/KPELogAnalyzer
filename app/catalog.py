"""Metric dictionary shared by API and documentation."""
from .media_semantics import metric_semantics
CATALOG = [
 dict(name='telemetry.network_loss',title='Perdita RTP su intervallo verificato',unit='%',kind='interval',source='Telemetria strutturata: rtp-sequence-window/1 oppure delta dei contatori RTCP SR/RR.',meaning='Perdita riferita a una finestra esplicita, prima di PLC/FEC e scarti di playout. Timestamp UTC derivato dal tempo monotono; originali ed evidenze conservati.',limits='Contatori di arrivo e attesi non sono sottratti senza una coorte comune. Reset, conflitti, finestre sovrapposte e gap RTCP oltre 30 s escludono la derivazione. Non è una misura di qualità percepita. Per i report remoti il tempo è quello locale di osservazione dei report, non una sincronizzazione con il peer.'),
 dict(name='vd.missing_packets',title='Pacchetti mancanti per evento NART',unit='packets',kind='event',source='[NARTn of Line m] Packet loss occurred … SN delta is … (N missing packets)',meaning='Numero esplicito di pacchetti segnalati come mancanti in un singolo salto della sequenza. Un punto isolato al timestamp del messaggio.',limits='Non è una percentuale RTCP, un contatore cumulativo o una perdita definitiva: riordino, arrivi tardivi e recupero possono modificare l’esito. Non sommare segnalazioni come pacchetti unici persi. Device, linea e sorgente restano separati; nessun SSRC viene inventato. Rotazioni con identico timestamp e identico messaggio sono deduplicate; numeri di sequenza diversi restano eventi distinti.'),
 dict(name='rtcp.rtt', title='RTT RTCP', unit='ms', kind='sample', source='RTT to this source: … ms; RTT by this source: … microseconds (÷1000)', meaning='Tempo di andata e ritorno riportato per la sorgente RTP/RTCP.', limits='Non è ritardo audio a senso unico. Può includere il percorso verso un relay/PBX. Un picco non localizza il guasto su un endpoint.'),
 dict(name='rtcp.jitter', title='Jitter RTCP', unit='ms', kind='sample', source='Jitter we perceive …; Receiver Report - jitter perceived by this remote peer …', meaning='Variabilità degli arrivi riportata localmente (incoming) o dal peer (outgoing).', limits='Separare direzioni, flow e SSRC. Non coincide con occupazione o target del buffer, né con il massimo VD.'),
 dict(name='rtcp.loss', title='Perdita RTCP', unit='%', kind='sample', source='Packet loss we perceive …; Receiver Report - remote peer pkt loss …', meaning='Percentuale di perdita riferita all’intervallo dichiarato dal report.', limits='Valori validi da 0 a 100. La media semplice dei report non è la perdita totale ponderata per pacchetti.'),
 dict(name='rtcp.packets_received', title='Pacchetti ricevuti', unit='packets', kind='counter', source='Packet we received from this source (total)', meaning='Contatore dei pacchetti ricevuti per sorgente.', limits='Può ripartire dopo reset/sessione. Non sommare campioni cumulativi né esportazioni dello stesso dispositivo.'),
 dict(name='network.ping', title='Ping ICMP', unit='ms', kind='sample', source='received … bytes … time=… ms', meaning='Tempo di andata e ritorno della sonda ICMP.', limits='La destinazione ICMP può differire dal peer multimediale. Non sostituisce RTT RTCP.'),
 dict(name='vd.max_arrival_delay', title='Massimo ritardo di arrivo NART', unit='ms', kind='event / gauge', source='m_maxPktArrivalTimeDelay to ms …; campo periodico m_maxPktArrivalTimeDelay (ms): …', meaning='Valore dichiarato dal motore per il massimo ritardo di arrivo. Nei WARNING è un aggiornamento del massimo.', limits='Il massimo può scendere quando il motore cambia finestra o stato. WARNING rappresentati come punti isolati: non sono campioni periodici del jitter.'),
 dict(name='vd.dejitter_target', title='Limite dinamico dejitter', unit='ms', kind='gauge', source='ring current max buffer usecs (for dynamic dejittering): … (÷1000)', meaning='Limite corrente del ring buffer nel device indicato nel contesto; su NART sostiene il dejittering della ricezione RTP.', limits='Non è l’audio effettivamente in coda. Si escludono gli altri device per sezione, non per valore: 20000 µs su NART è un valido campione di 20 ms.'),
 dict(name='vd.buffer', title='Audio nel buffer del device', unit='ms', kind='gauge', source='buffer len in usecs: … (÷1000); Audio currently in buffer (ms): …', meaning='Durata dell’audio presente nel buffer del device indicato nel contesto; su NART riguarda la ricezione RTP, sugli altri VID la rispettiva sorgente media.', limits='È una misura locale, non il ritardo totale della chiamata. I due nomi sono alias empirici; il valore e l’unità originali restano nel DB.'),
 dict(name='vd.silence_skipped', title='Silenzio saltato cumulativo', unit='ms (grafico: ms o s)', kind='counter', source='silence usecs skipped so far: … (÷1000); silence msecs skipped so far: …', meaning='Durata cumulativa del silenzio saltato dichiarata dal device. In Diagnostica A/B si può scegliere ms oppure dividere ancora per 1000 per mostrare secondi; nel dettaglio chiamata resta in ms.', limits='Non è perdita pacchetti né prova di voce persa. Può azzerarsi: non si presume continuità per tutta la chiamata.'),
 dict(name='derived.silence_delta', title='Incremento silenzio saltato', unit='ms', kind='interval', source='Differenza tra due campioni consecutivi di vd.silence_skipped, stessa prospettiva e device.', meaning='Quantità aggiuntiva nel periodo fra i due campioni; mostrata al timestamp del secondo.', limits='Il primo valore, un calo del contatore e un intervallo >30 s non producono delta. Non è un tasso al secondo. Entrambi gli eventi sono indicati come evidenza.'),
 dict(name='derived.buffer_sum', title='Somma dei buffer A+B', unit='ms', kind='derived gauge', source='Somma di vd.buffer dei due device scelti dopo correzione degli orologi; interpolazione lineare nei soli intervalli comuni.', meaning='Indicatore del buffering combinato dei due punti di vista, utile per confrontare gli andamenti.', limits='Non misura il ritardo end-to-end o conversazionale. Non include rete, codec o mixer; i due buffer ricevono direzioni diverse. Niente estrapolazione o interpolazione oltre 30 s. Servono due prospettive distinte, non due copie dello stesso dispositivo.'),
]
CATALOG.append(dict(name='derived.dejitter_sum',title='Somma dei limiti dinamici A+B',unit='ms',kind='derived gauge',source='Somma di vd.dejitter_target di A e B con interpolazione lineare solo nella copertura comune e con intervalli al massimo di 30 s.',meaning='Limiti dinamici combinati dei buffer di ricezione NART; distinto dalla somma dell’audio realmente in coda.',limits='Non è occupazione effettiva né misura di ritardo conversazionale. Nessuna estrapolazione; la selezione del periodo viene applicata prima della derivazione. Ogni punto conserva le evidenze dei campioni originali.'))
CATALOG.extend([
 dict(name='incident.buffer_underrun',title='Episodio di buffer underrun',unit='ms',kind='episode',source='Buffer underrun occurred; Still in buffer underrun … Event is currently … msecs; Buffer underrun event terminated … Event was … msecs long.',meaning='Periodo in cui l’osservatore non ottiene audio dal device NART selezionato. La durata dichiarata dal motore resta distinta dalla distanza fra timestamp dei messaggi.',limits='AWT (uscita audio) e gli altri VD osservati restano separati; VD generico non identifica una registrazione su file: non sommare le loro durate. Senza inizio, un messaggio di fine con durata consente solo di ricavare l’inizio; senza fine l’episodio resta aperto. Contatori periodici e mutedReasons non vengono trasformati in episodi. Derivato su richiesta dagli eventi, non memorizzato in metrics.'),
 dict(name='incident.media_missing',title='Episodio di media missing',unit='ms (minimo stimato)',kind='episode',source='Line … reported that flow … has not received RTP media for more than … sec/ms; has re-started receiving RTP media / has started receiving RTP media again.',meaning='Assenza RTP segnalata su una linea e un flow. La soglia prima della segnalazione si aggiunge al tempo fino alla ripresa per stimare un limite inferiore della durata.',limits='L’inizio effettivo non è misurato: la barra parte dalla segnalazione meno la soglia. Il limite è ricavato dai messaggi e dipende dai tempi di notifica. Ripresa senza segnalazione precedente: durata sconosciuta. Nessuna chiusura viene inventata alla fine della chiamata. Eventi di coda media_missing e riepiloghi non duplicano gli episodi.')
])
for name, title, meaning in [
 ('audio.dtmf_rtt','RTT DTMF KPE','Statistica KPE denominata dtmf_rtt; semantica dettagliata da confermare col produttore.'),
 ('audio.jitter','Jitter KPE','Statistica del motore denominata jitter.'),
 ('audio.jitter_rfc3550','Jitter RFC3550 KPE','Statistica del motore etichettata jitter_rfc3550.'),
 ('audio.ploss_jitter','Perdita jitter KPE','Statistica del motore denominata ploss_jitter; non equiparata automaticamente alla perdita RTCP.'),
 ('common.ploss','Perdita KPE','Statistica del motore denominata ploss.'),
 ('common.rtt','RTT KPE','Statistica del motore denominata rtt.'),
 ('common.rtp_pkt_rx','Pacchetti RX KPE','Conteggio RTP ricevuto dichiarato dal motore.'),
 ('common.rtp_pkt_tx','Pacchetti TX KPE','Conteggio RTP trasmesso dichiarato dal motore.')]:
 CATALOG.append(dict(name='kpe.'+name,title=title,unit='packets' if 'rtp_pkt' in name else 'raw',kind='reported statistic',source='JSON incoming/outgoing → '+name.replace('.', ' → ')+' → last/avg/min/max',meaning=meaning,limits='last/avg/min/max restano distinti; finestra statistica e unità non dichiarate non vengono dedotte. Le metriche raw non entrano nel grafico in millisecondi. Valori non numerici, NaN e infinito non diventano zero.'))


CATALOG.append(dict(name='derived.mos_reference',title='MOS a profilo fisso · sola perdita',unit='MOS',kind='derived step',source='Perdita RTCP (%) locale o dichiarata dal peer, oppure perdita da finestre strutturate verificate. Profilo loss-reference-1: G.711 10 ms, PLC Appendix I, Ie=0, Bpl=25.1, BurstR=1, R base=93.2.',meaning='Indice stimato a profilo costante per confrontare la perdita nelle due direzioni. R=93.2−95p/(p+25.1), limitato a 0–100; MOS=1+0.035R+0.000007R(R−60)(100−R).',limits='Non è qualità vocale misurata né E-model completo. Non valuta jitter, ritardo, scarti, burst o PLC reale. Nei log tradizionali il report riguarda il passato; il valore viene mantenuto al massimo 30 s fino al report successivo o alla fine chiamata. La telemetria verificata descrive invece la sua finestra esplicita già osservata. Report invalidi o discordanti interrompono la curva. Nel pannello MOS il peer è scelto esplicitamente e la sua ricezione locale è riutilizzata. Riferimenti: ITU-T G.107 (2015), G.113 (2024) tabella I.4.'))


# Shared dictionary for the observed 1.5.0 / VDK 4.14.0 textual structure.
from .periodic import FIELDS
PERIODIC_LIMITS = ('Osservatore, output, input, device e ciclo di vita restano distinti. '
    'Contatori cumulativi: non sommare campioni; a_counter_intervals segnala initial, reset, invalid, conflict e gap oltre 30 s. '
    'Un delta non localizza il fenomeno dentro l’intervallo. GOOD/BAD non significa pacchetti persi. '
    'Ciclo unknown = nessuna creazione osservata, non continuità dimostrata. Valori finiti invalidi conservati; NaN/N/A mai zero.')
for label,key,unit,kind in FIELDS:
    name='vd.'+key
    if any(m['name']==name for m in CATALOG):
        entry=next(m for m in CATALOG if m['name']==name)
        entry['limits']+=' Nel formato recente sono conservate anche sezioni non NART, con contesto proprio. '+PERIODIC_LIMITS
        continue
    CATALOG.append(dict(name=name,title=label,unit='ms' if unit=='us' else unit,kind=kind,
        source=label+(' (µs ÷ 1000; originali raw_value/raw_unit)' if unit=='us' else ''),
        meaning='Valore dichiarato nel blocco periodico del device/lettore. '+('Durata dichiarata in ms; senza suffisso esplicito si conserva raw.' if key.startswith('media_') else ''),
        limits=PERIODIC_LIMITS))
for key,title,unit,kind in [
 ('write_rate','Frequenza cumulativa di scrittura','samples/s','gauge'),
 ('scheduling_delay','Ritardo accumulato di scheduling','ms','counter'),
 ('underrun_duration','Durata corrente underrun del lettore','ms','gauge'),
 ('heartbeat_bytes_read','Byte letti heartbeat','bytes','reported statistic'),
 ('heartbeat_bytes_written','Byte scritti heartbeat','bytes','reported statistic'),
 ('heartbeat_window','Finestra cicli heartbeat','ms','interval'),
 *[('cycles_'+key,'Cicli '+title,'count','counter / reported statistic') for key,title in
   [('tbody_runs','Tbody Runs'),('read','Read'),('decode','Decode'),('adapttomw','AdaptToMw'),('append','Append'),
    ('readfrommw','ReadFromMW'),('adapttocodec','AdaptToCodec'),('encode','Encode'),('write','Write')]]]:
    CATALOG.append(dict(name='vd.'+key,title=title,unit=unit,kind=kind,source='Running Info / alive and kicking: '+title,
        meaning='Valore riportato dal motore. I cicli heartbeat si riferiscono alla finestra last ms; i byte heartbeat hanno finestra non confermata.',limits=PERIODIC_LIMITS))
for key,title,kind in [
 ('packets_sent_total','Pacchetti inviati dal peer, totale','counter'),
 ('packets_sent_interval','Pacchetti inviati dal peer, intervallo','interval'),
 ('packets_received_interval','Pacchetti ricevuti, intervallo','interval'),
 ('packets_lost_total','Pacchetti persi dal peer, totale','counter'),
 ('packets_lost_interval','Pacchetti persi dal peer, intervallo','interval')]:
    CATALOG.append(dict(name='rtcp.'+key,title=title,unit='packets',kind=kind,source='Campo numerico esplicito Sender/Receiver Report RTCP',
        meaning=title+'. Numeri esponenziali accettati; conteggi finiti negativi o non interi restano invalidi.',limits=PERIODIC_LIMITS+' Non derivare perdita da contatori senza coorte comune.'))
CATALOG.append(dict(name='derived.silence_played_delta',title='Incremento silenzio riprodotto per underrun',unit='ms',kind='interval',
    source='Differenza consecutiva di vd.silence_played nello stesso contesto, massimo 30 s, evidenze dei due campioni.',
    meaning='Silenzio aggiunto al ring per quello specifico lettore/input tra due osservazioni.',
    limits=PERIODIC_LIMITS+' Confrontare con episodi, senza sommare le due misure. Non è occupazione a precisione di un secondo.'))
PERIODIC_METADATA = [
    dict(name='vd.currently_in_*',type='boolean',meaning='Stati total/partial/VOD underrun e read/write/encoding/decoding error; scope del device corrente.'),
    dict(name='vd.current_processing_stage / vd.last_read_processing_stage_known / vd.last_write_processing_stage_known / vd.monitor_stage',type='object',meaning='state, code e timestamp osservato; nessuna conversione di fuso o latenza. Monitor: flow ignoto, non quello hardcoded.'),
    dict(name='vd.last_written_rtp_sn / vd.rtp_*_sn / vd.rtp_*_roc',type='integer',meaning='SN e ROC riportati, non perdite; conservare separati e considerare wrap.'),
    dict(name='vd.heartbeat_device_id',type='string',meaning='Identificatore VD osservato nel messaggio, non SSRC.'),
    dict(name='rtcp.message_number / rtcp.rtp_timestamp',type='integer or string',meaning='Identificatore/clock osservato; testo preservato se non intero.'),
    dict(name='rtcp.ntp_timestamp',type='string',meaning='Clock remoto come scritto, senza fuso dedotto o conversione in latenza.')]
for entry in CATALOG:
    if entry['name']=='vd.silence_played': entry['title']='Silenzio riprodotto per underrun, cumulativo'
    if entry['name']=='vd.underruns': entry['title']='Numero cumulativo di underrun del lettore'


_MEANINGS = {
 'vd.scheduling_delay':'Ritardo accumulato di scheduling dichiarato dal thread del VD. Descrive la temporizzazione locale, non il tempo di transito RTP.',
 'vd.scheduling_resets':'Numero di reset che il device attribuisce a ritardo di scheduling. Non è un conteggio di pacchetti persi o di reset della rete.',
 'vd.underruns':'Numero cumulativo di underrun del ring per lo specifico VOD lettore e VID collegato. Non è il conteggio complessivo di guasti della chiamata.',
 'vd.underrun_duration':'Durata dichiarata dell’underrun attualmente in corso per il lettore/input osservato; non contatore cumulativo né durata totale della chiamata.',
 'vd.silence_played':'Durata cumulativa del silenzio riprodotto per compensare underrun del ring per lo specifico VOD e VID. Non prova silenzio della sorgente o perdita RTP.',
 'vd.samples_skipped':'Numero cumulativo di campioni audio saltati dal device. Campioni audio e pacchetti RTP sono grandezze diverse.',
 'vd.write_rate':'Frequenza di scrittura riportata dal device in campioni/s. Non è bitrate di rete e non dimostra da sola regolarità dello scheduling.',
 'vd.buffer_hard_max':'Limite massimo rigido del ring buffer dichiarato dal device; non occupazione effettiva.',
 'vd.buffer_min':'Limite minimo del ring buffer dichiarato dal device; non minimo misurato sull’intera chiamata.',
 'vd.bytes_read':'Byte cumulativi letti dalla sorgente del device: rete, scheda audio o file secondo la specializzazione osservata. Non automaticamente traffico RTP.',
 'vd.bytes_decoder':'Byte cumulativi inviati al decoder, non necessariamente byte ricevuti sulla rete.',
 'vd.chunks_decoder':'Pacchetti/chunk cumulativi inviati al decoder. Chunk non equivale automaticamente a datagramma RTP.',
}
for entry in CATALOG:
    name=entry['name']
    entry['semantics']=metric_semantics(name)
    if name in _MEANINGS: entry['meaning']=_MEANINGS[name]
    if name in ('vd.media_read','vd.media_sent','vd.media_middleware'):
        entry['meaning']={'vd.media_read':'Durata cumulativa del media letto dal middleware.', 'vd.media_sent':'Durata cumulativa del media inviato in uscita.', 'vd.media_middleware':'Durata cumulativa del media inviato al middleware.'}[name]+' Non è tempo CPU, latenza o durata della chiamata. Usare ms solo con suffisso esplicito, altrimenti raw.'
    if name.startswith('vd.') and (name.endswith('_errors') or name.endswith('_error_duration')):
        entry['meaning']='Errori nella fase indicata dal campo originale (lettura, scrittura, codifica o decodifica). '+('Numero cumulativo di errori dichiarati.' if name.endswith('_errors') else 'Durata dell’evento di errore corrente, non totale cumulativo.')+' La fase e il device non identificano automaticamente la causa di rete.'
    if name.startswith('vd.heartbeat_bytes_'):
        entry['meaning']='Byte '+('letti' if name.endswith('read') else 'scritti')+' riportati dal thread nel messaggio heartbeat; finestra dei byte non confermata. Non derivare un bitrate dividendo per la finestra dei cicli.'
    if name=='vd.heartbeat_window':
        entry['meaning']='Finestra last ms dichiarata per i conteggi dei cicli heartbeat. Non è ritardo di scheduling né intervallo confermato per i byte.'
    if name.startswith('vd.cycles_'):
        entry['meaning']='Conteggio riportato per la fase '+name.removeprefix('vd.cycles_')+'. I cicli del thread non sono cicli CPU né millisecondi. Nei messaggi heartbeat vale la finestra last ms; distinguere il contesto dai cumulativi Running Info.'
    if name.startswith(('vd.packets_','vd.streak_')):
        entry['meaning']='Conteggio di ricezione dichiarato per la categoria del campo sorgente; mantenere separati totale, RTP, RTCP e sequenze GOOD/BAD. GOOD/BAD è una classificazione del motore, non una definizione confermata di perdita o qualità vocale.'
    if name.startswith('vd.'):
        entry['limits']+=' Il VD opera in un thread: distinguere scheduling locale, I/O e trasporto RTP. Un sintomo non identifica da solo una causa di rete.'


def catalog(db):
 result = list(CATALOG)
 known = {x['name'] for x in result}
 for row in db.execute('SELECT DISTINCT name,unit FROM metrics ORDER BY name'):
  if row['name'] not in known:
   result.append(dict(name=row['name'],title=row['name'],unit=row['unit'],kind='reported statistic',source='Campo numerico estratto dal log; consultare evento originale.',meaning='Metrica non ancora documentata individualmente.',semantics=metric_semantics('unknown'),limits='Semantica e unità non confermate: nessuna diagnosi automatica.'))
   known.add(row['name'])
 return result
