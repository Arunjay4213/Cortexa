#!/usr/bin/env python3
"""
EAS Attribution Diagnostic — Find exactly where the signal dies.

Diagnoses embedding collapse and signal degradation in the EAS attribution system.
"""

import asyncio
import sys
import numpy as np
from scipy import stats
from collections import defaultdict

# Add parent to path for imports
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from e2e.datasets import generate_personal_assistant_dataset
from e2e.agent_simulator import AgentSimulator, MockLLM
from sentence_transformers import SentenceTransformer


def compute_eas_scores(
    query_emb: np.ndarray,
    response_emb: np.ndarray,
    memory_embs: np.ndarray,
) -> np.ndarray:
    """Compute original EAS scores: cosim(m, resp) * cosim(m, query) normalized."""
    # Ensure normalized
    query_emb = query_emb / (np.linalg.norm(query_emb) + 1e-8)
    response_emb = response_emb / (np.linalg.norm(response_emb) + 1e-8)
    norms = np.linalg.norm(memory_embs, axis=1, keepdims=True)
    memory_embs = memory_embs / (norms + 1e-8)

    # Cosine similarities
    resp_sims = memory_embs @ response_emb  # (k,)
    query_sims = memory_embs @ query_emb    # (k,)

    # EAS: product normalized to sum to 1
    raw = resp_sims * query_sims
    if np.sum(raw) == 0:
        return np.ones(len(raw)) / len(raw)
    return raw / np.sum(raw)


