"""Configuration management — ~/.cortexa/config.toml.

Hierarchy (highest priority wins):
1. Explicit kwargs to CortexaConfig()
2. Environment variables: CORTEXA_<SECTION>_<KEY> (e.g. CORTEXA_NLI_BACKEND)
3. Config file: ~/.cortexa/config.toml
4. Built-in defaults
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from cortexa.engine.exceptions import ConfigError

# Default config directory
_DEFAULT_CONFIG_DIR = Path.home() / ".cortexa"
_DEFAULT_CONFIG_FILE = _DEFAULT_CONFIG_DIR / "config.toml"

_ENV_PREFIX = "CORTEXA_"


@dataclass
class NLIConfig:
    """NLI entailment engine settings."""

    backend: str = "api"  # "local" | "api"
    model_name: str | None = None  # override for local backend

    @classmethod
    def from_dict(cls, data: dict) -> NLIConfig:
        return cls(
            backend=data.get("backend", cls.backend),
            model_name=data.get("model_name"),
        )


@dataclass
class ThresholdConfig:
    """Tunable scoring thresholds."""

    ghost_mas: float = 0.05
    contradiction: float = 0.7
    staleness_days: int = 30
    temperature: float = 0.5

    @classmethod
    def from_dict(cls, data: dict) -> ThresholdConfig:
        return cls(
            ghost_mas=float(data.get("ghost_mas", cls.ghost_mas)),
            contradiction=float(data.get("contradiction", cls.contradiction)),
            staleness_days=int(data.get("staleness_days", cls.staleness_days)),
            temperature=float(data.get("temperature", cls.temperature)),
        )


@dataclass
class BackendConfig:
    """Memory backend settings."""

    type: str = "memory"  # "memory" | "mem0" | "chromadb"
    # Mem0 settings
    mem0_api_key: str | None = None
    mem0_org_id: str | None = None
    mem0_project_id: str | None = None
    # ChromaDB settings
    chromadb_host: str | None = None
    chromadb_port: int | None = None
    chromadb_collection: str = "cortexa_memories"
    chromadb_path: str | None = None  # for persistent local ChromaDB

    @classmethod
    def from_dict(cls, data: dict) -> BackendConfig:
        return cls(
            type=data.get("type", cls.type),
            mem0_api_key=data.get("mem0_api_key"),
            mem0_org_id=data.get("mem0_org_id"),
            mem0_project_id=data.get("mem0_project_id"),
            chromadb_host=data.get("chromadb_host"),
            chromadb_port=int(data["chromadb_port"]) if data.get("chromadb_port") else None,
            chromadb_collection=data.get("chromadb_collection", cls.chromadb_collection),
            chromadb_path=data.get("chromadb_path"),
        )


@dataclass
class CortexaConfig:
    """Root configuration — aggregates all config sections."""

    nli: NLIConfig = field(default_factory=NLIConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    backend: BackendConfig = field(default_factory=BackendConfig)
    decompose_mode: str = "fast"

    @classmethod
    def load(cls, config_path: Path | str | None = None) -> CortexaConfig:
        """Load config from TOML file, then overlay environment variables.

        Args:
            config_path: Path to config file. Defaults to ~/.cortexa/config.toml.
                        If the file doesn't exist, returns defaults.
        """
        path = Path(config_path) if config_path else _DEFAULT_CONFIG_FILE

        file_data: dict = {}
        if path.exists():
            file_data = _load_toml(path)

        config = cls._from_dict(file_data)
        config._apply_env_overrides()
        return config

    @classmethod
    def _from_dict(cls, data: dict) -> CortexaConfig:
        return cls(
            nli=NLIConfig.from_dict(data.get("nli", {})),
            thresholds=ThresholdConfig.from_dict(data.get("thresholds", {})),
            backend=BackendConfig.from_dict(data.get("backend", {})),
            decompose_mode=data.get("decompose_mode", cls.decompose_mode),
        )

    def _apply_env_overrides(self) -> None:
        """Override config values from CORTEXA_ environment variables."""
        env_map = {
            "CORTEXA_NLI_BACKEND": ("nli", "backend"),
            "CORTEXA_NLI_MODEL_NAME": ("nli", "model_name"),
            "CORTEXA_GHOST_THRESHOLD": ("thresholds", "ghost_mas"),
            "CORTEXA_CONTRADICTION_THRESHOLD": ("thresholds", "contradiction"),
            "CORTEXA_STALENESS_DAYS": ("thresholds", "staleness_days"),
            "CORTEXA_TEMPERATURE": ("thresholds", "temperature"),
            "CORTEXA_BACKEND_TYPE": ("backend", "type"),
            "CORTEXA_MEM0_API_KEY": ("backend", "mem0_api_key"),
            "CORTEXA_MEM0_ORG_ID": ("backend", "mem0_org_id"),
            "CORTEXA_MEM0_PROJECT_ID": ("backend", "mem0_project_id"),
            "CORTEXA_CHROMADB_HOST": ("backend", "chromadb_host"),
            "CORTEXA_CHROMADB_PORT": ("backend", "chromadb_port"),
            "CORTEXA_CHROMADB_COLLECTION": ("backend", "chromadb_collection"),
            "CORTEXA_CHROMADB_PATH": ("backend", "chromadb_path"),
            "CORTEXA_DECOMPOSE_MODE": (None, "decompose_mode"),
        }

        for env_key, (section, attr) in env_map.items():
            value = os.environ.get(env_key)
            if value is None:
                continue

            if section is None:
                # Top-level attribute
                setattr(self, attr, value)
            else:
                sub = getattr(self, section)
                current = getattr(sub, attr)
                # Cast to match the type of the default
                if isinstance(current, int):
                    value = int(value)
                elif isinstance(current, float):
                    value = float(value)
                setattr(sub, attr, value)

    def save(self, config_path: Path | str | None = None) -> None:
        """Save current config to a TOML file.

        Creates the config directory if it doesn't exist.
        """
        path = Path(config_path) if config_path else _DEFAULT_CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = ['# Cortexa configuration\n', '# Generated by cortexa\n\n']

        lines.append(f'decompose_mode = "{self.decompose_mode}"\n\n')

        lines.append("[nli]\n")
        lines.append(f'backend = "{self.nli.backend}"\n')
        if self.nli.model_name:
            lines.append(f'model_name = "{self.nli.model_name}"\n')
        lines.append("\n")

        lines.append("[thresholds]\n")
        lines.append(f"ghost_mas = {self.thresholds.ghost_mas}\n")
        lines.append(f"contradiction = {self.thresholds.contradiction}\n")
        lines.append(f"staleness_days = {self.thresholds.staleness_days}\n")
        lines.append(f"temperature = {self.thresholds.temperature}\n")
        lines.append("\n")

        lines.append("[backend]\n")
        lines.append(f'type = "{self.backend.type}"\n')
        if self.backend.mem0_api_key:
            lines.append(f'mem0_api_key = "{self.backend.mem0_api_key}"\n')
        if self.backend.chromadb_collection != "cortexa_memories":
            lines.append(f'chromadb_collection = "{self.backend.chromadb_collection}"\n')
        if self.backend.chromadb_path:
            lines.append(f'chromadb_path = "{self.backend.chromadb_path}"\n')

        path.write_text("".join(lines))


def _load_toml(path: Path) -> dict:
    """Load a TOML file, using tomllib (3.11+) or tomli fallback."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            raise ConfigError(
                "Python 3.10 requires the 'tomli' package for TOML support. "
                "Install with: pip install tomli"
            )

    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        raise ConfigError(f"Failed to load config from {path}: {e}")
