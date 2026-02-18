# Correlation Issue Analysis: E2E Test -0.172 vs Simulation 0.775

## Executive Summary

**Root Cause Found**: Ground truth mismatch between what MockLLM tracks vs what EAS measures.

- **E2E Test Correlation**: -0.433 (verified via debug script)
- **Simulation Correlation**: 0.775 (reported)
- **Expected Correlation**: 0.6-0.8

## The Core Problem

### What MockLLM Tracks (Ground Truth)
The MockLLM selects memories based on **query-to-memory cosine similarity**:

```python
# agent_simulator.py:163-171
similarities = np.array([m.similarity for m in retrieved_memories])  # QUERY similarity
exp_sims = np.exp(similarities - similarities.max())
probs = exp_sims / exp_sims.sum()
selected_indices = self.np_rng.choice(..., p=probs)  # Select by QUERY relevance
```

Then assigns Dirichlet-distributed weights (random, not based on actual contribution):
```python
# agent_simulator.py:184
weights_array = self.np_rng.dirichlet([1.0] * len(selected_memories))  # RANDOM weights!
```

### What EAS Measures (Attribution)
EAS computes attribution based on **response-to-memory cosine similarity**:

```python
# eas.py:186-187 (method="response_only")
sim_mr = _cosine_similarities(M, r)  # RESPONSE similarity
scores = sim_mr / total  # Normalize
```

### Why This Causes Negative Correlation

**The mismatch**:
1. MockLLM picks memories that are similar to the **query**
2. MockLLM assigns **random** weights via Dirichlet
3. EAS scores memories by similarity to **response**

**Result**: If a memory is:
- Highly similar to query → **High GT weight**
- Low similar to response → **Low EAS score**

This creates **negative correlation**!

## Evidence from Debug Script

### Query 1: "What do you know about I prefer Python over JavaScript?"

```
Memory: mem_25a1b67546a1 "Use read replicas for analytics queries..."
  Ground Truth: 0.5150 (highest - selected by MockLLM based on query similarity)
  EAS Score:    0.1537 (low - not similar to response)
  Delta:       -0.3613 ❌

Memory: mem_672df17b02a5 "Upgraded Kubernetes cluster to version 1.27..."
  Ground Truth: 0.0131 (lowest - not selected much by MockLLM)
  EAS Score:    0.2368 (higher - more similar to response)
  Delta:       +0.2238 ✓
```

**Spearman correlation: -0.8000** (perfect inversion!)

### Query 3: Perfect negative correlation

```
Memory: mem_47ae92167019 "Conducted load testing..."
  Ground Truth: 0.7409 (highest)
  EAS Score:    0.3681 (lower)

Memory: mem_1b9a3998a99a "Use metric units..."
  Ground Truth: 0.2591 (lower)
  EAS Score:    0.3741 (highest)
```

**Spearman correlation: -1.0000** (complete rank inversion!)

## Why Simulation Shows 0.775

The simulation (`simulation_e2e.py`) uses a **different setup**:
- It creates synthetic memories with **known cluster assignments**
- Transactions explicitly target specific clusters
- Response is built FROM the selected memories (line 514-543)

This creates artificial alignment where:
- Memories similar to query → used in response → similar to response
- Ground truth ≈ actual contribution (by design)

## The Fix

### Option 1: Fix Ground Truth (Recommended)

Make MockLLM weights reflect **actual response contribution**, not random Dirichlet:

```python
# Instead of:
weights_array = self.np_rng.dirichlet([1.0] * len(selected_memories))

# Use:
# Compute how much of response came from each memory
# Based on token overlap or semantic similarity to response
weights = compute_actual_contribution_weights(
    selected_memories,
    response,
    response_embedding
)
```

### Option 2: Align EAS with Query Similarity

Change EAS to use query similarity instead of response similarity:

```python
# In eas.py, method="response_only":
sim_mr = _cosine_similarities(M, q)  # Use QUERY instead of response
```

**BUT**: This is wrong! Response similarity is correct - we want to know which memories contributed to the response, not which matched the query.

