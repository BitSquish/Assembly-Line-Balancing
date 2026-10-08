# Assembly Line Balancing (SALBP-2)

Progetto per il corso di AMOD: due modelli di programmazione lineare intera e due
euristiche per il **Simple Assembly Line Balancing Problem di tipo 2**, confrontati
su 900 istanze generate pseudo-casualmente.

## Il problema

Una linea di montaggio ha **m stazioni in sequenza**. Ogni task *i* ha un tempo
*tᵢ* e va assegnato a una sola stazione; le precedenze (*i* → *j*) impongono che
*i* stia in una stazione uguale o precedente a quella di *j*. Il carico di una
stazione è la somma dei tempi dei suoi task.

**Obiettivo:** dato *m*, minimizzare il carico massimo di stazione *c* (il tempo
ciclo della linea). Esempio: con carichi 10, 12 e 9 il valore della soluzione è 12.

## Metodi

### Bound (`src/bounds.py`)

**Lower bound**, usato da tutti i metodi, calcolato in tre passi:

1. **Bound combinatori:** carico medio ⌈Σ tᵢ / m⌉ (LC1) e principio dei cassetti
   sui task più lunghi (LC2): tra i *k·m* + 1 task più lunghi, almeno *k* + 1
   stanno nella stessa stazione.
2. **Finestre di stazione semplici:** per un tempo ciclo *c*, il task *i* non può
   stare prima della stazione E_i(c) = ⌈(tᵢ + tempi di tutti i predecessori) / c⌉
   né dopo L_i(c) = m + 1 − ⌈(tᵢ + tempi di tutti i successori) / c⌉. Si alza *c*
   finché tutte le finestre sono non vuote.
3. **Teste e code ricorsive** (Johnson, 1988): le stesse finestre, calcolate con
   un limite più stretto sul tempo che deve precedere e seguire ogni task. Si
   alza *c* finché nessun task viola il test.

Ogni valore di *c* scartato è irraggiungibile da qualsiasi soluzione, quindi il
risultato è un lower bound valido. La validità è verificata nei test contro
l'ottimo calcolato per enumerazione completa.

**Upper bound iniziale:** soluzione greedy in ordine topologico. Serve solo a
fissare l'intervallo di *c* e le finestre di stazione dei modelli.

Il lower bound riportato per un modello PLI è il massimo tra il bound
combinatorio e quello restituito dal solver.

### Modelli PLI (`src/models/`)

I due modelli condividono le variabili *x[i, s]* (task *i* nella stazione *s*),
le finestre di stazione e i bound su *c*. Differiscono nella formulazione delle
precedenze, secondo la classificazione di Ritt & Costa (2018).

| Modello | File | Precedenze per l'arco (*i*, *j*) |
| --- | --- | --- |
| Patterson & Albracht (1975) | `patterson_albracht.py` | Σₛ s·x[i,s] ≤ Σₛ s·x[j,s]: un vincolo per arco |
| Ritt & Costa (2018) | `ritt_costa.py` | Σ_{s≤k} x[i,s] ≥ Σ_{s≤k} x[j,s] per ogni stazione k, più variabili sul tempo ciclo e tagli sulle finestre di stazione |

Il primo è la formulazione più compatta, il secondo quella con il rilassamento
lineare più forte. Entrambi usano le stesse finestre di stazione, gli stessi
bound e la riduzione transitiva degli archi, quindi il confronto misura la
formulazione e non il pre-processing. Con 200 task, Patterson & Albracht ha in
media circa 740 vincoli, Ritt & Costa circa 12.000.

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
dirette o indirette. Il generatore aggiunge archi *u* → *v* con *u* < *v* finché
l'OS raggiunge l'obiettivo (tolleranza 0,02). 
È lo stesso passo finale del generatore SALBPGen (Otto et al., 2013), che però
costruisce prima il grafo a stadi e può inserire catene e colli di bottiglia;
il generatore del progetto parte invece da un grafo vuoto.
Ogni istanza è riproducibile: il seed dipende solo dal seed di base, dal gruppo e dall'indice.

Disegno sperimentale (`configs/design.json`): fattoriale completo su tre fattori,
**25 istanze per combinazione, 36 combinazioni, 900 istanze**.

| Fattore | Livelli |
| --- | --- |
| Numero di task *n* | 20, 50, 100, 200 |
| Order strength | 0,2 (grafo sparso), 0,6 (denso), 0,9 (quasi una catena) |
| Numero di stazioni *m* | *n*/3 (tante), *n*/6 (medie), *n*/10 (poche) |

Da dove vengono le scelte:

- *n* = 20, 50, 100, i livelli di OS e le 25 istanze per combinazione seguono
  Otto, Otto & Scholl (2013).
- *n* = 200 è una scelta del progetto (Otto et al. arrivano a 1000 task).
- I tempi dei task, interi uniformi tra 1 e 100, sono una scelta del progetto.
- Il numero di stazioni in proporzione a *n* è una scelta del progetto. Otto et al.
  controllano la difficoltà attraverso i tempi dei task rispetto al tempo ciclo;
  nel SALBP-2 il tempo ciclo non è un dato, e il numero di stazioni ne fa le veci.
  Álvarez-Miranda et al. (2023) usano lo stesso parametro (numero atteso di task
  per stazione) e mostrano che l'impacchettamento dei task è la principale fonte
  di difficoltà: le istanze di Otto et al. ancora aperte hanno tutte circa due
  task per stazione.
