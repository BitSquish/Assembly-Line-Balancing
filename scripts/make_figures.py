"""Tabelle e grafici dai risultati degli esperimenti.

Uso:
    python -m scripts.make_figures --results results/results.csv \\
        --out results/figures_results/ --time-limit 180

Legge il CSV scritto da run_experiments.py (o dal menù, src/main.py) e produce,
nella cartella --out:

    tabella_riassunto.csv     per metodo, sul totale e per numero di task
    tabella_pli.csv           per gruppo e modello: % di ottimi dimostrati, tempo
                              medio, gap medio al termine, esecuzioni senza soluzione
    tabella_euristiche.csv    per gruppo ed euristica: scarto medio e massimo dal
                              riferimento, % di istanze in cui eguaglia il miglior
                              valore noto
    confronto_euristiche.csv  gruppi contro Hoffmann: vittorie, pareggi, sconfitte
                              e test di Wilcoxon (se scipy è installato)
    pli_ottimi.png            % di istanze risolte all'ottimo dimostrato
    pli_tempi.png             tempo medio di calcolo
    pli_gap.png               gap medio tra soluzione e lower bound al termine
    euristiche_scarto.png     scarto medio dal miglior lower bound
    euristiche_migliore.png   % di istanze in cui l'euristica eguaglia il miglior
                              valore noto

Ogni grafico è una griglia di pannelli che segue il disegno sperimentale: una
colonna per numero di task, una riga per order strength; dentro ogni pannello,
un gruppo di barre per numero di stazioni e una barra per metodo. I gruppi fuori
dal disegno fattoriale (per esempio con tempi bimodali) compaiono solo nelle
tabelle.

Riferimento per le euristiche. Per ogni istanza:
    miglior lower bound = massimo dei lower bound di tutti i metodi (ognuno è valido);
    miglior valore noto = minimo degli obiettivi di tutti i metodi.
Se i due coincidono l'ottimo è dimostrato. Lo scarto di un'euristica è
(obiettivo - miglior lower bound) / miglior lower bound: è la distanza dall'ottimo
quando l'ottimo è dimostrato, e un limite superiore a quella distanza altrimenti.

Le funzioni di questo modulo si possono anche importare:

    from scripts.make_figures import load_results, plot_grid
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
    "ritt_costa": ("Ritt & Costa", "#1baf7a"),
    "hoffmann": ("Hoffmann", "#eda100"),
    "gruppi": ("Gruppi", "#4a3aa7"),
}
PLI = ["patterson_albracht", "ritt_costa"]
HEURISTICS = ["hoffmann", "gruppi"]

# Il fattore "numero di stazioni" è memorizzato come task per stazione: m = n / valore.
STATION_LABELS = {3: "tante\n(n/3)", 6: "medie\n(n/6)", 10: "poche\n(n/10)"}

INK, INK_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e3e2dc", "#fcfcfb"


# ----------------------------------------------------------------- dati


def load_results(path: str | Path) -> pd.DataFrame:
    """Legge il CSV dei risultati e aggiunge i riferimenti per istanza.

    Le righe di metodi non presenti in METHODS vengono scartate (con un avviso):
    così un file che contiene ancora esecuzioni di un modello rimosso dal
    progetto si analizza comunque, e i riferimenti usano solo i metodi attuali.

    Colonne aggiunte: os_target (order strength obiettivo del gruppo), best_lb,
    best_ub, proven (ottimo dimostrato per l'istanza), dev (scarto dell'obiettivo
    dal miglior lower bound), is_best (eguaglia il miglior valore noto).
    """
    df = pd.read_csv(path)
    unknown = sorted(set(df["method"]) - set(METHODS))
    if unknown:
        print(f"  Attenzione: righe scartate per metodi non previsti: {unknown}")
        df = df[df["method"].isin(METHODS)].copy()
    errors = int((df["status"] == "error").sum())
    if errors:
        print(f"  Attenzione: {errors} esecuzioni in errore (vedi la colonna 'error' del CSV)")

    for col in ("objective", "lower_bound", "time_s", "gap", "n", "tasks_per_station"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["os_target"] = df["group"].map(_os_from_group)

    per_instance = df.groupby("instance").agg(
        best_lb=("lower_bound", "max"), best_ub=("objective", "min")
    )
    df = df.join(per_instance, on="instance")
    df["proven"] = df["best_lb"] == df["best_ub"]
    df["dev"] = (df["objective"] - df["best_lb"]) / df["best_lb"]
    df["is_best"] = df["objective"] == df["best_ub"]
    return df


def _os_from_group(group: str) -> float:
    # "n50_os0.2_r3_uniform" -> 0.2 (l'OS obiettivo; la colonna "os" è quella ottenuta)
    return float(next(p[2:] for p in group.split("_") if p.startswith("os")))


_GROUP_KEYS = ["group", "n", "os_target", "tasks_per_station", "time_dist", "method"]


def summary_table(df: pd.DataFrame) -> pd.DataFrame:
    """Una riga per metodo sul totale, poi una per metodo e numero di task."""
    order = [m for m in METHODS if m in set(df["method"])]

    def block(data: pd.DataFrame, label) -> pd.DataFrame:
        out = data.groupby("method").agg(
            istanze=("instance", "count"),
            ottimi_pct=("status", lambda s: 100 * (s == "optimal").mean()),
            scarto_medio_pct=("dev", lambda x: 100 * x.mean()),
            scarto_max_pct=("dev", lambda x: 100 * x.max()),
            miglior_valore_pct=("is_best", lambda x: 100 * x.mean()),
            tempo_medio_s=("time_s", "mean"),
        ).reindex(order).dropna(how="all")
        out.insert(0, "n", label)
        return out.reset_index()

    parts = [block(df, "tutti")] + [block(part, int(n)) for n, part in df.groupby("n")]
    return pd.concat(parts, ignore_index=True).round(2)


def pli_table(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["kind"] == "pli"]
    out = d.groupby(_GROUP_KEYS, sort=False).agg(
        istanze=("instance", "count"),
        ottimi_pct=("status", lambda s: 100 * (s == "optimal").mean()),
        tempo_medio_s=("time_s", "mean"),
        gap_medio_pct=("gap", lambda g: 100 * g.mean()),
        senza_soluzione=("status", lambda s: int(s.isin(["no_solution", "error", "solver_error"]).sum())),
    )
    return out.round(2).reset_index()


def heuristic_table(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["kind"] == "euristica"]
    out = d.groupby(_GROUP_KEYS, sort=False).agg(
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


def _fmt(value: float) -> str:
    """Numero con la virgola decimale e senza zeri inutili: 0.2 -> '0,2', 50.0 -> '50'."""
    return f"{value:g}".replace(".", ",")


def plot_grid(
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
    """Griglia di pannelli: colonne = numero di task, righe = order strength.

    In ogni pannello un gruppo di barre per numero di stazioni e una barra per
    metodo. L'asse verticale è lo stesso in tutti i pannelli, così le altezze
    si confrontano tra un pannello e l'altro.

    Args:
        data: righe dei risultati (da load_results), già filtrate se serve.
        value: colonna da aggregare (per esempio "time_s", "gap", "dev").
        methods: metodi da disegnare, nell'ordine voluto.
        agg: aggregazione per (gruppo, metodo): "mean" o una funzione.
        scale: fattore applicato ai valori (100 per passare a percentuali).
        reference_line: linea orizzontale di riferimento (per esempio il limite di tempo).
    """
    grid = data[data["time_dist"] == "uniform"]
    methods = [m for m in methods if m in set(grid["method"])]
    if not methods:
        print(f"  (nessun dato per {Path(path).name}: saltato)")
        return

    ns = sorted(grid["n"].unique())
    oss = sorted(grid["os_target"].unique())
    ratios = sorted(grid["tasks_per_station"].unique())
    table = grid.groupby(["os_target", "n", "tasks_per_station", "method"])[value].agg(agg) * scale
    # Istanze per gruppo, per ogni numero di task (il più frequente tra i suoi gruppi).
    per_group = grid.groupby(["n", "group"])["instance"].nunique().groupby("n").agg(
        lambda s: int(s.mode().iloc[0])
    )

    fig, axes = plt.subplots(
        len(oss), len(ns), sharex=True, sharey=True, squeeze=False,
        figsize=(1.2 + 2.5 * len(ns), 1.6 + 1.9 * len(oss)), facecolor=SURFACE,
    )
    width = 0.8 / len(methods)
    # Stesso asse verticale in tutti i pannelli, con un margine sopra la barra più alta.
    shown = table[table.index.get_level_values("method").isin(methods)]
    y_top = max(float(shown.max()) if len(shown) else 0.0, reference_line or 0.0)
    y_top = y_top * 1.1 if y_top > 0 else 1.0
    for row, os_value in enumerate(oss):
        for col, n in enumerate(ns):
            ax = axes[row][col]
            ax.set_facecolor(SURFACE)
            drawn = False
            for k, method in enumerate(methods):
                label, color = METHODS[method]
                heights = [table.get((os_value, n, r, method), float("nan")) for r in ratios]
                if all(pd.isna(h) for h in heights):
                    continue
                drawn = True
                x = [g + (k - (len(methods) - 1) / 2) * width for g in range(len(ratios))]
                # Lo spazio tra le barre è lasciato alla superficie (bordo dello stesso colore).
                ax.bar(x, [0 if pd.isna(h) else h for h in heights], width=width, color=color,
                       label=label, edgecolor=SURFACE, linewidth=1.5, zorder=3)
                # Una barra di altezza zero non si vede: si scrive il valore, così
                # "zero" si distingue da "dato mancante".
                for xk, h in zip(x, heights):
                    if pd.isna(h) or h == 0:
                        ax.text(xk, y_top * 0.015, "n.d." if pd.isna(h) else "0", ha="center",
                                va="bottom", fontsize=6.5, color=INK_MUTED, zorder=4)
            if not drawn:
                ax.text(0.5, 0.5, "nessun dato", transform=ax.transAxes, ha="center",
                        va="center", fontsize=8, color=INK_MUTED)
            if reference_line is not None:
                ax.axhline(reference_line, color=INK_MUTED, linewidth=1, linestyle=(0, (4, 3)),
                           zorder=2)

            if row == 0:
                ax.set_title(f"{int(n)} task\n({per_group[n]} istanze per gruppo)",
                             fontsize=9, color=INK, pad=6)
            if col == 0:
                ax.set_ylabel(f"OS {_fmt(os_value)}", fontsize=9, color=INK)
            ax.set_xticks(range(len(ratios)))
            ax.set_xticklabels(
                [STATION_LABELS.get(int(r), f"n/{_fmt(r)}") for r in ratios],
                fontsize=7.5, color=INK_MUTED,
            )
            ax.set_ylim(0, y_top)
            ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=1)
            ax.set_axisbelow(True)
            ax.tick_params(axis="both", length=0, labelcolor=INK_MUTED, labelsize=7.5)
            for side in ("top", "right", "left"):
                ax.spines[side].set_visible(False)
            ax.spines["bottom"].set_color(GRID)

    # Intestazione: titolo, legenda e una riga che spiega come leggere la griglia.
    height = fig.get_figheight()
    top = 1 - 0.80 / height                 # 0,80 pollici riservati all'intestazione
    fig.suptitle(title, x=0.01, y=1 - 0.08 / height, ha="left", va="top",
                 fontsize=11, color=INK)
    how_to_read = (f"{ylabel}. Colonne: numero di task. Righe: order strength (OS). "
                   "Asse orizzontale: numero di stazioni m.")
    if reference_line is not None and reference_label:
        how_to_read += f" Linea tratteggiata: {reference_label}."
    fig.text(0.01, 1 - 0.40 / height, how_to_read,
             ha="left", va="top", fontsize=8, color=INK_MUTED)
    handles = [plt.Rectangle((0, 0), 1, 1, color=METHODS[m][1]) for m in methods]
    fig.legend(handles, [METHODS[m][0] for m in methods], loc="upper left",
               bbox_to_anchor=(0.005, 1 - 0.58 / height), ncol=len(methods), frameon=False,
               fontsize=8.5, labelcolor=INK, handlelength=1.1, borderaxespad=0)

    fig.tight_layout(rect=(0, 0, 1, top))
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    print(f"  {path}")


def make_all(results: str | Path, out: str | Path, time_limit: float | None = None) -> None:
    """Scrive tutte le tabelle e tutti i grafici nella cartella out."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    df = load_results(results)
    print(f"{df['instance'].nunique()} istanze, metodi: {[m for m in METHODS if m in set(df['method'])]}")
    outside = sorted(df.loc[df["time_dist"] != "uniform", "group"].unique())
    if outside:
        print(f"  Gruppi solo nelle tabelle (fuori dalla griglia dei grafici): {outside}")

    summary_table(df).to_csv(out / "tabella_riassunto.csv", index=False)
    pli_table(df).to_csv(out / "tabella_pli.csv", index=False)
    heuristic_table(df).to_csv(out / "tabella_euristiche.csv", index=False)
    comparison = heuristic_comparison(df)
    if not comparison.empty:
        comparison.to_csv(out / "confronto_euristiche.csv", index=False)
    print(f"  tabelle in {out}")

    pli = df[df["kind"] == "pli"].copy()
    pli["optimal"] = pli["status"] == "optimal"
    plot_grid(pli, "optimal", PLI, scale=100,
              title="Istanze risolte all'ottimo dimostrato entro il limite di tempo",
              ylabel="% di istanze", path=out / "pli_ottimi.png")
    plot_grid(pli, "time_s", PLI,
              title="Tempo medio di calcolo dei modelli PLI",
              ylabel="Secondi", path=out / "pli_tempi.png",
              reference_line=time_limit, reference_label="limite di tempo")
    plot_grid(pli, "gap", PLI, scale=100,
              title="Gap medio tra soluzione e lower bound del modello al termine",
              ylabel="Gap (%)", path=out / "pli_gap.png")

    heur = df[df["kind"] == "euristica"].copy()
    plot_grid(heur, "dev", HEURISTICS, scale=100,
              title="Scarto medio delle euristiche dal miglior lower bound",
              ylabel="Scarto (%)", path=out / "euristiche_scarto.png")
    plot_grid(heur, "is_best", HEURISTICS, scale=100,
              title="Istanze in cui l'euristica eguaglia il miglior valore noto",
              ylabel="% di istanze", path=out / "euristiche_migliore.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--time-limit", type=float, default=None,
                        help="limite di tempo usato, per disegnarlo nel grafico dei tempi")
    args = parser.parse_args()
    make_all(args.results, args.out, args.time_limit)


if __name__ == "__main__":
    main()
