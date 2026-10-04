"""Regenerate the human-readable metric catalog from the UI/API dictionary."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.catalog import CATALOG, PERIODIC_METADATA
from app.media_semantics import markdown
header='''# Catalogo delle metriche

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

## Schede

'''
audit = '''## Verifica delle unità, metrica per metrica

Inventario verificato sui campi riconosciuti da parser.py, enrichment.py e periodic.py,
sulle finestre di telemetria e sui calcoli derivati. L’unità dei campioni resta
la fonte per l’asse verticale; una voce di catalogo non converte dati raw.
Le sei statistiche KPE raw restano non confermate in assenza di evidenza del produttore.

`derived.silence_played_delta` è in **millisecondi (ms)**: il campo di partenza
contiene **msecs**, non usecs. Esempio: 100 → 125 ms produce un incremento di
25 ms tra i due campioni, non 25 µs, non 25 ms/s e non una percentuale.

| Metrica | Unità nel grafico / CSV | Campo originale o derivazione |
|---|---|---|
'''
audit += ''.join(f"| `{e['name']}` | {e['unit_label']} | {e['source'].replace('|', '/')} |\n" for e in CATALOG)
contexts = '''
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
'''
contexts += ''.join(f"| `{e['name']}` | {e['kind']} | {e['orientation']['description']} |\n" for e in CATALOG)
parts=[header.replace("## Schede", markdown()+audit+contexts+"\n## Schede")]
for e in CATALOG:
 parts.append(f"### {e['title']} — `{e['name']}`\n\n**Unità:** {e['unit_label']}. **Tipo:** {e['kind']}.\n\n**Lettura dell’unità:** {e['unit_note']}\n\n{e['meaning'].strip()}\n\n**Direzione e contesto:** {e['orientation']['description']}\n\n**Ambito:** {e['semantics']['domain_label']}. {e['semantics']['scope']}\n\n**Origine e calcolo:** {e['source']}.\n\n**Limiti:** {e['limits']}\n\n")
parts.append('## Stati e metadati periodici\n\n'+''.join(f"- `{m['name']}` ({m['type']}): {m['meaning']}\n" for m in PERIODIC_METADATA)+'\n')
parts.append('''## Lettura del grafico e dei momenti critici

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
''')
Path('docs/metrics.md').write_text(''.join(parts),encoding='utf-8')
