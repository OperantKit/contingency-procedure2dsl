"""Layer 1: Parameter extraction (COD, LH, BO, FRCO) from text."""

from __future__ import annotations

from ..result import ExtractResult
from ..vocab_reverse import FRCO_PATTERN, PARAM_PATTERNS


def extract_params(text: str) -> list[ExtractResult]:
    """Extract schedule parameters (COD, LH, BO, FRCO) from text."""
    results: list[ExtractResult] = []

    for param_name, pattern in PARAM_PATTERNS.items():
        for m in pattern.finditer(text):
            # English groups: (1)=value, (2)=unit
            # Japanese postfix groups: (3)=value, (4)=unit
            # Japanese prefix groups: (5)=value, (6)=unit
            value = m.group(1) or m.group(3) or m.group(5)
            unit = m.group(2) or m.group(4) or m.group(6)
            if value is None:
                continue
            results.append(ExtractResult(
                ast={
                    "type": "ParamDecl",
                    "name": param_name,
                    "value": float(value),
                    "time_unit": unit or "s",
                },
                confidence=0.90,
                span=(m.start(), m.end()),
                source_text=m.group(0),
            ))

    # FRCO is count-based (no time unit)
    for m in FRCO_PATTERN.finditer(text):
        value = m.group(1) or m.group(2)
        if value is None:
            continue
        results.append(ExtractResult(
            ast={
                "type": "ParamDecl",
                "name": "FRCO",
                "value": float(value),
            },
            confidence=0.85,
            span=(m.start(), m.end()),
            source_text=m.group(0),
        ))

    return results
