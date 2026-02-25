"""
Synthetic memory generators.

Produces realistic memory text in multiple domains:
  - Customer support conversations
  - Technical documentation chunks
  - User preference statements
  - Factual knowledge claims
"""

from __future__ import annotations

import hashlib
import random
import string
import uuid
from itertools import cycle

# ── Seed phrases by domain ───────────────────────────────────────────────────

_SUPPORT_TEMPLATES = [
    "User reported that {feature} is not working correctly when {condition}.",
    "Customer {name} opened ticket #{num} complaining about {feature} performance.",
    "Support escalation: {feature} crashes on {platform} when user {action}.",
    "Resolved: {feature} issue was caused by {reason}. Fix deployed in v{version}.",
    "User asks how to configure {feature} for {use_case} environment.",
    "High priority: {num} users affected by {feature} outage since {time}.",
]

_TECH_DOC_TEMPLATES = [
    "The {component} module handles {responsibility} via the {pattern} pattern.",
    "Configuration: set {param}={value} to enable {feature} in {environment}.",
    "Performance note: {operation} has O({complexity}) time complexity.",
    "API endpoint {method} /{path} accepts {payload} and returns {response}.",
    "Known limitation: {feature} does not support {edge_case} in version {version}.",
    "Migration guide from v{version_old} to v{version_new}: {step}.",
]

_PREFERENCE_TEMPLATES = [
    "User {name} explicitly prefers {preference} over {alternative}.",
    "Agent {agent} has been configured to use {setting} by default.",
    "User communication preference: contact via {channel}, not {other_channel}.",
    "User timezone is {timezone}; schedule all meetings in that local time.",
    "User language preference: {lang}. Always respond in {lang}.",
    "User expertise level in {domain}: {level}. Adjust explanations accordingly.",
]

_FACT_TEMPLATES = [
    "{entity} was founded in {year} and is headquartered in {city}.",
    "The {protocol} specification defines {concept} as {definition}.",
    "{technology} version {version} was released on {date} with {feature}.",
    "According to {source}, {claim} with {confidence} confidence.",
    "{metric} for {system} averages {value} under typical {condition} load.",
    "Regulatory requirement: {regulation} mandates {requirement} by {deadline}.",
]

_NAMES = ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "Grace", "Henry"]
_FEATURES = ["authentication", "search", "notifications", "billing", "dashboard", "API", "cache"]
_PLATFORMS = ["macOS", "Windows", "Linux", "iOS", "Android", "Docker"]
_CHANNELS = ["email", "Slack", "SMS", "phone", "chat", "GitHub"]
_LANGS = ["Python", "TypeScript", "Go", "Rust", "Java", "C++"]
_LEVELS = ["beginner", "intermediate", "advanced", "expert"]
_TIMEZONES = ["US/Pacific", "US/Eastern", "Europe/London", "Asia/Tokyo", "UTC"]
_DOMAINS = ["machine learning", "distributed systems", "frontend", "databases", "security"]
_ENTITIES = ["OpenAI", "Google", "Microsoft", "Anthropic", "Meta", "Apple", "Amazon"]
_CITIES = ["San Francisco", "New York", "London", "Tokyo", "Berlin", "Singapore"]


def _rnd_str(chars: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=chars))


def _fill(template: str) -> str:
    return template.format(
        feature=random.choice(_FEATURES),
        name=random.choice(_NAMES),
        num=random.randint(1000, 9999),
        condition=f"{_rnd_str(4)} condition",
        platform=random.choice(_PLATFORMS),
        action=f"clicks {_rnd_str(5)}",
        reason=f"misconfigured {_rnd_str(4)} setting",
        version=f"{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
        use_case=f"{_rnd_str(4)}-{_rnd_str(4)}",
        time=f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d} UTC",
        component=f"{_rnd_str(5).capitalize()}",
        responsibility=f"managing {_rnd_str(4)} state",
        pattern=random.choice(["observer", "factory", "singleton", "strategy"]),
        param=f"CORTEX_{_rnd_str(4).upper()}",
        value=random.choice(["true", "false", "1", "auto", '"strict"']),
        environment=random.choice(["production", "staging", "development"]),
        operation=random.choice(["search", "insert", "delete", "update"]),
        complexity=random.choice(["n", "n log n", "1", "log n", "n²"]),
        method=random.choice(["GET", "POST", "PUT", "DELETE", "PATCH"]),
        path=f"/{_rnd_str(4)}/{_rnd_str(4)}",
        payload="JSON body",
        response="JSON object",
        edge_case=f"{_rnd_str(3)}-edge case",
        version_old=f"{random.randint(1, 3)}.x",
        version_new=f"{random.randint(4, 6)}.0",
        step=f"run migration script {_rnd_str(4)}.py",
        preference=random.choice(["email", "Markdown output", "verbose mode"]),
        alternative=random.choice(["Slack", "HTML output", "quiet mode"]),
        agent=f"agent-{_rnd_str(4)}",
        setting=random.choice(["dark mode", "compact layout", "auto-save"]),
        channel=random.choice(_CHANNELS),
        other_channel=random.choice(_CHANNELS),
        timezone=random.choice(_TIMEZONES),
        lang=random.choice(_LANGS),
        domain=random.choice(_DOMAINS),
        level=random.choice(_LEVELS),
        entity=random.choice(_ENTITIES),
        year=random.randint(1990, 2023),
        city=random.choice(_CITIES),
        protocol=f"{_rnd_str(3).upper()}v{random.randint(1, 4)}",
        concept=f"{_rnd_str(5)}_type",
        definition=f"a structured {_rnd_str(4)} object",
        technology=random.choice(["Python", "Node.js", "PostgreSQL", "Redis", "Kafka"]),
        date=f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        source=random.choice(["RFC 7231", "IEEE 802.11", "GDPR Article 17"]),
        claim=f"{_rnd_str(4)} improves performance by {random.randint(10, 80)}%",
        confidence=random.choice(["high", "medium", "low"]),
        metric=random.choice(["latency", "throughput", "error rate", "memory usage"]),
        system=random.choice(["API gateway", "database", "cache layer"]),
        regulation=random.choice(["GDPR", "CCPA", "HIPAA", "SOC 2"]),
        requirement=f"data retention for {random.randint(1, 7)} years",
        deadline=f"2024-{random.randint(1,12):02d}-01",
    )


