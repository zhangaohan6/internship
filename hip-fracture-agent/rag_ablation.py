#!/usr/bin/env python3
"""RAG ablation: run the Type C (clinical-guideline) questions with retrieval
ON vs OFF (HIP_NO_RAG=1) to quantify RAG's contribution to answer quality and
hallucination. Backend is whatever provider run_eval is given (DeepSeek here).

Usage:
  OPENAI_API_KEY=... OPENAI_BASE_URL=https://api.deepseek.com OPENAI_MODEL=deepseek-chat \
    python rag_ablation.py
"""
import json
import os

import eval_framework as ef


def summarise(results):
    n = len(results)
    return {
        "n": n,
        "score": round(sum(r.answer_score for r in results) / n, 3),
        "tool_acc": round(sum(1 for r in results if r.tool_correct) / n, 3),
        "halluc": round(sum(1 for r in results if r.hallucination_detected) / n, 3),
        "avg_latency": round(sum(r.latency_seconds for r in results) / n, 1),
    }


def run_condition(type_c, no_rag: bool):
    if no_rag:
        os.environ["HIP_NO_RAG"] = "1"
    else:
        os.environ.pop("HIP_NO_RAG", None)
    label = "RAG-OFF" if no_rag else "RAG-ON"
    print(f"\n===== {label} =====")
    results = ef.run_eval(questions=type_c, max_questions=9999, provider="openai")
    return summarise(results), [
        {"id": r.id, "score": r.answer_score, "halluc": r.hallucination_detected}
        for r in results
    ]


def main():
    gt = ef.compute_ground_truth()
    type_c = [t for t in ef.build_test_dataset(gt) if t["type"] == "C"]
    print(f"Type C (guideline) questions: {len(type_c)}")

    on_sum, on_detail = run_condition(type_c, no_rag=False)
    off_sum, off_detail = run_condition(type_c, no_rag=True)

    print("\n================ RAG ABLATION (Type C, guideline) ================")
    print(f"  {'metric':<16}{'RAG-ON':>10}{'RAG-OFF':>10}{'Δ (RAG gain)':>16}")
    for k in ["score", "tool_acc", "halluc", "avg_latency"]:
        d = on_sum[k] - off_sum[k]
        print(f"  {k:<16}{on_sum[k]:>10}{off_sum[k]:>10}{d:>+16.3f}")
    print("==================================================================")

    out = {"rag_on": on_sum, "rag_off": off_sum,
           "detail": {"rag_on": on_detail, "rag_off": off_detail}}
    json.dump(out, open("rag_ablation.json", "w"), indent=2, ensure_ascii=False)
    print("Saved: rag_ablation.json")


if __name__ == "__main__":
    main()
