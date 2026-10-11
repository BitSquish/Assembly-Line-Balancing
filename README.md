# Assembly Line Balancing (SALBP-2)

Progetto per il corso di AMOD (Algoritmi e Modelli per l'Ottimizzazione Discreta): due modelli di programmazione lineare intera e due
euristiche per il **Simple Assembly Line Balancing Problem di tipo 2**, confrontati
su 1800 istanze generate pseudo-casualmente.

## Il problema

Una linea di montaggio ha **m stazioni in sequenza**. Ogni task *i* ha un tempo
*tᵢ* e va assegnato a una sola stazione; le precedenze (*i* → *j*) impongono che
*i* stia in una stazione uguale o precedente a quella di *j*. Il carico di una
stazione è la somma dei tempi dei suoi task.

**Obiettivo:** dato *m*, minimizzare il carico massimo di stazione *c* (il tempo
ciclo della linea). 

## Metodi

### Bound (`src/bounds.py`)

**Lower bound**, usato da tutti i metodi. Segue i bound LC1-LC3 di Scholl &
Becker (2006, sez. 4.1), calcolati in tre passi:

1. **LC1 e LC2.** Carico medio: c ≥ max{t_max, ⌈Σ tᵢ / m⌉} (McNaughton, 1959).
   Principio dei cassetti (Klein & Scholl, 1996): tra i *k·m* + 1 task più
   lunghi, almeno *k* + 1 stanno nella stessa stazione.
2. **LC3 con finestre semplici.** Per un tempo ciclo *c*, il task *i* non può
   stare prima della stazione E_i(c) = ⌈(tᵢ + tempi di tutti i predecessori) / c⌉
   né dopo L_i(c) = m + 1 − ⌈(tᵢ + tempi di tutti i successori) / c⌉
   (Patterson & Albracht, 1975; Ritt & Costa, 2018, sez. 2.2). Si alza *c*
   finché tutte le finestre sono non vuote.
3. **LC3 con teste e code ricorsive.** Le stesse finestre, con un limite più
   stretto sul tempo che deve precedere e seguire ogni task, calcolato come il
   bound a una macchina LM4 di Johnson (1988), senza i bound di conteggio sui
   sottoproblemi. Si alza *c* finché nessun task viola il test.

Ogni valore di *c* scartato è irraggiungibile da qualsiasi soluzione, quindi il
risultato è un lower bound valido. La validità è verificata nei test contro
l'ottimo calcolato per enumerazione completa.

**Upper bound iniziale:** soluzione greedy in ordine topologico. Serve solo a
fissare l'intervallo di *c* e le finestre di stazione dei modelli.

Il lower bound riportato per un modello PLI è il massimo tra il bound
combinatorio e quello restituito dal solver.

### Modelli PLI (`src/models/`)

I due modelli condividono le variabili *x[i, s]* (task *i* nella stazione *s*),
le finestre di stazione statiche e i bound su *c*. Differiscono nella
formulazione delle precedenze; i nomi seguono Ritt & Costa (2018, tab. 2).

| Modello | File | Precedenze per l'arco (*i*, *j*) |
| --- | --- | --- |
| PA2-2, Patterson & Albracht (1975) | `patterson_albracht.py` | Σₛ s·x[i,s] ≤ Σₛ s·x[j,s]: un vincolo per arco |
| NF4-2, Ritt & Costa (2018) | `ritt_costa.py` | Σ_{s≤k} x[i,s] ≥ Σ_{s≤k} x[j,s] per ogni stazione k, più variabili sul tempo ciclo e tagli sulle finestre di stazione |

Il contributo di Patterson & Albracht (1975) usato qui è il vincolo di
precedenza e le finestre di stazione. Il loro articolo tratta il SALBP-1, ma
vincolo e finestre non dipendono dal tipo di problema. Ritt & Costa dimostrano
che la loro precedenza cumulata domina quella di Patterson & Albracht (prop. 2).

Il primo modello è il più compatto, il secondo ha il rilassamento lineare più
forte. Entrambi usano le stesse finestre di stazione, gli stessi bound e la
riduzione transitiva degli archi, quindi il confronto misura la formulazione e
non il pre-processing. Con 200 task, Patterson & Albracht ha in media circa
740 vincoli, Ritt & Costa tra 12.000 e 13.600.

I modelli sono scritti con PuLP e risolti con Gurobi.

### Euristiche (`src/heuristic/`)

| Euristica | File | Idea |
| --- | --- | --- |
| Gruppi (sviluppata nel progetto) | `groups.py` | raggruppa i task legati da precedenze, dispone i gruppi lungo la linea secondo il grafo dei gruppi e usa le foglie del grafo come riempitivi |
| Saturazione delle stazioni (Hoffmann, 1963, adattata al SALBP-2) | `hoffmann.py` | riempie ogni stazione con l'insieme di task disponibili che lascia il minimo tempo inutilizzato |

Entrambe cercano il più piccolo tempo ciclo ammissibile partendo dal lower bound
(schema descritto in Scholl & Becker, 2006, sez. 4.2.1 e 5.1.3), con lo stesso
ciclo esterno: il confronto misura solo il criterio di riempimento delle stazioni.

La saturazione delle stazioni è nata nello sviluppo del progetto come evoluzione
dell'euristica dei gruppi; una verifica sulla letteratura ha mostrato che il
criterio coincide con quello di Hoffmann, pensato per il SALBP-1. La versione del
progetto aggiunge la ricerca sul tempo ciclo e un limite di 20.000 nodi per
stazione, mai raggiunto nella campagna (vedi la docstring di `hoffmann.py`).

## Istanze

Generate da `src/generator.py`, che controlla direttamente l'**order strength**
(OS): la frazione di coppie di task il cui ordine è fissato dalle precedenze,
dirette o indirette. Il generatore aggiunge archi *u* → *v* con *u* < *v*,
saltando quelli già implicati, finché l'OS raggiunge l'obiettivo (tolleranza
0,02). È lo stesso passo finale del generatore SALBPGen (Otto et al., 2013), che
però costruisce prima il grafo a stadi e può inserire catene e colli di
bottiglia; il generatore del progetto parte invece da un grafo vuoto.
Ogni istanza è riproducibile: il seed dipende solo dal seed di base, dal gruppo
e dall'indice.

Disegno sperimentale (`configs/design.json`): fattoriale completo su quattro
fattori, **25 istanze per combinazione, 72 combinazioni, 1800 istanze**.

| Fattore | Livelli |
| --- | --- |
| Numero di task *n* | 20, 50, 100, 200 |
| Order strength | 0,2 (grafo sparso), 0,6 (denso), 0,9 (quasi una catena) |
| Numero di stazioni *m* | *n*/3 (tante), *n*/6 (medie), *n*/10 (poche) |
| Tempi dei task | uniformi tra 1 e 100, oppure bimodali (80% tra 1 e 33, 20% tra 68 e 100) |

Da dove vengono le scelte:

- *n* = 20, 50, 100, i livelli di OS e le 25 istanze per combinazione seguono
  Otto, Otto & Scholl (2013).
- *n* = 200 è una scelta del progetto (Otto et al. arrivano a 1000 task).
  Álvarez-Miranda et al. (2023) osservano che i metodi esatti iniziano a
  fallire intorno ai 100 task: con 200 il disegno ha un livello in cui i PLI
  non chiudono più.
- Il numero di stazioni in proporzione a *n* è una scelta del progetto. Otto et al.
  controllano la difficoltà attraverso i tempi dei task rispetto al tempo ciclo;
  nel SALBP-2 il tempo ciclo non è un dato, e il numero di stazioni ne fa le veci.
  Álvarez-Miranda et al. (2023) usano lo stesso parametro (numero atteso di task
  per stazione) e mostrano che l'impacchettamento dei task è la principale fonte
  di difficoltà: le istanze di Otto et al. ancora aperte hanno tutte circa due
  task per stazione.
- I tempi bimodali sono la distribuzione di default di SALBPGen e quella tipica
  dei dati industriali; i limiti degli intervalli sono una scelta del progetto.
- Otto et al. distinguono anche grafi con molte catene o colli di bottiglia;
  il progetto usa un solo tipo di grafo, senza questo controllo.

I nomi dei gruppi contengono la distribuzione (`_uniform`, `_bimodal`) ed entrano
nel seed: rinominarli cambia le istanze.

## Installazione

Richiede **Python ≥ 3.10** e **Gurobi** con licenza.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

La licenza inclusa in `gurobipy` installato con pip è limitata (2000 variabili e
2000 vincoli): basta per i test e per le istanze piccole. Per gli esperimenti
serve la licenza accademica gratuita di Gurobi.

## Uso

Tutti i comandi vanno lanciati dalla cartella del progetto.

### Menù

```bash
python -m src.main
```

| Voce | Cosa fa |
| --- | --- |
| 1 | campagna completa di `configs/design.json`; si può interrompere e riprendere |
| 2 | demo rapida: tre istanze da 50 task e una da 200, tutti i metodi, 15 secondi per PLI |
| 3 | personalizzato: metodi, limite di tempo e parametri delle istanze a scelta |
| 4 | tabella riassuntiva di un file di risultati |
| 5 | grafici e tabelle da un file di risultati |
| 6 | test del progetto |

Le voci 2 e 3 generano le istanze al momento, con la stessa regola della
campagna, e salvano istanze e risultati in `instances_demo/` e
`results/demo_<data>_<ora>.csv`.

### Comandi diretti

```bash
# test
python -m pytest

# generazione delle istanze
python -m scripts.gen_instances --config configs/design.json --out instances/

# campagna completa: 180 secondi per ogni modello PLI
python -m scripts.run_experiments --manifest instances/manifest.csv \
    --out results/results.csv --time-limit 180

# tabelle e grafici
python -m scripts.make_figures --results results/results.csv \
    --out results/figures_results/ --time-limit 180
```

`run_experiments` scrive una riga per (istanza, metodo) appena il risultato è
pronto e, se rilanciato, salta le esecuzioni già presenti. Con `--methods` si
eseguono solo alcuni metodi, per esempio `--methods hoffmann gruppi`.

## Esperimenti

| Impostazione | Valore |
| --- | --- |
| Limite di tempo per modello PLI | 180 secondi |
| Solver | Gurobi, 6 thread, `MIPGapAbs` = 0,999 |
| Esecuzione | in sequenza, un metodo alla volta |
| Macchina | AMD Ryzen 5 5500U (6 core), 8 GB di RAM |

`MIPGapAbs` sotto 1 è lecito perché l'ottimo è intero: quando la distanza tra
soluzione e bound scende sotto 1, l'ottimo è dimostrato.

Il limite di tempo vale per la sola risoluzione; il tempo riportato per i PLI
comprende anche la costruzione del modello (colonna `build_s`), quello delle
euristiche anche la costruzione del grafo e il calcolo del lower bound.

### Storia della campagna

La campagna sulle istanze uniformi è stata eseguita prima con il lower bound dei
passi 1 e 2. L'analisi dei risultati ha mostrato che a OS 0,9 quel bound era
debole: coincideva con l'ottimo solo nel 14% delle istanze chiuse, contro il 92%
a OS 0,2. È stato quindi aggiunto il passo 3.

Il bound entra nei metodi solo come valore (estremo inferiore di *c* nei PLI,
punto di partenza della ricerca nelle euristiche), quindi sono state rieseguite
solo le esecuzioni interessate (`scripts/rerun_bound.py`):

- tutte le euristiche, perché il loro tempo include il calcolo del bound;
- i PLI sulle 60 istanze in cui il bound cambia (tutte a OS 0,9).

Le soluzioni delle euristiche sono rimaste identiche; i PLI rieseguiti hanno
dato gli stessi ottimi. Il nuovo bound non chiude nessuna istanza aperta: dove
sale, il PLI aveva già dimostrato l'ottimo. Cambia la capacità delle euristiche
di certificare da sole l'ottimo (Hoffmann da 388 a 405 istanze). I risultati
della prima esecuzione e l'elenco delle istanze cambiate sono in
`results/storico/`.

I tempi bimodali sono stati aggiunti dopo, già con il bound completo: prima a
100 task e poi, visto che cambiavano molto la difficoltà, su tutto il disegno.

### Colonne dei risultati

| Colonna | Significato |
| --- | --- |
| `status` | `optimal` (ottimo dimostrato), `feasible` (limite di tempo, con soluzione), `no_solution`, `infeasible`, `solver_error`, `error` |
| `objective` | carico massimo della soluzione trovata; per un PLI fermato dal limite di tempo è l'incumbent |
| `lower_bound` | miglior lower bound del metodo (combinatorio o del solver) |
| `gap` | (objective − lower_bound) / lower_bound |
| `time_s`, `build_s` | tempo totale e tempo di costruzione del modello |

Per un modello PLI si riporta l'ottimo e il tempo, oppure, allo scadere del
limite, l'incumbent e il lower bound.

### Risultati principali

7200 esecuzioni, circa 48 ore di calcolo per i PLI (35 sulle istanze uniformi,
13 sulle bimodali). Nessuna esecuzione è terminata senza soluzione. L'ottimo è
noto, cioè dimostrato da almeno un metodo, in **719 istanze uniformi su 900** e
in **862 bimodali su 900**.

| Metodo | Ottimi dimostrati (unif. / bim.) | Ottimo raggiunto (unif. / bim.) | Scarto dal miglior LB (unif. / bim.) | Tempo medio (unif. / bim.) |
| --- | --- | --- | --- | --- |
| Patterson & Albracht | 575 / 816 | 83% / 95% | 0,53% / 0,16% | 71,6 / 25,8 s |
| Ritt & Costa | 600 / 828 | 84% / 96% | 0,61% / 0,11% | 68,3 / 27,4 s |
| Hoffmann | 405 / 598 | 82% / 88% | 0,66% / 0,21% | 0,11 / 0,11 s |
| Gruppi | 25 / 191 | 8% / 26% | 3,91% / 2,48% | 0,12 / 0,11 s |

- **Ottimi dimostrati:** istanze (su 900 per distribuzione) in cui il metodo,
  da solo, trova una soluzione uguale al proprio lower bound.
- **Ottimo raggiunto:** tra le istanze con ottimo noto, quota in cui il metodo
  trova una soluzione ottima, anche senza poterlo dimostrare. È la misura giusta
  per le euristiche.
- **Scarto dal miglior LB:** (obiettivo − miglior lower bound dell'istanza) /
  miglior lower bound, su tutte le istanze. Dove l'ottimo non è noto è un
  limite superiore alla distanza dall'ottimo.

Istanze chiuse per numero di task:

| Task | Uniformi | Bimodali |
| --- | --- | --- |
| 20 | 225 | 225 |
| 50 | 189 | 222 |
| 100 | 173 | 214 |
| 200 | 132 | 201 |

**Hoffmann contro il miglior PLI** (istanze in cui Hoffmann è migliore / uguale /
peggiore, test di Wilcoxon):

| Task | Uniformi | Bimodali |
| --- | --- | --- |
| 20 | 0 / 185 / 40 (p < 0,001) | 0 / 206 / 19 (p < 0,001) |
| 50 | 0 / 149 / 76 (p < 0,001) | 0 / 182 / 43 (p < 0,001) |
| 100 | 37 / 122 / 66 (p < 0,001) | 1 / 188 / 36 (p < 0,001) |
| 200 | 139 / 69 / 17 (p < 0,001) | 26 / 184 / 15 (p = 0,47) |

Osservazioni:

- **Hoffmann conviene quando l'impacchettamento è difficile.** Con tempi
  uniformi a 200 task è migliore dei PLI nella maggior parte delle istanze, in
  circa 0,3 secondi contro 180. Con tempi bimodali i PLI chiudono quasi tutto e
  a 200 task la differenza non è significativa, anche se lo scarto medio di
  Hoffmann resta il più basso (0,19% contro 0,36% del miglior PLI). Hoffmann
  dimostra da solo l'ottimo in 90 istanze uniformi e 20 bimodali in cui nessun
  PLI ci riesce.
- **Tempi bimodali più facili.** I task lunghi portano il bound vicino al tempo
  del task più lungo e i task brevi riempiono le stazioni, quindi il lower bound
  è spesso già l'ottimo. A parità di stazioni, però, le due distribuzioni danno
  un carico relativo diverso: il confronto non è a parità di difficoltà.
- **Difficoltà.** Con tempi uniformi il fattore decisivo è il numero di stazioni:
  le istanze chiuse sono il 49% con tante stazioni, il 92% con stazioni medie e
  il 99% con poche (con tempi bimodali 92%, 96% e 100%).
- **Patterson & Albracht contro Ritt & Costa.** Ritt & Costa dimostra l'ottimo in
  più istanze (chiuse solo da lui: 53 contro 28 uniformi, 26 contro 14
  bimodali), con il vantaggio maggiore a OS 0,9. Con tempi uniformi Patterson &
  Albracht trova più spesso la soluzione migliore (131 istanze contro 78), in
  linea con l'osservazione di Ritt & Costa sui limiti di stazione; con tempi
  bimodali sono quasi pari (27 contro 32).
- **Gruppi contro Hoffmann.** Hoffmann è migliore in 833 istanze uniformi e 671
  bimodali, peggiore in 2 per ciascuna distribuzione.
- **Istanze aperte.** Restano 181 istanze uniformi (gap medio 1,6%) e 38
  bimodali (1,2%), quasi tutte con tante stazioni.
- **Contesto.** Un PLI con solver generico e 3 minuti non compete con i
  branch-and-bound specializzati, che sulle istanze di letteratura da 100 task
  lasciano aperte pochissime istanze (Álvarez-Miranda et al., 2023). Lo scopo è
  confrontare le formulazioni tra loro e con l'euristica.

Tabelle e grafici completi sono in `results/figures_results/`. Quelli principali
riguardano le istanze uniformi e sono griglie di pannelli che seguono il
disegno: una colonna per numero di task, una riga per order strength e, dentro
ogni pannello, un gruppo di barre per numero di stazioni. Il confronto tra le
distribuzioni è in `tabella_distribuzioni_<n>.csv` e nei grafici
`distribuzioni_<n>_*.png`, una coppia di colonne per ogni numero di task.

## Note sulle scelte

- **Solver.** Il progetto è partito con HiGHS (open source). Durante i test,
  HiGHS 1.15.1 ha restituito risultati errati su due istanze piccole: in una ha
  dichiarato non ammissibile un modello ammissibile, nell'altra ha dichiarato
  ottima una soluzione che viola un vincolo. Il problema dipende dal presolve ed
  è stato segnalato agli sviluppatori:
  https://github.com/ERGO-Code/HiGHS/issues/3333. Si è quindi passati a Gurobi.
  I file per riprodurre il problema sono in `highs_bug_report/`.
- **Verifica dei modelli.** I test (`tests/test_models.py`) confrontano ogni
  modello con l'ottimo calcolato per enumerazione completa su 120 istanze
  piccole. Ogni soluzione, di PLI ed euristiche, passa da un validatore
  indipendente (`src/solution.py`).
- **Ottimo dimostrato.** Lo stato `optimal` è assegnato solo se l'obiettivo
  coincide con il lower bound, indipendentemente da quanto dichiara il solver.
  Vale anche per le euristiche: se la soluzione raggiunge il lower bound
  combinatorio, è ottima.

## Struttura

```
configs/              disegno sperimentale (design.json)
scripts/
  gen_instances.py    generazione delle istanze e del manifest
  run_experiments.py  esecuzione dei metodi sulle istanze
  make_figures.py     tabelle e grafici dai risultati
  rerun_bound.py      riesecuzione e verifica dopo il cambio di lower bound
src/
  main.py             menù del progetto
  instance.py         istanza e lettura/scrittura del formato .alb
  graph.py            chiusura e riduzione transitiva, order strength
  bounds.py           lower bound, upper bound, finestre di stazione
  solution.py         soluzione, validatore, esito di un metodo
  generator.py        generatore di istanze
  models/             modelli PLI
  heuristic/          euristiche
tests/                test (pytest)
instances/            istanze generate (con manifest.csv)
results/
  results.csv         risultati della campagna
  figures_results/    tabelle e grafici
  storico/            prima esecuzione e istanze con bound cambiato
highs_bug_report/     file del problema segnalato a HiGHS
```

## Riferimenti

- Álvarez-Miranda, E., Pereira, J., & Vilà, M. (2023). Analysis of the simple assembly line balancing problem complexity. *Computers & Operations Research*, 159, 106323.
- Hoffmann, T. R. (1963). Assembly line balancing with a precedence matrix. *Management Science*, 9(4), 551–562.
- Johnson, R. V. (1988). Optimally balancing large assembly lines with "FABLE". *Management Science*, 34(2), 240–253.
- Klein, R., & Scholl, A. (1996). Maximizing the production rate in simple assembly line balancing — A branch and bound procedure. *European Journal of Operational Research*, 91(2), 367–385.
- McNaughton, R. (1959). Scheduling with deadlines and loss functions. *Management Science*, 6(1), 1–12.
- Otto, A., Otto, C., & Scholl, A. (2013). Systematic data generation and test design for solution algorithms on the example of SALBPGen for assembly line balancing. *European Journal of Operational Research*, 228(1), 33–45.
- Patterson, J. H., & Albracht, J. J. (1975). Technical Note — Assembly-line balancing: Zero-one programming with Fibonacci search. *Operations Research*, 23(1), 166–172.
- Ritt, M., & Costa, A. M. (2018). Improved integer programming models for simple assembly line balancing and related problems. *International Transactions in Operational Research*, 25(4), 1345–1359. DOI 10.1111/itor.12206.
- Scholl, A. (1999). *Balancing and Sequencing of Assembly Lines* (2ª ed.). Physica-Verlag, Heidelberg.
- Scholl, A., & Becker, C. (2006). State-of-the-art exact and heuristic solution procedures for simple assembly line balancing. *European Journal of Operational Research*, 168(3), 666–693.