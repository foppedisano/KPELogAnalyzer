# Limiti noti e lavoro futuro

[Indice](README.md) · [Verifiche](validation.md)

Questa pagina distingue le funzioni disponibili dalle evoluzioni previste.
La raccolta dei dati necessari non implica che esista già l'algoritmo che li usa.

## MOS-001 — Indice di perdita, non misura percettiva

Il MOS usa un profilo fisso. Ritardo, burst, jitter e scarti al playout non entrano
nel punteggio. Missing packets e silenzio skippato restano contesto separato per
evitare doppi conteggi. Servono semantiche vendor e validazione sperimentale per
un modello più ricco. La media del registro sceglie l'ultima prospettiva importata;
più flussi/SSRC possono impedirne il riepilogo. Non è un aggregato di tutti i ricevitori.

## GEO-001 — Copertura e orologi

Il supporto geografico legacy usa pattern osservati, non una garanzia che ogni
export iOS/Android contenga posizioni. Fix sporadici o cached non ricostruiscono
un viaggio. Una galleria senza osservazioni può apparire vuota. Log legacy senza
fuso e telemetria UTC non vengono automaticamente riallineati. Le finestre manuali
modificate dopo l'import non ricalcolano automaticamente il prodotto geografico legacy.
I punti grigi di sola posizione non includono ancora tutte le posizioni strutturate.

## TEL-001 — Produttori e sovrapposizioni

Contratto, validatore, deduplicazione strutturata e integrazione selettiva sono
implementati. Gli emitter app/GW sono esterni al repository e vanno sviluppati
e verificati con traffico noto. I campi opzionali assenti restano ignoti.
Log testuali e telemetria strutturata non hanno deduplicazione reciproca generale.
L'hash del documento di un piano è archiviato ma non ricalcolato byte per byte.

## PRED-001 — Previsioni e piani offline

Non sono implementati map matching, scelta probabilistica dei rami stradali,
identificazione del treno, previsioni a breve termine, API di previsione,
generazione dei piani o controllo dell'audio nelle app. Il DB conserva velocità,
direzione e contesto quando forniti e permette l'audit degli eventi dei piani.

L'evoluzione prevista richiede replay causale senza usare dati futuri, separazione
dei viaggi fra training e test e confronto con una previsione semplice di base.
La velocità deve influire sia sull'orizzonte spaziale sia sul confronto della
qualità storica a condizioni simili. Bivi e svolte richiedono un grafo percorribile
e probabilità sui percorsi; una traiettoria ricorrente non identifica il mezzo fisico.
Un piano offline dovrà avere scadenza, condizioni di percorso, limiti applicabili
e fallback locale. Un timeout API non deve rendere permanente un comando obsoleto.

## SCALE-001 — Archivio locale e limiti

SQLite e le query sono limitati esplicitamente: questa versione non è un servizio
distribuito per milioni di dispositivi. Non c'è retention automatica né una politica
di aggregati storici per archivi illimitati. I limiti delle query non cancellano
gli input. Serviranno indici/aggregati, misure di carico e un protocollo operativo
prima di esporre un servizio di previsione ad alta frequenza.

## UI-001 — Configurazioni dei grafici

La selezione multimetriche del dettaglio/Confronta dura per la vista corrente.
Non viene salvata fra navigazioni. Diagnostica A/B offre configurazioni persistenti.
Le tre viste (chiamata, A/B, multicomponente) hanno controlli e criteri di disposizione
diversi; non tutte le personalizzazioni sono condivise.

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
