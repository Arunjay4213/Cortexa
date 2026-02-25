#!/usr/bin/env python3
"""
CortexOS SDK Demo — stores memories, recalls, runs CAMA, asserts hallucination detection.

Usage:
    python scripts/sdk_demo.py

Requires:
    - CortexOS engine running on localhost:8000
    - API key: ***REMOVED***
"""

import sys
import time

from cortexos import Cortex, CAMAAttribution

API_KEY = "***REMOVED***"
BASE_URL = "http://localhost:8000"
AGENT_ID = "sdk-demo-agent"

# ── Setup ─────────────────────────────────────────────────────────────────

print("=" * 60)
print("  CortexOS SDK Demo")
print("=" * 60)

cx = Cortex(api_key=API_KEY, agent_id=AGENT_ID, base_url=BASE_URL, timeout=120.0)

# Clean up any previous demo memories
print("\n[1] Cleaning up previous demo data...")
deleted = cx.forget_all()
print(f"    Deleted {deleted} existing memories")

# ── Store 5 memories ──────────────────────────────────────────────────────

print("\n[2] Storing 5 memories...")

memories = []

m1 = cx.remember(
    "Wheeler County, TX: satellite solar score 88, irradiance 5.6 kWh/m2/day, slope 2.1 degrees",
    importance=0.8,
    tags=["site", "texas"],
)
memories.append(m1)
print(f"    mem1: {m1.id[:12]}... score={m1.importance}")

m2 = cx.remember(
    "Land ownership: James R. Holloway, 847 acres, Wheeler County, Texas",
    importance=0.8,
    tags=["land", "ownership"],
)
memories.append(m2)
print(f"    mem2: {m2.id[:12]}... land ownership")

m3 = cx.remember(
    "Grid connection: nearest substation Shamrock 115kV, distance 1.1 miles, voltage 115kV",
    importance=0.7,
    tags=["grid", "infrastructure"],
)
memories.append(m3)
print(f"    mem3: {m3.id[:12]}... grid connection")

m4 = cx.remember(
    "Financial model: IRR 12.4%, CAPEX $98,200,000, LCOE $31.20/MWh, lease revenue $1,016,400/year",
    importance=0.9,
    tags=["financial", "model"],
)
memories.append(m4)
print(f"    mem4: {m4.id[:12]}... financials")

m5 = cx.remember(
    "Yield forecast: P50 298,450 MWh/year, capacity factor 22.8%, degradation 0.5%/year",
    importance=0.7,
    tags=["yield", "forecast"],
)
memories.append(m5)
print(f"    mem5: {m5.id[:12]}... yield forecast")

# ── Recall ────────────────────────────────────────────────────────────────

print("\n[3] Semantic recall: 'solar irradiance and financials'")
results = cx.recall("solar irradiance and financial projections", top_k=5)
print(f"    Recalled {len(results)} memories:")
for r in results:
    print(f"      [{r.score:.3f}] {r.memory.content[:70]}...")

assert len(results) >= 2, f"Expected at least 2 recall results, got {len(results)}"
print("    PASS: recall returned >= 2 results")

# ── CAMA Check — grounded response ───────────────────────────────────────

print("\n[4] CAMA check — grounded response (should have LOW hallucination index)")
grounded_response = (
    "The Wheeler County site has a solar score of 88 with irradiance of 5.6 kWh/m2/day. "
    "The land is owned by James R. Holloway, covering 847 acres. "
    "The nearest substation is Shamrock 115kV, just 1.1 miles away. "
    "The financial model shows an IRR of 12.4% with LCOE of $31.20/MWh."
)

memory_ids = [m.id for m in memories]
t0 = time.time()
cama: CAMAAttribution = cx.check(
    query="Tell me about the Wheeler County solar site",
    response=grounded_response,
    memory_ids=memory_ids,
)
elapsed = time.time() - t0

print(f"    Transaction: {cama.transaction_id[:12]}...")
print(f"    Claims: {len(cama.claims)}")
print(f"    Hallucination index: {cama.hallucination_index:.2f}")
print(f"    Dead memories: {len(cama.dead_memories)}")
print(f"    Latency: {elapsed:.1f}s")

