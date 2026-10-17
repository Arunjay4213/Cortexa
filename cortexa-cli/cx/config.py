"""Configuration management for Cortexa CLI."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


CONFIG_FILENAMES = [".cortexa.yml", ".cx.yml"]
GLOBAL_CONFIG_DIR = Path.home() / ".config" / "cortexa"
GLOBAL_CONFIG_PATH = GLOBAL_CONFIG_DIR / "config.yml"
EVENTS_DIR = Path.home() / ".cortexa"
EVENTS_LOG = EVENTS_DIR / "events.jsonl"


@dataclass
class CortexaConfig:
    """Runtime configuration for the CLI."""

    adapter: str = "demo"
    adapter_options: dict[str, Any] = field(default_factory=dict)
    api_key: str | None = None
    anthropic_api_key: str | None = None
    cortex_url: str = "https://api.cortexa.ink"
    telemetry: bool = False
    ghost_threshold: float = 0.05
    stale_days: int = 30

    @classmethod
    def load(cls) -> CortexaConfig:
        """Load config from project file, global file, then env vars."""
        data: dict[str, Any] = {}

        # Global config
        if GLOBAL_CONFIG_PATH.exists():
            with open(GLOBAL_CONFIG_PATH) as f:
                global_data = yaml.safe_load(f) or {}
                data.update(global_data)

        # Project-local config (overrides global)
        for name in CONFIG_FILENAMES:
            path = Path.cwd() / name
            if path.exists():
                with open(path) as f:
                    local_data = yaml.safe_load(f) or {}
                    data.update(local_data)
                break

        # Env var overrides
        if key := os.getenv("CORTEXA_API_KEY") or os.getenv("CORTEX_API_KEY"):
            data["api_key"] = key
        if key := os.getenv("ANTHROPIC_API_KEY"):
            data["anthropic_api_key"] = key
        if url := os.getenv("CORTEXA_URL") or os.getenv("CORTEX_URL"):
            data["cortex_url"] = url

        return cls(
            adapter=data.get("adapter", "demo"),
            adapter_options=data.get("adapter_options", {}),
            api_key=data.get("api_key"),
            anthropic_api_key=data.get("anthropic_api_key"),
            cortex_url=data.get("cortex_url", "https://api.cortexa.ink"),
            telemetry=data.get("telemetry", False),
            ghost_threshold=data.get("ghost_threshold", 0.05),
            stale_days=data.get("stale_days", 30),
        )

    def save_global(self) -> None:
        """Persist current config to the global config file."""
        GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "adapter": self.adapter,
            "adapter_options": self.adapter_options,
            "cortex_url": self.cortex_url,
            "telemetry": self.telemetry,
            "ghost_threshold": self.ghost_threshold,
            "stale_days": self.stale_days,
        }
        if self.api_key:
            data["api_key"] = self.api_key
        if self.anthropic_api_key:
            data["anthropic_api_key"] = self.anthropic_api_key
        with open(GLOBAL_CONFIG_PATH, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
