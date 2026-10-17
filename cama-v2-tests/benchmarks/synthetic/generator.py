"""Synthetic benchmark case generator.

Generates N planted-poison test cases across multiple domains.
Each case has a known culprit, known ghosts, and known stale memory.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Iterator

from .domains import DOMAINS


def generate_case(
    domain: str,
    template: dict,
    poison_variant: int = 0,
    case_id: int = 0,
) -> dict:
    """Generate a single test case from a domain template.

    Returns a dict with:
    - query, response, memories (list of dicts)
    - ground_truth: expected_culprit, expected_ghosts, expected_stale
    """
    # Pick poison values
    poison_values = {}
    for key, variants in template["poison_values"].items():
        idx = poison_variant % len(variants)
        poison_values[key] = variants[idx]

    # Build poison answer and memory
    poison_answer = template["poison_answer"]
    poison_memory_text = template["poison_memory"]
    for key, val in poison_values.items():
        poison_answer = poison_answer.replace(f"{{{key}}}", val)
        poison_memory_text = poison_memory_text.replace(f"{{{key}}}", val)

    # Build memories
    memories = []
    ghost_ids = []

    # Supporting memories
    for i, content in enumerate(template["supporting_memories"]):
        memories.append({
            "id": f"case{case_id}_support_{i}",
            "content": content,
            "created_at": datetime(2025, 1, 1).isoformat(),
        })

    # Poison memory (stale — source_updated_at > created_at)
    poison_id = f"case{case_id}_poison"
    memories.append({
        "id": poison_id,
        "content": poison_memory_text,
        "created_at": datetime(2025, 1, 1).isoformat(),
        "source_updated_at": (datetime(2025, 1, 1) + timedelta(days=180)).isoformat(),
    })

    # Ghost memories
    for i, content in enumerate(template["ghost_memories"]):
        gid = f"case{case_id}_ghost_{i}"
        memories.append({
            "id": gid,
            "content": content,
            "created_at": datetime(2025, 6, 1).isoformat(),
        })
        ghost_ids.append(gid)

    # Shuffle memories so poison isn't always in the same position
    random.shuffle(memories)

    return {
        "case_id": case_id,
        "domain": domain,
        "query": template["query"],
        "response": poison_answer,
        "memories": memories,
        "ground_truth": {
            "expected_culprit": poison_id,
            "expected_ghosts": ghost_ids,
            "expected_stale": [poison_id],
        },
    }


def generate_benchmark(n_cases: int = 500, seed: int = 42) -> list[dict]:
    """Generate N test cases distributed across all domains.

    Returns list of case dicts ready for evaluation.
    """
    random.seed(seed)

    # Flatten all templates
    all_templates: list[tuple[str, dict]] = []
    for domain, templates in DOMAINS.items():
        for t in templates:
            all_templates.append((domain, t))

    cases = []
    for i in range(n_cases):
        domain, template = all_templates[i % len(all_templates)]
        # Vary poison values
        n_variants = 1
        for variants in template["poison_values"].values():
            n_variants *= len(variants)
        poison_variant = (i // len(all_templates)) % n_variants

        case = generate_case(domain, template, poison_variant=poison_variant, case_id=i)
        cases.append(case)

    return cases


def iter_benchmark(n_cases: int = 500, seed: int = 42) -> Iterator[dict]:
    """Lazy iterator version of generate_benchmark."""
    yield from generate_benchmark(n_cases, seed)
