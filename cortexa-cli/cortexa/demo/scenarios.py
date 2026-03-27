"""Pre-built demo scenarios for showcasing Cortexa features.

Each scenario bundles a query, expected LLM response, and the set of
memories that would be retrieved — ready to run through the CAMA pipeline.

Usage:
    from cortexa.demo.scenarios import SCENARIOS, get_scenario

    scenario = get_scenario("shipping_trace")
    result = scorer.trace(
        query=scenario.query,
        response=scenario.response,
        memories=scenario.memories,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from cortexa.engine.models import Memory


@dataclass
class DemoScenario:
    """A pre-built demo scenario for the CAMA pipeline."""

    name: str
    title: str
    description: str
    query: str
    response: str
    memories: list[Memory] = field(default_factory=list)
    expected_issues: list[str] = field(default_factory=list)


def _now() -> datetime:
    return datetime.utcnow()


def build_shipping_trace() -> DemoScenario:
    """Shipping query with stale memory + ghost tokens.

    The hero scenario: mem_2847 says "2-day delivery" but the
    shipping policy changed to standard (5-7 days).
    """
    now = _now()
    return DemoScenario(
        name="shipping_trace",
        title="Stale Shipping Policy",
        description=(
            "A customer asks about delivery time. The agent retrieves a stale "
            'memory claiming "2-day delivery" — but the shipping policy changed '
            "6 weeks ago. Cortexa flags the stale memory and ghost tokens."
        ),
        query="When does my order arrive?",
        response="Your order arrives Thursday by 2pm with express 2-day delivery.",
        memories=[
            Memory(
                id="mem_2847",
                content="All orders ship express (2-day delivery)",
                source="shipping_policy.md",
                source_updated_at=now - timedelta(weeks=6),
                created_at=now - timedelta(days=90),
                last_accessed=now - timedelta(hours=1),
                access_count=142,
            ),
            Memory(
                id="mem_0010",
                content="Standard shipping takes 5-7 business days",
                source="shipping_policy.md",
                created_at=now - timedelta(days=10),
                last_accessed=now - timedelta(hours=3),
                access_count=200,
            ),
            Memory(
                id="mem_1203",
                content="User prefers blue color theme for dashboard",
                source="user_preferences",
                created_at=now - timedelta(days=60),
                last_accessed=now - timedelta(days=45),
                access_count=3,
            ),
            Memory(
                id="mem_0089",
                content="Returns accepted within 30 days of purchase",
                source="returns_policy.md",
                created_at=now - timedelta(days=90),
                last_accessed=now - timedelta(days=2),
                access_count=87,
            ),
            Memory(
                id="mem_0011",
                content="Express shipping costs $9.99 and takes 2 business days",
                source="shipping_policy.md",
                created_at=now - timedelta(days=10),
                last_accessed=now - timedelta(hours=5),
                access_count=150,
            ),
        ],
        expected_issues=[
            "STALE: mem_2847 — shipping policy updated after memory creation",
            "GHOST: mem_1203 — blue theme preference irrelevant to shipping",
            "GHOST: mem_0089 — returns policy irrelevant to shipping",
        ],
    )


def build_pricing_audit() -> DemoScenario:
    """Pricing query with contradicting memories.

    mem_0044 says free shipping over $50, mem_0055 says over $75.
    """
    now = _now()
    return DemoScenario(
        name="pricing_audit",
        title="Contradicting Free Shipping Thresholds",
        description=(
            "A customer asks about pricing. Two memories give conflicting "
            'free shipping thresholds: "$50" vs "$75". Cortexa flags the '
            "contradiction and recommends resolution."
        ),
        query="What's included with the premium plan?",
        response=(
            "The premium plan costs $49.99 per month. "
            "Free shipping on orders over $50."
        ),
        memories=[
            Memory(
                id="mem_0020",
                content="The premium plan costs $49.99 per month",
                source="pricing_page",
                created_at=now - timedelta(days=60),
                last_accessed=now - timedelta(days=3),
                access_count=40,
            ),
            Memory(
                id="mem_0044",
                content="Free shipping on orders over $50",
                source="promotions.md",
                created_at=now - timedelta(days=60),
                last_accessed=now - timedelta(days=1),
                access_count=55,
            ),
            Memory(
                id="mem_0055",
                content="Free shipping on orders over $75, no minimum for Prime members",
                source="shipping_policy.md",
                created_at=now - timedelta(days=100),
                last_accessed=now - timedelta(days=1),
                access_count=63,
            ),
        ],
        expected_issues=[
            "CONTRADICTION: mem_0044 vs mem_0055 — conflicting free shipping thresholds",
        ],
    )


def build_ghost_hunt() -> DemoScenario:
    """Scenario optimized for ghost token detection.

    Multiple irrelevant memories mixed with a few relevant ones.
    """
    now = _now()
    return DemoScenario(
        name="ghost_hunt",
        title="Ghost Token Waste Analysis",
        description=(
            "An agent retrieves 8 memories for a shipping query, but 5 of them "
            "are completely irrelevant (ghosts). Cortexa quantifies the wasted "
            "context tokens and estimates cost savings."
        ),
        query="How long does standard shipping take?",
        response="Standard shipping takes 5-7 business days.",
        memories=[
            # Relevant
            Memory(
                id="mem_0010",
                content="Standard shipping takes 5-7 business days",
                source="shipping_policy.md",
                created_at=now - timedelta(days=10),
                access_count=200,
            ),
            Memory(
                id="mem_0011",
                content="Express shipping costs $9.99 and takes 2 business days",
                source="shipping_policy.md",
                created_at=now - timedelta(days=10),
                access_count=150,
            ),
            Memory(
                id="mem_0100",
                content="Tracking numbers are sent via email within 24 hours of shipment",
                source="shipping_docs",
                created_at=now - timedelta(days=25),
                access_count=0,
            ),
            # Ghost candidates
            Memory(
                id="mem_1203",
                content="User prefers blue color theme for dashboard",
                source="user_preferences",
                created_at=now - timedelta(days=60),
                access_count=3,
            ),
            Memory(
                id="mem_0030",
                content="Password reset links expire after 24 hours",
                source="auth_docs",
                created_at=now - timedelta(days=90),
                access_count=15,
            ),
            Memory(
                id="mem_0200",
                content="Product reviews must be from verified purchasers",
                source="product_docs",
                created_at=now - timedelta(days=40),
                access_count=12,
            ),
            Memory(
                id="mem_0201",
                content="Loyalty points: earn 1 point per dollar spent",
                source="pricing_docs",
                created_at=now - timedelta(days=55),
                access_count=7,
            ),
            Memory(
                id="mem_0202",
                content="Profile photo upload supports JPG and PNG formats",
                source="account_docs",
                created_at=now - timedelta(days=70),
                access_count=2,
            ),
        ],
        expected_issues=[
            "GHOST: mem_1203, mem_0030, mem_0200, mem_0201, mem_0202 — irrelevant to shipping",
        ],
    )


def build_healthy_response() -> DemoScenario:
    """A clean scenario with no issues — demonstrates healthy output."""
    now = _now()
    return DemoScenario(
        name="healthy_response",
        title="Clean Response (No Issues)",
        description=(
            "A straightforward pricing query with well-sourced, consistent "
            "memories. Cortexa confirms the response is well-grounded."
        ),
        query="How much is the premium plan?",
        response="The premium plan costs $49.99 per month.",
        memories=[
            Memory(
                id="mem_0020",
                content="The premium plan costs $49.99 per month",
                source="pricing_page",
                created_at=now - timedelta(days=10),
                last_accessed=now - timedelta(hours=1),
                access_count=40,
            ),
            Memory(
                id="mem_0021",
                content="Annual billing saves 20%, bringing the price to $39.99 per month",
                source="pricing_page",
                created_at=now - timedelta(days=10),
                last_accessed=now - timedelta(hours=2),
                access_count=28,
            ),
        ],
        expected_issues=[],
    )


# Registry of all scenarios
SCENARIOS: dict[str, DemoScenario] = {}


def _register_scenarios() -> None:
    builders = [
        build_shipping_trace,
        build_pricing_audit,
        build_ghost_hunt,
        build_healthy_response,
    ]
    for builder in builders:
        scenario = builder()
        SCENARIOS[scenario.name] = scenario


def get_scenario(name: str) -> DemoScenario:
    """Get a scenario by name.

    Raises KeyError if the scenario doesn't exist.
    Available: shipping_trace, pricing_audit, ghost_hunt, healthy_response
    """
    if not SCENARIOS:
        _register_scenarios()
    return SCENARIOS[name]


def list_scenarios() -> list[str]:
    """List all available scenario names."""
    if not SCENARIOS:
        _register_scenarios()
    return list(SCENARIOS.keys())
