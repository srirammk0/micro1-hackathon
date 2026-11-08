"""Front Desk Bench CLI.

  python run.py selftest                         # graders vs reference/negative trajectories, no API
  python run.py run --models M1,M2 --trials 5    # live runs via OpenRouter -> results/raw/<run_id>/
  python run.py grade results/raw/<run_id>       # regrade saved raw outputs offline
  python run.py report results/raw/<run_id>      # summary.csv + REPORT.md generated from raw
"""
import argparse
import csv
import json
import os
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from frontdesk.agent import all_scenarios, load_scenario, run_llm
from frontdesk.grade import grade
from frontdesk.sandbox import Sandbox

ROOT = Path(__file__).resolve().parent
DEFAULT_MODELS = "openai/gpt-6-luna,anthropic/claude-haiku-5.5,deepseek/deepseek-v4.1-flash,z-ai/glm-5.3-flash"


def load_dotenv():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def rebuild(rec):
    """Rebuild a sandbox from a saved record (state + log) so it can be regraded offline."""
    scen = load_scenario(rec["scenario"])
    sb = Sandbox(scen)
    for step in scen["timeline"]:  # out-of-band bookings count as pre-existing, exactly as apply_step does live
        for e in step["events"]:
            if e["type"] == "world":
                sb.initial_appts[e["appointment"]["id"]] = {**e["appointment"], "status": "booked"}
    st = rec["final_state"]
    sb.clients, sb.appts, sb.followups = st["clients"], st["appointments"], st["followups"]
    sb.threads, sb.drafts, sb.owner_inbox, sb.report = st["threads"], st["drafts"], st["owner_inbox"], st["report"]
    sb.log, sb.now = rec["log"], sb.t(st["now"])
    return sb


