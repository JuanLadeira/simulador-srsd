"""Adversary modeling and metrics."""

from .observer import (
    Observation,
    FlowCorrelation,
    StructuralObserver,
    TimingAnalyzer,
    PathInferenceEngine,
)
from .metrics import (
    CorrelationMetrics,
    FingerprintingMetrics,
    AdversaryCapabilityMetrics,
    calculate_path_entropy,
    calculate_normalized_entropy,
    calculate_recurrence_rate,
    calculate_flow_identification_rate,
    calculate_adversary_advantage,
)

__all__ = [
    'Observation',
    'FlowCorrelation',
    'StructuralObserver',
    'TimingAnalyzer',
    'PathInferenceEngine',
    'CorrelationMetrics',
    'FingerprintingMetrics',
    'AdversaryCapabilityMetrics',
    'calculate_path_entropy',
    'calculate_normalized_entropy',
    'calculate_recurrence_rate',
    'calculate_flow_identification_rate',
    'calculate_adversary_advantage',
]
