# Grafico multimetriche della chiamata

Il dettaglio si apre sul MOS downstream. **Aggiungi metriche** apre una ricerca
con caselle per selezionare più parametri. La × nelle etichette rimuove un
parametro; il clic sulla legenda nasconde solo quella serie. Le selezioni rapide
Qualità, Rete e Ricezione sostituiscono la selezione corrente.

Metriche con la stessa unità condividono un pannello: RTT e jitter sono entrambi
in millisecondi. Unità diverse hanno pannelli con tempo, zoom e cursore comuni.
Le metriche raw hanno pannelli separati perché la loro unità non è documentata.
Sorgenti, flussi, device e SSRC mantengono serie distinte.

Ogni asse verticale riporta l’unità estesa: **ms · millisecondi**, percentuale,
pacchetti, byte, conteggio, campioni audio, campioni audio/s, chunk oppure MOS
(indice senza unità). Se non è confermata compare **raw · unità non confermata**.
L’unità è visibile anche nella selezione, nelle etichette e nella legenda.
Campioni dello stesso parametro con unità diverse restano in serie e pannelli
separati, anche nelle statistiche. La guida riporta il controllo di ogni metrica
e il campo originale che ne dichiara l’unità.

**Incremento silenzio riprodotto** (`derived.silence_played_delta`) è in **ms**:
il contatore di origine dichiara `msecs`. La differenza 100 → 125 ms produce
25 ms nell’intervallo osservato; non è un tasso al secondo né una percentuale.

La rotella normale scorre la pagina, anche sopra il grafico. **Ctrl + rotella**
ingrandisce intorno al puntatore. I pulsanti **− / +** cambiano lo zoom al centro
della finestra; **Reset zoom** torna alla copertura completa.
Tutti i pannelli mantengono lo stesso intervallo temporale. L'allineamento assoluto usa le correzioni delle sorgenti,
quello relativo usa l'inizio della prospettiva, come nel confronto preesistente.
Le linee si interrompono oltre 30 secondi senza dati. Gli eventi sono punti
isolati; MOS e altri intervalli espliciti terminano alla loro scadenza.
La lettura mostra il campione più vicino entro ±2,5 secondi oppure l'intervallo
valido, con timestamp effettivo ed evidenze. Non interpola valori mancanti.

Le tacche per `packets` sono intere, anche per zero o un solo pacchetto.
Le percentuali e le misure continue mantengono i decimali necessari. Il MOS
normale ha scala 1–5. Anche Diagnostica A/B usa tacche intere per i pacchetti.

Ogni metrica mantiene la propria statistica last/avg/min/max e il proprio CSV.
Le statistiche espandibili sono per serie e usano l'intera selezione, non lo
zoom. La media dei campioni è aritmetica; la media MOS del registro chiamate
rimane pesata sulla durata. La selezione è locale alla vista e non viene salvata.

Verifica opzionale delle scale: `node --test tests/test_chart_scale.js`.

## Copie dello stesso export

Il grafico esclude per default le prospettive storiche riconosciute come copie
della stessa sorgente/Call-ID. **Mostra copie storiche della stessa sorgente**
le include anche nei CSV. Le serie di produttori e SSRC diversi restano separate.
[Regole ed evidenze di identificazione](source-dedup.md).
