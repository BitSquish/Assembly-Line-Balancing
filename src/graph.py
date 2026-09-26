"""Precomputazioni sul grafo delle precedenze.

Il grafo diretto (N, E) di un'istanza SALBP è aciclico per definizione del
problema: le precedenze impongono un ordine parziale sulle operazioni, e un
ciclo renderebbe l'istanza inammissibile in partenza. ALBInstance non lo
verifica: la verifica richiede comunque di calcolare un ordinamento topologico, 
quindi la si fa una volta sola qui e la si riusa.

Le operazioni esposte da questa classe sono tutte ricorrenti in letteratura
e servono a valle di questo modulo:
    - chiusura transitiva  -> bound di stazione E_i, L_i (Ritt & Costa, 2015,
      sez. 2.2) e regola di priorità MaxCPW (Scholl & Becker, 2006, tab. 8);
    - riduzione transitiva -> elimina archi ridondanti nei vincoli di
      precedenza dei modelli PLI (un arco deducibile da altri due non va
      duplicato come vincolo);
    - order strength       -> misura di densità del grafo usata per classificare
      le istanze generate. ALBInstance.save() la scrive nel file .alb solo se è
      presente in instance.meta["order_strength"]: è compito del generatore
      calcolarla qui e inserirla in meta.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from .instance import ALBInstance


@dataclass(frozen=True, slots=True, repr=False)
class PrecedenceGraph:
    """Vista precomputata sulle precedenze di una ALBInstance.

    frozen=True e slots=True per lo stesso motivo di ALBInstance: è un
    oggetto derivato, riusato su tutta una campagna di esperimenti, e non
    deve poter essere modificato per errore.

    Nota implementativa: slots=True elimina il __dict__ dell'istanza, quindi
    functools.cached_property (che richiede __dict__ per memorizzare il
    valore) non è utilizzabile qui. Per questo chiusura, riduzione e
    ordinamento topologico sono calcolati tutti una volta sola in
    __post_init__, con lo stesso spirito della deduplica fatta in
    ALBInstance.__post_init__, invece che lazy alla prima richiesta.
    """

    instance: ALBInstance
    _digraph: nx.DiGraph = field(init=False, repr=False, compare=False)
    _closure: nx.DiGraph = field(init=False, repr=False, compare=False)
    _reduction: tuple[tuple[int, int], ...] = field(init=False, repr=False, compare=False)
    _topological_order: tuple[int, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        g = nx.DiGraph()
        g.add_nodes_from(range(self.instance.n_tasks))
        g.add_edges_from(self.instance.precedences)

        # Qui perché richiede l'ordinamento topologico:
        if not nx.is_directed_acyclic_graph(g):
            cycle = nx.find_cycle(g)
            raise ValueError(
                f"{self.instance.name}: il grafo delle precedenze contiene un "
                f"ciclo ({cycle}); un'istanza SALBP deve essere aciclica"
            )

        object.__setattr__(self, "_digraph", g)
        object.__setattr__(self, "_closure", nx.transitive_closure(g, reflexive=False))
        object.__setattr__(
            self, "_reduction", tuple(nx.transitive_reduction(g).edges())
        )
        object.__setattr__(
            self, "_topological_order", tuple(nx.topological_sort(g))
        )

    def __repr__(self) -> str:
        return (
            f"PrecedenceGraph({self.instance.name!r}, n={self.instance.n_tasks}, "
            f"|E|={self.instance.n_precedences}, OS={self.order_strength:.3f})"
        )

    # ------------------------------------------------------- struttura diretta

    def predecessors(self, i: int) -> frozenset[int]:
        """Predecessori diretti (immediati) del task i. P_i nella notazione
        di Scholl & Becker (2006, tab. 2)."""
        return frozenset(self._digraph.predecessors(i))

    def successors(self, i: int) -> frozenset[int]:
        """Successori diretti (immediati) del task i. F_i nella stessa notazione."""
        return frozenset(self._digraph.successors(i))

    # ------------------------------------------------------- chiusura transitiva

    def all_predecessors(self, i: int) -> frozenset[int]:
        """Tutti i predecessori, diretti e indiretti, di i (P*_i)."""
        return frozenset(self._closure.predecessors(i))

    def all_successors(self, i: int) -> frozenset[int]:
        """Tutti i successori, diretti e indiretti, di i (F*_i)."""
        return frozenset(self._closure.successors(i))

    def precedes(self, i: int, j: int) -> bool:
        """True se i deve stare in una stazione <= quella di j, direttamente
        o per transitività (i.e. i <= j nell'ordine parziale)."""
        return i == j or self._closure.has_edge(i, j)

    # ------------------------------------------------------- riduzione transitiva

    @property
    def reduction(self) -> tuple[tuple[int, int], ...]:
        """Il minimo insieme di archi che genera la stessa chiusura transitiva.

        Un arco (i, j) è ridondante se esiste già un cammino i -> ... -> j di
        lunghezza >= 2: rimuoverlo non cambia l'ordine parziale rappresentato,
        ma nei modelli PLI toglie una riga di vincolo per ogni arco ridondante
        (si veda instance.py: lo stesso principio applicato alla deduplica).
        """
        return self._reduction

    # ------------------------------------------------------- ordinamento e metriche

    @property
    def topological_order(self) -> tuple[int, ...]:
        """Un ordinamento topologico valido (ne esiste sempre almeno uno, essendo
        il grafo aciclico). Usato dalle procedure costruttive dell'euristica e
        dal calcolo dei bound di stazione."""
        return self._topological_order

    @property
    def order_strength(self) -> float:
        """OS = |E*| / (n(n-1)/2): frazione delle coppie ordinate di task il
        cui ordine relativo è fissato dalle precedenze, dirette o indirette.

        Definizione standard in letteratura ALBP (usata per classificare le
        istanze e riportata nel tag <order strength> dei file .alb di benchmark).
        """
        n = self.instance.n_tasks
        max_pairs = n * (n - 1) // 2
        if max_pairs == 0:
            return 0.0
        return self._closure.number_of_edges() / max_pairs