for c in cama.claims:
    status = "HALLUC" if c.is_hallucination else "OK"
    reason = f" [{c.hallucination_reason}]" if c.hallucination_reason else ""
    print(f"      [{status}] [{c.claim_type}] {c.claim[:65]}...{reason}")

# Grounded response should have low hallucination index
assert cama.hallucination_index <= 0.6, (
    f"Grounded response hallucination_index={cama.hallucination_index:.2f}, expected <= 0.6"
)
print(f"    PASS: hallucination_index={cama.hallucination_index:.2f} <= 0.6")

# ── CAMA Check — hallucinated response ───────────────────────────────────

print("\n[5] CAMA check — MIXED response (grounded facts + fabricated numbers)")
# This response mixes REAL data from memories with FABRICATED claims.
# Grounded: solar score 88, irradiance 5.6, Holloway owns the land, 847 acres
# Fabricated: 2,500 acres total (real=847), IRR 25.6% (real=12.4%), $5,000,000 revenue (real=$1,016,400)
mixed_response = (
    "The Wheeler County site has a solar score of 88 with irradiance of 5.6 kWh/m2/day. "
    "The land is owned by James R. Holloway. "
    "The total developable area spans 2,500 acres across multiple parcels. "
    "The IRR is projected at 25.6% with annual revenue exceeding $5,000,000. "
    "The nearest substation is Shamrock 115kV, 1.1 miles away."
)

cama_mixed: CAMAAttribution = cx.check(
    query="Tell me about the Wheeler County solar site",
    response=mixed_response,
    memory_ids=memory_ids,
)

print(f"    Transaction: {cama_mixed.transaction_id[:12]}...")
print(f"    Claims: {len(cama_mixed.claims)}")
print(f"    Hallucination index: {cama_mixed.hallucination_index:.2f}")

halluc_claims = [c for c in cama_mixed.claims if c.is_hallucination]
grounded_claims = [c for c in cama_mixed.claims if not c.is_hallucination]
print(f"    Grounded claims: {len(grounded_claims)}")
print(f"    Hallucinated claims: {len(halluc_claims)}")

for c in cama_mixed.claims:
    status = "HALLUC" if c.is_hallucination else "OK"
    reason = f" [{c.hallucination_reason}]" if c.hallucination_reason else ""
    print(f"      [{status}] [{c.claim_type}] {c.claim[:65]}...{reason}")

# Mixed response should have HIGHER hallucination index than the fully grounded one
assert cama_mixed.hallucination_index > cama.hallucination_index, (
    f"Mixed response ({cama_mixed.hallucination_index:.2f}) should have higher "
    f"hallucination_index than grounded ({cama.hallucination_index:.2f})"
)
print(f"    PASS: mixed ({cama_mixed.hallucination_index:.2f}) > grounded ({cama.hallucination_index:.2f})")

# Must detect at least 1 hallucinated claim (the fabricated numbers)
assert len(halluc_claims) >= 1, f"Expected at least 1 hallucinated claim, got {len(halluc_claims)}"
print(f"    PASS: {len(halluc_claims)} claims flagged as hallucinated")

# Must also have at least 1 grounded claim (the real data)
assert len(grounded_claims) >= 1, f"Expected at least 1 grounded claim, got {len(grounded_claims)}"
print(f"    PASS: {len(grounded_claims)} claims verified as grounded")

# ── Verify memory listing ────────────────────────────────────────────────

print("\n[6] Verify memory listing")
page = cx.list(limit=10)
print(f"    Total memories: {page.total}")
print(f"    Items returned: {len(page.items)}")
assert page.total >= 5, f"Expected at least 5 memories, got {page.total}"
print(f"    PASS: {page.total} memories in store")

# ── Cleanup ──────────────────────────────────────────────────────────────

print("\n[7] Cleanup — deleting demo memories")
deleted = cx.forget_all()
print(f"    Deleted {deleted} memories")

cx.close()

# ── Summary ──────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  ALL ASSERTIONS PASSED")
print("=" * 60)
print(f"""
  remember()       5 memories stored
  recall()         {len(results)} results returned
  check()          grounded HI={cama.hallucination_index:.2f}, mixed HI={cama_mixed.hallucination_index:.2f}
  forget_all()     {deleted} memories cleaned up
  list()           pagination verified
""")
