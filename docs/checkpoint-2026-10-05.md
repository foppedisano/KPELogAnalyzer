# Checkpoint — 5 ottobre 2026 · MCP 1.3.0

Leggere `AGENTS.md`, [installazione autonoma](getting-started.md) e il precedente
[checkpoint mappa](checkpoint-2026-10-04.md). Ramo `main`, remoto previsto
`https://github.com/foppedisano/KPELogAnalyzer.git`.

## Stato consolidato

- MCP stdio **1.3.0**, 12 strumenti. Nuovi adattatori per campioni PQ, percorso
  della chiamata e timeline rete/servizi; riusano i calcoli della UI.
- `analytics_geo_cells` accetta `metric=perceptual`; il default MOS resta
  compatibile. Celle dirette prioritarie, stime separate nei soli vuoti
  attraversati; percorso della singola chiamata conservato.
- Catalogo: `current_analysis`, `a_connectivity`, `a_user_attempts`.
  Copertura: conteggi grezzi per livello/stato. Nessuna associazione dei tentativi
  a chiamate per numero o tempo; destinatario e testo grezzo esclusi dalla vista.
- Schema **12**, parser **1.12.0**, PQ **awt-occupancy-4** invariati.
  Nessuna migrazione o importazione richiesta da questa integrazione.
- Nuovi endpoint in sola lettura, snapshot coerente, risposta massima 4 MiB.
  Profili temporali PQ e paginazione PQ/percorso non implementati;
  [contratto e limiti](analytics.md) descrivono le differenze dalle viste UI.

## Verifiche e servizio

**220 test superati**, in locale e Python 3.12 Docker senza rete, con repository
in sola lettura e database sintetici temporanei. Verificati MCP stdio → HTTP,
parità con API UI, evidenze, input errati, scope, authorizer e limite di risposta.
Documentazione e collegamenti locali controllati; frontend invariato.

Container `kpeloganalyzer-analyzer-1` ricostruito e healthy su
`http://127.0.0.1:8080/`. Handshake reale: MCP 1.3.0, 12 strumenti e catalogo
aggiornato. Backup consistente `pre-mcp-130-20261005-043502.sqlite3` nel volume
locale, quick_check positivo. Nessun dato demo nell'archivio personale.
Riconnettere il client MCP per ricaricare gli strumenti.

## Pubblicazione e ripartenza

L'utente ha autorizzato commit e push di codice, test sintetici e documentazione.
ZIP, database, backup e risultati locali restano esclusi dal repository.
Individuare il commit con `git log -1 -- docs/checkpoint-2026-10-05.md`;
controllare `git status --short` e l'allineamento con `origin/main` prima di
nuovi interventi. Il checkpoint non sostituisce la verifica dello stato remoto.

> Riprendi KPELogAnalyzer da AGENTS.md e docs/checkpoint-2026-10-05.md.
> Verifica Git e servizio locale. MCP 1.3.0 espone 12 strumenti; preserva
> precedenza delle celle dirette, stime separate e percorso chiamata.
> Mantieni installazione Docker autonoma, dati personali locali e modelli
> invariati. Attendi la mia prossima richiesta prima di ulteriori sviluppi.
