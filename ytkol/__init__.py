"""YouTube KOL evaluator.

Public API:
    from ytkol import evaluate, calculate_metrics, score_and_verdict
"""

from ytkol.calculator import calculate_metrics
from ytkol.models import Metrics, Report, Sample, Verdict
from ytkol.verdict import score_and_verdict

__all__ = [
    "calculate_metrics",
    "score_and_verdict",
    "Metrics",
    "Report",
    "Sample",
    "Verdict",
]
__version__ = "0.1.0"
