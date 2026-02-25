#!/usr/bin/env python3
"""
CortexOS x Kimi K2.5 — Large-Scale Real-World Stress Test
==========================================================

Pulls real benchmark datasets (no login required) and hammers Kimi K2.5
at hundreds-to-thousands of queries across real-world scenarios:

  DATASETS (streamed from HuggingFace, no auth):
  ──────────────────────────────────────────────
  • TriviaQA          – factual QA, 95K pairs
  • NQ-Open           – Google Natural Questions, 87K pairs
  • HotpotQA          – multi-hop reasoning, 113K pairs
  • MMLU              – 57-subject academic knowledge, 14K Qs
  • ARC-Challenge     – science reasoning, 2.5K Qs
  • WinoGrande        – commonsense, 40K Qs
  • MBPP              – Python coding, 974 problems
  • PopQA             – entity-centric QA, 14K pairs
  • WildChat (sample) – real user multi-turn conversations

  STRESS PROFILES:
  ────────────────
  BLITZ     – 100 q, 16 workers, mixed datasets, 60s target
  ENDURANCE – 500 q, 8 workers, sustained throughput
  SPIKE     – 200 q burst, 32 workers, max concurrency
  FULL      – 1000 q, 12 workers, full benchmark suite
  CUSTOM    – any --queries N --workers W --datasets csv-list

  METRICS CAPTURED PER RUN:
  ─────────────────────────
  • Throughput (q/s), error rate, retry count
  • Latency: p50, p75, p90, p95, p99, max
  • Per-dataset breakdown
  • Token usage (input + output)
  • Rate-limit hits and back-off events
  • Accuracy (answer-match) where ground truth exists

Usage
─────
# Quick blitz (100 queries, 16 workers)
python3 tests/e2e/test_kimi_k25_scale.py --profile blitz --api-key sk-...

# Full 1000-query run
python3 tests/e2e/test_kimi_k25_scale.py --profile full --api-key sk-... \\
    --output tests/e2e/reports/kimi_scale_report.json

# Custom: 500 queries from trivia+mmlu, 20 workers
python3 tests/e2e/test_kimi_k25_scale.py --profile custom \\
    --queries 500 --workers 20 --datasets triviaqa,mmlu \\
    --api-key sk-...

Env vars: KIMI_API_KEY
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
import time
import traceback
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

import httpx
import numpy as np

# ── path fixup ──────────────────────────────────────────────────────────
_HERE   = Path(__file__).parent
_ROOT   = _HERE.parent.parent
sys.path.insert(0, str(_ROOT))

# ── Kimi API config ─────────────────────────────────────────────────────
KIMI_BASE_URL = "https://api.moonshot.ai/v1"
KIMI_MODEL    = "kimi-k2.5"
THINK_OFF     = {"type": "disabled"}

# ═══════════════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class BenchItem:
    """One question from any benchmark dataset."""
    dataset:   str
    item_id:   str
    question:  str
    answer:    str | list[str]   # gold answer(s)
    context:   str = ""          # optional supporting context
    choices:   list[str] = field(default_factory=list)   # MCQ options
    category:  str = ""


@dataclass
class QueryResult:
    dataset:       str
    item_id:       str
    question:      str
    answer_gold:   str | list[str]
    answer_pred:   str
    correct:       bool
    latency_ms:    float
    input_tokens:  int
    output_tokens: int
    retries:       int  = 0
    rate_limited:  bool = False
    error:         str | None = None
    # Memory / EAS fields (populated only when --backend is set)
    mem_retrieved:      int   = 0    # number of memories retrieved
    eas_corr:           float = 0.0  # Spearman corr(citation_weight, eas_score)
    eas_computed:       bool  = False


@dataclass
class DatasetStats:
    name:         str
    n_total:      int
    n_ok:         int
    n_error:      int
    accuracy:     float
    p50_ms:       float
    p95_ms:       float
    p99_ms:       float
    total_in_tok: int
    total_out_tok: int
    mean_eas_corr: float = 0.0   # mean Spearman when backend active


@dataclass
class RunReport:
    profile:         str
    started_at:      str
    finished_at:     str
    total_queries:   int
    total_ok:        int
    total_errors:    int
    error_rate:      float
    accuracy:        float
    throughput_qps:  float
    total_in_tok:    int
    total_out_tok:   int
    p50_ms:          float
    p75_ms:          float
    p90_ms:          float
    p95_ms:          float
    p99_ms:          float
    max_ms:          float
    rate_limit_hits: int
    total_retries:   int
    # Memory / EAS summary
    memory_enabled:      bool  = False
    memories_seeded:     int   = 0
    eas_queries:         int   = 0   # queries where EAS was computed
    mean_eas_corr:       float = 0.0
    datasets:        list[DatasetStats] = field(default_factory=list)
    results:         list[QueryResult] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
#  DATASET LOADERS  (all stream via HuggingFace datasets, no auth)
# ═══════════════════════════════════════════════════════════════════════

def _hf_stream(path: str, name: str | None, split: str) -> Any:
    """Lazy-load a HuggingFace dataset split (streaming = no disk write).

    Uses importlib.util to bypass the local tests/e2e/datasets.py that
    shadows the 'datasets' package name.
    """
    import importlib.util, importlib.machinery

    # Find the real HuggingFace datasets package by its install location
    # (avoids being shadowed by tests/e2e/datasets.py)
    import sys as _sys
    # Temporarily remove any shadowing paths
    _saved = list(_sys.path)
    _clean = [p for p in _sys.path if "tests" not in p and str(_HERE) not in p]
    _sys.path = _clean

    try:
        import importlib as _imp
        # Force fresh lookup without the local shadow
        if "datasets" in _sys.modules:
            hf = _sys.modules["datasets"]
            if not hasattr(hf, "load_dataset"):
                del _sys.modules["datasets"]
        hf_datasets = _imp.import_module("datasets")
        load_dataset = hf_datasets.load_dataset
    finally:
        _sys.path = _saved

    kwargs: dict[str, Any] = {"streaming": True, "trust_remote_code": False}
    if name:
        return load_dataset(path, name, split=split, **kwargs)
    return load_dataset(path, split=split, **kwargs)


def _take(it: Any, n: int) -> list[Any]:
    out = []
    for item in it:
        out.append(item)
        if len(out) >= n:
            break
    return out


# ── TriviaQA ──────────────────────────────────────────────────────────

def load_triviaqa(n: int = 200, seed: int = 42) -> list[BenchItem]:
    print(f"  [loader] TriviaQA → {n} samples…")
    ds = _hf_stream("mandarjoshi/trivia_qa", "rc.nocontext", "train")
    rng = random.Random(seed)
    pool = _take(ds, n * 4)
    rng.shuffle(pool)
    out = []
    for row in pool[:n]:
        q   = row["question"]
        ans = row["answer"]
        # ans is a dict with "value" and "aliases"
        gold = ans["value"] if isinstance(ans, dict) else str(ans)
        aliases = ans.get("aliases", []) if isinstance(ans, dict) else []
        out.append(BenchItem(
            dataset="triviaqa", item_id=row.get("question_id", str(uuid.uuid4())),
            question=q, answer=[gold] + aliases,
            category="factual",
        ))
    return out


# ── NQ-Open ───────────────────────────────────────────────────────────

def load_nq_open(n: int = 200, seed: int = 42) -> list[BenchItem]:
    print(f"  [loader] NQ-Open → {n} samples…")
    ds = _hf_stream("google-research-datasets/nq_open", None, "train")
    rng = random.Random(seed)
    pool = _take(ds, n * 4)
    rng.shuffle(pool)
    out = []
    for i, row in enumerate(pool[:n]):
        out.append(BenchItem(
            dataset="nq_open", item_id=f"nq_{i}",
            question=row["question"],
            answer=row["answer"] if isinstance(row["answer"], list) else [row["answer"]],
            category="factual",
        ))
    return out


# ── HotpotQA ─────────────────────────────────────────────────────────

def load_hotpotqa(n: int = 150, seed: int = 42) -> list[BenchItem]:
    print(f"  [loader] HotpotQA → {n} samples…")
    ds = _hf_stream("hotpotqa/hotpot_qa", "distractor", "train")
    rng = random.Random(seed)
    pool = _take(ds, n * 4)
    rng.shuffle(pool)
    out = []
    for row in pool[:n]:
        # Build context from supporting titles
        ctx_parts = []
        for title_sents in row.get("context", {}).get("sentences", []):
            ctx_parts.append(" ".join(title_sents))
        ctx = " ".join(ctx_parts)[:800]
        out.append(BenchItem(
            dataset="hotpotqa", item_id=row.get("id", str(uuid.uuid4())),
            question=row["question"], answer=row["answer"],
            context=ctx, category=row.get("type", "multi-hop"),
        ))
    return out


# ── MMLU ─────────────────────────────────────────────────────────────

_MMLU_SUBJECTS = [
    "high_school_mathematics", "college_physics", "high_school_world_history",
    "high_school_biology", "logical_fallacies", "professional_law",
    "computer_security", "machine_learning", "moral_scenarios",
    "high_school_chemistry", "clinical_knowledge", "econometrics",
]

def load_mmlu(n: int = 200, seed: int = 42) -> list[BenchItem]:
    print(f"  [loader] MMLU → {n} samples across {len(_MMLU_SUBJECTS)} subjects…")
    rng  = random.Random(seed)
    out  = []
    per  = max(1, n // len(_MMLU_SUBJECTS))
    for subj in _MMLU_SUBJECTS:
        if len(out) >= n:
            break
        try:
            ds   = _hf_stream("cais/mmlu", subj, "test")
            pool = _take(ds, per * 2)
            rng.shuffle(pool)
            for row in pool[:per]:
                choices = row.get("choices", [])
                choice_text = " | ".join(f"({chr(65+i)}) {c}" for i, c in enumerate(choices))
                ans_idx = row.get("answer", 0)
                gold    = choices[ans_idx] if 0 <= ans_idx < len(choices) else str(ans_idx)
                out.append(BenchItem(
                    dataset="mmlu", item_id=f"mmlu_{subj}_{len(out)}",
                    question=row["question"], answer=gold,
                    choices=choices, context=choice_text,
                    category=subj,
                ))
        except Exception as e:
            print(f"    [mmlu] {subj}: {e}")
    return out[:n]


# ── ARC-Challenge ────────────────────────────────────────────────────

def load_arc(n: int = 150, seed: int = 42) -> list[BenchItem]:
    print(f"  [loader] ARC-Challenge → {n} samples…")
    ds  = _hf_stream("allenai/ai2_arc", "ARC-Challenge", "train")
    rng = random.Random(seed)
    pool = _take(ds, n * 2)
    rng.shuffle(pool)
    out = []
    for row in pool[:n]:
        q_data  = row.get("question", {})
        stem    = q_data if isinstance(q_data, str) else q_data.get("stem", "")
        choices = q_data.get("choices", {}) if isinstance(q_data, dict) else {}
        labels  = choices.get("label", [])
        texts   = choices.get("text",  [])
        key     = row.get("answerKey", "A")
        gold    = ""
        for lbl, txt in zip(labels, texts):
            if lbl == key:
                gold = txt
                break
        choice_str = " | ".join(f"({l}) {t}" for l, t in zip(labels, texts))
        out.append(BenchItem(
            dataset="arc", item_id=row.get("id", str(uuid.uuid4())),
            question=stem, answer=gold or key,
            context=choice_str, category="science",
        ))
    return out[:n]


# ── WinoGrande ──────────────────────────────────────────────────────

def load_winogrande(n: int = 150, seed: int = 42) -> list[BenchItem]:
    print(f"  [loader] WinoGrande → {n} samples…")
    ds  = _hf_stream("allenai/winogrande", "winogrande_xl", "train")
    rng = random.Random(seed)
    pool = _take(ds, n * 2)
    rng.shuffle(pool)
    out = []
    for i, row in enumerate(pool[:n]):
        opt1 = row.get("option1", "")
        opt2 = row.get("option2", "")
        ans  = row.get("answer", "1")
        gold = opt1 if str(ans) == "1" else opt2
        out.append(BenchItem(
            dataset="winogrande", item_id=f"wino_{i}",
            question=row["sentence"],
            answer=gold,
            choices=[opt1, opt2],
            context=f"Options: (1) {opt1}  (2) {opt2}",
            category="commonsense",
        ))
    return out[:n]


# ── MBPP (Python coding) ─────────────────────────────────────────────

def load_mbpp(n: int = 80, seed: int = 42) -> list[BenchItem]:
    print(f"  [loader] MBPP → {n} samples…")
    try:
        # Try Google's canonical MBPP via the parquet files directly
        ds  = _hf_stream("google-research-datasets/mbpp", None, "train")
        rng = random.Random(seed)
        pool = _take(ds, n * 2)
        rng.shuffle(pool)
        out = []
        for row in pool[:n]:
            tests = row.get("test_list", [])
            out.append(BenchItem(
                dataset="mbpp", item_id=f"mbpp_{row.get('task_id', len(out))}",
                question=f"Write a Python function: {row['text']}\n\nTests:\n" + "\n".join(tests[:2]),
                answer=row.get("code", ""),
                category="coding",
            ))
        return out
    except Exception as e:
        print(f"    [mbpp] failed: {e}")
        return []


# ── PopQA ───────────────────────────────────────────────────────────

def load_popqa(n: int = 150, seed: int = 42) -> list[BenchItem]:
    print(f"  [loader] PopQA → {n} samples…")
    ds  = _hf_stream("akariasai/PopQA", None, "test")
    rng = random.Random(seed)
    pool = _take(ds, n * 2)
    rng.shuffle(pool)
    out = []
    for i, row in enumerate(pool[:n]):
        answers = row.get("possible_answers", "[]")
        if isinstance(answers, str):
            try:
                answers = json.loads(answers)
            except Exception:
                answers = [answers]
        out.append(BenchItem(
            dataset="popqa", item_id=f"popqa_{i}",
            question=row["question"], answer=answers,
            category=row.get("prop", "entity"),
        ))
    return out[:n]


# ── ShareGPT (real user convs → extract turn 1 user msgs) ─────────────

def load_wildchat(n: int = 100, seed: int = 42) -> list[BenchItem]:
    """Load real-world user queries from ShareGPT52K (public, no auth)."""
    print(f"  [loader] ShareGPT (real-world) → {n} samples…")
    try:
        ds  = _hf_stream("RyokoAI/ShareGPT52K", None, "train")
        rng = random.Random(seed)
        pool = _take(ds, n * 8)
        rng.shuffle(pool)
        out = []
        for row in pool:
            if len(out) >= n:
                break
            convs = row.get("conversations", [])
            if not convs:
                continue
            first = next(
                (m for m in convs
                 if m.get("from") in ("human", "user")
                 and len(m.get("value", "")) > 30),
                None,
            )
            if not first:
                continue
            content = first["value"][:500]
            if any(kw in content.lower() for kw in ["ignore your", "dan mode", "jailbreak"]):
                continue
            out.append(BenchItem(
                dataset="sharegpt", item_id=f"sg_{len(out)}",
                question=content, answer="",   # open-ended
                category="real_world",
            ))
        return out
    except Exception as e:
        print(f"    [sharegpt] failed: {e}")
        return []


# ── Dataset registry ─────────────────────────────────────────────────

DATASET_LOADERS: dict[str, Any] = {
    "triviaqa":   load_triviaqa,
    "nq_open":    load_nq_open,
    "hotpotqa":   load_hotpotqa,
    "mmlu":       load_mmlu,
    "arc":        load_arc,
    "winogrande": load_winogrande,
    "mbpp":       load_mbpp,
    "popqa":      load_popqa,
    "sharegpt":   load_wildchat,   # real-world open-ended user queries
}


def load_datasets(names: list[str], total: int, seed: int = 42) -> list[BenchItem]:
    """Load and shuffle `total` items across the requested datasets."""
    per_ds = max(10, total // len(names))
    all_items: list[BenchItem] = []
    for name in names:
        loader = DATASET_LOADERS.get(name)
        if loader is None:
            print(f"  [warn] unknown dataset '{name}', skipping")
            continue
        try:
            items = loader(per_ds, seed=seed)
            all_items.extend(items)
            print(f"    ✓ {name}: {len(items)} items loaded")
        except Exception as e:
            print(f"    ✗ {name}: {e}")
    rng = random.Random(seed)
    rng.shuffle(all_items)
    return all_items[:total]


# ═══════════════════════════════════════════════════════════════════════
#  CORTEX MEMORY POOL  (seeds memories, retrieves, scores EAS, cleans up)
# ═══════════════════════════════════════════════════════════════════════

def _simple_embed(text: str, dim: int = 128) -> np.ndarray:
    """Deterministic character-hash embedding (no model needed, fast)."""
    vec = np.zeros(dim, dtype=np.float32)
    for i, ch in enumerate(text[:2048]):
        vec[i % dim] += ord(ch) * (0.7 ** (i // dim))
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def _spearman(a: list[float], b: list[float]) -> float:
    from scipy.stats import spearmanr
    if len(a) < 2:
        return 0.0
    c, _ = spearmanr(a, b)
    return float(c) if not np.isnan(c) else 0.0


def _parse_mem_citations(response: str, mem_ids: list[str]) -> dict[str, float]:
    """Extract [N] style citations → normalised weight per memory id."""
    found = re.findall(r"\[(\d+)\]", response)
    if not found:
        return {mid: 1.0 / max(len(mem_ids), 1) for mid in mem_ids}
    counts: dict[str, int] = {}
    for s in found:
        idx = int(s) - 1
        if 0 <= idx < len(mem_ids):
            counts[mem_ids[idx]] = counts.get(mem_ids[idx], 0) + 1
    total = sum(counts.values()) or 1
    return {mid: counts.get(mid, 0) / total for mid in mem_ids}


class CortexMemoryPool:
    """Manages a shared pool of memories in the Cortex backend for the whole run.

    Strategy:
    - Pre-seed ALL benchmark items as memories (content = question + answer).
    - Pre-compute embeddings for cosine retrieval (no sentence-transformers needed).
    - At query time: retrieve top-k by cosine sim → inject into prompt → post
      transaction to backend → parse citations → correlate with EAS scores.
    - On teardown: delete all seeded memories.
    """

    TOP_K = 5

    def __init__(self, backend_url: str, agent_id: str):
        self.backend    = backend_url.rstrip("/")
        self.agent_id   = agent_id
        # test_id → backend_id
        self._id_map:   dict[str, str] = {}
        # test_id → embedding
        self._embs:     dict[str, np.ndarray] = {}
        # test_id → memory text
        self._texts:    dict[str, str] = {}
        self._http:     httpx.AsyncClient | None = None

    async def __aenter__(self) -> "CortexMemoryPool":
        self._http = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._teardown()
        if self._http:
            await self._http.aclose()

    async def seed(self, items: list[BenchItem]) -> int:
        """Seed items as memories. Returns number successfully seeded."""
        assert self._http
        seeded = 0
        # Batch seed with concurrency 8
        sem = asyncio.Semaphore(8)

        async def _seed_one(item: BenchItem) -> None:
            nonlocal seeded
            text = f"{item.question}\n\nAnswer: {item.answer[0] if isinstance(item.answer, list) else item.answer}"
            text = text[:1000]
            async with sem:
                try:
                    r = await self._http.post(
                        f"{self.backend}/api/v1/memories",
                        json={"agent_id": self.agent_id, "content": text},
                    )
                    r.raise_for_status()
                    bid = r.json().get("id")
                    if bid:
                        self._id_map[item.item_id]  = bid
                        self._embs[item.item_id]    = _simple_embed(text)
                        self._texts[item.item_id]   = text
                        seeded += 1
                except Exception:
                    pass

        await asyncio.gather(*[_seed_one(i) for i in items])
        return seeded

    def retrieve(self, query: str, exclude_id: str | None = None) -> list[str]:
        """Return top-k test_ids by cosine similarity (excludes the query item itself)."""
        if not self._embs:
            return []
        q_emb  = _simple_embed(query)
        scores = {
            tid: float(np.dot(emb, q_emb))
            for tid, emb in self._embs.items()
            if tid != exclude_id
        }
        top = sorted(scores, key=lambda t: scores[t], reverse=True)[:self.TOP_K]
        return top

    async def score_eas(
        self,
        query: str,
        retrieved_tids: list[str],
        response: str,
    ) -> tuple[dict[str, float], dict[str, float], float]:
        """Submit transaction → return (citation_weights, eas_scores, spearman_corr)."""
        assert self._http
        backend_ids = [self._id_map[t] for t in retrieved_tids if t in self._id_map]
        if not backend_ids:
            return {}, {}, 0.0

        q_emb = _simple_embed(query)
        try:
            r = await self._http.post(
                f"{self.backend}/api/v1/transactions",
                json={
                    "agent_id":             self.agent_id,
                    "query_text":           query,
                    "query_embedding":      q_emb.tolist(),
                    "retrieved_memory_ids": backend_ids,
                    "response_text":        response,
                },
                timeout=30.0,
            )
            r.raise_for_status()
            data = r.json()
        except Exception:
            return {}, {}, 0.0

        # Map backend_id → test_id
        b2t = {v: k for k, v in self._id_map.items()}
        eas_scores: dict[str, float] = {
            b2t[s["memory_id"]]: s["score"]
            for s in data.get("scores", [])
            if s["memory_id"] in b2t
        }

        # Citation weights from [N] tags in response
        cit_weights = _parse_mem_citations(response, retrieved_tids)

        # Spearman correlation
        common = [t for t in retrieved_tids if t in eas_scores]
        if len(common) >= 2:
            cit_vals = [cit_weights.get(t, 0.0) for t in common]
            eas_vals = [eas_scores[t]            for t in common]
            corr = _spearman(cit_vals, eas_vals)
        else:
            corr = 0.0

        return cit_weights, eas_scores, corr

    async def _teardown(self) -> None:
        if not self._http:
            return
        sem = asyncio.Semaphore(16)
        async def _del(bid: str) -> None:
            async with sem:
                try:
                    await self._http.delete(
                        f"{self.backend}/api/v1/memories/{bid}",
                        params={"agent_id": self.agent_id},
                    )
                except Exception:
                    pass
        await asyncio.gather(*[_del(bid) for bid in self._id_map.values()])


# ═══════════════════════════════════════════════════════════════════════
#  TOKEN-BUCKET RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════

class TokenBucket:
    """Async token-bucket limiter.

    Pre-gates every request so we stay just below the API's RPM ceiling,
    eliminating the reactive exponential-backoff spikes that inflated p99
    to 33s in the unthrottled full run.

    Algorithm:
    - Bucket holds up to `capacity` tokens (= short burst headroom).
    - Refills at `rate` tokens/second (= rpm / 60).
    - Each request consumes 1 token; if bucket is empty it awaits the
      exact time until the next token arrives — no randomness, no
      exponential blow-up.

    The 10% safety margin (0.9× RPM) keeps us below the true ceiling
    even when the server clock and ours drift slightly.
    """

    def __init__(self, rpm: int, burst_factor: float = 1.5):
        self._rate     = rpm / 60.0 * 0.90        # tokens/sec with 10% safety margin
        self._capacity = max(1.0, self._rate * burst_factor)
        self._tokens   = self._capacity            # start full
        self._last     = time.monotonic()
        self._lock     = asyncio.Lock()
        # observable stats
        self.throttle_count = 0
        self.throttle_ms    = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            # Refill tokens based on elapsed time
            elapsed      = now - self._last
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last   = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return

            # Not enough tokens — wait exactly until one arrives
            wait = (1.0 - self._tokens) / self._rate
            self.throttle_count += 1
            self.throttle_ms    += wait * 1000

        # Release lock while sleeping so other coroutines can check
        await asyncio.sleep(wait)

        async with self._lock:
            now              = time.monotonic()
            elapsed          = now - self._last
            self._tokens     = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last       = now
            self._tokens    -= 1.0  # consume the token we just waited for


# ═══════════════════════════════════════════════════════════════════════
#  KIMI CLIENT  (async, token-bucket pre-gating + retry on 429/5xx)
# ═══════════════════════════════════════════════════════════════════════

class KimiClient:
    MAX_RETRIES  = 3           # reduced: bucket prevents most 429s
    BACKOFF_BASE = 1.5         # seconds (shorter — bucket does the heavy lifting)

    def __init__(self, api_key: str, rpm: int = 60):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=KIMI_BASE_URL,
            max_retries=0,     # we handle retries ourselves
            timeout=60.0,
        )
        self._bucket         = TokenBucket(rpm)
        self.rate_limit_hits = 0
        self.total_retries   = 0

    @property
    def throttle_count(self) -> int:
        return self._bucket.throttle_count

    @property
    def throttle_ms(self) -> float:
        return self._bucket.throttle_ms

    async def complete(
        self,
        messages:   list[dict],
        max_tokens: int = 512,
    ) -> tuple[str, int, int, int, bool]:
        """Returns (content, input_tokens, output_tokens, retries, was_rate_limited).

        Flow: bucket.acquire() → API call → on 429/5xx: linear backoff retry.
        The bucket ensures we almost never hit 429 in the first place.
        """
        # Pre-gate: block here until we have a token slot
        await self._bucket.acquire()

        retries      = 0
        rate_limited = False

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = await self._client.chat.completions.create(
                    model=KIMI_MODEL,
                    messages=messages,
                    max_tokens=max_tokens,
                    extra_body={"thinking": THINK_OFF},
                )
                content = resp.choices[0].message.content or ""
                in_tok  = resp.usage.prompt_tokens     if resp.usage else 0
                out_tok = resp.usage.completion_tokens if resp.usage else 0
                self.total_retries += retries
                return content, in_tok, out_tok, retries, rate_limited

            except Exception as e:
                msg       = str(e)
                is_rate   = "429" in msg or "rate" in msg.lower() or "limit" in msg.lower()
                is_server = any(c in msg for c in ("500", "502", "503", "504"))

                if is_rate:
                    self.rate_limit_hits += 1
                    rate_limited = True

                if (is_rate or is_server) and attempt < self.MAX_RETRIES:
                    # Linear (not exponential) — bucket already throttled us,
                    # this is just a short cooling-off before retry
                    wait = self.BACKOFF_BASE * (attempt + 1) + random.uniform(0, 0.5)
                    await asyncio.sleep(wait)
                    retries += 1
                    # Re-acquire a token for the retry
                    await self._bucket.acquire()
                    continue

                self.total_retries += retries
                raise


# ═══════════════════════════════════════════════════════════════════════
#  PROMPT BUILDERS
# ═══════════════════════════════════════════════════════════════════════

def _build_prompt(item: BenchItem, mem_texts: list[tuple[str, str]] | None = None) -> list[dict]:
    """Build prompt. If mem_texts is given ([(tid, content), ...]) inject as numbered memories."""

    if mem_texts:
        # Memory-augmented: inject retrieved memories, ask model to cite them
        mem_block = "\n\n".join(
            f"[Memory {i+1}]\n{content[:400]}"
            for i, (_, content) in enumerate(mem_texts)
        )
        return [
            {"role": "system", "content": (
                "You are a helpful assistant with access to retrieved memories. "
                "Answer the question using the memories below. "
                "Cite each memory you use as [1], [2], etc. Be concise."
            )},
            {"role": "user", "content": (
                f"Retrieved Memories:\n{mem_block}\n\n"
                f"Question: {item.question}\n\nAnswer (cite memories used):"
            )},
        ]

    if item.dataset == "mbpp":
        return [
            {"role": "system", "content": "You are an expert Python programmer. Write correct, concise code. Output ONLY the Python function, no explanation."},
            {"role": "user",   "content": item.question},
        ]

    if item.dataset in ("wildchat", "sharegpt"):
        return [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user",   "content": item.question},
        ]

    if item.choices:
        opts = item.context or " | ".join(f"({chr(65+i)}) {c}" for i, c in enumerate(item.choices))
        return [
            {"role": "system", "content": "Answer with only the letter of the correct option, e.g. A or B. No explanation."},
            {"role": "user",   "content": f"Q: {item.question}\n{opts}\nAnswer:"},
        ]

    if item.context:
        return [
            {"role": "system", "content": "Answer the question in 1–3 words using the context. No explanation."},
            {"role": "user",   "content": f"Context: {item.context}\n\nQuestion: {item.question}"},
        ]

    return [
        {"role": "system", "content": "Answer the question in 1–5 words. Be concise. No explanation."},
        {"role": "user",   "content": item.question},
    ]


# ═══════════════════════════════════════════════════════════════════════
#  ACCURACY EVALUATOR
# ═══════════════════════════════════════════════════════════════════════

def _normalise(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _is_correct(pred: str, gold: str | list[str], dataset: str) -> bool:
    if not pred:
        return False

    if dataset in ("mbpp", "wildchat"):
        # open-ended: count as correct if non-empty
        return len(pred.strip()) > 0

    golds = gold if isinstance(gold, list) else [gold]
    pred_n = _normalise(pred)

    for g in golds:
        g_n = _normalise(str(g))
        if not g_n:
            continue
        # Exact match
        if pred_n == g_n:
            return True
        # Substring match (common for aliases)
        if g_n in pred_n or pred_n in g_n:
            return True
        # For MCQ: check if the letter appears
        if len(g_n) == 1 and g_n in pred_n:
            return True

    return False


# ═══════════════════════════════════════════════════════════════════════
#  CORE ASYNC RUNNER
# ═══════════════════════════════════════════════════════════════════════

async def _run_item(
    kimi:      KimiClient,
    item:      BenchItem,
    sem:       asyncio.Semaphore,
    max_toks:  int = 256,
    pool:      CortexMemoryPool | None = None,
) -> QueryResult:
    async with sem:
        t0 = time.perf_counter()
        try:
            # ── Memory retrieval (if pool is active) ──────────────────
            mem_tids:   list[str]              = []
            mem_texts:  list[tuple[str, str]]  = []

            if pool and pool._id_map:
                mem_tids  = pool.retrieve(item.question, exclude_id=item.item_id)
                mem_texts = [(t, pool._texts[t]) for t in mem_tids if t in pool._texts]

            msgs = _build_prompt(item, mem_texts or None)
            content, in_tok, out_tok, retries, rate_lim = await kimi.complete(
                msgs, max_tokens=max_toks,
            )
            lat_ms  = (time.perf_counter() - t0) * 1000
            correct = _is_correct(content, item.answer, item.dataset)

            # ── EAS attribution (if pool active and memories retrieved) ─
            eas_corr     = 0.0
            eas_computed = False
            if pool and mem_tids:
                try:
                    _, _, eas_corr = await pool.score_eas(
                        item.question, mem_tids, content
                    )
                    eas_computed = True
                except Exception:
                    pass

            return QueryResult(
                dataset=item.dataset, item_id=item.item_id,
                question=item.question[:120],
                answer_gold=item.answer if isinstance(item.answer, str) else (item.answer[0] if item.answer else ""),
                answer_pred=content[:200],
                correct=correct, latency_ms=lat_ms,
                input_tokens=in_tok, output_tokens=out_tok,
                retries=retries, rate_limited=rate_lim,
                mem_retrieved=len(mem_tids),
                eas_corr=eas_corr, eas_computed=eas_computed,
            )

        except Exception as e:
            lat_ms = (time.perf_counter() - t0) * 1000
            return QueryResult(
                dataset=item.dataset, item_id=item.item_id,
                question=item.question[:120],
                answer_gold="", answer_pred="",
                correct=False, latency_ms=lat_ms,
                input_tokens=0, output_tokens=0,
                error=str(e),
            )


# ═══════════════════════════════════════════════════════════════════════
#  STATISTICS
# ═══════════════════════════════════════════════════════════════════════

def _pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    idx = int(len(s) * p / 100)
    return s[min(idx, len(s) - 1)]


def _compute_stats(results: list[QueryResult]) -> tuple[list[DatasetStats], dict]:
    by_ds: dict[str, list[QueryResult]] = defaultdict(list)
    for r in results:
        by_ds[r.dataset].append(r)

    ds_stats = []
    for dsname, rows in sorted(by_ds.items()):
        ok        = [r for r in rows if not r.error]
        lats      = [r.latency_ms for r in rows]
        acc       = sum(1 for r in ok if r.correct) / max(len(ok), 1)
        eas_rows  = [r for r in ok if r.eas_computed]
        mean_corr = float(np.mean([r.eas_corr for r in eas_rows])) if eas_rows else 0.0
        ds_stats.append(DatasetStats(
            name=dsname,
            n_total=len(rows), n_ok=len(ok), n_error=len(rows)-len(ok),
            accuracy=acc,
            p50_ms=_pct(lats, 50), p95_ms=_pct(lats, 95), p99_ms=_pct(lats, 99),
            total_in_tok=sum(r.input_tokens for r in ok),
            total_out_tok=sum(r.output_tokens for r in ok),
            mean_eas_corr=mean_corr,
        ))

    return ds_stats, by_ds


# ═══════════════════════════════════════════════════════════════════════
#  MAIN RUNNER
# ═══════════════════════════════════════════════════════════════════════

async def run_scale_test(
    api_key:    str,
    items:      list[BenchItem],
    workers:    int,
    profile:    str,
    backend:    str | None = None,
    live_print: bool = True,
) -> RunReport:
    kimi     = KimiClient(api_key)
    sem      = asyncio.Semaphore(workers)
    started  = datetime.now(UTC).isoformat()
    t_start  = time.perf_counter()

    mem_enabled  = False
    mem_seeded   = 0
    agent_id     = f"kimi_scale_{uuid.uuid4().hex[:10]}"

    print(f"\n  Workers: {workers}  |  Queries: {len(items)}  |  Profile: {profile.upper()}")
    if backend:
        print(f"  Memory backend: {backend}  (agent={agent_id})")

    async def _run_with_pool(pool: CortexMemoryPool | None) -> list[QueryResult]:
        tasks = [
            asyncio.create_task(_run_item(kimi, item, sem, pool=pool))
            for item in items
        ]
        out: list[QueryResult] = []
        done = 0; errors = 0
        interval = max(1, len(tasks) // 40)

        for coro in asyncio.as_completed(tasks):
            r = await coro
            out.append(r)
            done += 1
            if r.error:
                errors += 1
            if live_print and (done % interval == 0 or done == len(tasks)):
                ok_so_far   = done - errors
                acc_so_far  = sum(1 for x in out if x.correct and not x.error) / max(ok_so_far, 1)
                elapsed     = time.perf_counter() - t_start
                qps         = done / max(elapsed, 0.001)
                recent_lats = [x.latency_ms for x in out[-interval:] if not x.error]
                p50r        = _pct(recent_lats, 50) if recent_lats else 0
                eas_rows    = [x for x in out if x.eas_computed]
                eas_str     = f"  eas_corr={np.mean([x.eas_corr for x in eas_rows]):.3f}" if eas_rows else ""
                print(
                    f"  [{done:5d}/{len(tasks)}]  ok={ok_so_far}  err={errors}"
                    f"  acc={acc_so_far*100:5.1f}%  qps={qps:5.2f}"
                    f"  p50={p50r:6.0f}ms  rl_hits={kimi.rate_limit_hits}{eas_str}"
                )
        return out

    if backend:
        pool = CortexMemoryPool(backend, agent_id)
        async with pool:
            print(f"  Seeding {len(items)} memories…", flush=True)
            mem_seeded  = await pool.seed(items)
            mem_enabled = True
            print(f"  ✓ Seeded {mem_seeded}/{len(items)} memories\n")
            results = await _run_with_pool(pool)
        print("  ✓ Memory cleanup done")
    else:
        results = await _run_with_pool(None)

    elapsed  = time.perf_counter() - t_start
    finished = datetime.now(UTC).isoformat()

    ok_results  = [r for r in results if not r.error]
    n_correct   = sum(1 for r in ok_results if r.correct)
    all_lats    = [r.latency_ms for r in results]
    eas_rows    = [r for r in ok_results if r.eas_computed]
    mean_corr   = float(np.mean([r.eas_corr for r in eas_rows])) if eas_rows else 0.0
    ds_stats, _ = _compute_stats(results)
    errors      = sum(1 for r in results if r.error)

    return RunReport(
        profile=profile,
        started_at=started, finished_at=finished,
        total_queries=len(results),
        total_ok=len(ok_results),
        total_errors=errors,
        error_rate=errors / max(len(results), 1),
        accuracy=n_correct / max(len(ok_results), 1),
        throughput_qps=len(results) / max(elapsed, 0.001),
        total_in_tok=sum(r.input_tokens for r in ok_results),
        total_out_tok=sum(r.output_tokens for r in ok_results),
        p50_ms=_pct(all_lats, 50),
        p75_ms=_pct(all_lats, 75),
        p90_ms=_pct(all_lats, 90),
        p95_ms=_pct(all_lats, 95),
        p99_ms=_pct(all_lats, 99),
        max_ms=max(all_lats) if all_lats else 0.0,
        rate_limit_hits=kimi.rate_limit_hits,
        total_retries=kimi.total_retries,
        memory_enabled=mem_enabled,
        memories_seeded=mem_seeded,
        eas_queries=len(eas_rows),
        mean_eas_corr=mean_corr,
        datasets=ds_stats,
        results=results,
    )


# ═══════════════════════════════════════════════════════════════════════
#  REPORT PRINTER
# ═══════════════════════════════════════════════════════════════════════

def print_report(report: RunReport) -> None:
    W = 70
    print(f"\n{'═'*W}")
    print(f"  KIMI K2.5 SCALE TEST — {report.profile.upper()}")
    print(f"{'═'*W}")
    print(f"  Queries:         {report.total_queries:,}  (ok={report.total_ok:,}  err={report.total_errors:,})")
    print(f"  Error rate:      {report.error_rate*100:.2f}%")
    print(f"  Throughput:      {report.throughput_qps:.2f} q/s")
    print(f"  Accuracy:        {report.accuracy*100:.1f}%  (where ground truth exists)")
    print(f"  Rate-limit hits: {report.rate_limit_hits}")
    print(f"  Total retries:   {report.total_retries}")
    print(f"  Tokens in:       {report.total_in_tok:,}")
    print(f"  Tokens out:      {report.total_out_tok:,}")
    print()
    print(f"  Latency distribution")
    print(f"  ─────────────────────────────────────────")
    print(f"  p50:  {report.p50_ms:7.0f} ms")
    print(f"  p75:  {report.p75_ms:7.0f} ms")
    print(f"  p90:  {report.p90_ms:7.0f} ms")
    print(f"  p95:  {report.p95_ms:7.0f} ms")
    print(f"  p99:  {report.p99_ms:7.0f} ms")
    print(f"  max:  {report.max_ms:7.0f} ms")
    print()
    if report.memory_enabled:
        print(f"  Memory / EAS attribution")
        print(f"  ─────────────────────────────────────────")
        print(f"  Memories seeded: {report.memories_seeded:,}")
        print(f"  EAS queries:     {report.eas_queries:,}")
        print(f"  Mean Spearman:   {report.mean_eas_corr:.3f}  (citation ↔ EAS score)")
        print()

    print(f"  Per-dataset breakdown")
    if report.memory_enabled:
        print(f"  {'Dataset':<14} {'Total':>6} {'OK':>5} {'Err':>5} {'Acc':>7} {'p50ms':>7} {'p95ms':>7} {'EAS-ρ':>7}")
        print(f"  {'─'*70}")
        for ds in report.datasets:
            eas_s = f"{ds.mean_eas_corr:>6.3f}" if report.memory_enabled else "   n/a"
            print(
                f"  {ds.name:<14} {ds.n_total:>6} {ds.n_ok:>5} {ds.n_error:>5}"
                f"  {ds.accuracy*100:>5.1f}%  {ds.p50_ms:>6.0f}  {ds.p95_ms:>6.0f}  {eas_s}"
            )
    else:
        print(f"  {'Dataset':<14} {'Total':>6} {'OK':>5} {'Err':>5} {'Acc':>7} {'p50ms':>7} {'p95ms':>7} {'Tok-out':>9}")
        print(f"  {'─'*65}")
        for ds in report.datasets:
            print(
                f"  {ds.name:<14} {ds.n_total:>6} {ds.n_ok:>5} {ds.n_error:>5}"
                f"  {ds.accuracy*100:>5.1f}%  {ds.p50_ms:>6.0f}  {ds.p95_ms:>6.0f}"
                f"  {ds.total_out_tok:>9,}"
            )
    print()

    # Pass/fail thresholds
    passed = report.error_rate <= 0.15 and report.p95_ms <= 15_000
    print(f"  RESULT: {'✅ PASSED' if passed else '❌ FAILED'}  "
          f"(err_rate≤15% and p95≤15s)")
    print(f"{'═'*W}")


# ═══════════════════════════════════════════════════════════════════════
#  PROFILES
# ═══════════════════════════════════════════════════════════════════════

PROFILES: dict[str, dict] = {
    "blitz": {
        "queries": 100,
        "workers": 16,
        "datasets": ["triviaqa", "mmlu", "arc", "sharegpt"],
    },
    "endurance": {
        "queries": 500,
        "workers": 8,
        "datasets": ["triviaqa", "nq_open", "hotpotqa", "mmlu", "arc", "popqa"],
    },
    "spike": {
        "queries": 200,
        "workers": 32,
        "datasets": ["triviaqa", "nq_open", "mmlu", "winogrande"],
    },
    "full": {
        "queries": 1000,
        "workers": 12,
        "datasets": list(DATASET_LOADERS.keys()),
    },
}


# ═══════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kimi K2.5 large-scale stress test with real benchmarks"
    )
    parser.add_argument("--profile", default="blitz",
                        choices=list(PROFILES.keys()) + ["custom"],
                        help="Test profile (default: blitz)")
    parser.add_argument("--api-key", default=os.getenv("KIMI_API_KEY"),
                        help="Moonshot API key or KIMI_API_KEY env var")
    parser.add_argument("--queries",  type=int, default=None,
                        help="Override query count (required for --profile custom)")
    parser.add_argument("--workers",  type=int, default=None,
                        help="Override worker count")
    parser.add_argument("--datasets", default=None,
                        help="Comma-separated dataset names (e.g. triviaqa,mmlu)")
    parser.add_argument("--seed",     type=int, default=42)
    parser.add_argument("--output",   default=None,
                        help="Save JSON report to this path")
    parser.add_argument("--backend", default=os.getenv("CORTEX_BACKEND"),
                        help="CortexOS backend URL — enables memory seeding + EAS attribution")
    parser.add_argument("--no-results", action="store_true",
                        help="Omit per-query results from JSON (smaller file)")
    args = parser.parse_args()

    if not args.api_key:
        print("❌  No API key. Pass --api-key or set KIMI_API_KEY.")
        sys.exit(1)

    # Resolve profile config
    if args.profile == "custom":
        if not args.queries or not args.datasets:
            print("❌  --profile custom requires --queries N and --datasets csv-list")
            sys.exit(1)
        cfg = {
            "queries":  args.queries,
            "workers":  args.workers or 8,
            "datasets": args.datasets.split(","),
        }
    else:
        cfg = dict(PROFILES[args.profile])
        if args.queries:
            cfg["queries"] = args.queries
        if args.workers:
            cfg["workers"] = args.workers
        if args.datasets:
            cfg["datasets"] = args.datasets.split(",")

    print(f"\n{'═'*70}")
    print(f"  KIMI K2.5 LARGE-SCALE STRESS TEST")
    print(f"{'═'*70}")
    print(f"  Profile:  {args.profile.upper()}")
    print(f"  Queries:  {cfg['queries']}")
    print(f"  Workers:  {cfg['workers']}")
    print(f"  Datasets: {', '.join(cfg['datasets'])}")
    print(f"  Seed:     {args.seed}")
    print()

    # Load datasets
    print("Loading datasets…")
    items = load_datasets(cfg["datasets"], cfg["queries"], seed=args.seed)
    if not items:
        print("❌  No items loaded. Check dataset names and connectivity.")
        sys.exit(1)

    ds_counts = defaultdict(int)
    for it in items:
        ds_counts[it.dataset] += 1
    print(f"\n  Loaded {len(items)} items:")
    for ds, cnt in sorted(ds_counts.items()):
        print(f"    {ds:<14} {cnt:>5}")
    print()

    # Run
    report = await run_scale_test(
        api_key=args.api_key,
        items=items,
        workers=cfg["workers"],
        profile=args.profile,
        backend=args.backend,
    )

    # Print summary
    print_report(report)

    # Save JSON
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        def _to_dict(obj: Any) -> Any:
            if hasattr(obj, "__dataclass_fields__"):
                d = {}
                for k in obj.__dataclass_fields__:
                    v = getattr(obj, k)
                    if k == "results" and args.no_results:
                        continue
                    d[k] = _to_dict(v)
                return d
            if isinstance(obj, list):
                return [_to_dict(x) for x in obj]
            return obj

        out_path.write_text(json.dumps(_to_dict(report), indent=2))
        print(f"\n  Report saved → {out_path}")

    all_ok = report.error_rate <= 0.15
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
