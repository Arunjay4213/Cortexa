# CAMA v2 — Causal Attribution for Memory-Augmented Generation

Research prototype for hallucination detection and memory attribution in RAG/agent systems.

## The Problem

Given K memories, a query, and a black-box LLM response:
1. Which spans in the response are hallucinated?
2. Which memory **caused** each hallucination?
3. Which memories are **ghosts** (in context but contributing nothing)?
4. Which memories **contradict** each other?

No access to model internals. Works with Claude, GPT, or any API.

## The Algorithm

**Stage 1 — Detection:** LettuceDetect (fine-tuned ModernBERT token classifier, 79% F1 on RAGTruth). CPU fallback via sentence-embedding similarity.

**Stage 2 — Attribution (novel):** Leave-One-Out via Detector. Remove each memory, re-run the detector, measure the change in hallucination scores. K+1 forward passes through a tiny encoder (~110ms for 10 memories on GPU) instead of K+1 LLM API calls.

**Stage 3 — Diagnosis:** Ghost detection, contradiction detection (attribution-based + NLI pairwise), staleness, health scoring.

## What's Novel

1. **LOO-via-Detector** — 50-100x cheaper than LOO-via-LLM
2. **Signed attribution** — "supporting" vs "causing" direction from LOO delta sign
3. **Joint detection + attribution** — detection model serves double duty
4. **Memory-level attribution** — individual memories, not document chunks
5. **Synthetic attribution benchmark** — planted-poison ground truth

## Install

```bash
# Core (types + pipeline logic only)
pip install -e .

# With GPU detection (recommended)
pip install -e ".[gpu]"

# CPU-only fallback
pip install -e ".[cpu]"

# For benchmarks
pip install -e ".[bench,dev]"
```

## Usage

```python
from cama.pipeline import CAMAv2

cama = CAMAv2()

result = cama.trace(
    query="What is the population of France?",
    response="France has 69 million people and its capital is Paris.",
    memories=[
        {"id": "m1", "content": "France has 67 million people."},
        {"id": "m2", "content": "The capital of France is Paris."},
        {"id": "m3", "content": "User prefers metric units."},
    ],
)

print(f"Health: {result.health_score}")
print(f"Hallucinated spans: {[s.text for s in result.hallucinated_spans]}")
print(f"Ghost memories: {result.ghost_memories}")

for sa in result.span_attributions:
    print(f"\nSpan: '{sa.span.text}' — {sa.diagnosis}")
    for attr in sa.attributions[:3]:
        print(f"  {attr.memory_id}: MAS={attr.mas:.2f}, direction={attr.direction}")
```

## Benchmarks

```bash
# Build synthetic dataset
python -m benchmarks.build_synthetic

# Run all benchmarks
python scripts/run_all_benchmarks.py

# Individual benchmarks
python -m benchmarks.ragtruth_eval
python -m benchmarks.synthetic_eval
python -m benchmarks.latency_eval
```

## Tests

```bash
pytest tests/ -v
```

## Project Structure

```
cama-v2/
├── cama/
│   ├── types.py        # Pydantic data models
│   ├── text.py         # Sentence splitting, number extraction
│   ├── detect.py       # Stage 1: hallucination detection
│   ├── attribute.py    # Stage 2: LOO-via-detector attribution
│   ├── diagnose.py     # Stage 3: ghost/contradiction/stale/health
│   ├── pipeline.py     # Full pipeline orchestrator
│   ├── embed.py        # Embedding utilities
│   └── nli.py          # NLI cross-encoder for contradictions
├── tests/
├── benchmarks/
└── scripts/
```
