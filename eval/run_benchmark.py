"""Run the benchmark: retrieval ablations + end-to-end agent evaluation.

    python -m eval.run_benchmark --setup                 # ingest sample corpus + demo users first
    python -m eval.run_benchmark                         # full run, default settings from .env
    python -m eval.run_benchmark --limit 40 --judge      # quick run with LLM-as-judge
    python -m eval.run_benchmark --skip-agent            # retrieval metrics only (no LLM cost)

Outputs eval/reports/<timestamp>/{report.md, summary.json, results.jsonl}.

Measured
  retrieval   hit@k, recall@k, MRR@10, nDCG@10, doc_hit@k for vector / keyword / hybrid / hybrid+rerank
  answers     accuracy (required facts present), abstention precision/recall, ACL leak rate,
              optional LLM-judge correctness
  citations   precision (cited source supports the evidence), doc precision, recall
  latency     p50 / p95 / mean, per-stage means
  cost        tokens and USD (per question and total)
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import statistics
import time

from app.agent import answer_question
from app.auth import get_user_groups
from app.config import settings
from app.retrieval import MODES, search
from eval.metrics import (citation_metrics, facts_score, fact_present, percentile, retrieval_metrics,
                          slug_of)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ANSWERABLE = {"factual", "table", "structured", "multi_hop", "catalog"}
NEGATIVE = {"unanswerable", "access_denied"}


def load(path: Path, limit: int | None, categories: set[str] | None) -> list[dict]:
    items = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if categories:
        items = [i for i in items if i["category"] in categories]
    if limit:
        # stratified: keep category mix when limiting
        by = defaultdict(list)
        for i in items:
            by[i["category"]].append(i)
        frac = limit / len(items)
        items = [x for cat in by.values() for x in cat[: max(1, round(len(cat) * frac))]]
    return items


def setup_corpus() -> None:
    from app.ingest.pipeline import ingest_manifest
    from scripts.seed_users import main as seed

    for r in ingest_manifest(ROOT / "data" / "sample" / "manifest.json"):
        print(f"  [{r.status}] {r.title}")
    seed([])


# ------------------------------------------------------------------ retrieval --
def eval_retrieval(items: list[dict], modes: list[str], groups_of) -> dict:
    out = {}
    for mode in modes:
        rows, lat = [], []
        for it in items:
            if it["category"] not in ANSWERABLE or not it["evidence"]:
                continue
            groups = groups_of(it["user"])
            per_ev_tables = {"records" if slug.startswith(("kpi-", "office-", "compensation-")) else "chunks"
                             for slug in it["relevant_docs"]}
            t0 = time.perf_counter()
            results = []
            for table in sorted(per_ev_tables):
                hits = search(it["question"], groups, table=table, mode=mode, top_k=10)
                results += [{"text": h.text, "source_uri": h.source_uri, "score": h.score} for h in hits]
            lat.append((time.perf_counter() - t0) * 1000)
            if len(per_ev_tables) > 1:  # multi-source: interleave by score
                results.sort(key=lambda r: -r["score"])
            m = retrieval_metrics(results[:10], it["evidence"], it["relevant_docs"])
            m["category"] = it["category"]
            rows.append(m)
        keys = [k for k in rows[0] if k != "category"] if rows else []
        out[mode] = {k: statistics.mean(r[k] for r in rows) for k in keys}
        out[mode]["n"] = len(rows)
        out[mode]["latency_ms_p50"] = percentile(lat, 50)
        out[mode]["latency_ms_p95"] = percentile(lat, 95)
    return out


# ---------------------------------------------------------------- end-to-end --
JUDGE_PROMPT = """You grade answers from an enterprise assistant against a reference answer.
Question: {q}
Reference answer: {ref}
Assistant answer: {ans}
Return JSON: {{"verdict": "correct" | "partial" | "incorrect", "reason": "<short>"}}.
"correct" = all key facts of the reference are stated and nothing contradicts it."""


def judge(it: dict, answer: str) -> dict:
    from app.llm import chat_json

    res, usage = chat_json([{"role": "user", "content": JUDGE_PROMPT.format(
        q=it["question"], ref=it["reference_answer"], ans=answer)}], max_tokens=150)
    return {"verdict": res.get("verdict", "incorrect"), "reason": res.get("reason", ""),
            "judge_input_tokens": usage.input_tokens, "judge_output_tokens": usage.output_tokens}


def eval_agent(items: list[dict], mode: str, groups_of, use_judge: bool) -> list[dict]:
    rows = []
    for n, it in enumerate(items, 1):
        groups = groups_of(it["user"])
        try:
            r = answer_question(it["question"], groups, mode=mode, include_source_text=True)
        except Exception as e:  # count crashes as failures, keep going
            rows.append({**it, "error": str(e)[:300], "correct": False, "abstained": False})
            continue
        src_by_sid = {s["sid"]: s for s in r["retrieved"]}
        cited_slugs = {slug_of(c["source_uri"]) for c in r["citations"]}
        row = {
            "id": it["id"], "category": it["category"], "user": it["user"], "question": it["question"],
            "answer": r["answer"], "abstained": r["abstained"], "abstain_reason": r["abstain_reason"],
            "citations": [{k: c[k] for k in ("sid", "title", "source_uri", "section", "page", "support")}
                          for c in r["citations"]],
            "rounds": r["rounds"], "tool_calls": [t["name"] for t in r["tool_calls"]],
            "latency_ms": r["timings"]["total_ms"], "timings": r["timings"], "usage": r["usage"],
        }
        if it["category"] in ANSWERABLE:
            fs = facts_score(it["must_include"], r["answer"]) if not r["abstained"] else 0.0
            row["facts_score"] = fs
            row["correct"] = (not r["abstained"]) and fs == 1.0
            row.update(citation_metrics(r["citations"], src_by_sid, it["evidence"], it["relevant_docs"])
                       if not r["abstained"] else {})
        else:
            row["correct"] = r["abstained"]
        if it["category"] == "access_denied":
            leaked_fact = any(fact_present(f, r["answer"]) for f in it["forbidden"]) and not r["abstained"]
            leaked_src = any(slug_of(s["source_uri"]) == it["restricted_doc"] for s in r["retrieved"])
            row["leak"] = leaked_fact or leaked_src or it["restricted_doc"] in cited_slugs
            row["acl_violation"] = leaked_src
        if use_judge and settings.llm_enabled and it["category"] in ANSWERABLE and not r["abstained"]:
            row.update(judge(it, r["answer"]))
        rows.append(row)
        mark = "ok " if row["correct"] else "BAD"
        print(f"  {mark} {it['id']} [{it['category']:<13}] {r['timings']['total_ms']:>7.0f}ms  {it['question'][:70]}")
    return rows


def summarize(rows: list[dict]) -> dict:
    ok_rows = [r for r in rows if "error" not in r]
    ans = [r for r in ok_rows if r["category"] in ANSWERABLE]
    neg = [r for r in ok_rows if r["category"] in NEGATIVE]
    answered = [r for r in ans if not r["abstained"]]
    abst_all = [r for r in ok_rows if r["abstained"]]
    lat = [r["latency_ms"] for r in ok_rows]

    def mean(xs):
        xs = list(xs)
        return statistics.mean(xs) if xs else 0.0

    by_cat = {}
    for cat in sorted({r["category"] for r in rows}):
        rs = [r for r in rows if r["category"] == cat]
        by_cat[cat] = {"n": len(rs), "accuracy": mean(r["correct"] for r in rs),
                       "abstain_rate": mean(r.get("abstained", False) for r in rs),
                       "latency_ms_p50": percentile([r["latency_ms"] for r in rs if "latency_ms" in r], 50)}
    stages = defaultdict(list)
    for r in ok_rows:
        for k, v in r["timings"].items():
            stages[k].append(v)
    judged = [r for r in answered if "verdict" in r]
    s = {
        "n_questions": len(rows), "errors": len(rows) - len(ok_rows),
        "overall_accuracy": mean(r["correct"] for r in rows),
        "answerable_accuracy": mean(r["correct"] for r in ans),
        "answerable_facts_score": mean(r.get("facts_score", 0) for r in ans),
        "false_abstention_rate": mean(r["abstained"] for r in ans),
        "abstention_recall": mean(r["abstained"] for r in neg),          # refused when it should
        "abstention_precision": (sum(r["category"] in NEGATIVE for r in abst_all) / len(abst_all)) if abst_all else 0.0,
        "hallucination_rate_on_negatives": mean(not r["abstained"] for r in neg),
        "acl_leak_rate": mean(r["leak"] for r in ok_rows if r["category"] == "access_denied"),
        "acl_violations": sum(r.get("acl_violation", False) for r in ok_rows),
        "citation_precision": mean(r["cit_precision"] for r in answered),
        "citation_doc_precision": mean(r["cit_doc_precision"] for r in answered),
        "citation_recall": mean(r["cit_recall"] for r in answered),
        "answers_with_citations": mean(r.get("n_citations", 0) > 0 for r in answered),
        "latency_ms_p50": percentile(lat, 50), "latency_ms_p95": percentile(lat, 95), "latency_ms_mean": mean(lat),
        "stage_ms_mean": {k: round(mean(v), 1) for k, v in sorted(stages.items())},
        "input_tokens": sum(r["usage"]["input_tokens"] for r in ok_rows),
        "output_tokens": sum(r["usage"]["output_tokens"] for r in ok_rows),
        "cost_usd_total": sum(r["usage"]["cost_usd"] for r in ok_rows),
        "cost_usd_per_question": mean(r["usage"]["cost_usd"] for r in ok_rows),
        "llm_calls_per_question": mean(r["usage"]["llm_calls"] for r in ok_rows),
        "by_category": by_cat,
    }
    if judged:
        s["judge_correct"] = mean(r["verdict"] == "correct" for r in judged)
        s["judge_partial"] = mean(r["verdict"] == "partial" for r in judged)
    return s


# ------------------------------------------------------------------- report ---
def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def render(config: dict, retr: dict, summ: dict | None, rows: list[dict]) -> str:
    L = [f"# Benchmark report — {config['timestamp']}", ""]
    L += ["## Configuration", "", "| setting | value |", "|---|---|"]
    L += [f"| {k} | `{v}` |" for k, v in config.items() if k != "timestamp"]
    L.append("")
    if retr:
        L += ["## Retrieval quality (ablation)", "",
              "Relevance = retrieved chunk contains a gold evidence span. Answerable questions only.", "",
              "| mode | n | hit@1 | hit@5 | recall@5 | recall@10 | MRR@10 | nDCG@10 | doc_hit@5 | p50 ms | p95 ms |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for mode, m in retr.items():
            L.append(f"| {mode} | {m['n']} | {pct(m['hit@1'])} | {pct(m['hit@5'])} | {pct(m['recall@5'])} | "
                     f"{pct(m['recall@10'])} | {m['mrr@10']:.3f} | {m['ndcg@10']:.3f} | {pct(m['doc_hit@5'])} | "
                     f"{m['latency_ms_p50']:.0f} | {m['latency_ms_p95']:.0f} |")
        L.append("")
    if summ:
        L += ["## End-to-end agent", "", "| metric | value |", "|---|---|",
              f"| questions | {summ['n_questions']} (errors: {summ['errors']}) |",
              f"| **overall accuracy** | **{pct(summ['overall_accuracy'])}** |",
              f"| answerable accuracy (all required facts present) | {pct(summ['answerable_accuracy'])} |",
              f"| answerable fact coverage | {pct(summ['answerable_facts_score'])} |",
              f"| false abstention rate (answerable) | {pct(summ['false_abstention_rate'])} |",
              f"| abstention recall (unanswerable + access denied) | {pct(summ['abstention_recall'])} |",
              f"| abstention precision | {pct(summ['abstention_precision'])} |",
              f"| hallucination rate on negatives | {pct(summ['hallucination_rate_on_negatives'])} |",
              f"| **ACL leak rate** | **{pct(summ['acl_leak_rate'])}** (violations in retrieval: {summ['acl_violations']}) |",
              f"| citation precision (evidence-level) | {pct(summ['citation_precision'])} |",
              f"| citation precision (document-level) | {pct(summ['citation_doc_precision'])} |",
              f"| citation recall | {pct(summ['citation_recall'])} |",
              f"| answers with ≥1 citation | {pct(summ['answers_with_citations'])} |"]
        if "judge_correct" in summ:
            L.append(f"| LLM-judge correct / partial | {pct(summ['judge_correct'])} / {pct(summ['judge_partial'])} |")
        L += ["", "### Latency and cost", "", "| metric | value |", "|---|---|",
              f"| latency p50 / p95 / mean | {summ['latency_ms_p50']:.0f} / {summ['latency_ms_p95']:.0f} / {summ['latency_ms_mean']:.0f} ms |",
              f"| stage means (ms) | {', '.join(f'{k}={v}' for k, v in summ['stage_ms_mean'].items())} |",
              f"| LLM calls per question | {summ['llm_calls_per_question']:.2f} |",
              f"| tokens in / out | {summ['input_tokens']:,} / {summ['output_tokens']:,} |",
              f"| cost total / per question | ${summ['cost_usd_total']:.4f} / ${summ['cost_usd_per_question']:.5f} |",
              "", "### By category", "", "| category | n | accuracy | abstain rate | p50 ms |", "|---|---|---|---|---|"]
        for cat, c in summ["by_category"].items():
            L.append(f"| {cat} | {c['n']} | {pct(c['accuracy'])} | {pct(c['abstain_rate'])} | {c['latency_ms_p50']:.0f} |")
        fails = [r for r in rows if not r.get("correct")]
        if fails:
            L += ["", f"### Failures ({len(fails)})", "", "| id | category | question | answer |", "|---|---|---|---|"]
            for r in fails[:40]:
                a = (r.get("answer") or r.get("error", "")).replace("|", "/").replace("\n", " ")[:140]
                L.append(f"| {r['id']} | {r['category']} | {r['question'][:80]} | {a} |")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--benchmark", default=str(HERE / "benchmark.jsonl"))
    ap.add_argument("--setup", action="store_true", help="ingest sample corpus and demo users first")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--categories", help="comma-separated subset")
    ap.add_argument("--modes", default=",".join(MODES), help="retrieval modes to ablate")
    ap.add_argument("--agent-mode", default="hybrid_rerank")
    ap.add_argument("--skip-agent", action="store_true")
    ap.add_argument("--skip-retrieval", action="store_true")
    ap.add_argument("--judge", action="store_true", help="add LLM-as-judge grading (needs GROQ_API_KEY)")
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    if a.setup:
        setup_corpus()
    items = load(Path(a.benchmark), a.limit, set(a.categories.split(",")) if a.categories else None)
    cache: dict[str, list[str]] = {}

    def groups_of(user: str) -> list[str]:
        if user not in cache:
            cache[user] = get_user_groups(user)
            if not cache[user]:
                raise SystemExit(f"user {user!r} has no groups - run with --setup first")
        return cache[user]

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path(a.out) if a.out else HERE / "reports" / ts
    out.mkdir(parents=True, exist_ok=True)
    config = {"timestamp": ts, "questions": len(items), "llm": settings.llm_model if settings.llm_enabled else "none (extractive)",
              "embed_backend": f"{settings.embed_backend}:{settings.embed_model if settings.embed_backend != 'hash' else 'hash-384'}",
              "rerank_backend": f"{settings.rerank_backend}:{settings.rerank_model if settings.rerank_backend == 'cross-encoder' else ''}",
              "agent_mode": a.agent_mode, "final_top_k": settings.final_top_k,
              "min_evidence_score": settings.min_evidence_score}

    retr = {}
    if not a.skip_retrieval:
        print("== retrieval ablation")
        retr = eval_retrieval(items, [m for m in a.modes.split(",") if m], groups_of)
        for m, v in retr.items():
            print(f"  {m:<14} hit@5={v['hit@5']:.3f} recall@10={v['recall@10']:.3f} mrr={v['mrr@10']:.3f} ndcg={v['ndcg@10']:.3f}")
    rows, summ = [], None
    if not a.skip_agent:
        print(f"== agent ({len(items)} questions)")
        rows = eval_agent(items, a.agent_mode, groups_of, a.judge)
        summ = summarize(rows)
        with (out / "results.jsonl").open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    (out / "summary.json").write_text(json.dumps({"config": config, "retrieval": retr, "agent": summ},
                                                 indent=2, default=str), encoding="utf-8")
    (out / "report.md").write_text(render(config, retr, summ, rows), encoding="utf-8")
    if summ:
        print(f"\noverall accuracy {pct(summ['overall_accuracy'])} | answerable {pct(summ['answerable_accuracy'])} | "
              f"abstention recall {pct(summ['abstention_recall'])} | ACL leaks {pct(summ['acl_leak_rate'])} | "
              f"citation precision {pct(summ['citation_precision'])} | p95 {summ['latency_ms_p95']:.0f} ms | "
              f"cost ${summ['cost_usd_total']:.4f}")
    print(f"report: {out / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
