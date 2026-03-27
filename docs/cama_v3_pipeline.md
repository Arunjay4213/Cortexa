# CAMA v3: The SummaC-Inspired Rewrite

## THE FUNDAMENTAL MISTAKE WE'VE BEEN MAKING

We've been running a two-stage pipeline:
1. Detect hallucinated spans (LettuceDetect / EmbeddingDetector)
2. Attribute those spans to memories (NLI cross-encoder)

This fails in 5/8 real-world scenarios because **the response IS supported by the
memories — the memories themselves are wrong.** "Ships in 2-3 days" is perfectly
entailed by a memory that says "ships in 2-3 days." LettuceDetect correctly sees
this as grounded. But the memory is stale — the real policy changed to 5-7 days.

No hallucination detector will ever catch this. The response-to-memory relationship
is fine. The problem is the memory-to-reality relationship.

**We don't need a hallucination detector. We need a direct attribution matrix.**

## THE NEW APPROACH: SummaC-style NLI Pair Matrix

From SummaC (Laban et al., TACL 2022): NLI models fail at document-level
consistency checking because of granularity mismatch. They work at sentence level.
The fix: build an M×N entailment matrix between all source sentences and all
generated sentences, then aggregate.

Apply this to memory attribution:

```
Instead of: Detect spans → Attribute spans to memories
Do this:    Build NLI matrix (response_sentences × memories) → Direct attribution
```

### Step 1: Sentence-Level NLI Pair Matrix

Split the response into sentences. For each (response_sentence, memory) pair,
compute NLI scores. This gives us an N×M matrix where:
- N = number of response sentences
- M = number of memories
- Each cell = {entailment, contradiction, neutral} scores

```python
response_sentences = split_sentences(response)  # ["Ships in 2-3 days", "Free for orders over $50"]
memories = [mem.content for mem in memory_list]  # 47 memories

# Build the pair matrix (using bi-encoder pre-filter for speed)
# Step 1a: Embed everything
sent_embeddings = embed(response_sentences)  # N x 384
mem_embeddings = embed(memories)             # M x 384
cosine_sim = sent_embeddings @ mem_embeddings.T  # N x M

# Step 1b: For each sentence, pick top-K most similar memories
K = 10
for i, sent in enumerate(response_sentences):
    top_k_indices = argsort(cosine_sim[i])[-K:]
    
    # Step 1c: Run NLI cross-encoder on (memory, sentence) pairs
    pairs = [(memories[j], sent) for j in top_k_indices]
    nli_scores = cross_encoder.predict(pairs)  # Returns raw logits
    
    # Fill the matrix
    for j, scores in zip(top_k_indices, nli_scores):
        matrix[i][j] = scores  # {contradiction, entailment, neutral}
```

Total NLI calls: N × K (e.g., 3 sentences × 10 memories = 30 pairs)
Latency: ~150ms on CPU. Constant regardless of total memory count.

### Step 2: Attribution from the Matrix

For each response sentence, the memory with the **highest entailment score**
is the primary attribution source. No normalization needed — raw scores.

```python
for i, sent in enumerate(response_sentences):
    # Which memory does this sentence draw from?
    entailment_scores = [matrix[i][j]["entailment"] for j in range(M)]
    primary_memory = argmax(entailment_scores)
    primary_score = max(entailment_scores)
    
    # Is there a contradiction? (sentence entailed by one memory,
    # contradicted by another)
    contradiction_scores = [matrix[i][j]["contradiction"] for j in range(M)]
    top_contradiction = argmax(contradiction_scores)
    
    attribution = {
        "sentence": sent,
        "primary_memory": primary_memory,
        "entailment_score": primary_score,  # Raw logit, NOT normalized
        "contradicting_memory": top_contradiction if max(contradiction_scores) > threshold else None,
    }
```

**P@1 = "does the primary_memory match the expected culprit?"**

