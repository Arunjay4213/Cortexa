"""Scenario 3: Financial Advisor Agent.

30 memories, 3 queries.
Tests: evolving risk profile, stale market data, contradictions.
"""

from datetime import datetime, timedelta

_now = datetime(2025, 10, 1)
_old = _now - timedelta(days=365)
_stale_update = _now - timedelta(days=7)

SCENARIO = {
    "name": "Financial Advisor Agent",
    "domain": "finance",
    "memories": [
        # --- Client Profile (5) ---
        {"id": "client_1", "content": "Client: David Park, age 42. Married, two children (ages 8, 12).", "created_at": _old.isoformat()},
        {"id": "client_2", "content": "Annual household income: $185,000. Current savings: $420,000.", "created_at": _old.isoformat()},
        {"id": "client_3", "content": "Risk tolerance: Moderate. Investment horizon: 20+ years (retirement at 62).", "created_at": _old.isoformat()},
        {"id": "client_4", "content": "Employer: TechCorp Inc. 401(k) match: 6% of salary.", "created_at": _old.isoformat()},
        {"id": "client_5", "content": "Mortgage: $350,000 remaining at 3.5% fixed, 22 years left.", "created_at": _old.isoformat()},
        # --- Portfolio Holdings (8) ---
        {"id": "port_1", "content": "VTSAX (Total Stock Market Index): $150,000 (35.7% of portfolio).", "created_at": _old.isoformat()},
        {"id": "port_2", "content": "VBTLX (Total Bond Market Index): $80,000 (19.0% of portfolio).", "created_at": _old.isoformat()},
        {"id": "port_3", "content": "VTIAX (International Stock Index): $60,000 (14.3% of portfolio).", "created_at": _old.isoformat()},
        {"id": "port_4", "content": "VGSLX (Real Estate Index): $30,000 (7.1% of portfolio).", "created_at": _old.isoformat()},
        {"id": "port_5", "content": "AAPL individual stock: $25,000 (6.0% of portfolio).", "created_at": _old.isoformat()},
        {"id": "port_6", "content": "TSLA individual stock: $15,000 (3.6% of portfolio).", "created_at": _old.isoformat()},
        {"id": "port_7", "content": "Emergency fund: $35,000 in high-yield savings (4.5% APY).", "created_at": _old.isoformat()},
        {"id": "port_8", "content": "529 college fund: $25,000 (target: $100K per child by 18).", "created_at": _old.isoformat()},
        # --- Market Context (5) ---
        {"id": "market_1", "content": "S&P 500 YTD return: +18.2% as of 2025-09-30.", "created_at": _old.isoformat()},
        {"id": "market_2", "content": "Federal Funds Rate: 4.25-4.50% (December 2025 forecast: 3.75-4.00%).", "created_at": _old.isoformat()},
        {"id": "market_3", "content": "Inflation rate (CPI): 2.4% year-over-year.", "created_at": _old.isoformat()},
        {"id": "market_4", "content": "10-year Treasury yield: 4.1%. Inverted yield curve has normalized.", "created_at": _old.isoformat()},
        {"id": "market_5", "content": "Consensus forecast: moderate economic growth through 2026.", "created_at": _old.isoformat()},
        # --- Stale (3) ---
        {"id": "stale_fin_1", "content": "Risk tolerance: Aggressive. Prefers growth-heavy allocation.", "created_at": _old.isoformat(), "source_updated_at": _stale_update.isoformat()},
        {"id": "stale_fin_2", "content": "Annual income: $145,000.", "created_at": _old.isoformat(), "source_updated_at": _stale_update.isoformat()},
        {"id": "stale_fin_3", "content": "S&P 500 YTD return: -5.3%.", "created_at": _old.isoformat(), "source_updated_at": _stale_update.isoformat()},
        # --- Poison (2) ---
        {"id": "poison_fin_1", "content": "Client should allocate 80% to individual stocks for maximum growth potential.", "created_at": _old.isoformat()},
        {"id": "poison_fin_2", "content": "Client has no children and plans to retire at age 70.", "created_at": _old.isoformat()},
        # --- Ghost (4) ---
        {"id": "ghost_fin_1", "content": "Office holiday closure: Dec 24-Jan 1.", "created_at": _old.isoformat()},
        {"id": "ghost_fin_2", "content": "Client prefers meeting on Wednesday afternoons.", "created_at": _old.isoformat()},
        {"id": "ghost_fin_3", "content": "Firm uses Schwab for custodial services.", "created_at": _old.isoformat()},
        {"id": "ghost_fin_4", "content": "Client drives from Palo Alto office.", "created_at": _old.isoformat()},
    ],
    "queries": [
        {
            "query": "What is the recommended portfolio allocation for this client?",
            "response": "Given the client's aggressive risk tolerance and no dependents, I recommend 85% individual stocks for maximum growth with retirement at age 75.",
            "ground_truth": {
                "expected_culprit": "poison_fin_1",
                "expected_ghosts": ["ghost_fin_1", "ghost_fin_2", "ghost_fin_3", "ghost_fin_4"],
                "expected_contradictions": [("client_3", "stale_fin_1"), ("client_1", "poison_fin_2")],
                "expected_stale": ["stale_fin_1", "stale_fin_2", "stale_fin_3"],
            },
        },
        {
            "query": "What is the client's current income and savings overview?",
            "response": "The client earns $165,000 annually with current savings of $480,000.",
            "ground_truth": {
                "expected_culprit": "stale_fin_2",
                "expected_ghosts": ["ghost_fin_1", "ghost_fin_2", "ghost_fin_3", "ghost_fin_4"],
                "expected_contradictions": [("client_2", "stale_fin_2")],
                "expected_stale": ["stale_fin_1", "stale_fin_2", "stale_fin_3"],
            },
        },
        {
            "query": "How is the S&P 500 performing this year?",
            "response": "The S&P 500 is down 8.7% year-to-date.",
            "ground_truth": {
                "expected_culprit": "stale_fin_3",
                "expected_ghosts": ["ghost_fin_1", "ghost_fin_2", "ghost_fin_3", "ghost_fin_4"],
                "expected_contradictions": [("market_1", "stale_fin_3")],
                "expected_stale": ["stale_fin_1", "stale_fin_2", "stale_fin_3"],
            },
        },
    ],
}
