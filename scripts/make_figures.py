"""Tabelle e grafici dai risultati degli esperimenti.

Uso:
    python -m scripts.make_figures --results results/pilot.csv --out results/figures_pilot/
    python -m scripts.make_figures --results results/results.csv --out results/figures/

Legge il CSV scritto da run_experiments.py e produce, nella cartella --out:

    tabella_pli.csv           per gruppo e modello: % di ottimi dimostrati, tempo
                              medio, gap medio al time limit, esecuzioni senza soluzione
    tabella_euristiche.csv    per gruppo ed euristica: scarto medio dal riferimento,
                              % di istanze in cui eguaglia il miglior valore noto
    confronto_euristiche.csv  gruppi contro Hoffmann: vittorie, pareggi, sconfitte
                              e test di Wilcoxon (se scipy è installato)
    pli_ottimi.png            % di istanze risolte all'ottimo, per gruppo e modello
    pli_tempi.png             tempo medio di calcolo, per gruppo e modello
    pli_gap.png               gap medio al time limit, per gruppo e modello
    euristiche_scarto.png     scarto medio dal riferimento, per gruppo ed euristica
    euristiche_migliore.png   % di istanze in cui l'euristica eguaglia il miglior valore noto

Riferimento per le euristiche. Per ogni istanza:
    miglior lower bound = massimo dei lower bound di tutti i metodi (ognuno è valido);
    miglior valore noto = minimo degli obiettivi di tutti i metodi.
Se i due coincidono l'ottimo è dimostrato. Lo scarto di un'euristica è
(obiettivo - miglior lower bound) / miglior lower bound: è la distanza dall'ottimo
quando un PLI lo ha dimostrato, e un limite superiore a quella distanza altrimenti.

I grafici usano le funzioni di questo modulo, che si possono anche importare:

    from scripts.make_figures import load_results, plot_grouped_bars
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")                       # nessuna finestra: si salva solo su file
import matplotlib.pyplot as plt
import pandas as pd

# Colore fisso per metodo (segue il metodo, non la posizione nel grafico).
METHODS = {
    "patterson_albracht": ("Patterson & Albracht", "#2a78d6"),
    "bowman_white": ("Bowman-White", "#eb6834"),
    "ritt_costa": ("Ritt & Costa", "#1baf7a"),
    "hoffmann": ("Hoffmann", "#eda100"),
    "gruppi": ("Gruppi", "#4a3aa7"),
}
PLI = ["patterson_albracht", "bowman_white", "ritt_costa"]
HEURISTICS = ["hoffmann", "gruppi"]

INK, INK_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e3e2dc", "#fcfcfb"


# ----------------------------------------------------------------- dati


def load_results(path: str | Path) -> pd.DataFrame:
    """Legge il CSV dei risultati e aggiunge i riferimenti per istanza.

    Colonne aggiunte: best_lb, best_ub, proven (ottimo dimostrato per l'istanza),
    dev (scarto dell'obiettivo dal miglior lower bound), is_best (eguaglia il
    miglior valore noto), group_label (etichetta breve del gruppo).
    """
    df = pd.read_csv(path)
    for col in ("objective", "lower_bound", "time_s", "gap"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    per_instance = df.groupby("instance").agg(
        best_lb=("lower_bound", "max"), best_ub=("objective", "min")
    )
    df = df.join(per_instance, on="instance")
    df["proven"] = df["best_lb"] == df["best_ub"]
    df["dev"] = (df["objective"] - df["best_lb"]) / df["best_lb"]
    df["is_best"] = df["objective"] == df["best_ub"]
    df["group_label"] = [
        _group_label(n, os_target, r, dist)
        for n, os_target, r, dist in zip(
            df["n"], df["group"].map(_os_from_group), df["tasks_per_station"], df["time_dist"]
        )
    ]
    return df


def _os_from_group(group: str) -> str:
    # "n50_os0.2_r3_uniform" -> "0.2" (l'OS obiettivo; la colonna "os" è quella ottenuta)
    return next(p[2:] for p in group.split("_") if p.startswith("os"))


def _group_label(n, os_target, r, dist) -> str:
    label = f"n={n}\nOS {os_target}\n{r} task/staz."
    return label + ("\nbimodale" if dist == "bimodal" else "")


def _group_order(df: pd.DataFrame) -> list[str]:
    """Gruppi nell'ordine in cui compaiono nel CSV (quello del disegno)."""
    return list(dict.fromkeys(df["group_label"]))


def pli_table(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["kind"] == "pli"]
    out = d.groupby(["group", "method"], sort=False).agg(
        istanze=("instance", "count"),
        ottimi_pct=("status", lambda s: 100 * (s == "optimal").mean()),
        tempo_medio_s=("time_s", "mean"),
        gap_medio_pct=("gap", lambda g: 100 * g.mean()),
        senza_soluzione=("status", lambda s: int(s.isin(["no_solution", "error", "solver_error"]).sum())),
    )
    return out.round(2).reset_index()


def heuristic_table(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["kind"] == "euristica"]
    out = d.groupby(["group", "method"], sort=False).agg(
        istanze=("instance", "count"),
        scarto_medio_pct=("dev", lambda x: 100 * x.mean()),
        scarto_max_pct=("dev", lambda x: 100 * x.max()),
        miglior_valore_pct=("is_best", lambda x: 100 * x.mean()),
        istanze_con_ottimo_dimostrato=("proven", "sum"),
        tempo_medio_s=("time_s", "mean"),
    )
    return out.round(3).reset_index()


def heuristic_comparison(df: pd.DataFrame, a: str = "gruppi", b: str = "hoffmann") -> pd.DataFrame:
    """Confronto appaiato a contro b, per gruppo e sul totale.

    Il test dei ranghi con segno di Wilcoxon (Otto et al., 2013, sez. 6.1) dice se
    la differenza tra le due euristiche sulle stesse istanze è significativa.
    """
    wide = df[df["method"].isin([a, b])].pivot(index="instance", columns="method", values="objective")
    if a not in wide or b not in wide:
        return pd.DataFrame()
    wide = wide.dropna().join(df.drop_duplicates("instance").set_index("instance")["group"])

    try:
        from scipy.stats import wilcoxon
    except ImportError:
        wilcoxon = None

    rows = []
    for name, part in [*wide.groupby("group", sort=False), ("TOTALE", wide)]:
        diff = part[a] - part[b]
        p_value = None
        if wilcoxon is not None and (diff != 0).sum() >= 1:
            p_value = round(float(wilcoxon(part[a], part[b]).pvalue), 5)
        rows.append({
            "group": name, "istanze": len(part),
            f"{a}_meglio": int((diff < 0).sum()), "pari": int((diff == 0).sum()),
            f"{b}_meglio": int((diff > 0).sum()),
            "differenza_media_pct": round(100 * (diff / part[b]).mean(), 3),
            "wilcoxon_p": p_value,
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------- grafici


def plot_grouped_bars(
    data: pd.DataFrame,
    value: str,
    methods: list[str],
    *,
    title: str,
    ylabel: str,
    path: str | Path,
    agg="mean",
    scale: float = 1.0,
    reference_line: float | None = None,
    reference_label: str = "",
) -> None:
    """Barre affiancate: un gruppo di barre per gruppo di istanze, una barra per metodo.

    Args:
        data: righe dei risultati (da load_results), già filtrate se serve.
        value: colonna da aggregare (per esempio "time_s", "gap", "dev").
        methods: metodi da disegnare, nell'ordine voluto.
        agg: aggregazione per (gruppo, metodo): "mean" o una funzione.
        scale: fattore applicato ai valori (100 per passare a percentuali).
        reference_line: linea orizzontale di riferimento (per esempio il time limit).
    """
    methods = [m for m in methods if m in set(data["method"])]
    if not methods:
        print(f"  (nessun dato per {Path(path).name}: saltato)")
        return
    groups = _group_order(data)
    table = (
        data.groupby(["group_label", "method"])[value].agg(agg).unstack("method").reindex(groups) * scale
    )

    width = 0.8 / len(methods)
    fig, ax = plt.subplots(figsize=(max(7.0, 1.05 * len(groups) + 2.0), 4.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for k, method in enumerate(methods):
        label, color = METHODS[method]
        x = [g + (k - (len(methods) - 1) / 2) * width for g in range(len(groups))]
        # Lo spazio tra le barre è lasciato alla superficie (bordo dello stesso colore).
        ax.bar(x, table[method].fillna(0), width=width, color=color, label=label,
               edgecolor=SURFACE, linewidth=1.5, zorder=3)

    if reference_line is not None:
        ax.axhline(reference_line, color=INK_MUTED, linewidth=1, zorder=2)
        ax.annotate(reference_label, xy=(len(groups) - 0.5, reference_line), xytext=(0, 3),
                    textcoords="offset points", ha="right", va="bottom",
                    fontsize=8, color=INK_MUTED)

    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(groups, fontsize=8, color=INK_MUTED)
    ax.set_ylabel(ylabel, fontsize=9, color=INK_MUTED)
    ax.set_title(title, fontsize=11, color=INK, loc="left", pad=28)
    ax.set_ylim(bottom=0)
    ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=1)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0, labelcolor=INK_MUTED, labelsize=8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    if len(methods) > 1:
        ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=len(methods),
                  frameon=False, fontsize=8.5, labelcolor=INK, handlelength=1.1)

    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    print(f"  {path}")


def make_all(results: str | Path, out: str | Path, time_limit: float | None = None) -> None:
    """Scrive tutte le tabelle e tutti i grafici nella cartella out."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    df = load_results(results)
    print(f"{df['instance'].nunique()} istanze, metodi: {sorted(df['method'].unique())}")

    pli_table(df).to_csv(out / "tabella_pli.csv", index=False)
    heuristic_table(df).to_csv(out / "tabella_euristiche.csv", index=False)
    comparison = heuristic_comparison(df)
    if not comparison.empty:
        comparison.to_csv(out / "confronto_euristiche.csv", index=False)
    print(f"  tabelle in {out}")

    pli = df[df["kind"] == "pli"].copy()
    pli["optimal"] = pli["status"] == "optimal"
    plot_grouped_bars(pli, "optimal", PLI, scale=100,
                      title="Istanze risolte all'ottimo dimostrato entro il time limit",
                      ylabel="% di istanze", path=out / "pli_ottimi.png")
    plot_grouped_bars(pli, "time_s", PLI,
                      title="Tempo medio di calcolo dei modelli PLI",
                      ylabel="secondi", path=out / "pli_tempi.png",
                      reference_line=time_limit, reference_label="time limit")
    plot_grouped_bars(pli, "gap", PLI, scale=100,
                      title="Gap medio tra soluzione e lower bound al termine",
                      ylabel="gap (%)", path=out / "pli_gap.png")

    heur = df[df["kind"] == "euristica"].copy()
    plot_grouped_bars(heur, "dev", HEURISTICS, scale=100,
                      title="Scarto medio delle euristiche dal miglior lower bound",
                      ylabel="scarto (%)", path=out / "euristiche_scarto.png")
    plot_grouped_bars(heur, "is_best", HEURISTICS, scale=100,
                      title="Istanze in cui l'euristica eguaglia il miglior valore noto",
                      ylabel="% di istanze", path=out / "euristiche_migliore.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--time-limit", type=float, default=None,
                        help="time limit usato, per disegnarlo nel grafico dei tempi")
    args = parser.parse_args()
    make_all(args.results, args.out, args.time_limit)


if __name__ == "__main__":
    main()