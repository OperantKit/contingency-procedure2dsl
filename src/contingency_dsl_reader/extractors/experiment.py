"""Experiment segmentation for multi-experiment papers.

Detects ``Experiment N`` / ``EXPERIMENT N`` / ``Study N`` / ``実験N`` section
headings and splits the source document into independent experiment
segments. Each segment is fed back through the standard extraction pipeline
(phase-aware first, single-Program otherwise) and wrapped in an
``Experiment`` AST node.

Output conforms to ``contingency-dsl/schema/experiment/experiment.schema.json``:

    {"type": "Experiment",
     "label": "Experiment 1",
     "body": <Program | PhaseSequence>}

The paper-level wrapper (``{"type": "Paper", "experiments": [...]}``) is
assembled by ``pipeline.extract_paper``, which returns ``None`` for
mono-experiment inputs to preserve back-compat with ``extract_all``.
"""

from __future__ import annotations

import re

from ..result import ExtractResult

# Whitespace class covering ASCII space/tab, NBSP (U+00A0 — common in
# PDF-extracted text between a word and a number), and ideographic space
# (U+3000 — common in Japanese prose).
_WS = r"[ \t\u00A0\u3000]"

# Heading line: optional markdown prefix, one of the label words, a number
# with optional alphabetic suffix (e.g. "2a"), trailing punctuation.
# Anchored with ^ and (\r?)$ under MULTILINE so inline mentions inside prose
# ("as shown in Experiment 1, ...") are ignored and CRLF line endings match.
# The trailing group allows either nothing, a lone period, or a colon
# followed by a subtitle ("Experiment 1: Autoshaping"). Sentence-style
# continuations ("Experiment 1 was successful.") are rejected because the
# char after the number must be whitespace+terminator or ./:subtitle.
_HEADING = re.compile(
    rf"^{_WS}*"
    r"(?:#{1,6}[ \t]+)?"
    r"(?P<label>"
    r"(?:EXPERIMENT|Experiment|Study|実験|研究)"
    rf"{_WS}*[0-9]+[A-Za-z]*"
    r")"
    rf"{_WS}*"
    r"(?:\.|:[^\n\r]*)?"
    rf"{_WS}*\r?$",
    re.MULTILINE,
)


def detect_experiment_boundaries(text: str) -> list[tuple[str, str]]:
    """Return ``(label, body)`` pairs for each detected experiment heading.

    Returns an empty list when the text contains no heading-style experiment
    markers. A single detected heading yields a single pair — the caller
    decides whether that is a Paper or a bare Program.
    """
    matches = list(_HEADING.finditer(text))
    if not matches:
        return []

    pairs: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        label = _normalize_label(m.group("label"))
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        pairs.append((label, body))
    return pairs


def _normalize_label(raw: str) -> str:
    """Collapse internal whitespace so 'Experiment  1' and 'EXPERIMENT\\t1'
    produce the same canonical label while preserving case. NBSP and
    ideographic space are folded to ASCII space."""
    return re.sub(r"[ \t\u00A0\u3000]+", " ", raw.strip())


def extract_experiments(text: str) -> list[ExtractResult]:
    """Return one ``ExtractResult`` per detected experiment, each wrapping an
    ``Experiment`` AST dict. Empty list when no experiment headings found.

    Each result's ``span`` covers the body segment (not the full text) so
    that callers can correlate back to the source positions. When the body
    has no extractable schedule, the body still resolves to a well-formed
    ``{"type": "Program", "schedule": {}, ...}`` via ``to_program``, keeping
    the output shape stable for downstream compilers.
    """
    matches = list(_HEADING.finditer(text))
    if not matches:
        return []

    results: list[ExtractResult] = []
    for i, m in enumerate(matches):
        label = _normalize_label(m.group("label"))
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        body_ast = _compile_body(body)
        ast = {
            "type": "Experiment",
            "label": label,
            "body": body_ast,
        }
        results.append(
            ExtractResult(
                ast=ast,
                confidence=0.70,
                span=(body_start, body_end),
                source_text=body,
            )
        )
    return results


def _compile_body(body: str) -> dict:
    """Pick Program vs PhaseSequence for a single experiment segment.

    Phase-aware extraction takes priority: a segment that itself describes
    multiple phases becomes a PhaseSequence. Otherwise the segment is
    compiled to a Program via ``ExtractionReport.to_program``.
    """
    from ..pipeline import extract_all
    from .phase import extract_phase_sequence

    phase_seq = extract_phase_sequence(body)
    if phase_seq is not None:
        return phase_seq.ast
    return extract_all(body).to_program()
