# ClimaG Master Integration for Home Assistant

L'integrazione **ClimaG** è un componente personalizzato (custom component) avanzato per Home Assistant progettato e sviluppato da **Gex89**. 

Il suo scopo principale è la centralizzazione e il coordinamento deterministico di un sistema di climatizzazione multizona. ClimaG funge da "Master" intelligente che monitora costantemente i singoli termostati di zona, regola l'apertura delle rispettive valvole e pilota in modo ottimale ed efficiente una pompa di calore centralizzata, calcolando dinamicamente le temperature ideali di mandata sia in riscaldamento che in raffrescamento.

---

## Caratteristiche Principali

- **Coordinamento Intelligente delle Zone**: Se una zona indipendente richiede riscaldamento o raffrescamento, il Master si attiva automaticamente e allinea il sistema. Se tutte le zone si spengono, il sistema Master spegne la produzione centrale con logiche di ritardo configurabili.
- **Calcolo Dinamico Tmf/Tmc**: Algoritmo reattivo che calcola la temperatura di mandata ideale per il raffrescamento ($Tmf$) e per il riscaldamento ($Tmc$) basandosi sul massimo Delta T reale ($T_{\text{attiva}} - T_{\text{desiderata}}$) rilevato tra le zone attive.
- **Variabile `master_cmd`**: Gestione avanzata dei flussi dei comandi dall'interfaccia utente. Quando l'utente imposta una modalità direttamente dal pannello Master, ClimaG forza in modo intelligente l'accensione e l'allineamento dei termostati secondari spenti o in sola ventilazione.
- **Protezione e Temporizzazione dei Carichi**: Gestione nativa dei tempi di accensione e spegnimento per preservare l'idraulica e i cicli di vita della pompa di calore (ritardi di apertura valvole e spegnimenti ritardati).

---

## Installazione

### Metodo 1: Installazione Manuale
1. Accedi alla cartella di configurazione di Home Assistant (dove risiede il file `configuration.yaml`).
2. Se non esiste, crea una cartella chiamata `custom_components`.
3. All'interno di `custom_components`, crea una nuova cartella denominata `climag`.
4. Copia all'interno di questa cartella tutti i file dell'integrazione:
   - `__init__.py`
   - `climate.py`
   - `config_flow.py`
   - `manifest.json`
   - `number.py`
   - `select.py`
   - `strings.json`
5. Riavvia Home Assistant.

### Metodo 2: Tramite HACS (Consigliato per il rilascio su GitHub)
Una volta caricato il repository su GitHub:
1. Su Home Assistant, vai su **HACS** > **Integrazioni**.
2. Clicca sui tre puntini in alto a destra e seleziona **Repository personalizzati**.
3. Incolla l'URL del tuo repository GitHub, seleziona la categoria `Integration` e clicca su **Aggiungi**.
4. Trova l'integrazione **ClimaG** nella lista, clicca su **Scarica** e riavvia Home Assistant.

---

## Configurazione Iniziale (Config Flow)

Dopo il riavvio, vai su **Impostazioni** > **Dispositivi e Servizi** > **Aggiungi Integrazione** e cerca **ClimaG**. Si aprirà una schermata di configurazione guidata graficamente basata sui seguenti parametri:

| Parametro | Tipo Selector | Descrizione |
| :--- | :--- | :--- |
| **Nome del Controller Master** | Testo | Il nome amichevole da assegnare all'entità principale (Es: `ClimaG Master`). Determinerà anche lo slug dei dispositivi generati. |
| **Sensore Temperatura Esterna** | Entità `sensor` | (Opzionale) Sensore di temperatura esterna con `device_class: temperature` per il monitoraggio climatico. |
| **Termostati di Zona da coordinare** | Entità `climate` (Multiplo) | Selezione multipla di tutti i termostati delle singole stanze che il controllore Master deve monitorare e coordinare. |
| **Entità della Pompa di Calore** | Entità `climate` (Singolo) | L'entità climatica principale che controlla l'hardware della pompa di calore centralizzata. |

*Nota: Tramite il pulsante **Configura** sull'integrazione già installata, è possibile modificare in qualsiasi momento il sensore esterno, i termostati di zona e la pompa di calore associata senza dover reinstallare il componente.*

---

## Parametri di Configurazione Avanzati (Entità `number`)

Una volta completata l'installazione, l'integrazione genererà automaticamente delle entità di controllo di tipo `number` (sotto la categoria Configurazione) per regolare il comportamento degli algoritmi in tempo reale:

- **kpc / kpf** *(Default: 2.0 / 1.0)*: Coefficienti moltiplicativi per il calcolo proporzionale del Delta T termico delle zone.
- **Tmf-b** *(Default: 18.0°C)*: Temperatura di base per il calcolo del raffrescamento.
- **Tmc-b** *(Default: 45.0°C)*: Temperatura di base per il calcolo del riscaldamento.
- **Tmf min / Tmf max**: Limiti di sicurezza rigidi entro cui può oscillare la temperatura di mandata calcolata per il raffrescamento.
- **Tmc min / Tmc max**: Limiti di sicurezza rigidi entro cui può oscillare la temperatura di mandata calcolata per il riscaldamento.
- **valve_on_delay**: Tempo di attesa (in secondi) dall'apertura della prima valvola di zona prima di impartire l'effettivo comando di accensione alla pompa di calore (permette alle valvole motorizzate di completare l'apertura fisica).
- **termo_off_delay**: Il tempo (in secondi) che deve trascorrere da quando il selettore ClimaG Mode passa a `off` (o da quando tutte le zone si spengono contemporaneamente) prima di spegnere definitivamente la pompa di calore. Evita continui cicli di accensione/spegnimento ravvicinati.
- **climag_mode_delay**: Ritardo di attivazione globale quando viene cambiata la modalità dal selettore principale.

---
## Crediti e Sviluppo
L'integrazione ClimaG è stata ideata, strutturata e realizzata interamente da **Gex89**.
