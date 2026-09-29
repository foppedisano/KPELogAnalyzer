# Media plane VDK e semantica delle osservazioni

[Indice](README.md) · [Metriche](metrics.md) · [API/MCP](analytics.md)

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

## Come leggere una misura

1. Identificare la prospettiva e il device concreto, senza dedurli dal prefisso `vd.`.
2. Leggere ambito, campo originale, unità e tipo (campione, cumulativo, intervallo o stato).
3. Distinguere misure del thread, ricezione RTP e disponibilità del media.
4. Per un contatore per VOD mantenere la coppia input/output; il totale di uscita di un mixer non è una misura separata per ciascun input.
5. Confrontare solo intervalli coperti, conservando eventi e file:riga. Non sommare cumulativi, osservatori o input come durata della chiamata.

La tassonomia descrive il funzionamento VDK; non ricostruisce automaticamente collegamenti mancanti nei log. La conferma della gerarchia non conferma nuove unità, finestre temporali o il significato interno di GOOD/BAD.
