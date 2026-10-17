"""Cortexa — Memory intelligence platform for AI agents."""

__version__ = "0.1.0"

from cortexa.sdk.client import Cortexa
from cortexa.sdk.config import CortexaConfig

__all__ = ["Cortexa", "CortexaConfig", "__version__"]
