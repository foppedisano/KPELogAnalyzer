# Come funziona la piattaforma

[Indice](README.md) · [Capire le metriche](metric-reading.md)

## Dal file alla conclusione

Il percorso è: **ZIP → file → eventi → chiamate e prospettive → metriche →
grafici, MOS e mappa**. Ogni passaggio conserva i riferimenti che permettono di
tornare al messaggio di origine. Un grafico aiuta a trovare un problema; il log
serve a verificare che cosa sia stato effettivamente osservato.

| Termine | Significato pratico |
|---|---|
| Importazione o sorgente | Uno ZIP, cioè una fotografia dei log esportati. Non è l'identità permanente di un dispositivo. |
| File | Un membro dello ZIP. File diversi possono descrivere parti diverse della stessa chiamata. |
| Evento | Un messaggio del log, anche su più righe, con timestamp e testo normalizzato. |
| Chiamata | Una sessione identificata dall'esatto SIP Call-ID, oppure una sessione locale senza tale identità. Non coincide necessariamente con l'intera conversazione tra persone. |
| Prospettiva | La chiamata vista in una determinata importazione. Mantiene tempi, linea e sorgente propri. |
| Conversazione | Un insieme di tratte collegate da evidenze esplicite o dall'analista. Non fonde i Call-ID. |
| Metrica | Un valore con unità, tempo, direzione, statistica e provenienza. Flow, SSRC e device distinguono serie diverse. |

### Esempio: due app e due gateway

Alice, Bob e i rispettivi gateway possono produrre quattro ZIP. Ognuno può
contenere una chiamata, ma il totale globale dipende dai Call-ID: se coincidono
si hanno più prospettive della stessa chiamata; se un PBX cambia Call-ID si hanno
tratte distinte. Quattro ZIP non implicano né quattro conversazioni né una sola
chiamata globale. La vista Conversazioni rende consultabili i collegamenti.

## Importazione e deduplicazione

L'importazione è atomica per ZIP: riesce tutta oppure viene annullata. Nel
caricamento multiplo gli ZIP già riusciti rimangono importati anche se uno dei
successivi fallisce. Non vengono estratti file in cartelle arbitrarie.

| Livello | Regola |
|---|---|
| Stesso ZIP byte per byte | SHA-256 già noto: nessuna nuova importazione. |
| Stesso Call-ID da produttori diversi | Stessa chiamata globale, prospettive separate. |
| Rotazioni di log nello stesso ZIP | Le metriche duplicate secondo le chiavi dell'estrattore non moltiplicano le osservazioni; gli eventi restano consultabili. |
| Export tradizionali dello stesso produttore riconosciuto | Le chiamate già presenti vengono ignorate; identità incerta: import conservato. [Criteri](source-dedup.md). |
| Telemetria strutturata | Chiave stabile source_id/event_id tra ZIP; le copie aggiungono evidenza. Contenuti discordanti con lo stesso ID invalidano le derivazioni coinvolte. |
| Mappa | Deduplicazione delle evidenze riconosciute e unione del tempo sovrapposto, secondo il metodo geografico. Non è una deduplicazione generale di qualunque formato. |

In **Sorgenti e copertura**:

- **Chiamate distinte**: quante chiamate sono conservate come prospettive da quello ZIP.
- **Chiamate ignorate**: già presenti dalla stessa sorgente riconosciuta.
- **Copie storiche**: prospettive ripetute già nel DB, conservate ma escluse dal grafico normale.
- **Nuove nel DB**: chiamate la cui prima importazione è quella sorgente.
- **Già presenti**: chiamate osservate anche in un'importazione precedente.

Sono conteggi ricostruiti dalle prospettive attuali, incluse finestre manuali.
Esempio: il primo export contiene 20 chiamate; quello del giorno dopo ne contiene
25, di cui 20 già importate dallo stesso produttore riconosciuto. La seconda
importazione mostra 5 distinte, 5 nuove e 20 ignorate. Se invece la sorgente è
diversa o non identificabile, conserva 25 prospettive: 5 nuove e 20 già presenti
globalmente. Non sommare i conteggi degli ZIP per stimare le chiamate globali.

