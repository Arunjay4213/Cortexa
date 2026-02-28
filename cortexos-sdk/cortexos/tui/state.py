"""Central reactive state store for the CortexOS TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EventRecord:
    """Typed record parsed from an SSE event."""

    type: str  # "check" | "gate" | "shield"
    ts: datetime
    hi: float
    total_claims: int
    grounded: int
    hallucinated: int
    opinion_count: int
    latency_ms: float
    verdicts: list[str]
    claims: list[dict]
    api_key_id: str | None
    agent_id: str
    response_preview: str
    flagged: int
    flagged_claims: list[dict]
    suggested_corrections: list[dict] | None
    raw: dict

    @classmethod
    def from_sse(cls, data: dict) -> EventRecord | None:
        event_type = data.get("type", "")
        if event_type not in ("check", "gate", "shield"):
            return None
        try:
            ts = datetime.fromisoformat(data.get("ts", ""))
        except (ValueError, TypeError):
            ts = datetime.now()

        grounded_val = data.get("grounded", 0)
        # gate events use grounded as bool
        if isinstance(grounded_val, bool):
            grounded_int = 0
        else:
            grounded_int = int(grounded_val)

        return cls(
            type=event_type,
            ts=ts,
            hi=float(data.get("hi", 0.0)),
            total_claims=int(data.get("total_claims", 0)),
            grounded=grounded_int,
            hallucinated=int(data.get("hallucinated", 0)),
            opinion_count=int(data.get("opinion_count", 0)),
            latency_ms=float(data.get("latency_ms", 0)),
            verdicts=data.get("verdicts", []),
            claims=data.get("claims", []),
            api_key_id=data.get("api_key_id"),
            agent_id=data.get("agent_id", "unknown"),
            response_preview=data.get("response_preview", "")
            or data.get("candidate_preview", ""),
            flagged=int(data.get("flagged", 0)),
            flagged_claims=data.get("flagged_claims", []),
            suggested_corrections=data.get("suggested_corrections"),
            raw=data,
        )


@dataclass
class AgentStats:
    """Per-agent accumulated stats."""

    api_key_id: str
    checks: int = 0
    total_hi: float = 0.0
    total_hallucinated: int = 0
    total_claims: int = 0
    last_seen: datetime | None = None

    @property
    def avg_hi(self) -> float:
        return self.total_hi / self.checks if self.checks > 0 else 0.0

    @property
    def halluc_pct(self) -> float:
        return self.total_hallucinated / self.total_claims if self.total_claims > 0 else 0.0


@dataclass
class SessionState:
    """Accumulates events and computes derived metrics."""

    events: list[EventRecord] = field(default_factory=list)
    agents: dict[str, AgentStats] = field(default_factory=dict)
    _hi_values: list[float] = field(default_factory=list)
    _latencies: list[float] = field(default_factory=list)
    blocked_count: int = 0
    injection_count: int = 0

    def add_event(self, record: EventRecord) -> None:
        self.events.append(record)
        self._hi_values.append(record.hi)
        self._latencies.append(record.latency_ms)

        if record.type == "gate" and record.raw.get("grounded") is False:
            self.blocked_count += 1
        if record.type == "shield" and record.raw.get("safe") is False:
            self.injection_count += 1

        # Update agent stats (prefer agent_id, fall back to api_key_id)
        agent_id = record.agent_id if record.agent_id != "unknown" else (record.api_key_id or "unknown")
        if agent_id not in self.agents:
            self.agents[agent_id] = AgentStats(api_key_id=agent_id)
        agent = self.agents[agent_id]
        agent.checks += 1
        agent.total_hi += record.hi
        agent.total_hallucinated += record.hallucinated
        agent.total_claims += record.total_claims
        agent.last_seen = record.ts

    @property
    def total_checks(self) -> int:
        return len(self.events)

    @property
    def total_claims(self) -> int:
        return sum(e.total_claims for e in self.events)

    @property
    def total_grounded(self) -> int:
        return sum(e.grounded for e in self.events)

    @property
    def total_hallucinated(self) -> int:
        return sum(e.hallucinated for e in self.events)

    @property
    def avg_hi(self) -> float:
        return sum(self._hi_values) / len(self._hi_values) if self._hi_values else 0.0

    @property
    def avg_latency(self) -> float:
        return sum(self._latencies) / len(self._latencies) if self._latencies else 0.0

    @property
    def p95_latency(self) -> float:
        if not self._latencies:
            return 0.0
        s = sorted(self._latencies)
        idx = int(len(s) * 0.95)
        return s[min(idx, len(s) - 1)]

    @property
    def halluc_pct(self) -> float:
        tc = self.total_claims
        return self.total_hallucinated / tc if tc > 0 else 0.0

    @property
    def hi_trend(self) -> list[float]:
        return self._hi_values[-30:]

    def all_claims(self) -> list[tuple[EventRecord, dict]]:
        """Flatten all claims across all events."""
        result = []
        for event in self.events:
            for claim in event.claims:
                result.append((event, claim))
        return result

    def gate_events(self) -> list[EventRecord]:
        return [e for e in self.events if e.type in ("gate", "shield")]

    def clear(self) -> None:
        self.events.clear()
        self.agents.clear()
        self._hi_values.clear()
        self._latencies.clear()
        self.blocked_count = 0
        self.injection_count = 0