This works because:
- "Ships in 2-3 days" will have HIGH entailment with the stale shipping memory
- We don't need to detect it as a hallucination — we just need to know WHERE
  the sentence came from
- Then staleness is a metadata check: "is primary_memory stale?"

### Step 3: Memory Quality Diagnosis (No Detector Needed)

Once we know which memory each sentence draws from, diagnosis is pure metadata:

```python
for attr in attributions:
    memory = get_memory(attr["primary_memory"])
    
    # Staleness: metadata check
    if memory.source_updated_at and memory.source_updated_at > memory.created_at:
        attr["diagnosis"] = "stale_memory"
        attr["severity"] = (now - memory.created_at).days / 30
    
    # Ghost: no sentence draws from this memory
    # (computed after all attributions)
    
    # Contradiction: two memories entail contradictory sentences
    if attr["contradicting_memory"]:
        attr["diagnosis"] = "contradiction"
```

### Step 4: Ghost Detection (From the Matrix, Not a Detector)

A ghost memory is one where **no response sentence** has high entailment with it.
Read this directly from the matrix columns:

```python
for j, memory in enumerate(memories):
    max_entailment = max(matrix[i][j]["entailment"] for i in range(N))
    if max_entailment < ghost_threshold:  # e.g., raw logit < 0.0
        ghost_ids.append(memory.id)
```

This replaces the EmbeddingDetector's ghost detection AND the two-pass NLI
confirmation. One matrix, one pass.

### Step 5: Contradiction Detection (Memory-vs-Memory, Not Response-Based)

For contradictions between memories, use the Contradiction Detection approach
from the RAG systems paper. This is INDEPENDENT of the response:

```python
# Cluster memories by topic using embeddings
mem_embeddings = embed(memories)
cosine_sim = mem_embeddings @ mem_embeddings.T

# For each pair of similar memories (cosine > 0.75), check NLI
for i, j in high_similarity_pairs(cosine_sim, threshold=0.75):
    # Require content word overlap (same subject)
    if content_word_overlap(memories[i], memories[j]) < 2:
        continue
    
    # NLI contradiction check
    scores = cross_encoder.predict([(memories[i].content, memories[j].content)])
    if softmax(scores)["contradiction"] > 0.8:
        contradictions.append((i, j))
```

This runs ONCE when memories are loaded, not per-trace. Cost: O(M²) pairs
but pre-filtered by cosine similarity to ~M/10 pairs.

## WHY THIS FIXES THE REAL-WORLD BENCHMARK

The 5 failing scenarios all share the same pattern:
- Response is grounded in a stale/wrong memory
- LettuceDetect sees it as supported (correctly!)
- No spans → no attribution → P@1 = 0%

With the SummaC matrix approach:
- Response sentence "Ships in 2-3 days" → highest entailment with mem_2847
  (the stale shipping memory)
- No hallucination detector needed — we directly know mem_2847 is the source
- Staleness check: mem_2847.source_updated_at > mem_2847.created_at → STALE
- P@1 = correct, because we identified the source memory

**The hallucination detector was always the wrong tool for this job.**
We're not detecting hallucinations. We're tracing attributions.

## IMPLEMENTATION

### New file: `cama/matrix.py`

