"""Demo adapter with synthetic data for impressive demos.

Generates a realistic memory store with planted ghost tokens,
contradictions, stale memories, and a mix of MAS scores.
"""

from __future__ import annotations

import hashlib
import math
import random
from datetime import datetime, timedelta
from typing import Any

from cx.adapters.base import MemoryAdapter, MemoryRecord

# ── Seed data ─────────────────────────────────────────────────────────
# Three collections that tell a compelling e-commerce support bot story.

_USER_PREFS = [
    ("Preferred name is Alex", 0.72, False, False, 2, "onboarding_form"),
    ("Ships to 742 Evergreen Terrace, Springfield", 0.81, False, False, 8, "address_update"),
    ("Timezone is EST (UTC-5)", 0.03, True, False, 0, "signup_flow"),
    ("Likes the color blue", 0.01, True, False, 0, "onboarding_v1"),
    ("General greeting preference: casual", 0.02, True, False, 0, "chat_settings"),
    ("Payment method: Visa ending 4242", 0.65, False, False, 5, "billing_settings"),
    ("Email notifications enabled", 0.04, True, False, 0, "notification_prefs"),
    ("Preferred language: English", 0.00, True, False, 0, "signup_flow"),
    ("Customer since January 2024", 0.55, False, False, 3, "crm_import"),
    ("Loyalty tier: Gold", 0.78, False, False, 12, "rewards_system"),
    ("Birthday is March 15", 0.12, False, False, 1, "profile_update"),
    ("Prefers phone support over chat", 0.01, True, False, 0, "support_prefs"),
]

_PRODUCT_DOCS = [
    ("All orders ship express (2-day delivery)", 0.87, False, True, 19, "onboarding_v1.pdf"),
    ("Standard shipping is 5-7 business days", 0.34, False, True, 4, "shipping_policy_v3.pdf"),
    ("Returns accepted within 30 days with receipt", 0.91, False, False, 22, "returns_policy.pdf"),
    ("Free shipping on orders over $50", 0.73, False, False, 15, "promotions.pdf"),
    ("Holiday hours: closed Dec 25, Jan 1", 0.08, True, False, 0, "hr_calendar"),
    ("Product warranty: 1 year limited", 0.82, False, False, 11, "warranty_docs.pdf"),
    ("Express upgrade available for $9.99", 0.69, False, False, 7, "pricing_sheet.pdf"),
    ("Refund processed within 5 business days", 0.44, False, True, 6, "returns_policy.pdf"),
    ("Refund takes 10-14 business days", 0.38, False, True, 3, "returns_policy_old.pdf"),
    ("Size chart: S=34, M=38, L=42, XL=46 inches", 0.56, False, False, 9, "product_specs.pdf"),
    ("Gift wrapping available for $4.99", 0.15, False, False, 1, "services_catalog.pdf"),
    ("Bulk discount: 10% off 5+ items", 0.61, False, False, 6, "pricing_sheet.pdf"),
    ("Price match guarantee within 14 days", 0.77, False, False, 10, "price_policy.pdf"),
    ("All sales final during clearance events", 0.45, False, True, 5, "clearance_policy.pdf"),
    ("Clearance items can be returned within 7 days", 0.29, False, True, 2, "clearance_policy_v2.pdf"),
]

_CONVERSATION_HISTORY = [
    ("User asked about order #1847 status on Feb 3", 0.42, False, False, 2, "chat_log"),
    ("Resolved shipping delay complaint on Jan 28", 0.38, False, False, 1, "ticket_4521"),
    ("User requested size exchange for item SKU-2847", 0.35, False, False, 1, "ticket_4590"),
    ("Mentioned they're shopping for a birthday gift", 0.22, False, False, 1, "chat_log"),
    ("Asked about loyalty points balance twice", 0.51, False, False, 3, "chat_log"),
    ("Complained about slow website on mobile", 0.03, True, False, 0, "feedback_form"),
    ("Said 'thanks, you're helpful' at end of chat", 0.00, True, False, 0, "chat_log"),
    ("Inquired about B2B pricing for office supplies", 0.66, False, False, 4, "chat_log"),
    ("Reported broken link on FAQ page", 0.01, True, False, 0, "feedback_form"),
]

