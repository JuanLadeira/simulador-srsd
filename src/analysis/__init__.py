"""Analysis and validation tools for SRSD experiments."""

from .comparator import (
    ComparisonResult,
    ResultComparator,
    statistical_significance,
)
from .validator import (
    ValidationStatus,
    ValidationCriteria,
    H1ValidationResult,
    H2ValidationResult,
    FullValidationResult,
    HypothesisValidator,
)

__all__ = [
    'ComparisonResult',
    'ResultComparator',
    'statistical_significance',
    'ValidationStatus',
    'ValidationCriteria',
    'H1ValidationResult',
    'H2ValidationResult',
    'FullValidationResult',
    'HypothesisValidator',
]
