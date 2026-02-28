# CortexOS Python SDK

The official Python SDK for [Cortexa](https://cortexa.ink) — hallucination detection and verification for LLM agents.

## Quickstart

```bash
pip install cortexos
```

```python
import cortexos

cortexos.configure(api_key="your-key")

result = cortexos.check(
    response="The return window is 30 days",
    sources=["Return policy: 30-day window for all items."]
)
print(f"Hallucination Index: {result.hallucination_index}")
# → Hallucination Index: 0.0
```

Get an API key at [cortexa.ink](https://cortexa.ink)

## Installation

```bash
pip install cortexos
```

## Quick start

```python
from cortexos import Cortex

cx = Cortex(api_key="sk-...", agent_id="support-bot")

# Store a memory
mem = cx.remember(
    "User prefers email over Slack for all communications",
    importance=0.85,
    tags=["preferences", "communication"],
    metadata={"source": "conversation_123"},
)

# Semantic recall
results = cx.recall("how does the user want to be contacted?", top_k=5)
for r in results:
    print(f"[{r.score:.2f}] {r.memory.content}")

# EAS attribution — score which memories contributed to your LLM response
attr = cx.attribute(
    query="How should I contact the user?",
    response="Based on their preferences, contact them via email.",
    memory_ids=[mem.id],
)
print(attr.scores)  # {"mem_xxx": 0.91}

# Combined recall + attribution in one call
result = cx.recall_and_attribute(
    query="How should I reach the user?",
    response="Contact via email.",
    top_k=10,
)
```

## Async usage

```python
import asyncio
from cortexos import AsyncCortex

async def main():
    async with AsyncCortex(api_key="sk-...", agent_id="my-agent") as cx:
        mem = await cx.remember("User lives in Tokyo", importance=0.7)
        results = await cx.recall("where does the user live?")
        await cx.forget(mem.id)

asyncio.run(main())
```

## API reference

### `Cortex` / `AsyncCortex`

| Method | Description |
|--------|-------------|
| `remember(content, *, importance, tags, metadata, tier, ttl)` | Store a new memory |
| `get(memory_id)` | Fetch a memory by ID |
| `update(memory_id, *, importance, tags, metadata, tier)` | Update memory fields |
| `forget(memory_id)` | Soft-delete a memory |
| `list(*, limit, offset, tier, sort_by, order)` | Paginated memory listing |
| `recall(query, *, top_k, min_score, tags)` | Semantic search |
| `attribute(query, response, memory_ids)` | Run EAS attribution |
| `recall_and_attribute(query, response, *, top_k, min_score)` | Recall + attribute |

### Types

- **`Memory`** — `id`, `content`, `agent_id`, `tier`, `importance`, `tags`, `metadata`, `retrieval_count`, `created_at`
- **`RecallResult`** — `memory: Memory`, `score: float`
- **`Attribution`** — `transaction_id`, `query`, `response`, `scores: dict[str, float]`
- **`RecallAndAttributeResult`** — `memories: list[RecallResult]`, `attribution: Attribution`
- **`Page`** — `items: list[Memory]`, `total`, `offset`, `limit`, `has_more`

### Errors

| Exception | When |
|-----------|------|
| `CortexError` | Base class for all SDK errors |
| `AuthError` | Invalid or missing API key (401/403) |
| `RateLimitError` | Too many requests (429); has `.retry_after` |
| `MemoryNotFoundError` | Memory ID does not exist (404) |
| `ValidationError` | Invalid request payload (422) |
| `ServerError` | Unexpected 5xx from the server |

## Configuration

```python
cx = Cortex(
    agent_id="my-agent",
    api_key="sk-...",           # Optional if server has no auth
    base_url="https://api.cortexa.ink",
    timeout=30.0,               # Per-request timeout (seconds)
    max_retries=3,              # Retries on 429/502/503/504
)
```

## Running tests

```bash
# Unit tests (no server required)
pip install "cortexos[dev]"
pytest tests/test_client.py -v

# Integration tests (requires a running cortex-engine)
pytest tests/test_integration.py -v
```
