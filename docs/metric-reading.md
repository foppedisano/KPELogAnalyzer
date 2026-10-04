# Capire le metriche

[Indice](README.md) · [Catalogo completo](metrics.md) · [Grafici](call-chart.md)

## Tre domande diverse

1. **Cosa è arrivato dalla rete?** Perdita, jitter, RTT e conteggi RTP/RTCP.
2. **Cosa ha fatto il ricevitore?** Buffer, target dejitter e silenzio skippato.
3. **C'è stata mancanza di media/audio?** Missing packets, media missing e underrun
   descrivono fenomeni diversi, con precisioni temporali diverse.

Un solo indicatore non risponde a tutte e tre. In particolare il MOS a profilo
fisso rende confrontabile la componente di perdita; non è un voto completo alla rete.

## Direzioni: chi sta misurando?

Downstream significa **peer/GW → app**, upstream **app → peer/GW**.

| Log disponibili | Downstream dell'app | Upstream dell'app |
|---|---|---|
| Solo app | Ricezione locale | Ricezione dichiarata dal peer nei report RTCP |
| App e GW della stessa tratta, selezionato esplicitamente | Ricezione app | Riutilizzo della ricezione locale GW |
| Solo GW, ruolo locale GW nel pannello MOS | Report sul peer app | Ricezione locale GW |

Non invertire ogni campo che si chiama incoming/outgoing senza leggerne il
significato. I nomi tecnici interni conservano la prospettiva del produttore;
le etichette della UI indicano il contesto. Il ruolo xcoder non identifica da
solo la tratta verso l'app. Una sorgente non classificata è un'app **presunta**.

## Quale metrica scegliere

| Metrica | Come leggerla | Cosa non dedurre |
|---|---|---|
| RTT RTCP, ms | Tempo di andata e ritorno verso la sorgente RTP/RTCP. Confronta picchi e andamento. | Non dividerlo automaticamente per due per ottenere il ritardo audio. |
| Jitter RTCP, ms | Variabilità degli arrivi riportata dal ricevitore locale o remoto. | Non è l'audio in coda né il massimo ritardo di un singolo pacchetto. |
| Perdita RTCP, % | Perdita dichiarata nel report. Ogni direzione resta distinta. | La media semplice dei report non è la perdita totale pesata sul numero di pacchetti. |
| Pacchetti ricevuti, packets | Contatore cumulativo: osserva crescita e reset. | Non sommare i campioni consecutivi. |
| Missing packets NART, packets | Conteggio esplicito nel singolo evento di salto della sequenza. Sono punti isolati. | Non è una percentuale e non prova quanti pacchetti siano definitivamente persi. |
| Massimo ritardo NART, ms | Massimo dichiarato dal motore; il WARNING è un aggiornamento. | Non è una serie periodica del jitter. |
| Audio nel buffer NART, ms | Durata dell'audio effettivamente in coda al campione. | Non comprende tutta la latenza della chiamata. |
| Limite dinamico dejitter, ms | Limite corrente del buffer indicato dal motore. | Non è l'occupazione effettiva. |
| Silenzio skippato, ms | Contatore cumulativo del silenzio saltato dal ricevitore. | Non equivale automaticamente a voce persa. |
| Incremento silenzio skippato, ms | Differenza fra due campioni compatibili; collocata al secondo campione. | Non è un tasso al secondo. Reset e gap oltre 30 s non producono delta. |
| Underrun, ms | Durata di un episodio in cui l'osservatore segnala mancanza di audio dal buffer. | Uscita audio e registrazione possono descrivere lo stesso fenomeno: non sommarle. |
| Media missing, ms | Assenza RTP segnalata; spesso la durata è un limite inferiore. | Una ripresa senza inizio noto non consente una durata esatta. |
| Ping ICMP, ms | Risposta dell'endpoint della sonda ICMP. | L'endpoint può essere diverso dal peer RTP. |
| Statistiche KPE raw | Valori originali last/avg/min/max con semantica o unità non confermata. | Non convertirli in ms o % per somiglianza del nome. |
| Perdita telemetria, % | Perdita su una finestra RTP verificata o su delta RTCP compatibili. | Contatori generici attesi/ricevuti non bastano senza una coorte comune. |

Il [catalogo](metrics.md) specifica messaggi di origine, formule e vincoli per
ogni nome tecnico. Le metriche nuove non documentate sono indicate come tali.

