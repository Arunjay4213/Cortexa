"""Shared test fixtures — synthetic e-commerce dataset for the shipping date story."""

from datetime import datetime, timedelta

import pytest

from cortexa.engine.models import Memory


@pytest.fixture
def now():
    return datetime(2026, 3, 24, 12, 0, 0)


@pytest.fixture
def memories(now):
    """76-memory synthetic dataset for a fake e-commerce support agent.

    Key planted issues:
    - mem_2847: STALE — shipping policy changed 6 weeks ago
    - mem_1203: GHOST — "user prefers blue color theme" (irrelevant to shipping)
    - mem_0089: GHOST — "returns accepted within 30 days" (ghost for shipping queries)
    - mem_0044 vs mem_0055: CONTRADICTION — conflicting free shipping thresholds
    """
    three_months_ago = now - timedelta(days=90)
    six_weeks_ago = now - timedelta(weeks=6)
    two_months_ago = now - timedelta(days=60)

    planted = [
        # The hero stale memory — shipping policy changed
        Memory(
            id="mem_2847",
            content="All orders ship express (2-day delivery)",
            source="shipping_policy.md",
            source_updated_at=six_weeks_ago,  # source updated AFTER creation
            created_at=three_months_ago,
            last_accessed=now - timedelta(hours=1),
            access_count=142,
        ),
        # Ghost: irrelevant to shipping queries
        Memory(
            id="mem_1203",
            content="User prefers blue color theme for dashboard",
            source="user_preferences",
            created_at=two_months_ago,
            last_accessed=now - timedelta(days=45),
            access_count=3,
        ),
        # Ghost for shipping queries (but valid for returns queries)
        Memory(
            id="mem_0089",
            content="Returns accepted within 30 days of purchase",
            source="returns_policy.md",
            created_at=three_months_ago,
            last_accessed=now - timedelta(days=2),
            access_count=87,
        ),
        # Contradiction pair: different free shipping thresholds
        Memory(
            id="mem_0044",
            content="Free shipping on orders over $50",
            source="promotions.md",
            created_at=two_months_ago,
            last_accessed=now - timedelta(days=1),
            access_count=55,
        ),
        Memory(
            id="mem_0055",
            content="Free shipping on orders over $75, no minimum for Prime members",
            source="shipping_policy.md",
            created_at=three_months_ago - timedelta(days=10),
            last_accessed=now - timedelta(days=1),
            access_count=63,
        ),
        # Normal shipping memories
        Memory(
            id="mem_0010",
            content="Standard shipping takes 5-7 business days",
            source="shipping_policy.md",
            created_at=now - timedelta(days=10),
            last_accessed=now - timedelta(hours=3),
            access_count=200,
        ),
        Memory(
            id="mem_0011",
            content="Express shipping costs $9.99 and takes 2 business days",
            source="shipping_policy.md",
            created_at=now - timedelta(days=10),
            last_accessed=now - timedelta(hours=5),
            access_count=150,
        ),
        # Pricing memories
        Memory(
            id="mem_0020",
            content="The premium plan costs $49.99 per month",
            source="pricing_page",
            created_at=two_months_ago,
            last_accessed=now - timedelta(days=3),
            access_count=40,
        ),
        Memory(
            id="mem_0021",
            content="Annual billing saves 20%, bringing the price to $39.99 per month",
            source="pricing_page",
            created_at=two_months_ago,
            last_accessed=now - timedelta(days=5),
            access_count=28,
        ),
        # Account memory
        Memory(
            id="mem_0030",
            content="Password reset links expire after 24 hours",
            source="auth_docs",
            created_at=three_months_ago,
            last_accessed=now - timedelta(days=20),
            access_count=15,
        ),
    ]

    # Generate 66 more filler memories to reach 76 total
    categories = ["shipping", "returns", "pricing", "account", "product"]
    filler_content = {
        "shipping": [
            "Tracking numbers are sent via email within 24 hours of shipment",
            "International shipping available to 40+ countries",
            "Signature required for orders over $200",
            "Holiday shipping cutoff is December 18 for standard delivery",
            "PO Box addresses only support USPS shipping methods",
            "Alaska and Hawaii orders may take 2-3 additional business days",
            "Same-day delivery available in select metro areas",
            "Shipping confirmation includes estimated delivery date",
            "Package insurance included for orders over $100",
            "Bulk orders over 50 units qualify for freight shipping",
            "Weekend delivery available with premium shipping option",
            "Carbon-neutral shipping option available at checkout",
            "Delivery instructions can be added during checkout",
        ],
        "returns": [
            "Refunds processed within 5-7 business days after receipt",
            "Original shipping costs are non-refundable",
            "Exchanges available for different size or color",
            "Return shipping label included in every order",
            "Opened electronics have a 15-day return window",
            "Gift returns receive store credit instead of refund",
            "Defective items can be returned within 90 days",
            "Return tracking available through the customer portal",
            "Restocking fee of 15% applies to opened items over $500",
            "Items must be in original packaging for full refund",
            "Holiday purchases have extended return window until Jan 31",
            "Personalized items are final sale and cannot be returned",
            "Free return shipping on defective or incorrect items",
        ],
        "pricing": [
            "Student discount of 15% available with valid .edu email",
            "Enterprise pricing available for teams of 10+",
            "First month free for new subscribers",
            "Price match guarantee within 30 days of purchase",
            "Referral bonus: $10 credit for each successful referral",
            "Volume discounts: 10% off orders of 25+ units",
            "Seasonal sale typically offers 25-30% off select items",
            "Loyalty points: earn 1 point per dollar spent",
            "Bundle pricing: save 15% when buying 3 or more",
            "Early bird pricing: 20% off pre-orders",
            "Military discount: 10% off all orders with verification",
            "Price adjustments honored within 14 days of purchase",
            "Clearance items are final sale at 50-70% off",
        ],
        "account": [
            "Two-factor authentication available via SMS or authenticator app",
            "Account data can be exported in CSV or JSON format",
            "Email preferences can be managed in account settings",
            "Inactive accounts are deactivated after 12 months",
            "Multiple shipping addresses can be saved to account",
            "Order history available for the past 3 years",
            "Guest checkout available without creating an account",
            "Account deletion requests processed within 30 days",
            "Saved payment methods encrypted with AES-256",
            "Login sessions expire after 30 days of inactivity",
            "Account sharing is not permitted under Terms of Service",
            "Notification preferences: email, SMS, or push notifications",
            "Profile photo upload supports JPG and PNG formats",
        ],
        "product": [
            "All products come with a 1-year manufacturer warranty",
            "Product reviews must be from verified purchasers",
            "Size chart available on each product detail page",
            "Product availability updated in real-time",
            "Wish list items preserved for 6 months",
            "Back-in-stock notifications available via email",
            "Product comparison tool available for up to 4 items",
            "360-degree product view available on select items",
            "Material sourcing information in product details",
            "Care instructions included with every clothing item",
            "Product dimensions listed in both inches and centimeters",
            "Color accuracy may vary slightly from screen display",
            "Limited edition items are first-come, first-served",
            "Pre-orders ship on the announced release date",
        ],
    }

    idx = 100
    for cat in categories:
        for content in filler_content[cat]:
            days_ago = (idx % 80) + 5
            planted.append(
                Memory(
                    id=f"mem_{idx:04d}",
                    content=content,
                    source=f"{cat}_docs",
                    created_at=now - timedelta(days=days_ago),
                    last_accessed=now - timedelta(days=(idx % 20)),
                    access_count=idx % 50,
                )
            )
            idx += 1

    return planted[:76]  # exactly 76


@pytest.fixture
def shipping_memories(memories):
    """Just the memories relevant to a shipping query."""
    shipping_ids = {"mem_2847", "mem_1203", "mem_0089", "mem_0010", "mem_0011"}
    return [m for m in memories if m.id in shipping_ids]


@pytest.fixture
def shipping_response():
    return "Your order arrives Thursday by 2pm"


@pytest.fixture
def shipping_query():
    return "When does my order arrive?"


@pytest.fixture
def pricing_response():
    return "The premium plan costs $49.99 per month, with free shipping on orders over $50"


@pytest.fixture
def contradiction_memories(memories):
    """The two memories that contradict each other on free shipping threshold."""
    ids = {"mem_0044", "mem_0055"}
    return [m for m in memories if m.id in ids]