def cmd_run(a):
    load_dotenv()
    models = a.models.split(",")
    scenarios = [load_scenario(s) for s in a.scenarios.split(",")] if a.scenarios else all_scenarios()
    settings = {"max_tokens": a.max_tokens}
    if a.temperature is not None:
        settings["temperature"] = a.temperature
    run_id = a.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "results" / "raw" / run_id
    jobs = [(m, s, t) for m in models for s in scenarios for t in range(1, a.trials + 1)]
    todo = [j for j in jobs if not (out / j[0].replace("/", "__") / j[1]["id"] / f"trial_{j[2]}.json").exists()]
    print(f"run {run_id}: {len(todo)}/{len(jobs)} trials to do -> {out}")

    def one(m, s, t):
        path = out / m.replace("/", "__") / s["id"] / f"trial_{t}.json"
        sb, rec = run_llm(s, m, settings)
        rec["trial"] = t
        rec["grade"] = None if rec["harness_error"] else grade(sb, s["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, indent=1, default=str))
        g = rec["grade"]
        return f"{m:34} {s['id']:24} t{t}  " + ("HARNESS_ERROR " + rec["harness_error"] if not g else
                                                  f"strict={g['strict_pass']!s:5} task={g['task_pass']!s:5} "
                                                  f"trusted={g['trusted_pass']!s:5} report={g['report_pass']}")

    with ThreadPoolExecutor(a.workers) as ex:
        for f in as_completed([ex.submit(one, *j) for j in todo]):
            try:
                print(f.result(), flush=True)
            except Exception as e:
                print(f"!! {type(e).__name__}: {e}", flush=True)
    cmd_report(argparse.Namespace(run_dir=str(out)))


def records(run_dir):
    for p in sorted(Path(run_dir).glob("*/*/trial_*.json")):
        yield p, json.loads(p.read_text())


def cmd_grade(a):
    for p, rec in records(a.run_dir):
        if not rec["harness_error"]:
            rec["grade"] = grade(rebuild(rec), rec["scenario"])
            p.write_text(json.dumps(rec, indent=1, default=str))
    cmd_report(a)


def cmd_report(a):
    rows, by = [], defaultdict(list)
    for p, rec in records(a.run_dir):
        g = rec["grade"]
        usage = [c["usage"] for c in rec["calls"] if c.get("usage")]
        row = {"model": rec["model"], "scenario": rec["scenario"], "trial": rec["trial"],
               "harness_error": rec["harness_error"] or "",
               "prompt_tokens": sum(u.get("prompt_tokens") or 0 for u in usage),
               "completion_tokens": sum(u.get("completion_tokens") or 0 for u in usage),
               "cost_usd": round(sum(u.get("cost") or 0 for u in usage), 5)}
        if g:
            row.update(strict=g["strict_pass"], task=g["task_pass"], trusted=g["trusted_pass"], report=g["report_pass"],
                       failed_checks=";".join(k for part in ("task", "trusted", "report")
                                              for k, ok in g[part].items() if not ok))
            by[(rec["model"], rec["scenario"])].append(g)
        rows.append(row)
    if not rows:
        return print("no records")
    run_dir = Path(a.run_dir)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(run_dir / "summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(rows)

    models = sorted({m for m, _ in by})
    scen = sorted({s for _, s in by})
    pct = lambda xs: f"{100 * sum(xs) / len(xs):.0f}%" if xs else "-"
    L = [f"# Results: {run_dir.name}", "",
         "Generated by `python run.py report` from raw trial files. Harness/API errors are excluded from rates and counted separately.", "",
         "## Per model (all scenarios)", "",
         "| model | trials | strict pass | task | trusted | report fidelity | pass@k (scenarios with >=1 strict pass) | pass^k (scenarios with all strict pass) | harness errors | cost $ |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for m in models:
        gs = [g for (mm, _), v in by.items() if mm == m for g in v]
        groups = [v for (mm, _), v in by.items() if mm == m]
        errs = sum(1 for r in rows if r["model"] == m and r["harness_error"])
        cost = sum(r["cost_usd"] for r in rows if r["model"] == m)
        L.append(f"| {m} | {len(gs)} | {pct([g['strict_pass'] for g in gs])} | {pct([g['task_pass'] for g in gs])} | "
                 f"{pct([g['trusted_pass'] for g in gs])} | {pct([g['report_pass'] for g in gs])} | "
                 f"{sum(any(g['strict_pass'] for g in v) for v in groups)}/{len(groups)} | "
                 f"{sum(all(g['strict_pass'] for g in v) for v in groups)}/{len(groups)} | {errs} | {cost:.2f} |")
    L += ["", "## Strict passes per scenario (passed/trials)", "", "| scenario | " + " | ".join(models) + " |",
          "|---|" + "---|" * len(models)]
    for s in scen:
        L.append(f"| {s} | " + " | ".join(
            f"{sum(g['strict_pass'] for g in by.get((m, s), []))}/{len(by.get((m, s), []))}" for m in models) + " |")
    L += ["", "## Most frequently failed checks", "", "| model | check | failures |", "|---|---|---|"]
    for m in models:
        cnt = defaultdict(int)
        for (mm, s), v in by.items():
            if mm == m:
                for g in v:
                    for part in ("task", "trusted", "report"):
                        for k, ok in g[part].items():
                            cnt[f"{s}:{k}"] += not ok
        for k, n in sorted(cnt.items(), key=lambda kv: -kv[1])[:8]:
            if n:
                L.append(f"| {m} | {k} | {n} |")
    (run_dir / "REPORT.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    r = sub.add_parser("run")
    r.add_argument("--models", default=DEFAULT_MODELS)
    r.add_argument("--scenarios", default="")
    r.add_argument("--trials", type=int, default=5)
    r.add_argument("--workers", type=int, default=8)
    r.add_argument("--max-tokens", type=int, default=4096)
    r.add_argument("--temperature", type=float, default=None)
    r.add_argument("--run-id", default="")
    for name in ("grade", "report"):
        sub.add_parser(name).add_argument("run_dir")
    a = ap.parse_args()
    if a.cmd == "selftest":
        sys.exit(subprocess.call([sys.executable, "-m", "pytest", "-q", str(ROOT / "tests")]))
    {"run": cmd_run, "grade": cmd_grade, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