```python
"""SummaC-inspired NLI pair matrix for memory attribution.

Instead of detect-then-attribute, build a direct sentence×memory
entailment matrix and read attributions from it.
"""
from __future__ import annotations
import logging
import numpy as np
from cama.types import Memory, HallucinatedSpan, SpanAttribution, MemoryAttribution
from cama.text import split_sentences
from cama.nli import NLIModel

logger = logging.getLogger(__name__)


class NLIPairMatrix:
    """Sentence × Memory NLI pair matrix.
    
    Rows = response sentences
    Columns = memories
    Cells = {entailment, contradiction, neutral} raw logits
    """
    
    def __init__(
        self,
        top_k: int = 10,
        model_name: str = "cross-encoder/nli-deberta-v3-xsmall",
    ):
        self.top_k = top_k
        self.nli = NLIModel(model_name=model_name)
    
    def build(
        self,
        response: str,
        memories: list[Memory],
    ) -> dict:
        """Build the pair matrix and extract attributions.
        
        Returns:
        {
            "sentences": [str],
            "matrix": np.array of shape (N, M, 3),  # [contra, entail, neutral]
            "attributions": [{"sentence_idx", "memory_idx", "memory_id", "entailment", ...}],
            "ghost_ids": [str],
            "sentence_sources": [{sentence_idx: memory_id}],
        }
        """
        sentences = split_sentences(response)
        if not sentences:
            sentences = [response]
        
        N = len(sentences)
        M = len(memories)
        
        # Initialize matrix with zeros
        # Shape: (N, M, 3) — last dim is [contradiction, entailment, neutral]
        matrix = np.full((N, M, 3), -10.0)  # Default: very negative logits
        
        # Pre-filter: embed everything, find top-K per sentence
        active_pairs = self._prefilter(sentences, memories)
        
        # Build NLI pairs
        pairs = []
        pair_indices = []
        for si, mi_list in active_pairs.items():
            for mi in mi_list:
                pairs.append((memories[mi].content, sentences[si]))
                pair_indices.append((si, mi))
        
        if not pairs:
            return self._empty_result(sentences, memories)
        
        # Batch NLI inference
        scores = self.nli.predict_batch(pairs)
        
        # Fill matrix
        for (si, mi), score in zip(pair_indices, scores):
            matrix[si, mi, 0] = score["contradiction"]
            matrix[si, mi, 1] = score["entailment"]
            matrix[si, mi, 2] = score["neutral"]
        
        # Extract results
        attributions = self._extract_attributions(matrix, sentences, memories)
        ghost_ids = self._extract_ghosts(matrix, memories)
        
        return {
            "sentences": sentences,
            "matrix": matrix,
            "attributions": attributions,
            "ghost_ids": ghost_ids,
        }
    
    def _prefilter(
        self,
        sentences: list[str],
        memories: list[Memory],
    ) -> dict[int, list[int]]:
        """Bi-encoder pre-filter: top-K memories per sentence."""
        if len(memories) <= self.top_k:
            all_idx = list(range(len(memories)))
            return {si: all_idx for si in range(len(sentences))}
        
        try:
            from cama.embed import embed_texts, cosine_similarity_matrix
            
            sent_emb = embed_texts(sentences)
            mem_emb = embed_texts([m.content for m in memories])
            sim = cosine_similarity_matrix(sent_emb, mem_emb)
            
            result = {}
            for si in range(len(sentences)):
                top_k = np.argsort(sim[si])[-self.top_k:][::-1].tolist()
                result[si] = top_k
            return result
        except ImportError:
            all_idx = list(range(len(memories)))
            return {si: all_idx for si in range(len(sentences))}
    
    def _extract_attributions(
        self,
        matrix: np.ndarray,
        sentences: list[str],
        memories: list[Memory],
    ) -> list[dict]:
        """For each sentence, find primary source memory."""
        N, M, _ = matrix.shape
        attributions = []
        
        for si in range(N):
            entailment_scores = matrix[si, :, 1]  # Column 1 = entailment
            contradiction_scores = matrix[si, :, 0]  # Column 0 = contradiction
            
            primary_mi = int(np.argmax(entailment_scores))
            primary_score = float(entailment_scores[primary_mi])
            
            # Find if any memory contradicts this sentence
            top_contra_mi = int(np.argmax(contradiction_scores))
            top_contra_score = float(contradiction_scores[top_contra_mi])
            
            attributions.append({
                "sentence_idx": si,
                "sentence": sentences[si],
                "primary_memory_idx": primary_mi,
                "primary_memory_id": memories[primary_mi].id,
                "entailment_score": primary_score,
                "contradicting_memory_idx": top_contra_mi if top_contra_score > 0.0 else None,
                "contradicting_memory_id": memories[top_contra_mi].id if top_contra_score > 0.0 else None,
                "contradiction_score": top_contra_score,
            })
        
        return attributions
    
    def _extract_ghosts(
        self,
        matrix: np.ndarray,
        memories: list[Memory],
        threshold: float = 0.0,
    ) -> list[str]:
        """Memories where no sentence has entailment above threshold."""
        N, M, _ = matrix.shape
        ghost_ids = []
        
        for mi in range(M):
            max_entailment = float(np.max(matrix[:, mi, 1]))
            if max_entailment < threshold:
                ghost_ids.append(memories[mi].id)
        
        return ghost_ids
    
    def _empty_result(self, sentences, memories):
        return {
            "sentences": sentences,
            "matrix": np.zeros((len(sentences), len(memories), 3)),
            "attributions": [],
            "ghost_ids": [m.id for m in memories],
        }
```

