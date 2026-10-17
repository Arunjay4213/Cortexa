"""Contradiction detection between memories.

Two approaches:
1. Pairwise NLI: check if one memory contradicts another (O(n²) on co-retrieved).
2. Claim-level: if two memories have high MAS but disagree on a claim.
"""

from __future__ import annotations

from collections.abc import Callable

from cortexa.engine.models import Attribution, Claim, Contradiction, EntailmentScore, Memory


class ContradictionDetector:
    """Detects contradictions between memories."""

    def __init__(self, contradiction_threshold: float = 0.7) -> None:
        self.contradiction_threshold = contradiction_threshold

    def detect_from_entailments(
        self,
        memories: list[Memory],
        claims: list[Claim],
        entailments: list[EntailmentScore],
        attributions: list[Attribution],
    ) -> list[Contradiction]:
        """Detect contradictions using claim-level entailment analysis.

        If two memories both have significant MAS for the same claim but one
        entails and the other contradicts, flag as contradiction.
        """
        contradictions: list[Contradiction] = []
        seen_pairs: set[tuple[str, str]] = set()

        # Index by claim_id
        claim_ents: dict[str, list[EntailmentScore]] = {}
        for es in entailments:
            claim_ents.setdefault(es.claim_id, []).append(es)

        claim_attrs: dict[str, list[Attribution]] = {}
        for attr in attributions:
            claim_attrs.setdefault(attr.claim_id, []).append(attr)

        # Build memory lookup
        mem_map = {m.id: m for m in memories}

        for claim in claims:
            ents = claim_ents.get(claim.id, [])
            attrs = claim_attrs.get(claim.id, [])

            # Find memories with significant attribution for this claim
            significant = [a for a in attrs if a.mas_score > 0.05]

            # Check pairs of significant memories
            for i, a1 in enumerate(significant):
                for a2 in significant[i + 1 :]:
                    pair_key = tuple(sorted([a1.memory_id, a2.memory_id]))
                    if pair_key in seen_pairs:
                        continue

                    # Look up entailment labels
                    e1 = next((e for e in ents if e.memory_id == a1.memory_id), None)
                    e2 = next((e for e in ents if e.memory_id == a2.memory_id), None)

                    if e1 is None or e2 is None:
                        continue

                    # Contradiction pattern: one entails, other contradicts
                    if (
                        e1.label == "entailment"
                        and e2.label == "contradiction"
                        and e2.contradiction > self.contradiction_threshold
                    ) or (
                        e2.label == "entailment"
                        and e1.label == "contradiction"
                        and e1.contradiction > self.contradiction_threshold
                    ):
                        seen_pairs.add(pair_key)

                        m1 = mem_map.get(a1.memory_id)
                        m2 = mem_map.get(a2.memory_id)
                        m1_text = m1.content[:80] if m1 else a1.memory_id
                        m2_text = m2.content[:80] if m2 else a2.memory_id

                        severity = max(
                            e1.contradiction if e1.label == "contradiction" else 0,
                            e2.contradiction if e2.label == "contradiction" else 0,
                        )

                        contradictions.append(
                            Contradiction(
                                memory_id_1=a1.memory_id,
                                memory_id_2=a2.memory_id,
                                claim_id=claim.id,
                                explanation=(
                                    f'Memories disagree on "{claim.text[:60]}": '
                                    f'"{m1_text}" vs "{m2_text}"'
                                ),
                                severity=round(severity, 3),
                            )
                        )

        return contradictions

    def detect_pairwise(
        self,
        memories: list[Memory],
        score_fn: Callable[[str, str], tuple[float, float, float]] | None = None,
    ) -> list[Contradiction]:
        """Detect contradictions via pairwise NLI between memories.

        This is O(n²) so should only be used on co-retrieved memory sets.

        Args:
            memories: Memories to compare pairwise.
            score_fn: Optional function (str, str) -> (contradiction, entailment, neutral).
                     If None, returns empty (needs entailment backend).
        """
        if score_fn is None or len(memories) < 2:
            return []

        contradictions: list[Contradiction] = []

        for i, m1 in enumerate(memories):
            for m2 in memories[i + 1 :]:
                cont, ent, _ = score_fn(m1.content, m2.content)
                if cont > self.contradiction_threshold:
                    contradictions.append(
                        Contradiction(
                            memory_id_1=m1.id,
                            memory_id_2=m2.id,
                            explanation=(
                                f'Direct contradiction (p={cont:.2f}): '
                                f'"{m1.content[:60]}" vs "{m2.content[:60]}"'
                            ),
                            severity=round(cont, 3),
                        )
                    )

        return contradictions
