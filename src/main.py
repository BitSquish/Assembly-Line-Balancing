"""Menù principale del progetto SALBP-2.

Uso (dalla cartella del progetto):
    python -m src.main

    1) Tutti gli esperimenti: la campagna completa definita in configs/design.json.
    2) Demo rapida: tre istanze da 50 task, tutti i metodi, 15 secondi per ogni PLI
       (al massimo un minuto e mezzo con due modelli PLI).
    3) Personalizzato: metodi, limite di tempo e parametri delle istanze a scelta.
    4) Vedi risultati: tabella riassuntiva di un file di risultati già prodotto.
    5) Genera grafici e tabelle da un file di risultati.
    6) Esegui i test del progetto.

Le voci 2 e 3 generano le istanze al momento, con la stessa regola della campagna
(scripts/gen_instances.py), e salvano istanze e risultati in instances_demo/ e
results/demo_<data>_<ora>.csv. Le durate stimate si basano sulla campagna.
"""

from __future__ import annotations

import csv
import itertools
import json
import os
import subprocess
import sys
import time
import zlib
from datetime import datetime
from pathlib import Path

from scripts.gen_instances import group_name, groups_from_config
from scripts.run_experiments import FIELDS, METHODS
from src.generator import generate
from src.graph import PrecedenceGraph

try:
    from colorama import just_fix_windows_console
    just_fix_windows_console()       # abilita i codici ANSI nella console di Windows
except ImportError:
    pass                             # senza colorama: colori corretti nei terminali moderni


class Style:
    """Codici ANSI per colori e formattazione del terminale."""
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


# ------------------------------------------------------------------ impostazioni

DESIGN = Path("configs/design.json")
CAMPAIGN_INSTANCES = Path("instances")
CAMPAIGN_RESULTS = Path("results/results.csv")
CAMPAIGN_TIME_LIMIT = 180.0          # secondi per ogni PLI nella campagna

DEMO_TIME_LIMIT = 15.0
DEMO_GROUPS = [
    ("facile: poche precedenze, stazioni medie",
     {"n": 50, "order_strength": 0.2, "tasks_per_station": 6, "time_dist": "uniform"}),
    ("molte precedenze, tante stazioni",
     {"n": 50, "order_strength": 0.9, "tasks_per_station": 3, "time_dist": "uniform"}),
    ("difficile: poche precedenze, tante stazioni",
     {"n": 50, "order_strength": 0.2, "tasks_per_station": 3, "time_dist": "uniform"}),
    ("grande: 200 task, l'euristica supera i PLI",
     {"n": 200, "order_strength": 0.2, "tasks_per_station": 6, "time_dist": "uniform"}),
]

BASE_SEED = 2026                     # lo stesso di configs/design.json
DEFAULT_TIME_LIMIT = 30.0            # proposto nella voce "Personalizzato"

PLI = [name for name, (kind, _) in METHODS.items() if kind == "pli"]
HEURISTICS = [name for name, (kind, _) in METHODS.items() if kind != "pli"]

LABELS = {
    "patterson_albracht": "PLI Patterson-Albracht",
    "ritt_costa": "PLI Ritt-Costa",
    "hoffmann": "Euristica di Hoffmann",
    "gruppi": "Euristica dei gruppi",
}