## Come si attribuiscono i campioni

Il Call-ID è il collegamento più forte. Per i messaggi che indicano solo una
linea, il parser ricostruisce la finestra temporale di quella linea nella stessa
sorgente. Linea e tempo devono individuare una sola chiamata. La linea `0` può
essere riutilizzata molte volte: non è un'identità globale.

Se mancano prove o ci sono finestre ambigue, la metrica resta **non attribuita**.
La puoi cercare in Esplora log o SQL. Un record senza chiamata non è perso.
Per file sciolti e log incompleti esistono finestre manuali esplicite e annotate.
Un file VD può contenere più device: la sua attribuzione generale non sostituisce
quella del singolo campo numerico estratto.

## Un percorso di analisi

1. Controlla **Sorgenti e copertura**: piattaforma, periodo, avvisi, nuove chiamate.
2. Nel **Registro chiamate**, ordina per MOS medio o minimo. Il valore grande è
   la media pesata sulla durata; un trattino significa assenza o ambiguità.
3. Apri la chiamata: il primo pannello mostra il MOS downstream. Usa
   **Aggiungi metriche** oppure **Rete** per confrontare RTT, jitter e perdita.
4. Cerca lo stesso intervallo in silenzio skippato, missing packets e incidenti.
   Leggi timestamp effettivi ed eventi, non solo massimi o colori.
5. Se hai i log del ricevitore opposto, selezionalo in **MOS e ricezione**;
   per buffer e analisi salvabili usa **Diagnostica A/B**.
6. Passa alla **Mappa qualità** solo se esistono posizioni associabili. Controlla
   tempo osservato, giorni e accuratezza prima di confrontare le zone.

`completed` descrive il ciclo della chiamata, non la bontà dell'audio. Un MOS alto
con ritardo elevato o buffer underrun richiede comunque attenzione.

## Tempo, intervalli e medie

I log tradizionali mantengono l'orario scritto, senza fuso inventato. La correzione
della sorgente sposta solo l'allineamento grafico; nella diagnostica l'offset
specifico dell'analisi non modifica quello globale. Due campioni affiancati dal
tooltip possono differire fino alla tolleranza indicata: leggere l'ora effettiva.

Per i report tradizionali il MOS resta valido dal report fino al successivo,
alla fine chiamata o a 30 secondi, scegliendo il primo limite. Per la telemetria
strutturata verificata descrive invece una finestra esplicita già osservata.
I periodi scoperti non diventano MOS zero.

Esempio di media temporale: MOS 4 per 9 secondi e MOS 2 per 1 secondo danno
`(4×9 + 2×1)/10 = 3,8`. La media dei due campioni sarebbe 3: risponde a una
domanda diversa. Il registro usa 3,8; le statistiche dei campioni nel grafico
sono etichettate come aritmetiche. Il MOS non si ricava facendo la media di MOS
appartenenti a flussi o ricevitori diversi senza una regola esplicita.

## Mappa e futuro predittivo

La mappa interseca gli intervalli di posizione e MOS con il periodo scelto,
poi aggrega nelle celle. Cambiare cella o periodo non cancella le osservazioni.
Una zona vuota significa che non c'è copertura utilizzabile, anche se proprio
lì la connessione era assente. La risposta aggregata non espone identità;
il database locale conserva la provenienza per verificare le elaborazioni.

La raccolta strutturata prepara posizione, velocità, rete, configurazioni e
azioni per algoritmi futuri. **Non esistono ancora previsione del percorso,
riconoscimento del treno, API di previsione o generazione di piani offline**.
Gli eventi dei piani sono archiviabili e verificabili; le app devono ancora
implementare i produttori e il controllo operativo nei rispettivi progetti.

## Conservazione e riproducibilità

Non c'è eliminazione automatica dei dati vecchi. Il testo normalizzato e le
evidenze restano nel DB; conserva anche lo ZIP se serve l'originale byte per byte.
Le analisi salvate conservano configurazioni e vengono ricalcolate: esporta JSON
per congelare un risultato, CSV per i campioni, **Esporta database** per un backup
consistente. Il DB e gli ZIP rimangono locali e non vanno pubblicati nel repository.
