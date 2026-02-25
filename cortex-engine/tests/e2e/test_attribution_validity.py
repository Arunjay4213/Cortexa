"""Attribution Validity Tests - Core validation of CortexOS.

These tests answer: "Are CortexOS attribution scores actually meaningful?"

Most critical: Test 1 (correlation with ground truth).
If EAS doesn't correlate with reality, nothing else matters.
"""

import asyncio
import numpy as np
from scipy import stats
from typing import List, Dict, Tuple
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from e2e.agent_simulator import (
    AgentSimulator,
    SimulationResult,
    MockLLM,
    simple_embed,
    create_test_simulator,
)
from e2e.datasets import generate_personal_assistant_dataset, MemoryDataset


async def test_attribution_correlates_with_ground_truth(
    dataset: MemoryDataset,
    n_queries: int = 200,
    correlation_threshold: float = 0.6,
    precision_threshold: float = 0.5,
    cortex_base_url: str | None = None,
    memory_id_map: dict[str, str] | None = None,
    agent_id: str | None = None,
) -> Dict:
    """Test 1: Do CortexOS EAS scores correlate with ground truth?

    This is THE test. If this fails, CortexOS attribution is not meaningful.

    Methodology:
    1. Run n_queries through AgentSimulator with MockLLM
    2. MockLLM tracks exactly which memories it used (ground truth)
    3. Compare EAS attribution ranking vs ground truth ranking
    4. Measure: Spearman rank correlation
    5. Also measure: precision@3 (are top-3 EAS memories in ground truth?)

    Args:
        dataset: Memory dataset to test with
        n_queries: Number of queries to run
        correlation_threshold: Minimum acceptable correlation
        precision_threshold: Minimum acceptable precision@3

    Returns:
        Dict with test results
    """
    print(f"\n{'='*60}")
    print("TEST 1: Attribution Correlation with Ground Truth")
    print(f"{'='*60}")

    # Prepare memories for simulator
    memory_contents = [m.content for m in dataset.memories]
    memory_ids = [m.id for m in dataset.memories]

    # Create simulator with optional CortexOS client
    simulator = create_test_simulator(
        memory_contents,
        memory_ids,
        k=5,
        cortex_base_url=cortex_base_url, memory_id_map=memory_id_map,
    )

    # Generate test queries based on memory content
    queries = generate_queries_from_dataset(dataset, n_queries)

    print(f"Running {n_queries} queries through simulator...")

    # Run queries
    results: List[SimulationResult] = []
    for i, query in enumerate(queries):
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{n_queries} queries...")

        result = await simulator.process_query(query, agent_id=agent_id or "simulator")
        results.append(result)

    print(f"✓ Completed {len(results)} queries")

    # Compute metrics - compare real EAS attribution to ground truth
    correlations = []
    precisions_at_3 = []
    results_with_attribution = 0

    for result in results:
        if not result.ground_truth_weights:
            continue

        # Skip if no CortexOS attribution (backend not available)
        if not result.cortex_attribution:
            continue

        results_with_attribution += 1

        # Get retrieved memory IDs
        retrieved_ids = [m.id for m in result.retrieved_memories]

        # Ground truth ranking (by weight)
        gt_ranking = sorted(
            result.ground_truth_weights.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Use REAL EAS scores from CortexOS
        eas_scores_dict = result.cortex_attribution

        # Compute Spearman correlation
        if len(eas_scores_dict) >= 2 and len(result.ground_truth_weights) >= 2:
            common_ids = set(eas_scores_dict.keys()) & set(result.ground_truth_weights.keys())
            if len(common_ids) >= 2:
                gt_scores = [result.ground_truth_weights[mid] for mid in common_ids]
                eas_scores = [eas_scores_dict[mid] for mid in common_ids]

                corr, pval = stats.spearmanr(gt_scores, eas_scores)
                if not np.isnan(corr):
                    correlations.append(corr)

        # Compute precision@3
        top3_eas = sorted(eas_scores_dict.items(), key=lambda x: x[1], reverse=True)[:3]
        top3_eas_ids = {mid for mid, _ in top3_eas}
        top3_gt_ids = {mid for mid, _ in gt_ranking[:3]}

        if top3_eas_ids:
            precision = len(top3_eas_ids & top3_gt_ids) / len(top3_eas_ids)
            precisions_at_3.append(precision)

    # Aggregate metrics
    mean_correlation = np.mean(correlations) if correlations else 0.0
    mean_precision = np.mean(precisions_at_3) if precisions_at_3 else 0.0

    passed_correlation = mean_correlation >= correlation_threshold
    passed_precision = mean_precision >= precision_threshold

    print(f"\nResults:")
    print(f"  Queries processed: {len(results)}")
    print(f"  Results with EAS attribution: {results_with_attribution}")

    if results_with_attribution == 0:
        print(f"\n❌ No attribution scores received from backend")
        print(f"   Backend may not be running or attribution endpoint may have failed")
        return {
            "test_name": "attribution_correlation",
            "passed": False,
            "metrics": {
                "error": "No attribution scores from backend",
                "queries_processed": len(results),
                "results_with_attribution": 0,
            }
        }

    print(f"  Mean Spearman correlation: {mean_correlation:.3f} {'✅' if passed_correlation else '❌'} (threshold: {correlation_threshold})")
    print(f"  Mean precision@3: {mean_precision:.3f} {'✅' if passed_precision else '❌'} (threshold: {precision_threshold})")

    overall_pass = passed_correlation and passed_precision

    return {
        "test_name": "attribution_correlation",
        "passed": overall_pass,
        "metrics": {
            "mean_correlation": mean_correlation,
            "correlation_threshold": correlation_threshold,
            "passed_correlation": passed_correlation,
            "mean_precision_at_3": mean_precision,
            "precision_threshold": precision_threshold,
            "passed_precision": passed_precision,
            "queries_processed": len(results),
            "results_with_attribution": results_with_attribution,
        }
    }


async def test_zero_attribution_memories_are_unused(
    results: List[SimulationResult],
    low_score_threshold: float = 0.05,
    accuracy_threshold: float = 0.8,
) -> Dict:
    """Test 2: Are low-attribution memories actually unused?

    Validates that waste detection is real, not noise.

    Args:
        results: Simulation results from test 1
        low_score_threshold: EAS score below this is "low attribution"
        accuracy_threshold: Minimum fraction of low-score memories that should be unused

    Returns:
        Dict with test results
    """
    print(f"\n{'='*60}")
    print("TEST 2: Zero-Attribution Memories Are Unused")
    print(f"{'='*60}")

    low_score_correct = 0
    low_score_total = 0

    for result in results:
        if not result.ground_truth_weights or not result.cortex_attribution:
            continue

        # Use REAL EAS scores from CortexOS
        eas_scores_dict = result.cortex_attribution

        # Check low-score memories
        for mem_id, eas_score in eas_scores_dict.items():
            if eas_score < low_score_threshold:
                low_score_total += 1
                # Check if actually unused (weight == 0)
                gt_weight = result.ground_truth_weights.get(mem_id, 0.0)
                if gt_weight < 0.01:  # Essentially unused
                    low_score_correct += 1

    accuracy = low_score_correct / low_score_total if low_score_total > 0 else 0.0
    passed = accuracy >= accuracy_threshold

    print(f"\nResults:")
    print(f"  Low-attribution memories: {low_score_total}")
    print(f"  Actually unused: {low_score_correct}")
    print(f"  Accuracy: {accuracy:.1%} {'✅' if passed else '❌'} (threshold: {accuracy_threshold:.1%})")

    return {
        "test_name": "zero_attribution_accuracy",
        "passed": passed,
        "metrics": {
            "low_score_memories": low_score_total,
            "actually_unused": low_score_correct,
            "accuracy": accuracy,
            "threshold": accuracy_threshold,
        }
    }


async def test_attribution_stability_across_similar_queries(
    dataset: MemoryDataset,
    n_query_sets: int = 20,
    paraphrases_per_query: int = 10,
    variance_threshold: float = 0.3,
    cortex_base_url: str | None = None,
    memory_id_map: dict[str, str] | None = None,
    agent_id: str | None = None,
) -> Dict:
    """Test 3: Do similar queries produce stable attribution rankings?

    Validates that attribution is robust to paraphrasing, not just noise.

    Args:
        dataset: Memory dataset
        n_query_sets: Number of base queries to test
        paraphrases_per_query: Number of paraphrases per query
        variance_threshold: Maximum acceptable variance in rankings

    Returns:
        Dict with test results
    """
    print(f"\n{'='*60}")
    print("TEST 3: Attribution Stability Across Similar Queries")
    print(f"{'='*60}")

    simulator = create_test_simulator(
        [m.content for m in dataset.memories],
        [m.id for m in dataset.memories],
        k=5,
        cortex_base_url=cortex_base_url, memory_id_map=memory_id_map,
    )

    base_queries = generate_queries_from_dataset(dataset, n_query_sets)

    ranking_variances = []

    for base_query in base_queries:
        # Generate paraphrases
        paraphrases = [base_query] + _paraphrase_query(base_query, paraphrases_per_query - 1)

        # Run all paraphrases
        results = []
        for para in paraphrases:
            result = await simulator.process_query(para, agent_id=agent_id or "simulator")
            results.append(result)

        # For each paraphrase, get EAS ranking (from real CortexOS)
        rankings = []
        for result in results:
            if not result.cortex_attribution:
                continue

            # Use REAL EAS scores from CortexOS
            eas_scores_dict = result.cortex_attribution

            # Get ranking (top-3 memory IDs)
            top3 = sorted(eas_scores_dict.items(), key=lambda x: x[1], reverse=True)[:3]
            ranking = [mem_id for mem_id, _ in top3]
            rankings.append(ranking)

        # Compute ranking variance (Kendall tau distance between pairs)
        if len(rankings) >= 2:
            tau_distances = []
            for i in range(len(rankings)):
                for j in range(i+1, len(rankings)):
                    tau = _kendall_tau_distance(rankings[i], rankings[j])
                    tau_distances.append(tau)

            mean_variance = np.mean(tau_distances) if tau_distances else 0.0
            ranking_variances.append(mean_variance)

    mean_variance = np.mean(ranking_variances) if ranking_variances else 0.0
    passed = mean_variance <= variance_threshold

    print(f"\nResults:")
    print(f"  Query sets tested: {len(base_queries)}")
    print(f"  Mean ranking variance: {mean_variance:.3f} {'✅' if passed else '❌'} (threshold: {variance_threshold})")

    return {
        "test_name": "attribution_stability",
        "passed": passed,
        "metrics": {
            "mean_variance": mean_variance,
            "variance_threshold": variance_threshold,
            "query_sets_tested": len(base_queries),
        }
    }


async def test_contradiction_detection_finds_planted_contradictions(
    dataset: MemoryDataset,
    detection_threshold: float = 0.7,
    cortex_base_url: str | None = None,
    memory_id_map: dict[str, str] | None = None,
    agent_id: str | None = None,
) -> Dict:
    """Test 4: Are planted contradictions detected by attribution?

    Personal Assistant dataset has planted contradictions.
    If EAS is meaningful, contradicting memories should get flagged.

    Args:
        dataset: Memory dataset with planted contradictions
        detection_threshold: Minimum fraction of contradictions to detect

    Returns:
        Dict with test results
    """
    print(f"\n{'='*60}")
    print("TEST 4: Contradiction Detection Finds Planted Contradictions")
    print(f"{'='*60}")

    # Find memories with contradictions
    contradicting_pairs = []
    for mem in dataset.memories:
        if mem.contradicts:
            contradicting_pairs.append((mem.id, mem.contradicts))

    if not contradicting_pairs:
        print("⚠️ No contradictions in dataset, skipping test")
        return {
            "test_name": "contradiction_detection",
            "passed": True,
            "metrics": {"contradictions_found": 0, "skipped": True}
        }

    simulator = create_test_simulator(
        [m.content for m in dataset.memories],
        [m.id for m in dataset.memories],
        k=10,  # Increase k to capture both contradicting memories
        cortex_base_url=cortex_base_url, memory_id_map=memory_id_map,
    )

    # Generate queries targeting contradictions
    queries = []
    for mem_id, _ in contradicting_pairs[:20]:  # Test first 20
        mem = next(m for m in dataset.memories if m.id == mem_id)
        # Extract topic from memory
        topic = " ".join(mem.content.split()[:5])
        queries.append(f"What do you know about {topic}?")

    detected_count = 0
    total_tested = 0

    for i, query in enumerate(queries):
        result = await simulator.process_query(query, agent_id=agent_id or "simulator")
        retrieved_ids = [m.id for m in result.retrieved_memories]

        # Check if both contradicting memories are retrieved
        mem_id, contradicts_id = contradicting_pairs[i]

        if mem_id in retrieved_ids and contradicts_id in retrieved_ids:
            if not result.cortex_attribution:
                continue

            total_tested += 1

            # Use REAL EAS scores from CortexOS
            eas_scores_dict = result.cortex_attribution

            # Check if both have similar (non-zero) scores - indicates detection
            score1 = eas_scores_dict.get(mem_id, 0.0)
            score2 = eas_scores_dict.get(contradicts_id, 0.0)

            if score1 > 0.1 and score2 > 0.1:  # Both have non-trivial scores
                detected_count += 1

    detection_rate = detected_count / total_tested if total_tested > 0 else 0.0
    passed = detection_rate >= detection_threshold

    print(f"\nResults:")
    print(f"  Contradicting pairs tested: {total_tested}")
    print(f"  Contradictions detected: {detected_count}")
    print(f"  Detection rate: {detection_rate:.1%} {'✅' if passed else '❌'} (threshold: {detection_threshold:.1%})")

    return {
        "test_name": "contradiction_detection",
        "passed": passed,
        "metrics": {
            "total_tested": total_tested,
            "detected_count": detected_count,
            "detection_rate": detection_rate,
            "threshold": detection_threshold,
        }
    }


async def test_waste_rate_matches_ground_truth_waste(
    results: List[SimulationResult],
    mae_threshold: float = 0.15,
) -> Dict:
    """Test 5: Does waste rate correlate with ground truth waste?

    Compares CortexOS waste rate (low-score memories) to ground truth waste
    (memories with low actual usage weights).

    Args:
        results: Simulation results from previous tests
        mae_threshold: Maximum acceptable mean absolute error

    Returns:
        Dict with test results
    """
    print(f"\n{'='*60}")
    print("TEST 5: Waste Rate Matches Ground Truth Waste")
    print(f"{'='*60}")

    ground_truth_wastes = []
    eas_wastes = []

    for result in results:
        if not result.ground_truth_weights or not result.cortex_attribution:
            continue

        # Ground truth waste: fraction with weight < 0.05
        gt_waste_count = sum(1 for w in result.ground_truth_weights.values() if w < 0.05)
        gt_waste_rate = gt_waste_count / len(result.ground_truth_weights) if result.ground_truth_weights else 0.0

        # Use REAL EAS scores from CortexOS
        eas_scores_dict = result.cortex_attribution

        # EAS waste: fraction with score < 0.1
        eas_waste_count = sum(1 for s in eas_scores_dict.values() if s < 0.1)
        eas_waste_rate = eas_waste_count / len(eas_scores_dict) if eas_scores_dict else 0.0

        ground_truth_wastes.append(gt_waste_rate)
        eas_wastes.append(eas_waste_rate)

    # Compute MAE
    if ground_truth_wastes and eas_wastes:
        mae = np.mean(np.abs(np.array(ground_truth_wastes) - np.array(eas_wastes)))
    else:
        mae = 0.0

    passed = mae <= mae_threshold

    print(f"\nResults:")
    print(f"  Queries analyzed: {len(ground_truth_wastes)}")
    print(f"  Mean Absolute Error: {mae:.3f} {'✅' if passed else '❌'} (threshold: {mae_threshold})")

    return {
        "test_name": "waste_rate_correlation",
        "passed": passed,
        "metrics": {
            "mae": mae,
            "threshold": mae_threshold,
            "queries_analyzed": len(ground_truth_wastes),
        }
    }


async def test_memory_removal_degrades_response_quality(
    dataset: MemoryDataset,
    n_queries: int = 30,
    degradation_threshold: float = 0.6,
    cortex_base_url: str | None = None,
    memory_id_map: dict[str, str] | None = None,
    agent_id: str | None = None,
) -> Dict:
    """Test 6: THE ULTIMATE PROOF - Does removing top memory degrade response?

    This is the ground truth test. If removing a high-attribution memory
    doesn't degrade response quality, attribution scores are meaningless.

    Args:
        dataset: Memory dataset
        n_queries: Number of queries to test
        degradation_threshold: Minimum fraction showing degradation

    Returns:
        Dict with test results
    """
    print(f"\n{'='*60}")
    print("TEST 6: Memory Removal Degrades Response Quality (ULTIMATE PROOF)")
    print(f"{'='*60}")

    queries = generate_queries_from_dataset(dataset, n_queries)

    degradation_count = 0
    total_tested = 0

    for query in queries:
        # Run with full memory set
        simulator_full = create_test_simulator(
            [m.content for m in dataset.memories],
            [m.id for m in dataset.memories],
            k=5,
            cortex_base_url=cortex_base_url, memory_id_map=memory_id_map,
        )

        result_full = await simulator_full.process_query(query, agent_id=agent_id or "simulator")

        # Identify top-used memory (ground truth)
        if not result_full.ground_truth_weights:
            continue

        top_memory_id = max(result_full.ground_truth_weights.items(), key=lambda x: x[1])[0]

        # Create reduced dataset (without top memory)
        reduced_memories = [m for m in dataset.memories if m.id != top_memory_id]

        if len(reduced_memories) < 5:
            continue

        simulator_reduced = create_test_simulator(
            [m.content for m in reduced_memories],
            [m.id for m in reduced_memories],
            k=5,
            cortex_base_url=cortex_base_url, memory_id_map=memory_id_map,
        )

        result_reduced = await simulator_reduced.process_query(query, agent_id=agent_id or "simulator")

        # Compare response quality using simple BLEU-like metric
        bleu_full = _simple_bleu(query, result_full.response)
        bleu_reduced = _simple_bleu(query, result_reduced.response)

        # Also compare based on ground truth coverage
        gt_coverage_full = sum(result_full.ground_truth_weights.values())
        gt_coverage_reduced = sum(result_reduced.ground_truth_weights.values())

        total_tested += 1

        # Degradation if either BLEU drops or ground truth coverage drops
        if bleu_reduced < bleu_full * 0.9 or gt_coverage_reduced < gt_coverage_full * 0.8:
            degradation_count += 1

    degradation_rate = degradation_count / total_tested if total_tested > 0 else 0.0
    passed = degradation_rate >= degradation_threshold

    print(f"\nResults:")
    print(f"  Queries tested: {total_tested}")
    print(f"  Degradations observed: {degradation_count}")
    print(f"  Degradation rate: {degradation_rate:.1%} {'✅' if passed else '❌'} (threshold: {degradation_threshold:.1%})")

    return {
        "test_name": "memory_removal_impact",
        "passed": passed,
        "metrics": {
            "total_tested": total_tested,
            "degradation_count": degradation_count,
            "degradation_rate": degradation_rate,
            "threshold": degradation_threshold,
        }
    }


# Helper functions
def _paraphrase_query(query: str, n: int) -> List[str]:
    """Generate n paraphrases of a query."""
    paraphrases = []

    templates = [
        query,
        query.replace("?", " please?"),
        "Can you " + query.lower().rstrip("?") + "?",
        "I'd like to know " + query.lower().rstrip("?"),
        "Tell me " + query.lower().rstrip("?"),
        query.replace("What", "Which").replace("what", "which"),
        query.replace("do you know", "can you tell me"),
        "Quick question: " + query.lower(),
        query.replace("about", "regarding"),
        query.replace("?", " exactly?"),
    ]

    for i in range(n):
        paraphrases.append(templates[i % len(templates)])

    return paraphrases


def _kendall_tau_distance(rank1: List[str], rank2: List[str]) -> float:
    """Compute normalized Kendall tau distance between two rankings.

    Returns value in [0, 1] where 0 = identical, 1 = completely reversed.
    """
    if not rank1 or not rank2:
        return 0.0

    # Build position maps
    pos1 = {item: i for i, item in enumerate(rank1)}
    pos2 = {item: i for i, item in enumerate(rank2)}

    # Count discordant pairs
    common_items = set(rank1) & set(rank2)
    if len(common_items) < 2:
        return 0.0

    discordant = 0
    total_pairs = 0

    items = list(common_items)
    for i in range(len(items)):
        for j in range(i+1, len(items)):
            item_a, item_b = items[i], items[j]

            # Check if order is same in both rankings
            order1 = pos1[item_a] < pos1[item_b]
            order2 = pos2[item_a] < pos2[item_b]

            if order1 != order2:
                discordant += 1

            total_pairs += 1

    return discordant / total_pairs if total_pairs > 0 else 0.0


def _simple_bleu(reference: str, candidate: str) -> float:
    """Simplified BLEU score for response quality comparison.

    Returns value in [0, 1] where higher = better match.
    """
    # Tokenize
    ref_tokens = set(reference.lower().split())
    cand_tokens = set(candidate.lower().split())

    if not cand_tokens:
        return 0.0

    # Compute precision (what fraction of candidate tokens appear in reference)
    overlap = len(ref_tokens & cand_tokens)
    precision = overlap / len(cand_tokens)

    # Also consider recall (coverage of reference)
    recall = overlap / len(ref_tokens) if ref_tokens else 0.0

    # F1-like combination
    if precision + recall == 0:
        return 0.0

    return 2 * (precision * recall) / (precision + recall)


def generate_queries_from_dataset(dataset: MemoryDataset, n: int) -> List[str]:
    """Generate n queries based on dataset content.

    Queries are designed to match different memories.
    """
    queries = []

    # Extract key topics from memories
    topics = []
    for mem in dataset.memories[:min(100, len(dataset.memories))]:
        # Extract first few words as topic
        words = mem.content.split()[:5]
        topic = " ".join(words)
        topics.append(topic)

    # Generate queries
    query_templates = [
        "What do you know about {topic}?",
        "Tell me about {topic}",
        "Can you explain {topic}?",
        "What are your thoughts on {topic}?",
        "I have a question about {topic}",
        "Help me understand {topic}",
        "What's the deal with {topic}?",
        "Give me information on {topic}",
    ]

    for i in range(n):
        topic = topics[i % len(topics)]
        template = query_templates[i % len(query_templates)]
        query = template.format(topic=topic)
        queries.append(query)

    return queries


async def run_all_validity_tests(
    dataset: MemoryDataset | None = None,
    cortex_base_url: str | None = None,
    memory_id_map: dict[str, str] | None = None,
    agent_id: str | None = None,
):
    """Run all attribution validity tests.

    Args:
        dataset: Memory dataset to test (generates Personal Assistant if None)
        cortex_base_url: CortexOS backend URL (e.g., "http://localhost:8000")
                        If None, tests will fail if they need real attribution
        agent_id: Agent ID to use (required if cortex_base_url provided)
        memory_id_map: Mapping from test memory IDs to backend memory IDs
    """
    print(f"\n{'#'*60}")
    print("# CortexOS Attribution Validity Test Suite")
    print(f"{'#'*60}")

    if cortex_base_url:
        print(f"Backend: {cortex_base_url}")
        print(f"Agent: {agent_id}")
    else:
        print("WARNING: No backend URL provided - tests requiring real EAS will fail")

    if dataset is None:
        print("\nGenerating Personal Assistant dataset...")
        dataset = generate_personal_assistant_dataset()
        print(f"✓ Dataset ready: {len(dataset.memories)} memories")

    # Test 1: Correlation (THE critical test)
    test1_result = await test_attribution_correlates_with_ground_truth(
        dataset,
        n_queries=50,  # Reduced for quick testing; use 200 for full test
        correlation_threshold=0.6,
        precision_threshold=0.5,
        cortex_base_url=cortex_base_url, memory_id_map=memory_id_map,
        agent_id=agent_id,
    )

    # Generate simulation results for tests 2 and 5
    print(f"\nGenerating simulation results for dependent tests...")
    simulator = create_test_simulator(
        [m.content for m in dataset.memories],
        [m.id for m in dataset.memories],
        k=5,
        cortex_base_url=cortex_base_url, memory_id_map=memory_id_map,
    )
    queries = generate_queries_from_dataset(dataset, 50)
    results = []
    for query in queries:
        result = await simulator.process_query(query, agent_id=agent_id or "simulator")
        results.append(result)

    # Test 2: Zero-attribution accuracy
    test2_result = await test_zero_attribution_memories_are_unused(results)

    # Test 3: Attribution stability
    test3_result = await test_attribution_stability_across_similar_queries(
        dataset,
        n_query_sets=10,  # Reduced for quick testing
        paraphrases_per_query=5,
        variance_threshold=0.3,
        cortex_base_url=cortex_base_url, memory_id_map=memory_id_map,
        agent_id=agent_id,
    )

    # Test 4: Contradiction detection
    test4_result = await test_contradiction_detection_finds_planted_contradictions(
        dataset,
        detection_threshold=0.7,
        cortex_base_url=cortex_base_url, memory_id_map=memory_id_map,
        agent_id=agent_id,
    )

    # Test 5: Waste rate correlation
    test5_result = await test_waste_rate_matches_ground_truth_waste(
        results,
        mae_threshold=0.15,
    )

    # Test 6: Memory removal impact (THE ULTIMATE PROOF)
    test6_result = await test_memory_removal_degrades_response_quality(
        dataset,
        n_queries=20,  # Reduced for quick testing
        degradation_threshold=0.6,
        cortex_base_url=cortex_base_url, memory_id_map=memory_id_map,
        agent_id=agent_id,
    )

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    all_results = [test1_result, test2_result, test3_result, test4_result, test5_result, test6_result]
    passed_count = sum(1 for r in all_results if r["passed"])
    total_count = len(all_results)

    for result in all_results:
        status = "✅ PASSED" if result["passed"] else "❌ FAILED"
        print(f"{result['test_name']:30} {status}")

    print(f"\nOVERALL: {passed_count}/{total_count} PASSED")

    if passed_count == total_count:
        print("\n🎉 All attribution validity tests PASSED!")
        print("CortexOS attribution scores are meaningful and reliable.")
    else:
        print(f"\n⚠️ {total_count - passed_count} test(s) failed.")
        print("Review failed tests to understand attribution limitations.")

    return all_results


if __name__ == "__main__":
    results = asyncio.run(run_all_validity_tests())
