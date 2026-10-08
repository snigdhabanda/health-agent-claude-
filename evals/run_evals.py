"""Run the eval: ask each model every question, grade every answer (plus Genie's), write results.md.

    python evals/run_evals.py                                   # all models + Genie, all questions
    python evals/run_evals.py --models claude-sonnet-5-5 --only q01 q13 --no-genie   # smoke test

Raw answers, SQL, and judge reasoning go to evals/runs/<timestamp>/ (gitignored: they hold real values).
results.md holds only pass rates, cost, and latency, so it is safe to commit.
"""

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

import anthropic
import yaml
from dotenv import load_dotenv

EVALS = Path(__file__).resolve().parent
ROOT = EVALS.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EVALS))
load_dotenv(ROOT / ".env")

from agent import DEFAULT_TOOLS, PRICES, TOOL_MODES, ask  # noqa: E402
from build_answers import ANSWERS, load_questions  # noqa: E402
from db import get_backend  # noqa: E402
from grader import JUDGE_MODEL, grade  # noqa: E402

MODELS = ["claude-haiku-4-5", "claude-sonnet-5-5", "claude-opus-5-5"]
GENIE_ANSWERS = EVALS / "genie_answers.local.yaml"
TIERS = ["lookup", "aggregate", "edge"]


def reference_for(answers: dict, qid: str):
    a = answers[qid]
    return a["expected"] if a.get("expected") is not None else a["rows"]


def run_model(model: str, questions: list[dict], client, backend, workers: int, system_prompt: str, tools: str) -> dict[str, dict]:
    def one(q):
        try:
            r = ask(q["question"], model=model, backend=backend, client=client, system_prompt=system_prompt, tools=tools)
            out = asdict(r) | {"cost_usd": r.cost_usd}
        except anthropic.APIError as e:
            out = {"answer": "", "error": f"{type(e).__name__}: {e}", "cost_usd": 0.0, "latency_s": 0.0, "queries": []}
        print(f"  {model} {q['id']} done ({out.get('latency_s', 0):.0f}s)", flush=True)
        return q["id"], out

    with ThreadPoolExecutor(workers) as pool:
        return dict(pool.map(one, questions))


def grade_all(label: str, answers_by_q: dict[str, str], questions, refs, client, workers) -> dict[str, dict]:
    def one(q):
        v = grade(client, q, reference_for(refs, q["id"]), answers_by_q.get(q["id"], ""))
        return q["id"], v.model_dump()

    print(f"  grading {label}...", flush=True)
    with ThreadPoolExecutor(workers) as pool:
        return dict(pool.map(one, questions))