### New file: `cama/pipeline_v3.py`

```python
"""CAMA v3 pipeline: SummaC-inspired direct attribution.

No hallucination detector. Direct sentence×memory NLI matrix.
"""
from __future__ import annotations
import time
import logging
from datetime import datetime

from cama.matrix import NLIPairMatrix
from cama.types import (
    Memory, HallucinatedSpan, SpanAttribution, MemoryAttribution,
    Contradiction, TraceResult,
)
from cama.text import split_sentences
from cama.nli import NLIModel
from cama.diagnose import Diagnoser

logger = logging.getLogger(__name__)


class CAMAv3Pipeline:
    """Direct attribution pipeline.
    
    1. Build NLI pair matrix (response_sentences × memories)
    2. Extract attributions from matrix
    3. Diagnose: staleness (metadata), ghosts (from matrix), contradictions (memory-vs-memory NLI)
    """
    
    def __init__(
        self,
        top_k: int = 10,
        model_name: str = "cross-encoder/nli-deberta-v3-xsmall",
    ):
        self.matrix_builder = NLIPairMatrix(top_k=top_k, model_name=model_name)
        self.nli = NLIModel(model_name=model_name)
        self.diagnoser = Diagnoser()
    
    def trace(
        self,
        query: str,
        response: str,
        memories: list[Memory],
    ) -> TraceResult:
        start = time.perf_counter()
        
        # Step 1: Build pair matrix
        result = self.matrix_builder.build(response, memories)
        
        # Step 2: Convert to SpanAttribution format (for compatibility)
        span_attributions = self._to_span_attributions(result, memories)
        
        # Step 3: Ghost detection (from matrix)
        ghost_ids = result["ghost_ids"]
        
        # Step 4: Staleness detection (pure metadata)
        stale_ids = self.diagnoser.detect_stale(memories)
        
        # Step 5: Contradiction detection (memory-vs-memory NLI)
        contradictions = self.diagnoser.detect_contradictions(
            memories, span_attributions, nli_model=self.nli,
        )
        
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        trace_result = TraceResult(
            query=query,
            response=response,
            span_attributions=span_attributions,
            ghosts=ghost_ids,
            stale=stale_ids,
            contradictions=contradictions,
            latency_ms=elapsed_ms,
            detection_method="NLIPairMatrix",
            attribution_method="SummaC-Direct",
        )
        trace_result.health_score = self.diagnoser.compute_health(trace_result)
        return trace_result
    
    def _to_span_attributions(
        self,
        matrix_result: dict,
        memories: list[Memory],
    ) -> list[SpanAttribution]:
        """Convert matrix attributions to SpanAttribution format."""
        span_attributions = []
        
        for attr in matrix_result["attributions"]:
            si = attr["sentence_idx"]
            sentence = attr["sentence"]
            
            # Create a "span" from the sentence
            span = HallucinatedSpan(
                text=sentence,
                start=0,  # Approximate
                end=len(sentence),
                score=1.0,  # Every sentence is "detected" in v3
            )
            
            # Build memory attributions for this sentence
            mem_attributions = []
            matrix = matrix_result["matrix"]
            
            for mi, mem in enumerate(memories):
                raw_contra = float(matrix[si, mi, 0])
                raw_entail = float(matrix[si, mi, 1])
                raw_neutral = float(matrix[si, mi, 2])
                
                # Direction
                diff = raw_entail - raw_contra
                if diff > 0.5:
                    direction = "supporting"
                elif diff < -0.5:
                    direction = "causing"
                elif max(raw_entail, raw_contra) < -5.0:
                    direction = "ghost"
                else:
                    direction = "ghost"
                
                relevance = max(raw_entail, raw_contra, 0.0)
                
                mem_attributions.append(MemoryAttribution(
                    memory_id=mem.id,
                    mas=relevance,
                    delta=diff,
                    direction=direction,
                    neutral_score=raw_neutral,
                    raw_contradiction=raw_contra,
                    raw_entailment=raw_entail,
                ))
            
            # Normalize MAS for display
            total = sum(a.mas for a in mem_attributions) + 1e-8
            for a in mem_attributions:
                a.mas = a.mas / total
            
            # Sort by raw scores
            def sort_key(a):
                if a.direction == "causing":
                    return (2, a.raw_contradiction)
                elif a.direction == "supporting":
                    return (1, a.raw_entailment)
                return (0, 0.0)
            mem_attributions.sort(key=sort_key, reverse=True)
            
            # Culprit
            culprit = None
            diagnosis = "supported"
            if attr.get("contradicting_memory_id") and attr["contradiction_score"] > 0.0:
                culprit = attr["contradicting_memory_id"]
                diagnosis = "wrong_memory"
            
            # Check if primary memory is stale
            primary_mem = next((m for m in memories if m.id == attr["primary_memory_id"]), None)
            if primary_mem and primary_mem.source_updated_at and primary_mem.created_at:
                if primary_mem.source_updated_at > primary_mem.created_at:
                    culprit = primary_mem.id
                    diagnosis = "stale_memory"
            
            span_attributions.append(SpanAttribution(
                span=span,
                attributions=mem_attributions,
                diagnosis=diagnosis,
                culprit_memory_id=culprit,
            ))
        
        return span_attributions
```