# Contradiction pairs (memory content A, memory content B, explanation)
_CONTRADICTIONS = [
    (
        "All orders ship express (2-day delivery)",
        "Standard shipping is 5-7 business days",
        "Shipping time conflict: onboarding_v1 says express, current policy says standard.",
    ),
    (
        "Refund processed within 5 business days",
        "Refund takes 10-14 business days",
        "Refund timeline conflict: current vs. old returns policy.",
    ),
    (
        "All sales final during clearance events",
        "Clearance items can be returned within 7 days",
        "Clearance returns conflict: old policy says final, new policy allows 7-day returns.",
    ),
]


def _make_embedding(content: str, dim: int = 64) -> list[float]:
    """Generate a deterministic pseudo-embedding from content."""
    h = hashlib.sha256(content.encode()).hexdigest()
    values = []
    for i in range(0, min(len(h), dim * 2), 2):
        byte_val = int(h[i:i + 2], 16)
        values.append((byte_val / 255.0) * 2 - 1)  # normalize to [-1, 1]
    while len(values) < dim:
        values.append(0.0)
    # L2 normalize
    norm = math.sqrt(sum(v * v for v in values))
    if norm > 0:
        values = [v / norm for v in values]
    return values


class DemoAdapter(MemoryAdapter):
    """Synthetic memory store for demo/showcase purposes."""

    def __init__(self, seed: int = 42, **_: Any) -> None:
        self._rng = random.Random(seed)
        self._memories: dict[str, MemoryRecord] = {}
        self._archived: set[str] = set()
        self._generate()

    def _generate(self) -> None:
        now = datetime.now()
        counter = 0

        collections = [
            ("user_preferences", _USER_PREFS),
            ("product_docs", _PRODUCT_DOCS),
            ("conversation_history", _CONVERSATION_HISTORY),
        ]

        for collection, items in collections:
            for content, mas, ghost, contradiction, access_count, source in items:
                counter += 1
                mid = f"mem_{counter:04d}"
                days_ago = self._rng.randint(1, 120)
                created = now - timedelta(days=days_ago)

                if ghost:
                    last_access = created  # never accessed again
                    access_count = 0
                elif access_count > 0:
                    last_access = now - timedelta(days=self._rng.randint(0, 7))
                else:
                    last_access = now - timedelta(days=self._rng.randint(30, 90))

                # Source update timestamps (for staleness detection)
                source_updated = None
                if source.endswith(".pdf"):
                    source_updated = now - timedelta(days=self._rng.randint(0, 45))

                self._memories[mid] = MemoryRecord(
                    id=mid,
                    content=content,
                    collection=collection,
                    embedding=_make_embedding(content),
                    metadata={
                        "ghost": ghost,
                        "contradiction": contradiction,
                    },
                    created_at=created,
                    last_accessed=last_access,
                    access_count=access_count,
                    source=source,
                    source_updated_at=source_updated,
                    mas_score=mas,
                    mas_history=[
                        max(0.0, min(1.0, mas + self._rng.gauss(0, 0.05)))
                        for _ in range(10)
                    ],
                )

        # Add some extra filler memories to reach ~100
        filler_contents = [
            "User prefers dark mode interface",
            "Account created via Google OAuth",
            "Subscribed to weekly newsletter",
            "Opted out of SMS notifications",
            "Browser: Chrome 120 on macOS",
            "Last login from IP 192.168.1.x",
            "Cart abandonment: 3 items on Jan 15",
            "Viewed category: Electronics (5 times)",
            "Clicked promotion banner: Winter Sale",
            "Search history: 'wireless headphones'",
            "Search history: 'laptop stand'",
            "Wishlist: Bluetooth speaker SKU-1122",
            "Previous order: headphones, $49.99",
            "Previous order: USB-C cable, $12.99",
            "Previous order: laptop stand, $34.99",
            "Support satisfaction: 4/5 stars",
            "Agent note: VIP customer, prioritize",
            "Delivery preference: leave at door",
            "Billing address same as shipping",
            "Two-factor auth enabled",
            "API key last rotated 45 days ago",
            "Webhook endpoint registered",
            "Custom field: department = Engineering",
            "Tag: early-adopter",
            "Tag: high-value",
            "Segment: power-user",
            "Funnel stage: retained",
            "NPS score: 8 (promoter)",
            "Churn risk: low",
            "Lifetime value: $847",
            "Avg order value: $42.35",
            "Session count: 127",
            "Feature flag: new-checkout = true",
            "A/B test: pricing-v2 = variant-B",
            "Locale: en-US",
            "Currency: USD",
            "Referral source: Twitter",
            "First touch: blog post on AI agents",
            "Attribution: organic search",
            "Device: iPhone 15 Pro",
        ]

        for i, content in enumerate(filler_contents):
            counter += 1
            mid = f"mem_{counter:04d}"
            mas = round(self._rng.uniform(0.0, 0.5), 2)
            days_ago = self._rng.randint(5, 90)
            created = now - timedelta(days=days_ago)
            last_access = now - timedelta(days=self._rng.randint(0, 60))

            self._memories[mid] = MemoryRecord(
                id=mid,
                content=content,
                collection=self._rng.choice(["user_preferences", "conversation_history", "analytics"]),
                embedding=_make_embedding(content),
                metadata={"ghost": mas < 0.05, "contradiction": False},
                created_at=created,
                last_accessed=last_access,
                access_count=self._rng.randint(0, 8),
                source="system",
                mas_score=mas,
                mas_history=[
                    max(0.0, min(1.0, mas + self._rng.gauss(0, 0.03)))
                    for _ in range(10)
                ],
            )

    # ── Interface implementation ──────────────────────────────────────

    def connect(self) -> str:
        return f"Demo Store ({len(self._memories)} memories, {len(self.list_collections())} collections)"

    def list_memories(self, collection: str | None = None) -> list[MemoryRecord]:
        mems = [m for m in self._memories.values() if m.id not in self._archived]
        if collection:
            mems = [m for m in mems if m.collection == collection]
        return mems

    def get_memory(self, memory_id: str) -> MemoryRecord | None:
        if memory_id in self._archived:
            return None
        return self._memories.get(memory_id)

    def list_collections(self) -> list[str]:
        return sorted({m.collection for m in self._memories.values() if m.id not in self._archived})

    def get_embeddings(self, memory_ids: list[str]) -> dict[str, list[float]]:
        result = {}
        for mid in memory_ids:
            mem = self._memories.get(mid)
            if mem and mem.embedding:
                result[mid] = mem.embedding
        return result

    def archive_memory(self, memory_id: str) -> bool:
        if memory_id in self._memories:
            self._archived.add(memory_id)
            return True
        return False

    def delete_memory(self, memory_id: str) -> bool:
        if memory_id in self._memories:
            del self._memories[memory_id]
            self._archived.discard(memory_id)
            return True
        return False

    def update_memory(self, memory_id: str, content: str) -> bool:
        if mem := self._memories.get(memory_id):
            mem.content = content
            mem.embedding = _make_embedding(content)
            return True
        return False

    def get_contradictions(self) -> list[dict]:
        """Return planted contradiction pairs."""
        results = []
        memories = self.list_memories()
        content_to_id = {m.content: m.id for m in memories}

        for content_a, content_b, explanation in _CONTRADICTIONS:
            id_a = content_to_id.get(content_a)
            id_b = content_to_id.get(content_b)
            if id_a and id_b:
                mem_a = self._memories[id_a]
                mem_b = self._memories[id_b]
                results.append({
                    "memory_a": {"id": id_a, "content": content_a, "source": mem_a.source, "mas": mem_a.mas_score},
                    "memory_b": {"id": id_b, "content": content_b, "source": mem_b.source, "mas": mem_b.mas_score},
                    "explanation": explanation,
                })
        return results
