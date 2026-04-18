"""Extraction pipeline: Layer 1 (rules) → Layer 2 (LLM) fallback.

The pipeline collects schedule candidates in roughly decreasing specificity
order. After a primary candidate has been chosen, the pipeline attaches
leaf-level properties (limitedHold / timeout / responseCost) that are
no longer represented as wrapper nodes in the current AST schema.
"""

from __future__ import annotations

from .extractors.annotations import (
    extract_apparatus_annotations,
    extract_component_annotations,
    extract_measurement_annotations,
    extract_procedure_annotations,
    extract_subject_annotations,
)
from .extractors.params import extract_params
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
from .result import ExtractionReport, ExtractResult


def extract_all(text: str) -> ExtractionReport:
    """Run the full Layer 1 extraction pipeline on text.

    Priority order (most specific first):
      1. Respondent primitives (Pair.*, Extinction, Contingency, ...)
      2. Trial-based (MTS, Go/NoGo — contain consequence sub-schedules)
      3. SecondOrder (two atomics in a specific structure)
      4. Modifier (DRL/DRH/DRO/PR/Lag/Pctl)
      5. Aversive (Sidman/DiscrimAv)
      6. Overlay (punishment superimposed on baseline)
      7. Compound (combinator + multiple atomics)
      8. Atomic (single schedule)
      9. Special (EXT, CRF)

    After picking a primary, ``attach_leaf_properties`` overlays any
    detected limitedHold / timeout / responseCost clauses onto the leaf
    node.
    """
    schedules: list[ExtractResult] = []

    resp = extract_respondent(text)
    if resp is not None:
        schedules.append(resp)

    tb = extract_trial_based(text)
    if tb is not None:
        schedules.append(tb)

    so = extract_second_order(text)
    if so is not None:
        schedules.append(so)

    mod = extract_modifier(text)
    if mod is not None:
        schedules.append(mod)

    av = extract_aversive(text)
    if av is not None:
        schedules.append(av)

    overlay = extract_overlay(text)
    if overlay is not None:
        schedules.append(overlay)

    adj = extract_adjusting(text)
    if adj is not None:
        schedules.append(adj)

    interlock = extract_interlocking(text)
    if interlock is not None:
        schedules.append(interlock)

    compound = extract_compound_schedule(text)
    if compound is not None:
        schedules.append(compound)

    # LH-augmented single atomic. This replaces the old LimitedHold wrapper
    # result; the output has limitedHold on the leaf.
    lh = extract_limited_hold(text)
    if lh is not None:
        schedules.append(lh)

    if not schedules:
        atomics = extract_atomic_schedules(text)
        schedules.extend(atomics)

    special = extract_special_schedule(text)
    if special is not None and not schedules:
        schedules.append(special)

    # Post-process: attach leaf-properties (limitedHold / timeout / responseCost)
    # to the highest-confidence candidate.
    if schedules:
        schedules = list(schedules)
        primary = max(range(len(schedules)), key=lambda i: schedules[i].confidence)
        sc = schedules[primary]
        new_ast = attach_leaf_properties(sc.ast, text)
        if new_ast is not sc.ast:
            schedules[primary] = ExtractResult(
                ast=new_ast, confidence=sc.confidence,
                span=sc.span, source_text=sc.source_text,
                warnings=sc.warnings,
            )

    # Parameters
    params = extract_params(text)

    # Annotations (all five JEAB categories)
    annotations: list[ExtractResult] = []
    annotations.extend(extract_subject_annotations(text))
    annotations.extend(extract_apparatus_annotations(text))
    annotations.extend(extract_measurement_annotations(text))
    annotations.extend(extract_procedure_annotations(text))
    annotations.extend(extract_component_annotations(text))

    return ExtractionReport(
        schedules=tuple(schedules),
        params=tuple(params),
        annotations=tuple(annotations),
    )


def extract_paper(text: str) -> ExtractResult | None:
    """Extract a ``Paper`` wrapper when the text contains multiple experiment
    headings ("Experiment 1", "EXPERIMENT 2", "Study 3", "実験1", ...).

    Returns ``None`` when fewer than two experiment headings are detected, so
    callers can fall back to ``extract_all`` / ``extract_phase_sequence`` for
    single-experiment papers. The returned AST conforms to
    ``contingency-dsl/schema/experiment/experiment.schema.json``::

        {"type": "Paper",
         "experiments": [{"type": "Experiment", "label": ..., "body": ...}, ...]}
    """
    from .extractors.experiment import extract_experiments

    experiments = extract_experiments(text)
    if len(experiments) < 2:
        return None

    ast = {
        "type": "Paper",
        "experiments": [r.ast for r in experiments],
    }
    confidence = min(r.confidence for r in experiments)
    return ExtractResult(
        ast=ast,
        confidence=confidence,
        span=(0, len(text)),
        source_text=text,
    )


def extract_all_with_fallback(
    text: str,
    *,
    model: str = "claude-sonnet-4-6",
    api_key: str | None = None,
    confidence_threshold: float = 0.5,
) -> ExtractionReport:
    """Layer 1 → Layer 2 fallback pipeline.

    Runs Layer 1 (regex) first. If no schedule is found or confidence
    is below threshold, falls back to Layer 2 (LLM).

    Requires: pip install contingency-dsl-reader[llm]
    """
    report = extract_all(text)

    primary = report.primary_schedule
    if primary is not None and primary.confidence >= confidence_threshold:
        return report

    from .extractors.llm import extract_schedule_llm
    llm_result = extract_schedule_llm(text, model=model, api_key=api_key)

    return ExtractionReport(
        schedules=(llm_result,),
        params=report.params,
        annotations=report.annotations,
    )