### Update the real-world evaluator

The P@1 evaluation needs a small update. In v3, EVERY response sentence gets
a SpanAttribution (no detector filtering). The evaluator should check if ANY
span_attribution has culprit_memory_id matching the expected culprit:

```python
# In evaluate.py, the P@1 check:
if expected_culprit and result.span_attributions:
    for sa in result.span_attributions:
        if sa.culprit_memory_id == expected_culprit:
            p_at_1_hits += 1
            break
```

This already works. But now EVERY sentence produces a SpanAttribution, so
we'll get matches even when the old detector would have found 0 spans.

### Update the benchmark runner

```python
# In runner.py, add a v3 pipeline option:
if args.pipeline == "v3":
    from cama.pipeline_v3 import CAMAv3Pipeline
    pipeline = CAMAv3Pipeline(top_k=10)
else:
    # Old v2 pipeline with detector + attributor
    pipeline = CAMAv2Pipeline(detector=..., attributor=...)
```

## EXPECTED RESULTS

| Metric | v2 (current) | v3 (predicted) | Why |
|--------|-------------|----------------|-----|
| P@1 (synthetic) | 77.8% | ~80% | Same NLI, but no detector noise |
| P@1 (real-world) | 27.3% | **>60%** | No detector = no lost spans |
| Ghost Precision | 38.7% → 71.2% | ~70% | Matrix-based, threshold tunable |
| Contradiction P | 4.8% | >40% | Strict memory-vs-memory NLI |
| Latency (47 mem) | 1379-3634ms | **<400ms** | 30 NLI pairs vs 141+ |
| Stale Detection | 100% | 100% | Pure metadata, unchanged |