def summarize(configs: dict, questions: list[dict], refs: dict) -> str:
    unchecked = [q["id"] for q in questions if not refs[q["id"]].get("checked")]
    tier_of = {q["id"]: q["tier"] for q in questions}
    probes_of = {q["id"]: q["probes"] for q in questions}
    lines = ["# Eval results", ""]
    if unchecked:
        lines += [f"> **Preliminary:** {len(unchecked)} of {len(questions)} reference answers aren't hand-checked yet.", ""]
    lines += [f"Questions: {len(questions)}. Judge: `{JUDGE_MODEL}`. Pass = fully correct; partial counts as a miss.", ""]

    header = ["Config", "Pass", "Partial", *[f"{t} pass" for t in TIERS], "$/question", "p50 latency", "SQL queries/q"]
    lines += ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for name, c in configs.items():
        g = c["grades"]
        n = len(g)
        passed = sum(v["verdict"] == "pass" for v in g.values())
        partial = sum(v["verdict"] == "partial" for v in g.values())
        tier_cells = []
        for t in TIERS:
            ids = [q for q in g if tier_of[q] == t]
            tier_cells.append(f"{sum(g[q]['verdict'] == 'pass' for q in ids)}/{len(ids)}" if ids else "–")
        runs = c.get("runs")
        if runs:
            cost = f"${statistics.mean(r['cost_usd'] for r in runs.values()):.4f}"
            lat = f"{statistics.median(r['latency_s'] for r in runs.values()):.1f}s"
            nq = f"{statistics.mean(len(r['queries']) for r in runs.values()):.1f}"
        else:
            cost = lat = nq = "n/a"
        lines.append(f"| {name} | {passed}/{n} ({passed / n:.0%}) | {partial} | " + " | ".join(tier_cells) + f" | {cost} | {lat} | {nq} |")

    lines += ["", "## Per question", ""]
    names = list(configs)
    lines += ["| Question | Probes | " + " | ".join(names) + " |", "|" + "---|" * (len(names) + 2)]
    mark = {"pass": "✅", "partial": "🟡", "fail": "❌"}
    for q in questions:
        cells = [mark[configs[n]["grades"][q["id"]]["verdict"]] for n in names]
        lines.append(f"| {q['id']} {q['question']} | {', '.join(probes_of[q['id']])} | " + " | ".join(cells) + " |")

    lines += ["", "## Misses by probe", ""]
    by_probe = defaultdict(Counter)
    for n in names:
        for qid, v in configs[n]["grades"].items():
            if v["verdict"] != "pass":
                for p in probes_of[qid]:
                    by_probe[p][n] += 1
    lines += ["| Probe | " + " | ".join(names) + " |", "|" + "---|" * (len(names) + 1)]
    for p in sorted(by_probe, key=lambda p: -sum(by_probe[p].values())):
        lines.append(f"| {p} | " + " | ".join(str(by_probe[p][n]) for n in names) + " |")

    lines += ["", "## Failure types", ""]
    lines += ["| Failure type | " + " | ".join(names) + " |", "|" + "---|" * (len(names) + 1)]
    ft = {n: Counter(v["failure_type"] for v in configs[n]["grades"].values() if v["verdict"] != "pass") for n in names}
    for f in sorted({f for c in ft.values() for f in c}):
        lines.append(f"| {f} | " + " | ".join(str(ft[n][f]) for n in names) + " |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="*", default=MODELS, choices=sorted(PRICES))
    parser.add_argument("--prompt", type=Path, default=ROOT / "system_prompt.md", help="system prompt file")
    parser.add_argument("--label", default="", help="suffix for config names, e.g. '+v2'")
    parser.add_argument("--tools", default=DEFAULT_TOOLS, choices=TOOL_MODES,
                        help="mcp: Databricks managed MCP server; run_sql: the hand-built tool used for the published results")
    parser.add_argument("--only", nargs="*", help="question ids")
    parser.add_argument("--no-genie", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--regrade", metavar="RUN_DIR", help="re-grade a saved run's answers without re-running the agents")
    args = parser.parse_args()

    questions = [q for q in load_questions(include_labs=False) if not args.only or q["id"] in args.only]
    refs = yaml.safe_load(ANSWERS.read_text())
    client = anthropic.Anthropic()
    backend = get_backend()
    run_dir = EVALS / "runs" / time.strftime("%Y%m%d-%H%M%S")
    if not args.regrade:
        run_dir.mkdir(parents=True)

    configs = {}
    if args.regrade:
        saved = json.loads((Path(args.regrade) / "results.json").read_text())
        for name, c in saved.items():
            answers = c["answers"] if "runs" not in c else {qid: r["answer"] for qid, r in c["runs"].items()}
            answers = {qid: a for qid, a in answers.items() if qid in {q["id"] for q in questions}}
            configs[name] = c | {"grades": grade_all(name, answers, [q for q in questions if q["id"] in answers], refs, client, args.workers)}
            if "runs" in c:
                configs[name]["runs"] = {qid: r for qid, r in c["runs"].items() if qid in answers}
        args.models, args.no_genie = [], True
        run_dir = run_dir.with_name(run_dir.name + "-regrade")
        run_dir.mkdir()
    if not args.no_genie:
        genie = yaml.safe_load(GENIE_ANSWERS.read_text())
        configs["genie"] = {"answers": genie, "grades": grade_all("genie", genie, questions, refs, client, args.workers)}
    for model in args.models:
        name = model + args.label
        print(f"running {name} on {len(questions)} questions", flush=True)
        runs = run_model(model, questions, client, backend, args.workers, args.prompt.read_text(), args.tools)
        answers = {qid: r["answer"] for qid, r in runs.items()}
        configs[name] = {"runs": runs, "prompt": args.prompt.name, "tools": args.tools, "grades": grade_all(name, answers, questions, refs, client, args.workers)}

    (run_dir / "results.json").write_text(json.dumps(configs, indent=1, default=str))
    report = summarize(configs, questions, refs)
    (run_dir / "results.md").write_text(report)
    if not args.only and not args.label:
        (EVALS / "results.md").write_text(report)
    print(report)
    total = sum(r["cost_usd"] for c in configs.values() for r in c.get("runs", {}).values())
    print(f"agent cost: ${total:.2f} (judge cost not included)  raw: {run_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
