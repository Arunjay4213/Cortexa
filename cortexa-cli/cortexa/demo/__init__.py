"""Demo mode data — synthetic memory store and scenarios."""

from cortexa.demo.dataset import generate_demo_memories, get_planted_issue_ids
from cortexa.demo.scenarios import (
    SCENARIOS,
    DemoScenario,
    get_scenario,
    list_scenarios,
)

__all__ = [
    "generate_demo_memories",
    "get_planted_issue_ids",
    "SCENARIOS",
    "DemoScenario",
    "get_scenario",
    "list_scenarios",
]
