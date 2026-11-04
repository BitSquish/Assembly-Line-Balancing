# Assembly Line Balancing (SALBP-2)

Progetto per il corso di AMOD (Algoritmi e Modelli per l'Ottimizzazione
Discreta): due modelli di programmazione lineare intera (PLI) e due euristiche
per il **Simple Assembly Line Balancing Problem di tipo 2**, confrontati su 1800
istanze generate pseudo-casualmente.

In breve:

- fino a 20 task i PLI chiudono tutte le istanze. Con tempi uniformi la quota
  scende all'84% a 50 task e al 27% a 200; con tempi bimodali resta all'81%
  anche a 200 task;
- con tempi uniformi la difficoltà dipende soprattutto dal numero di stazioni:
  si chiude il 95% delle istanze con poche stazioni e il 45% con tante;
- l'euristica di Hoffmann, adattata al SALBP-2, trova l'ottimo nell'80% (tempi
  uniformi) e nell'88% (bimodali) delle istanze chiuse dai PLI, in 0,1 secondi
  di media. A 200 task con tempi uniformi è migliore dei PLI in 139 istanze su
  225;
- nessuno dei due PLI domina l'altro: Ritt & Costa dimostra più ottimi con
  precedenze dense, Patterson & Albracht è competitivo con precedenze sparse.

## Il problema

Una linea di montaggio ha $`m`$ **stazioni in sequenza**. Ogni task $`i`$ ha un
tempo intero $`t_i`$ e va assegnato a una sola stazione; una precedenza
$`i \to j`$ impone che $`i`$ stia in una stazione uguale o precedente a quella
di $`j`$. Il carico di una stazione è la somma dei tempi dei suoi task.

**Obiettivo:** il numero di stazioni $`m`$ è dato; si cerca l'assegnamento dei
task che rende minimo il carico della stazione più carica. Questo carico si
chiama **tempo ciclo** $`c`$: è il tempo che ogni stazione ha a disposizione per
ogni pezzo, quindi la linea produce un pezzo ogni $`c`$ unità di tempo. Ridurre
$`c`$ significa aumentare la produttività.

Esempio: 3 stazioni con carichi 10, 12 e 9 danno $`c = 12`$, perché la seconda
stazione rallenta tutta la linea. Spostando un task da 2 unità dalla seconda
alla terza (se le precedenze lo permettono) i carichi diventano 10, 10 e 11 e
$`c`$ scende a 11.

## Metodi

### Lower bound (`src/bounds.py`)

Tutti i metodi usano lo stesso lower bound sul tempo ciclo, costruito sullo
schema dei bound LC1, LC2 e LC3 di Scholl & Becker (2006, sez. 4.1). Nelle
formule i tempi sono in ordine decrescente ($`t_1 \ge t_2 \ge \dots \ge t_n`$),
mentre $`P_i`$ e $`F_i`$ sono gli insiemi di tutti i predecessori e di tutti i
successori del task $`i`$, diretti e indiretti.

**Valore di partenza: LC1 e LC2** (`simple_lower_bound`). Il carico medio
(McNaughton, 1959) e il task più lungo danno

```math
c \;\ge\; \mathrm{LC1} = \max\left\{\, t_1,\; \left\lceil \frac{\sum_i t_i}{m} \right\rceil \right\}
```

Principio dei cassetti (Klein & Scholl, 1996): tra i $`k\,m+1`$ task più lunghi,
almeno $`k+1`$ stanno nella stessa stazione, quindi

```math
c \;\ge\; \mathrm{LC2} = \max_{k \ge 1} \; \sum_{h=0}^{k} t_{k m + 1 - h}
```

**Fase 1: LC3 con finestre semplici** (`window_lower_bound`; Patterson &
Albracht, 1975; Ritt & Costa, 2018, sez. 2.2). Con tempo ciclo $`c`$, il task
$`i`$ non può stare prima della stazione $`E_i(c)`$ né dopo la stazione
$`L_i(c)`$:

```math
E_i(c) = \left\lceil \frac{t_i + \sum_{h \in P_i} t_h}{c} \right\rceil
\qquad
L_i(c) = m + 1 - \left\lceil \frac{t_i + \sum_{h \in F_i} t_h}{c} \right\rceil
```

Partendo da $`\max(\mathrm{LC1}, \mathrm{LC2})`$ si alza $`c`$ finché
$`E_i(c) \le L_i(c)`$ per ogni task.

**Fase 2: LC3 con teste e code ricorsive** (`lower_bound`). Le somme dei tempi
di predecessori e successori trattano il lavoro come se si potesse dividere
liberamente tra le stazioni. La fase 2 le sostituisce con una testa $`a_i`$ e
una coda $`b_i`$ più grandi, calcolate come nel bound LM4 di Johnson (1988),
senza i bound di conteggio sui sottoproblemi. Per la coda si prendono tutti i
successori $`h_1, h_2, \dots`$ di $`i`$ in ordine di coda decrescente: i primi
$`k`$ vanno eseguiti tutti dopo $`i`$, e dopo l'ultimo di loro resta almeno la
sua coda.

