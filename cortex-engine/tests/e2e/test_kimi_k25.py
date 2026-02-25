#!/usr/bin/env python3
"""
CortexOS x Kimi K2.5 — End-to-End Scaled Testing
==================================================

Full attribution pipeline validated against Kimi K2.5 (Moonshot AI).
Kimi API is OpenAI-compatible; base_url = https://api.moonshot.ai/v1

Test tiers
----------
1. SMOKE      – quick sanity (3 queries, no concurrency)
2. STANDARD   – 10 queries, citation correlation, think-mode disabled
3. THINK      – 10 queries, thinking mode enabled
4. VISION     – image understanding + attribution
5. TOOL_CALL  – tool-use flow (thinking + tool constraints)
6. CONCURRENT – 20 parallel queries (scaled throughput)
7. STRESS     – 50 queries, 8 workers, latency percentiles, error rate

Usage
-----
# Quick smoke test (no backend needed)
python tests/e2e/test_kimi_k25.py --tier smoke --api-key sk-...

# Full scaled run against live backend
python tests/e2e/test_kimi_k25.py \\
    --tier stress \\
    --api-key sk-... \\
    --backend http://localhost:8001 \\
    --workers 8 \\
    --queries 50

Environment variables (alternative to flags)
--------------------------------------------
KIMI_API_KEY      Moonshot API key
CORTEX_BACKEND    CortexOS backend URL
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import numpy as np

# ── path fixup ──────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_ROOT))

from tests.e2e.agent_simulator import simple_embed  # type: ignore
from tests.e2e.datasets import generate_personal_assistant_dataset  # type: ignore

# ── Constants ───────────────────────────────────────────────────────────

KIMI_BASE_URL = "https://api.moonshot.ai/v1"
KIMI_MODEL    = "kimi-k2.5"

THINK_ON  = {"type": "enabled"}
THINK_OFF = {"type": "disabled"}

# Tool-use constraints: when thinking is enabled, tool_choice must be "auto"/"none"
TOOL_CHOICE_THINK = "auto"

# ── Data structures ─────────────────────────────────────────────────────

@dataclass
class QueryResult:
    query:            str
    response:         str
    citation_weights: dict[str, float]
    eas_scores:       dict[str, float]
    latency_ms:       float
    thinking_tokens:  int = 0
    output_tokens:    int = 0
    error:            str | None = None


@dataclass
class TierReport:
    tier:             str
    queries_run:      int
    queries_ok:       int
    mean_correlation: float
    p50_ms:           float
    p95_ms:           float
    p99_ms:           float
    error_rate:       float
    passed:           bool
    details:          list[QueryResult] = field(default_factory=list)


# ── Kimi K2.5 client ─────────────────────────────────────────────────────

class KimiClient:
    """Thin OpenAI-compatible client for Kimi K2.5 with citation tracking."""

    def __init__(self, api_key: str):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=KIMI_BASE_URL,
        )

    async def chat(
        self,
        messages: list[dict],
        *,
        thinking: dict = THINK_OFF,
        max_tokens: int = 1024,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
    ) -> tuple[str, int, int]:
        """Send messages and return (content, thinking_tokens, output_tokens).

        Kimi K2.5 constraints enforced here:
        - temperature / top_p / n / penalties must use defaults
        - when thinking enabled + tools: tool_choice must be "auto"/"none"
        """
        kwargs: dict[str, Any] = {
            "model":      KIMI_MODEL,
            "messages":   messages,
            "max_tokens": max_tokens,
            "extra_body": {"thinking": thinking},
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or TOOL_CHOICE_THINK
        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            raise RuntimeError(f"Kimi API error: {e}") from e

        choice     = resp.choices[0]
        content    = choice.message.content or ""
        out_tokens = resp.usage.completion_tokens if resp.usage else 0
        # thinking tokens live in usage.completion_tokens_details (if present)
        think_toks = 0
        if resp.usage and hasattr(resp.usage, "completion_tokens_details"):
            d = resp.usage.completion_tokens_details
            if d and hasattr(d, "reasoning_tokens"):
                think_toks = d.reasoning_tokens or 0
        return content, think_toks, out_tokens

    async def chat_with_image(
        self,
        text_prompt: str,
        image_b64: str,
        image_mime: str = "image/png",
        *,
        thinking: dict = THINK_OFF,
    ) -> tuple[str, int, int]:
        """Vision call with a base64-encoded image."""
        messages = [
            {"role": "system", "content": "You are Kimi."},
            {
                "role": "user",
                "content": [
                    {
                        "type":      "image_url",
                        "image_url": {"url": f"data:{image_mime};base64,{image_b64}"},
                    },
                    {"type": "text", "text": text_prompt},
                ],
            },
        ]
        return await self.chat(messages, thinking=thinking)


# ── Citation parser ──────────────────────────────────────────────────────

def _parse_citations(
    response: str,
    memories: list[tuple[str, str]],  # (id, content)
) -> dict[str, float]:
    """Extract [N] citations → normalised weights per memory id."""
    found = re.findall(r"\[(\d+)\]", response)
    if not found:
        return {mid: 1.0 / max(len(memories), 1) for mid, _ in memories}

    counts: dict[str, int] = {}
    for s in found:
        idx = int(s) - 1
        if 0 <= idx < len(memories):
            mid = memories[idx][0]
            counts[mid] = counts.get(mid, 0) + 1

    total = sum(counts.values())
    return {mid: counts.get(mid, 0) / total for mid, _ in memories}


# ── Memory prompt builder ────────────────────────────────────────────────

def _build_memory_prompt(query: str, memories: list[tuple[str, str]]) -> list[dict]:
    mem_text = "\n\n".join(
        f"[Memory {i+1}] (ID: {mid})\n{content}"
        for i, (mid, content) in enumerate(memories)
    )
    return [
        {"role": "system", "content": "You are a helpful assistant. Answer using ONLY the retrieved memories below. Cite each memory you use as [1], [2], etc."},
        {"role": "user",   "content": f"Retrieved Memories:\n{mem_text}\n\nQuestion: {query}\n\nAnswer (cite memories used):"},
    ]


# ── CortexOS backend helpers ─────────────────────────────────────────────

async def _seed_memories(
    client: httpx.AsyncClient,
    backend: str,
    agent_id: str,
    memory_ids: list[str],
    memory_texts: list[str],
) -> dict[str, str]:
    """Seed memories → return {test_id: backend_id}."""
    mapping: dict[str, str] = {}
    for tid, content in zip(memory_ids, memory_texts):
        try:
            r = await client.post(
                f"{backend}/api/v1/memories",
                json={"agent_id": agent_id, "content": content},
                timeout=10.0,
            )
            r.raise_for_status()
            bid = r.json().get("id")
            if bid:
                mapping[tid] = bid
        except Exception as e:
            print(f"    [seed] Warning: {e}")
    return mapping


async def _get_eas_scores(
    client: httpx.AsyncClient,
    backend: str,
    agent_id: str,
    query: str,
    query_emb: np.ndarray,
    backend_ids: list[str],
    response: str,
    backend_to_test: dict[str, str],
) -> dict[str, float]:
    """Submit a transaction and return {test_id: eas_score}."""
    try:
        r = await client.post(
            f"{backend}/api/v1/transactions",
            json={
                "agent_id":             agent_id,
                "query_text":           query,
                "query_embedding":      query_emb.tolist(),
                "retrieved_memory_ids": backend_ids,
                "response_text":        response,
            },
            timeout=30.0,
        )
        r.raise_for_status()
        data = r.json()
        return {
            backend_to_test.get(s["memory_id"], s["memory_id"]): s["score"]
            for s in data.get("scores", [])
        }
    except Exception as e:
        print(f"    [eas] Warning: {e}")
        return {}


async def _cleanup(
    client: httpx.AsyncClient,
    backend: str,
    agent_id: str,
    backend_ids: list[str],
) -> None:
    for bid in backend_ids:
        try:
            await client.delete(
                f"{backend}/api/v1/memories/{bid}",
                params={"agent_id": agent_id},
                timeout=5.0,
            )
        except Exception:
            pass


# ── Core query runner ────────────────────────────────────────────────────

async def _run_query(
    *,
    kimi:           KimiClient,
    query:          str,
    memories:       list[tuple[str, str]],   # (test_id, content)
    memory_embs:    np.ndarray,
    backend:        str | None,
    http:           httpx.AsyncClient | None,
    agent_id:       str,
    id_map:         dict[str, str],          # test_id → backend_id
    thinking:       dict,
    semaphore:      asyncio.Semaphore,
) -> QueryResult:
    async with semaphore:
        t0 = time.perf_counter()
        try:
            # Retrieve top-5 by cosine similarity
            q_emb    = simple_embed(query)
            sims     = memory_embs @ q_emb
            top_idx  = np.argsort(sims)[-5:][::-1]
            top_mems = [memories[i] for i in top_idx]

            msgs     = _build_memory_prompt(query, top_mems)
            response, think_toks, out_toks = await kimi.chat(msgs, thinking=thinking)

            latency  = (time.perf_counter() - t0) * 1000
            cit_wts  = _parse_citations(response, top_mems)

            eas: dict[str, float] = {}
            if backend and http and id_map:
                b2t      = {v: k for k, v in id_map.items()}
                b_ids    = [id_map[mid] for mid, _ in top_mems if mid in id_map]
                eas      = await _get_eas_scores(
                    http, backend, agent_id, query, q_emb,
                    b_ids, response, b2t,
                )

            return QueryResult(
                query=query, response=response,
                citation_weights=cit_wts, eas_scores=eas,
                latency_ms=latency, thinking_tokens=think_toks,
                output_tokens=out_toks,
            )
        except Exception as e:
            latency = (time.perf_counter() - t0) * 1000
            return QueryResult(
                query=query, response="", citation_weights={},
                eas_scores={}, latency_ms=latency, error=str(e),
            )


# ── Correlation helper ───────────────────────────────────────────────────

def _spearman(a: list[float], b: list[float]) -> float:
    from scipy import stats  # optional; fall back to numpy rank
    try:
        c, _ = stats.spearmanr(a, b)
        return float(c) if not np.isnan(c) else 0.0
    except ImportError:
        # manual rank correlation
        def _rank(x: list[float]) -> list[float]:
            order = np.argsort(x)
            ranks = np.empty(len(x))
            ranks[order] = np.arange(1, len(x) + 1)
            return list(ranks)
        ra, rb = _rank(a), _rank(b)
        n = len(ra)
        if n < 2:
            return 0.0
        d2 = sum((x - y) ** 2 for x, y in zip(ra, rb))
        return 1 - 6 * d2 / (n * (n ** 2 - 1))


def _compute_correlations(results: list[QueryResult]) -> list[float]:
    corrs = []
    for r in results:
        if r.error:
            continue
        common = set(r.citation_weights) & set(r.eas_scores)
        if len(common) < 2:
            continue
        cit = [r.citation_weights[m] for m in common]
        eas = [r.eas_scores[m]       for m in common]
        c   = _spearman(cit, eas)
        corrs.append(c)
    return corrs


def _latency_percentiles(results: list[QueryResult]) -> tuple[float, float, float]:
    lats = sorted(r.latency_ms for r in results)
    if not lats:
        return 0.0, 0.0, 0.0
    def _pct(p: float) -> float:
        idx = int(len(lats) * p / 100)
        return lats[min(idx, len(lats) - 1)]
    return _pct(50), _pct(95), _pct(99)


# ── Tier runners ─────────────────────────────────────────────────────────

_STANDARD_QUERIES = [
    "What's my favorite programming language?",
    "Tell me about my pet",
    "What time do I usually wake up?",
    "Where do I work?",
    "What's my favorite food?",
    "Tell me about my exercise routine",
    "What music do I like?",
    "What are my hobbies?",
    "What framework do I prefer for backend?",
    "What database do I usually use?",
    "How do I prefer to take notes?",
    "Tell me about my morning routine",
    "What's my commute like?",
    "Who are my closest colleagues?",
    "What side projects am I working on?",
    "What is my preferred code editor?",
    "How do I manage my calendar?",
    "What's my preferred meeting format?",
    "What languages do I speak?",
    "What's my sleeping schedule?",
    "Tell me about my goals for this year",
    "What podcasts do I enjoy?",
    "How do I prefer to communicate?",
    "What's my favourite cloud provider?",
    "How do I approach code reviews?",
    "What sports do I follow?",
    "What's my go-to productivity tool?",
    "Describe my home setup for work",
    "What kind of team culture do I thrive in?",
    "What tech conferences do I attend?",
    "What project management method do I use?",
    "How do I decompress after work?",
    "What's my reading list like?",
    "How do I prefer to onboard new tools?",
    "What's my backup strategy?",
    "How do I structure my workday?",
    "What security practices do I follow?",
    "Tell me about my network setup at home",
    "What testing frameworks do I prefer?",
    "What CI/CD tools do I use?",
    "What version control workflow do I follow?",
    "How do I handle technical debt?",
    "What's my approach to documentation?",
    "How do I keep up with new technology?",
    "What is my favourite open-source project?",
    "How do I handle disagreements in code reviews?",
    "What's my mentorship philosophy?",
    "How do I track bugs in my projects?",
    "What's my stance on remote work?",
    "How do I celebrate project launches?",
]


async def _run_tier(
    *,
    tier:       str,
    kimi:       KimiClient,
    queries:    list[str],
    thinking:   dict,
    workers:    int,
    backend:    str | None,
    pass_corr:  float = 0.30,
    pass_err:   float = 0.10,
) -> TierReport:
    print(f"\n{'='*65}")
    print(f"  TIER: {tier.upper()} | queries={len(queries)} workers={workers} think={thinking['type']}")
    print(f"{'='*65}")

    # Load dataset
    dataset       = generate_personal_assistant_dataset()
    mem_texts     = [m.content for m in dataset.memories]
    mem_ids       = [m.id      for m in dataset.memories]
    mem_embs      = np.array([simple_embed(t) for t in mem_texts])
    memories_list = list(zip(mem_ids, mem_texts))

    agent_id = f"kimi_test_{uuid.uuid4().hex[:8]}"
    id_map:  dict[str, str] = {}

    http_ctx: httpx.AsyncClient | None = None
    if backend:
        http_ctx = httpx.AsyncClient(timeout=60.0)
        print(f"  Seeding {len(mem_ids)} memories to backend…")
        id_map = await _seed_memories(http_ctx, backend, agent_id, mem_ids, mem_texts)
        print(f"  ✓ Seeded {len(id_map)}")

    sem     = asyncio.Semaphore(workers)
    tasks   = [
        _run_query(
            kimi=kimi, query=q,
            memories=memories_list, memory_embs=mem_embs,
            backend=backend, http=http_ctx,
            agent_id=agent_id, id_map=id_map,
            thinking=thinking, semaphore=sem,
        )
        for q in queries
    ]

    results: list[QueryResult] = []
    done = 0
    for coro in asyncio.as_completed(tasks):
        r = await coro
        done += 1
        status = "ERR" if r.error else f"{r.latency_ms:6.0f}ms"
        print(f"  [{done:3d}/{len(tasks)}] {status}  {r.query[:55]}")
        if r.error:
            print(f"          ↳ {r.error}")
        results.append(r)

    # Cleanup
    if http_ctx:
        await _cleanup(http_ctx, backend, agent_id, list(id_map.values()))  # type: ignore[arg-type]
        await http_ctx.aclose()

    # Stats
    errors   = [r for r in results if r.error]
    ok       = [r for r in results if not r.error]
    corrs    = _compute_correlations(ok)
    mean_c   = float(np.mean(corrs)) if corrs else 0.0
    p50, p95, p99 = _latency_percentiles(results)
    err_rate = len(errors) / max(len(results), 1)
    passed   = (mean_c >= pass_corr or not backend) and err_rate <= pass_err

    print(f"\n  Results")
    print(f"  -------")
    print(f"  Queries OK:     {len(ok)}/{len(results)}")
    print(f"  Error rate:     {err_rate*100:.1f}%")
    print(f"  Latency p50:    {p50:.0f} ms")
    print(f"  Latency p95:    {p95:.0f} ms")
    print(f"  Latency p99:    {p99:.0f} ms")
    if corrs:
        print(f"  Corr computed:  {len(corrs)}/{len(ok)}")
        print(f"  Mean Spearman:  {mean_c:.3f}")
    if passed:
        print(f"  Status:         ✅ PASSED")
    else:
        print(f"  Status:         ❌ FAILED (corr={mean_c:.3f} err={err_rate:.2f})")

    return TierReport(
        tier=tier, queries_run=len(results), queries_ok=len(ok),
        mean_correlation=mean_c, p50_ms=p50, p95_ms=p95, p99_ms=p99,
        error_rate=err_rate, passed=passed, details=results,
    )


# ── Vision tier (standalone, no backend needed) ──────────────────────────

def _make_test_png_b64() -> str:
    """Generate a valid 64×64 PNG with a red square using only stdlib."""
    import struct, zlib

    def _chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    w, h = 64, 64
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # 8-bit RGB
    # Raw image: each scanline = filter_byte(0) + RGB pixels
    row = b"\x00" + b"\xFF\x00\x00" * w  # red row
    raw = row * h
    idat_data = zlib.compress(raw)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", idat_data)
        + _chunk(b"IEND", b"")
    )
    return base64.b64encode(png).decode()


async def _run_vision_tier(kimi: KimiClient) -> TierReport:
    """Send a synthetic 64×64 red PNG and verify a non-empty description."""
    print(f"\n{'='*65}")
    print(f"  TIER: VISION")
    print(f"{'='*65}")

    RED_64X64_PNG_B64 = _make_test_png_b64()

    results: list[QueryResult] = []
    prompts = [
        "Describe the colour and dimensions of this image.",
        "What is shown in this image? Be specific.",
    ]
    for p in prompts:
        t0 = time.perf_counter()
        try:
            txt, think_toks, out_toks = await kimi.chat_with_image(
                p, RED_64X64_PNG_B64, thinking=THINK_OFF,
            )
            lat = (time.perf_counter() - t0) * 1000
            print(f"  prompt: {p[:50]}")
            print(f"  answer: {txt[:120]}")
            print(f"  latency: {lat:.0f} ms")
            results.append(QueryResult(
                query=p, response=txt, citation_weights={},
                eas_scores={}, latency_ms=lat,
                thinking_tokens=think_toks, output_tokens=out_toks,
            ))
        except Exception as e:
            lat = (time.perf_counter() - t0) * 1000
            print(f"  ERR: {e}")
            results.append(QueryResult(
                query=p, response="", citation_weights={},
                eas_scores={}, latency_ms=lat, error=str(e),
            ))

    ok       = [r for r in results if not r.error and r.response]
    err_rate = 1 - len(ok) / max(len(results), 1)
    p50, p95, p99 = _latency_percentiles(results)
    passed   = err_rate == 0.0

    print(f"\n  Status: {'✅ PASSED' if passed else '❌ FAILED'}")
    return TierReport(
        tier="vision", queries_run=len(results), queries_ok=len(ok),
        mean_correlation=0.0, p50_ms=p50, p95_ms=p95, p99_ms=p99,
        error_rate=err_rate, passed=passed, details=results,
    )


# ── Tool-call tier ───────────────────────────────────────────────────────

async def _run_tool_tier(kimi: KimiClient) -> TierReport:
    """Test tool calling with thinking mode enabled."""
    print(f"\n{'='*65}")
    print(f"  TIER: TOOL_CALL (thinking=enabled, tool_choice=auto)")
    print(f"{'='*65}")

    tools = [
        {
            "type": "function",
            "function": {
                "name":        "get_weather",
                "description": "Get the current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"},
                        "unit":     {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location"],
                },
            },
        }
    ]

    queries = [
        "What's the weather like in Tokyo?",
        "Should I bring an umbrella in London today?",
        "Is it hot in Dubai right now?",
    ]

    results: list[QueryResult] = []
    for q in queries:
        t0 = time.perf_counter()
        try:
            msgs = [{"role": "user", "content": q}]
            txt, think_toks, out_toks = await kimi.chat(
                msgs, thinking=THINK_ON,
                tools=tools, tool_choice=TOOL_CHOICE_THINK,
            )
            lat = (time.perf_counter() - t0) * 1000
            print(f"  Q: {q}")
            print(f"  A: {txt[:120] if txt else '(tool_call triggered)'}")
            print(f"  latency: {lat:.0f} ms  think_tokens: {think_toks}")
            results.append(QueryResult(
                query=q, response=txt or "(tool_call)", citation_weights={},
                eas_scores={}, latency_ms=lat,
                thinking_tokens=think_toks, output_tokens=out_toks,
            ))
        except Exception as e:
            lat = (time.perf_counter() - t0) * 1000
            print(f"  ERR: {e}")
            results.append(QueryResult(
                query=q, response="", citation_weights={},
                eas_scores={}, latency_ms=lat, error=str(e),
            ))

    ok       = [r for r in results if not r.error]
    err_rate = 1 - len(ok) / max(len(results), 1)
    p50, p95, p99 = _latency_percentiles(results)
    passed   = err_rate <= 0.34   # allow 1 failure out of 3

    print(f"\n  Status: {'✅ PASSED' if passed else '❌ FAILED'}")
    return TierReport(
        tier="tool_call", queries_run=len(results), queries_ok=len(ok),
        mean_correlation=0.0, p50_ms=p50, p95_ms=p95, p99_ms=p99,
        error_rate=err_rate, passed=passed, details=results,
    )


# ── Summary printer ──────────────────────────────────────────────────────

def _print_summary(reports: list[TierReport]) -> None:
    print(f"\n{'='*65}")
    print(f"  FINAL SUMMARY")
    print(f"{'='*65}")
    print(f"  {'Tier':<14} {'Queries':>7} {'ErrRate':>8} {'p50ms':>7} {'p95ms':>7} {'Corr':>6}  Status")
    print(f"  {'-'*62}")
    all_ok = True
    for r in reports:
        status = "✅" if r.passed else "❌"
        if not r.passed:
            all_ok = False
        corr_s = f"{r.mean_correlation:.3f}" if r.mean_correlation else "  n/a"
        print(
            f"  {r.tier:<14} {r.queries_run:>7} {r.error_rate*100:>7.1f}%"
            f" {r.p50_ms:>7.0f} {r.p95_ms:>7.0f} {corr_s:>6}  {status}"
        )
    print(f"\n  Overall: {'✅ ALL PASSED' if all_ok else '❌ SOME FAILED'}")


# ── Entry point ──────────────────────────────────────────────────────────

async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Kimi K2.5 E2E scaled test for CortexOS")
    parser.add_argument("--tier",    default="standard",
                        choices=["smoke", "standard", "think", "vision",
                                 "tool_call", "concurrent", "stress", "all"])
    parser.add_argument("--api-key", default=os.getenv("KIMI_API_KEY"),
                        help="Moonshot API key (or KIMI_API_KEY env var)")
    parser.add_argument("--backend", default=os.getenv("CORTEX_BACKEND"),
                        help="CortexOS backend URL (optional)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Max concurrent requests (default: 4)")
    parser.add_argument("--queries", type=int, default=None,
                        help="Override number of queries")
    parser.add_argument("--output",  default=None,
                        help="Save JSON report to this file")
    args = parser.parse_args()

    if not args.api_key:
        print("❌  No API key. Set --api-key or KIMI_API_KEY env var.")
        sys.exit(1)

    kimi    = KimiClient(args.api_key)
    reports: list[TierReport] = []

    tier = args.tier

    if tier in ("smoke", "all"):
        n = args.queries or 3
        reports.append(await _run_tier(
            tier="smoke", kimi=kimi,
            queries=_STANDARD_QUERIES[:n],
            thinking=THINK_OFF, workers=1,
            backend=args.backend,
        ))

    if tier in ("standard", "all"):
        n = args.queries or 10
        reports.append(await _run_tier(
            tier="standard", kimi=kimi,
            queries=_STANDARD_QUERIES[:n],
            thinking=THINK_OFF, workers=min(args.workers, 4),
            backend=args.backend,
        ))

    if tier in ("think", "all"):
        n = args.queries or 10
        reports.append(await _run_tier(
            tier="think", kimi=kimi,
            queries=_STANDARD_QUERIES[:n],
            thinking=THINK_ON, workers=min(args.workers, 2),
            backend=args.backend,
        ))

    if tier in ("vision", "all"):
        reports.append(await _run_vision_tier(kimi))

    if tier in ("tool_call", "all"):
        reports.append(await _run_tool_tier(kimi))

    if tier in ("concurrent", "all"):
        n = args.queries or 20
        reports.append(await _run_tier(
            tier="concurrent", kimi=kimi,
            queries=_STANDARD_QUERIES[:n],
            thinking=THINK_OFF, workers=args.workers,
            backend=args.backend,
        ))

    if tier in ("stress", "all"):
        n = args.queries or 50
        reports.append(await _run_tier(
            tier="stress", kimi=kimi,
            queries=(_STANDARD_QUERIES * 3)[:n],
            thinking=THINK_OFF, workers=args.workers,
            backend=args.backend,
            pass_corr=0.25, pass_err=0.15,
        ))

    _print_summary(reports)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(json.dumps(
            [
                {
                    "tier":             r.tier,
                    "queries_run":      r.queries_run,
                    "queries_ok":       r.queries_ok,
                    "mean_correlation": r.mean_correlation,
                    "p50_ms":           r.p50_ms,
                    "p95_ms":           r.p95_ms,
                    "p99_ms":           r.p99_ms,
                    "error_rate":       r.error_rate,
                    "passed":           r.passed,
                }
                for r in reports
            ],
            indent=2,
        ))
        print(f"\n  Report saved to {out_path}")

    all_ok = all(r.passed for r in reports)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
