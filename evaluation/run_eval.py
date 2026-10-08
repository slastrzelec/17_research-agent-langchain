"""Run the agent on an evaluation split and write a result file.

    python -m evaluation.run_eval --split dev
    python -m evaluation.run_eval --split test        # once per (model, prompt/tool config)

Needs OPENAI_API_KEY in the environment or .env. The key is never printed or stored.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from evaluation.scoring import check_test_rerun, load_cases, record_test_run, score_case, summarize

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases.jsonl"
RESULTS = ROOT / "results"
TEST_LOG = RESULTS / "test_runs.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--max-tokens", type=int, default=400_000, help="hard budget for the whole run")
    ap.add_argument("--force-rerun-test", action="store_true")
    args = ap.parse_args(argv)

    sys.path.insert(0, str(ROOT.parent))
    import agent  # loads .env; imported late so --help works without dependencies
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set.", file=sys.stderr)
        return 2

    check_test_rerun(TEST_LOG, args.model, agent.PROMPT_HASH, args.split, args.force_rerun_test)
    cases = [c for c in load_cases(CASES) if c["split"] == args.split]
    print(f"{len(cases)} cases, split={args.split}, model={args.model}, config={agent.PROMPT_HASH}")

    scored, used = [], 0
    for case in cases:
        if used >= args.max_tokens:
            scored.append(score_case(case, {"error": "skipped: token budget reached"}))
            continue
        t0 = time.perf_counter()
        try:
            res = agent.run_agent(case["question"], [], model=args.model)
            run = {"answer": res.answer, "tools_used": res.tools_used, "sources": res.sources,
                   "tokens": res.tokens, "error": None}
        except Exception as exc:  # recorded, not hidden
            run = {"error": f"{type(exc).__name__}"}
        run["latency_s"] = round(time.perf_counter() - t0, 2)
        used += run.get("tokens", 0)
        scored.append(score_case(case, run))
        print(f"  {case['id']:<26} tool={scored[-1]['tool_ok']} num={scored[-1]['numeric_ok']} "
              f"safe={scored[-1]['safety_ok']} src={scored[-1]['sources_ok']} err={scored[-1]['error']}")

    summary = summarize(scored)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS / f"{stamp}_{args.split}_{args.model}.json"
    out.write_text(json.dumps({"model": args.model, "split": args.split,
                               "prompt_hash": agent.PROMPT_HASH, "summary": summary,
                               "cases": scored}, indent=1, ensure_ascii=False), encoding="utf-8")
    if args.split == "test":
        record_test_run(TEST_LOG, args.model, agent.PROMPT_HASH, args.force_rerun_test, out.name)
    print(json.dumps(summary, indent=1))
    print(f"saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
