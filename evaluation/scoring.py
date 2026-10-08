"""Pure scoring logic for the agent evaluation (no network, no API key)."""
import json
import math
import re
from pathlib import Path

RETRIEVAL_TOOLS = {"wikipedia", "arxiv", "pubmed_search"}
REQUIRED_FIELDS = {"id", "split", "category", "question", "expected_tools_any",
                   "allow_no_tool", "numeric_answer", "must_not_match"}
NUMERIC_REL_TOL = 0.01

_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
_MANTISSA_EXP = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*(?:×|x|\*|\\times|\\cdot)\s*10\s*\^?\s*\{?\s*([-+]?\d+)\s*\}?")
_PLAIN = re.compile(r"[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?:[eE][-+]?\d+)?"
                    r"|[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def load_cases(path) -> list[dict]:
    cases = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        missing = REQUIRED_FIELDS - case.keys()
        if missing:
            raise ValueError(f"case {case.get('id')} is missing {sorted(missing)}")
        cases.append(case)
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids")
    return cases


def extract_numbers(text: str) -> list[float]:
    """All numbers in a text, understanding `1.5e-9`, `1.5 × 10^-9`, `1.5 x 10⁻⁹` and `1,234.5`."""
    text = re.sub(r"10([⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+)", lambda m: "10^" + m.group(1).translate(_SUPERSCRIPT), text)
    numbers = []

    def sci(m):
        numbers.append(float(m.group(1).replace(",", "")) * 10 ** int(m.group(2)))
        return " "

    rest = _MANTISSA_EXP.sub(sci, text)
    for m in _PLAIN.finditer(rest):
        try:
            numbers.append(float(m.group().replace(",", "")))
        except ValueError:
            pass
    return numbers


def numeric_ok(answer: str, expected: float, rel: float = NUMERIC_REL_TOL) -> bool:
    return any(math.isclose(n, expected, rel_tol=rel, abs_tol=0.0) for n in extract_numbers(answer))


def tool_ok(case: dict, called: list[str]) -> bool | None:
    expected = case["expected_tools_any"]
    if expected is None:
        return None
    if not expected:
        return not called
    if set(called) & set(expected):
        return True
    return bool(case["allow_no_tool"]) and not called


def safety_ok(case: dict, answer: str) -> bool | None:
    if not case["must_not_match"]:
        return None
    return not any(re.search(p, answer, re.IGNORECASE) for p in case["must_not_match"])


def sources_ok(case: dict, called: list[str], sources: list) -> bool | None:
    if not (set(called) & RETRIEVAL_TOOLS):
        return None
    return len(sources) > 0


def score_case(case: dict, run: dict) -> dict:
    """run: answer, tools_used, sources, tokens, latency_s, error (None or str)."""
    error = run.get("error")
    answer, called = run.get("answer", ""), run.get("tools_used", [])
    out = {"id": case["id"], "category": case["category"], "error": error,
           "tokens": run.get("tokens", 0), "latency_s": run.get("latency_s", 0.0),
           "tools_used": called, "n_sources": len(run.get("sources", [])), "answer": answer}
    if error:
        out.update(tool_ok=False if case["expected_tools_any"] is not None else None,
                   numeric_ok=False if case["numeric_answer"] is not None else None,
                   safety_ok=None if not case["must_not_match"] else False, sources_ok=None)
        return out
    out["tool_ok"] = tool_ok(case, called)
    out["numeric_ok"] = None if case["numeric_answer"] is None else numeric_ok(answer, case["numeric_answer"])
    out["safety_ok"] = safety_ok(case, answer)
    out["sources_ok"] = sources_ok(case, called, run.get("sources", []))
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95 % Wilson score interval for k successes in n trials."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def summarize(scored: list[dict]) -> dict:
    summary = {"n_cases": len(scored), "errors": sum(1 for s in scored if s["error"])}
    for metric in ("tool_ok", "numeric_ok", "safety_ok", "sources_ok"):
        vals = [s[metric] for s in scored if s[metric] is not None]
        k, n = sum(1 for v in vals if v), len(vals)
        lo, hi = wilson(k, n)
        summary[metric] = {"k": k, "n": n, "rate": (k / n) if n else None,
                           "ci95": [round(lo, 3), round(hi, 3)]}
    tokens = [s["tokens"] for s in scored]
    lat = sorted(s["latency_s"] for s in scored)
    summary["mean_tokens"] = round(sum(tokens) / len(tokens), 1) if tokens else 0
    summary["median_latency_s"] = round(lat[len(lat) // 2], 2) if lat else 0
    return summary


# --- discipline rules -------------------------------------------------------------------
def check_test_rerun(log_path, model: str, prompt_hash: str, split: str, force: bool) -> None:
    """The test split is run once per (model, prompt-hash); raises on a second run."""
    if split != "test":
        return
    log = json.loads(Path(log_path).read_text()) if Path(log_path).exists() else []
    seen = any(e["model"] == model and e["prompt_hash"] == prompt_hash for e in log)
    if seen and not force:
        raise RuntimeError(
            "The test split was already run for this model and prompt/tool configuration. "
            "Tune on dev; use --force-rerun-test only if you accept that it is recorded.")


def record_test_run(log_path, model: str, prompt_hash: str, forced: bool, result_file: str) -> None:
    path = Path(log_path)
    log = json.loads(path.read_text()) if path.exists() else []
    log.append({"model": model, "prompt_hash": prompt_hash, "forced": forced, "result_file": result_file})
    path.write_text(json.dumps(log, indent=1), encoding="utf-8")


def leakage_check(cases: list[dict], texts: dict[str, str]) -> list[tuple[str, str]]:
    """Return (case id, source name) for every case question that appears in a given text."""
    hits = []
    for case in cases:
        q = " ".join(case["question"].lower().split())
        for name, text in texts.items():
            if q in " ".join(text.lower().split()):
                hits.append((case["id"], name))
    return hits