# Parametri delle istanze nella voce "Personalizzato":
# (chiave, titolo, spiegazione, [(valore, etichetta)], funzione per "altro valore")
PARAMETERS = [
    ("n", "Numero di task",
     "Quanti task ha ogni istanza generata: è la dimensione del problema.",
     [(20, "20  (istanza piccola)"), (50, "50  (istanza media)"),
      (100, "100 (istanza grande)"), (200, "200 (istanza molto grande)")],
     lambda v: int(v) if 4 <= int(v) <= 1000 else None),
    ("order_strength", "Densità delle precedenze (order strength)",
     "Frazione delle coppie di task il cui ordine è imposto dalle precedenze:\n"
     "  0 = nessuna precedenza, 1 = task in un'unica catena.",
     [(0.2, "0.2 (grafo sparso)"), (0.6, "0.6 (grafo denso)"), (0.9, "0.9 (quasi una catena)")],
     lambda v: float(v.replace(",", ".")) if 0 <= float(v.replace(",", ".")) <= 0.95 else None),
    ("tasks_per_station", "Numero di stazioni",
     "Scelto in proporzione ai task: m = n / 3, n / 6 oppure n / 10. Come distribuire\n"
     "  i task tra le stazioni lo decide il metodo risolutivo.",
     [(3, "tante stazioni  (m = n / 3)"),
      (6, "stazioni medie  (m = n / 6)"),
      (10, "poche stazioni  (m = n / 10)")],
     lambda v: int(v) if 1 <= int(v) <= 100 else None),
    ("time_dist", "Tempi dei task",
     "Interi tra 1 e 100. Uniformi: tutti i valori ugualmente probabili.\n"
     "  Bimodali: 80% task corti (1-33), 20% task lunghi (68-100).",
     [("uniform", "uniformi"), ("bimodal", "bimodali")],
     None),
]


# ------------------------------------------------------------------ durata

def stations(g: dict) -> int:
    return max(2, round(g["n"] / g["tasks_per_station"]))


# Quota di esecuzioni PLI arrivate al limite di 180 s nella campagna
# (results/results.csv): per numero di task, poi tante / medie / poche
# stazioni, poi OS 0.2 / 0.6 / 0.9.
_SHARE_N, _SHARE_R, _SHARE_OS = (20, 50, 100, 200), (3, 6, 10), (0.2, 0.6, 0.9)
_SHARE = {
    20: ((0, 0, 0), (0, 0, 0), (0, 0, 0)),
    50: ((0.86, 0.78, 0), (0, 0.02, 0), (0, 0, 0)),
    100: ((1, 1, 0.52), (0.46, 0.62, 0), (0, 0, 0)),
    200: ((1, 1, 1), (1, 1, 1), (0.34, 0.5, 0.4)),
}


def timeout_share(g: dict) -> float:
    """Quota di esecuzioni PLI che arrivano al limite di tempo, misurata nella
    campagna con 180 s. Per parametri fuori dal disegno si usa la combinazione
    più vicina. Con limiti più bassi la quota reale è più alta."""
    def nearest(values, x):
        return min(range(len(values)), key=lambda k: abs(values[k] - x))
    n = _SHARE_N[nearest(_SHARE_N, g["n"])]
    return _SHARE[n][nearest(_SHARE_R, g["tasks_per_station"])][nearest(_SHARE_OS, g["order_strength"])]

def duration(groups: list[dict], per_group: int, methods: list[str], time_limit: float) -> tuple[float, float]:
    """
    Stima la durata totale di un insieme di esperimenti, considerando sia la durata stimata che quella massima.
    (durata stimata, durata massima) in secondi.  

    """
    n_pli = sum(m in PLI for m in methods)
    n_heur = len(methods) - n_pli
    worst = estimate = 0.0
    for g in groups:
        count = per_group
        runs = count * n_pli
        share = timeout_share(g)
        worst += runs * time_limit
        estimate += runs * (share * time_limit + (1 - share) * min(5.0, time_limit))
        estimate += count * n_heur * 0.2
        worst += count * n_heur * 1.0
    return estimate, worst


def fmt_time(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} secondi"
    if seconds < 5400:
        return f"{seconds / 60:.0f} minuti"
    return f"{seconds / 3600:.1f} ore"


# ------------------------------------------------------------------ domande

def ask(prompt: str, default: str) -> str:
    answer = input(f"{Style.CYAN}>{Style.RESET} {Style.BOLD}{prompt}{Style.RESET} "
                   f"[{Style.DIM}{default}{Style.RESET}]: ").strip()
    return answer or default


def confirm(prompt: str = "Procedo?", default: str = "s") -> bool:
    return ask(f"{prompt} (s/n)", default).lower() in ("s", "si", "sì", "y")


