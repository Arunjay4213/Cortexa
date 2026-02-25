# CortexOS Quickstart

Get persistent memory and hallucination detection for your LLM agents in under 5 minutes.

---

## 1. Get an API Key

```bash
# Self-hosted: generate a key via the admin endpoint
curl -X POST http://localhost:8000/api/v1/auth/keys \
  -H "X-Admin-Secret: $CORTEX_ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-app", "scopes": ["read", "write"]}'
```

Save the returned `api_key` — you'll need it for all SDK calls.

## 2. Install

```bash
pip install cortexos
```

Requires Python 3.11+. No native dependencies.

## 3. Connect

```python
from cortexos import Cortex

cx = Cortex(
    api_key="sk-cortex-...",
    agent_id="my-agent",
    base_url="http://localhost:8000",  # or your hosted URL
)
```

## 4. Store Memories

```python
# Store a fact your agent learned
mem = cx.remember(
    "User prefers email over Slack for all communications",
    importance=0.85,
    tags=["preferences", "communication"],
    metadata={"source": "conversation_123"},
)
print(mem.id)  # "a1b2c3d4-..."
```

**Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `content` | `str` | required | The text to store |
| `importance` | `float` | 0.5 | Criticality score [0.0, 1.0] |
| `tags` | `list[str]` | `[]` | Filterable tags |
| `metadata` | `dict` | `{}` | Arbitrary key-value pairs |
| `tier` | `str` | `"warm"` | `"hot"`, `"warm"`, or `"cold"` |
| `ttl` | `int` | `None` | Auto-expire after N seconds |

## 5. Recall

```python
results = cx.recall("how does the user want to be contacted?", top_k=5)

for r in results:
    print(f"[{r.score:.2f}] {r.memory.content}")
    # [0.91] User prefers email over Slack for all communications
```

Feed these into your LLM prompt as context. CortexOS handles embedding, similarity search, and retrieval counting.

## 6. Check for Hallucinations

```python
# After your LLM generates a response, verify it
memory_ids = [r.memory.id for r in results]

cama = cx.check(
    query="How should I contact the user?",
    response="The user wants to be contacted via phone at 555-0123.",
    memory_ids=memory_ids,
)

print(f"Hallucination index: {cama.hallucination_index:.0%}")
# Hallucination index: 100%

for claim in cama.claims:
    if claim.is_hallucination:
        print(f"  FABRICATED: {claim.claim} [{claim.hallucination_reason}]")
        # FABRICATED: The user wants to be contacted via phone at 555-0123 [numerical_ungrounded]
```

**`check()` runs two stages:**
1. Creates a transaction with EAS (Equitable Attribution Scores)
2. Runs CAMA (Claim-Aware Memory Attribution) — decomposes the response into atomic claims, checks each against stored memories using NLI entailment + numerical grounding

## Under the Hood

```
User Query → Recall (semantic search) → LLM generates response
                                              ↓
                                     check() triggers CAMA:
                                       1. Claim decomposition
                                       2. Numerical gate (exact number matching)
                                       3. NLI entailment (DeBERTa)
                                       4. Shapley attribution (per-claim, per-memory)
                                       5. Hallucination index
```

**Hallucination reasons:**
| Reason | Meaning |
|--------|---------|
| `numerical_ungrounded` | Fabricated numbers not found in any memory |
| `nli_empty` | No memory passed the entailment threshold |
| `nli_low` | Some entailment but below confidence threshold |
| `opinion_skip` | Subjective claim — excluded from index |

## LangChain Integration

```python
from cortexos import Cortex
from langchain_core.runnables import RunnableLambda

cx = Cortex(api_key="sk-...", agent_id="langchain-bot")

def cortex_recall(query: str) -> str:
    """Recall relevant context from CortexOS."""
    results = cx.recall(query, top_k=5)
    return "\n".join(f"- {r.memory.content}" for r in results)

def cortex_remember(output: dict) -> dict:
    """Store the interaction as a memory."""
    cx.remember(
        f"Q: {output['query']}\nA: {output['response']}",
        importance=0.6,
    )
    return output

# Use as a step in your chain
recall_step = RunnableLambda(cortex_recall)
remember_step = RunnableLambda(cortex_remember)
```

## CrewAI Integration

```python
from crewai import Agent, Task, Crew
from cortexos import Cortex

cx = Cortex(api_key="sk-...", agent_id="crewai-researcher")

# Store research findings as memories
def store_finding(content: str):
    cx.remember(content, importance=0.8, tags=["research"])

# Recall context for tasks
def get_context(topic: str) -> str:
    results = cx.recall(topic, top_k=10)
    return "\n".join(r.memory.content for r in results)

# Use in CrewAI agent backstory or task context
researcher = Agent(
    role="Research Analyst",
    backstory=f"Previous findings:\n{get_context('market analysis')}",
    # ...
)
```

## Cross-Agent Memory

CortexOS namespaces memories by `agent_id`, but agents can read each other's memories:

```python
# Agent A stores a memory
cx_a = Cortex(api_key="sk-...", agent_id="agent-a")
cx_a.remember("Customer budget is $50,000", importance=0.9)

# Agent B recalls from Agent A's namespace
cx_b = Cortex(api_key="sk-...", agent_id="agent-b")
results = cx_b.recall("budget information", agent_id="agent-a", top_k=5)
```

## API Reference

| Method | Description |
|--------|-------------|
| `remember(content, *, importance, tags, metadata, tier, ttl)` | Store a memory |
| `recall(query, *, top_k, min_score, tags, agent_id)` | Semantic search |
| `get(memory_id)` | Fetch a single memory |
| `update(memory_id, *, importance, tags, metadata, tier)` | Update fields |
| `forget(memory_id)` | Soft-delete a memory |
| `forget_all()` | Delete all memories for the agent |
| `list(*, limit, offset, tier, sort_by, order)` | Paginated listing |
| `attribute(query, response, memory_ids)` | Run EAS attribution |
| `cama_attribute(transaction_id)` | Run CAMA on a transaction |
| `check(query, response, memory_ids)` | One-shot hallucination check |
| `recall_and_attribute(query, response, *, top_k)` | Recall + EAS in one call |

**Async:** All methods are available on `AsyncCortex` with the same signatures (prefix with `await`).

## Self-Hosting

```bash
# Clone and start with Docker Compose
git clone https://github.com/cortexos/cortex-engine.git
cd cortex-engine
cp .env.example .env
# Edit .env: set CORTEX_ADMIN_SECRET to a random string

docker compose up -d
# PostgreSQL + CortexOS will start, migrations run automatically
# Server ready at http://localhost:8000
# Health check: curl http://localhost:8000/healthz
```

## Deploy to Railway

```bash
# Push to Railway (uses railway.toml)
railway up
# Add a PostgreSQL plugin, set environment variables:
#   CORTEX_DATABASE_URL=postgresql+asyncpg://...
#   CORTEX_DATABASE_URL_SYNC=postgresql://...
#   CORTEX_ADMIN_SECRET=<random-string>
```
