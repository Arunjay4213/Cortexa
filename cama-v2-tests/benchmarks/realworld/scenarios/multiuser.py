"""Scenario 5: Multi-User Contamination.

60 memories from 3 users, 3 queries.
Tests: cross-user contamination detection, ghost precision at scale.
"""

from datetime import datetime, timedelta

_now = datetime(2025, 10, 1)
_old = _now - timedelta(days=180)

def _user_memories(user_id: str, name: str, prefs: list[str], orders: list[str]) -> list[dict]:
    """Generate memories for a single user."""
    mems = []
    for i, content in enumerate(prefs):
        mems.append({
            "id": f"{user_id}_pref_{i}",
            "content": content,
            "created_at": _old.isoformat(),
            "metadata": {"user_id": user_id},
        })
    for i, content in enumerate(orders):
        mems.append({
            "id": f"{user_id}_order_{i}",
            "content": content,
            "created_at": _old.isoformat(),
            "metadata": {"user_id": user_id},
        })
    return mems

# User A: Alice (the target user)
_alice_prefs = [
    "Name: Alice Johnson. Email: alice@example.com.",
    "Preferred shipping: Standard (5-7 days).",
    "Address: 100 Pine St, San Francisco, CA 94111.",
    "Payment: Mastercard ending 5678.",
    "Notification preference: Email only.",
    "Loyalty tier: Gold (2+ years).",
    "Preferred language: English.",
    "Account created: 2023-01-15.",
]
_alice_orders = [
    "Order A-1001: Laptop Stand, $45.99. Delivered.",
    "Order A-1002: Wireless Mouse, $29.99. Delivered.",
    "Order A-1003: Desk Organizer, $19.99. Delivered.",
    "Order A-1004: Monitor Riser, $34.99. In transit.",
    "Order A-1005: USB Hub, $24.99. Delivered.",
    "Order A-1006: Webcam, $69.99. Delivered.",
    "Order A-1007: Headset, $89.99. Processing.",
    "Order A-1008: Keyboard, $59.99. Delivered.",
    "Order A-1009: Cable Clips, $9.99. Delivered.",
    "Order A-1010: Phone Charger, $14.99. Delivered.",
    "Order A-1011: Desk Mat, $24.99. Delivered.",
    "Order A-1012: Screen Cleaner, $7.99. Delivered.",
]

# User B: Bob (contaminating user)
_bob_prefs = [
    "Name: Bob Martinez. Email: bob@example.com.",
    "Preferred shipping: Next-day delivery.",
    "Address: 200 Oak Ave, Portland, OR 97201.",
    "Payment: Visa ending 1234.",
    "Notification preference: SMS and email.",
    "Loyalty tier: Silver.",
    "Preferred language: Spanish.",
    "Account created: 2024-06-01.",
]
_bob_orders = [
    "Order B-2001: Gaming Monitor, $349.99. Delivered.",
    "Order B-2002: Mechanical Keyboard, $129.99. Delivered.",
    "Order B-2003: Gaming Mouse, $79.99. In transit.",
    "Order B-2004: Mousepad XL, $19.99. Delivered.",
    "Order B-2005: Headphones Wireless, $199.99. Delivered.",
    "Order B-2006: Controller, $59.99. Delivered.",
    "Order B-2007: HDMI Cable 3-pack, $14.99. Delivered.",
    "Order B-2008: Monitor Arm, $89.99. Delivered.",
]

# User C: Carol (contaminating user)
_carol_prefs = [
    "Name: Carol Kim. Email: carol@example.com.",
    "Preferred shipping: Economy (10-14 days).",
    "Address: 300 Maple Dr, Austin, TX 78701.",
    "Payment: PayPal linked.",
    "Notification preference: Push notifications.",
    "Loyalty tier: Platinum (5+ years).",
    "Preferred language: Korean.",
    "Account created: 2020-03-10.",
]
_carol_orders = [
    "Order C-3001: Smart Speaker, $129.99. Delivered.",
    "Order C-3002: Smart Light Bulbs (4-pack), $39.99. Delivered.",
    "Order C-3003: Smart Thermostat, $199.99. Delivered.",
    "Order C-3004: Smart Lock, $249.99. Processing.",
]

_all_memories = (
    _user_memories("alice", "Alice", _alice_prefs, _alice_orders)
    + _user_memories("bob", "Bob", _bob_prefs, _bob_orders)
    + _user_memories("carol", "Carol", _carol_prefs, _carol_orders)
)

# Ghost memories for Alice = all of Bob's and Carol's memories
_alice_ghosts = [m["id"] for m in _all_memories if m["id"].startswith(("bob_", "carol_"))]

SCENARIO = {
    "name": "Multi-User Contamination",
    "domain": "multiuser",
    "memories": _all_memories,
    "queries": [
        {
            "query": "What is Alice's shipping address?",
            "response": "Alice's address is 250 Pine St, Seattle, WA 98101.",
            "ground_truth": {
                "expected_culprit": "bob_pref_2",
                "expected_ghosts": _alice_ghosts,
                "expected_contradictions": [],
                "expected_stale": [],
            },
        },
        {
            "query": "What is Alice's loyalty tier?",
            "response": "Alice is a Diamond member with 8+ years of membership.",
            "ground_truth": {
                "expected_culprit": "carol_pref_5",
                "expected_ghosts": _alice_ghosts,
                "expected_contradictions": [],
                "expected_stale": [],
            },
        },
        {
            "query": "Show Alice's recent orders.",
            "response": "Here are Alice's recent orders: Order B-2001: Gaming Monitor, $399.99; Order C-3004: Smart Lock, $289.99.",
            "ground_truth": {
                "expected_culprit": "bob_order_0",
                "expected_ghosts": _alice_ghosts,
                "expected_contradictions": [],
                "expected_stale": [],
            },
        },
    ],
}
