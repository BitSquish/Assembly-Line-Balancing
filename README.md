# Assembly Line Balancing (SALBP-2)

Progetto per il corso di AMOD: due modelli di programmazione lineare intera e due
euristiche per il **Simple Assembly Line Balancing Problem di tipo 2**, confrontati
su istanze generate pseudo-casualmente.

## Il problema

Una linea di montaggio ha **m stazioni in sequenza**. Ogni task *i* ha un tempo
*tᵢ* e va assegnato a una sola stazione; le precedenze (*i* → *j*) impongono che
*i* stia in una stazione uguale o precedente a quella di *j*. Il carico di una
stazione è la somma dei tempi dei suoi task.

**Obiettivo:** dato *m*, minimizzare il carico massimo di stazione *c* (il tempo
ciclo della linea). Esempio: con carichi 10, 12 e 9 il valore della soluzione è 12.

## Metodi

### Modelli PLI (`src/models/`)

I due modelli condividono le variabili *x[i, s]* (task *i* nella stazione *s*),
le finestre di stazione e i bound su *c*. Differiscono nella formulazione delle
precedenze, secondo la classificazione di Ritt & Costa (2018).

| Modello | File | Precedenze per l'arco (*i*, *j*) |
| --- | --- | --- |
| Patterson & Albracht (1975) | `patterson_albracht.py` | Σₛ s·x[i,s] ≤ Σₛ s·x[j,s]: un vincolo per arco |
| Ritt & Costa (2018) | `ritt_costa.py` | Σ_{s≤k} x[i,s] ≥ Σ_{s≤k} x[j,s] per ogni stazione k, più variabili sul tempo ciclo e tagli sulle finestre di stazione |

Il primo è la formulazione più compatta, il secondo quella con il rilassamento
lineare più forte: Ritt & Costa dimostrano che la loro precedenza domina quella
di Patterson & Albracht. Entrambi usano le stesse finestre di stazione statiche,
gli stessi bound e la riduzione transitiva degli archi, quindi il confronto
misura la formulazione e non il pre-processing.

I modelli sono scritti con PuLP e risolti con Gurobi.

### Euristiche (`src/heuristic/`)

| Euristica | File | Idea |
| --- | --- | --- |
| Gruppi (sviluppata nel progetto) | `groups.py` | raggruppa i task legati da precedenze, dispone i gruppi lungo la linea secondo il grafo dei gruppi e usa le foglie del grafo come riempitivi |
| Hoffmann (1963) | `hoffmann.py` | riempie ogni stazione con l'insieme di task che lascia il minimo tempo inutilizzato; riferimento dalla letteratura |

Entrambe cercano il più piccolo tempo ciclo ammissibile partendo dal lower bound
(ricerca descritta in Scholl & Becker, 2006, sez. 4.2.1 e 5.1.3).

La saturazione delle stazioni è nata nello sviluppo del progetto come evoluzione
dell'euristica dei gruppi; una verifica sulla letteratura ha mostrato che coincide
con l'euristica di Hoffmann. Rispetto all'originale, pensata per il SALBP-1 e con
enumerazione completa degli insiemi, la versione del progetto aggiunge la ricerca
sul tempo ciclo e limita a 20.000 i nodi esplorati per stazione (vedi la docstring
di `hoffmann.py`).

### Bound (`src/bounds.py`)

- **Lower bound:** il massimo tra LC1 (McNaughton, 1959), LC2 (Klein & Scholl,
  1996) e LC3, basato sulle stazioni minime e massime di ogni task (Scholl, 1999),
  come descritti in Scholl & Becker (2006).
- **Upper bound iniziale:** soluzione greedy in ordine topologico. Serve solo a
  fissare l'intervallo di *c* e le finestre di stazione dei modelli.

Il lower bound riportato per un modello PLI è il massimo tra questo bound
combinatorio e quello restituito dal solver.

## Istanze

Generate da `src/generator.py`, che controlla direttamente l'**order strength**
(OS): la frazione di coppie di task il cui ordine è fissato dalle precedenze,
dirette o indirette. Il generatore aggiunge archi *u* → *v* con *u* < *v* finché
l'OS raggiunge l'obiettivo (tolleranza 0,02). Ogni istanza è riproducibile: il
seed dipende solo dal seed di base, dal gruppo e dall'indice.

Disegno sperimentale (`configs/design.json`): fattoriale completo su tre fattori.

| Fattore | Livelli |
| --- | --- |
| Numero di task *n* | 20, 50, 100, 200 |
| Order strength | 0,2 (grafo sparso), 0,6 (denso), 0,9 (quasi una catena) |
| Numero di stazioni *m* | *n*/3 (tante), *n*/6 (medie), *n*/10 (poche) |

Sono 36 gruppi: 25 istanze per gruppo con 20, 50 e 100 task, 10 istanze per
gruppo con 200 task (per limiti di tempo di calcolo). **765 istanze in totale.**

