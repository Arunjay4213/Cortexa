"""Custom exception classes for the engine."""


class CortexaError(Exception):
    """Base exception for all Cortexa errors."""


class ModelNotFoundError(CortexaError):
    """NLI model not found or not downloaded."""


class ModelLoadError(CortexaError):
    """Failed to load the NLI model."""


class DecompositionError(CortexaError):
    """Failed to decompose response into claims."""


class EntailmentError(CortexaError):
    """Failed to compute entailment scores."""


class BackendError(CortexaError):
    """Memory backend connection or query error."""


class ConfigError(CortexaError):
    """Invalid or missing configuration."""
