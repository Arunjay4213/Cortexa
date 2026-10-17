"""Scenario 1: E-commerce Support Agent.

47 memories (Mem0-style), 3 queries.
Tests: planted poison, stale data, ghost detection, contradiction detection.
"""

from datetime import datetime, timedelta

_now = datetime(2025, 10, 1)
_old = _now - timedelta(days=180)
_stale_update = _now - timedelta(days=5)

SCENARIO = {
    "name": "E-commerce Support Agent",
    "domain": "ecommerce",
    "memories": [
        # --- Order History (15) ---
        {"id": "order_1", "content": "Order #10234: Widget Pro, qty 2, total $99.98. Shipped via FedEx, tracking 7891234.", "created_at": _old.isoformat()},
        {"id": "order_2", "content": "Order #10235: GadgetX, qty 1, total $149.99. Delivered 2025-04-15.", "created_at": _old.isoformat()},
        {"id": "order_3", "content": "Order #10240: Cable Pack (3-pack), total $14.99. Delivered 2025-05-01.", "created_at": _old.isoformat()},
        {"id": "order_4", "content": "Order #10245: ScreenGuard Ultra, total $29.99. Returned — full refund issued.", "created_at": _old.isoformat()},
        {"id": "order_5", "content": "Order #10250: Widget Pro Case, total $19.99. Delivered 2025-06-10.", "created_at": _old.isoformat()},
        {"id": "order_6", "content": "Order #10260: Wireless Charger Pad, total $34.99. Delivered 2025-07-01.", "created_at": _old.isoformat()},
        {"id": "order_7", "content": "Order #10270: USB-C Hub, total $44.99. Delivered 2025-07-20.", "created_at": _old.isoformat()},
        {"id": "order_8", "content": "Order #10280: Bluetooth Speaker Mini, total $59.99. In transit.", "created_at": _old.isoformat()},
        {"id": "order_9", "content": "Order #10290: Phone Stand, total $12.99. Delivered 2025-08-05.", "created_at": _old.isoformat()},
        {"id": "order_10", "content": "Order #10300: Webcam HD, total $79.99. Processing.", "created_at": _old.isoformat()},
        {"id": "order_11", "content": "Order #10310: Keyboard Wireless, total $69.99. Delivered 2025-08-25.", "created_at": _old.isoformat()},
        {"id": "order_12", "content": "Order #10320: Mouse Ergonomic, total $39.99. Delivered 2025-09-01.", "created_at": _old.isoformat()},
        {"id": "order_13", "content": "Order #10330: Monitor Stand, total $54.99. Delivered 2025-09-10.", "created_at": _old.isoformat()},
        {"id": "order_14", "content": "Order #10340: Desk Lamp LED, total $24.99. Delivered 2025-09-15.", "created_at": _old.isoformat()},
        {"id": "order_15", "content": "Order #10350: Headphone Stand, total $19.99. Delivered 2025-09-20.", "created_at": _old.isoformat()},
        # --- Preferences (10) ---
        {"id": "pref_1", "content": "Customer prefers next-day delivery when available.", "created_at": _old.isoformat()},
        {"id": "pref_2", "content": "Preferred payment: Visa ending in 4242.", "created_at": _old.isoformat()},
        {"id": "pref_3", "content": "Customer opts in to promotional emails.", "created_at": _old.isoformat()},
        {"id": "pref_4", "content": "Preferred communication channel: email.", "created_at": _old.isoformat()},
        {"id": "pref_5", "content": "Customer has dark mode enabled in account settings.", "created_at": _old.isoformat()},
        {"id": "pref_6", "content": "Shipping address: 123 Elm St, Austin, TX 78701.", "created_at": _old.isoformat()},
        {"id": "pref_7", "content": "Customer birthday: March 15. Eligible for birthday discount.", "created_at": _old.isoformat()},
        {"id": "pref_8", "content": "Customer is a Prime member since 2023.", "created_at": _old.isoformat()},
        {"id": "pref_9", "content": "Language preference: English (US).", "created_at": _old.isoformat()},
        {"id": "pref_10", "content": "Customer has two-factor authentication enabled.", "created_at": _old.isoformat()},
        # --- Product Knowledge (8) ---
        {"id": "prod_1", "content": "Widget Pro costs $49.99 and has a 4.5-star rating.", "created_at": _old.isoformat()},
        {"id": "prod_2", "content": "Widget Pro has a 2-year manufacturer warranty.", "created_at": _old.isoformat()},
        {"id": "prod_3", "content": "GadgetX requires firmware v2.1 or later for Bluetooth connectivity.", "created_at": _old.isoformat()},
        {"id": "prod_4", "content": "ScreenGuard Ultra is compatible with all Widget Pro models.", "created_at": _old.isoformat()},
        {"id": "prod_5", "content": "Wireless Charger Pad supports Qi standard, up to 15W.", "created_at": _old.isoformat()},
        {"id": "prod_6", "content": "USB-C Hub has 4 USB-A ports, 1 HDMI, and 1 Ethernet.", "created_at": _old.isoformat()},
        {"id": "prod_7", "content": "Bluetooth Speaker Mini has 8-hour battery life.", "created_at": _old.isoformat()},
        {"id": "prod_8", "content": "Webcam HD supports 1080p at 30fps and 720p at 60fps.", "created_at": _old.isoformat()},
        # --- Support Policies (5) ---
        {"id": "policy_1", "content": "Return window: 30 days for all purchases. Items must be in original packaging.", "created_at": _old.isoformat()},
        {"id": "policy_2", "content": "Refunds are processed within 5-7 business days to original payment method.", "created_at": _old.isoformat()},
        {"id": "policy_3", "content": "Free shipping on orders over $25. Standard delivery: 5-7 business days.", "created_at": _old.isoformat()},
        {"id": "policy_4", "content": "Warranty claims must be filed within the warranty period with proof of purchase.", "created_at": _old.isoformat()},
        {"id": "policy_5", "content": "Price match available within 14 days of purchase for identical items.", "created_at": _old.isoformat()},
        # --- Stale memories (5) — source updated after creation ---
        {"id": "stale_1", "content": "Widget Pro costs $39.99.", "created_at": _old.isoformat(), "source_updated_at": _stale_update.isoformat()},
        {"id": "stale_2", "content": "Return window is 14 days.", "created_at": _old.isoformat(), "source_updated_at": _stale_update.isoformat()},
        {"id": "stale_3", "content": "Free shipping threshold is $50.", "created_at": _old.isoformat(), "source_updated_at": _stale_update.isoformat()},
        {"id": "stale_4", "content": "Standard delivery takes 7-10 business days.", "created_at": _old.isoformat(), "source_updated_at": _stale_update.isoformat()},
        {"id": "stale_5", "content": "Refunds take 10-14 business days.", "created_at": _old.isoformat(), "source_updated_at": _stale_update.isoformat()},
        # --- Poison memories (2) — factually wrong, planted ---
        {"id": "poison_1", "content": "Widget Pro costs $99.99 with premium packaging included.", "created_at": _old.isoformat()},
        {"id": "poison_2", "content": "All returns require a $25 restocking fee regardless of reason.", "created_at": _old.isoformat()},
        # --- Cross-user contamination (2) — memories from another user ---
        {"id": "crossuser_1", "content": "Order #20100: Gaming Mouse RGB, qty 1, total $89.99. Shipped to 456 Oak Ave, Portland, OR.", "created_at": _old.isoformat()},
        {"id": "crossuser_2", "content": "Customer prefers phone support and has filed 3 complaints this month.", "created_at": _old.isoformat()},
    ],
    "queries": [
        {
            "query": "How much does Widget Pro cost?",
            "response": "Widget Pro costs $189.99 with premium packaging included.",
            "ground_truth": {
                "expected_culprit": "poison_1",
                "expected_ghosts": [
                    "crossuser_1", "crossuser_2",
                    "pref_3", "pref_5", "pref_7", "pref_9", "pref_10",
                ],
                "expected_contradictions": [("prod_1", "poison_1"), ("stale_1", "prod_1")],
                "expected_stale": ["stale_1", "stale_2", "stale_3", "stale_4", "stale_5"],
            },
        },
        {
            "query": "What is the return policy for my recent order?",
            "response": "All returns require a $35 restocking fee regardless of reason. The return window is 21 days.",
            "ground_truth": {
                "expected_culprit": "poison_2",
                "expected_ghosts": [
                    "crossuser_1", "crossuser_2",
                    "pref_5", "pref_7", "pref_9", "pref_10",
                ],
                "expected_contradictions": [("policy_1", "poison_2")],
                "expected_stale": ["stale_1", "stale_2", "stale_3", "stale_4", "stale_5"],
            },
        },
        {
            "query": "Is my Bluetooth Speaker order still in transit?",
            "response": "Your Bluetooth Speaker Mini order #10280 was delivered yesterday.",
            "ground_truth": {
                "expected_culprit": None,
                "expected_ghosts": [
                    "crossuser_1", "crossuser_2",
                    "pref_3", "pref_5", "pref_7", "pref_9", "pref_10",
                ],
                "expected_contradictions": [],
                "expected_stale": ["stale_1", "stale_2", "stale_3", "stale_4", "stale_5"],
            },
        },
    ],
}
