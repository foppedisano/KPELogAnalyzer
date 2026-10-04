# Documentazione

La piattaforma legge log, conserva le evidenze e calcola indicatori verificabili.
Il MOS mostrato è un **indice basato sulla perdita a profilo fisso**: non riassume
da solo tutta la qualità della rete o dell'audio.

Checkpoint corrente: [4 ottobre 2026](checkpoint-2026-10-04.md).

## Percorso consigliato

1. [Installazione e aggiornamento](getting-started.md): Docker, URL locale, backup.
2. [Come funziona la piattaforma](platform-guide.md): importazioni, chiamate,
   prospettive, deduplicazione e flusso di analisi.
3. [Capire le metriche](metric-reading.md): cosa misura ogni famiglia e come
   interpretare insieme MOS, RTT, jitter, buffer ed eventi audio.
4. [Grafico della chiamata](call-chart.md): aggiungere metriche, scale e zoom.

## Guide operative

| Obiettivo | Guida |
|---|---|
| Interrogare i dati da un agent e salvare query generali | [Analisi libere e MCP](analytics.md) |
| Capire identità, scarti e copie storiche | [Deduplicazione per sorgente](source-dedup.md) |
| Confrontare due osservazioni e salvare l'analisi | [Diagnostica A/B](diagnostics.md) |
| Capire le due direzioni e usare il ricevitore GW | [Metodo MOS](mos.md) |
| Vedere qualità, copertura e variazioni nel tempo per zona | [Mappa qualità](geography.md) |
| Distinguere celle dirette/stimate, esplorare il percorso e recuperare posizioni iOS | [Perceptual Quality](perceptual-quality.md) |
| Confrontare contatori audio e transitori | [Transitori](transients.md) |
| Distinguere rete mobile, Wi-Fi, tethering e sequenze | [Movimento e rete](mobility.md) |
| Raccogliere le tratte di una conversazione | [Conversazioni e piattaforme](conversations.md) |
| Collegare esplicitamente app e transcoder | [App e xcoder](xcoder.md) |

## Riferimenti tecnici

- [Inventario dei campi periodici recenti](periodic-metrics-inventory.md) e
  [piano di implementazione / passaggio di chat](periodic-metrics-implementation.md).
- [Catalogo delle metriche](metrics.md): generato da `app/catalog.py`, condiviso con UI/API.
- [Architettura e dati](architecture.md): attribuzione, pipeline, tabelle e migrazioni.
- [API locale](api.md): parametri, risultati e limiti.
- [Telemetria app/GW, base v1](telemetry.md) e [revisione 1.1](telemetry-integration.md):
  contratto degli emitter, ID, orologi, finestre RTP e audit dei piani offline.
- [Limiti e lavoro futuro](open-issues.md): confine tra funzioni implementate e proposte.
- [Verifiche](validation.md): stato recente e cronologia dei collaudi.

Lo schema SQLite corrente è **12**; il contratto di telemetria consigliato per i
nuovi emitter è **kpe.telemetry/1.1**, con v1 ancora accettato. Sono numeri di
versione di oggetti diversi. Il parser comunica la propria versione in `/api/health`.

## Media plane e terminologia

La [guida al media plane VDK](media-plane.md) distingue VID/VOD, le specializzazioni audio e le connessioni molti-a-molti. Ogni VD opera nel proprio thread: separare scheduling locale, statistiche di ricezione RTP e conseguenze sul media. Il catalogo delle metriche e la guida in linea espongono lo stesso ambito semantico.

## Profili temporali delle zone

Per la metrica MOS, il clic su una cella apre storico giornaliero/settimanale/mensile/annuale, ricorrenze orarie, copertura ed evidenze. Gli stessi calcoli sono disponibili tramite `POST /api/analytics/geo-temporal` e `analytics_geo_temporal`; `POST /api/analytics/geo-cells` e `analytics_geo_cells` scoprono le celle. [Guida, denominatori e contratto completo](geo-temporal.md). Il catalogo MCP espone gli schemi in `geo_temporal`. Riconnettere il client MCP per rileggere i nuovi strumenti.

- [Tentativi utente e rete/servizi](connectivity.md): blocchi prima del SIP, ragioni osservate, timeline per secondo e migrazione 12.
