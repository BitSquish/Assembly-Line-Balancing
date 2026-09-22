"""Rappresentazione e I/O di un'istanza SALBP.

Convenzione:
    - indici 0-based in memoria (liste e tuple Python);
    - indici 1-based sul file .alb, come nei benchmark di letteratura.
La conversione avviene dentro save() e load().
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Un tag del formato .alb è una riga isolata del tipo "<task times>".
_TAG = re.compile(r"^<(.+)>$")


def _parse_sections(text: str) -> dict[str, list[str]]:
    """Spezza un file .alb in sezioni: nome del tag -> righe che lo seguono.

    È volutamente tollerante: un tag che non conosciamo non genera errore, finisce
    semplicemente nel dizionario e viene ignorato da chi legge. Serve perché i file
    di letteratura contengono blocchi che a noi non interessano (<order strength>,
    <number of stations per task>, ...) e un parser rigido non aprirebbe metà
    delle istanze pubbliche.
    """
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:                       # le righe vuote separano i blocchi
            continue
        if (match := _TAG.match(line)) is not None:
            current = match.group(1).strip().lower()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)

    return sections


@dataclass(frozen=True, slots=True, repr=False)
class ALBInstance:
    """Una singola istanza del problema.

    frozen=True: durante una campagna di centinaia di istanze
    un modello che modifica i dati falserebbe tutti i run successivi senza
    lasciare traccia. Così fallisce subito.

    slots=True elimina il __dict__ per istanza.

    repr=False perché il repr automatico stamperebbe mille tempi: inutilizzabile
    nel debugger e nei messaggi di errore. Si definisce uno compatto più sotto.

    Attributi:
        name:         identificativo, di norma il nome del file senza estensione.
        task_times:   tempo di ogni operazione, indicizzato 0-based.
        precedences:  archi diretti (i, j), "i su una stazione di indice <= quella di j".
        m_stations:   numero di stazioni. Dato di input nel SALBP-2.
        cycle_time:   presente nelle istanze SALBP-1 e nei file benchmark, dove è
                      il dato e il numero di stazioni è l'incognita. None altrimenti.
        meta:         parametri del generatore (seed, order strength, distribuzione).
    """

    name: str
    task_times: tuple[int, ...]
    precedences: tuple[tuple[int, int], ...]
    m_stations: int
    cycle_time: int | None = None

    # compare=False: il campo meta descrive COME l'istanza è stata prodotta, non
    # QUALE problema rappresenta. Senza questo, il test di round trip fallirebbe
    # sempre, perché load() aggiunge il percorso del file di provenienza.
    meta: dict = field(default_factory=dict, compare=False)

    # ------------------------------------------------------------------ derivati

    @property
    def n_tasks(self) -> int:
        """Numero di operazioni.

        Derivato e mai memorizzato: un campo n_tasks separato prima o poi si
        desincronizza da task_times, e il bug che ne segue è invisibile.
        """
        return len(self.task_times)

    @property
    def n_precedences(self) -> int:
        """Numero di archi diretti (dopo la deduplica fatta in __post_init__)."""
        return len(self.precedences)

    @property
    def total_time(self) -> int:
        """Somma dei tempi. Base di LB1 e dell'efficienza di linea."""
        return sum(self.task_times)

    # ------------------------------------------------------------- costruzione

    def __post_init__(self) -> None:
        """Normalizza i dati e verifica le invarianti.

        Non controlla l'aciclicità: è O(n + |E|) e richiede comunque l'ordinamento
        topologico, quindi appartiene a PrecedenceGraph, che lo calcola una volta
        sola e lo riusa.
        """
        # object.__setattr__ è l'unico modo di scrivere su una dataclass frozen.
        # È legittimo farlo qui, durante la costruzione, e soltanto qui: serve ad
        # accettare liste in ingresso e memorizzare comunque tuple, così l'istanza
        # è hashable e confrontabile senza che il chiamante debba pensarci.
        object.__setattr__(self, "task_times", tuple(int(t) for t in self.task_times))

        # dict.fromkeys deduplica preservando l'ordine. I file di benchmark ogni
        # tanto ripetono un arco, e ogni duplicato è una riga di vincolo sprecata
        # nel modello PLI: su |E|*m righe del modello 2 non è un dettaglio.
        deduped = dict.fromkeys((int(u), int(v)) for u, v in self.precedences)
        object.__setattr__(self, "precedences", tuple(deduped))

        n = self.n_tasks
        if n == 0:
            raise ValueError(f"{self.name}: istanza senza operazioni")
        if self.m_stations < 1:
            raise ValueError(
                f"{self.name}: m_stations = {self.m_stations}, deve essere >= 1"
            )

        for i, t in enumerate(self.task_times):
            if t <= 0:
                raise ValueError(
                    f"{self.name}: l'operazione {i} ha tempo {t}, deve essere > 0"
                )

        for u, v in self.precedences:
            if not (0 <= u < n and 0 <= v < n):
                raise ValueError(
                    f"{self.name}: arco ({u}, {v}) fuori dal range [0, {n - 1}]"
                )
            if u == v:
                raise ValueError(f"{self.name}: cappio sull'operazione {u}")

    def __repr__(self) -> str:
        """Compatto di proposito: è quello che vedi nei messaggi di errore."""
        return (
            f"ALBInstance({self.name!r}, n={self.n_tasks}, m={self.m_stations}, "
            f"|E|={self.n_precedences}, sum_t={self.total_time})"
        )

    # --------------------------------------------------------------------- I/O

    def save(self, path: str | Path) -> None:
        """Scrive l'istanza in formato .alb.

        Emette sia <cycle time> (quando lo conosciamo) sia <number of stations>.
        Il primo è il tag che gli strumenti di letteratura si aspettano, il secondo
        è il dato che serve al SALBP-2. Dato che entrambi i parser sono tolleranti,
        il file resta leggibile da tutte e due le parti.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        blocks: list[str] = [f"<number of tasks>\n{self.n_tasks}\n"]

        if self.cycle_time is not None:
            blocks.append(f"<cycle time>\n{self.cycle_time}\n")

        blocks.append(f"<number of stations>\n{self.m_stations}\n")

        if (os_value := self.meta.get("order_strength")) is not None:
            blocks.append(f"<order strength>\n{float(os_value):.6f}\n")

        blocks.append(
            "<task times>\n"
            + "\n".join(f"{i + 1} {t}" for i, t in enumerate(self.task_times))
            + "\n"
        )
        blocks.append(
            "<precedence relations>\n"
            + "\n".join(f"{u + 1},{v + 1}" for u, v in self.precedences)
            + "\n"
        )
        blocks.append("<end>\n")

        p.write_text("\n".join(blocks), encoding="utf-8", newline="\n")

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        m_stations: int | None = None,
        name: str | None = None,
    ) -> ALBInstance:
        """Legge un file .alb, incluse le istanze benchmark di letteratura.

        Args:
            m_stations: forza il numero di stazioni ignorando quello nel file.
                Serve per i benchmark SALBP-1, che il numero di stazioni non ce
                l'hanno, e per risolvere la stessa istanza con m diversi — che è
                uno dei fattori del disegno sperimentale.
            name: sovrascrive il nome, che di default è il nome del file.
        """
        p = Path(path)
        sections = _parse_sections(p.read_text(encoding="utf-8"))

        if "number of tasks" not in sections:
            raise ValueError(f"{p.name}: manca il blocco <number of tasks>")
        n = int(sections["number of tasks"][0])

        if "task times" not in sections:
            raise ValueError(f"{p.name}: manca il blocco <task times>")

        # None come sentinella, non 0, per distinguere "tempo mancante" da
        # "tempo pari a zero" e l'errore dice quale operazione manca.
        times: list[int | None] = [None] * n
        for line in sections["task times"]:
            fields = line.split()
            if len(fields) != 2:
                raise ValueError(f"{p.name}: riga di tempo malformata: {line!r}")
            idx = int(fields[0]) - 1               # 1-based -> 0-based
            if not 0 <= idx < n:
                raise ValueError(
                    f"{p.name}: indice operazione {idx + 1} fuori dal range 1..{n}"
                )
            times[idx] = int(fields[1])

        if missing := [i + 1 for i, t in enumerate(times) if t is None]:
            raise ValueError(
                f"{p.name}: tempi mancanti per le operazioni {missing[:10]}"
                f"{' ...' if len(missing) > 10 else ''}"
            )

        precedences: list[tuple[int, int]] = []
        for line in sections.get("precedence relations", []):
            # I file usano la virgola, alcuni generatori lo spazio: accettiamo entrambi.
            fields = line.replace(",", " ").split()
            if len(fields) != 2:
                raise ValueError(f"{p.name}: riga di precedenza malformata: {line!r}")
            precedences.append((int(fields[0]) - 1, int(fields[1]) - 1))

        cycle_time = (
            int(sections["cycle time"][0]) if sections.get("cycle time") else None
        )

        m = m_stations
        if m is None and sections.get("number of stations"):
            m = int(sections["number of stations"][0])
        if m is None:
            raise ValueError(
                f"{p.name}: il file non contiene il numero di stazioni. "
                f"Passalo esplicitamente: ALBInstance.load(path, m_stations=...)"
            )

        meta: dict = {"source_file": str(p)}
        if sections.get("order strength"):
            meta["order_strength"] = float(sections["order strength"][0])

        return cls(
            name=name or p.stem,
            task_times=tuple(times),  # type: ignore[arg-type]  # i None sono esclusi sopra
            precedences=tuple(precedences),
            m_stations=m,
            cycle_time=cycle_time,
            meta=meta,
        )