The big unlock: real-world P@1 jumps from 27% to 60%+ because we SKIP THE
DETECTOR. Every response sentence gets attributed. The 5 scenarios that
produced 0 spans now produce attributions for every sentence.

## WHAT TO RUN

```bash
source ~/.venvs/cama/bin/activate
cd ~/cortex/cama-v2

# 1. Create the new files
# matrix.py and pipeline_v3.py as described above

# 2. Run unit tests (existing tests should still pass)
python -m pytest tests/ -q

# 3. Quick sanity check
python -c "
from cama.pipeline_v3 import CAMAv3Pipeline
from cama.types import Memory
from datetime import datetime, timedelta

pipeline = CAMAv3Pipeline(top_k=10)

# Stale memory scenario
memories = [
    Memory(id='m1', content='Express shipping takes 2-3 business days for \$9.99',
           created_at=datetime.now() - timedelta(days=90),
           source_updated_at=datetime.now() - timedelta(days=10)),
    Memory(id='m2', content='Free shipping on orders over \$50',
           created_at=datetime.now() - timedelta(days=30)),
    Memory(id='m3', content='User prefers dark mode and metric units',
           created_at=datetime.now() - timedelta(days=60)),
]

result = pipeline.trace(
    query='How fast does my order ship?',
    response='Your order ships in 2-3 business days via express for \$9.99.',
    memories=memories,
)

print(f'Health: {result.health_score}')
print(f'Ghosts: {result.ghosts}')
print(f'Stale: {result.stale}')
for sa in result.span_attributions:
    print(f'  Sentence: {sa.span.text[:60]}')
    print(f'  Culprit: {sa.culprit_memory_id}')
    print(f'  Diagnosis: {sa.diagnosis}')
    print(f'  Top attr: {sa.attributions[0].memory_id} (ent={sa.attributions[0].raw_entailment:.1f})')
"

# Expected output:
# Culprit: m1 (the stale shipping memory)
# Diagnosis: stale_memory
# m3 should be a ghost (no response sentence references it)

# 4. Run synthetic benchmark with v3 pipeline
cd ~/cortex/cama-v2-tests
PYTHONPATH=~/cortex/cama-v2:. ~/.venvs/cama/bin/python -m benchmarks.synthetic.evaluate \
  --n 50 --pipeline v3 --output benchmark_v3_matrix.json

# 5. Run real-world benchmark with v3 pipeline
PYTHONPATH=~/cortex/cama-v2:. ~/.venvs/cama/bin/python -m benchmarks.realworld.runner \
  --pipeline v3 --output realworld_v3_matrix.json

# 6. Generate report
PYTHONPATH=~/cortex/cama-v2:. ~/.venvs/cama/bin/python -m benchmarks.report
```

## WHY THIS IS THE RIGHT ARCHITECTURE

1. **SummaC proved** that sentence-level NLI matrices beat document-level NLI
   for consistency detection. We're applying the same insight to attribution.

2. **CARE-RAG proved** that conflict detection between retrieved evidence
   (memories) is a separate concern from response generation. We decouple
   memory quality checking from response grounding.

3. **The Contradiction Detection paper** showed three types of conflicts:
   self-contradictory, pairwise, conditional. Our memory-vs-memory NLI
   handles the pairwise case. Staleness metadata handles the temporal case.

4. **Every production reranking system** uses bi-encoder → cross-encoder.
   We use the same pattern: embedding pre-filter → NLI scoring.

5. **The detector was solving the wrong problem.** LettuceDetect answers
   "is this response supported by the context?" Cortexa needs to answer
   "which memory does each sentence come from, and is that memory reliable?"
   These are fundamentally different questions.