def choose(title: str, options: list[str], default: int = 1) -> int:
    """Stampa le opzioni numerate e restituisce il numero scelto (da 1)."""
    print(f"\n{Style.BOLD}{Style.MAGENTA}== {title}{Style.RESET}")
    for k, text in enumerate(options, 1):
        print(f"  {Style.CYAN}{k}){Style.RESET} {text}")
    while True:
        raw = ask("Scelta", str(default))
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)
        print(f"  {Style.RED}Scegli un numero da 1 a {len(options)}.{Style.RESET}")


def ask_parameter(title: str, help_text: str, variants: list, parse) -> list:
    """Una variante, tutte, oppure un valore fuori elenco. Restituisce la lista dei valori."""
    options = [label for _, label in variants] + ["tutte le varianti"]
    if parse is not None:
        options.append("altro valore")

    choice = choose(f"{title}{Style.RESET}\n  {Style.DIM}{help_text}", options)

    if choice <= len(variants):
        return [variants[choice - 1][0]]
    if choice == len(variants) + 1:
        return [value for value, _ in variants]
    while True:
        try:
            value = parse(input(f"{Style.CYAN}>{Style.RESET} {Style.BOLD}Valore:{Style.RESET} ").strip())
            if value is not None:
                return [value]
        except ValueError:
            pass
        print(f"  {Style.RED}Valore non valido, riprova.{Style.RESET}")


def ask_float(prompt: str, default: float) -> float:
    while True:
        try:
            value = float(ask(prompt, f"{default:g}").replace(",", "."))
            if value > 0:
                return value
        except ValueError:
            pass
        print(f"  {Style.RED}Serve un numero positivo.{Style.RESET}")


def ask_int(prompt: str, default: int, low: int, high: int) -> int:
    while True:
        raw = ask(prompt, str(default))
        if raw.isdigit() and low <= int(raw) <= high:
            return int(raw)
        print(f"  {Style.RED}Serve un intero tra {low} e {high}.{Style.RESET}")


# ------------------------------------------------------------------ esecuzione

def print_groups(groups: list[dict], notes: list[str] | None = None) -> None:
    for k, g in enumerate(groups):
        note = f"  {Style.DIM}({notes[k]}){Style.RESET}" if notes else ""
        print(f"  {Style.CYAN}-{Style.RESET} {group_name(g):26s} task = {g['n']:<4d} "
              f"stazioni = {stations(g):<3d} OS = {g['order_strength']:<4g} "
              f"tempi = {g['time_dist']}{note}")


