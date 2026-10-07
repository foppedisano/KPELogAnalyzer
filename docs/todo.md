# Attività e idee

[Indice](README.md) · [Limiti tecnici](open-issues.md) · [Checkpoint corrente](checkpoint-2026-10-07-performance.md)

Questo file raccoglie il lavoro da concordare con il proprietario. Una voce
proposta non autorizza lo sviluppo: prima di iniziare, concordare obiettivo e
priorità. I limiti tecnici restano in `open-issues.md`; i checkpoint descrivono
lo stato verificato da cui riprendere, senza sostituire questa lista.

## Attività concordate

Nessuna attività di sviluppo in attesa al 6 ottobre 2026. Switch Network e
integrazione MCP 1.4.0 sono completati; verifiche e stato nel checkpoint.

## Idee da valutare

Queste voci riassumono limiti già documentati, non una roadmap approvata.
Priorità e ordine di esecuzione sono da concordare.

| ID | Proposta | Priorità | Dipendenze / decisioni | Criterio di completamento proposto |
|---|---|---|---|---|
| TODO-001 | Paginazione o selezione temporale per PQ e percorso via MCP | Da concordare | Definire ordinamento, snapshot e trattamento dei confini temporali; [limiti MCP](open-issues.md#limiti-mcp-130) | Recuperare una chiamata oltre 4 MiB con richieste limitate, senza perdere o duplicare campioni ed evidenze |
| TODO-002 | Profili temporali geografici PQ | Da concordare | Concordare denominatori e separazione fra dati diretti e stimati; [metodo PQ](perceptual-quality.md) | Risultati verificabili su fixture sintetiche, senza mescolare stime e medie dirette né riutilizzare implicitamente il metodo MOS |
| TODO-003 | Conservare la configurazione multimetriche e multicomponente | Da concordare | Decidere quali controlli persistono e il formato revisionato; [UI-001 e XCODER-003](open-issues.md) | Riapertura con selezioni e impostazioni concordate, senza modificare identità o offset delle sorgenti |
| TODO-004 | Misurare e migliorare le prestazioni delle mappe su archivi estesi | Da concordare | Benchmark sintetico riproducibile e obiettivi misurabili; [SCALE-001 e GEO-002](open-issues.md) | Miglioramento misurato a parità di risultati, evidenze e limiti; eventuale cache con invalidazione verificata |
| TODO-005 | Validare il supporto xcoder sul formato reale | Da concordare | Disponibilità di un campione privato e semantiche attendibili; [XCODER-001 e XCODER-002](open-issues.md) | Copertura e ambiguità documentate, regressioni sintetiche per le differenze osservate; nessun log reale nel repository |
| TODO-006 | Valutare incertezza geografica e qualità percettiva | Da concordare | Evidenze indipendenti e protocollo di validazione; [PQ-001, MOS-001 e GEO-002](open-issues.md) | Assunzioni, misure e limiti verificabili; nessuna modifica del punteggio priva di evidenza |

Map matching, previsioni e piani offline restano temi esplorativi descritti in
[PRED-001](open-issues.md#pred-001--previsioni-e-piani-offline). Non sono attività
approvate e non implicano propagazione della qualità a zone non osservate.

## Come aggiornare la lista

- Assegnare un ID stabile e distinguere **proposta**, **concordata**, **in corso**,
  **bloccata** e **completata**. La posizione nelle sezioni indica lo stato iniziale.
- Per attività concordate indicare priorità, risultato atteso, dipendenze e
  criteri di completamento; aggiungere il motivo quando un'attività è bloccata.
- Alla conclusione riportare data, commit e verifiche, aggiornando anche guide,
  limiti e checkpoint quando cambia il comportamento. Conservare l'ID originale.
- Nessuna scadenza, dipendenza o priorità è implicita. Usare solo esempi sintetici;
  log, destinatari, credenziali e database personali restano fuori dal documento.

## Completate

- 5 ottobre 2026: organizzata questa lista e aggiornati i collegamenti della
  documentazione. Nessuna evoluzione del modello avviata.

- SWITCH-001, 5 ottobre 2026: evidenziate richieste Switch Network esplicite in
  eventi, timeline, grafici, mappe e MCP. Verifiche sintetiche nel checkpoint;
  incluso nel consolidamento del 6 ottobre 2026.

- LOG-001, 5 ottobre 2026: controlli per famiglia e ambito dei log implementati;
  documentazione e verifiche nel checkpoint corrente.

Proposta ulteriore (non autorizzata): LOCAL-001, riparazione completa e audit
delle associazioni/derivazioni delle sessioni locali storiche, preservando ID
e annotazioni. Il limite di lettura introdotto per gli elenchi non è un backfill.

Proposte del 6 ottobre (da concordare): EXPORT-001, backup su disco e download
in streaming per database grandi; IMPORT-001, avanzamento delle fasi di import
e aggiornamento registro con misure delle prestazioni.

- PERF-001, 6 ottobre 2026: ottimizzazioni richieste per chiamata, import e mappa:
  indice schema 13, catalogo limitato alla selezione, riuso evidenze AWT e
  integrale degli intervalli. Misure e limiti nel checkpoint; la mappa globale
  rimane costosa su periodi ampi. Ulteriori cache/aggregati da concordare.
