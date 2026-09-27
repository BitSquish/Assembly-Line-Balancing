"""Soluzione, validatore ed esito di un metodo risolutivo.

Stazioni numerate 1..m, come nei paper e in bounds.py; task 0-based come in
ALBInstance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .instance import ALBInstance


@dataclass(frozen=True, slots=True, repr=False)
class Solution:
    """Assegnamento dei task alle stazioni.

    stations[i] = stazione (1..m) a cui è assegnato il task i.
    Carichi e carico massimo si calcolano una volta sola alla costruzione.
    La soluzione NON viene validata qui: una soluzione non ammissibile deve
    poter esistere, altrimenti il validatore non avrebbe niente da rifiutare.
    """

    instance: ALBInstance
    stations: tuple[int, ...]
    loads: tuple[int, ...] = field(init=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "stations", tuple(int(s) for s in self.stations))
        if len(self.stations) != self.instance.n_tasks:
            raise ValueError(
                f"{self.instance.name}: {len(self.stations)} assegnamenti "
                f"per {self.instance.n_tasks} task"
            )
        loads = [0] * self.instance.m_stations
        for i, s in enumerate(self.stations):
            if 1 <= s <= self.instance.m_stations:
                loads[s - 1] += self.instance.task_times[i]
        object.__setattr__(self, "loads", tuple(loads))

    @property
    def max_load(self) -> int:
        """Il valore della funzione obiettivo: il tempo ciclo realizzato."""
        return max(self.loads)

    def __repr__(self) -> str:
        return f"Solution({self.instance.name!r}, max_load={self.max_load}, loads={self.loads})"


def violations(solution: Solution) -> list[str]:
    """Elenco dei vincoli violati; lista vuota se la soluzione è ammissibile.

    Controlla tutto da zero, senza fidarsi di chi ha prodotto la soluzione:
    è il controllo comune a PLI ed euristica.
    """
    inst = solution.instance
    m = inst.m_stations
    errors: list[str] = []
    for i, s in enumerate(solution.stations):
        if not 1 <= s <= m:
            errors.append(f"task {i}: stazione {s} fuori da 1..{m}")
    for u, v in inst.precedences:
        if solution.stations[u] > solution.stations[v]:
            errors.append(
                f"precedenza ({u}, {v}) violata: stazione "
                f"{solution.stations[u]} > {solution.stations[v]}"
            )
    return errors


def is_feasible(solution: Solution) -> bool:
    return not violations(solution)


# ------------------------------------------------------------------ esito


class Status(Enum):
    OPTIMAL = "optimal"          # ottimo dimostrato
    FEASIBLE = "feasible"        # time limit scaduto, con incumbent
    NO_SOLUTION = "no_solution"  # time limit scaduto, senza incumbent
    INFEASIBLE = "infeasible"    # il modello non ha soluzione (non dovrebbe capitare)


@dataclass(frozen=True, slots=True, repr=False)
class SolveResult:
    """Una riga dei risultati: un metodo su un'istanza.

    È il formato comune per i due PLI e per l'euristica, così la campagna
    di esperimenti li tratta tutti allo stesso modo.
    """

    method: str
    instance_name: str
    status: Status
    objective: int | None          # carico massimo della soluzione trovata
    lower_bound: int | None        # miglior lower bound noto
    time_s: float
    solution: Solution | None = field(default=None, compare=False)
    extra: dict = field(default_factory=dict, compare=False)

    @property
    def gap(self) -> float | None:
        """(obiettivo - lower bound) / lower bound; 0 se ottimo dimostrato."""
        if self.objective is None or not self.lower_bound:
            return None
        return (self.objective - self.lower_bound) / self.lower_bound

    def __repr__(self) -> str:
        return (
            f"SolveResult({self.method}, {self.instance_name}, {self.status.value}, "
            f"obj={self.objective}, lb={self.lower_bound}, t={self.time_s:.2f}s)"
        )