def run(groups: list[dict], per_group: int, methods: list[str], time_limit: float) -> list[dict]:
    """Genera le istanze ed esegue i metodi; restituisce le righe dei risultati."""
    inst_dir = Path("instances_demo")
    out = Path("results") / f"demo_{datetime.now():%Y%m%d_%H%M%S}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    total = len(groups) * per_group * len(methods)
    count = 0

    print(f"\n{Style.BOLD}Avvio esecuzione{Style.RESET}")
    print(f"{Style.DIM}Istanze in {inst_dir}/, risultati in {out}{Style.RESET}\n")

    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        try:
            for g in groups:
                gname = group_name(g)
                m = stations(g)
                for k in range(per_group):
                    seed = zlib.crc32(f"{BASE_SEED}|{gname}|{k}".encode())
                    name = f"{gname}_{k:02d}"
                    inst = generate(g["n"], m, g["order_strength"],
                                    time_dist=g["time_dist"], seed=seed, name=name)
                    inst.save(inst_dir / gname / f"{name}.alb")
                    os_real = round(PrecedenceGraph(inst).order_strength, 4)
                    for method in methods:
                        count += 1
                        kind, solve = METHODS[method]
                        row = {
                            "instance": name, "group": gname, "n": g["n"], "m": m,
                            "os": os_real, "tasks_per_station": g["tasks_per_station"],
                            "time_dist": g["time_dist"], "method": method, "kind": kind,
                        }
                        t0 = time.perf_counter()
                        try:
                            res = solve(inst, time_limit)
                            extra = dict(res.extra)
                            row.update({
                                "status": res.status.value,
                                "objective": res.objective,
                                "lower_bound": res.lower_bound,
                                "gap": None if res.gap is None else round(res.gap, 6),
                                "time_s": round(res.time_s, 3),
                                "build_s": round(extra.pop("build_s", 0.0), 3) if kind == "pli" else "",
                                "n_vars": extra.pop("n_vars", ""),
                                "n_constraints": extra.pop("n_constraints", ""),
                                "extra": json.dumps(extra),
                                "error": "",
                            })
                            status_color = Style.GREEN if row["status"] == "optimal" else Style.YELLOW
                        except Exception as exc:               # noqa: BLE001
                            row.update({
                                "status": "error",
                                "time_s": round(time.perf_counter() - t0, 3),
                                "error": f"{type(exc).__name__}: {exc}",
                            })
                            status_color = Style.RED

                        writer.writerow(row)
                        fh.flush()
                        rows.append(row)

                        prefix = f"{Style.DIM}[{count:03d}/{total:03d}]{Style.RESET}"
                        print(f"{prefix} {Style.CYAN}{name:30s}{Style.RESET} {LABELS.get(method, method):24s} "
                              f"{status_color}{row['status']:9s}{Style.RESET} "
                              f"carico max = {str(row.get('objective') or '-'):<5} "
                              f"lower bound = {str(row.get('lower_bound') or '-'):<5} "
                              f"t = {row['time_s']:>6.2f} s")
        except KeyboardInterrupt:
            print(f"\n{Style.YELLOW}Interrotto: riepilogo delle esecuzioni completate.{Style.RESET}")

    return rows


def summary(rows: list[dict], methods: list[str]) -> None:
    """Tabella per combinazione e metodo.

    Lo scostamento è calcolato rispetto al miglior lower bound dell'istanza
    (il massimo tra quelli di tutti i metodi eseguiti), che coincide con
    l'ottimo quando un metodo lo ha dimostrato.

    "Ottimi" conta le istanze in cui il metodo dimostra l'ottimo da solo.
    "Ott. ragg." conta, tra le istanze il cui ottimo è noto perché qualche
    metodo lo ha dimostrato, quelle in cui il metodo lo ha trovato: è la misura
    corretta per le euristiche, che possono trovare l'ottimo senza certificarlo.
    """
    ok = [r for r in rows if r.get("objective") not in (None, "")]
    best_lb: dict[str, int] = {}
    best_ub: dict[str, int] = {}
    for r in ok:
        best_lb[r["instance"]] = max(best_lb.get(r["instance"], 0), r["lower_bound"])
        best_ub[r["instance"]] = min(best_ub.get(r["instance"], r["objective"]), r["objective"])
    closed = {i for i in best_ub if best_lb[i] == best_ub[i]}      # ottimo noto

    line_thick = Style.MAGENTA + "=" * 100 + Style.RESET
    line_thin = Style.DIM + "-" * 100 + Style.RESET

    print(f"\n{line_thick}")
    print(f"{Style.BOLD}{'Combinazione':26s} {'Metodo':24s} {'Ottimi':>7s} {'Ott. ragg.':>11s} "
          f"{'Carico max':>11s} {'Scost. %':>9s} {'Tempo s':>8s}{Style.RESET}")
    print(line_thin)

    for gname in dict.fromkeys(r["group"] for r in rows):
        for method in methods:
            sel = [r for r in ok if r["group"] == gname and r["method"] == method]
            if not sel:
                continue

            optimal = sum(r["status"] == "optimal" for r in sel)
            color = Style.GREEN if optimal > 0 else ""
            opt_str = f"{color}{optimal:>3d}{Style.RESET}/{len(sel):<3d}"

            known = [r for r in sel if r["instance"] in closed]
            reached = sum(r["objective"] == best_ub[r["instance"]] for r in known)
            reach_str = f"{reached:>3d}/{len(known):<3d}" if known else "n.d."

            mean_obj = sum(r["objective"] for r in sel) / len(sel)
            dev = 100 * sum(
                (r["objective"] - best_lb[r["instance"]]) / best_lb[r["instance"]] for r in sel
            ) / len(sel)
            mean_t = sum(r["time_s"] for r in sel) / len(sel)

            print(f"{gname:26s} {LABELS.get(method, method):24s} {opt_str} {reach_str:>11s} "
                  f"{mean_obj:>11.1f} {dev:>9.2f} {mean_t:>8.2f}")
        print(line_thin)

    print(f"{Style.DIM}Ottimi:     istanze in cui il metodo dimostra l'ottimo (carico massimo = lower bound).")
    print("Ott. ragg.: istanze in cui il metodo trova l'ottimo, tra quelle con ottimo noto.")
    print("Carico max: carico massimo di stazione, in media sulle istanze (da minimizzare).")
    print(f"Scost. %:   distanza media dal miglior lower bound noto per l'istanza.{Style.RESET}")

    errors = [r for r in rows if r["status"] == "error"]
    if errors:
        print(f"\n{Style.RED}{Style.BOLD}ATTENZIONE:{Style.RESET} {Style.RED}{len(errors)} esecuzioni "
              f"in errore, per esempio: {errors[0]['error']}{Style.RESET}")