_ALL_TEMPLATES = (
    _SUPPORT_TEMPLATES + _TECH_DOC_TEMPLATES + _PREFERENCE_TEMPLATES + _FACT_TEMPLATES
)


def generate_memory_content(target_length: int | None = None, domain: str | None = None) -> str:
    """Generate a single realistic memory string.

    Args:
        target_length: If set, pad/trim to approximately this many characters.
        domain: 'support', 'tech', 'preference', 'fact', or None for random.
    """
    domain_map = {
        "support": _SUPPORT_TEMPLATES,
        "tech": _TECH_DOC_TEMPLATES,
        "preference": _PREFERENCE_TEMPLATES,
        "fact": _FACT_TEMPLATES,
    }
    templates = domain_map.get(domain or "", _ALL_TEMPLATES)
    base = _fill(random.choice(templates))

    if target_length is None:
        return base

    while len(base) < target_length:
        base += " " + _fill(random.choice(templates))

    return base[:target_length]


def generate_memories(
    count: int,
    agent_id: str = "stress-test",
    target_length: int | None = None,
    domain: str | None = None,
    tier: str = "warm",
    criticality: float = 0.5,
) -> list[dict]:
    """Return a list of MemoryCreate-compatible dicts."""
    return [
        {
            "content": generate_memory_content(target_length, domain),
            "agent_id": agent_id,
            "tier": tier,
            "criticality": criticality,
            "metadata": {"batch_id": str(uuid.uuid4()), "seq": i},
        }
        for i in range(count)
    ]


def generate_needle_memories(
    queries_and_answers: list[tuple[str, str]],
    agent_id: str = "stress-needle",
) -> list[dict]:
    """Create 'needle' memories with known relevance to specific queries.

    Returns list of (query, memory_dict) for ground-truth evaluation.
    """
    return [
        (
            query,
            {
                "content": answer,
                "agent_id": agent_id,
                "tier": "hot",
                "criticality": 1.0,
                "metadata": {"needle": True, "query": query},
            },
        )
        for query, answer in queries_and_answers
    ]


def generate_contradiction_pairs(count: int, agent_id: str = "stress-test") -> list[tuple[dict, dict]]:
    """Generate (mem_A, mem_B) pairs where A and B say opposite things."""
    pairs = [
        (
            "User prefers communication via email and explicitly requested email updates.",
            "User said they hate email and want all communications via Slack only.",
        ),
        (
            "The system should use PostgreSQL as the primary database.",
            "Management decision: migrate all data to MongoDB, no PostgreSQL allowed.",
        ),
        (
            "Deployment policy: always require two approvals before production push.",
            "New policy from CTO: single approval is sufficient for production deployments.",
        ),
        (
            "User timezone is US/Pacific (UTC-8).",
            "User confirmed they are in Europe/London (UTC+0).",
        ),
        (
            "API rate limit for this client is 100 requests per minute.",
            "API rate limit was upgraded to 10,000 requests per minute for premium tier.",
        ),
    ]
    result = []
    cycled = cycle(pairs)
    for _ in range(count):
        a_text, b_text = next(cycled)
        suffix = f" [{uuid.uuid4().hex[:6]}]"
        result.append((
            {"content": a_text + suffix, "agent_id": agent_id, "tier": "warm", "criticality": 0.5, "metadata": {}},
            {"content": b_text + suffix, "agent_id": agent_id, "tier": "warm", "criticality": 0.5, "metadata": {}},
        ))
    return result
