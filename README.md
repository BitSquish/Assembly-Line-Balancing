# Assembly Line Balancing

Due modelli di programmazione lineare intera e un'euristica per il Simple
Assembly Line Balancing Problem di tipo 2: dato il numero di stazioni,
minimizzare il carico massimo di stazione.

> Stato: scheletro. Le classi sono definite con le rispettive responsabilità,
> l'implementazione è in corso.

## Struttura

| Percorso | Contenuto |
| --- | --- |
| `src/instance.py` | dati di un'istanza e I/O sul formato `.alb` |
| `src/graph.py` | chiusura e riduzione transitiva, order strength |
| `src/solution.py` | soluzione e validatore |
| `src/bounds.py` | lower bound e finestre di stazione |
| `src/generator.py` | generazione pseudo-casuale con order strength controllata |
| `src/models/` | i due modelli PLI, con interfaccia comune |
| `src/heuristic/` | regole di priorità, costruzione greedy, ricerca locale |
| `src/experiments/` | esperimenti e scrittura dei risultati |

## Installazione

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Riproduzione dei risultati

```bash
python -m scripts.gen_instances   --config configs/design.yaml --out instances/
python -m scripts.run_experiments --instances instances/ --out results/raw/results.csv
python -m scripts.make_figures    --results results/raw/results.csv --out results/figures/
```