# ------------------------------------------------------------------ voci del menù

def campaign() -> None:
    """Voce 1: campagna completa, tramite gli script gen_instances e run_experiments."""
    cfg = json.loads(DESIGN.read_text(encoding="utf-8"))
    groups = groups_from_config(cfg)
    per_group = cfg["instances_per_group"]
    methods = list(METHODS)
    estimate, worst = duration(groups, per_group, methods, CAMPAIGN_TIME_LIMIT)

    print(f"\n{Style.BOLD}Campagna completa ({DESIGN}){Style.RESET}")
    total = len(groups) * per_group 
    print(f"{Style.DIM}Gruppi: {len(groups)} | Istanze per gruppo: {per_group} "
          f"| Totale: {total} istanze{Style.RESET}")    
    print_groups(groups)
    print(f"\n{Style.BOLD}Metodi:{Style.RESET} {', '.join(LABELS.get(m, m) for m in methods)}")
    print(f"{Style.BOLD}Limite di tempo:{Style.RESET} {CAMPAIGN_TIME_LIMIT:g} secondi per ogni PLI")
    print(f"{Style.BOLD}Durata stimata:{Style.RESET} {fmt_time(estimate)} "
          f"{Style.DIM}(massima {fmt_time(worst)}){Style.RESET}")
    print(f"{Style.YELLOW}Le esecuzioni già presenti in {CAMPAIGN_RESULTS} vengono saltate: "
          f"si può interrompere con Ctrl+C e riprendere.{Style.RESET}")

    if not confirm("Avvio la campagna completa?", default="n"):
        return

    manifest = CAMPAIGN_INSTANCES / "manifest.csv"
    try:
        if not manifest.exists():
            subprocess.run([sys.executable, "-m", "scripts.gen_instances",
                            "--config", str(DESIGN), "--out", str(CAMPAIGN_INSTANCES)], check=True)
        subprocess.run([sys.executable, "-m", "scripts.run_experiments",
                        "--manifest", str(manifest), "--out", str(CAMPAIGN_RESULTS),
                        "--time-limit", str(CAMPAIGN_TIME_LIMIT)], check=True)
    except KeyboardInterrupt:
        print(f"\n{Style.YELLOW}Campagna interrotta: scegliendo di nuovo questa voce "
              f"riprende da qui.{Style.RESET}")
    except subprocess.CalledProcessError as exc:
        print(f"\n{Style.RED}Errore: lo script si è fermato (codice {exc.returncode}).{Style.RESET}")


