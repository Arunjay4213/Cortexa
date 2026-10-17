# CortexOS Python SDK

**v0.3.0** — The official Python SDK for [Cortexa](https://cortexa.ink) — hallucination detection, memory intelligence, and verification for LLM agents.

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

## Usage

### Simple API

```python
import cortexos

# Configure once
cortexos.configure(api_key="cx-...")

# Check an LLM response against source documents
result = cortexos.check(
    response="The product ships in 2-3 business days",
    sources=["Shipping: 2-3 business day delivery for all orders."]
)
print(result.hallucination_index)  # 0.0 = fully grounded
print(result.passed)               # True (HI < 0.3)

# Gate a memory before storing
gate = cortexos.gate(
    memory="Revenue grew 500% last quarter",
    sources=["Revenue grew 10% in Q4."]
)
print(gate.grounded)  # False
print(gate.flagged_claims)  # [{"text": "...", "verdict": "NUM_MISMATCH"}]
```

### Client API

```python
from cortexos import Cortex

cx = Cortex(api_key="cx-...", base_url="https://api.cortexa.ink")

result = cx.check(
    response="The return window is 30 days",
    sources=["Return policy: 30-day window for all items."],
)
print(result.hallucination_index)
```

### Async usage

```python
import asyncio
from cortexos import AsyncCortex

async def main():
    async with AsyncCortex(api_key="cx-...") as cx:
        result = await cx.check(
            response="The return window is 30 days",
            sources=["Return policy: 30-day window for all items."],
        )
        print(result.hallucination_index)

asyncio.run(main())
```

## API reference

### `Cortex` / `AsyncCortex`

| Method | Description |
|--------|-------------|
| `check(response, sources)` | Full hallucination check with per-claim verdicts |
| `gate(memory, sources)` | Gate check: should this memory be stored? |
| `memory_write(memory)` | Write memory with automatic duplicate detection |
| `memory_health(agent_id)` | Get memory health stats (duplicate %, token burn savings) |
| `trace(query)` | Find which memories caused a bad agent answer |
| `memory_clear(agent_id)` | Clear all memories for an agent |
| `health()` | Check server health |

### Memory Intelligence (v0.3.0)

```python
from cortexos import Cortex

cx = Cortex(api_key="cx-...", agent_id="support-bot")

# Write memories — duplicates are automatically blocked
result = cx.memory_write("The return window is 30 days.")
print(result.status)  # "written"

result = cx.memory_write("Returns are accepted within 30 days.")
print(result.status)         # "duplicate"
print(result.duplicate_pct)  # 50.0

# Run a health check — find out what % of your store is duplicates
health = cx.memory_health()
print(f"{health.duplicate_pct:.0f}% duplicates — {health.token_burn_savings_pct:.0f}% token waste")
# → 43% duplicates — 43% token waste

# Trace which memory caused a wrong answer
trace = cx.trace("The return window is 45 days")
for match in trace.matches:
    print(f"{match.score:.2f}  {match.memory}")
# → 0.82  The return window is 30 days.
```

### Top-level functions

| Function | Description |
|----------|-------------|
| `cortexos.check(response, sources)` | One-liner hallucination check |
| `cortexos.gate(memory, sources)` | One-liner gate check |
| `cortexos.configure(api_key, base_url)` | Set module-level defaults |

### Types

- **`CheckResult`** — `hallucination_index`, `total_claims`, `grounded_count`, `hallucinated_count`, `claims`, `passed`
- **`ClaimResult`** — `text`, `grounded`, `verdict`, `reason`, `source_quote`, `confidence`
- **`GateResult`** — `grounded`, `hallucination_index`, `flagged_claims`
- **`MemoryWriteResult`** — `status`, `memory_id`, `duplicate_of`, `duplicate_pct`, `is_duplicate`
- **`MemoryHealthResult`** — `total_memories`, `duplicate_count`, `duplicate_pct`, `token_burn_savings_pct`
- **`TraceResult`** — `query`, `matches`, `total_searched`; each `TraceMatch` has `memory`, `score`, `ts`, `memory_id`

### Errors

| Exception | When |
|-----------|------|
| `CortexError` | Base class for all SDK errors |
| `AuthError` | Invalid or missing API key (401/403) |
| `RateLimitError` | Too many requests (429); has `.retry_after` |
| `ServerError` | Unexpected 5xx from the server |

## TUI Monitor

```bash
pip install "cortexos[tui]"
cortexos monitor --api-key cx-... --url https://api.cortexa.ink
```

## Configuration

```python
cx = Cortex(
    api_key="cx-...",
    base_url="https://api.cortexa.ink",
    timeout=30.0,
    max_retries=3,
)
```

Or use environment variables:

```bash
export CORTEX_API_KEY=cx-...
export CORTEX_URL=https://api.cortexa.ink
```

## Running tests

```bash
pip install "cortexos[dev]"
pytest tests/test_client.py -v
```
