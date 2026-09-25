# Android, iOS e conversazioni

Importa gli ZIP con lo stesso pulsante **Importa log**, senza scegliere un parser
Android o iOS. Le metriche sono riconosciute dal formato e dalle unità scritte nei
log, non dal sistema operativo. Le rotazioni e i formati VD precedenti e nuovi
possono convivere nello stesso archivio.

## Metadati e copertura Android

I file `kpe-android*` identificano gli export Android osservati; `ios_hwwrapper.log`
identifica quelli iOS. Quando manca una prova la piattaforma resta sconosciuta.
Da `info.log` vengono mostrati modello, versione OS e versione app, con riferimenti
al file/evento/riga. La versione di questo file è un **metadato dell’esportazione**:
non viene retrodatata alle chiamate precedenti né sostituisce le versioni associate
agli eventi KPE. I metadati sono visibili in Sorgenti, nel dettaglio chiamata e
nelle schede delle conversazioni.

Negli export Android verificati non è presente `CallInfo.log`: le statistiche KPE
possono essere riepiloghi finali, mentre VD e RTCP hanno propri campioni temporali.
Il sistema non inventa campioni periodici. L'assenza di una metrica non significa
zero. I log SIP possono coprire un periodo più lungo del file KPE: in tal caso una
chiamata resta visibile ma potrebbe non avere una linea ricostruita o metriche
attribuite. I campioni ambigui restano nel DB, senza attribuzioni per supposizione.
I file wrapper/app non riconosciuti come metriche restano consultabili come eventi
grezzi. Il supporto è verificato sui formati osservati e su fixture sintetiche,
non su ogni versione Android o personalizzazione del vendor.

## Trovare una conversazione

Apri **Conversazioni**. Per impostazione iniziale vedi i gruppi con più Call-ID e
i collegamenti espliciti. Puoi cercare data, sorgente, partecipante o Call-ID.
Attiva **Includi lo stesso Call-ID in più esportazioni** per vedere anche le
osservazioni ripetute della stessa chiamata.

Le prove sono distinte:

- **Identificatore condiviso:** stesso `X-Call-UUID` valido negli header INVITE.
  Collega Call-ID differenti senza fonderli nel database. Identifica il tentativo
  di comunicazione; può comprendere chiamate non risposte o rami di un fork.
- **Stesso Call-ID:** una chiamata presente in più log set. Potrebbero essere
  esportazioni dello stesso dispositivo, non due partecipanti.
- **Collegamento manuale:** seleziona le chiamate nel registro, poi usa
  **Collega manualmente** e specifica la prova. Serve quando il gateway riscrive
  gli identificatori senza lasciare una correlazione riconoscibile.
- **Sessione app / xcoder:** associa le prospettive in **App e xcoder** usando la
  stessa sessione e indicando partecipante, componente e nodo. La sessione appare
  anche nell'elenco Conversazioni, con tutti i componenti disponibili.

Né orari simili né numeri telefonici uguali sono sufficienti per un collegamento
automatico. Identificatori discordanti o riutilizzati a più di 24 ore di distanza
mostrano **Da verificare**: sono candidati, non conversazioni confermate. Anche
un UUID coerente non prova che ogni dispositivo abbia scambiato audio.

## Esplorare e confrontare

**Esplora** mostra una scheda per osservazione: chiamata, sorgente, piattaforma,
ruolo annotato, orari, esito, numero di metriche e copertura. Espandi **Prove del
collegamento** per vedere UUID ed eventi con file/riga. Un CANCEL con
`Reason: SIP;cause=200;text="Call completed elsewhere"` viene mostrato come
**Risposta altrove**, mantenendo lo stato grezzo nel DB.

Il confronto preseleziona l'osservazione più ricca di metriche di ogni Call-ID.
Controlla le caselle per non sovrapporre esportazioni duplicate. Seleziona il
device VD per ciascuna osservazione e, facoltativamente, il periodo. Puoi
confrontare da 1 a 16 osservazioni: due app, le app con i rispettivi gateway, o
una conferenza più ampia. La presenza di tutti i componenti non è obbligatoria.

Il grafico usa l'asse temporale reale e le correzioni orologio salvate in Sorgenti.
Una correlazione SIP non sincronizza gli orologi. La legenda permette di mostrare
o nascondere serie, cambiare colori/simboli e filtrare la direzione delle misure.
Le lacune e gli episodi audio conservano le regole della diagnostica. L'esportazione
JSON include la chiave del gruppo, le prospettive scelte e l'analisi. Non vengono
sommati automaticamente buffer dell'app e del gateway.

Se disponi dei log xcoder, importa ciascun set separatamente. Un UUID condiviso
può collegarlo automaticamente; altrimenti usa una sessione esplicita con tutte
le osservazioni. Il parser xcoder resta da verificare su log reali: finora è stata
assunta la compatibilità VDK, come documentato nelle open issues del progetto.
