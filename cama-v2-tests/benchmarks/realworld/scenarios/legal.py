"""Scenario 4: Legal Contract Agent.

25 memories, 3 queries.
Tests: contract version changes, clause conflicts, stale terms.
"""

from datetime import datetime, timedelta

_now = datetime(2025, 10, 1)
_old = _now - timedelta(days=365)
_stale_update = _now - timedelta(days=14)

SCENARIO = {
    "name": "Legal Contract Agent",
    "domain": "legal",
    "memories": [
        # --- Contract Terms (8) ---
        {"id": "term_1", "content": "Service Agreement v3.2: Term is 24 months starting January 1, 2025.", "created_at": _old.isoformat()},
        {"id": "term_2", "content": "Monthly service fee: $5,000. Payment due within 30 days of invoice.", "created_at": _old.isoformat()},
        {"id": "term_3", "content": "Early termination fee: $10,000 plus remaining months at 50% rate.", "created_at": _old.isoformat()},
        {"id": "term_4", "content": "Auto-renewal: Contract renews for 12-month terms unless 90-day notice given.", "created_at": _old.isoformat()},
        {"id": "term_5", "content": "SLA guarantee: 99.9% uptime. Credits issued for downtime exceeding 0.1%.", "created_at": _old.isoformat()},
        {"id": "term_6", "content": "Data retention: Provider retains data for 90 days after contract termination.", "created_at": _old.isoformat()},
        {"id": "term_7", "content": "Liability cap: Total liability not to exceed 12 months of fees paid.", "created_at": _old.isoformat()},
        {"id": "term_8", "content": "Governing law: State of California. Arbitration required for disputes.", "created_at": _old.isoformat()},
        # --- Amendment History (4) ---
        {"id": "amend_1", "content": "Amendment 1 (2025-03): Added GDPR compliance clause. Provider acts as data processor.", "created_at": _old.isoformat()},
        {"id": "amend_2", "content": "Amendment 2 (2025-06): Expanded SLA to include API response time <200ms p95.", "created_at": _old.isoformat()},
        {"id": "amend_3", "content": "Amendment 3 (2025-08): Reduced early termination fee to $5,000 flat.", "created_at": _old.isoformat()},
        {"id": "amend_4", "content": "Amendment 4 (2025-09): Added SOC 2 Type II compliance requirement.", "created_at": _old.isoformat()},
        # --- Stale (3) --- old contract terms superseded by amendments ---
        {"id": "stale_legal_1", "content": "Early termination fee: $15,000 plus full remaining balance.", "created_at": _old.isoformat(), "source_updated_at": _stale_update.isoformat()},
        {"id": "stale_legal_2", "content": "SLA guarantee: 99.5% uptime only. No API performance guarantees.", "created_at": _old.isoformat(), "source_updated_at": _stale_update.isoformat()},
        {"id": "stale_legal_3", "content": "No GDPR compliance requirements in the agreement.", "created_at": _old.isoformat(), "source_updated_at": _stale_update.isoformat()},
        # --- Poison (2) ---
        {"id": "poison_legal_1", "content": "The contract has no early termination fee. Client can cancel at any time.", "created_at": _old.isoformat()},
        {"id": "poison_legal_2", "content": "Liability is unlimited. Provider covers all damages without cap.", "created_at": _old.isoformat()},
        # --- Ghost (5) ---
        {"id": "ghost_legal_1", "content": "Client's office is on the 14th floor, Suite 1420.", "created_at": _old.isoformat()},
        {"id": "ghost_legal_2", "content": "Client's legal team prefers PDF document format.", "created_at": _old.isoformat()},
        {"id": "ghost_legal_3", "content": "Contract review meetings held quarterly.", "created_at": _old.isoformat()},
        {"id": "ghost_legal_4", "content": "Client's fiscal year ends March 31.", "created_at": _old.isoformat()},
        {"id": "ghost_legal_5", "content": "Lead attorney: Maria Gonzalez, Barr & Associates.", "created_at": _old.isoformat()},
    ],
    "queries": [
        {
            "query": "What is the early termination fee for our current contract?",
            "response": "The early termination fee is $8,500 with a 60-day notice period required.",
            "ground_truth": {
                "expected_culprit": "poison_legal_1",
                "expected_ghosts": ["ghost_legal_1", "ghost_legal_2", "ghost_legal_3", "ghost_legal_4", "ghost_legal_5"],
                "expected_contradictions": [("amend_3", "poison_legal_1"), ("term_3", "poison_legal_1")],
                "expected_stale": ["stale_legal_1", "stale_legal_2", "stale_legal_3"],
            },
        },
        {
            "query": "What is the provider's liability cap?",
            "response": "Liability is capped at 24 months of fees. The provider's coverage is limited per the contract terms.",
            "ground_truth": {
                "expected_culprit": "poison_legal_2",
                "expected_ghosts": ["ghost_legal_1", "ghost_legal_2", "ghost_legal_3", "ghost_legal_4", "ghost_legal_5"],
                "expected_contradictions": [("term_7", "poison_legal_2")],
                "expected_stale": ["stale_legal_1", "stale_legal_2", "stale_legal_3"],
            },
        },
        {
            "query": "Does the contract include GDPR compliance?",
            "response": "Yes, Amendment 1 added GDPR compliance. The provider acts as data processor under the agreement.",
            "ground_truth": {
                "expected_culprit": None,
                "expected_ghosts": ["ghost_legal_1", "ghost_legal_2", "ghost_legal_3", "ghost_legal_4", "ghost_legal_5"],
                "expected_contradictions": [("amend_1", "stale_legal_3")],
                "expected_stale": ["stale_legal_1", "stale_legal_2", "stale_legal_3"],
            },
        },
    ],
}
