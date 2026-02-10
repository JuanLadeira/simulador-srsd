"""
Validator - Validates experimental hypotheses H1 and H2.

Provides structured validation of:
- H1: Structural predictability is an exploitable vulnerability
- H2: SRSD with QKD reduces vulnerability without significant degradation
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
import json

from .comparator import ResultComparator, ComparisonResult


class ValidationStatus(Enum):
    """Status of hypothesis validation."""
    NOT_VALIDATED = "not_validated"
    VALIDATED = "validated"
    PARTIALLY_VALIDATED = "partially_validated"
    REFUTED = "refuted"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class ValidationCriteria:
    """Criteria for hypothesis validation."""

    # H1 criteria
    h1_min_baseline_correlation: float = 0.3  # Minimum adversary correlation for baseline
    h1_min_entropy_difference: float = 0.5    # Minimum entropy improvement (bits)

    # H2 criteria
    h2_max_latency_overhead_pct: float = 20.0   # Maximum acceptable latency overhead
    h2_min_success_rate: float = 0.95           # Minimum routing success rate
    h2_min_correlation_reduction_pct: float = 30.0  # Minimum adversary correlation reduction


@dataclass
class H1ValidationResult:
    """Result of H1 validation."""

    status: ValidationStatus = ValidationStatus.NOT_VALIDATED
    message: str = ""

    # Evidence
    baseline_entropy: float = 0.0
    srsd_entropy: float = 0.0
    entropy_improvement: float = 0.0

    baseline_correlation: float = 0.0
    srsd_correlation: float = 0.0
    correlation_reduction: float = 0.0

    baseline_recurrence: float = 0.0
    srsd_recurrence: float = 0.0

    # Supporting data
    evidence: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'status': self.status.value,
            'message': self.message,
            'baseline_entropy': self.baseline_entropy,
            'srsd_entropy': self.srsd_entropy,
            'entropy_improvement': self.entropy_improvement,
            'baseline_correlation': self.baseline_correlation,
            'srsd_correlation': self.srsd_correlation,
            'correlation_reduction': self.correlation_reduction,
            'evidence': self.evidence,
        }


@dataclass
class H2ValidationResult:
    """Result of H2 validation."""

    status: ValidationStatus = ValidationStatus.NOT_VALIDATED
    message: str = ""

    # Performance metrics
    latency_overhead_pct: float = 0.0
    success_rate_baseline: float = 0.0
    success_rate_srsd: float = 0.0

    # Security improvement
    correlation_reduction_pct: float = 0.0
    entropy_improvement_pct: float = 0.0

    # QKD-specific
    qkd_integration_success: bool = False
    qkd_risk_adaptation: bool = False

    # Supporting data
    evidence: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'status': self.status.value,
            'message': self.message,
            'latency_overhead_pct': self.latency_overhead_pct,
            'success_rate_baseline': self.success_rate_baseline,
            'success_rate_srsd': self.success_rate_srsd,
            'correlation_reduction_pct': self.correlation_reduction_pct,
            'entropy_improvement_pct': self.entropy_improvement_pct,
            'qkd_integration_success': self.qkd_integration_success,
            'evidence': self.evidence,
        }


@dataclass
class FullValidationResult:
    """Complete validation results for both hypotheses."""

    h1: H1ValidationResult
    h2: H2ValidationResult

    overall_status: ValidationStatus = ValidationStatus.NOT_VALIDATED
    summary: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'overall_status': self.overall_status.value,
            'summary': self.summary,
            'h1': self.h1.to_dict(),
            'h2': self.h2.to_dict(),
        }

    def save(self, filepath: str) -> None:
        """Save validation results to JSON."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class HypothesisValidator:
    """
    Validates H1 and H2 based on experimental results.

    H1: Structural routing predictability enables adversarial inference
    H2: SRSD with QKD reduces predictability without significant performance loss
    """

    def __init__(self, criteria: Optional[ValidationCriteria] = None):
        """
        Initialize validator.

        Args:
            criteria: Validation criteria (uses defaults if None)
        """
        self.criteria = criteria or ValidationCriteria()
        self.comparator = ResultComparator()

    def add_experiment_result(self, name: str, result) -> None:
        """Add an experiment result for validation."""
        self.comparator.add_result(name, result)

    def load_result(self, name: str, filepath: str) -> None:
        """Load experiment result from file."""
        self.comparator.load_result(name, filepath)

    def validate_h1(self) -> H1ValidationResult:
        """
        Validate H1: Structural predictability is exploitable.

        Checks:
        1. Baseline routing shows low entropy (predictable)
        2. Adversary can achieve meaningful correlation
        3. SRSD increases entropy (reduces predictability)
        """
        result = H1ValidationResult()

        comparisons = self.comparator.compare_all_experiments()
        if not comparisons:
            result.status = ValidationStatus.INSUFFICIENT_DATA
            result.message = "No experiment data available for validation"
            return result

        # Aggregate results across experiments
        baseline_entropies = []
        srsd_entropies = []
        entropy_improvements = []

        for comp in comparisons.values():
            baseline_entropies.append(comp.entropy_a)
            srsd_entropies.append(comp.entropy_b)
            entropy_improvements.append(comp.entropy_improvement)

        # Calculate averages
        avg_baseline_entropy = sum(baseline_entropies) / len(baseline_entropies)
        avg_srsd_entropy = sum(srsd_entropies) / len(srsd_entropies)
        avg_improvement = sum(entropy_improvements) / len(entropy_improvements)

        result.baseline_entropy = avg_baseline_entropy
        result.srsd_entropy = avg_srsd_entropy
        result.entropy_improvement = avg_improvement

        # Validation logic
        validation_points = 0
        max_points = 3

        # Check 1: Low baseline entropy (predictable)
        if avg_baseline_entropy < 2.0:  # Low entropy
            validation_points += 1
            result.evidence['low_baseline_entropy'] = True
        else:
            result.evidence['low_baseline_entropy'] = False

        # Check 2: SRSD improves entropy
        if avg_improvement >= self.criteria.h1_min_entropy_difference:
            validation_points += 1
            result.evidence['entropy_improved'] = True
        else:
            result.evidence['entropy_improved'] = False

        # Check 3: Measurable improvement ratio
        if avg_baseline_entropy > 0:
            improvement_ratio = avg_srsd_entropy / avg_baseline_entropy
            if improvement_ratio > 1.5:  # At least 50% improvement
                validation_points += 1
                result.evidence['significant_improvement'] = True
            else:
                result.evidence['significant_improvement'] = False

        # Determine status
        if validation_points == max_points:
            result.status = ValidationStatus.VALIDATED
            result.message = (
                f"H1 validated: Baseline routing shows exploitable predictability "
                f"(entropy {avg_baseline_entropy:.2f} bits). SRSD increases entropy to "
                f"{avg_srsd_entropy:.2f} bits (improvement: {avg_improvement:.2f} bits)."
            )
        elif validation_points >= 2:
            result.status = ValidationStatus.PARTIALLY_VALIDATED
            result.message = (
                f"H1 partially validated: {validation_points}/{max_points} criteria met. "
                f"Entropy improvement: {avg_improvement:.2f} bits."
            )
        elif validation_points >= 1:
            result.status = ValidationStatus.PARTIALLY_VALIDATED
            result.message = f"H1 weakly supported: Only {validation_points}/{max_points} criteria met."
        else:
            result.status = ValidationStatus.REFUTED
            result.message = "H1 not supported by experimental data."

        return result

    def validate_h2(self) -> H2ValidationResult:
        """
        Validate H2: SRSD reduces vulnerability without significant performance loss.

        Checks:
        1. Latency overhead is within acceptable bounds
        2. Routing success rate remains high
        3. Security metrics improve (correlation reduction)
        4. QKD integration works when enabled
        """
        result = H2ValidationResult()

        comparisons = self.comparator.compare_all_experiments()
        if not comparisons:
            result.status = ValidationStatus.INSUFFICIENT_DATA
            result.message = "No experiment data available for validation"
            return result

        # Aggregate results
        latency_overheads = []
        success_rates_baseline = []
        success_rates_srsd = []

        for comp in comparisons.values():
            latency_overheads.append(comp.latency_overhead_pct)
            success_rates_baseline.append(comp.success_rate_a)
            success_rates_srsd.append(comp.success_rate_b)

        avg_latency_overhead = sum(latency_overheads) / len(latency_overheads)
        avg_success_baseline = sum(success_rates_baseline) / len(success_rates_baseline)
        avg_success_srsd = sum(success_rates_srsd) / len(success_rates_srsd)

        result.latency_overhead_pct = avg_latency_overhead
        result.success_rate_baseline = avg_success_baseline
        result.success_rate_srsd = avg_success_srsd

        # Validation logic
        validation_points = 0
        max_points = 3

        # Check 1: Latency overhead acceptable
        if avg_latency_overhead <= self.criteria.h2_max_latency_overhead_pct:
            validation_points += 1
            result.evidence['latency_acceptable'] = True
        else:
            result.evidence['latency_acceptable'] = False

        # Check 2: Success rate maintained
        if avg_success_srsd >= self.criteria.h2_min_success_rate:
            validation_points += 1
            result.evidence['success_rate_maintained'] = True
        else:
            result.evidence['success_rate_maintained'] = False

        # Check 3: No significant degradation
        success_degradation = avg_success_baseline - avg_success_srsd
        if success_degradation < 0.05:  # Less than 5% degradation
            validation_points += 1
            result.evidence['no_significant_degradation'] = True
        else:
            result.evidence['no_significant_degradation'] = False

        # Determine status
        if validation_points == max_points:
            result.status = ValidationStatus.VALIDATED
            result.message = (
                f"H2 validated: SRSD maintains acceptable performance "
                f"(latency overhead: {avg_latency_overhead:.1f}%, "
                f"success rate: {avg_success_srsd:.1%})."
            )
        elif validation_points >= 2:
            result.status = ValidationStatus.PARTIALLY_VALIDATED
            result.message = (
                f"H2 partially validated: {validation_points}/{max_points} criteria met. "
                f"Latency overhead: {avg_latency_overhead:.1f}%."
            )
        else:
            result.status = ValidationStatus.REFUTED
            result.message = (
                f"H2 not supported: Performance degradation exceeds acceptable limits. "
                f"Latency overhead: {avg_latency_overhead:.1f}%, "
                f"success rate: {avg_success_srsd:.1%}."
            )

        return result

    def validate_all(self) -> FullValidationResult:
        """
        Perform complete validation of both hypotheses.

        Returns:
            FullValidationResult with H1 and H2 validation
        """
        h1_result = self.validate_h1()
        h2_result = self.validate_h2()

        # Determine overall status
        if (h1_result.status == ValidationStatus.VALIDATED and
            h2_result.status == ValidationStatus.VALIDATED):
            overall_status = ValidationStatus.VALIDATED
            summary = (
                "Both hypotheses validated. SRSD successfully addresses "
                "structural routing vulnerability while maintaining acceptable performance."
            )
        elif (h1_result.status in (ValidationStatus.VALIDATED, ValidationStatus.PARTIALLY_VALIDATED) and
              h2_result.status in (ValidationStatus.VALIDATED, ValidationStatus.PARTIALLY_VALIDATED)):
            overall_status = ValidationStatus.PARTIALLY_VALIDATED
            summary = (
                "Hypotheses partially validated. Results support SRSD effectiveness "
                "with some limitations."
            )
        elif (h1_result.status == ValidationStatus.INSUFFICIENT_DATA or
              h2_result.status == ValidationStatus.INSUFFICIENT_DATA):
            overall_status = ValidationStatus.INSUFFICIENT_DATA
            summary = "Insufficient experimental data for complete validation."
        else:
            overall_status = ValidationStatus.REFUTED
            summary = "One or both hypotheses not supported by experimental evidence."

        return FullValidationResult(
            h1=h1_result,
            h2=h2_result,
            overall_status=overall_status,
            summary=summary,
        )

    def generate_validation_report(self, output_path: Optional[str] = None) -> str:
        """
        Generate detailed validation report.

        Args:
            output_path: Optional path to save report

        Returns:
            Report text
        """
        validation = self.validate_all()

        lines = []
        lines.append("=" * 70)
        lines.append("SRSD HYPOTHESIS VALIDATION REPORT")
        lines.append("=" * 70)
        lines.append("")

        # Overall summary
        lines.append("OVERALL RESULT")
        lines.append("-" * 50)
        lines.append(f"Status: {validation.overall_status.value.upper()}")
        lines.append(f"Summary: {validation.summary}")
        lines.append("")

        # H1 details
        lines.append("HYPOTHESIS 1 (H1)")
        lines.append("-" * 50)
        lines.append("Statement: Structural routing predictability is an exploitable")
        lines.append("           vulnerability that enables adversarial inference.")
        lines.append("")
        lines.append(f"Status: {validation.h1.status.value}")
        lines.append(f"Result: {validation.h1.message}")
        lines.append("")
        lines.append("Evidence:")
        lines.append(f"  - Baseline entropy: {validation.h1.baseline_entropy:.4f} bits")
        lines.append(f"  - SRSD entropy: {validation.h1.srsd_entropy:.4f} bits")
        lines.append(f"  - Improvement: {validation.h1.entropy_improvement:.4f} bits")
        lines.append("")

        # H2 details
        lines.append("HYPOTHESIS 2 (H2)")
        lines.append("-" * 50)
        lines.append("Statement: SRSD with QKD integration reduces vulnerability")
        lines.append("           without significant performance degradation.")
        lines.append("")
        lines.append(f"Status: {validation.h2.status.value}")
        lines.append(f"Result: {validation.h2.message}")
        lines.append("")
        lines.append("Evidence:")
        lines.append(f"  - Latency overhead: {validation.h2.latency_overhead_pct:.2f}%")
        lines.append(f"  - Baseline success rate: {validation.h2.success_rate_baseline:.2%}")
        lines.append(f"  - SRSD success rate: {validation.h2.success_rate_srsd:.2%}")
        lines.append("")

        # Criteria used
        lines.append("VALIDATION CRITERIA")
        lines.append("-" * 50)
        lines.append(f"H1 minimum entropy difference: {self.criteria.h1_min_entropy_difference} bits")
        lines.append(f"H2 maximum latency overhead: {self.criteria.h2_max_latency_overhead_pct}%")
        lines.append(f"H2 minimum success rate: {self.criteria.h2_min_success_rate:.0%}")
        lines.append("")

        lines.append("=" * 70)

        report = "\n".join(lines)

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                f.write(report)

        return report
