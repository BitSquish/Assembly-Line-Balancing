# Assembly Line Balancing (SALBP-2)

Progetto per il corso di AMOD: tre modelli di programmazione lineare intera e due
euristiche per il **Simple Assembly Line Balancing Problem di tipo 2**, confrontati
su istanze generate pseudo-casualmente.

## Il problema

Una linea di montaggio ha **m stazioni in sequenza**. Ogni operazione (task) *i*
ha un tempo *tᵢ* e va assegnata a una sola stazione; le precedenze (*i* → *j*)
impongono che *i* stia in una stazione uguale o precedente a quella di *j*.
Il carico di una stazione è la somma dei tempi delle sue operazioni.

**Obiettivo:** dato *m*, minimizzare il carico massimo di stazione *c* (il tempo
ciclo della linea). Esempio: con carichi 10, 12 e 9 il valore della soluzione è 12.

## Metodi

### Modelli PLI (`src/models/`)

I tre modelli condividono variabili *x[i, s]* (task *i* nella stazione *s*),
finestre di stazione e bound su *c*; differiscono nella formulazione delle
precedenze, secondo la classificazione di Ritt & Costa (2018).

| Modello | File | Precedenze per l'arco (*i*, *j*) |
| --- | --- | --- |
| Patterson & Albracht (1975) | `patterson_albracht.py` | Σₛ s·x[i,s] ≤ Σₛ s·x[j,s] (un vincolo per arco) |
| Bowman (1960), White (1961) | `bowman_white.py` | x[j,t] ≤ Σ_{s≤t} x[i,s] per ogni stazione t |
| Ritt & Costa (2018) | `ritt_costa.py` | Σ_{s≤k} x[i,s] ≥ Σ_{s≤k} x[j,s] per ogni stazione k, più variabili sul tempo ciclo e tagli sulle finestre |

Ritt & Costa dimostrano che la loro precedenza domina strettamente le altre due.
Tutti i modelli usano le stesse finestre di stazione statiche e la riduzione
transitiva degli archi, quindi il confronto misura la formulazione, non il
pre-processing.

### Euristiche (`src/heuristic/`)

| Euristica | File | Idea |
| --- | --- | --- |
| Gruppi (sviluppata nel progetto) | `groups.py` | raggruppa le operazioni legate da precedenze, le dispone lungo la linea secondo il grafo dei gruppi e usa le foglie del grafo come riempitivi |
| Hoffmann (1963) | `hoffmann.py` | riempie ogni stazione con l'insieme di operazioni che lascia il minimo tempo inutilizzato; riferimento dalla letteratura |

Entrambe cercano il più piccolo tempo ciclo fattibile partendo dal lower bound
(ricerca descritta in Scholl & Becker, 2006, sez. 4.2.1 e 5.1.3).
La saturazione delle stazioni è nata nello sviluppo del progetto come evoluzione
dell'euristica dei gruppi; una verifica sulla letteratura ha mostrato che coincide
con l'euristica di Hoffmann (vedi la docstring di `hoffmann.py`).

### Bound (`src/bounds.py`)

- **Lower bound:** LC1 (McNaughton, 1959), LC2 (Klein & Scholl, 1996) e LC3,
  basato sulle stazioni minime e massime di ogni task (Scholl, 1999), come
  descritti in Scholl & Becker (2006).
- **Upper bound iniziale:** soluzione greedy in ordine topologico.

## Istanze

Generate da `src/generator.py`, che controlla direttamente l'**order strength**
(OS, frazione di coppie di task ordinate dalle precedenze) aggiungendo archi
*u* → *v* con *u* < *v* finché si raggiunge l'obiettivo. Ogni istanza è
riproducibile: il seed dipende solo da configurazione, gruppo e indice.

Disegno sperimentale (`configs/design.json`), con fattori e livelli tratti da
Otto, Otto & Scholl (2013):

| Fattore | Livelli |
| --- | --- |
| Numero di task *n* | 50, 100 |
| Order strength | 0,2 (sparso), 0,6 (denso) |
| Task per stazione *n/m* | 3 (difficile), 6 (intermedio) |
| Tempi | interi uniformi in [1, 100] |

Gruppi aggiuntivi: OS 0,9; tempi bimodali (80% corti, 20% lunghi);
istanze facili con 10 task per stazione. **25 istanze per gruppo, 350 in totale.**

Nel SALBP-2 il tempo ciclo non è noto in anticipo, quindi non si possono generare
i tempi relativi al tempo ciclo come in Otto et al.; il numero medio di task per
stazione ne fa le veci (pochi task per stazione = task lunghi rispetto al ciclo =
istanze più difficili, come mostrato anche da Álvarez-Miranda et al., 2023).

## Installazione

Richiede **Python ≥ 3.10** e **Gurobi** con licenza.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

La licenza inclusa in `gurobipy` installato con pip è limitata (2000 variabili e
2000 vincoli): basta per i test, non per le istanze grandi. Per gli esperimenti
serve la licenza accademica gratuita di Gurobi.