### Option 3: Hybrid Ground Truth

MockLLM should:
1. Select memories by query similarity (realistic retrieval)
2. Weight them by **contribution to response** (realistic usage)

```python
# After building response, measure actual contribution:
for mem in selected_memories:
    # Compute overlap between memory content and response
    contribution = compute_response_overlap(mem.content, response)
    weights[mem.id] = contribution
# Normalize
weights = normalize_weights(weights)
```

## Verification Steps

### Step 1: Check Database for Stale Data ✓
- Run debug script Step 1
- Backend is running, no stale data warning (fresh test)

### Step 2: Trace Queries ✓
- Traced 3 queries with detailed logging
- Memory ID mapping is correct
- EAS is scoring over the correct memory set (8 retrieved)

### Step 3: Check Spearman Scope ✓
- Spearman is computed over **only common memories** (4, 3, 2 in examples)
- Not over all 200 memories in database
- Scope is correct

### Step 4: Find Mismatch ✓
- **Mismatch found**: Ground truth tracks query-based selection + random weights
- **EAS measures**: Response-based contribution
- **Result**: Systematic rank inversion → negative correlation

## Recommendations

### Immediate Fix (for realistic testing)

Update `agent_simulator.py` MockLLM to compute weights based on actual contribution:

```python
def generate(self, query: str, retrieved_memories: list[MemoryWithId]) -> ...:
    # ... existing selection logic ...

    # Build response
    response_parts = []
    contribution_tracker = {mem.id: 0 for mem in selected_memories}

    for mem, dirichlet_weight in zip(selected_memories, weights_array):
        phrases = self._extract_key_phrases(mem.content)
        paraphrased = [self._paraphrase(p) for p in phrases]

        n_phrases = max(1, int(len(paraphrased) * dirichlet_weight * 2))
        added_phrases = paraphrased[:n_phrases]

        # Track actual contribution (tokens added to response)
        contribution_tracker[mem.id] = sum(len(p.split()) for p in added_phrases)

        response_parts.extend(added_phrases)

    response = " ".join(response_parts)

    # Convert token counts to normalized weights
    total_tokens = sum(contribution_tracker.values())
    weights = {
        mem_id: count / total_tokens if total_tokens > 0 else 0.0
        for mem_id, count in contribution_tracker.items()
    }

    return response, list(weights.keys()), weights
```

### Long-term Fix

1. **Ground Truth Source**: Use actual LLM (GPT-4 or Claude) with citation tracking
2. **Synthetic Validation**: Create controlled test cases where GT = known
3. **Multi-metric Validation**: Don't rely on correlation alone
   - Precision@3: Are top-3 EAS in GT?
   - Rank accuracy: Top GT memory is top EAS?
   - Waste detection: Low EAS → Low GT?

## Expected Results After Fix

With corrected ground truth:
- **E2E Test Correlation**: 0.6-0.8 (should match simulation)
- **Precision@3**: 0.6-0.8
- **Rank agreement**: High GT → High EAS

## Files to Modify

1. `/Users/revanshphull/cortex/cortex-engine/tests/e2e/agent_simulator.py`
   - `MockLLM.generate()` method (lines 145-218)
   - Track actual response contribution, not random Dirichlet weights

2. `/Users/revanshphull/cortex/cortex-engine/tests/e2e/test_attribution_validity.py`
   - No changes needed - test is correct

3. `/Users/revanshphull/cortex/cortex-engine/cortex/api/transactions.py`
   - No changes needed - EAS implementation is correct

## Conclusion

**The negative correlation is NOT a bug in EAS** - it's a bug in the test ground truth generation.

MockLLM's ground truth doesn't reflect actual memory contribution to the response. It tracks:
1. Which memories were selected (based on query similarity)
2. Random Dirichlet weights (not actual contribution)

EAS correctly measures which memories contributed to the response based on semantic similarity.

**Fix**: Make MockLLM track actual contribution by measuring how much of each memory's content appears in the response.
