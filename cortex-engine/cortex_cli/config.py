"""Configuration for CortexOS CLI — reads from env or CLI flags."""

from __future__ import annotations

import os


CORTEX_URL = os.environ.get("CORTEX_URL", "http://localhost:8000")
CORTEX_API_KEY = os.environ.get("CORTEX_API_KEY", os.environ.get("CORTEX_KEY", ""))
