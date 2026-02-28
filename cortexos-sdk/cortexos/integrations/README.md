# CortexOS Integrations

Drop-in replacement clients for **Mem0** and **SuperMemory** that transparently
apply CortexOS verification on every write.

## Installation

```bash
pip install cortexos

# Plus whichever memory provider you use:
pip install mem0ai        # for Mem0
pip install supermemory   # for SuperMemory
```

## Quick Start — Mem0

Replace your existing Mem0 import:

```python
# Before
from mem0 import MemoryClient
client = MemoryClient(api_key="m0-...")

# After
from cortexos.integrations import Mem0Client
client = Mem0Client(
    mem0_api_key="m0-...",
    cortex_api_key="cx-...",
    cortex_base_url="https://api.cortexa.ink",
    sources=["Your ground-truth documents here."],
)
```

Every `.add()` call now runs shield + gate verification before writing to Mem0.
All other methods (search, get_all, delete, history) pass through unchanged.

## Quick Start — SuperMemory

```python
from cortexos.integrations import SuperMemoryClient

client = SuperMemoryClient(
    supermemory_api_key="sm-...",
    cortex_api_key="cx-...",
    sources=["Ground truth document text."],
)

# Verified add
client.add("Machine learning is a subset of AI.")

# Search passes through unchanged
results = client.search("machine learning")
```

## Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cortex_api_key` | `str \| None` | `None` | API key for CortexOS engine |
| `cortex_base_url` | `str` | `https://api.cortexa.ink` | CortexOS engine URL |
| `sources` | `list[str] \| callable \| None` | `None` | Ground-truth docs for gate |
| `shield_enabled` | `bool` | `True` | Run shield checks on writes |
| `gate_enabled` | `bool` | `True` | Run gate checks on writes |
| `gate_threshold` | `float` | `0.3` | HI threshold for gate (0.0-1.0) |
| `on_block` | `callable \| None` | `None` | Callback when gate blocks |
| `on_threat` | `callable \| None` | `None` | Callback when shield fires |

## Source Resolvers

### Static sources (same for all users)

```python
client = Mem0Client(
    mem0_api_key="m0-...",
    sources=[
        "Product ships from warehouse in 2-3 business days.",
        "Return window is 30 days from delivery.",
    ],
)
```

### Dynamic sources (per-user)

```python
def get_user_sources(user_id):
    """Fetch the user's specific context documents."""
    docs = my_database.get_docs_for(user_id)
    return [doc.text for doc in docs]

client = Mem0Client(
    mem0_api_key="m0-...",
    sources=get_user_sources,
)

# When add() is called, sources are resolved for this user
client.add("User's order arrives tomorrow", user_id="user-42")
```

### Shield-only mode (no sources)

```python
# sources=None → shield runs, gate is skipped
client = Mem0Client(
    mem0_api_key="m0-...",
    sources=None,
    shield_enabled=True,
)
```

## Handling Blocked Writes

```python
from cortexos.exceptions import MemoryBlockedError

try:
    client.add("Revenue grew 500% last quarter", user_id="user-1")
except MemoryBlockedError as e:
    print(f"Blocked: {e.reason}")

    if e.is_injection:
        print("Injection attack detected!")

    if e.gate_result:
        for claim in e.gate_result.flagged_claims:
            print(f"  - {claim['text']}: {claim['verdict']}")
```

## Callbacks

```python
def handle_block(memory: str, gate_result):
    """Called when gate blocks a write."""
    print(f"BLOCKED: {memory[:50]}...")
    for claim in gate_result.flagged_claims:
        print(f"  Flagged: {claim['text']} ({claim['verdict']})")

def handle_threat(memory: str, shield_result):
    """Called when shield detects a threat."""
    print(f"THREAT: {shield_result.threat_type} ({shield_result.severity})")

client = Mem0Client(
    mem0_api_key="m0-...",
    sources=["Ground truth."],
    on_block=handle_block,
    on_threat=handle_threat,
)
```

## Fail-Open Policy

If CortexOS is unreachable, writes proceed with a warning log.
Your app won't break if CortexOS is temporarily down.

```
WARNING:cortexos.integrations:CortexOS shield failed: Connection refused. Failing open.
```

## Direct Verification Client

For custom integrations, use the verification client directly:

```python
from cortexos.verification import VerificationClient

vc = VerificationClient(api_key="cx-...", base_url="https://api.cortexa.ink")

# Async
result = await vc.check("Agent response text", sources=["source doc"])
print(f"HI: {result.hallucination_index}, passed: {result.passed}")

# Sync
result = vc.check_sync("Agent response text", sources=["source doc"])
```
