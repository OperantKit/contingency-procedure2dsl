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
    annotations = _dedupe_annotations(annotations)

    return ExtractionReport(
        schedules=tuple(schedules),
        params=tuple(params),
        annotations=tuple(annotations),
    )


_SINGLETON_KEYWORDS = frozenset({
    # Subject-level facts that describe one cohort. When the Method text
    # mentions multiple values (typically from cross-study citations in the
    # Discussion), keep only the first mention so the paper-compile pass
    # produces a matching re-extraction on round-trip.
    "species", "strain", "n", "deprivation", "history", "population",
})


def _dedupe_annotations(anns: list[ExtractResult]) -> list[ExtractResult]:
    """Collapse duplicate annotations to the single highest-confidence hit.

    Two levels of dedup:

    1. Tuple-level: same (keyword, positional, params) → keep the highest
       confidence occurrence.
    2. Keyword-level (for singleton keywords only): multiple @species (or
       @strain, @n, ...) are collapsed to the first distinct value. This
       prevents a paper whose Discussion cites cross-species literature
       from producing a multi-@species Program whose compile → re-extract
       round-trip doesn't converge.

    Free-form list-style keywords (e.g. @reinforcer, @sd) are left alone.
    """
    import json as _json

    def _tuple_key(r: ExtractResult) -> str:
        ast = r.ast
        return _json.dumps(
            {k: ast.get(k) for k in ("keyword", "positional", "params")},
            sort_keys=True, ensure_ascii=False, default=str,
        )

    # Step 1: tuple-level dedup keeping best confidence.
    best: dict[str, ExtractResult] = {}
    for r in anns:
        key = _tuple_key(r)
        prior = best.get(key)
        if prior is None or r.confidence > prior.confidence:
            best[key] = r

    # Preserve first-appearance order when emitting.
    ordered: list[ExtractResult] = []
    seen_keys: set[str] = set()
    seen_singleton: set[str] = set()
    for r in anns:
        key = _tuple_key(r)
        if key in seen_keys:
            continue
        kw = r.ast.get("keyword", "")
        if kw in _SINGLETON_KEYWORDS and kw in seen_singleton:
            continue
        seen_keys.add(key)
        if kw in _SINGLETON_KEYWORDS:
            seen_singleton.add(kw)
        ordered.append(best[key])
    return ordered


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

    # Attach general-method preamble (text before the first Experiment
    # heading) as Paper-level shared annotations, so subject/apparatus
    # info described once at the top applies to every experiment.
    # Apply the same singleton-keyword collapse as extract_all so that
    # keys like ``n`` / ``species`` keep only the first value.
    preamble_end = experiments[0].span[0] if experiments[0].span else 0
    preamble = text[:preamble_end].strip()
    shared_annotations: list[dict] = []
    if preamble:
        from .extractors.annotations import (
            extract_subject_annotations,
            extract_apparatus_annotations,
        )
        raw = (
            extract_subject_annotations(preamble)
            + extract_apparatus_annotations(preamble)
        )
        shared_annotations = [r.ast for r in _dedupe_annotations(raw)]

    ast = {
        "type": "Paper",
        "experiments": [r.ast for r in experiments],
    }
    if shared_annotations:
        ast["shared_annotations"] = shared_annotations
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

    Requires: pip install contingency-procedure2dsl[llm]
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
