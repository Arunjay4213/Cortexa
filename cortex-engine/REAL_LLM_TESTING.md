# Testing CortexOS EAS with Real LLMs (Claude/Gemini)

This guide shows how to test EAS attribution with **real Claude or Gemini APIs** instead of MockLLM.

## What This Tests

The real LLM test validates that **EAS scores correlate with which memories a real LLM actually cites**.

**How it works:**
1. Retrieves top-5 memories for a query
2. Prompts the real LLM to answer using those memories **with citations** ([1], [2], etc.)
3. Parses which memories the LLM actually cited
4. Compares LLM citations vs EAS attribution scores
5. Reports **Spearman correlation**

**Expected result:** Correlation > 0.5 means EAS successfully predicts which memories real LLMs use!

## Setup

### Option 1: Test with Claude API

```bash
# Install Claude SDK
pip install anthropic

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Make sure backend is running
curl http://localhost:8001/healthz

# Run test
cd cortex-engine
python tests/e2e/test_real_llm.py --llm claude --backend http://localhost:8001
```

### Option 2: Test with Gemini API

```bash
# Install Gemini SDK
pip install google-generativeai

# Set your API key
export GOOGLE_API_KEY="AIza..."

# Make sure backend is running
curl http://localhost:8001/healthz

# Run test
cd cortex-engine
python tests/e2e/test_real_llm.py --llm gemini --backend http://localhost:8001
```

## Test Options

```bash
# Test with 20 queries instead of 10
python tests/e2e/test_real_llm.py --llm claude --backend http://localhost:8001 --queries 20

# Test Gemini with 5 quick queries
python tests/e2e/test_real_llm.py --llm gemini --backend http://localhost:8001 --queries 5
```

## Expected Output

```
======================================================================
REAL LLM TEST: CLAUDE vs CortexOS EAS
======================================================================

Loading dataset...
✓ Loaded 200 memories

Initializing claude API...
✓ Using model: claude-3-5-sonnet-20241022

Pre-embedding memories...
✓ Embeddings shape: (200, 384)

Setting up CortexOS backend at http://localhost:8001...
✓ Seeded 200 memories to backend

Running 10 queries...

Query 1/10: What's my favorite programming language?...
  Response: Based on the memories, your favorite programming language is Python...
  Citations: 2 memories cited
  Correlation: 0.800

Query 2/10: Tell me about my pet...
  Response: According to the memory, your pet is a dog named Max [1]...
  Citations: 1 memories cited
  Correlation: 0.900

...

======================================================================
RESULTS
======================================================================

Queries tested: 10
Correlations computed: 10
Mean Spearman correlation: 0.723

✅ PASSED: EAS correlates well with CLAUDE citations!
   EAS can predict which memories real LLMs use.
```

## Interpreting Results

| Correlation | Interpretation |
|-------------|----------------|
| **≥ 0.5** | ✅ **PASSED** - EAS accurately predicts which memories the LLM uses |
| **0.3 - 0.5** | ⚠️ **MODERATE** - Some correlation, but not strong |
| **< 0.3** | ❌ **WEAK** - EAS doesn't align well with LLM citations |

## What's Being Measured

### LLM Citations (Ground Truth)
```
Question: What's my favorite programming language?

Response: Based on memory [1], you prefer Python over JavaScript [1]
for backend development. You also use black [2] for formatting.

Citations:
  [1] → Memory about Python preference (2 citations)
  [2] → Memory about black formatter (1 citation)

Weights:
  Memory 1: 2/3 = 0.667
  Memory 2: 1/3 = 0.333
```

### EAS Scores (What We're Testing)
```
EAS computes:
  Memory 1: 0.650 (high similarity to response)
  Memory 2: 0.350 (moderate similarity to response)
```

### Correlation
```
Spearman correlation between [0.667, 0.333] and [0.650, 0.350]
→ 1.0 (perfect rank correlation!)
```

## Why This Matters

- **MockLLM test** proves EAS correlates with token contribution (synthetic)
- **Real LLM test** proves EAS correlates with actual LLM citations (real-world)

If both pass, we have **strong evidence** that EAS attribution is meaningful and practical!

## Cost Estimate

### Claude API (Sonnet 3.5)
- Input: ~500 tokens/query × 10 queries = 5,000 tokens
- Output: ~200 tokens/query × 10 queries = 2,000 tokens
- **Cost:** ~$0.05 for 10 queries

### Gemini API (Flash 1.5)
- Input: ~500 tokens/query × 10 queries = 5,000 tokens
- Output: ~200 tokens/query × 10 queries = 2,000 tokens
- **Cost:** Free tier should cover this!

## Next Steps

After running the test:

1. **If correlation > 0.5:** ✅ EAS works with real LLMs! Document and celebrate.
2. **If correlation 0.3-0.5:** ⚠️ Investigate why (citation parsing? prompt design?)
3. **If correlation < 0.3:** ❌ Debug - maybe LLMs cite differently than EAS expects

## Troubleshooting

**Error: "ANTHROPIC_API_KEY not set"**
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

**Error: "Backend not running"**
```bash
# Start backend
uvicorn cortex.api.app:app --port 8001
```

**Error: "ModuleNotFoundError: anthropic"**
```bash
pip install anthropic
# or
pip install google-generativeai
```

**Low correlation (<0.3):**
- Check if LLM is actually using citations properly
- Try different queries that are more memory-specific
- Increase --queries to get more stable average

## Advanced: Compare Both LLMs

```bash
# Test both in sequence
python tests/e2e/test_real_llm.py --llm claude --backend http://localhost:8001 --queries 10
python tests/e2e/test_real_llm.py --llm gemini --backend http://localhost:8001 --queries 10

# Compare correlations
echo "Claude vs Gemini: Which LLM's citations correlate better with EAS?"
```

## Summary

This test validates that **EAS attribution works with production LLMs**, not just synthetic MockLLM.

**Key insight:** If real LLMs cite the same memories that EAS scores highly, then EAS is measuring something meaningful about memory usage!