```math
b_i \;\ge\; \max_k \Bigl( t_{h_1} + \dots + t_{h_k} + b_{h_k} \Bigr)
```

Il lavoro della coda occupa almeno $`\lceil b_i / c \rceil`$ stazioni in fondo
alla linea. Se nella prima di queste stazioni lo spazio libero è minore di
$`t_i`$, il task non ci entra e la coda sale al multiplo di $`c`$ successivo. La
testa si calcola allo stesso modo sui predecessori. Un valore di $`c`$ è escluso
se per qualche task

```math
\left\lceil \frac{a_i + t_i}{c} \right\rceil \;>\; m + 1 - \left\lceil \frac{t_i + b_i}{c} \right\rceil
\qquad \text{oppure} \qquad
a_i + t_i + b_i \;>\; m\,c
```

e si alza $`c`$, a partire dal valore della fase 1, finché nessun task viola il
test.

Ogni valore di $`c`$ scartato è irraggiungibile da qualsiasi soluzione, quindi il
risultato è un lower bound valido. La validità è verificata nei test contro
l'ottimo calcolato per enumerazione completa.

Nella campagna la fase 1 alza il valore di partenza in 139 istanze (68 uniformi,
71 bimodali) e la fase 2 lo alza ancora in 113 (60 uniformi, 53 bimodali). Sono
quasi tutte a OS 0,9: le precedenze dense allungano teste e code.

### Upper bound iniziale