## Uso

```bash
# test
python -m pytest

# generazione delle istanze (prova pilota e campagna completa)
python -m scripts.gen_instances --config configs/pilot.json  --out instances_pilot/
python -m scripts.gen_instances --config configs/design.json --out instances/

# esperimenti: prova pilota (60 s per modello PLI)
python -m scripts.run_experiments --manifest instances_pilot/manifest.csv \
    --out results/pilot.csv --time-limit 60

# esperimenti: campagna completa (300 s per modello PLI)
python -m scripts.run_experiments --manifest instances/manifest.csv \
    --out results/results.csv --time-limit 300
```

`run_experiments` scrive una riga per (istanza, metodo) appena il risultato è
pronto e, se rilanciato, salta le esecuzioni già presenti: si può interrompere e
riprendere. Con `--methods` si eseguono solo alcuni metodi, per esempio
`--methods hoffmann gruppi`.

### Risultati

Colonne principali di `results/*.csv`:

| Colonna | Significato |
| --- | --- |
| `status` | `optimal` (ottimo dimostrato), `feasible` (time limit con soluzione), `no_solution`, `infeasible`, `solver_error`, `error` |
| `objective` | carico massimo della soluzione trovata |
| `lower_bound` | miglior lower bound del metodo (combinatorio o del solver) |
| `gap` | (objective − lower_bound) / lower_bound |
| `time_s`, `build_s` | tempo totale e tempo di costruzione del modello |

L'analisi confronta ogni euristica con il miglior lower bound disponibile per
l'istanza (il massimo tra quelli di tutti i metodi), che coincide con l'ottimo
quando un PLI l'ha dimostrato.

## Note sulle scelte

- **Solver.** Il progetto è partito con HiGHS (open source). Durante i test,
  HiGHS 1.15.1 ha restituito risultati errati su due istanze piccole: in una ha
  dichiarato non ammissibile un modello ammissibile, nell'altra ha dichiarato
  ottima una soluzione che viola un vincolo. Il problema dipende dal presolve ed
  è stato segnalato agli sviluppatori: https://github.com/ERGO-Code/HiGHS/issues/3333.
  Si è quindi passati a Gurobi.
- **Verifica dei modelli.** I test (`tests/test_models.py`) confrontano ogni
  modello con l'ottimo calcolato per enumerazione completa su 120 istanze
  piccole. Ogni soluzione, di PLI ed euristiche, passa da un validatore
  indipendente (`src/solution.py`).
- **Ottimo dimostrato.** Lo stato `optimal` è assegnato solo se l'obiettivo
  coincide con il lower bound, indipendentemente da quanto dichiara il solver.

## Struttura

```
configs/            disegno sperimentale (design.json, pilot.json)
scripts/            generazione delle istanze ed esperimenti
src/
  instance.py       istanza e lettura/scrittura del formato .alb
  graph.py          chiusura e riduzione transitiva, order strength
  bounds.py         lower bound, upper bound, finestre di stazione
  solution.py       soluzione, validatore, esito di un metodo
  generator.py      generatore di istanze
  models/           modelli PLI
  heuristic/        euristiche
tests/              test (pytest)
instances*/         istanze generate (con manifest.csv)
results/            risultati degli esperimenti
```

## Riferimenti

- Álvarez-Miranda, E., Pereira, J., & Vilà, M. (2023). Analysis of the simple assembly line balancing problem complexity. *Computers & Operations Research*, 159.
- Bowman, E. H. (1960). Assembly-line balancing by linear programming. *Operations Research*, 8(3), 385–389.
- Hoffmann, T. R. (1963). Assembly line balancing with a precedence matrix. *Management Science*.
- Klein, R., & Scholl, A. (1996). Maximizing the production rate in simple assembly line balancing — A branch and bound procedure. *European Journal of Operational Research*, 91(2).
- McNaughton, R. (1959). Scheduling with deadlines and loss functions. *Management Science*, 6(1).
- Otto, A., Otto, C., & Scholl, A. (2013). Systematic data generation and test design for solution algorithms on the example of SALBPGen for assembly line balancing. *European Journal of Operational Research*, 228(1), 33–45.
- Patterson, J. H., & Albracht, J. J. (1975). Assembly-line balancing: zero-one programming with Fibonacci search. *Operations Research*, 23(1), 166–172.
- Ritt, M., & Costa, A. M. (2018). Improved integer programming models for simple assembly line balancing and related problems. *International Transactions in Operational Research*. DOI 10.1111/itor.12206.
- Scholl, A. (1999). *Balancing and Sequencing of Assembly Lines* (2ª ed.). Physica-Verlag.
- Scholl, A., & Becker, C. (2006). State-of-the-art exact and heuristic solution procedures for simple assembly line balancing. *European Journal of Operational Research*, 168(3), 666–693.
- White, W. W. (1961). Comments on a paper by Bowman. *Operations Research*, 9(2), 274–276.