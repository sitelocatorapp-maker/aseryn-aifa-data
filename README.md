# ASERYN AIFA Data

Catalogo remoto dei farmaci per ASERYN.

Il catalogo viene generato automaticamente dagli open data AIFA e pubblicato tramite GitHub Pages.

- Ricerca client avviata da 3 caratteri.
- Shard per le prime 3 lettere normalizzate del nome del farmaco.
- Aggiornamento automatico settimanale tramite GitHub Actions.
- I file generati in `public/` non devono essere modificati manualmente.

URL previsto:
`https://sitelocatorapp-maker.github.io/aseryn-aifa-data`

## Manutenzione del repository

Il workflow `Aggiorna archivio AIFA` genera e pubblica settimanalmente il catalogo su GitHub Pages. Il presente aggiornamento documentale non modifica la frequenza di esecuzione, lo script di generazione, i dati pubblicati o la configurazione di GitHub Pages.

GitHub può disabilitare i workflow programmati dopo un periodo di inattività del repository: verificare periodicamente lo stato del workflow nella sezione Actions. Un commit documentale aggiorna l'attività del repository, ma non costituisce una garanzia di attivazione permanente.