def demo() -> None:
    """Voce 2: demo rapida, senza domande."""
    methods = list(METHODS)
    groups = [g for _, g in DEMO_GROUPS]
    estimate, worst = duration(groups, 1, methods, DEMO_TIME_LIMIT)

    print(f"\n{Style.BOLD}Demo rapida{Style.RESET} (3 istanze da 50 task, "
          f"{len(PLI)} PLI e {len(HEURISTICS)} euristiche)")
    print(f"{Style.DIM}Limite di tempo: {DEMO_TIME_LIMIT:g} secondi per ogni PLI | "
          f"Durata stimata: {fmt_time(estimate)} (massima {fmt_time(worst)}){Style.RESET}\n")
    print_groups(groups, notes=[text for text, _ in DEMO_GROUPS])

    rows = run(groups, 1, methods, DEMO_TIME_LIMIT)
    if rows:
        summary(rows, methods)


def custom() -> None:
    """Voce 3: scelta di metodi, limite di tempo e parametri delle istanze."""
    choice = choose(
        "Metodi da eseguire",
        ["Solo i modelli PLI (soluzione esatta, con limite di tempo)",
         "Solo le euristiche (soluzione approssimata, immediata)",
         f"Tutti ({len(PLI)} PLI e {len(HEURISTICS)} euristiche)",
         "Scelgo i singoli metodi"],
        default=3,
    )

    if choice == 1:
        methods = list(PLI)
    elif choice == 2:
        methods = list(HEURISTICS)
    elif choice == 3:
        methods = list(METHODS)
    else:
        names = list(METHODS)
        print()
        for k, name in enumerate(names, 1):
            print(f"  {Style.CYAN}{k}){Style.RESET} {LABELS.get(name, name)}")
        while True:
            raw = ask("Numeri dei metodi, separati da virgola (es. 1,3)",
                      ",".join(str(k) for k in range(1, len(names) + 1)))
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            if parts and all(p.isdigit() and 1 <= int(p) <= len(names) for p in parts):
                methods = list(dict.fromkeys(names[int(p) - 1] for p in parts))
                break
            print(f"  {Style.RED}Scelta non valida, riprova.{Style.RESET}")

    time_limit = 0.0
    if any(m in PLI for m in methods):
        print(f"\n{Style.BOLD}{Style.MAGENTA}== Limite di tempo per ogni PLI{Style.RESET}")
        print(f"  {Style.DIM}Allo scadere il PLI restituisce la miglior soluzione trovata "
              f"e il lower bound.{Style.RESET}")
        time_limit = ask_float("Secondi (Invio per il valore proposto)", DEFAULT_TIME_LIMIT)

    values = {key: ask_parameter(title, text, variants, parse)
              for key, title, text, variants, parse in PARAMETERS}

    print(f"\n{Style.BOLD}{Style.MAGENTA}== Istanze per combinazione{Style.RESET}")
    print(f"  {Style.DIM}Quante istanze generare per ogni combinazione di parametri: "
          f"i risultati in tabella sono medie su queste istanze.{Style.RESET}")
    per_group = ask_int("Numero", 1, 1, 100)

    keys = [key for key, *_ in PARAMETERS]
    groups = [dict(zip(keys, combo)) for combo in itertools.product(*(values[k] for k in keys))]
    estimate, worst = duration(groups, per_group, methods, time_limit)

    print(f"\n{Style.BOLD}Riepilogo{Style.RESET}")
    print(f"{Style.DIM}{len(groups)} combinazioni x {per_group} istanze x {len(methods)} metodi "
          f"= {len(groups) * per_group * len(methods)} esecuzioni{Style.RESET}")
    print_groups(groups)
    print(f"{Style.BOLD}Durata stimata:{Style.RESET} {fmt_time(estimate)} "
          f"{Style.DIM}(massima {fmt_time(worst)}){Style.RESET}")

    if not confirm("Procedo con la generazione e l'esecuzione?"):
        return
    rows = run(groups, per_group, methods, time_limit)
    if rows:
        summary(rows, methods)


