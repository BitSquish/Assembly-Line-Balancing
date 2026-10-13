"""Esempio delle slide: l'istanza da 10 task usata per sviluppare l'euristica.

Uso:
    python -m scripts.esempio --out results/esempio/

Esegue i quattro metodi sull'istanza (la stessa di tests/test_heuristic.py),
stampa bound e soluzioni e salva due figure:
    esempio_grafo.png     grafo delle precedenze, task colorati per stazione
                          (soluzione di Hoffmann)
    esempio_carichi.png   carico di ogni stazione, con il lower bound
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

from scripts.make_figures import GRID, INK, INK_MUTED, SURFACE
from scripts.run_experiments import METHODS
from src.bounds import lower_bound, simple_lower_bound, window_lower_bound, StationBounds
from src.graph import PrecedenceGraph
from src.instance import ALBInstance

# Task 1..10 nel testo, indici 0..9 nel codice.
EXAMPLE = ALBInstance(
    "esempio",
    (4, 8, 7, 4, 7, 1, 7, 5, 5, 2),
    ((0, 2), (1, 6), (2, 5), (2, 6), (2, 8), (3, 7), (3, 8), (4, 9), (6, 7), (6, 9)),
    m_stations=3,
)

STATION_COLORS = ["#316cb3", "#d9731c", "#3f8f0c", "#7c1c78"]
# Posizioni (colonna, riga) dei task 1..10 nel disegno, scelte per avere un solo
# incrocio: ogni sorgente sta nella colonna subito prima del suo primo successore.
POSITIONS = {1: (0, -1), 2: (1, 1), 3: (1, 0), 4: (1, -1),
             5: (2, 1.5), 7: (2, 0.5), 6: (2, -0.5), 9: (2, -1.5),
             10: (3, 0.5), 8: (3, -0.5)}


def draw_graph(inst: ALBInstance, stations: tuple[int, ...], path: Path) -> None:
    """Grafo delle precedenze con le posizioni di POSITIONS, task colorati per stazione."""
    pos = {j - 1: xy for j, xy in POSITIONS.items()}     # task 1..10 -> indici 0..9
    dg = nx.DiGraph(list(inst.precedences))
    dg.add_nodes_from(range(inst.n_tasks))
    fig, ax = plt.subplots(figsize=(8, 4.2))
    nx.draw_networkx_edges(dg, pos, ax=ax, edge_color=INK_MUTED, arrowsize=14,
                           node_size=1500, width=1.2)
    nx.draw_networkx_nodes(dg, pos, ax=ax, node_size=1500, linewidths=0,
                           node_color=[STATION_COLORS[stations[j] - 1] for j in dg.nodes])
    nx.draw_networkx_labels(dg, pos, ax=ax, font_color="white", font_size=8.5,
                            labels={j: f"{j + 1}\n(t = {inst.task_times[j]})" for j in dg.nodes})
    for s in range(1, inst.m_stations + 1):
        ax.scatter([], [], s=120, color=STATION_COLORS[s - 1], label=f"stazione {s}")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=inst.m_stations,
              frameon=False, fontsize=9)
    ax.set_title("Task e tempo t, colorati per stazione", fontsize=11, color=INK, loc="left")
    ax.axis("off")
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    print(f"  {path}")


def draw_loads(inst: ALBInstance, stations: tuple[int, ...], lb: int, path: Path) -> None:
    """Barre impilate: ogni stazione con i suoi task, linea al lower bound."""
    fig, ax = plt.subplots(figsize=(6, 3.2))
    for s in range(1, inst.m_stations + 1):
        left = 0
        for j in [j for j in range(inst.n_tasks) if stations[j] == s]:
            t = inst.task_times[j]
            ax.barh(s, t, left=left, color=STATION_COLORS[s - 1], edgecolor=SURFACE, linewidth=2)
            ax.text(left + t / 2, s, str(j + 1), ha="center", va="center", color="white", fontsize=9)
            left += t
        ax.text(left + 0.3, s, str(left), va="center", fontsize=9, color=INK)
    ax.axvline(lb, color=INK_MUTED, linestyle=(0, (4, 3)), linewidth=1)
    ax.text(lb, 0.35, f"lower bound {lb}", ha="center", fontsize=8, color=INK_MUTED)
    top = max(lb, max(sum(inst.task_times[j] for j in range(inst.n_tasks) if stations[j] == s)
                      for s in range(1, inst.m_stations + 1)))
    ax.set_xticks(range(0, top + 1, 2))
    ax.set_yticks(range(1, inst.m_stations + 1))
    ax.set_yticklabels([f"stazione {s}" for s in range(1, inst.m_stations + 1)], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("carico", fontsize=9, color=INK_MUTED)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0, labelcolor=INK_MUTED)
    ax.set_facecolor(SURFACE)
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    print(f"  {path}")




def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("results/esempio"))
    parser.add_argument("--time-limit", type=float, default=10.0)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    inst, g = EXAMPLE, PrecedenceGraph(EXAMPLE)
    print(f"Somma dei tempi {inst.total_time}, m = {inst.m_stations}")
    print(f"LC1 e LC2: {simple_lower_bound(inst)} | finestre semplici: "
          f"{window_lower_bound(inst, g)} | teste ricorsive: {lower_bound(inst, g)}")

    results = {}
    for name, (_, solve) in METHODS.items():
        res = solve(inst, args.time_limit)
        results[name] = res
        groups = [[j + 1 for j in range(inst.n_tasks) if res.solution.stations[j] == s]
                  for s in range(1, inst.m_stations + 1)]
        print(f"  {name:20s} c = {res.objective} ({res.status.value}), stazioni {groups}, "
              f"carichi {list(res.solution.loads)}")

    best = results["hoffmann"]
    draw_graph(inst, best.solution.stations, args.out / "esempio_grafo.png")
    draw_loads(inst, best.solution.stations, best.lower_bound, args.out / "esempio_carichi.png")



if __name__ == "__main__":
    main()