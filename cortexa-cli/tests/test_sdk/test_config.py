"""Tests for cortexa.sdk.config — CortexaConfig."""

import os
from pathlib import Path

import pytest

from cortexa.sdk.config import (
    BackendConfig,
    CortexaConfig,
    NLIConfig,
    ThresholdConfig,
)


class TestDefaults:
    def test_default_nli(self):
        config = CortexaConfig()
        assert config.nli.backend == "api"
        assert config.nli.model_name is None

    def test_default_thresholds(self):
        config = CortexaConfig()
        assert config.thresholds.ghost_mas == 0.05
        assert config.thresholds.contradiction == 0.7
        assert config.thresholds.staleness_days == 30
        assert config.thresholds.temperature == 0.5

    def test_default_backend(self):
        config = CortexaConfig()
        assert config.backend.type == "memory"
        assert config.backend.mem0_api_key is None

    def test_default_decompose_mode(self):
        config = CortexaConfig()
        assert config.decompose_mode == "fast"


class TestFromDict:
    def test_full_dict(self):
        data = {
            "decompose_mode": "thorough",
            "nli": {"backend": "local", "model_name": "custom-model"},
            "thresholds": {
                "ghost_mas": 0.10,
                "contradiction": 0.8,
                "staleness_days": 60,
                "temperature": 1.0,
            },
            "backend": {
                "type": "chromadb",
                "chromadb_collection": "test_col",
                "chromadb_path": "/tmp/test",
            },
        }
        config = CortexaConfig._from_dict(data)
        assert config.decompose_mode == "thorough"
        assert config.nli.backend == "local"
        assert config.nli.model_name == "custom-model"
        assert config.thresholds.ghost_mas == 0.10
        assert config.thresholds.staleness_days == 60
        assert config.backend.type == "chromadb"
        assert config.backend.chromadb_path == "/tmp/test"

    def test_partial_dict(self):
        data = {"nli": {"backend": "local"}}
        config = CortexaConfig._from_dict(data)
        assert config.nli.backend == "local"
        # Other sections should have defaults
        assert config.thresholds.ghost_mas == 0.05
        assert config.backend.type == "memory"

    def test_empty_dict(self):
        config = CortexaConfig._from_dict({})
        assert config.nli.backend == "api"
        assert config.backend.type == "memory"


class TestEnvOverrides:
    def test_nli_backend_override(self, monkeypatch):
        monkeypatch.setenv("CORTEXA_NLI_BACKEND", "local")
        config = CortexaConfig()
        config._apply_env_overrides()
        assert config.nli.backend == "local"

    def test_ghost_threshold_override(self, monkeypatch):
        monkeypatch.setenv("CORTEXA_GHOST_THRESHOLD", "0.10")
        config = CortexaConfig()
        config._apply_env_overrides()
        assert config.thresholds.ghost_mas == 0.10

    def test_staleness_days_override(self, monkeypatch):
        monkeypatch.setenv("CORTEXA_STALENESS_DAYS", "60")
        config = CortexaConfig()
        config._apply_env_overrides()
        assert config.thresholds.staleness_days == 60

    def test_backend_type_override(self, monkeypatch):
        monkeypatch.setenv("CORTEXA_BACKEND_TYPE", "chromadb")
        config = CortexaConfig()
        config._apply_env_overrides()
        assert config.backend.type == "chromadb"

    def test_decompose_mode_override(self, monkeypatch):
        monkeypatch.setenv("CORTEXA_DECOMPOSE_MODE", "thorough")
        config = CortexaConfig()
        config._apply_env_overrides()
        assert config.decompose_mode == "thorough"

    def test_mem0_api_key_override(self, monkeypatch):
        monkeypatch.setenv("CORTEXA_MEM0_API_KEY", "secret-key")
        config = CortexaConfig()
        config._apply_env_overrides()
        assert config.backend.mem0_api_key == "secret-key"


class TestLoadFromFile:
    def test_load_missing_file(self, tmp_path):
        config = CortexaConfig.load(tmp_path / "nonexistent.toml")
        # Should return defaults when file doesn't exist
        assert config.nli.backend == "api"

    def test_load_and_save_roundtrip(self, tmp_path):
        path = tmp_path / "config.toml"
        original = CortexaConfig(
            nli=NLIConfig(backend="local", model_name="test-model"),
            thresholds=ThresholdConfig(ghost_mas=0.10, staleness_days=60),
        )
        original.save(path)

        loaded = CortexaConfig.load(path)
        assert loaded.nli.backend == "local"
        assert loaded.nli.model_name == "test-model"
        assert loaded.thresholds.ghost_mas == 0.10
        assert loaded.thresholds.staleness_days == 60

    def test_save_creates_directory(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "config.toml"
        config = CortexaConfig()
        config.save(nested)
        assert nested.exists()

    def test_load_with_env_overlay(self, tmp_path, monkeypatch):
        path = tmp_path / "config.toml"
        config = CortexaConfig(nli=NLIConfig(backend="api"))
        config.save(path)

        # Env should override file
        monkeypatch.setenv("CORTEXA_NLI_BACKEND", "local")
        loaded = CortexaConfig.load(path)
        assert loaded.nli.backend == "local"


class TestSubconfigs:
    def test_nli_from_dict(self):
        c = NLIConfig.from_dict({"backend": "local", "model_name": "x"})
        assert c.backend == "local"
        assert c.model_name == "x"

    def test_threshold_from_dict(self):
        c = ThresholdConfig.from_dict({"ghost_mas": "0.1", "staleness_days": "60"})
        assert c.ghost_mas == 0.1
        assert c.staleness_days == 60

    def test_backend_from_dict(self):
        c = BackendConfig.from_dict({
            "type": "mem0",
            "mem0_api_key": "key123",
            "chromadb_port": "8000",
        })
        assert c.type == "mem0"
        assert c.mem0_api_key == "key123"
        assert c.chromadb_port == 8000