- Otto et al. distinguono anche grafi con molte catene o colli di bottiglia;
  il progetto usa un solo tipo di grafo, senza questo controllo.

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

Il limite di tempo vale per la sola risoluzione; il tempo riportato per i PLI
comprende anche la costruzione del modello (colonna `build_s`), quello delle
euristiche anche la costruzione del grafo e il calcolo del lower bound.

### Storia della campagna

La campagna è stata eseguita prima con il lower bound dei passi 1 e 2. L'analisi
dei risultati ha mostrato che a OS 0,9 quel bound era debole: coincideva con
l'ottimo solo nel 14% delle istanze chiuse, contro il 92% a OS 0,2. È stato
quindi aggiunto il passo 3.

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

3600 esecuzioni, circa 35 ore di calcolo per i PLI. Nessuna esecuzione è terminata
senza soluzione. L'ottimo è noto, cioè dimostrato da almeno un metodo, in
**719 istanze su 900** (225 a 20 task, 189 a 50, 173 a 100, 132 a 200).

| Metodo | Ottimi dimostrati | Ottimo raggiunto | Scarto dal miglior LB | Tempo medio |
| --- | --- | --- | --- | --- |
| Patterson & Albracht | 575 (64%) | 83% | 0,53% | 71,6 s |
| Ritt & Costa | 600 (67%) | 84% | 0,61% | 68,3 s |
| Hoffmann | 405 (45%) | 82% | 0,66% | 0,11 s |
| Gruppi | 25 (3%) | 8% | 3,91% | 0,12 s |

- **Ottimi dimostrati:** istanze in cui il metodo, da solo, trova una soluzione
  uguale al proprio lower bound.
- **Ottimo raggiunto:** tra le 719 istanze con ottimo noto, quota in cui il metodo
  trova una soluzione ottima, anche senza poterlo dimostrare. È la misura giusta
  per le euristiche.
- **Scarto dal miglior LB:** (obiettivo − miglior lower bound dell'istanza) /
  miglior lower bound, su tutte le 900 istanze. Dove l'ottimo non è noto è un
  limite superiore alla distanza dall'ottimo.

Osservazioni:

- **Difficoltà.** Il fattore decisivo è il numero di stazioni: le istanze chiuse
  sono il 49% con tante stazioni, il 92% con stazioni medie e il 99% con poche.
  I PLI chiudono tutte le istanze da 20 task e il 19-20% di quelle da 200.
- **Patterson & Albracht contro Ritt & Costa.** Ritt & Costa dimostra l'ottimo in
  più istanze (53 chiuse solo da Ritt & Costa, 28 solo da Patterson & Albracht),
  con il vantaggio maggiore a OS 0,9. Patterson & Albracht trova più spesso la
  soluzione migliore (131 istanze contro 78).
- **Hoffmann contro il miglior PLI** (istanze in cui Hoffmann è migliore / uguale /
  peggiore):

  | Task | Migliore | Uguale | Peggiore |
  | --- | --- | --- | --- |
  | 20 | 0 | 185 | 40 |
  | 50 | 0 | 149 | 76 |
  | 100 | 37 | 122 | 66 |
  | 200 | 139 | 69 | 17 |

  Fino a 50 task i PLI sono sempre almeno pari; a 200 task Hoffmann è migliore
  nella maggior parte delle istanze (test di Wilcoxon, p < 0,001), in circa 0,3
  secondi contro 180. Dimostra da solo l'ottimo in 90 istanze in cui nessun PLI
  ci riesce.
- **Gruppi contro Hoffmann.** Hoffmann è migliore in 833 istanze, uguale in 65,
  peggiore in 2.
- **Istanze aperte.** Restano 181 istanze senza ottimo dimostrato, con un gap
  medio dell'1,6% tra miglior soluzione e miglior lower bound.

Tabelle e grafici completi sono in `results/figures_results/`. I grafici sono
griglie di pannelli che seguono il disegno: una colonna per numero di task, una
riga per order strength e, dentro ogni pannello, un gruppo di barre per numero
di stazioni.

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

- Álvarez-Miranda, E., Pereira, J., & Vilà, M. (2023). Analysis of the simple assembly line balancing problem complexity. *Computers & Operations Research*, 159, 106323.- Hoffmann, T. R. (1963). Assembly line balancing with a precedence matrix. *Management Science*, 9(4).
- Johnson, R. V. (1988). Optimally balancing large assembly lines with "FABLE". *Management Science*, 34(2).
- Klein, R., & Scholl, A. (1996). Maximizing the production rate in simple assembly line balancing — A branch and bound procedure. *European Journal of Operational Research*, 91(2).
- McNaughton, R. (1959). Scheduling with deadlines and loss functions. *Management Science*, 6(1).
- Otto, A., Otto, C., & Scholl, A. (2013). Systematic data generation and test design for solution algorithms on the example of SALBPGen for assembly line balancing. *European Journal of Operational Research*, 228(1), 33–45.
- Patterson, J. H., & Albracht, J. J. (1975). Assembly-line balancing: zero-one programming with Fibonacci search. *Operations Research*, 23(1), 166–172.
- Ritt, M., & Costa, A. M. (2018). Improved integer programming models for simple assembly line balancing and related problems. *International Transactions in Operational Research*. DOI 10.1111/itor.12206.
- Scholl, A., & Becker, C. (2006). State-of-the-art exact and heuristic solution procedures for simple assembly line balancing. *European Journal of Operational Research*, 168(3), 666–693.