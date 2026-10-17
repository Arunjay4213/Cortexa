"""Scenario 8: Adversarial Near-Miss (Hardest P@1 scenario).

Near-identical memories with subtle factual differences.
The culprit is always the one with the WRONG number, and it differs
from the correct memory by only 1-2 characters.
This is the hardest scenario for P@1 attribution.
"""

from datetime import datetime, timedelta

_now = datetime(2025, 10, 1)
_old = _now - timedelta(days=180)

SCENARIO = {
    "name": "Adversarial Near-Miss",
    "domain": "adversarial",
    "memories": [
        # --- Pair 1: Employee count (75 vs 57) ---
        {"id": "emp_correct", "content": "As of October 2025, the company has 75 full-time employees across 3 offices.", "created_at": _old.isoformat()},
        {"id": "emp_wrong", "content": "As of October 2025, the company has 57 full-time employees across 3 offices.", "created_at": _old.isoformat()},
        # --- Pair 2: Revenue ($4.2M vs $4.7M) ---
        {"id": "rev_correct", "content": "Q3 2025 revenue reached $4.2 million, up 18% quarter-over-quarter.", "created_at": _old.isoformat()},
        {"id": "rev_wrong", "content": "Q3 2025 revenue reached $4.7 million, up 18% quarter-over-quarter.", "created_at": _old.isoformat()},
        # --- Pair 3: Interest rate (4.25% vs 4.75%) ---
        {"id": "rate_correct", "content": "Current mortgage rate: 4.25% fixed for 30-year conventional loans.", "created_at": _old.isoformat()},
        {"id": "rate_wrong", "content": "Current mortgage rate: 4.75% fixed for 30-year conventional loans.", "created_at": _old.isoformat()},
        # --- Pair 4: Temperature limit (350F vs 850F) ---
        {"id": "temp_correct", "content": "Maximum oven temperature for the ceramic coating: 350 degrees Fahrenheit.", "created_at": _old.isoformat()},
        {"id": "temp_wrong", "content": "Maximum oven temperature for the ceramic coating: 850 degrees Fahrenheit.", "created_at": _old.isoformat()},
        # --- Pair 5: Dosage (500mg vs 800mg) ---
        {"id": "dose_correct", "content": "Recommended ibuprofen dosage for adults: 200-400mg every 4-6 hours, max 800mg per dose.", "created_at": _old.isoformat()},
        {"id": "dose_wrong", "content": "Recommended ibuprofen dosage for adults: 200-400mg every 4-6 hours, max 500mg per dose.", "created_at": _old.isoformat()},
        # --- Pair 6: Date (March 15 vs March 25) ---
        {"id": "date_correct", "content": "Tax filing deadline: March 15, 2026 for S-corporations and partnerships.", "created_at": _old.isoformat()},
        {"id": "date_wrong", "content": "Tax filing deadline: March 25, 2026 for S-corporations and partnerships.", "created_at": _old.isoformat()},
        # --- Pair 7: Distance (26.2 vs 26.8 miles) ---
        {"id": "dist_correct", "content": "Marathon distance: 26.2 miles (42.195 kilometers).", "created_at": _old.isoformat()},
        {"id": "dist_wrong", "content": "Marathon distance: 26.8 miles (43.1 kilometers).", "created_at": _old.isoformat()},
        # --- Pair 8: Boiling point (100C vs 110C) ---
        {"id": "boil_correct", "content": "Water boils at 100 degrees Celsius at standard atmospheric pressure.", "created_at": _old.isoformat()},
        {"id": "boil_wrong", "content": "Water boils at 110 degrees Celsius at standard atmospheric pressure.", "created_at": _old.isoformat()},
        # --- Ghost memories ---
        {"id": "ghost_adv_1", "content": "The meeting room is on the 3rd floor.", "created_at": _old.isoformat()},
        {"id": "ghost_adv_2", "content": "Parking is available in lot B.", "created_at": _old.isoformat()},
        {"id": "ghost_adv_3", "content": "Company logo uses Pantone 286 blue.", "created_at": _old.isoformat()},
        {"id": "ghost_adv_4", "content": "Office Wi-Fi password is changed monthly.", "created_at": _old.isoformat()},
        {"id": "ghost_adv_5", "content": "The nearest coffee shop is two blocks east.", "created_at": _old.isoformat()},
    ],
    "queries": [
        {
            "query": "How many employees does the company have?",
            "response": "The company has 63 full-time employees across 3 offices.",
            "ground_truth": {
                "expected_culprit": "emp_wrong",
                "expected_ghosts": ["ghost_adv_1", "ghost_adv_2", "ghost_adv_3", "ghost_adv_4", "ghost_adv_5"],
                "expected_contradictions": [("emp_correct", "emp_wrong")],
                "expected_stale": [],
            },
        },
        {
            "query": "What was Q3 revenue?",
            "response": "Q3 2025 revenue reached $4.5 million, up 18% quarter-over-quarter.",
            "ground_truth": {
                "expected_culprit": "rev_wrong",
                "expected_ghosts": ["ghost_adv_1", "ghost_adv_2", "ghost_adv_3", "ghost_adv_4", "ghost_adv_5"],
                "expected_contradictions": [("rev_correct", "rev_wrong")],
                "expected_stale": [],
            },
        },
        {
            "query": "What is the maximum oven temperature for the ceramic coating?",
            "response": "The maximum oven temperature for the ceramic coating is 750 degrees Fahrenheit.",
            "ground_truth": {
                "expected_culprit": "temp_wrong",
                "expected_ghosts": ["ghost_adv_1", "ghost_adv_2", "ghost_adv_3", "ghost_adv_4", "ghost_adv_5"],
                "expected_contradictions": [("temp_correct", "temp_wrong")],
                "expected_stale": [],
            },
        },
    ],
}
