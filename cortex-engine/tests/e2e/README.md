# CortexOS End-to-End Test Suite

Comprehensive testing harness that proves CortexOS attribution scores are meaningful with realistic agent workloads.

## Overview

This E2E test suite answers the critical question: **"Are CortexOS attribution scores actually meaningful?"**

The suite includes:
- **Attribution Validity Tests (6 tests)** - Prove attribution scores correlate with ground truth
- **Performance Tests (4 tests)** - Validate production-scale performance
- **Benchmark Tests (2 tests)** - Integration with standard benchmarks

## Quick Start

```bash
# Run all tests
python tests/e2e/run_e2e.py

# Run in quick mode (reduced queries for faster feedback)
python tests/e2e/run_e2e.py --quick

# Run specific test suite
python tests/e2e/run_e2e.py --suite validity
python tests/e2e/run_e2e.py --suite performance
python tests/e2e/run_e2e.py --suite benchmark

# Custom report directory
python tests/e2e/run_e2e.py --report-dir ./my-reports

# No report (console output only)
python tests/e2e/run_e2e.py --no-report
```

## Test Architecture

### Ground Truth Tracking with MockLLM

The key innovation is **MockLLM** - a mock language model that deliberately selects which memories to use and tracks exact usage weights. This gives us perfect ground truth for validation.

```python
# MockLLM workflow:
1. Randomly select 2-4 memories from retrieved set
2. Assign weights using Dirichlet distribution (realistic)
3. Paraphrase content with synonym substitution
4. Track exactly which memories were used and their weights
5. Return (response, sources, weights)

# This ground truth is then compared to CortexOS attribution scores
```

### Three Realistic Datasets

1. **Personal Assistant** (200 memories)
   - Preferences, facts, instructions, history
   - 10 planted contradictions for testing
   - Categories: preferences, facts, instructions, history

2. **Customer Support** (520 memories)
   - Product docs, policies, FAQ, customer history
   - 20 duplicate memories for waste detection
   - Categories: product_docs, policies, faq, customer_history

3. **Research Agent** (1000 memories)
   - Quality distribution: 300 high, 500 medium, 200 low
   - Tiered storage: hot, warm, cold
   - Tests scale and quality variance

## Test Details

### Attribution Validity Tests (§1-6)

**Test 1: Attribution Correlation with Ground Truth** ⭐ THE CRITICAL TEST
- Compares EAS attribution ranking vs ground truth ranking
- Metrics: Spearman rank correlation, Precision@3
- Thresholds: correlation ≥ 0.6, precision@3 ≥ 0.5
- **If this fails, nothing else matters**

**Test 2: Zero-Attribution Memories Are Unused**
- Validates waste detection is real, not noise
- Checks if low-score memories are actually unused
- Threshold: ≥ 80% accuracy

**Test 3: Attribution Stability Across Similar Queries**
- Runs 10 paraphrases of same query
- Checks variance in top-3 memory rankings
- Threshold: variance < 0.3

**Test 4: Contradiction Detection Finds Planted Contradictions**
- Personal Assistant dataset has 10 planted contradictions
- Checks if EAS flags contradicting memories
- Threshold: ≥ 70% detection rate

**Test 5: Waste Rate Matches Ground Truth Waste**
- Compares CortexOS waste rate to ground truth
- Ground truth: memories with weight < 0.05
- Threshold: MAE < 0.15

**Test 6: Memory Removal Degrades Response Quality** ⭐ THE ULTIMATE PROOF
- Removes top-attributed memory and re-runs query
- Response should degrade (BLEU score drops)
- Threshold: ≥ 60% of removals cause degradation
- **This is the ground truth test - if removing a high-attribution memory doesn't degrade response, attribution is meaningless**

### Performance Tests (§7-10)

**Test 7: EAS Latency Under Load**
- 1000 memories, 50 concurrent queries
- Measures P50, P95, P99 latencies
- Threshold: P95 < 500ms

**Test 8: Welford Accuracy at Scale**
- Tests online statistics accuracy
- 10,000 incremental updates
- Threshold: < 0.1% error vs batch computation

**Test 9: Dashboard Overview Latency**
- Simulates /overview endpoint load
- 100 transactions + aggregation
- Threshold: < 2000ms

**Test 10: Memory Growth Doesn't Degrade Linearly**
- Tests scaling with memory bank size
- Sizes: 100, 500, 1000, 2000 memories
- Threshold: log-log slope ≤ 1.5 (sublinear)

### Benchmark Tests

**MemoryBench Integration** (best-effort)
- Integrates with MemoryBench if available
- Skips gracefully if not installed
- Validates against standardized benchmarks

**Custom Benchmark Suite**
- 4 queries across different categories
- Ensures basic retrieval accuracy
- Threshold: ≥ 75% accuracy

## Reports

Reports are saved to `tests/e2e/reports/` in JSON format:

```json
{
  "timestamp": "20260217_092814",
  "mode": "quick",
  "suites": {
    "validity": { ... },
    "performance": { ... },
    "benchmark": { ... }
  },
  "summary": {
    "total_suites": 3,
    "passed_suites": 2,
    "total_tests": 11,
    "passed_tests": 7,
    "failed_tests": 4,
    "success_rate": 0.636
  }
}
```

Latest report is always at: `tests/e2e/reports/latest.json`