`greedy_solution` scorre i task in ordine topologico e chiude una stazione appena
il suo carico raggiunge la media $`\sum_i t_i / m`$. La soluzione è sempre
ammissibile e il suo carico massimo è il $`\overline{c}`$ usato dai modelli PLI.
È volutamente semplice: nella campagna sta in media il 33% sopra la soluzione di
Hoffmann (vedi [Limiti](#limiti)).

### Modelli PLI (`src/models/`)

I due modelli condividono la parte di assegnamento. La variabile binaria
$`x_{is}`$ vale 1 se il task $`i`$ va nella stazione $`s`$, ed è creata solo per
le stazioni della finestra $`E_i \le s \le L_i`$ calcolata al tempo ciclo
massimo $`\overline{c}`$:

```math
\min\; c
\qquad
\sum_{s} x_{is} = 1 \quad \forall i
\qquad
\sum_{i} t_i\, x_{is} \le c \quad \forall s
\qquad
\underline{c} \le c \le \overline{c}
```

dove $`\underline{c}`$ è il lower bound e $`\overline{c}`$ l'upper bound
iniziale. I modelli differiscono nella formulazione delle precedenze; i nomi
seguono Ritt & Costa (2018, tab. 2). In entrambi i vincoli di precedenza si
scrivono solo sugli archi della riduzione transitiva del grafo.

**PA2-2, Patterson & Albracht (1975)** (`patterson_albracht.py`): un vincolo
per arco, che confronta l'indice delle due stazioni.

```math
\sum_{s} s\, x_{is} \;\le\; \sum_{s} s\, x_{js} \qquad \forall\, (i, j)
```

**NF4-2, Ritt & Costa (2018)** (`ritt_costa.py`): un vincolo per arco e per
stazione. Entro ogni stazione $`k`$, il task $`j`$ può essere già assegnato
solo se lo è anche $`i`$. Fuori dall'intervallo $`E_j \le k < L_i`$ il vincolo
è sempre soddisfatto e non viene scritto.

```math
\sum_{s \le k} x_{is} \;\ge\; \sum_{s \le k} x_{js} \qquad \forall\, (i, j),\; \forall\, k
```

Il tempo ciclo è rappresentato anche da variabili binarie $`r_t`$, una per ogni
valore $`t = \underline{c}, \dots, \overline{c}`$, con
$`\sum_t r_t = 1`$ e $`c = \sum_t t\, r_t`$. Le finestre di stazione dipendono
da $`t`$, e i tagli di Ritt & Costa (2018, eq. 24-25) vietano gli assegnamenti
fuori dalla finestra del tempo ciclo scelto:

```math
\sum_{u \le e} x_{iu} \;\le\; 1 - \sum_{t \,:\, e < E_i(t)} r_t
\qquad \forall\, i,\;\; E_i(\overline{c}) \le e < E_i(\underline{c})
```

```math
\sum_{u \ge l} x_{iu} \;\le\; 1 - \sum_{t \,:\, L_i(t) < l} r_t
\qquad \forall\, i,\;\; L_i(\underline{c}) < l \le L_i(\overline{c})
```

Da Patterson & Albracht (1975) vengono il vincolo di precedenza e le finestre di
stazione, che non dipendono dal tipo di problema. Ritt & Costa (2018) dimostrano
che la loro precedenza cumulata domina quella di Patterson & Albracht.

Il primo modello è il più compatto, il secondo ha il rilassamento lineare più
forte. Entrambi usano le stesse finestre di stazione, gli stessi bound e la
stessa riduzione transitiva, quindi il confronto misura la formulazione e non il
pre-processing. Dimensioni medie dei modelli a 200 task:

| | Patterson & Albracht | Ritt & Costa |
| --- | --- | --- |
| Vincoli di precedenza | 1 per arco | fino a $`m`$ per arco |
| Variabili aggiuntive | nessuna | $`r_t`$, una per valore di $`c`$ |
| Variabili | circa 5.150 | circa 5.230 |
| Vincoli, tempi uniformi / bimodali | 736 / 738 | 11.948 / 13.609 |
| Vincoli, tante / medie / poche stazioni | 765 / 731 / 716 | 23.775 / 9.552 / 5.009 |
| Vincoli, OS 0,2 / 0,6 / 0,9 | 710 / 798 / 704 | 15.539 / 13.341 / 9.457 |

I vincoli di Ritt & Costa crescono con il numero di stazioni e con la larghezza
delle finestre, che è massima quando le precedenze sono sparse.

I modelli sono scritti con PuLP e risolti con Gurobi.

### Euristiche (`src/heuristic/`)

| Euristica | File | Idea |
| --- | --- | --- |
| Gruppi (sviluppata nel progetto) | `groups.py` | raggruppa i task legati da precedenze, dispone i gruppi lungo la linea secondo il grafo dei gruppi e usa le foglie del grafo come riempitivi |
| Saturazione delle stazioni (Hoffmann, 1963, adattata al SALBP-2) | `hoffmann.py` | riempie ogni stazione con l'insieme di task disponibili che lascia il minimo tempo inutilizzato |

Entrambe cercano il più piccolo tempo ciclo ammissibile partendo dal lower
bound: per $`c`$ = LB, LB + 1, ... riempiono le $`m`$ stazioni una alla volta e
si fermano al primo $`c`$ con cui tutti i task trovano posto (schema descritto in
Scholl & Becker, 2006, sez. 4.2.1 e 5.1.3). Il ciclo esterno è lo stesso, quindi
il confronto tra le due misura solo il criterio di riempimento delle stazioni.

**Gruppi.** Le foglie (task senza successori) restano fuori dai gruppi e servono
da riempitivi. Gli altri task formano gruppi a ondate: ogni radice si unisce ai
figli i cui predecessori sono già tutti in un gruppo, gli altri aspettano
l'ondata successiva. I gruppi si dispongono per livello nel grafo dei gruppi
(crescente) e per costo (decrescente). A ogni passo si sceglie tra il primo
gruppo che entra nella stazione, eventualmente spezzato, e la foglia più lunga
disponibile, prendendo quello che porta il carico più vicino a $`c`$.

**Hoffmann.** A ogni stazione si sceglie, tra gli insiemi di task disponibili e
chiusi rispetto alle precedenze, quello con il carico più vicino a $`c`$ senza
superarlo. È un problema di tipo zaino con precedenze, risolto con una ricerca
in profondità con memoria degli insiemi visitati.

La saturazione delle stazioni è nata nello sviluppo del progetto come evoluzione
dell'euristica dei gruppi: portando all'estremo la regola "lasciare il minimo
spazio vuoto", i gruppi diventano superflui. Una verifica sulla letteratura ha
mostrato che il criterio coincide con quello di Hoffmann (1963), pensato per il
SALBP-1 e con enumerazione completa degli insiemi. La versione del progetto
aggiunge la ricerca sul tempo ciclo e un limite di 20.000 nodi per stazione.
Nella campagna il limite è scattato una sola volta, su
`n200_os0.2_r10_bimodal_22`, e la soluzione è comunque ottima (302 = lower
bound).

## Istanze

Generate da `src/generator.py`, che controlla direttamente l'**order strength**
(OS): la frazione di coppie di task il cui ordine è fissato dalle precedenze,
dirette o indirette.

```math
\mathrm{OS} = \frac{\text{coppie } (i, j) \text{ con } i \text{ predecessore, diretto o indiretto, di } j}{n(n-1)/2}
```

Il generatore aggiunge archi $`u \to v`$ con $`u < v`$, saltando quelli già
implicati, finché l'OS raggiunge l'obiettivo con tolleranza 0,02; in tutte le
1800 istanze l'OS ottenuta sta tra l'obiettivo e l'obiettivo + 0,02. È lo stesso
passo finale del generatore SALBPGen (Otto et al., 2013), che però costruisce
prima il grafo a stadi e può inserire catene e colli di bottiglia; il generatore
del progetto parte invece da un grafo vuoto. Ogni istanza è riproducibile: il
seed dipende solo dal seed di base, dal gruppo e dall'indice.

Disegno sperimentale (`configs/design.json`): fattoriale completo su quattro
fattori, **72 gruppi da 25 istanze, 1800 istanze**.

| Fattore | Livelli |
| --- | --- |
| Numero di task $`n`$ | 20, 50, 100, 200 |
| Order strength | 0,2 (sparso), 0,6 (medio), 0,9 (denso, quasi una catena) |
| Numero di stazioni $`m`$ | $`n/3`$ (tante), $`n/6`$ (medie), $`n/10`$ (poche), arrotondato |
| Tempi dei task | interi uniformi tra 1 e 100, oppure bimodali (80% tra 1 e 33, 20% tra 68 e 100) |

Da dove vengono le scelte:

- $`n`$ = 20, 50, 100, i livelli di OS e le 25 istanze per gruppo seguono
  Otto, Otto & Scholl (2013).
- $`n`$ = 200 è una scelta del progetto (Otto et al. arrivano a 1000 task).
  Álvarez-Miranda et al. (2023) osservano che i metodi esatti iniziano a
  fallire intorno ai 100 task: con 200 task e tempi uniformi i PLI chiudono il
  27% delle istanze (con tempi bimodali l'81%).
- Il numero di stazioni in proporzione a $`n`$ è una scelta del progetto. Otto
  et al. controllano la difficoltà attraverso i tempi dei task rispetto al tempo
  ciclo; nel SALBP-2 il tempo ciclo non è un dato, e il numero di stazioni ne fa
  le veci. Álvarez-Miranda et al. (2023) usano lo stesso parametro (numero
  atteso di task per stazione) e mostrano che l'impacchettamento dei task è la
  principale fonte di difficoltà: le istanze di Otto et al. ancora aperte hanno
  tutte circa due task per stazione.
- I tempi bimodali, con molti task brevi e pochi lunghi, riprendono la forma
  considerata da Otto et al. (2013) come tipica delle linee reali. La proporzione
  80/20 e gli intervalli sono una scelta del progetto.
- Otto et al. distinguono anche grafi con molte catene o colli di bottiglia;
  il progetto usa un solo tipo di grafo, senza questo controllo.

I nomi dei gruppi (per esempio `n50_os0.2_r3_uniform`) contengono i livelli dei
fattori ed entrano nel seed: rinominarli cambia le istanze.

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

# tabelle dei grafici delle slide
python -m scripts.grafici_slide --results results/results.csv \
    --out results/grafici_slide/

# istanza di esempio delle slide: bound, soluzioni e figure
python -m scripts.esempio --out results/esempio/
```

`run_experiments` scrive una riga per (istanza, metodo) appena il risultato è
pronto e, se rilanciato, salta le esecuzioni già presenti. Con `--methods` si
eseguono solo alcuni metodi, per esempio `--methods hoffmann gruppi`.

## Esperimenti

| Impostazione | Valore |
| --- | --- |
| Limite di tempo per modello PLI | 180 secondi |
| Solver | Gurobi tramite PuLP, 6 thread, `MIPGapAbs` = 0,999 |
| Esecuzione | in sequenza, un metodo alla volta |
| Macchina | AMD Ryzen 5 5500U (6 core), 8 GB di RAM |

`MIPGapAbs` sotto 1 è lecito perché l'ottimo è intero: quando la distanza
assoluta tra soluzione e bound scende sotto 1, il bound arrotondato per eccesso
coincide con la soluzione e l'ottimo è dimostrato.

Per ogni modello PLI si registra l'ottimo e il tempo, oppure, allo scadere del
limite, la miglior soluzione trovata (incumbent) e il lower bound. Ogni
euristica è confrontata con l'ottimo o, se l'ottimo non è noto, con il miglior
lower bound.

Tempi:

- il limite di 180 secondi vale per il solver. Il tempo riportato per i PLI
  comprende anche la costruzione del modello (colonna `build_s`), quindi può
  superare il limite: arriva al massimo a 207 secondi;
- il tempo dei PLI non comprende grafo, lower bound e soluzione greedy, calcolati
  alla creazione del modello in frazioni di secondo. Quello delle euristiche li
  comprende.

### Colonne dei risultati

`results/results.csv` ha una riga per istanza e metodo (7200 righe).

| Colonna | Significato |
| --- | --- |
| `instance`, `group`, `n`, `m`, `os`, `tasks_per_station`, `time_dist` | istanza e livelli dei fattori (`os` è l'order strength ottenuta) |
| `method`, `kind` | metodo (`patterson_albracht`, `ritt_costa`, `hoffmann`, `gruppi`) e tipo (`pli`, `euristica`) |
| `status` | `optimal` (ottimo dimostrato), `feasible` (limite di tempo, con soluzione), `no_solution`, `infeasible`, `solver_error`, `error` |
| `objective` | carico massimo della soluzione trovata; per un PLI fermato dal limite di tempo è l'incumbent |
| `lower_bound` | miglior lower bound del metodo (combinatorio o del solver) |
| `gap` | $`(\text{objective} - \text{lower\_bound}) / \text{lower\_bound}`$ |
| `time_s`, `build_s` | tempo totale e tempo di costruzione del modello |
| `n_vars`, `n_constraints` | dimensione del modello PLI |
| `extra` | per i PLI `c_min` e `c_max`; per le euristiche i tempi ciclo provati e, per Hoffmann, gli interventi del limite di nodi |

## Risultati

7200 esecuzioni, circa 48 ore di calcolo per i PLI (35 sulle istanze uniformi,
13 sulle bimodali). Tutte le esecuzioni sono terminate con una soluzione: nessun
errore, nessun PLI senza incumbent.

### Definizioni

| Termine | Significato |
| --- | --- |
| ottimo dimostrato da un metodo | la soluzione del metodo coincide con il suo lower bound |
| istanza chiusa dai PLI | almeno uno dei due PLI dimostra l'ottimo |
| miglior lower bound ($`\mathrm{LB}^*`$) | il massimo dei lower bound di tutti i metodi (ognuno è valido) |
| ottimo noto | la miglior soluzione tra tutti i metodi coincide con $`\mathrm{LB}^*`$; comprende anche le istanze in cui l'ottimo lo dimostra solo Hoffmann |
| istanza aperta | ottimo non noto |
| ottimo raggiunto | tra le istanze con ottimo noto (o chiuse dai PLI), quota in cui il metodo trova una soluzione ottima, anche senza poterlo dimostrare: è la misura giusta per le euristiche |
| scarto | $`(z - \mathrm{LB}^*) / \mathrm{LB}^*`$, con $`z`$ il valore trovato dal metodo; dove l'ottimo non è noto è un limite superiore alla distanza dall'ottimo |

Su 900 istanze per distribuzione, quelle chiuse dai PLI sono 628 con tempi
uniformi e 842 con tempi bimodali; quelle con ottimo noto 719 e 862.

### Riepilogo per metodo

Tempi uniformi (900 istanze):

| Metodo | Ottimi dimostrati | Ottimo raggiunto, istanze chiuse dai PLI (628) | Ottimo raggiunto, istanze con ottimo noto (719) | Scarto medio | Tempo medio |
| --- | --- | --- | --- | --- | --- |
| Patterson & Albracht | 575 (63,9%) | 95,1% | 83,0% | 0,53% | 71,6 s |
| Ritt & Costa | 600 (66,7%) | 95,7% | 83,6% | 0,61% | 68,3 s |
| Hoffmann | 405 (45,0%) | 79,5% | 82,1% | 0,66% | 0,11 s |
| Gruppi | 25 (2,8%) | 8,8% | 7,6% | 3,91% | 0,12 s |

Tempi bimodali (900 istanze):

| Metodo | Ottimi dimostrati | Ottimo raggiunto, istanze chiuse dai PLI (842) | Ottimo raggiunto, istanze con ottimo noto (862) | Scarto medio | Tempo medio |
| --- | --- | --- | --- | --- | --- |
| Patterson & Albracht | 816 (90,7%) | 97,6% | 95,4% | 0,16% | 25,8 s |
| Ritt & Costa | 828 (92,0%) | 98,3% | 96,1% | 0,11% | 27,4 s |
| Hoffmann | 598 (66,4%) | 88,1% | 88,4% | 0,21% | 0,11 s |
| Gruppi | 191 (21,2%) | 27,0% | 26,3% | 2,48% | 0,11 s |

Le due colonne dell'ottimo raggiunto vanno lette insieme. Le istanze con ottimo
noto comprendono 91 istanze uniformi e 20 bimodali in cui l'ottimo è noto solo
perché Hoffmann ha raggiunto il lower bound: lì i PLI, per costruzione, non
l'hanno trovato. Su quell'insieme Hoffmann sembra alla pari dei PLI (82% contro
83–84% con tempi uniformi). Il confronto alla pari è sulle istanze chiuse dai
PLI: Hoffmann trova l'ottimo nell'80% (uniformi) e nell'88% (bimodali) dei casi,
contro il 95–98% dei PLI, in 0,1 secondi invece di 26–72.

### Dimensione delle istanze

| Task | Uniformi: chiuse dai PLI | Uniformi: ottimo noto | Uniformi: tempo medio PLI | Bimodali: chiuse dai PLI | Bimodali: ottimo noto | Bimodali: tempo medio PLI |
| --- | --- | --- | --- | --- | --- | --- |
| 20 | 225 | 225 | 0,1 s | 225 | 225 | < 0,1 s |
| 50 | 189 | 189 | 36,7 s | 222 | 222 | 5,8 s |
| 100 | 154 | 173 | 83,7 s | 213 | 214 | 16,9 s |
| 200 | 60 | 132 | 159,3 s | 182 | 201 | 83,5 s |

Ogni riga è su 225 istanze; il tempo è la media dei due PLI. Con tempi uniformi
a 200 task i PLI chiudono il 27% delle istanze; considerando anche Hoffmann
l'ottimo è noto nel 59%.

### Cosa rende difficile un'istanza

Percentuale di istanze chiuse per numero di stazioni:

| Stazioni | Uniformi: chiuse dai PLI | Uniformi: ottimo noto | Bimodali: chiuse dai PLI | Bimodali: ottimo noto |
| --- | --- | --- | --- | --- |
| tante ($`n/3`$) | 45% | 49% | 91% | 92% |
| medie ($`n/6`$) | 69% | 92% | 89% | 96% |
| poche ($`n/10`$) | 95% | 99% | 100% | 100% |

e per order strength:

| OS | Uniformi: chiuse dai PLI | Bimodali: chiuse dai PLI |
| --- | --- | --- |
| 0,2 | 66% | 94% |
| 0,6 | 63% | 94% |
| 0,9 | 80% | 92% |

- Con tempi uniformi il fattore decisivo è il numero di stazioni. Con poche
  stazioni ci sono molte combinazioni per riempirle e il lower bound si
  raggiunge facilmente; con tante stazioni (circa 3 task ciascuna)
  l'impacchettamento è rigido.
- La differenza tra "chiuse dai PLI" e "ottimo noto" mostra due modi diversi di
  restare aperti:
  - con stazioni medie o poche il lower bound è già quello giusto: al PLI manca
    la soluzione entro 180 secondi, e Hoffmann la trova;
  - con tante stazioni né i PLI né Hoffmann raggiungono il lower bound, che
    probabilmente è debole (vedi [Istanze aperte](#istanze-aperte-e-lower-bound)).
- Con tempi uniformi le istanze dense (OS 0,9) sono le più facili: le finestre
  di stazione si restringono. Con tempi bimodali l'OS conta poco.

### Più tempo non basta

Istanze chiuse dai PLI se il limite di tempo fosse stato più basso (tempo del
solver, senza la costruzione del modello; `results/grafici_slide/chiusura_per_tempo_limite.csv`):

| Tempi | 60 s | 90 s | 120 s | 150 s | 180 s |
| --- | --- | --- | --- | --- | --- |
| Uniformi | 585 | 609 | 620 | 624 | 628 |
| Bimodali | 799 | 813 | 824 | 837 | 842 |

Tra 120 e 180 secondi si chiudono solo 8 istanze uniformi e 18 bimodali in più:
un limite più lungo cambierebbe poco le conclusioni.

### Patterson & Albracht contro Ritt & Costa

Ottimi dimostrati su 300 istanze per livello di OS:

| OS | PA, uniformi | RC, uniformi | PA, bimodali | RC, bimodali |
| --- | --- | --- | --- | --- |
| 0,2 | 189 | 178 | 281 | 274 |
| 0,6 | 173 | 181 | 276 | 277 |
| 0,9 | 213 | 241 | 259 | 277 |

- Ritt & Costa dimostra l'ottimo in più istanze. Quelle chiuse da uno solo dei
  due modelli sono 53 per Ritt & Costa e 28 per Patterson & Albracht con tempi
  uniformi, 26 e 14 con tempi bimodali.
- Con precedenze dense (OS 0,9) vince Ritt & Costa: i vincoli cumulativi e i
  tagli sulle finestre escludono molte assegnazioni. Il caso estremo è il gruppo
  uniforme da 100 task con tante stazioni: 84% di ottimi contro 12%.
- Con precedenze sparse (OS 0,2) Patterson & Albracht è pari o migliore: i
  vincoli di Ritt & Costa servono a poco ma sono molti di più (circa 15.500
  contro 710 a 200 task). Nel gruppo uniforme da 200 task con poche stazioni:
  88% di ottimi contro 44%.
- Con tempi uniformi Patterson & Albracht trova più spesso la soluzione migliore
  (131 istanze contro 78); con tempi bimodali sono quasi pari (27 contro 32).

Nessuno dei due modelli domina: la scelta dipende dalla struttura delle
precedenze.

### Hoffmann contro i PLI

Istanze in cui Hoffmann è migliore / uguale / peggiore del migliore dei due PLI,
con il test dei ranghi con segno di Wilcoxon (Otto et al., 2013, sez. 6.1):

| Task | Uniformi | Bimodali |
| --- | --- | --- |
| 20 | 0 / 185 / 40 (p < 0,001) | 0 / 206 / 19 (p < 0,001) |
| 50 | 0 / 149 / 76 (p < 0,001) | 0 / 182 / 43 (p < 0,001) |
| 100 | 37 / 122 / 66 (p < 0,001) | 1 / 188 / 36 (p < 0,001) |
| 200 | 139 / 69 / 17 (p < 0,001) | 26 / 184 / 15 (p = 0,47) |

- Fino a 50 task Hoffmann non batte mai il miglior PLI.
- A 200 task con tempi uniformi è migliore in 139 istanze su 225, in 0,3 secondi
  contro i circa 160 dei PLI: i PLI si fermano al limite di tempo con soluzioni
  peggiori.
- A 200 task con tempi bimodali la differenza non è significativa; lo scarto
  medio è simile (0,19% Hoffmann, 0,22% il miglior PLI).

Hoffmann conviene quando i PLI non chiudono. Sulle istanze che nessun PLI chiude:

| Gruppo | Istanze | Hoffmann migliore / pari / peggiore | Gap miglior PLI | Gap Hoffmann | Hoffmann raggiunge $`\mathrm{LB}^*`$ |
| --- | --- | --- | --- | --- | --- |
| uniformi, tante stazioni | 165 | 75 / 20 / 70 | 2,25% | 2,37% | 11 |
| uniformi, stazioni medie | 92 | 88 / 4 / 0 | 0,64% | 0,12% | 67 |
| uniformi, poche stazioni | 15 | 13 / 2 / 0 | 0,20% | 0,03% | 13 |
| bimodali, tante stazioni | 26 | 6 / 8 / 12 | 1,77% | 2,11% | 1 |
| bimodali, stazioni medie | 32 | 21 / 10 / 1 | 0,58% | 0,28% | 19 |

I gap sono misurati rispetto al miglior lower bound. Con stazioni medie o poche
Hoffmann è migliore in 101 istanze uniformi su 107 e raggiunge il lower bound in
80: lì il bound era già l'ottimo, e ai PLI mancava il tempo per trovare la
soluzione. Con tante stazioni il confronto è sostanzialmente pari, e Hoffmann
raggiunge il bound solo in 11 istanze uniformi su 165.

Hoffmann raggiunge il miglior lower bound in 111 istanze che i PLI lasciano
aperte. In 110 lo dimostra da solo (90 uniformi, 20 bimodali), perché il suo
lower bound combinatorio coincide con la soluzione; nell'istanza restante il
bound che chiude è quello duale di un PLI.

### Hoffmann contro Gruppi

Hoffmann è migliore in 833 istanze uniformi e 671 bimodali, pari in 65 e 227,
peggiore in 2 per ciascuna distribuzione (Wilcoxon su tutte le 1800 istanze,
p < 0,001). Lo scarto medio è 0,66% contro 3,91% con tempi uniformi e 0,21%
contro 2,48% con tempi bimodali. Il ciclo esterno su $`c`$ è lo stesso, quindi
la differenza viene tutta dal criterio di riempimento delle stazioni.

### Istanze aperte e lower bound

Restano aperte 181 istanze uniformi (154 con tante stazioni, 25 medie, 2 poche;
gap medio tra miglior soluzione e miglior lower bound 1,6%) e 38 bimodali (25
con tante stazioni, 13 medie; gap medio 1,2%).

Con tante stazioni il lower bound combinatorio è probabilmente il limite. Tra le
istanze uniformi con ottimo noto, l'ottimo supera il lower bound combinatorio
nell'81% dei casi con tante stazioni (in media del 3,6%), contro il 26–34% con
stazioni medie o poche (`results/grafici_slide/bound_debole.csv`). Sulle istanze
uniformi aperte con tante stazioni il bound duale del solver supera quello
combinatorio solo nel 15% dei casi.

### Tempi uniformi e bimodali

Con tempi bimodali tutte le istanze sono più facili: i PLI chiudono 842 istanze
contro 628, in poco più di un terzo del tempo. Due effetti:

- **con tante stazioni il bound è il task più lungo.** Il tempo medio di un task
  bimodale è circa 30 (contro 50 per i tempi uniformi), quindi con circa 3 task
  per stazione il carico medio è circa 91, sotto il tempo del task più lungo
  (in media 97). Il tempo ciclo lo fissa quel task, e le altre stazioni hanno
  margine. Nel 75% delle istanze bimodali con tante stazioni il lower bound
  coincide con il tempo del task più lungo; con tempi uniformi, o con meno
  stazioni, non succede mai;
- **con stazioni medie o poche i task brevi riempiono gli spazi** lasciati da
  quelli lunghi, e il lower bound si raggiunge più spesso.

A parità di numero di stazioni le due distribuzioni danno quindi un carico
relativo diverso: il confronto tra uniformi e bimodali non è a parità di
difficoltà.

### Figure e tabelle

`results/figures_results/` (da `make_figures.py`) contiene le tabelle per
gruppo e metodo, i confronti appaiati con test di Wilcoxon e sei grafici in due
versioni (`_uniform` e `_bimodal`, con lo stesso asse verticale). Ogni grafico è
una griglia che segue il disegno: una colonna per numero di task, una riga per
OS e, in ogni pannello, un gruppo di barre per numero di stazioni.
`confronto_distribuzioni.png` confronta direttamente uniformi e bimodali. In
questi file "istanze chiuse" e "ottimo raggiunto" sono calcolati sulle istanze
con ottimo noto (vedi [Definizioni](#definizioni)).

`results/grafici_slide/` (da `grafici_slide.py`) contiene le tabelle dei grafici
delle slide, con la virgola decimale e il separatore ";". Qui "chiusa"
significa chiusa dai PLI.

## Storia della campagna

La campagna sulle istanze uniformi è stata eseguita prima con il lower bound
della sola fase 1. L'analisi dei risultati ha mostrato che a OS 0,9 quel bound
era debole: tra le istanze con ottimo noto coincideva con l'ottimo solo nel 14%
dei casi, contro il 92% a OS 0,2. È stata quindi aggiunta la fase 2.

Il bound entra nei metodi solo come valore (estremo inferiore di $`c`$ nei PLI,
punto di partenza della ricerca nelle euristiche), quindi sono state rieseguite
solo le esecuzioni interessate (`scripts/rerun_bound.py`):

- tutte le euristiche, perché il loro tempo include il calcolo del bound;
- i PLI sulle 60 istanze uniformi in cui il bound cambia, tutte a OS 0,9.

Le soluzioni delle euristiche sono rimaste identiche e i PLI rieseguiti hanno
dato gli stessi ottimi. Il nuovo bound non chiude nessuna istanza aperta: le 60
istanze erano già chiuse dai PLI. Cambia la capacità delle euristiche di
certificare da sole l'ottimo: Hoffmann passa da 388 a 405 istanze, Gruppi da 15
a 25. I risultati della prima esecuzione e l'elenco delle istanze cambiate sono
in `results/storico/`.

I tempi bimodali sono stati aggiunti dopo, già con il bound completo: prima a
100 task e poi, visto che cambiavano molto la difficoltà, su tutto il disegno.

## Verifiche della correttezza

- **Enumerazione completa.** I test (`tests/test_models.py`) confrontano ogni
  modello PLI con l'ottimo calcolato per enumerazione completa su 120 istanze
  piccole (7 task, da 2 a 4 stazioni). Sulle stesse istanze si verifica che le
  euristiche diano soluzioni ammissibili e mai sotto l'ottimo, e che i lower
  bound non lo superino mai.
- **Validatore indipendente.** Ogni soluzione, di PLI ed euristiche, passa da un
  validatore (`src/solution.py`) che ricontrolla da zero stazioni e precedenze.
- **Ottimo dimostrato.** Lo stato `optimal` è assegnato solo se l'obiettivo
  coincide con il lower bound, indipendentemente da quanto dichiara il solver.
  Vale anche per le euristiche: se la soluzione raggiunge il lower bound
  combinatorio, è ottima.
- **Coerenza dei risultati.** In nessuna istanza il lower bound di un metodo
  supera la soluzione di un altro (`make_figures.py` si ferma con un errore se
  succede), quindi gli ottimi dichiarati da metodi diversi coincidono sempre.
- **Riproducibilità.** Rigenerando le 1800 istanze dal seed si ottengono file
  identici byte per byte a quelli in `instances/`.

## Limiti

- **Upper bound iniziale largo.** I PLI ricevono solo l'istanza e il limite di
  tempo: nessun upper bound dalle euristiche, così PLI ed euristiche restano
  indipendenti. Il prezzo è un $`\overline{c}`$ della soluzione greedy, in media
  il 33% sopra la soluzione di Hoffmann. L'intervallo di $`c`$ copre in media
  60–77 valori, e pesa soprattutto su Ritt & Costa (una variabile $`r_t`$ per
  valore e finestre più larghe, quindi più vincoli).
- **Finestre dei modelli semplici.** Il lower bound usa teste e code ricorsive
  nella fase 2, ma le finestre $`E_i, L_i`$ dei modelli PLI sono calcolate con le
  somme semplici di predecessori e successori, uguali per i due modelli.
- **Bound semplificato.** La fase 2 non usa i bound di conteggio sui
  sottoproblemi di LM4, né i bound più forti della letteratura (per esempio LC4,
  Scholl & Becker, 2006, sez. 4.1).
- **Generatore.** Un solo tipo di grafo, senza il controllo di catene e colli di
  bottiglia di SALBPGen.
- **Contesto.** Un PLI con solver generico e 3 minuti non compete con i
  branch-and-bound specializzati, che sulle istanze di letteratura da 100 task
  lasciano aperte pochissime istanze (Álvarez-Miranda et al., 2023). Lo scopo è
  confrontare le formulazioni tra loro e con le euristiche.

## Perché Gurobi

Il progetto è partito con HiGHS (open source). Durante i test, HiGHS 1.15.1 ha
restituito risultati errati su due istanze piccole: in una ha dichiarato non
ammissibile un modello ammissibile, nell'altra ha dichiarato ottima una
soluzione che viola un vincolo. Il problema dipende dal presolve ed è stato
segnalato agli sviluppatori: https://github.com/ERGO-Code/HiGHS/issues/3333. Si
è quindi passati a Gurobi. I file per riprodurre il problema sono in
`highs_bug_report/`.

## Struttura

```
configs/              disegno sperimentale (design.json)
scripts/
  gen_instances.py    generazione delle istanze e del manifest
  run_experiments.py  esecuzione dei metodi sulle istanze
  make_figures.py     tabelle e grafici dai risultati
  grafici_slide.py    tabelle per i grafici delle slide
  esempio.py          istanza di esempio delle slide: bound, soluzioni e figure
  rerun_bound.py      storico: riesecuzione e verifica dopo il cambio di lower bound
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
  figures_results/    tabelle e grafici (make_figures.py)
  grafici_slide/      tabelle dei grafici delle slide (grafici_slide.py)
  esempio/            figure dell'istanza di esempio (esempio.py)
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
