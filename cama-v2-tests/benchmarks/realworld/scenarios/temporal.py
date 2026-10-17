"""Scenario 7: Temporal Drift (12-month memory evolution).

40 memories showing how facts change over time.
Tests: detecting stale information when multiple versions exist.
"""

from datetime import datetime, timedelta

_base = datetime(2025, 1, 1)


def _at_month(month: int) -> str:
    """Return ISO datetime for a given month offset from base."""
    return (_base + timedelta(days=30 * month)).isoformat()


SCENARIO = {
    "name": "Temporal Memory Drift",
    "domain": "temporal",
    "memories": [
        # --- Evolving company metrics (each pair: old stale + new current) ---
        # Revenue
        {"id": "rev_q1", "content": "Q1 2025 revenue: $2.1 million.", "created_at": _at_month(0)},
        {"id": "rev_q2", "content": "Q2 2025 revenue: $2.8 million.", "created_at": _at_month(3)},
        {"id": "rev_q3", "content": "Q3 2025 revenue: $3.5 million.", "created_at": _at_month(6)},
        {"id": "rev_q4_proj", "content": "Q4 2025 projected revenue: $4.2 million.", "created_at": _at_month(9)},
        # Headcount
        {"id": "hc_jan", "content": "Company headcount: 45 employees as of January 2025.", "created_at": _at_month(0)},
        {"id": "hc_apr", "content": "Company headcount: 52 employees as of April 2025.", "created_at": _at_month(3)},
        {"id": "hc_jul", "content": "Company headcount: 68 employees as of July 2025.", "created_at": _at_month(6)},
        {"id": "hc_oct", "content": "Company headcount: 75 employees as of October 2025.", "created_at": _at_month(9)},
        # Product pricing
        {"id": "price_v1", "content": "Product pricing: $29/month for Pro plan. Set January 2025.", "created_at": _at_month(0)},
        {"id": "price_v2", "content": "Product pricing: $39/month for Pro plan. Effective April 2025.", "created_at": _at_month(3)},
        {"id": "price_v3", "content": "Product pricing: $49/month for Pro plan. Effective August 2025.", "created_at": _at_month(7)},
        # Office location
        {"id": "office_v1", "content": "Office address: 100 Market St, Suite 200, San Francisco.", "created_at": _at_month(0)},
        {"id": "office_v2", "content": "Office address: 500 Howard St, Floor 12, San Francisco. Moved June 2025.", "created_at": _at_month(5)},
        # Customer count
        {"id": "cust_q1", "content": "Active customers: 1,200 as of Q1 2025.", "created_at": _at_month(0)},
        {"id": "cust_q2", "content": "Active customers: 1,850 as of Q2 2025.", "created_at": _at_month(3)},
        {"id": "cust_q3", "content": "Active customers: 2,500 as of Q3 2025.", "created_at": _at_month(6)},
        {"id": "cust_q4", "content": "Active customers: 3,100 as of Q4 2025 (projected).", "created_at": _at_month(9)},
        # Stale versions (explicitly marked with source_updated_at) ---
        {"id": "stale_rev", "content": "Annual revenue: $6 million.", "created_at": _at_month(0), "source_updated_at": _at_month(9)},
        {"id": "stale_hc", "content": "Company headcount: 30 employees.", "created_at": _at_month(0), "source_updated_at": _at_month(9)},
        {"id": "stale_price", "content": "Product pricing: $19/month for Pro plan.", "created_at": _at_month(0), "source_updated_at": _at_month(7)},
        {"id": "stale_cust", "content": "Active customers: 800.", "created_at": _at_month(0), "source_updated_at": _at_month(6)},
        # --- Strategy & plans (static context) ---
        {"id": "strategy_1", "content": "2025 goal: Reach $15M ARR by December.", "created_at": _at_month(0)},
        {"id": "strategy_2", "content": "Focus areas: Enterprise sales, product-led growth, APAC expansion.", "created_at": _at_month(0)},
        {"id": "strategy_3", "content": "Key hire: VP of Engineering. Target start Q2 2025.", "created_at": _at_month(0)},
        {"id": "strategy_4", "content": "Series B: Raised $25M at $120M valuation, March 2025.", "created_at": _at_month(2)},
        # --- Team info (static) ---
        {"id": "team_1", "content": "CEO: Alex Rivera. Founded the company in 2022.", "created_at": _at_month(0)},
        {"id": "team_2", "content": "CTO: Priya Sharma. Joined from Google in 2023.", "created_at": _at_month(0)},
        {"id": "team_3", "content": "VP Sales: Marcus Johnson. Hired January 2025.", "created_at": _at_month(0)},
        {"id": "team_4", "content": "VP Engineering: Lisa Chang. Started May 2025.", "created_at": _at_month(4)},
        # --- Ghost memories ---
        {"id": "ghost_t1", "content": "Board meeting scheduled for last Friday of each quarter.", "created_at": _at_month(0)},
        {"id": "ghost_t2", "content": "Company uses Slack for internal communication.", "created_at": _at_month(0)},
        {"id": "ghost_t3", "content": "All-hands meeting every other Monday at 10am.", "created_at": _at_month(0)},
        {"id": "ghost_t4", "content": "Engineering team uses GitHub for version control.", "created_at": _at_month(0)},
        {"id": "ghost_t5", "content": "Free lunch provided on Tuesdays and Thursdays.", "created_at": _at_month(0)},
        # --- Poison ---
        {"id": "poison_t1", "content": "Company headcount: 120 employees.", "created_at": _at_month(0)},
        {"id": "poison_t2", "content": "Pro plan costs $99/month.", "created_at": _at_month(0)},
        # Padding to reach 40
        {"id": "misc_1", "content": "Q2 board deck is available on the shared drive.", "created_at": _at_month(3)},
        {"id": "misc_2", "content": "Annual company retreat planned for November.", "created_at": _at_month(8)},
        {"id": "misc_3", "content": "New competitor 'RivalCo' launched similar product in August.", "created_at": _at_month(7)},
        {"id": "misc_4", "content": "Customer NPS score: 72 as of Q3 2025.", "created_at": _at_month(6)},
    ],
    "queries": [
        {
            "query": "How many employees does the company have?",
            "response": "The company has 95 employees.",
            "ground_truth": {
                "expected_culprit": "poison_t1",
                "expected_ghosts": ["ghost_t1", "ghost_t2", "ghost_t3", "ghost_t4", "ghost_t5"],
                "expected_contradictions": [("hc_oct", "poison_t1")],
                "expected_stale": ["stale_rev", "stale_hc", "stale_price", "stale_cust"],
            },
        },
        {
            "query": "What does the Pro plan cost?",
            "response": "The Pro plan costs $79/month.",
            "ground_truth": {
                "expected_culprit": "poison_t2",
                "expected_ghosts": ["ghost_t1", "ghost_t2", "ghost_t3", "ghost_t4", "ghost_t5"],
                "expected_contradictions": [("price_v3", "poison_t2")],
                "expected_stale": ["stale_rev", "stale_hc", "stale_price", "stale_cust"],
            },
        },
        {
            "query": "What is the latest quarterly revenue?",
            "response": "Q3 2025 revenue was $3.5 million, with Q4 projected at $4.2 million.",
            "ground_truth": {
                "expected_culprit": None,
                "expected_ghosts": ["ghost_t1", "ghost_t2", "ghost_t3", "ghost_t4", "ghost_t5"],
                "expected_contradictions": [],
                "expected_stale": ["stale_rev", "stale_hc", "stale_price", "stale_cust"],
            },
        },
    ],
}