Da dove vengono le scelte:

- I livelli di *n* e di OS e le 25 istanze per combinazione seguono Otto, Otto &
  Scholl (2013).
- I tempi dei task, interi uniformi tra 1 e 100, sono una scelta del progetto.
- Il numero di stazioni in proporzione a *n* è una scelta del progetto. Otto et al.
  controllano la difficoltà attraverso il rapporto tra tempi dei task e tempo
  ciclo; nel SALBP-2 il tempo ciclo non è un dato, e il numero di stazioni ne fa
  le veci: tante stazioni significano task lunghi rispetto al carico di stazione,
  cioè istanze più difficili (si veda anche Álvarez-Miranda et al., 2023).

Il generatore prevede anche tempi bimodali (80% task corti, 20% lunghi), usabili
dal menù ma non inclusi nel disegno.

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
| 2 | demo rapida: tre istanze da 50 task, tutti i metodi, 15 secondi per PLI |
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

Il limite di tempo vale per la sola risoluzione; il tempo riportato comprende
anche la costruzione del modello (colonna `build_s`).

### Risultati

Colonne principali di `results/*.csv`:

| Colonna | Significato |
| --- | --- |
| `status` | `optimal` (ottimo dimostrato), `feasible` (limite di tempo, con soluzione), `no_solution`, `infeasible`, `solver_error`, `error` |
| `objective` | carico massimo della soluzione trovata |
| `lower_bound` | miglior lower bound del metodo (combinatorio o del solver) |
| `gap` | (objective − lower_bound) / lower_bound |
| `time_s`, `build_s` | tempo totale e tempo di costruzione del modello |

Per un modello PLI si riporta l'ottimo e il tempo, oppure, allo scadere del
limite, la miglior soluzione trovata e il lower bound.

L'analisi confronta ogni euristica con il miglior lower bound disponibile per
l'istanza (il massimo tra quelli di tutti i metodi), che coincide con l'ottimo
quando un metodo lo ha dimostrato. I grafici sono griglie di pannelli che seguono
il disegno: una colonna per numero di task, una riga per order strength e, dentro
ogni pannello, un gruppo di barre per numero di stazioni.

## Note sulle scelte

- **Solver.** Il progetto è partito con HiGHS (open source). Durante i test,
  HiGHS 1.15.1 ha restituito risultati errati su due istanze piccole: in una ha
  dichiarato non ammissibile un modello ammissibile, nell'altra ha dichiarato
  ottima una soluzione che viola un vincolo. Il problema dipende dal presolve ed
  è stato segnalato agli sviluppatori:
  https://github.com/ERGO-Code/HiGHS/issues/3333. Si è quindi passati a Gurobi.
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
configs/            disegno sperimentale (design.json)
scripts/
  gen_instances.py    generazione delle istanze e del manifest
  run_experiments.py  esecuzione dei metodi sulle istanze
  make_figures.py     tabelle e grafici dai risultati
src/
  main.py           menù del progetto
  instance.py       istanza e lettura/scrittura del formato .alb
  graph.py          chiusura e riduzione transitiva, order strength
  bounds.py         lower bound, upper bound, finestre di stazione
  solution.py       soluzione, validatore, esito di un metodo
  generator.py      generatore di istanze
  models/           modelli PLI
  heuristic/        euristiche
tests/              test (pytest)
instances/          istanze generate (con manifest.csv)
results/            risultati, tabelle e grafici
```

## Riferimenti

- Álvarez-Miranda, E., Pereira, J., & Vilà, M. (2023). Analysis of the simple assembly line balancing problem complexity. *Computers & Operations Research*, 159.
- Hoffmann, T. R. (1963). Assembly line balancing with a precedence matrix. *Management Science*.
- Klein, R., & Scholl, A. (1996). Maximizing the production rate in simple assembly line balancing — A branch and bound procedure. *European Journal of Operational Research*, 91(2).
- McNaughton, R. (1959). Scheduling with deadlines and loss functions. *Management Science*, 6(1).
- Otto, A., Otto, C., & Scholl, A. (2013). Systematic data generation and test design for solution algorithms on the example of SALBPGen for assembly line balancing. *European Journal of Operational Research*, 228(1), 33–45.
- Patterson, J. H., & Albracht, J. J. (1975). Assembly-line balancing: zero-one programming with Fibonacci search. *Operations Research*, 23(1), 166–172.
- Ritt, M., & Costa, A. M. (2018). Improved integer programming models for simple assembly line balancing and related problems. *International Transactions in Operational Research*. DOI 10.1111/itor.12206.
- Scholl, A. (1999). *Balancing and Sequencing of Assembly Lines* (2ª ed.). Physica-Verlag.
- Scholl, A., & Becker, C. (2006). State-of-the-art exact and heuristic solution procedures for simple assembly line balancing. *European Journal of Operational Research*, 168(3), 666–693.
