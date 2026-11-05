"""Figure di esempio delle slide: istanza da 10 task e order strength

Uso:
    python -m scripts.esempio --out results/esempio/

Esegue i quattro metodi sull'istanza (la stessa di tests/test_heuristic.py),
stampa bound e soluzioni e salva due figure:
    esempio_grafo.png     grafo delle precedenze, task colorati per stazione
                          (soluzione di Hoffmann)
    order_strength.png    grafi e matrice delle precedenze per OS 0,2, 0,6 e 0,9
                          (generatore, 10 task, seed 1)
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
from src.bounds import lower_bound, simple_lower_bound, window_lower_bound
from src.graph import PrecedenceGraph
from src.instance import ALBInstance
from matplotlib.patches import Rectangle
from src.generator import generate

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


# Figura dell'order strength: tre istanze da 10 task del generatore, seed 1,
# una per livello di OS del disegno sperimentale.
OS_LEVELS = [(0.2, "sparso"), (0.6, "medio"), (0.9, "quasi una catena")]
OS_SEED = 1
NODE_COLOR, EDGE_COLOR = "#316cb3", "#6f6e69"


def _layered_positions(graph: nx.DiGraph) -> dict[int, tuple[float, float]]:
    """Colonna = livello del task (cammino più lungo da una sorgente), righe centrate."""
    level: dict[int, int] = {}
    for v in nx.topological_sort(graph):
        level[v] = max((level[u] + 1 for u in graph.predecessors(v)), default=0)
    columns: dict[int, list[int]] = {}
    for v, lv in level.items():
        columns.setdefault(lv, []).append(v)
    return {v: (lv, -(i - (len(vs) - 1) / 2))
            for lv, vs in columns.items() for i, v in enumerate(sorted(vs))}


def draw_order_strength(path: Path, n: int = 10) -> None:
    """Sopra: grafo delle precedenze (solo archi diretti) per OS 0,2, 0,6 e 0,9.

    Sotto: matrice delle precedenze (chiusura transitiva), un quadrato per
    coppia di task, blu se l'ordine è fissato. OS = quadrati blu / (n(n-1)/2).
    """
    total = n * (n - 1) // 2
    fig, axes = plt.subplots(2, 3, figsize=(13, 8.2), gridspec_kw={"height_ratios": [1, 1.05]})
    fig.patch.set_facecolor(SURFACE)
    for k, (os_target, label) in enumerate(OS_LEVELS):
        inst = generate(n, 2, os_target, seed=OS_SEED)      # m non conta per il grafo
        g = nx.DiGraph()
        g.add_nodes_from(range(n))
        g.add_edges_from(inst.precedences)
        reduced, closure = nx.transitive_reduction(g), nx.transitive_closure_dag(g)

        ax = axes[0, k]
        pos = _layered_positions(reduced)
        nx.draw_networkx_edges(reduced, pos, ax=ax, edge_color=EDGE_COLOR, arrowsize=12,
                               node_size=520, width=1.2)
        nx.draw_networkx_nodes(reduced, pos, ax=ax, node_size=520, node_color=NODE_COLOR, linewidths=0)
        nx.draw_networkx_labels(reduced, pos, ax=ax, labels={v: v + 1 for v in reduced},
                                font_color="white", font_size=9)
        os_value = f"{inst.meta['order_strength']:.2f}".replace(".", ",")
        ax.set_title(f"OS = {os_value}  ({label})", fontsize=14, color=INK, fontweight="bold")   
        ax.axis("off")
        ax.margins(0.12)

        ax = axes[1, k]
        ordered = 0
        for i in range(n):
            for j in range(i + 1, n):
                on = closure.has_edge(i, j) or closure.has_edge(j, i)
                ordered += on
                ax.add_patch(Rectangle((j - 1, n - 2 - i), 0.9, 0.9, color=NODE_COLOR if on else GRID))
        for i in range(n - 1):
            ax.text(-0.4, n - 2 - i + 0.45, str(i + 1), ha="right", va="center", fontsize=8, color=INK_MUTED)
            ax.text(i + 0.45, n - 1 + 0.2, str(i + 2), ha="center", va="bottom", fontsize=8, color=INK_MUTED)
        ax.set_xlim(-1.2, n - 0.8)
        ax.set_ylim(-0.6, n)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.text((n - 2) / 2, -0.5, f"{ordered} coppie ordinate su {total}", ha="center", va="top",
                fontsize=12, color=INK, fontweight="bold")                                      
    fig.text(0.5, 0.505, "Ogni quadrato è una coppia di task: blu se le precedenze ne fissano l'ordine "
             f"(anche indirettamente), grigio se l'ordine è libero.  OS = quadrati blu / {total}",
             ha="center", fontsize=10.5, color=INK_MUTED)
    fig.tight_layout(h_pad=5)
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
    draw_order_strength(args.out / "order_strength.png")


if __name__ == "__main__":
    main()