def pick_results() -> Path | None:
    """Fa scegliere uno dei file CSV in results/ (il più recente per primo)."""
    files = sorted(Path("results").glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        print(f"\n{Style.YELLOW}Nessun file di risultati in results/: esegui prima "
              f"la voce 1, 2 o 3.{Style.RESET}")
        return None
    labels = [
        f"{p.name:32s} {Style.DIM}{datetime.fromtimestamp(p.stat().st_mtime):%d/%m/%Y %H:%M}{Style.RESET}"
        for p in files
    ]
    return files[choose("File di risultati", labels) - 1]


def load_rows(path: Path) -> list[dict]:
    """Legge un CSV di risultati e riporta i numeri al loro tipo."""
    rows = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            for key in ("objective", "lower_bound"):
                row[key] = int(float(row[key])) if row.get(key) not in (None, "") else None
            row["time_s"] = float(row["time_s"]) if row.get("time_s") else 0.0
            rows.append(row)
    return rows


def show_results() -> None:
    """Voce 4: tabella riassuntiva di un file di risultati già prodotto."""
    path = pick_results()
    if path is None:
        return
    rows = load_rows(path)
    if not rows:
        print(f"\n{Style.YELLOW}{path} è vuoto.{Style.RESET}")
        return
    methods = [m for m in METHODS if any(r["method"] == m for r in rows)]
    instances = len({r["instance"] for r in rows})
    print(f"\n{Style.BOLD}{path}{Style.RESET} "
          f"{Style.DIM}({instances} istanze, {len(rows)} esecuzioni){Style.RESET}")
    summary(rows, methods)


def make_figures() -> None:
    """Voce 5: grafici e tabelle di un file di risultati, tramite scripts.make_figures."""
    path = pick_results()
    if path is None:
        return
    out = Path("results") / f"figures_{path.stem}"
    command = [sys.executable, "-m", "scripts.make_figures",
               "--results", str(path), "--out", str(out)]
    if path == CAMPAIGN_RESULTS:
        command += ["--time-limit", str(CAMPAIGN_TIME_LIMIT)]
    try:
        subprocess.run(command, check=True)
        print(f"\n{Style.GREEN}Grafici e tabelle in {out}/{Style.RESET}")
    except subprocess.CalledProcessError as exc:
        print(f"\n{Style.RED}Errore: lo script si è fermato (codice {exc.returncode}).{Style.RESET}")


def run_tests() -> None:
    """Voce 6: test del progetto (pytest)."""
    print(f"\n{Style.BOLD}Test del progetto (pytest){Style.RESET}")
    print(f"{Style.DIM}Ogni modello PLI è confrontato con l'ottimo calcolato per enumerazione "
          f"completa su istanze piccole.{Style.RESET}\n")
    result = subprocess.run([sys.executable, "-m", "pytest", "-q"])
    if result.returncode != 0:
        print(f"\n{Style.RED}Alcuni test non sono passati (codice {result.returncode}).{Style.RESET}")


def main() -> None:
    frame = f"{Style.BOLD}{Style.CYAN}{'=' * 74}{Style.RESET}"
    print(frame)
    print(f"{Style.BOLD}Progetto SALBP-2{Style.RESET}")
    print(f"{Style.DIM}Assegnare i task a m stazioni in sequenza, rispettando le precedenze,")
    print(f"minimizzando il carico massimo di stazione.{Style.RESET}")
    print(frame)

    actions = [campaign, demo, custom, show_results, make_figures, run_tests]
    while True:
        choice = choose(
            "Menù principale",
            ["Esegui tutti gli esperimenti (campagna completa, molte ore)",
             f"Demo rapida (3 istanze, {len(PLI)} PLI e {len(HEURISTICS)} euristiche, "
             f"al massimo {fmt_time(3 * len(PLI) * DEMO_TIME_LIMIT + 3)})",
             "Personalizzato (metodi, limite di tempo e parametri a scelta)",
             "Vedi risultati (tabella di un file già prodotto)",
             "Genera grafici e tabelle da un file di risultati",
             "Esegui i test (verifica di modelli ed euristiche)",
             f"{Style.RED}Esci{Style.RESET}"],
            default=2,
        )
        if choice == len(actions) + 1:
            print(f"\n{Style.DIM}Chiusura.{Style.RESET}")
            return
        actions[choice - 1]()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{Style.DIM}Interrotto. Uscita.{Style.RESET}")