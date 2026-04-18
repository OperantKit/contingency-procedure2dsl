"""Phase / PhaseSequence extraction from Method-section prose.

Detects multi-phase experimental designs (e.g., acquisition / extinction
/ renewal test in a Pavlovian extinction paper, or baseline / treatment /
reversal in a single-subject design). Splits the source text at phase
boundaries and feeds each segment back through ``extract_all`` to build
a ``PhaseSequence`` AST dict.

The output conforms to ``schema/experiment/phase-sequence.schema.json``:

    {"type": "PhaseSequence",
     "shared_annotations": [...],
     "shared_param_decls": [...],
     "phases": [{"type": "Phase", "label": ..., "schedule": ...,
                 "phase_annotations": [...], "criterion": {...}}, ...]}

Limitations: rule-based detection covers common phase labels (acquisition,
extinction, renewal test, baseline, treatment, reversal, DRL, etc.). For
ambiguous or novel labels, fall back to ``extract_all_with_fallback``.
"""

from __future__ import annotations

import re

from ..result import ExtractResult

# Pattern 1: explicit phase markers — "In the acquisition phase, ..."
#            "【獲得】..." or "獲得フェーズ..."
_PHASE_EN = re.compile(
    r"(?:In\s+the\s+|During\s+(?:the\s+)?)(?P<label>[A-Za-z][\w\s-]+?)\s+"
    r"phase\s*,\s*(?P<body>.+?)"
    r"(?=(?:In\s+the\s+|During\s+(?:the\s+)?)[A-Za-z][\w\s-]+?\s+phase\s*,|$)",
    re.IGNORECASE | re.DOTALL,
)

_PHASE_JA = re.compile(
    r"【(?P<label>[^】]+)】\s*(?P<body>.+?)(?=【[^】]+】|$)",
    re.DOTALL,
)

_CRITERION_FIXED_EN = re.compile(
    r"[Tt]his\s+phase\s+lasted\s+(\d+)\s+sessions",
)
_CRITERION_FIXED_JA = re.compile(r"本フェーズは(\d+)セッション実施した")

_CRITERION_STABILITY_EN = re.compile(
    r"until\s+(?:response\s+rates|reinforcement\s+rates|latencies|interresponse\s+times)\s+varied\s+by\s+no\s+more\s+than\s+"
    r"(\d+(?:\.\d+)?)\%\s+across\s+(\d+)\s+consecutive\s+sessions",
    re.IGNORECASE,
)
_CRITERION_STABILITY_JA = re.compile(
    r"直近(\d+)セッションの(\S+?)の変動が(\d+(?:\.\d+)?)%以内",
)


def detect_phase_boundaries(text: str) -> list[tuple[str, str]]:
    """Return a list of (label, body) pairs or [] if the text is mono-phase."""
    pairs: list[tuple[str, str]] = []

    for m in _PHASE_EN.finditer(text):
        label = m.group("label").strip()
        body = m.group("body").strip()
        if label and body:
            pairs.append((label, body))

    if pairs:
        return pairs

    for m in _PHASE_JA.finditer(text):
        label = m.group("label").strip()
        body = m.group("body").strip()
        if label and body:
            pairs.append((label, body))

    return pairs


def _detect_criterion(body: str) -> dict | None:
    m = _CRITERION_FIXED_EN.search(body) or _CRITERION_FIXED_JA.search(body)
    if m:
        return {"type": "FixedSessions", "count": int(m.group(1))}

    m = _CRITERION_STABILITY_EN.search(body)
    if m:
        return {
            "type": "Stability",
            "window_sessions": int(m.group(2)),
            "max_change_pct": float(m.group(1)),
            "measure": "rate",
        }
    m = _CRITERION_STABILITY_JA.search(body)
    if m:
        measure_ja = m.group(2)
        measure_map = {"反応率": "rate", "強化率": "reinforcers", "潜時": "latency", "反応間間隔": "iri"}
        return {
            "type": "Stability",
            "window_sessions": int(m.group(1)),
            "max_change_pct": float(m.group(3)),
            "measure": measure_map.get(measure_ja, "rate"),
        }

    if re.search(
        r"at\s+the\s+experimenter'?s\s+discretion|実験者の判断", body, re.IGNORECASE,
    ):
        return {"type": "ExperimenterJudgment"}

    return None


def extract_phase_sequence(text: str) -> ExtractResult | None:
    """Extract a PhaseSequence from multi-phase Method-section text.

    Returns None when the text does not appear to describe multiple phases.
    The caller can then fall back to single-Program extraction via
    ``extract_all``.
    """
    from .annotations import (
        extract_apparatus_annotations,
        extract_measurement_annotations,
        extract_procedure_annotations,
        extract_subject_annotations,
    )
    from ..pipeline import extract_all

    boundaries = detect_phase_boundaries(text)
    if len(boundaries) < 2:
        return None

    # Shared annotations come from the entire text (program-wide).
    shared_anns: list[dict] = []
    for r in extract_subject_annotations(text):
        shared_anns.append(r.ast)
    for r in extract_apparatus_annotations(text):
        shared_anns.append(r.ast)
    for r in extract_measurement_annotations(text):
        shared_anns.append(r.ast)
    for r in extract_procedure_annotations(text):
        shared_anns.append(r.ast)

    phases: list[dict] = []
    for label, body in boundaries:
        phase_report = extract_all(body)
        primary = phase_report.primary_schedule
        schedule = primary.ast if primary else None
        phase: dict = {
            "type": "Phase",
            "label": label,
            "schedule": schedule,
        }
        crit = _detect_criterion(body)
        if crit is not None:
            phase["criterion"] = crit
        phases.append(phase)

    ast = {
        "type": "PhaseSequence",
        "shared_annotations": shared_anns,
        "shared_param_decls": [],
        "phases": phases,
    }
    return ExtractResult(
        ast=ast,
        confidence=0.70,
        span=(0, len(text)),
        source_text=text,
    )