## MOS: cosa rende confrontabile

Il modello `loss-reference-1` mantiene fissi codec, packetizzazione e PLC di
riferimento. Varia la perdita osservata, non il codec reale della chiamata.
Questo evita di cambiare il punteggio solo perché una chiamata usa un codec
diverso. **Non elimina l'influenza del ricevitore dalla misura originale** e non
ricostruisce la perdita pura di rete quando il log non consente di distinguerla.

Il profilo è G.711 10 ms, PLC Appendix I; la formula completa è nella
[guida MOS](mos.md). Con perdita zero restituisce circa **4,41**, non 5.
Non penalizza RTT, jitter, burst o silenzio skippato: per questo un MOS 4,41
può coesistere con problemi audio. I colori rosso <3, arancio 3–4, verde ≥4
sono soglie esplorative, non una certificazione della qualità.

### Perché non sommare missing packets e silenzio skippato alla perdita

Possono descrivere effetti sovrapposti: un pacchetto segnalato mancante può
arrivare tardi, essere recuperato o influenzare il buffer. Aggiungere una penalità
per ogni indicatore rischia di contare più volte lo stesso evento. La piattaforma
li affianca nel tempo al MOS e conserva gli input separati. Una futura formula
più ricca richiederà semantiche del motore e validazione sperimentale.

## Campione, contatore o intervallo?

- Un **campione** descrive l'istante osservato; una linea è un aiuto visivo.
- Un **contatore** accumula dall'inizio di un'epoca e può ripartire.
- Un **evento** segnala qualcosa in un istante: non va reso continuo.
- Un **intervallo** caratterizza una finestra, non ogni singolo pacchetto.
- Un **episodio** ha inizio/fine osservati, ricavati o ignoti, dichiarati nella tabella.
- `last/avg/min/max` sono statistiche del motore con finestra non sempre nota;
  la media aritmetica dell'analizzatore è un'altra operazione.

Esempio: silenzio cumulativo da 1.000 a 1.200 ms in 10 secondi significa delta
200 ms, cioè 2% della durata della finestra nel pannello MOS. Non significa
automaticamente che sia andato perso il 2% della voce o dei pacchetti.

## Leggere insieme i grafici

Apri una chiamata e scegli **Rete**, poi aggiungi MOS downstream, silenzio skippato
e missing packets. RTT e jitter condividono il pannello ms; MOS, percentuali e
conteggi hanno altre scale, con asse temporale comune. I conteggi usano tacche
intere; le percentuali possono avere decimali. La legenda nasconde singole serie
senza rimuovere la metrica.

Verifica prima la stessa sorgente, lo stesso flow/SSRC e gli orologi. Un aumento
contemporaneo di jitter, buffer e silenzio skippato è un fatto da approfondire;
non prova da solo un guasto radio, congestione o un problema del gateway.
Anche carico del dispositivo e scheduling possono influire sulla ricezione.

## Assenze e anomalie

**Nessun dato non significa zero.** La raccolta può essere incompleta, una metrica
può non esistere in quella versione o non avere attribuzione univoca. Nel registro
più flussi possono impedire un MOS unico. Guarda copertura ed evidenze prima di
confrontare medie: dieci secondi buoni in una chiamata lunga non ne descrivono il resto.

Valori finiti non validi restano archiviati e sono normalmente esclusi; nel
grafico della chiamata puoi abilitare **Mostra anomali** per le metriche che li
espongono. I derivati non vengono inventati per input invalidi. I buchi temporali
restano buchi nel grafico. Nella mappa PQ si può stimare la posizione di secondi
con qualità AWT disponibile, ma soltanto fra estremi della stessa chiamata/sorgente
entro 120 s. Le celle stimate sono esplicite e non sostituiscono dati diretti.
Un 100 PQ significa nessun underrun registrato, assumendo completo il log,
non qualità percepita verificata. [Metodo PQ e zone](perceptual-quality.md).

## Media plane e terminologia

La [guida al media plane VDK](media-plane.md) distingue VID/VOD, le specializzazioni audio e le connessioni molti-a-molti. Ogni VD opera nel proprio thread: separare scheduling locale, statistiche di ricezione RTP e conseguenze sul media. Il catalogo delle metriche e la guida in linea espongono lo stesso ambito semantico.