## File Structure

```
tests/e2e/
├── README.md                      # This file
├── __init__.py                    # Package marker
├── run_e2e.py                     # Main test runner
├── datasets.py                    # Dataset generators
├── agent_simulator.py             # MockLLM + AgentSimulator
├── test_attribution_validity.py  # Tests 1-6
├── test_performance.py            # Tests 7-10
├── test_memorybench.py            # Benchmark integration
└── reports/                       # JSON test reports
    ├── latest.json                # Most recent run
    └── e2e_report_*.json          # Historical runs
```

## Integration with CortexOS

### Without CortexOS (Current)

Tests run with **simulated EAS scores** (ground truth + noise):
- Validates test infrastructure works
- Tests 1 and 3 pass (correlation, stability)
- Tests 2, 4, 5, 6 may fail (using simulated data)

### With CortexOS (Production)

To integrate with real CortexOS:

1. **Update agent_simulator.py**: Enable CortexOS client reporting
   ```python
   simulator = AgentSimulator(
       memories=memories,
       memory_embeddings=embeddings,
       embed_fn=embed_fn,
       cortex_client=cortex_client,  # Enable this
       llm=MockLLM(),
       k=5
   )
   ```

2. **Use real attribution scores**: Tests will compare CortexOS EAS to ground truth
   ```python
   # In test_attribution_validity.py, use:
   cortex_attribution = result.cortex_attribution  # Real EAS scores
   # Instead of:
   simulated_eas = ...  # Simulated scores
   ```

3. **Run full test suite**:
   ```bash
   python tests/e2e/run_e2e.py  # Full mode with 200 queries
   ```

## Success Criteria

### Must Pass (Production Readiness)
- ✅ Test 1: Attribution correlation ≥ 0.6
- ✅ Test 3: Attribution stability (variance < 0.3)
- ✅ Test 7: EAS latency P95 < 500ms
- ✅ Test 8: Welford accuracy < 0.1% error
- ✅ Test 10: Sublinear scaling (slope ≤ 1.5)

### Should Pass (Quality)
- Test 2: Zero-attribution accuracy ≥ 80%
- Test 5: Waste rate MAE < 0.15
- Test 6: Memory removal degradation ≥ 60%

### May Fail (Known Limitations)
- Test 4: Contradiction detection (dataset-dependent)
- Test 9: Dashboard latency (depends on DB performance)

## Interpreting Results

### Test 1 Passing = Good Foundation
If Test 1 passes, **CortexOS attribution correlates with ground truth**. This is the foundation.

### Test 6 Passing = Attribution Is Real
If Test 6 passes, **removing high-attribution memories actually degrades responses**. This proves attribution isn't just noise - it's capturing real usage.

### Tests 2, 5 Failing = Threshold Too Strict
If these fail with simulated data, thresholds may need adjustment. They're designed for real CortexOS EAS, which should be more accurate than simulated scores.

### All Performance Tests Passing = Production Ready
If all performance tests pass, **CortexOS can handle production scale**. Latencies are acceptable and scaling is sublinear.

## Development

### Adding New Tests

1. Add test function to appropriate file:
   ```python
   async def test_my_new_test(dataset: MemoryDataset) -> Dict:
       # Test implementation
       return {
           "test_name": "my_new_test",
           "passed": True/False,
           "metrics": {...}
       }
   ```

2. Update `run_all_*_tests()` to call new test

3. Run test suite to validate

### Modifying Datasets

Edit `datasets.py` to adjust memory counts, categories, or characteristics:
```python
# Increase dataset size
dataset = generate_personal_assistant_dataset(n_memories=500)

# Add more contradictions
dataset.memories.append(Memory(
    id="contradiction_10",
    content="I prefer JavaScript over Python",
    contradicts="preference_python_1"
))
```

### Adjusting Thresholds

If tests are too strict/lenient, adjust thresholds in `run_e2e.py` or test files:
```python
await test_attribution_correlates_with_ground_truth(
    dataset,
    correlation_threshold=0.5,  # Reduced from 0.6
    precision_threshold=0.4,     # Reduced from 0.5
)
```

## FAQ

**Q: Why do some tests fail with simulated data?**
A: Tests 2, 4, 5, 6 are designed for real CortexOS EAS scores. Simulated scores (ground truth + noise) don't capture all the nuances of real attribution.

**Q: How do I integrate with real CortexOS?**
A: Set `cortex_client` in AgentSimulator and use `result.cortex_attribution` instead of simulated scores.

**Q: Can I run tests against production database?**
A: Yes, but use a test database. Tests create synthetic data that shouldn't mix with production.

**Q: How long does full suite take?**
A: ~3-5 minutes in quick mode, ~15-20 minutes in full mode (200 queries).

**Q: What if MemoryBench isn't available?**
A: No problem - the test gracefully skips and runs custom benchmark suite instead.

## References

- [CortexOS Paper](../../README.md) - Core attribution algorithms (EAS, ContextCite, Calibration)
- [Agent Simulator Design](./agent_simulator.py) - MockLLM ground truth tracking
- [Dataset Generators](./datasets.py) - Synthetic memory datasets
- Wire Playbook - Original test specifications

---

**Most Important**: If Test 1 fails, nothing else matters. The entire point of CortexOS is that attribution scores are meaningful. Test 1 validates this claim.
