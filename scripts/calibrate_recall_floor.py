#!/usr/bin/env python
"""Calibrate MIN_RECALL_SCORE from real Spine data.

Measures the similarity distribution of:
- True positive facts (target documents)
- Conversational noise ("good morning", "thanks", etc.)
- Near-miss filler (similar structure, different content)

Outputs a recommended floor with margin analysis.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# The script lives in the repo's scripts/, not backend/: everything under backend/**/*.py
# ships in the installer, and a calibration tool is not part of the product.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from core.execution_engine import ExecutionEngine, _relevance_of
from runtimes.memory.contracts import MemoryType
from runtimes.memory.runtime import MemoryRuntimeImpl


def load_real_spine(db_path: str) -> MemoryRuntimeImpl:
    """Load an existing Spine database."""
    runtime = MemoryRuntimeImpl(
        store_type="sqlite",
        db_path=db_path,
        index_type="hybrid",
        embedding_dim=1024,
        embedding_backend="ollama",
        embedding_model="bge-m3",
        embed_on_gpu=False,  # Force CPU for consistent results
    )
    return runtime


def build_test_spine(runtime: MemoryRuntimeImpl, size: int = 500) -> None:
    """Build a test Spine with realistic data."""
    import asyncio
    import random

    _CLIENTS = ("Ridgeway", "Lantern House", "Ovo Media", "Blackthorn", "Maren Studio",
                "Copperfield", "Sable & Co", "Northgate", "Verity Films", "Ashwood")
    _TEMPLATES = (
        "Invoice INV-{c}-{n:03d} for {C}. Issued {d} {m} 2026 in NGN. {svc} at a day "
        "rate of {r},000 naira. Payment terms: {t} days from the invoice date.",
        "{C} brief. The deliverable is a {sec}-second {svc2} for the {season} campaign. "
        "{rev} rounds of revisions are included. Final delivery is {d} {m} 2026.",
        "Mutual non-disclosure agreement with {C}, signed {d} {m} 2026. "
        "Confidentiality survives for {yr} years after termination.",
        "{C} paid invoice INV-{c}-{n:03d} on {d} {m} 2026, {late} days after the due date.",
    )
    _SVC = ("3D generalist services", "motion design", "compositing", "colour grading")
    _SVC2 = ("product film", "explainer", "sizzle reel", "brand ident")
    _MONTHS = ("January", "March", "May", "July", "September", "November")
    _PREFERENCES = (
        "Prefer to keep every project file under the client folder, and never "
        "archive a document until the final invoice has cleared.",
        "Always render previews at half resolution first. Never commit a final "
        "pass without a summary of what changed since the last one.",
        "Prefer morning calls for a new brief. Anything that needs a decision goes "
        "out the evening before, never on the day itself.",
        "Keep a backup of every delivered file for two years. Prefer an external "
        "drive over cloud storage for anything under a signed agreement.",
        "Prefer to send anything client-facing as a PDF, and never leave a "
        "document without a filename that says what it is.",
    )

    def _filler(n: int, seed: int = 7) -> list[str]:
        rng = random.Random(seed)
        out = []
        for i in range(n):
            if i % 12 == 11:
                out.append(rng.choice(_PREFERENCES))
                continue
            client = rng.choice(_CLIENTS)
            out.append(rng.choice(_TEMPLATES).format(
                c=client[:4].upper(), C=client, n=i, d=rng.randint(1, 28),
                m=rng.choice(_MONTHS), svc=rng.choice(_SVC), svc2=rng.choice(_SVC2),
                r=rng.randint(80, 900), t=rng.choice((7, 14, 30, 45)),
                sec=rng.choice((15, 30, 45, 60)), season=rng.choice(("autumn", "spring")),
                rev=rng.choice(("Two", "Three")), yr=rng.choice((2, 3, 5)),
                late=rng.randint(1, 40),
            ))
        return out

    async def build():
        await runtime.initialize()
        # Add some known target facts
        targets = {
            "harbour-invoice": (
                "Invoice INV-HARB-014 for Harbour Lane Studio. Issued 2 July 2026 in NGN. "
                "Motion design at a day rate of 425,000 naira. Payment terms: 14 days from the invoice date."
            ),
            "century-invoice": (
                "Invoice INV-CENT-001 for Century. Issued 8 June 2026 in NGN. "
                "3D generalist services at a day rate of 250,000 naira. Payment terms: 30 days from the invoice date."
            ),
            "harbour-brief": (
                "Harbour Lane Studio brief. The deliverable is a 45-second title sequence "
                "for the autumn campaign. Two rounds of revisions are included. Final delivery is 12 September 2026."
            ),
            "nda": (
                "Mutual non-disclosure agreement with Quadron Studios, signed 3 March 2026. "
                "Confidentiality survives for three years after termination."
            ),
            "note": (
                "Prefer Nigerian English spelling in anything client-facing, "
                "and never send a document without a summary paragraph at the top."
            ),
        }
        for doc_id, text in targets.items():
            await runtime.remember(content=text, memory_type=MemoryType.SEMANTIC,
                                   metadata={"doc_id": doc_id, "origin": "user_document"})
        # Add filler
        for i, text in enumerate(_filler(size - len(targets))):
            await runtime.remember(content=text, memory_type=MemoryType.SEMANTIC,
                                   metadata={"doc_id": f"filler-{i}", "origin": "user_document"})

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(build())
    finally:
        loop.close()


def measure_score_distribution(
    runtime: MemoryRuntimeImpl,
    test_queries: list[str],
    target_doc_ids: list[str],
    noise_queries: list[str],
    top_k: int = 100,
) -> dict:
    """Measure relevance score distributions for targets vs noise."""
    import asyncio

    target_scores = []      # Score of the ACTUAL target document for each query
    filler_scores = []      # Scores of non-target documents (distractors)
    noise_scores = []       # Scores for unanswerable/conversational queries

    async def retrieve_all(query: str):
        return await runtime.retrieve(query=query, max_results=top_k)

    loop = asyncio.new_event_loop()
    try:
        # Related queries — measure the TARGET document's score
        for query, target_id in zip(test_queries, target_doc_ids):
            results = loop.run_until_complete(retrieve_all(query))
            target_found = False
            for r in results:
                rel = _relevance_of(r)
                doc_id = getattr(r.record, "metadata", {}).get("doc_id", "")
                if doc_id == target_id:
                    target_scores.append((query, rel, target_id))
                    target_found = True
                else:
                    filler_scores.append((query, rel, doc_id))
            if not target_found:
                print(f"WARNING: Target {target_id} not found for query: {query}")

        # Unanswerable queries — all results are noise
        for query in noise_queries:
            results = loop.run_until_complete(retrieve_all(query))
            for r in results:
                rel = _relevance_of(r)
                noise_scores.append((query, rel, getattr(r.record, "metadata", {}).get("doc_id", "")))

        # Conversational noise
        conversational = [
            "good morning",
            "thanks",
            "okay",
            "sure",
            "hello",
            "hi there",
            "how are you",
            "fine thanks",
            "got it",
            "understood",
        ]
        for query in conversational:
            results = loop.run_until_complete(retrieve_all(query))
            for r in results:
                rel = _relevance_of(r)
                noise_scores.append((query, rel, getattr(r.record, "metadata", {}).get("doc_id", "")))

    finally:
        loop.close()

    return {
        "targets": target_scores,
        "fillers": filler_scores,
        "noise": noise_scores,
    }


def analyze_and_recommend(scores: dict) -> dict:
    """Analyze distributions and recommend floor."""
    targets = [s[1] for s in scores["targets"]]
    fillers = [s[1] for s in scores["fillers"]]
    noise = [s[1] for s in scores["noise"]]

    if not targets or not noise:
        return {"error": "Insufficient data"}

    targets_sorted = sorted(targets)
    fillers_sorted = sorted(fillers)
    noise_sorted = sorted(noise)

    # Key percentiles for TARGET documents
    target_min = min(targets)
    target_p10 = targets_sorted[len(targets_sorted) // 10]
    target_median = targets_sorted[len(targets_sorted) // 2]
    target_p90 = targets_sorted[9 * len(targets_sorted) // 10]
    target_max = max(targets)

    # Key percentiles for FILLER (distractor) documents
    filler_min = min(fillers) if fillers else 0
    filler_p50 = fillers_sorted[len(fillers_sorted) // 2] if fillers else 0
    filler_p90 = fillers_sorted[9 * len(fillers_sorted) // 10] if fillers else 0
    filler_max = max(fillers) if fillers else 0

    # Key percentiles for NOISE (unanswerable/conversational)
    noise_p90 = noise_sorted[9 * len(noise_sorted) // 10]
    noise_p95 = noise_sorted[19 * len(noise_sorted) // 20]
    noise_p99 = noise_sorted[99 * len(noise_sorted) // 100]
    noise_max = max(noise)

    # Recommended floor: above noise_p99, below target_p10
    # With safety margin
    recommended = max(noise_p99 + 0.02, 0.42)
    if recommended > target_p10:
        recommended = (noise_max + target_p10) / 2

    return {
        "current_floor": ExecutionEngine.MIN_RECALL_SCORE,
        "targets": {
            "count": len(targets),
            "min": target_min,
            "p10": target_p10,
            "median": target_median,
            "p90": target_p90,
            "max": target_max,
        },
        "fillers": {
            "count": len(fillers),
            "min": filler_min,
            "median": filler_p50,
            "p90": filler_p90,
            "max": filler_max,
        },
        "noise": {
            "count": len(noise),
            "p90": noise_p90,
            "p95": noise_p95,
            "p99": noise_p99,
            "max": noise_max,
        },
        "margin": {
            "min_target_vs_max_noise": target_min - noise_max,
            "p10_target_vs_p99_noise": target_p10 - noise_p99,
            "p10_target_vs_p90_filler": target_p10 - filler_p90,
        },
        "recommended_floor": round(recommended, 3),
        "recommended_floor_with_margin": round(recommended + 0.03, 3),
    }


def main():
    parser = argparse.ArgumentParser(description="Calibrate MIN_RECALL_SCORE")
    parser.add_argument("--db", help="Path to existing Spine DB")
    parser.add_argument("--build-test", action="store_true", help="Build test Spine")
    parser.add_argument("--size", type=int, default=500, help="Test Spine size")
    parser.add_argument("--output", help="Write results to JSON file")
    args = parser.parse_args()

    if args.build_test:
        # Build test Spine in temp location
        import tempfile
        tmp = tempfile.mkdtemp(prefix="zaram-calibrate-")
        db_path = str(Path(tmp) / "calibrate.db")
        print(f"Building test Spine at {db_path}...")
        # Force CPU embeddings for reliable calibration (GPU may not be available)
        runtime = MemoryRuntimeImpl(
            store_type="sqlite",
            db_path=db_path,
            index_type="hybrid",
            embedding_dim=1024,
            embedding_backend="ollama",
            embedding_model="bge-m3",
            embed_on_gpu=False,  # Force CPU for consistent results
        )
        build_test_spine(runtime, args.size)
    elif args.db:
        db_path = args.db
        if not Path(db_path).exists():
            print(f"Database not found: {db_path}")
            sys.exit(1)
        runtime = load_real_spine(db_path)
    else:
        print("Either --db or --build-test required")
        sys.exit(1)

    # Test queries that should match targets
    test_queries = [
        "What is Harbour Lane's day rate?",
        "When is Century's invoice due?",
        "How long is the title sequence?",
        "What did I agree with Quadron?",
        "How should I write to clients?",
    ]
    target_doc_ids = [
        "harbour-invoice",
        "century-invoice",
        "harbour-brief",
        "nda",
        "note",
    ]

    # Queries that should match nothing
    noise_queries = [
        "Who won the 2026 World Cup?",
        "What is the capital of France?",
        "How do I change a bicycle tyre?",
    ]

    print("Measuring score distributions...")
    scores = measure_score_distribution(runtime, test_queries, target_doc_ids, noise_queries)
    results = analyze_and_recommend(scores)

    print("\n" + "=" * 60)
    print("SCORE DISTRIBUTION ANALYSIS")
    print("=" * 60)
    print(f"\nCurrent MIN_RECALL_SCORE: {results['current_floor']}")
    print(f"\nTarget documents ({results['targets']['count']} scores):")
    for k, v in results['targets'].items():
        if k != 'count':
            print(f"  {k}: {v:.3f}")
    print(f"\nFiller/distractor documents ({results['fillers']['count']} scores):")
    for k, v in results['fillers'].items():
        if k != 'count':
            print(f"  {k}: {v:.3f}")
    print(f"\nNoise — unanswerable + conversational ({results['noise']['count']} scores):")
    for k, v in results['noise'].items():
        if k != 'count':
            print(f"  {k}: {v:.3f}")
    print(f"\nMargins:")
    for k, v in results['margin'].items():
        print(f"  {k}: {v:+.3f}")
    print(f"\n>>> RECOMMENDED MIN_RECALL_SCORE: {results['recommended_floor']}")
    print(f">>> WITH 3% MARGIN:             {results['recommended_floor_with_margin']}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults written to {args.output}")

    # Cleanup
    if args.build_test:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()