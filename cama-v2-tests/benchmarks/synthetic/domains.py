"""Domain-specific memory templates for synthetic benchmark generation.

Each domain defines:
- poison_answer: response with WRONG numbers (not matching any memory)
- poison_memory: memory with CORRECT value (structurally similar to response)
- supporting_memories: additional context memories
- ghost_memories: irrelevant memories

Key design: the poison_answer's numbers must NOT appear in any memory,
so the EmbeddingDetector's numerical grounding gate flags them.
The poison_memory has the correct value and is the structurally closest
match to the hallucinated span — making it the expected_culprit by MAS.
"""

from __future__ import annotations

DOMAINS: dict[str, list[dict]] = {
    "ecommerce": [
        {
            "query": "What is the price of Widget Pro?",
            "correct_answer": "Widget Pro costs $49.99.",
            "poison_answer": "Widget Pro costs ${poison_price}. We also offer an extended protection plan for $199.",
            "poison_memory": "Widget Pro costs $49.99.",
            "supporting_memories": [
                "Widget Pro has a 4.5 star rating.",
                "Widget Pro comes in blue and silver.",
                "Free shipping on orders over $25.",
            ],
            "ghost_memories": [
                "Customer prefers dark mode.",
                "Account created via Google OAuth.",
            ],
            "poison_values": {"poison_price": ["99.99", "199.99", "29.99", "149.99"]},
        },
        {
            "query": "What is the return policy?",
            "correct_answer": "Returns are accepted within 30 days.",
            "poison_answer": "Returns are accepted within {poison_days} days. A restocking fee of $75 applies to all returns.",
            "poison_memory": "Return window: 30 days for all purchases.",
            "supporting_memories": [
                "Refunds processed within 5 business days.",
                "Items must be in original packaging.",
            ],
            "ghost_memories": [
                "Customer likes email notifications.",
            ],
            "poison_values": {"poison_days": ["7", "14", "90", "365"]},
        },
    ],
    "medical": [
        {
            "query": "What is the recommended dosage?",
            "correct_answer": "The recommended dosage is 500mg twice daily.",
            "poison_answer": "The recommended dosage is {poison_dosage}mg twice daily. Blood tests are required every 2 weeks during treatment.",
            "poison_memory": "Recommended dosage: 500mg twice daily.",
            "supporting_memories": [
                "Patient DOB: 1985-03-15.",
                "Primary physician: Dr. Chen.",
                "Blood type: O+.",
            ],
            "ghost_memories": [
                "Patient prefers morning appointments.",
            ],
            "poison_values": {"poison_dosage": ["250", "1000", "750", "200"]},
        },
    ],
    "finance": [
        {
            "query": "What is the Q4 revenue projection?",
            "correct_answer": "Q4 revenue is projected at $4.2 million.",
            "poison_answer": "Q4 revenue is projected at ${poison_revenue} million. The board has approved a $3 million expansion budget.",
            "poison_memory": "Projected Q4 revenue: $4.2 million.",
            "supporting_memories": [
                "Q3 actual revenue: $3.8 million.",
                "YoY growth rate: 12%.",
            ],
            "ghost_memories": [
                "CFO prefers quarterly board meetings.",
                "Office lease expires December 2026.",
            ],
            "poison_values": {"poison_revenue": ["5.1", "6.3", "8.0", "2.1"]},
        },
    ],
    "legal": [
        {
            "query": "What is the early termination fee?",
            "correct_answer": "The early termination fee is $500.",
            "poison_answer": "The early termination fee is ${poison_fee}. A 90-day notice period is also required.",
            "poison_memory": "Early termination fee: $500.",
            "supporting_memories": [
                "Contract effective date: January 1, 2025.",
                "Contract term: 24 months.",
            ],
            "ghost_memories": [
                "Client prefers communication via email.",
            ],
            "poison_values": {"poison_fee": ["10000", "5000", "2500", "750"]},
        },
    ],
    "tech_support": [
        {
            "query": "What is the recommended RAM for this software?",
            "correct_answer": "The recommended RAM is 8GB.",
            "poison_answer": "The recommended RAM is {poison_ram}GB. A dedicated GPU with 4GB VRAM is also recommended.",
            "poison_memory": "System requirement: 8GB RAM recommended.",
            "supporting_memories": [
                "Supported OS: Windows 10+, macOS 12+.",
                "Disk space: 500MB required.",
                "Internet connection required for activation.",
            ],
            "ghost_memories": [
                "Customer has a Dell laptop.",
                "Last support ticket: 2025-09-01.",
            ],
            "poison_values": {"poison_ram": ["16", "32", "4", "64"]},
        },
    ],
    "hr": [
        {
            "query": "How many vacation days do employees get?",
            "correct_answer": "Employees receive 15 vacation days per year.",
            "poison_answer": "Employees receive {poison_days} vacation days per year. Unused days can be carried over up to 40 hours.",
            "poison_memory": "Annual vacation: 15 days.",
            "supporting_memories": [
                "Sick leave: 10 days per year.",
                "Parental leave: 12 weeks paid.",
            ],
            "ghost_memories": [
                "Office location: 123 Main St.",
            ],
            "poison_values": {"poison_days": ["20", "25", "30"]},
        },
    ],
    "insurance": [
        {
            "query": "What is the monthly premium?",
            "correct_answer": "The monthly premium is $250.",
            "poison_answer": "The monthly premium is ${poison_premium}. A $100 copay applies to specialist visits.",
            "poison_memory": "Monthly premium: $250.",
            "supporting_memories": [
                "Deductible: $1,000.",
                "Coverage limit: $500,000.",
                "Policy number: INS-2025-0042.",
            ],
            "ghost_memories": [
                "Agent assigned: Sarah Johnson.",
            ],
            "poison_values": {"poison_premium": ["500", "750", "125", "1000"]},
        },
    ],
    "education": [
        {
            "query": "What is the tuition for the program?",
            "correct_answer": "The tuition is $15,000 per semester.",
            "poison_answer": "The tuition is ${poison_tuition} per semester. A $500 technology fee is also charged each semester.",
            "poison_memory": "Tuition: $15,000 per semester.",
            "supporting_memories": [
                "Program duration: 4 semesters.",
                "Financial aid available for qualifying students.",
            ],
            "ghost_memories": [
                "Campus has a new student center.",
                "Library hours: 8am-10pm.",
            ],
            "poison_values": {"poison_tuition": ["25000", "35000", "8000", "50000"]},
        },
    ],
}
