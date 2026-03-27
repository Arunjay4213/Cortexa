# CortexOS SDK — Full Reference

> **Version:** 0.2.2 · **Python:** ≥3.11 · **License:** MIT
> **PyPI:** [pypi.org/project/cortexos](https://pypi.org/project/cortexos/)

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [SDK API](#sdk-api)
  - [Module-Level Functions](#module-level-functions)
  - [Cortex (Sync Client)](#cortex-sync-client)
  - [AsyncCortex (Async Client)](#asynccortex-async-client)
  - [VerificationClient (Low-Level)](#verificationclient-low-level)
- [Result Types](#result-types)
- [Error Handling](#error-handling)
- [Integrations](#integrations)
  - [Mem0](#mem0-integration)
  - [SuperMemory](#supermemory-integration)
  - [Building Custom Integrations](#building-custom-integrations)
- [TUI Monitor](#tui-monitor)
  - [Launch](#launch)
  - [Keyboard Shortcuts](#keyboard-shortcuts)
  - [Tabs](#tabs)
  - [Command Palette](#command-palette)
- [Environment Variables](#environment-variables)
- [Defaults & Constants](#defaults--constants)

---

## Installation

```bash
# Core SDK (check + gate)
pip install cortexos

# With TUI monitor
pip install "cortexos[tui]"

# With dev/test tools
pip install "cortexos[dev]"

# Everything
pip install "cortexos[tui,dev]"
```

### Dependencies

| Extra | Packages |
|-------|----------|
| core | `httpx >=0.27`, `pydantic >=2.7` |
| tui | `textual >=0.80`, `httpx-sse >=0.4`, `click >=8` |
| dev | `pytest >=8`, `pytest-asyncio >=0.23`, `respx >=0.21` |

---

## Quick Start

```python
import cortexos

cortexos.configure(api_key="cx-your-key")

# Verify an LLM response against source documents
result = cortexos.check(
    response="The return window is 30 days.",
    sources=["Return policy: 30-day window for all items."]
)

print(result.hallucination_index)  # 0.0 = fully grounded
print(result.passed)               # True (HI < 0.3)
print(result.claims[0].verdict)    # "GROUNDED"
```

---

## Configuration

Three ways to configure, in order of precedence:

### 1. Pass directly to client

```python
from cortexos import Cortex

cx = Cortex(
    api_key="cx-...",
    base_url="https://api.cortexa.ink",
    timeout=30.0,
    max_retries=3,
)
```

### 2. Module-level configure

```python
import cortexos

cortexos.configure(
    api_key="cx-...",
    base_url="https://api.cortexa.ink",
)

# All subsequent calls use these defaults
result = cortexos.check(response="...", sources=["..."])
```

### 3. Environment variables

```bash
export CORTEX_API_KEY=cx-...
export CORTEX_URL=https://api.cortexa.ink    # optional, has default
```

---

## SDK API

### Module-Level Functions

These are the simplest way to use CortexOS — import and call.

#### `cortexos.configure(api_key=None, base_url=None)`

Set module-level defaults for all subsequent calls.

```python
cortexos.configure(api_key="cx-...")
```

#### `cortexos.check(response, sources, *, api_key=None, base_url=None, config=None) → CheckResult`

One-liner hallucination check.

```python
result = cortexos.check(
    response="The product ships in 2-3 business days.",
    sources=["Shipping: 2-3 business day delivery for all orders."]
)

print(result.hallucination_index)   # 0.0
print(result.passed)                # True
print(result.total_claims)          # 1
print(result.claims[0].verdict)     # "GROUNDED"
```

#### `cortexos.gate(memory, sources, *, api_key=None, base_url=None) → GateResult`

One-liner memory gating — should this memory be stored?

```python
gate = cortexos.gate(
    memory="Revenue grew 500% last quarter.",
    sources=["Revenue grew 10% in Q4."]
)

print(gate.grounded)        # False
print(gate.flagged_claims)  # [{"text": "...", "verdict": "NUM_MISMATCH"}]
```

---

### Cortex (Sync Client)

Full-featured synchronous client with connection pooling and retries.

```python
from cortexos import Cortex

cx = Cortex(
    api_key="cx-...",                       # required (or CORTEX_API_KEY env)
    base_url="https://api.cortexa.ink",     # optional
    agent_id="default",                      # identifies this agent
    timeout=30.0,                            # request timeout in seconds
    max_retries=3,                           # retry count for transient errors
)
```

**Context manager support:**

```python
with Cortex(api_key="cx-...") as cx:
    result = cx.check(response="...", sources=["..."])
# Connection automatically cleaned up
```

#### `cx.check(response, sources, *, agent_id=None, config=None) → CheckResult`

Full hallucination verification pipeline.

```python
result = cx.check(
    response="Our SLA guarantees 99.9% uptime.",
    sources=[
        "SLA terms: We guarantee 99.9% uptime for enterprise plans.",
        "Standard plans have 99.5% uptime SLA."
    ],
    agent_id="support-bot",  # optional override
)

print(result.hallucination_index)   # 0.0–1.0
print(result.total_claims)          # number of atomic claims extracted
print(result.grounded_count)        # claims verified against sources
print(result.hallucinated_count)    # claims contradicted by sources
print(result.opinion_count)         # subjective claims (not checkable)
print(result.latency_ms)            # pipeline latency
print(result.passed)                # True if HI < 0.3
print(result.passed_at(0.5))        # True if HI < custom threshold

for claim in result.claims:
    print(f"  {claim.verdict}: {claim.text}")
    print(f"    confidence: {claim.confidence}")
    print(f"    quote: {claim.source_quote}")
```

#### `cx.gate(memory, sources, *, agent_id=None) → GateResult`

Memory gating — verify before storing.

```python
gate = cx.gate(
    memory="User prefers overnight shipping.",
    sources=["User selected standard shipping on last 3 orders."]
)

if not gate.grounded:
    print("Blocked — hallucinated memory")
    for claim in gate.flagged_claims:
        print(f"  {claim['verdict']}: {claim['text']}")
```

#### `cx.health() → dict`

Server health check.

```python
status = cx.health()
print(status)  # {"status": "ok", ...}
```

---

### AsyncCortex (Async Client)

Identical API to `Cortex`, but all methods are `async`.

```python
import asyncio
from cortexos import AsyncCortex

async def main():
    async with AsyncCortex(api_key="cx-...") as cx:
        # Check
        result = await cx.check(
            response="The CEO founded the company in 2015.",
            sources=["Founded in 2015 by Jane Smith."]
        )
        print(result.hallucination_index)

        # Gate
        gate = await cx.gate(
            memory="Customer is a platinum member.",
            sources=["Customer tier: Gold."]
        )
        print(gate.grounded)  # False

        # Health
        health = await cx.health()
        print(health)

asyncio.run(main())
```

---

### VerificationClient (Low-Level)

Thin async HTTP client used internally by integrations. Includes `shield()` for injection detection.

```python
from cortexos import VerificationClient

vc = VerificationClient(api_key="cx-...", base_url="https://api.cortexa.ink")

# Async usage
result = await vc.check(response="...", sources=["..."])
gate   = await vc.gate(candidate_memory="...", sources=["..."])
shield = await vc.shield(candidate_memory="...", source_type="user_input")

# Sync wrappers (for non-async contexts)
result = vc.check_sync(response="...", sources=["..."])
gate   = vc.gate_sync(candidate_memory="...", sources=["..."])
shield = vc.shield_sync(candidate_memory="...", source_type="user_input")
```

---

## Result Types

### CheckResult

Returned by `check()`.

| Field | Type | Description |
|-------|------|-------------|
| `hallucination_index` | `float` | 0.0 (fully grounded) → 1.0 (fully hallucinated) |
| `total_claims` | `int` | Number of atomic claims extracted |
| `grounded_count` | `int` | Claims verified by sources |
| `hallucinated_count` | `int` | Claims contradicted by sources |
| `opinion_count` | `int` | Subjective/uncheckable claims |
| `claims` | `list[ClaimResult]` | Per-claim breakdown |
| `latency_ms` | `float` | Pipeline latency in milliseconds |
| `passed` | `bool` | Property — `True` if HI < 0.3 |

| Method | Description |
|--------|-------------|
| `passed_at(threshold)` | `True` if HI < given threshold |

### ClaimResult

Individual claim verdict.

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | The atomic claim text |
| `grounded` | `bool` | Whether the claim is supported |
| `verdict` | `str` | One of the verdict types below |
| `reason` | `str` | Explanation of the verdict |
| `source_quote` | `str \| None` | Supporting quote from sources |
| `confidence` | `float` | Model confidence (0.0–1.0) |

**Verdict types:**

| Verdict | Meaning |
|---------|---------|
| `GROUNDED` | Claim is supported by the source documents |
| `NUM_MISMATCH` | Numerical value doesn't match the sources |
| `UNSUPPORTED` | Claim has no support in the sources |
| `OPINION` | Subjective claim — cannot be fact-checked |

### GateResult

Returned by `gate()`.

| Field | Type | Description |
|-------|------|-------------|
| `grounded` | `bool` | `True` if memory passed the gate |
| `hallucination_index` | `float` | HI score |
| `flagged_claims` | `list[dict]` | Claims that failed verification |
| `suggested_corrections` | `list[dict] \| None` | Suggested fixes (if available) |

### ShieldResult

Returned by `shield()` (via VerificationClient).

| Field | Type | Description |
|-------|------|-------------|
| `safe` | `bool` | `True` if no threats detected |
| `threat_type` | `str \| None` | `INSTRUCTION_INJECTION`, `ANOMALY`, etc. |
| `severity` | `str \| None` | `CRITICAL`, `WARN`, `INFO` |
| `blocked_content` | `str \| None` | The flagged content |
| `source_type` | `str` | Origin type of the content |

---

## Error Handling

All exceptions inherit from `CortexError`.

```python
from cortexos import Cortex, CortexError, AuthError, RateLimitError, ServerError

cx = Cortex(api_key="cx-...")

try:
    result = cx.check(response="...", sources=["..."])
except AuthError:
    print("Invalid or missing API key (401/403)")
except RateLimitError as e:
    print(f"Rate limited — retry after {e.retry_after}s")
except ServerError:
    print("Server error (5xx)")
except CortexError:
    print("Other SDK error")
```

### Exception Hierarchy

```
CortexError                       # Base for all SDK errors
├── AuthError                     # 401/403 — invalid/missing API key
├── RateLimitError                # 429 — too many requests
│   └── .retry_after: float       #   seconds to wait
├── MemoryNotFoundError           # 404 — memory ID not found
├── ValidationError               # 422 — invalid request payload
└── ServerError                   # 5xx — unexpected server error

CortexOSError                     # Base for integration errors
├── MemoryBlockedError            # Memory write blocked by shield/gate
│   ├── .is_injection: bool       #   was it an injection attempt?
│   └── .reason: str              #   why it was blocked
└── VerificationUnavailableError  # API unreachable (fail-open)
```

### Retry Behavior

The HTTP layer automatically retries transient errors:

| Retried | Not Retried |
|---------|-------------|
| 429 (rate limit) | 401 (auth) |
| 502 (bad gateway) | 404 (not found) |
| 503 (unavailable) | 422 (validation) |
| 504 (timeout) | |

Backoff: `0.5s × 2^attempt` (exponential), up to `max_retries` (default 3).

---

## Integrations

Drop-in wrappers for popular memory providers. They intercept writes with CortexOS verification while passing reads through unchanged.

### Mem0 Integration

```bash
pip install cortexos mem0ai
```

```python
from cortexos.integrations.mem0 import Mem0Client

mem = Mem0Client(
    mem0_api_key="m0-...",
    cortex_api_key="cx-...",

    # Provide source documents for gate verification
    sources=["Company policy: 30-day return window."],
    # Or dynamic sources per user:
    # sources=lambda user_id: fetch_docs_for(user_id),

    shield_enabled=True,       # detect injection attacks
    gate_enabled=True,         # verify grounding before write
    gate_threshold=0.3,        # block if HI ≥ 0.3

    # Optional callbacks
    on_block=lambda mem, result: print(f"Blocked: {mem}"),
    on_threat=lambda mem, result: print(f"Threat: {result.threat_type}"),
)

# Verified writes — shield + gate run before write reaches Mem0
mem.add("User prefers express shipping.", user_id="u123")

# Unverified reads — pass through directly to Mem0
results = mem.search("shipping preference", user_id="u123")
memories = mem.get_all(user_id="u123")
mem.update(memory_id="...", text="updated text")
mem.delete(memory_id="...")
mem.delete_all(user_id="u123")
history = mem.history(memory_id="...")
```

**What happens on `add()`:**
1. **Shield** checks for injection/anomaly → raises `MemoryBlockedError` if threat found
2. **Gate** verifies grounding against sources → raises `MemoryBlockedError` if HI ≥ threshold
3. If both pass → write reaches Mem0
4. If CortexOS API is unreachable → **fail-open** (write proceeds with warning)

### SuperMemory Integration

```bash
pip install cortexos supermemory
```

```python
from cortexos.integrations.supermemory import SuperMemoryClient

sm = SuperMemoryClient(
    supermemory_api_key="sm-...",
    cortex_api_key="cx-...",
    sources=["Product catalog: ..."],
    shield_enabled=True,
    gate_enabled=True,
    gate_threshold=0.3,
)

# Verified writes
sm.add(content="Product X costs $99.", container_tag="products")
sm.add_batch(documents=[
    {"content": "Fact 1", "container_tag": "facts"},
    {"content": "Fact 2", "container_tag": "facts"},
])

# Unverified reads
results = sm.search(q="pricing")
memories = sm.search_memories(q="pricing")
doc = sm.get(document_id="...")
docs = sm.list()
sm.update(document_id="...", content="updated")
sm.delete(document_id="...")
sm.upload_file(file=open("data.pdf", "rb"))
```

### Building Custom Integrations

Extend `VerifiedMemoryClient` to wrap any memory provider:

```python
from cortexos.integrations.base import VerifiedMemoryClient

class MyMemoryClient(VerifiedMemoryClient):
    def __init__(self, my_provider, **cortex_kwargs):
        super().__init__(**cortex_kwargs)
        self._provider = my_provider

    def write(self, text, user_id=None):
        # This runs shield + gate before writing
        self._verify_write_sync(text, user_id=user_id)
        return self._provider.write(text)

    async def write_async(self, text, user_id=None):
        await self._verify_write(text, user_id=user_id)
        return await self._provider.write_async(text)

    # Reads pass through — no verification needed
    def read(self, query):
        return self._provider.read(query)
```

**Constructor options for `VerifiedMemoryClient`:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cortex_api_key` | `str \| None` | `None` | API key (or env var) |
| `cortex_base_url` | `str` | `https://api.cortexa.ink` | Engine URL |
| `sources` | `list[str] \| Callable \| None` | `None` | Static docs or `fn(user_id) → docs` |
| `shield_enabled` | `bool` | `True` | Run injection detection |
| `gate_enabled` | `bool` | `True` | Run grounding verification |
| `gate_threshold` | `float` | `0.3` | Block if HI ≥ threshold |
| `on_block` | `Callable` | `None` | `fn(memory, GateResult)` callback |
| `on_threat` | `Callable` | `None` | `fn(memory, ShieldResult)` callback |

---

## TUI Monitor

A real-time terminal dashboard for monitoring all verification activity across your agents.

### Launch

```bash
# Install TUI extras
pip install "cortexos[tui]"

# Launch monitor
cortexos -k cx-your-api-key

# Custom engine URL
cortexos -k cx-your-api-key -u https://your-engine.example.com
```

**CLI Options:**

| Flag | Long | Description |
|------|------|-------------|
| `-k` | `--api-key` | API key (required, or `CORTEX_API_KEY` env) |
| `-u` | `--url` | Engine base URL (default: `https://api.cortexa.ink`) |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1` | Switch to Feed tab |
| `2` | Switch to Claims tab |
| `3` | Switch to Memory tab |
| `4` | Switch to Agents tab |
| `5` | Switch to Inspect tab |
| `p` | Pause / resume event stream |
| `c` | Clear session data |
| `q` | Quit |
| `:` or `Ctrl+\` | Open command palette |
| `Esc` | Dismiss command palette |

### Tabs

#### Tab 1 — Feed

Live stream of all verification events as they happen.

**Layout:**
- **Left:** Scrolling event log — each entry shows type, HI score, claim counts, and verdict summary
- **Right sidebar:** Session stats (total checks, grounded%, halluc%, avg HI, latency) + HI trend sparkline

**Tab-specific keys:**
| Key | Action |
|-----|--------|
| `f` | Cycle filter: All → Check → Gate → Shield |
| `p` | Pause/resume |

**Event color coding:**
| HI Range | Color |
|----------|-------|
| < 0.2 | Green |
| 0.2–0.4 | Yellow-green |
| 0.4–0.6 | Orange |
| 0.6–0.8 | Red-orange |
| ≥ 0.8 | Hot pink |

---

#### Tab 2 — Claims

Searchable table of every individual claim across all checks.

**Columns:** `#`, `Time`, `Verdict`, `Confidence`, `Claim Text`

**Tab-specific keys:**
| Key | Action |
|-----|--------|
| `s` | Cycle sort: Time → Verdict → Confidence |
| `f` | Cycle filter: All → Grounded → Num Mismatch → Unsupported → Opinion |
| `Enter` | Jump to Inspect tab for selected event |

**Verdict colors:**
| Verdict | Icon | Color |
|---------|------|-------|
| GROUNDED | ✦ | Green |
| NUM_MISMATCH | ● | Red |
| UNSUPPORTED | ● | Orange |
| OPINION | ◌ | Gray |

---

#### Tab 3 — Memory

Memory operation log — tracks all gate and shield activity.

**Stats displayed:**
- Writes attempted / blocked / blocked %
- Injections caught
- Anomalies detected
- Agent trust distribution

**Indicators:**
- Gate pass → green
- Gate block → red with HI score
- Shield injection → red background alert

---

#### Tab 4 — Agents

Per-agent leaderboard ranked by hallucination risk (worst first).

**Columns:** `Agent`, `Checks`, `Avg HI`, `Halluc%`, `Trend`, `Last Seen`

**Features:**
- Mini sparklines showing HI trend per agent (last 5 values)
- Risk banner for high-hallucination agents
- Auto-refresh on new events

---

#### Tab 5 — Inspect

Deep-dive into a single verification event.

**Header:** Event type, timestamp, latency, HI score, hallucination count

**Body:** Full claim breakdown:
- Verdict with icon and color
- Confidence bar (16-char visual)
- Reason text
- Source quote (if available)
- Attribution scores (if available)

**Tab-specific keys:**
| Key | Action |
|-----|--------|
| `e` | Export event to JSON (`/tmp/cortex_session.json`) |
| `r` | Re-verify (placeholder) |

---

### Command Palette

Open with `:` or `Ctrl+\`. Type a command and press Enter.

| Command | Description |
|---------|-------------|
| `clear` | Clear all session data |
| `export` | Export session to `/tmp/cortex_session.json` |
| `filter check` | Show only check events |
| `filter gate` | Show only gate events |
| `filter all` | Show all event types |
| `threshold` | Display current gate threshold (HI ≤ 0.3) |
| `connect` | Show connection URL |
| `feed` | Switch to Feed tab |
| `claims` | Switch to Claims tab |
| `memory` | Switch to Memory tab |
| `agents` | Switch to Agents tab |
| `inspect` | Switch to Inspect tab |
| `pause` | Toggle pause |
| `quit` | Exit monitor |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CORTEX_API_KEY` | API key for authentication | — (required) |
| `CORTEX_URL` | Base URL for the CortexOS engine | `https://api.cortexa.ink` |

---

## Defaults & Constants

| Setting | Value |
|---------|-------|
| Default base URL | `https://api.cortexa.ink` |
| Request timeout | 30 seconds |
| Max retries | 3 |
| Retry backoff | `0.5s × 2^attempt` |
| Gate pass threshold | HI < 0.3 |
| Retried status codes | 429, 502, 503, 504 |
| Non-retried status codes | 401, 404, 422 |
| Fail-open policy | Integrations allow writes when API is unreachable |

---

## Running Tests

```bash
pip install "cortexos[dev]"
pytest tests/test_client.py -v
pytest tests/ -v  # all tests
```

---

*Get an API key at [cortexa.ink](https://cortexa.ink)*
