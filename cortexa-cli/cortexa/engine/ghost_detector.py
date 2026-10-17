"""Ghost token identification — memories consuming tokens with no attribution.

A memory is a "ghost token" if:
- MAS < 0.05 across all claims in the current trace, OR
- MAS < 0.10 across last N traces (rolling window), OR
- Never accessed in the last 30 days
"""

from datetime import datetime, timedelta

from cortexa.engine.models import Attribution, GhostToken, Memory, TraceResult


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    return max(1, len(text) // 4)


class GhostDetector:
    """Detects ghost tokens — memories that waste context with no contribution."""

    def __init__(
        self,
        ghost_threshold: float = 0.05,
        rolling_threshold: float = 0.10,
        inactive_days: int = 30,
    ) -> None:
        self.ghost_threshold = ghost_threshold
        self.rolling_threshold = rolling_threshold
        self.inactive_days = inactive_days

    def detect(
        self,
        memories: list[Memory],
        attributions: list[Attribution],
        recent_traces: list[TraceResult] | None = None,
    ) -> list[GhostToken]:
        """Detect ghost tokens in a set of memories.

        Args:
            memories: All memories that were retrieved/used.
            attributions: Attributions from the current trace.
            recent_traces: Optional rolling window of recent traces.
        """
        ghosts: list[GhostToken] = []
        now = datetime.utcnow()

        # Compute max MAS per memory in current trace
        current_max_mas: dict[str, float] = {}
        for attr in attributions:
            mid = attr.memory_id
            if mid not in current_max_mas or attr.mas_score > current_max_mas[mid]:
                current_max_mas[mid] = attr.mas_score

        # Compute rolling average MAS if traces provided
        rolling_avg_mas: dict[str, float] = {}
        if recent_traces:
            mas_sums: dict[str, list[float]] = {}
            for trace in recent_traces:
                trace_max: dict[str, float] = {}
                for attr in trace.attributions:
                    mid = attr.memory_id
                    if mid not in trace_max or attr.mas_score > trace_max[mid]:
                        trace_max[mid] = attr.mas_score
                for mid, score in trace_max.items():
                    mas_sums.setdefault(mid, []).append(score)
            for mid, scores in mas_sums.items():
                rolling_avg_mas[mid] = sum(scores) / len(scores)

        for memory in memories:
            max_mas = current_max_mas.get(memory.id, 0.0)
            waste = _estimate_tokens(memory.content)

            # Check 1: Low MAS in current trace
            if max_mas < self.ghost_threshold:
                ghosts.append(
                    GhostToken(
                        memory_id=memory.id,
                        max_mas=max_mas,
                        waste_tokens=waste,
                        reason=f"MAS {max_mas:.3f} < {self.ghost_threshold} in current trace",
                    )
                )
                continue

            # Check 2: Low rolling average MAS
            if memory.id in rolling_avg_mas:
                avg = rolling_avg_mas[memory.id]
                if avg < self.rolling_threshold:
                    ghosts.append(
                        GhostToken(
                            memory_id=memory.id,
                            max_mas=max_mas,
                            waste_tokens=waste,
                            reason=(
                                f"Rolling avg MAS {avg:.3f} < {self.rolling_threshold} "
                                f"across {len(recent_traces)} traces"
                            ),
                        )
                    )
                    continue

            # Check 3: Never accessed recently
            if memory.last_accessed is not None:
                days_since = (now - memory.last_accessed).days
                if days_since > self.inactive_days:
                    ghosts.append(
                        GhostToken(
                            memory_id=memory.id,
                            max_mas=max_mas,
                            waste_tokens=waste,
                            reason=f"Not accessed in {days_since} days (threshold: {self.inactive_days})",
                        )
                    )

        return ghosts

    def estimate_waste(
        self, ghosts: list[GhostToken], memories: list[Memory], queries_per_day: float = 100
    ) -> tuple[int, float]:
        """Estimate total token waste and monthly cost.

        Returns:
            (total_waste_tokens, monthly_cost_usd) at $0.01/1K tokens.
        """
        total_tokens = sum(g.waste_tokens for g in ghosts)
        monthly_cost = total_tokens * (0.01 / 1000) * queries_per_day * 30
        return total_tokens, round(monthly_cost, 2)
