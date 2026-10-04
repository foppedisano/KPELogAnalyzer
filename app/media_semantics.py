"""Shared terminology supplied by the VDK domain owner; no parser inference."""
MEDIA_PLANE = dict(
    version='vdk-media-1',
    basis='Gerarchia e funzionamento confermati dal referente VDK; unità e campi specifici restano vincolati alle evidenze dei log.',
    devices=[dict(name=n,parent=p,expanded=e,role=r) for n,p,e,r in [
        ('VD',None,'Virtual Device','Classe generale; ogni VD opera nel proprio thread.'),
        ('VID','VD','Virtual Input Device','Introduce media nel grafo e lo distribuisce a tutti i VOD connessi.'),
        ('VOD','VD','Virtual Output Device','Riceve media dai VID connessi, li miscela e scrive sulla propria destinazione.'),
        ('VAID','VID','Virtual Audio Input Device','Ramo audio degli input virtuali.'),
        ('VAOD','VOD','Virtual Audio Output Device','Ramo audio degli output virtuali.'),
        ('VVID','VID','Virtual Video Input Device','Ramo video; non presente nei log KPE attuali.'),
        ('VVOD','VOD','Virtual Video Output Device','Ramo video; non presente nei log KPE attuali.'),
        ('NART','VAID','Network Audio Reader Thread','Legge il media ricevuto dalla rete RTP.'),
        ('NAWT','VAOD','Network Audio Writer Thread','Scrive il media da trasmettere sulla rete RTP.'),
        ('ART','VAID','Audio Reader Thread','Legge dalla scheda audio o equivalente: ruolo del microfono.'),
        ('AWT','VAOD','Audio Writer Thread','Scrive sulla scheda audio o equivalente: ruolo degli speaker.'),
        ('FileReaderThread','VAID','FileReaderThread','Legge media da file.'),
        ('FileWriterThread','VAOD','FileWriterThread','Scrive media su file.'),
    ]],
    rules=[
        'Input/output si riferiscono al grafo interno del media plane, non al chiamante/chiamato. KPE attualmente tratta solo audio.',
        'Le connessioni VID → VOD sono molti-a-molti: un VID distribuisce a più VOD; un VOD miscela più VID. ART → NAWT e NART → AWT sono percorsi elementari, non topologie da presumere nei log.',
        'Ogni VD ha un thread. Le statistiche comuni di scheduling descrivono la temporizzazione locale; non sono direttamente jitter o perdita di rete.',
        'Le statistiche specifiche NART descrivono la ricezione RTP osservata localmente. Il thread ricevente è soggetto allo scheduling: i soli sintomi non separano automaticamente rete e ritardi locali.',
        'RTP trasporta il media; SIP appartiene alla segnalazione. RTCP riporta statistiche del trasporto RTP.',
        'VD è una classe generale, non sinonimo di registrazione su file. Un nome VD generico non dimostra la destinazione; occorre il device specializzato o altra evidenza esplicita.',
        'Distinguere stato del thread, ricezione RTP, disponibilità del buffer e conseguenze sul media. Underrun e silenzio riprodotto non provano da soli perdita di rete o qualità percepita.',
        'Il prefisso storico vd. identifica una famiglia di metriche, non una classe concreta né una direzione. Anche un NART può esporre scheduling e buffer oltre alle statistiche RTP.',
    ],
    context=dict(observer='Emittente/osservatore del messaggio: non automaticamente il device misurato.',
        output_device='VOD della sezione di uscita; il suo output può essere un mix di più VID.',
        input_device='VID collegato nella sezione corrente; mantenere distinta ogni relazione VID/VOD.',
        device='Device cui appartiene il campo corrente; non dedurne la classe dal solo prefisso della metrica.',
        lifecycle='Ciclo delimitato da creazioni osservate; unknown non dimostra continuità.',
        direction='Direzione osservata del trasporto; distinta da VID/VOD. outgoing nei report RTCP descrive la ricezione del peer.'),
)

DOMAINS = {
    'scheduling':'Scheduling del thread locale',
    'rtp_transport':'Trasporto RTP osservato',
    'buffer_media':'Buffer e disponibilità del media',
    'processing':'Elaborazione e I/O del device',
    'network_probe':'Sonda di rete',
    'quality_model':'Modello di qualità derivato',
    'unspecified':'Semantica specifica non confermata',
}

