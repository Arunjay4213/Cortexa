"""Scenario 6: Retrieval Noise Stress Test.

Tests K=5, 10, 20 noisy retrieval results with hallucination buried in noise.
The core challenge: can CAMA find the culprit when surrounded by many
topically similar but irrelevant memories?
"""

from datetime import datetime, timedelta

_now = datetime(2025, 10, 1)
_old = _now - timedelta(days=180)


def _make_noise_memories(topic: str, n: int, start_id: int = 0) -> list[dict]:
    """Generate n topically adjacent but irrelevant memories."""
    noise_templates = {
        "product_pricing": [
            "Widget Lite costs $24.99.",
            "Widget Max costs $79.99.",
            "Widget Mini costs $14.99.",
            "Widget Ultra costs $129.99.",
            "Widget Basic costs $19.99.",
            "Widget Plus costs $54.99.",
            "Widget Enterprise costs $299.99.",
            "Widget Starter Pack costs $39.99.",
            "Widget Accessories Bundle costs $34.99.",
            "Widget Extended Warranty costs $49.99.",
            "Widget Premium Case costs $29.99.",
            "Widget Screen Protector costs $9.99.",
            "Widget Charging Dock costs $44.99.",
            "Widget Travel Case costs $19.99.",
            "Widget Desktop Stand costs $24.99.",
            "Widget Wall Mount costs $15.99.",
            "Widget Cleaning Kit costs $12.99.",
            "Widget Replacement Tips (5-pack) costs $7.99.",
            "Widget Bluetooth Adapter costs $19.99.",
            "Widget USB-C Cable costs $11.99.",
        ],
    }
    templates = noise_templates.get(topic, noise_templates["product_pricing"])
    mems = []
    for i in range(n):
        mems.append({
            "id": f"noise_{start_id + i}",
            "content": templates[i % len(templates)],
            "created_at": _old.isoformat(),
        })
    return mems


# Core memories (always present)
_core = [
    {"id": "core_product", "content": "Widget Pro costs $49.99.", "created_at": _old.isoformat()},
    {"id": "core_warranty", "content": "Widget Pro has a 2-year warranty.", "created_at": _old.isoformat()},
    {"id": "core_rating", "content": "Widget Pro has a 4.5-star rating with 2,340 reviews.", "created_at": _old.isoformat()},
]

# Poison memory
_poison = [
    {"id": "poison_price", "content": "Widget Pro costs $199.99 for the premium edition.", "created_at": _old.isoformat()},
]

# Ghost memories (truly irrelevant)
_ghosts = [
    {"id": "ghost_weather", "content": "Today's weather in Austin: 85F, sunny.", "created_at": _old.isoformat()},
    {"id": "ghost_recipe", "content": "Classic pancake recipe: 1 cup flour, 1 egg, 1 cup milk.", "created_at": _old.isoformat()},
    {"id": "ghost_trivia", "content": "The speed of light is approximately 299,792 km/s.", "created_at": _old.isoformat()},
]

# K=5 scenario: minimal noise
_k5_memories = _core + _poison + _ghosts + _make_noise_memories("product_pricing", 5, start_id=100)
_k5_ghost_ids = ["ghost_weather", "ghost_recipe", "ghost_trivia"] + [f"noise_{100+i}" for i in range(5)]

# K=10 scenario: moderate noise
_k10_memories = _core + _poison + _ghosts + _make_noise_memories("product_pricing", 10, start_id=200)
_k10_ghost_ids = ["ghost_weather", "ghost_recipe", "ghost_trivia"] + [f"noise_{200+i}" for i in range(10)]

# K=20 scenario: heavy noise
_k20_memories = _core + _poison + _ghosts + _make_noise_memories("product_pricing", 20, start_id=300)
_k20_ghost_ids = ["ghost_weather", "ghost_recipe", "ghost_trivia"] + [f"noise_{300+i}" for i in range(20)]

SCENARIO = {
    "name": "Retrieval Noise (K=5/10/20)",
    "domain": "retrieval_noise",
    "memories": _k20_memories,  # Use heaviest config for the scenario
    "queries": [
        {
            "query": "How much does Widget Pro cost?",
            "response": "Widget Pro costs $179.99 for the premium edition.",
            "ground_truth": {
                "expected_culprit": "poison_price",
                "expected_ghosts": _k20_ghost_ids,
                "expected_contradictions": [("core_product", "poison_price")],
                "expected_stale": [],
            },
        },
        {
            "query": "Tell me about Widget Pro pricing.",
            "response": "The Widget Pro premium edition is priced at $159.99.",
            "ground_truth": {
                "expected_culprit": "poison_price",
                "expected_ghosts": _k20_ghost_ids,
                "expected_contradictions": [("core_product", "poison_price")],
                "expected_stale": [],
            },
        },
        {
            "query": "What are Widget Pro's details?",
            "response": "Widget Pro has a 4.5-star rating and 2-year warranty. It costs $49.99.",
            "ground_truth": {
                "expected_culprit": None,
                "expected_ghosts": _k20_ghost_ids,
                "expected_contradictions": [],
                "expected_stale": [],
            },
        },
    ],
}
