"""Stage 3: Aggregation and diagnosis.

Ghost detection, contradiction detection, staleness, health scoring,
memory health reports.
"""

from __future__ import annotations

import logging
from datetime import datetime
from itertools import combinations

from cama.types import (
    Contradiction,
    Memory,
    SpanAttribution,
    TraceResult,
)

logger = logging.getLogger(__name__)

# Staleness severity tiers
STALE_CRITICAL = "CRITICAL"
STALE_WARNING = "WARNING"
STALE_LOW = "LOW"


class Diagnoser:
    """Aggregate attribution results into actionable diagnoses."""

    def detect_ghosts(
        self,
        memories: list[Memory],
        span_attributions: list[SpanAttribution],
        query: str = "",
        ghost_threshold: float = 0.02,
        mas_threshold: float = 0.05,
        attribution_method: str = "",
        similarity_threshold: float = 0.20,
    ) -> list[str]:
        """Find ghost memories via query-memory cosine similarity.

        A ghost memory is semantically unrelated to the query. We embed the
        query and all memories, then flag any memory whose cosine similarity
        to the query falls below similarity_threshold.

        Falls back to MAS-based detection if embeddings are unavailable or
        no query is provided.
        """
        if not memories:
            return []

        # Primary method: cosine similarity between query and each memory
        if query:
            try:
                from cama.embed import embed_texts, cosine_similarity_matrix

                texts = [query] + [m.content for m in memories]
                embeddings = embed_texts(texts)
                query_emb = embeddings[0:1]
                memory_embs = embeddings[1:]
                sims = cosine_similarity_matrix(query_emb, memory_embs)[0]

                ghosts = []
                for i, m in enumerate(memories):
                    if sims[i] < similarity_threshold:
                        ghosts.append(m.id)
                return sorted(ghosts)
            except (ImportError, ValueError, Exception) as e:
                logger.warning("Embeddings unavailable (%s), falling back to MAS-based ghost detection", e)

        # Fallback: MAS-based detection (original approach)
        if not span_attributions:
            return []

        ghost_candidates = set(m.id for m in memories)
        for sa in span_attributions:
            for attr in sa.attributions:
                if abs(attr.delta) > ghost_threshold or attr.mas > mas_threshold:
                    ghost_candidates.discard(attr.memory_id)

        return sorted(ghost_candidates)

    # Stopwords for content word overlap check in contradiction detection
    _STOPWORDS = frozenset({
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
        "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "and", "but", "or", "nor", "not", "so", "yet", "both",
        "either", "neither", "each", "every", "all", "any", "few", "more",
        "most", "other", "some", "such", "no", "only", "own", "same", "than",
        "too", "very", "just", "because", "if", "when", "while", "where",
        "how", "what", "which", "who", "whom", "this", "that", "these",
        "those", "i", "me", "my", "we", "our", "you", "your", "he", "him",
        "his", "she", "her", "it", "its", "they", "them", "their",
    })

    def _content_word_overlap(self, text_a: str, text_b: str) -> int:
        """Count overlapping content words (non-stopwords) between two texts."""
        words_a = set(text_a.lower().split()) - self._STOPWORDS
        words_b = set(text_b.lower().split()) - self._STOPWORDS
        return len(words_a & words_b)

    def detect_contradictions(
        self,
        memories: list[Memory],
        span_attributions: list[SpanAttribution],
        nli_model: object | None = None,
        sim_threshold: float = 0.75,
        nli_threshold: float = 0.8,
        mas_threshold: float = 0.05,
        min_word_overlap: int = 2,
    ) -> list[Contradiction]:
        """Find contradicting memory pairs.

        Method 1 (attribution-based): memories with opposing directions on same span,
                requires BOTH to have raw_contradiction or raw_entailment > 0.0 (raw logit).
        Method 2 (strict NLI pairwise): requires ALL of:
                - Embedding cosine similarity > sim_threshold (0.75)
                - NLI contradiction > nli_threshold (0.8)
                - At least min_word_overlap content words in common
                - Both memories have MAS > mas_threshold on at least one span
        """
        contradictions: list[Contradiction] = []
        seen_pairs: set[tuple[str, str]] = set()

        # Method 1: Attribution-based (raw logit > 0 means positive evidence)
        for sa in span_attributions:
            supporting = [
                a for a in sa.attributions
                if a.direction == "supporting" and a.raw_entailment > 0.0
            ]
            causing = [
                a for a in sa.attributions
                if a.direction == "causing" and a.raw_contradiction > 0.0
            ]

            for s in supporting:
                for c in causing:
                    pair = tuple(sorted([s.memory_id, c.memory_id]))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)

                    contradictions.append(Contradiction(
                        memory_id_1=s.memory_id,
                        memory_id_2=c.memory_id,
                        explanation=(
                            f"On span '{sa.span.text}': "
                            f"{s.memory_id} supports (ent={s.raw_entailment:.1f}), "
                            f"{c.memory_id} contradicts (con={c.raw_contradiction:.1f})"
                        ),
                        span_text=sa.span.text,
                    ))

        # Method 2: Strict NLI pairwise (if model available)
        if nli_model is not None:
            # Build set of memory IDs with MAS > threshold on at least one span
            relevant_ids = set()
            for sa in span_attributions:
                for attr in sa.attributions:
                    if attr.mas > mas_threshold:
                        relevant_ids.add(attr.memory_id)

            relevant_memories = [m for m in memories if m.id in relevant_ids] if relevant_ids else memories
            self._nli_contradictions(
                relevant_memories, nli_model, contradictions, seen_pairs,
                sim_threshold, nli_threshold, min_word_overlap,
            )

        return contradictions

    def _nli_contradictions(
        self,
        memories: list[Memory],
        nli_model: object,
        contradictions: list[Contradiction],
        seen_pairs: set[tuple[str, str]],
        sim_threshold: float,
        nli_threshold: float = 0.8,
        min_word_overlap: int = 2,
    ) -> None:
        """Find contradictions via strict NLI pairwise check.

        Requires ALL of:
        - Embedding cosine similarity > sim_threshold
        - NLI contradiction > nli_threshold
        - At least min_word_overlap content words in common
        """
        # Pre-filter: only check pairs with high semantic overlap
        try:
            from cama.embed import embed_texts, cosine_similarity_matrix

            mem_texts = [m.content for m in memories]
            embeddings = embed_texts(mem_texts)
            sim_matrix = cosine_similarity_matrix(embeddings, embeddings)

            pairs_to_check: list[tuple[int, int]] = []
            for i, j in combinations(range(len(memories)), 2):
                if sim_matrix[i, j] > sim_threshold:
                    # Also require content word overlap
                    overlap = self._content_word_overlap(
                        memories[i].content, memories[j].content
                    )
                    if overlap >= min_word_overlap:
                        pairs_to_check.append((i, j))
        except ImportError:
            # No embeddings — fall back to word overlap only
            pairs_to_check = []
            for i, j in combinations(range(len(memories)), 2):
                overlap = self._content_word_overlap(
                    memories[i].content, memories[j].content
                )
                if overlap >= min_word_overlap:
                    pairs_to_check.append((i, j))

        for i, j in pairs_to_check:
            pair = tuple(sorted([memories[i].id, memories[j].id]))
            if pair in seen_pairs:
                continue

            is_contra, confidence = nli_model.is_contradiction(
                memories[i].content,
                memories[j].content,
                threshold=nli_threshold,
            )
            if is_contra:
                seen_pairs.add(pair)
                contradictions.append(Contradiction(
                    memory_id_1=memories[i].id,
                    memory_id_2=memories[j].id,
                    explanation=f"NLI contradiction (confidence={confidence:.2f})",
                ))

    def detect_stale(self, memories: list[Memory]) -> list[str]:
        """Find memories whose source was updated after they were created."""
        stale = []
        for m in memories:
            if (
                m.source_updated_at
                and m.created_at
                and m.source_updated_at > m.created_at
            ):
                stale.append(m.id)
        return stale

    def compute_health(self, trace: TraceResult) -> float:
        """Compute overall memory health score (0-100).

        Deductions:
        - Ghost memories: up to -40
        - Contradictions: up to -25
        - Stale memories: up to -25
        - Hallucination rate: up to -10
        """
        total_memories = max(len(trace.memories_used), 1)
        ghost_pct = len(trace.ghost_memories) / total_memories * 100
        stale_pct = len(trace.stale_memories) / total_memories * 100

        health = 100.0
        health -= ghost_pct * 0.4
        health -= min(len(trace.contradictions) * 8, 25)
        health -= stale_pct * 0.25
        health -= min(trace.hallucination_rate * 100, 10)

        return max(0.0, min(100.0, round(health)))

    def estimate_ghost_waste(
        self,
        ghost_memories: list[Memory],
        cost_per_token: float = 0.000003,
        avg_daily_queries: int = 1000,
    ) -> dict[str, float]:
        """Estimate token waste from ghost memories.

        Returns dict with waste_tokens, waste_cost_daily, waste_cost_monthly.
        """
        # Rough token estimate: ~4 chars per token
        waste_tokens = sum(len(m.content) // 4 for m in ghost_memories)
        waste_cost_daily = waste_tokens * cost_per_token * avg_daily_queries
        waste_cost_monthly = waste_cost_daily * 30

        return {
            "waste_tokens": waste_tokens,
            "waste_cost_daily": round(waste_cost_daily, 4),
            "waste_cost_monthly": round(waste_cost_monthly, 2),
        }

    # --- 4B: Staleness severity ---

    def detect_stale_with_severity(
        self,
        memories: list[Memory],
        span_attributions: list[SpanAttribution] | None = None,
        reference_date: datetime | None = None,
    ) -> list[dict]:
        """Find stale memories with severity scoring.

        severity = (days_since_update / 30) * mas_score
        Tiers: CRITICAL (>0.8), WARNING (0.4-0.8), LOW (<0.4)

        Returns list of dicts with memory_id, severity_score, tier, days_stale.
        """
        ref = reference_date or datetime.now()
        # Pre-compute average MAS per memory (if attributions available)
        mas_avg: dict[str, float] = {}
        if span_attributions:
            mas_sums: dict[str, list[float]] = {}
            for sa in span_attributions:
                for attr in sa.attributions:
                    mas_sums.setdefault(attr.memory_id, []).append(attr.mas)
            for mid, scores in mas_sums.items():
                mas_avg[mid] = sum(scores) / len(scores) if scores else 0.0

        results = []
        for m in memories:
            if not (m.source_updated_at and m.created_at and m.source_updated_at > m.created_at):
                continue

            days_stale = (ref - m.created_at).days
            mas_score = mas_avg.get(m.id, 0.1)  # default low MAS for unknown
            severity = (days_stale / 30.0) * mas_score
            severity = min(severity, 1.0)  # cap at 1.0

            if severity > 0.8:
                tier = STALE_CRITICAL
            elif severity > 0.4:
                tier = STALE_WARNING
            else:
                tier = STALE_LOW

            results.append({
                "memory_id": m.id,
                "severity_score": round(severity, 3),
                "tier": tier,
                "days_stale": days_stale,
            })

        return sorted(results, key=lambda x: x["severity_score"], reverse=True)

    # --- 4C: Memory health report ---

    def build_memory_health_report(
        self,
        memories: list[Memory],
        span_attributions: list[SpanAttribution],
        ghost_ids: list[str],
        stale_ids: list[str],
        contradictions: list[Contradiction],
        attribution_method: str = "",
    ) -> list[dict]:
        """Build per-memory health report.

        Each entry: memory_id, status, mas_avg, ghost_score, stale_severity,
        contradiction_partners, recommendation.
        """
        # MAS averages
        mas_scores: dict[str, list[float]] = {}
        neutral_scores: dict[str, list[float]] = {}
        for sa in span_attributions:
            for attr in sa.attributions:
                mas_scores.setdefault(attr.memory_id, []).append(attr.mas)
                neutral_scores.setdefault(attr.memory_id, []).append(attr.neutral_score)

        # Contradiction partners lookup
        contra_partners: dict[str, list[str]] = {}
        for c in contradictions:
            contra_partners.setdefault(c.memory_id_1, []).append(c.memory_id_2)
            contra_partners.setdefault(c.memory_id_2, []).append(c.memory_id_1)

        # Stale severity
        stale_severities = self.detect_stale_with_severity(memories, span_attributions)
        stale_sev_map = {s["memory_id"]: s for s in stale_severities}

        ghost_set = set(ghost_ids)
        stale_set = set(stale_ids)

        report = []
        for m in memories:
            mas_vals = mas_scores.get(m.id, [])
            mas_avg = sum(mas_vals) / len(mas_vals) if mas_vals else 0.0
            neu_vals = neutral_scores.get(m.id, [])
            ghost_score = sum(neu_vals) / len(neu_vals) if neu_vals else 0.0

            partners = contra_partners.get(m.id, [])
            sev = stale_sev_map.get(m.id, {})

            # Determine status
            if m.id in ghost_set:
                status = "ghost"
            elif m.id in stale_set:
                status = "stale"
            elif partners:
                status = "contradicted"
            elif mas_avg > 0.1:
                status = "active"
            else:
                status = "inactive"

            # Recommendation
            if status == "ghost":
                recommendation = "Remove — irrelevant to context, wasting tokens."
            elif status == "stale":
                tier = sev.get("tier", STALE_LOW)
                if tier == STALE_CRITICAL:
                    recommendation = "Update urgently — critically outdated and actively referenced."
                elif tier == STALE_WARNING:
                    recommendation = "Update soon — outdated source detected."
                else:
                    recommendation = "Review — source may have changed."
            elif status == "contradicted":
                recommendation = f"Resolve conflict with: {', '.join(partners)}."
            else:
                recommendation = "OK"

            report.append({
                "memory_id": m.id,
                "status": status,
                "mas_avg": round(mas_avg, 4),
                "ghost_score": round(ghost_score, 4),
                "stale_severity": sev.get("severity_score", 0.0),
                "stale_tier": sev.get("tier"),
                "contradiction_partners": partners,
                "recommendation": recommendation,
            })

        return report
