"""contingency-dsl-reader: Extract contingency-dsl AST from academic paper text.

Layer 1 (rule-based, stdlib only):
    extract_schedule(text) -> ExtractResult
    extract_all(text) -> ExtractionReport
    extract_respondent(text) -> ExtractResult | None
    extract_phase_sequence(text) -> ExtractResult | None
    extract_experiments(text) -> list[ExtractResult]
    extract_paper(text) -> ExtractResult | None

Layer 2 (LLM, opt-in via `pip install contingency-dsl-reader[llm]`):
    extract_schedule_llm(text, model=...) -> ExtractResult
    extract_all_with_fallback(text, model=...) -> ExtractionReport
"""

from .extractors.experiment import extract_experiments
from .extractors.phase import extract_phase_sequence
from .extractors.respondent import extract_respondent
from .extractors.schedule import (
    attach_leaf_properties,
    extract_adjusting,
    extract_atomic_schedules,
    extract_aversive,
    extract_compound_schedule,
    extract_interlocking,
    extract_limited_hold,
    extract_modifier,
    extract_overlay,
    extract_second_order,
    extract_special_schedule,
    extract_trial_based,
)
from .pipeline import extract_all, extract_all_with_fallback, extract_paper
from .result import ExtractionReport, ExtractResult

__all__ = [
    # Pipeline
    "extract_all",
    "extract_all_with_fallback",
    "extract_paper",
    "extract_schedule",
    # Schedule extractors
    "extract_atomic_schedules",
    "extract_compound_schedule",
    "extract_limited_hold",
    "attach_leaf_properties",
    "extract_second_order",
    "extract_modifier",
    "extract_aversive",
    "extract_overlay",
    "extract_adjusting",
    "extract_interlocking",
    "extract_trial_based",
    "extract_special_schedule",
    # Respondent / Experiment
    "extract_respondent",
    "extract_phase_sequence",
    "extract_experiments",
    # Result types
    "ExtractResult",
    "ExtractionReport",
]


def extract_schedule(text: str) -> ExtractResult | None:
    """Convenience: extract the primary schedule from text.

    Uses Layer 1 (regex) only. For LLM fallback, use extract_all_with_fallback().
    Phase-aware extraction is available via extract_phase_sequence().
    """
    report = extract_all(text)
    return report.primary_schedule
