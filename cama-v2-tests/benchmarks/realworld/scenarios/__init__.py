"""Real-world stress test scenarios for CAMA v2."""

from .ecommerce import SCENARIO as ecommerce
from .healthcare import SCENARIO as healthcare
from .financial import SCENARIO as financial
from .legal import SCENARIO as legal
from .multiuser import SCENARIO as multiuser
from .retrieval_noise import SCENARIO as retrieval_noise
from .temporal import SCENARIO as temporal
from .adversarial_nearmiss import SCENARIO as adversarial_nearmiss

ALL_SCENARIOS = [
    ecommerce,
    healthcare,
    financial,
    legal,
    multiuser,
    retrieval_noise,
    temporal,
    adversarial_nearmiss,
]
