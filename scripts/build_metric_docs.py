"""Regenerate the human-readable metric catalog from the UI/API dictionary."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.catalog import CATALOG
header='''# Catalogo delle metriche

Questa guida è generata da `app/catalog.py`, la stessa fonte usata da **Guida alle metriche** nell’interfaccia e da `GET /api/catalog`. Rigenerazione: `python scripts/build_metric_docs.py`.

Per una prima lettura: [capire le metriche](metric-reading.md),
[logica della piattaforma](platform-guide.md) e [grafico multimetriche](call-chart.md).
Le schede sotto sono il riferimento tecnico; il metodo MOS completo è in [mos.md](mos.md).

## Regole comuni

- **Prospettiva**: osservazione di una chiamata in una sorgente importata. Non identifica permanentemente un telefono: due export dello stesso dispositivo possono duplicarsi.
- **Downstream / upstream**: rispetto all’app. Incoming RTCP e VD descrivono la ricezione locale (downstream); jitter/loss dei Receiver Report outgoing descrivono la ricezione del peer/GW (upstream). RTT e ping sono bidirezionali. Per xcoder o tratta ignota si mantengono ricezione locale/del peer, senza inversione automatica. Sorgenti senza ruolo dichiarato: app presunta, non identità verificata.
- **Flow / SSRC / device**: restano distinti; non aggregare flussi o destinatari diversi. Il device selezionato nella diagnostica filtra le metriche VD; RTT mostra separatamente tutti i flow/SSRC attribuiti alla prospettiva.
- **sample / gauge**: osservazione al timestamp. **event**: aggiornamento esplicito, senza interpolazione. **counter**: contatore cumulativo soggetto a reset. **interval**: valore riferito a un intervallo (delta oppure finestra esplicita). **step**: valore mantenuto fino a una scadenza dichiarata; il MOS legacy usa questa rappresentazione.
- **last / avg / min / max**: statistiche riportate da KPE, non calcolate dall’analizzatore. Non è nota automaticamente la loro finestra temporale. La media nelle tabelle RTCP è aritmetica sui campioni, non pesata per durata o pacchetti.
- **Unità**: µs ÷ 1000 = ms; ms ÷ 1000 = s. Il DB conserva le metriche VD in ms, compreso il contatore di silenzio; Diagnostica A/B consente di scegliere ms oppure secondi; il grafico della chiamata mantiene ms. `raw` significa unità non confermata.
- **Validità**: valori finiti negativi e percentuali fuori 0–100 restano con `valid=0`. Valori mancanti, non numerici, NaN e infinito non diventano zero. La diagnostica esclude i campioni invalidi.
- **Provenienza**: `metrics.event_id` porta a `events` e al file. `source_line` è la riga precisa del campo per il nuovo estrattore; se nulla usare `events.line_no`, inizio del record. `raw_value/raw_unit` preservano la conversione del nuovo estrattore; possono essere null per metriche precedenti.
- **Orologio**: timestamp originali invariati, senza fuso dedotto. L’offset della sorgente, in secondi, si somma solo per allineamento nei grafici e derivazioni diagnostiche. Un offset positivo sposta la sorgente in avanti.
- **Deduplicazione**: osservazioni nuove identiche per sorgente, timestamp, metrica, device, linea, flow, SSRC, valore e tipo sono contate una sola volta. Per i log tradizionali si ignorano le chiamate già presenti quando il produttore è riconosciuto con prove locali concordanti; le copie storiche restano consultabili. Vedi [identità della sorgente](source-dedup.md). La telemetria strutturata deduplica source_id/event_id tra ZIP; la mappa ha regole proprie di unione delle evidenze sovrapposte. Vedi [logica della piattaforma](platform-guide.md).

## Schede

'''
parts=[header]
for e in CATALOG:
 parts.append(f"### {e['title']} — `{e['name']}`\n\n**Unità:** {e['unit']}. **Tipo:** {e['kind']}.\n\n{e['meaning']}\n\n**Origine e calcolo:** {e['source']}.\n\n**Limiti:** {e['limits']}\n\n")
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

I nomi interni VD/KPE sono interpretati empiricamente dai log disponibili, senza una specifica proprietaria completa. Una metrica KPE non ancora descritta riceve nella UI una scheda esplicitamente non confermata; non si inventano unità o diagnosi.
''')
Path('docs/metrics.md').write_text(''.join(parts),encoding='utf-8')