ORIENTATIONS = {
    'awt_quality': 'Continuità del percorso locale NART → AWT; sola ricezione locale, nessun report del peer.',
    'roundtrip': 'Andata e ritorno RTP/RTCP; non assegnare upstream o downstream.',
    'probe': 'Sonda ICMP verso la destinazione osservata; non identifica automaticamente il peer RTP.',
    'combined': 'Indicatore dei due device scelti A+B; non una direzione né una latenza end-to-end.',
    'receiver_report': 'Incoming: ricezione locale; outgoing: ricezione dichiarata dal peer. Il verso del report non è il verso del media misurato.',
    'model': 'Stima sulla perdita del ricevitore locale (incoming) o del peer (outgoing), non qualità misurata.',
    'verified_loss': 'Perdita su intervallo verificato del ricevitore locale (incoming) o del peer (outgoing).',
    'local_packets': 'Pacchetti ricevuti localmente; non confondere con quelli soltanto dichiarati come inviati dal peer.',
    'peer_sent': 'Pacchetti inviati dal peer secondo il Sender Report; non prova che siano arrivati localmente.',
    'peer_lost': 'Pacchetti persi nella ricezione del peer secondo il Receiver Report; non perdita della ricezione locale.',
    'rtp_receive': 'Ricezione RTP locale NART/flow; preservare device e flusso senza dedurre una causa di rete.',
    'device': 'Misura locale del device o della relazione VID/VOD. NART: ricezione; input verso NAWT: trasmissione. Device generico, solo microfono/speaker o contesto misto: non assegnare automaticamente downstream.',
    'unconfirmed': 'Semantica specifica non confermata: il nome e la direzione del JSON non bastano per assegnare upstream/downstream.',
}


def metric_orientation(name):
    if name == 'derived.perceptual_quality': rule = 'awt_quality'
    elif name == 'rtcp.rtt': rule = 'roundtrip'
    elif name == 'network.ping': rule = 'probe'
    elif name in ('derived.buffer_sum', 'derived.dejitter_sum'): rule = 'combined'
    elif name in ('rtcp.jitter', 'rtcp.loss'): rule = 'receiver_report'
    elif name == 'derived.mos_reference': rule = 'model'
    elif name == 'telemetry.network_loss': rule = 'verified_loss'
    elif name in ('rtcp.packets_received', 'rtcp.packets_received_interval'): rule = 'local_packets'
    elif name in ('rtcp.packets_sent_total', 'rtcp.packets_sent_interval'): rule = 'peer_sent'
    elif name in ('rtcp.packets_lost_total', 'rtcp.packets_lost_interval'): rule = 'peer_lost'
    elif name in ('vd.missing_packets', 'vd.max_arrival_delay', 'incident.media_missing'): rule = 'rtp_receive'
    elif name.startswith('vd.') or name in ('derived.silence_delta', 'derived.silence_played_delta', 'incident.buffer_underrun'): rule = 'device'
    else: rule = 'unconfirmed'
    return dict(rule=rule, description=ORIENTATIONS[rule])


def metric_semantics(name):
    key=name.removeprefix('vd.')
    if 'scheduling' in key or key.startswith('cycles_') or key=='heartbeat_window':
        domain='scheduling'
    elif name.startswith('rtcp.') or key.startswith(('packets_','streak_')) or key in ('missing_packets','max_arrival_delay') or name=='telemetry.network_loss' or name=='incident.media_missing':
        domain='rtp_transport'
    elif name.startswith('mos.') or name in ('derived.mos_reference','derived.perceptual_quality'):
        domain='quality_model'
    elif name=='network.ping':
        domain='network_probe'
    elif any(x in name for x in ('buffer','silence','underrun','dejitter','samples_skipped')):
        domain='buffer_media'
    elif name.startswith('vd.'):
        domain='processing'
    else:
        domain='unspecified'
    return dict(domain=domain,domain_label=DOMAINS[domain],
        scope='Conservare prospettiva, observer, device, output_device, input_device, lifecycle, flow e SSRC ove disponibili. Il campo può riguardare un thread, un device o una relazione VID/VOD: consultare origine e contesto.',
        interpretation='Ambito della misura, non diagnosi causale. Scheduling, trasporto e conseguenze sul media vanno confrontati mantenendo le evidenze e la copertura.')

def markdown():
    text='## Media plane VDK: device e interpretazione\n\n'+MEDIA_PLANE['basis']+'\n\n'
    text+='| Nome | Classe padre | Denominazione | Ruolo |\n|---|---|---|---|\n'
    for d in MEDIA_PLANE['devices']:
        text+=f"| {d['name']} | {d['parent'] or '—'} | {d['expanded']} | {d['role']} |\n"
    text+='\n'+''.join('- '+r+'\n' for r in MEDIA_PLANE['rules'])
    text+='\n### Contesto delle osservazioni\n\n'+''.join(f'- `{k}`: {v}\n' for k,v in MEDIA_PLANE['context'].items())
    return text+'\n'
