"""Build synthetic benchmark for memory attribution evaluation.

Generates examples with planted poison memories, ghost memories,
and contradiction pairs to evaluate attribution precision.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)

# Synthetic test cases organized by domain
TEMPLATES: list[dict] = [
    # E-commerce
    {
        "domain": "e-commerce",
        "query": "What are the details of the Widget Pro?",
        "correct_memories": [
            {"id": "m1", "content": "Widget Pro costs $49.99."},
            {"id": "m2", "content": "Widget Pro has a 4.5 star rating on Amazon."},
            {"id": "m3", "content": "Returns accepted within 30 days of purchase."},
        ],
        "poison_memory": {
            "id": "m_poison",
            "content": "Widget Pro ships in 2-3 business days.",
            "true_content": "Widget Pro ships in 7-10 business days.",
        },
        "ghost_memories": [
            {"id": "m_ghost1", "content": "User prefers dark mode in the app."},
        ],
        "response": "Widget Pro costs $49.99 and ships in 2-3 business days. It has a 4.5 star rating with free returns within 30 days.",
        "hallucinated_spans": ["ships in 2-3 business days"],
    },
    # Healthcare
    {
        "domain": "healthcare",
        "query": "What is the dosage for Metformin?",
        "correct_memories": [
            {"id": "m1", "content": "Metformin is used to treat type 2 diabetes."},
            {"id": "m2", "content": "Common side effects include nausea and diarrhea."},
            {"id": "m3", "content": "Metformin should be taken with meals."},
        ],
        "poison_memory": {
            "id": "m_poison",
            "content": "Standard starting dose is 1000mg twice daily.",
            "true_content": "Standard starting dose is 500mg twice daily.",
        },
        "ghost_memories": [
            {"id": "m_ghost1", "content": "Patient last visited on March 15, 2024."},
        ],
        "response": "Metformin is used for type 2 diabetes. The standard starting dose is 1000mg twice daily, taken with meals. Common side effects include nausea and diarrhea.",
        "hallucinated_spans": ["1000mg twice daily"],
    },
    # Finance
    {
        "domain": "finance",
        "query": "What is the current state of ACME Corp stock?",
        "correct_memories": [
            {"id": "m1", "content": "ACME Corp (ACME) is traded on NYSE."},
            {"id": "m2", "content": "ACME Corp reported Q3 revenue of $2.1 billion."},
            {"id": "m3", "content": "The company has 15,000 employees globally."},
        ],
        "poison_memory": {
            "id": "m_poison",
            "content": "ACME stock price is $145.50 per share.",
            "true_content": "ACME stock price is $127.30 per share.",
        },
        "ghost_memories": [
            {"id": "m_ghost1", "content": "User's preferred currency is EUR."},
            {"id": "m_ghost2", "content": "Market closes at 4 PM EST."},
        ],
        "response": "ACME Corp (ACME) trades on NYSE at $145.50 per share. They reported Q3 revenue of $2.1 billion and have 15,000 employees worldwide.",
        "hallucinated_spans": ["$145.50 per share"],
    },
    # Tech Support
    {
        "domain": "tech_support",
        "query": "How do I fix the WiFi issue on my laptop?",
        "correct_memories": [
            {"id": "m1", "content": "User has a Dell XPS 15 running Windows 11."},
            {"id": "m2", "content": "The WiFi driver version is 22.100.1."},
            {"id": "m3", "content": "User tried restarting the router already."},
        ],
        "poison_memory": {
            "id": "m_poison",
            "content": "The latest WiFi driver version is 22.180.0.",
            "true_content": "The latest WiFi driver version is 22.200.2.",
        },
        "ghost_memories": [
            {"id": "m_ghost1", "content": "User's account was created in 2019."},
        ],
        "response": "For your Dell XPS 15 on Windows 11, you should update the WiFi driver from version 22.100.1 to the latest version 22.180.0. Since you already restarted the router, a driver update is the next step.",
        "hallucinated_spans": ["22.180.0"],
    },
    # Travel
    {
        "domain": "travel",
        "query": "What's the best way to get from the airport to downtown Tokyo?",
        "correct_memories": [
            {"id": "m1", "content": "Narita Express (N'EX) runs from Narita Airport to Tokyo Station."},
            {"id": "m2", "content": "The journey takes approximately 60 minutes."},
            {"id": "m3", "content": "A one-way ticket costs 3,250 yen."},
        ],
        "poison_memory": {
            "id": "m_poison",
            "content": "The Narita Express runs every 15 minutes during peak hours.",
            "true_content": "The Narita Express runs every 30 minutes during peak hours.",
        },
        "ghost_memories": [
            {"id": "m_ghost1", "content": "User's flight arrives at 2 PM local time."},
        ],
        "response": "Take the Narita Express (N'EX) from Narita Airport to Tokyo Station. It runs every 15 minutes during peak hours, takes about 60 minutes, and costs 3,250 yen one-way.",
        "hallucinated_spans": ["every 15 minutes"],
    },
    # Education
    {
        "domain": "education",
        "query": "What are the admission requirements for MIT?",
        "correct_memories": [
            {"id": "m1", "content": "MIT requires SAT or ACT scores for admission."},
            {"id": "m2", "content": "The application deadline is January 1."},
            {"id": "m3", "content": "MIT's acceptance rate is around 4%."},
        ],
        "poison_memory": {
            "id": "m_poison",
            "content": "MIT requires a minimum GPA of 3.5 for admission.",
            "true_content": "MIT does not have a strict minimum GPA requirement.",
        },
        "ghost_memories": [
            {"id": "m_ghost1", "content": "User is currently a high school junior."},
        ],
        "response": "MIT requires SAT or ACT scores, with a minimum GPA of 3.5. The application deadline is January 1, and the acceptance rate is around 4%.",
        "hallucinated_spans": ["minimum GPA of 3.5"],
    },
    # Contradiction example
    {
        "domain": "e-commerce",
        "query": "When does the sale end?",
        "correct_memories": [
            {"id": "m1", "content": "The summer sale started on June 1."},
        ],
        "poison_memory": {
            "id": "m_poison",
            "content": "The summer sale ends on June 30.",
            "true_content": "The summer sale ends on July 15.",
        },
        "ghost_memories": [
            {"id": "m_ghost1", "content": "User browsed kitchen appliances yesterday."},
        ],
        "response": "The summer sale started on June 1 and ends on June 30.",
        "hallucinated_spans": ["ends on June 30"],
        "contradiction_pair": None,
    },
    # Fabrication example (hallucination not from any memory)
    {
        "domain": "general",
        "query": "Tell me about the company's founding.",
        "correct_memories": [
            {"id": "m1", "content": "The company was founded in 2010."},
            {"id": "m2", "content": "The headquarters is in San Francisco."},
        ],
        "poison_memory": None,
        "ghost_memories": [
            {"id": "m_ghost1", "content": "User asked about pricing last week."},
        ],
        "response": "The company was founded in 2010 in San Francisco by John Smith and Jane Doe.",
        "hallucinated_spans": ["by John Smith and Jane Doe"],
    },
]

# Additional templates for contradiction testing
CONTRADICTION_TEMPLATES: list[dict] = [
    {
        "domain": "e-commerce",
        "query": "Is the Widget Pro in stock?",
        "memories": [
            {"id": "m1", "content": "Widget Pro is currently in stock with 50 units available."},
            {"id": "m2", "content": "Widget Pro is out of stock and backordered until next month."},
            {"id": "m3", "content": "Widget Pro comes in black and silver colors."},
        ],
        "contradiction_pair": ("m1", "m2"),
        "response": "The Widget Pro is in stock with 50 units available. It comes in black and silver.",
        "hallucinated_spans": [],
    },
    {
        "domain": "healthcare",
        "query": "Can I take aspirin with blood thinners?",
        "memories": [
            {"id": "m1", "content": "Aspirin should not be combined with blood thinners due to bleeding risk."},
            {"id": "m2", "content": "Low-dose aspirin can be safely combined with blood thinners."},
            {"id": "m3", "content": "Always consult your doctor before combining medications."},
        ],
        "contradiction_pair": ("m1", "m2"),
        "response": "Low-dose aspirin can be safely combined with blood thinners. Always consult your doctor.",
        "hallucinated_spans": [],
    },
]


def build_benchmark(n: int = 200, seed: int = 42) -> list[dict]:
    """Generate n synthetic benchmark examples.

    Each example contains:
    - memories: list of memory dicts
    - query: str
    - response: str
    - ground_truth: dict with hallucinated_spans, poison_memory_id, ghost_memory_ids,
      contradiction_pair
    """
    random.seed(seed)
    examples: list[dict] = []

    for i in range(n):
        # Pick template
        if i < len(TEMPLATES):
            template = TEMPLATES[i]
        else:
            template = random.choice(TEMPLATES)

        # Assemble memories
        memories = list(template["correct_memories"])

        poison_id = None
        if template.get("poison_memory"):
            poison = template["poison_memory"]
            memories.append({"id": poison["id"], "content": poison["content"]})
            poison_id = poison["id"]

        ghost_ids = []
        for ghost in template.get("ghost_memories", []):
            memories.append(ghost)
            ghost_ids.append(ghost["id"])

        # Shuffle memories
        random.shuffle(memories)

        examples.append({
            "id": f"synth_{i:04d}",
            "domain": template["domain"],
            "query": template["query"],
            "response": template["response"],
            "memories": memories,
            "ground_truth": {
                "hallucinated_spans": template["hallucinated_spans"],
                "poison_memory_id": poison_id,
                "ghost_memory_ids": ghost_ids,
                "contradiction_pair": template.get("contradiction_pair"),
            },
        })

    # Add contradiction examples
    for i, ct in enumerate(CONTRADICTION_TEMPLATES):
        examples.append({
            "id": f"contra_{i:04d}",
            "domain": ct["domain"],
            "query": ct["query"],
            "response": ct["response"],
            "memories": ct["memories"],
            "ground_truth": {
                "hallucinated_spans": ct["hallucinated_spans"],
                "poison_memory_id": None,
                "ghost_memory_ids": [],
                "contradiction_pair": ct["contradiction_pair"],
            },
        })

    return examples


def save_benchmark(
    examples: list[dict],
    output_path: str = "benchmarks/synthetic_dataset.json",
) -> None:
    """Save benchmark to JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(examples, f, indent=2)
    logger.info("Saved %d examples to %s", len(examples), path)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    examples = build_benchmark(n=200)
    save_benchmark(examples)
    print(f"Built {len(examples)} synthetic examples")
    print(f"Domains: {set(e['domain'] for e in examples)}")
    print(f"With poison: {sum(1 for e in examples if e['ground_truth']['poison_memory_id'])}")
    print(f"With ghosts: {sum(1 for e in examples if e['ground_truth']['ghost_memory_ids'])}")
    print(f"With contradictions: {sum(1 for e in examples if e['ground_truth']['contradiction_pair'])}")


if __name__ == "__main__":
    main()
