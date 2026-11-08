"""Charts from a summary.csv written by `python run.py report <run_dir>`.

Input columns (written by run.py cmd_report, one row per trial):
  model, scenario, trial, harness_error, prompt_tokens, completion_tokens, cost_usd,
  strict, task, trusted, report, failed_checks
  strict/task/trusted/report are "True"/"False" for graded trials. Rows with a non-empty
  harness_error are excluded from all rates (same policy as REPORT.md).

Usage:
  python scripts/make_charts.py [path/to/summary.csv] [out_dir]
  Default input: results/summary.csv, else the newest results/raw/*/summary.csv.
  Default out_dir: docs/img/
Writes:
  pass_rates_by_model.png        grouped bars: Task / Trusted / Report fidelity per model
  heatmap_scenario_by_model.png  strict pass rate per scenario x model (passed/trials annotated)
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def find_csv(arg):
    if arg:
        return Path(arg)
    p = ROOT / "results" / "summary.csv"
    if p.exists():
        return p
    runs = sorted((ROOT / "results" / "raw").glob("*/summary.csv"))
    return runs[-1] if runs else p


def load(path):
    with open(path, newline="") as f:
        return [r for r in csv.DictReader(f) if not r.get("harness_error")]


def aggregate(rows):
    by_model = defaultdict(lambda: defaultdict(list))  # model -> metric -> [bool]
    by_cell = defaultdict(list)                        # (model, scenario) -> [strict bool]
    for r in rows:
        for m in ("task", "trusted", "report"):
            by_model[r["model"]][m].append(r[m] == "True")
        by_cell[(r["model"], r["scenario"])].append(r["strict"] == "True")
    return by_model, by_cell


def plot_models(by_model, models, out):
    labels = [("task", "Task"), ("trusted", "Trusted"), ("report", "Report fidelity")]
    width = 0.27
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, (key, label) in enumerate(labels):
        vals = [100 * sum(by_model[m][key]) / len(by_model[m][key]) for m in models]
        xs = [j + (i - 1) * width for j in range(len(models))]
        ax.bar(xs, vals, width, label=label)
        for x, v in zip(xs, vals):
            ax.text(x, v + 1, f"{v:.0f}%", ha="center", fontsize=8)
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels([f"{m}\n(n={len(by_model[m]['task'])} trials)" for m in models], fontsize=8)
    ax.set_ylim(0, 110)
    ax.set_ylabel("Per-trial pass rate (%)")
    ax.set_title("Front Desk Bench: pass rate by verdict and model")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def plot_heatmap(by_cell, models, scenarios, out):
    values, labels = [], []
    for s in scenarios:
        row_v, row_l = [], []
        for m in models:
            xs = by_cell.get((m, s), [])
            row_v.append(sum(xs) / len(xs) if xs else float("nan"))
            row_l.append(f"{sum(xs)}/{len(xs)}" if xs else "-")
        values.append(row_v)
        labels.append(row_l)
    fig, ax = plt.subplots(figsize=(1.8 + 2.2 * len(models), 1.2 + 0.7 * len(scenarios)))
    im = ax.imshow(values, vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
    for i in range(len(scenarios)):
        for j in range(len(models)):
            ax.text(j, i, labels[i][j], ha="center", va="center", fontsize=9)
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(models, rotation=20, ha="right", fontsize=8)
    ax.set_yticks(range(len(scenarios)))
    ax.set_yticklabels(scenarios, fontsize=8)
    ax.set_title("Strict pass (task + trusted + report) per scenario")
    fig.colorbar(im, ax=ax, label="strict pass rate")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main():
    src = find_csv(sys.argv[1] if len(sys.argv) > 1 else None)
    if not src.exists():
        print(f"summary.csv not found at {src}. Run `python run.py run ...` then "
              f"`python run.py report results/raw/<run_id>` first, or pass the CSV path.")
        sys.exit(1)
    rows = load(src)
    if not rows:
        print(f"{src} has no graded trials (every row is a harness error or the file is empty).")
        sys.exit(1)
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs" / "img"
    out_dir.mkdir(parents=True, exist_ok=True)
    by_model, by_cell = aggregate(rows)
    models = sorted(by_model)
    scenarios = sorted({r["scenario"] for r in rows})
    plot_models(by_model, models, out_dir / "pass_rates_by_model.png")
    plot_heatmap(by_cell, models, scenarios, out_dir / "heatmap_scenario_by_model.png")
    print(f"read {len(rows)} graded trials from {src}")
    print(f"wrote {out_dir / 'pass_rates_by_model.png'}")
    print(f"wrote {out_dir / 'heatmap_scenario_by_model.png'}")


if __name__ == "__main__":
    main()