async def main():
    print("=" * 70)
    print("PHASE 1: DIAGNOSE — Find exactly where the signal dies")
    print("=" * 70)
    print()

    # 1. Load dataset
    print("Loading Personal Assistant dataset (200 memories)...")
    dataset = generate_personal_assistant_dataset()
    print(f"✓ Loaded {len(dataset.memories)} memories\n")

    # 2. Initialize embedding model
    print("Initializing embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("✓ Model loaded\n")

    # 3. Pre-embed all 200 memories
    print("Pre-embedding all memories...")
    memory_texts = [m.content for m in dataset.memories]
    memory_ids = [m.id for m in dataset.memories]
    memory_embeddings = model.encode(memory_texts, convert_to_numpy=True)
    print(f"✓ Embeddings shape: {memory_embeddings.shape}\n")

    # Create ID to index mapping
    id_to_idx = {mid: i for i, mid in enumerate(memory_ids)}

    # 4. Run 30 queries through AgentSimulator with MockLLM
    print("Running 30 queries through AgentSimulator with MockLLM...")
    print()

    # Create simulator with MockLLM
    llm = MockLLM(seed=42)

    def embed_fn(texts):
        if isinstance(texts, str):
            # Single string: return 1D array (384,)
            return model.encode([texts], convert_to_numpy=True)[0]
        else:
            # List of strings: return 2D array (n, 384)
            return model.encode(texts, convert_to_numpy=True)

    simulator = AgentSimulator(
        memories=[(mid, text) for mid, text in zip(memory_ids, memory_texts)],
        memory_embeddings=memory_embeddings,
        embed_fn=embed_fn,
        llm=llm,
        k=8,  # top-8 retrieval
    )

    # Storage for diagnostics
    all_results = []

    # Generate 30 test queries based on random memories
    test_queries = [
        "What's my favorite programming language?",
        "Tell me about my pet",
        "What time do I usually wake up?",
        "What's my email address?",
        "Where do I work?",
        "What's my favorite food?",
        "Tell me about my exercise routine",
        "What music do I like?",
        "What's my home address?",
        "What are my hobbies?",
        "What's my phone number?",
        "Tell me about my travel preferences",
        "What's my favorite movie?",
        "What framework do I prefer for backend?",
        "What database do I usually use?",
        "What's my git username?",
        "Tell me about my work schedule",
        "What IDE do I use?",
        "What's my favorite book?",
        "Tell me about my diet preferences",
        "What's my birthday?",
        "What languages can I speak?",
        "What's my morning routine?",
        "Tell me about my family",
        "What car do I drive?",
        "What's my coffee preference?",
        "What's my timezone?",
        "Tell me about my education",
        "What's my favorite sport?",
        "What's my laptop model?",
    ]

    # Run 30 queries
    for i, query_text in enumerate(test_queries[:30]):
        result = await simulator.process_query(query_text)

        # Get retrieved memory indices and embeddings
        retrieved_ids = [m.id for m in result.retrieved_memories]
        retrieved_indices = [id_to_idx[mid] for mid in retrieved_ids]
        retrieved_embs = memory_embeddings[retrieved_indices]
        retrieved_texts = [m.content for m in result.retrieved_memories]

        # Embed query and response
        query_emb = embed_fn(result.query)
        response_emb = embed_fn(result.response)

        # Compute similarities
        resp_sims = retrieved_embs @ response_emb
        query_sims = retrieved_embs @ query_emb

        # Compute EAS scores
        eas_scores = compute_eas_scores(query_emb, response_emb, retrieved_embs)

        # Ground truth labels (1 if used, 0 if not)
        gt_labels = []
        for mid in retrieved_ids:
            gt_labels.append(1 if result.ground_truth_weights.get(mid, 0.0) > 0 else 0)

        all_results.append({
            'query': result.query,
            'response': result.response,
            'retrieved_ids': retrieved_ids,
            'retrieved_texts': retrieved_texts,
            'resp_sims': resp_sims,
            'query_sims': query_sims,
            'eas_scores': eas_scores,
            'gt_labels': np.array(gt_labels),
            'gt_weights': result.ground_truth_weights,
        })

    print(f"✓ Processed 30 queries\n")

    # 5. Print table for first 5 queries
    print("=" * 70)
    print("DETAILED RESULTS FOR FIRST 5 QUERIES")
    print("=" * 70)
    print()

    for i in range(min(5, len(all_results))):
        r = all_results[i]
        print(f"Query {i+1}: \"{r['query'][:60]}...\"")
        print()
        print(f"{'Memory (first 40 chars)':<42} | {'cos(m,resp)':<11} | {'cos(m,query)':<12} | {'EAS':<7} | {'GT':<2}")
        print("-" * 90)

        for j in range(len(r['retrieved_texts'])):
            mem_preview = r['retrieved_texts'][j][:40].replace('\n', ' ')
            resp_sim = r['resp_sims'][j]
            query_sim = r['query_sims'][j]
            eas = r['eas_scores'][j]
            gt = r['gt_labels'][j]

            print(f"{mem_preview:<42} | {resp_sim:>11.3f} | {query_sim:>12.3f} | {eas:>7.3f} | {gt:>2}")

        print()

    # 6. Compute AGGREGATE DIAGNOSTICS
    print("=" * 70)
    print("AGGREGATE DIAGNOSTICS ACROSS 30 QUERIES")
    print("=" * 70)
    print()

    # Collect all scores by whether memory was used or not
    used_resp_sims = []
    unused_resp_sims = []
    used_query_sims = []
    unused_query_sims = []
    used_eas_scores = []
    unused_eas_scores = []

    # For correlation computations
    all_query_sims_flat = []
    all_resp_sims_flat = []
    all_eas_flat = []
    all_gt_flat = []

    for r in all_results:
        for j in range(len(r['gt_labels'])):
            is_used = r['gt_labels'][j] == 1

            if is_used:
                used_resp_sims.append(r['resp_sims'][j])
                used_query_sims.append(r['query_sims'][j])
                used_eas_scores.append(r['eas_scores'][j])
            else:
                unused_resp_sims.append(r['resp_sims'][j])
                unused_query_sims.append(r['query_sims'][j])
                unused_eas_scores.append(r['eas_scores'][j])

            all_query_sims_flat.append(r['query_sims'][j])
            all_resp_sims_flat.append(r['resp_sims'][j])
            all_eas_flat.append(r['eas_scores'][j])
            all_gt_flat.append(r['gt_labels'][j])

    # EMBEDDING COLLAPSE CHECK
    print("EMBEDDING COLLAPSE CHECK:")
    mean_used_resp = np.mean(used_resp_sims) if used_resp_sims else 0.0
    mean_unused_resp = np.mean(unused_resp_sims) if unused_resp_sims else 0.0
    gap = mean_used_resp - mean_unused_resp

    print(f"- Mean cosim(m, response) for USED memories:    {mean_used_resp:.3f}")
    print(f"- Mean cosim(m, response) for UNUSED memories:  {mean_unused_resp:.3f}")
    print(f"- Gap (used - unused):                          {gap:.3f}")

    if gap < 0.05:
        print("→ CONFIRMED embedding collapse — response embedding is equidistant")
    elif gap < 0.15:
        print("→ PARTIAL collapse — weak signal from response embedding")
    else:
        print("→ Embeddings are fine, problem is elsewhere")
    print()

    # TERM CONTRIBUTION CHECK
    print("TERM CONTRIBUTION CHECK:")

    # Spearman correlation of each term vs ground truth
    query_corr, _ = stats.spearmanr(all_query_sims_flat, all_gt_flat)
    resp_corr, _ = stats.spearmanr(all_resp_sims_flat, all_gt_flat)
    eas_corr, _ = stats.spearmanr(all_eas_flat, all_gt_flat)

    print(f"- Spearman corr of cosim(m, query) alone vs GT:     {query_corr:.3f}")
    print(f"- Spearman corr of cosim(m, response) alone vs GT:  {resp_corr:.3f}")
    print(f"- Spearman corr of EAS (product) vs GT:             {eas_corr:.3f}")

    if query_corr > eas_corr:
        print("→ Response term adds NOISE — query alone is better!")
    if resp_corr < 0.1:
        print("→ Response embedding is USELESS — near-zero correlation with GT")
    print()

    # SCORE DISTRIBUTION
    print("SCORE DISTRIBUTION:")
    mean_used_eas = np.mean(used_eas_scores) if used_eas_scores else 0.0
    std_used_eas = np.std(used_eas_scores) if used_eas_scores else 0.0
    mean_unused_eas = np.mean(unused_eas_scores) if unused_eas_scores else 0.0
    std_unused_eas = np.std(unused_eas_scores) if unused_eas_scores else 0.0

    print(f"- EAS scores for USED memories:   mean={mean_used_eas:.3f} std={std_used_eas:.3f}")
    print(f"- EAS scores for UNUSED memories: mean={mean_unused_eas:.3f} std={std_unused_eas:.3f}")

    # Overlap: what % of unused scores exceed the mean used score?
    if unused_eas_scores and used_eas_scores:
        overlap_count = sum(1 for score in unused_eas_scores if score > mean_used_eas)
        overlap_pct = 100.0 * overlap_count / len(unused_eas_scores)
        print(f"- Overlap: {overlap_pct:.1f}% of unused scores exceed mean used score")
    print()

    # 7. MockLLM verification for 3 queries
    print("=" * 70)
    print("MOCKLM VERIFICATION (3 queries)")
    print("=" * 70)
    print()

    for i in range(min(3, len(all_results))):
        r = all_results[i]
        print(f"Query {i+1}: {r['query']}")
        print()

        # Find which memories were actually used (GT > 0)
        used_memories = []
        for mid in r['retrieved_ids']:
            if r['gt_weights'].get(mid, 0.0) > 0:
                idx = id_to_idx[mid]
                used_memories.append((mid, memory_texts[idx], r['gt_weights'][mid]))

        print(f"Memories used by MockLLM ({len(used_memories)}):")
        for mid, text, weight in used_memories:
            print(f"  [{weight:.2f}] {text[:80]}...")
        print()

        print(f"Generated response:")
        print(f"  {r['response'][:200]}...")
        print()
        print("-" * 70)
        print()


async def phase3_comparison():
    """Phase 3: Compare all EAS methods."""
    print("\n")
    print("=" * 70)
    print("PHASE 3: COMPARISON — All EAS Methods")
    print("=" * 70)
    print()

    # Import EAS methods
    from cortex.attribution.eas import compute_eas

    # Reload dataset and re-run 30 queries (reuse from phase 1)
    print("Re-running 30 queries with both methods...")
    dataset = generate_personal_assistant_dataset()
    model = SentenceTransformer('all-MiniLM-L6-v2')

    memory_texts = [m.content for m in dataset.memories]
    memory_ids = [m.id for m in dataset.memories]
    memory_embeddings = model.encode(memory_texts, convert_to_numpy=True)
    id_to_idx = {mid: i for i, mid in enumerate(memory_ids)}

    llm = MockLLM(seed=42)

    def embed_fn(texts):
        if isinstance(texts, str):
            return model.encode([texts], convert_to_numpy=True)[0]
        else:
            return model.encode(texts, convert_to_numpy=True)

    simulator = AgentSimulator(
        memories=[(mid, text) for mid, text in zip(memory_ids, memory_texts)],
        memory_embeddings=memory_embeddings,
        embed_fn=embed_fn,
        llm=llm,
        k=8,
    )

    test_queries = [
        "What's my favorite programming language?",
        "Tell me about my pet",
        "What time do I usually wake up?",
        "What's my email address?",
        "Where do I work?",
        "What's my favorite food?",
        "Tell me about my exercise routine",
        "What music do I like?",
        "What's my home address?",
        "What are my hobbies?",
        "What's my phone number?",
        "Tell me about my travel preferences",
        "What's my favorite movie?",
        "What framework do I prefer for backend?",
        "What database do I usually use?",
        "What's my git username?",
        "Tell me about my work schedule",
        "What IDE do I use?",
        "What's my favorite book?",
        "Tell me about my diet preferences",
        "What's my birthday?",
        "What languages can I speak?",
        "What's my morning routine?",
        "Tell me about my family",
        "What car do I drive?",
        "What's my coffee preference?",
        "What's my timezone?",
        "Tell me about my education",
        "What's my favorite sport?",
        "What's my laptop model?",
    ]

    # Track metrics for all methods
    methods = {
        "cosine": {"corr": [], "p3": [], "p1": []},
        "response_only": {"corr": [], "p3": [], "p1": []},
        "response_weighted": {"corr": [], "p3": [], "p1": []},
        "contrastive": {"corr": [], "p3": [], "p1": []},
    }

    for query_text in test_queries[:30]:
        result = await simulator.process_query(query_text)

        retrieved_ids = [m.id for m in result.retrieved_memories]
        retrieved_indices = [id_to_idx[mid] for mid in retrieved_ids]
        retrieved_embs = memory_embeddings[retrieved_indices]
        retrieved_texts = [m.content for m in result.retrieved_memories]

        query_emb = embed_fn(result.query)
        response_emb = embed_fn(result.response)

        # Ground truth labels
        gt_labels = np.array([1 if result.ground_truth_weights.get(mid, 0.0) > 0 else 0
                              for mid in retrieved_ids])

        # Compute scores for all methods
        scores_by_method = {}
        scores_by_method["cosine"] = compute_eas(
            retrieved_embs, query_emb, response_emb, method="cosine"
        )["scores"]
        scores_by_method["response_only"] = compute_eas(
            retrieved_embs, query_emb, response_emb, method="response_only"
        )["scores"]
        scores_by_method["response_weighted"] = compute_eas(
            retrieved_embs, query_emb, response_emb, method="response_weighted"
        )["scores"]
        scores_by_method["contrastive"] = compute_eas(
            retrieved_embs, query_emb, response_emb,
            method="contrastive",
            memory_texts=retrieved_texts,
            response_text=result.response,
            tau=0.7, alpha=0.9
        )["scores"]

        # Compute metrics for each method
        if len(gt_labels) >= 2 and np.sum(gt_labels) > 0:
            for method_name, scores in scores_by_method.items():
                corr, _ = stats.spearmanr(scores, gt_labels)
                methods[method_name]["corr"].append(corr)

                # Precision@3
                top3 = np.argsort(scores)[-3:]
                gt_top3 = np.where(gt_labels == 1)[0]
                p3 = len(set(top3) & set(gt_top3)) / min(3, len(gt_top3)) if len(gt_top3) > 0 else 0.0
                methods[method_name]["p3"].append(p3)

                # Precision@1
                top1 = np.argmax(scores)
                p1 = 1.0 if top1 in gt_top3 else 0.0
                methods[method_name]["p1"].append(p1)

    # Print comparison
    print()
    print("COMPARISON (30 queries):")
    print(f"| {'Method':<18} | {'Spearman':<13} | {'P@3':<9} | {'P@1':<9} |")
    print("|" + "-" * 20 + "|" + "-" * 15 + "|" + "-" * 11 + "|" + "-" * 11 + "|")
    for method_name in ["cosine", "response_only", "response_weighted", "contrastive"]:
        m = methods[method_name]
        print(f"| {method_name:<18} | {np.mean(m['corr']):13.11f} | {np.mean(m['p3']):9.7f} | {np.mean(m['p1']):9.7f} |")
    print()

    # Hyperparameter sweep
    print("Hyperparameter sweep:")
    print()

    tau_values = [0.1, 0.3, 0.5, 0.7, 1.0]
    alpha_values = [0.5, 0.6, 0.7, 0.8, 0.9]

    best_tau = 0.5
    best_alpha = 0.7
    best_corr = np.mean(contrastive_correlations)

    grid_results = {}

    print("Grid search (tau x alpha):")
    for tau in tau_values:
        for alpha in alpha_values:
            # Re-run with these params
            correlations = []

            for query_text in test_queries[:30]:
                result = await simulator.process_query(query_text)

                retrieved_ids = [m.id for m in result.retrieved_memories]
                retrieved_indices = [id_to_idx[mid] for mid in retrieved_ids]
                retrieved_embs = memory_embeddings[retrieved_indices]
                retrieved_texts = [m.content for m in result.retrieved_memories]

                query_emb = embed_fn(result.query)
                response_emb = embed_fn(result.response)

                gt_labels = np.array([1 if result.ground_truth_weights.get(mid, 0.0) > 0 else 0
                                      for mid in retrieved_ids])

                cont_scores = compute_contrastive_eas(
                    query_emb, response_emb, retrieved_embs,
                    retrieved_texts, result.response,
                    tau=tau, alpha=alpha
                )

                if len(gt_labels) >= 2 and np.sum(gt_labels) > 0:
                    corr, _ = stats.spearmanr(cont_scores, gt_labels)
                    correlations.append(corr)

            mean_corr = np.mean(correlations)
            grid_results[(tau, alpha)] = mean_corr

            if mean_corr > best_corr:
                best_corr = mean_corr
                best_tau = tau
                best_alpha = alpha

    # Print grid
    print()
    print(f"| {'tau\\alpha':<9} | {' | '.join(f'{a:<5}' for a in alpha_values)} |")
    print("|" + "-" * 11 + "|" + "-" * 7 * len(alpha_values) + "-" * len(alpha_values) + "|")

    for tau in tau_values:
        row = f"| {tau:<9.1f} | "
        row += " | ".join(f"{grid_results[(tau, a)]:>5.3f}" for a in alpha_values)
        row += " |"
        print(row)

    print()
    print(f"Best tau (from {tau_values}):    {best_tau} → corr {best_corr:.3f}")
    print(f"Best alpha (from {alpha_values}):   {best_alpha} → corr {best_corr:.3f}")
    print(f"Best combo:  tau={best_tau} alpha={best_alpha} → corr {best_corr:.3f}")
    print()

    improvement = best_corr - np.mean(original_correlations)
    print(f"Improvement over original: {improvement:+.3f}")
    print()

    if improvement > 0.1:
        print("✅ CONTRASTIVE EAS WINS BY >0.1!")
        print("→ Proceed to Phase 4: Update production code")
    else:
        print("❌ Contrastive EAS does NOT beat original by >0.1")
        print("→ Problem is elsewhere, need more investigation")

    return improvement, best_tau, best_alpha


if __name__ == "__main__":
    asyncio.run(main())
    # Run Phase 3 comparison
    improvement, best_tau, best_alpha = asyncio.run(phase3_comparison())
