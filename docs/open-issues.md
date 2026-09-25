# Open issues

## XCODER-001 — Supporto sviluppato senza log reali (aperta)

Il supporto xcoder è stato sviluppato **alla cieca rispetto ai log del transcoder**:
su indicazione del proprietario del progetto assumiamo che timestamp, nomi dei file
e messaggi VD/RTP/KPE siano uguali a quelli delle app. I test usano esclusivamente
fixture sintetiche; non costituiscono validazione del formato prodotto da Kalliope GW.

Quando sarà disponibile un log set reale, verificare:

- nomi e rotazioni dei file, timestamp e unità;
- lifecycle delle linee, Call-ID e collegamento tra tratta app e tratta gateway;
- server condiviso tra partecipanti e chiamate simultanee;
- device, flow e SSRC, significato di incoming/outgoing su ogni tratta;
- riconoscimento di dejittering, underrun e media missing;
- eventuali statistiche specifiche di transcoding Opus/G.711 e ridondanza.

Conservare il campione privato fuori da Git, aggiungere fixture sintetiche per le
differenze e aggiornare parser/documentazione. Nessuna associazione automatica
app–xcoder o conversione di unità deve essere introdotta senza evidenza.

## XCODER-002 — Leg multiple nella stessa prospettiva (aperta)

Il modello corrente ha una prospettiva per coppia import/Call-ID. Se un xcoder
riporta più tratte o linee con lo stesso Call-ID nello stesso log set, occorre
verificare un'identità più granulare (dialog/linea/tratta). Non duplicare o
attribuire arbitrariamente le osservazioni ambigue. Due processi/nodi diversi
devono essere importati come log set separati.

## XCODER-003 — Configurazioni multicomponente (aperta)

Sessione, partecipante, ruolo, nodo e nota persistono nel database. Il confronto
multicomponente esporta dati, evidenze e configurazione JSON; selezione dei device,
periodo, zoom e stili non hanno ancora il salvataggio/riapertura delle analisi A/B.
