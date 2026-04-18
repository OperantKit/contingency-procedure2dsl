"""Respondent (Pavlovian) primitive extraction from Method-section prose.

Recovers Tier A primitives (R1-R14) defined in schema/respondent/ast.schema.json
from English and Japanese source text using rule-based matches. The
extractors produce AST dicts matching the respondent schema (e.g.
``{"type": "PairForwardDelay", "cs": "tone", "us": "shock", ...}``).
"""

from __future__ import annotations

import re

from ..result import ExtractResult

_DUR = r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)"


def _duration(value: str, unit: str) -> dict:
    return {"value": float(value), "unit": unit}


def _ident(s: str) -> str:
    """Normalize a CS/US label back to an identifier-like token."""
    return s.strip().replace(" ", "_").lower()


# --- R1: ForwardDelay ------------------------------------------------------

_FD_EN = re.compile(
    r"(\w+)\s+served\s+as\s+the\s+conditioned\s+stimulus\s+and\s+(\w+)\s+as\s+"
    r"the\s+unconditioned\s+stimulus\s+in\s+a\s+forward-delay\s+pairing\s+procedure\s+"
    rf"\(CS-US\s+interval\s+{_DUR};\s*CS\s+duration\s+{_DUR}\)",
    re.IGNORECASE,
)
_FD_JA = re.compile(
    r"(\S+?)を条件刺激、(\S+?)を無条件刺激とする順行遅延対呈示を実施した"
    rf"（CS-US\s*間隔\s*{_DUR}、CS\s*持続\s*{_DUR}）",
)


def extract_pair_forward_delay(text: str) -> ExtractResult | None:
    m = _FD_EN.search(text)
    if m:
        ast = {
            "type": "PairForwardDelay",
            "cs": _ident(m.group(1)),
            "us": _ident(m.group(2)),
            "isi": _duration(m.group(3), m.group(4)),
            "cs_duration": _duration(m.group(5), m.group(6)),
        }
        return ExtractResult(ast=ast, confidence=0.85,
                             span=(m.start(), m.end()), source_text=m.group(0))
    m = _FD_JA.search(text)
    if m:
        ast = {
            "type": "PairForwardDelay",
            "cs": _ident(m.group(1)),
            "us": _ident(m.group(2)),
            "isi": _duration(m.group(3), m.group(4)),
            "cs_duration": _duration(m.group(5), m.group(6)),
        }
        return ExtractResult(ast=ast, confidence=0.85,
                             span=(m.start(), m.end()), source_text=m.group(0))
    return None


# --- R2: ForwardTrace ------------------------------------------------------

_FT_EN = re.compile(
    r"(\w+)\s+served\s+as\s+the\s+conditioned\s+stimulus\s+and\s+(\w+)\s+as\s+the\s+"
    r"unconditioned\s+stimulus\s+in\s+a\s+forward-trace\s+pairing\s+procedure\s+"
    rf"\(trace\s+interval\s+{_DUR}(?:;\s*CS\s+duration\s+{_DUR})?\)",
    re.IGNORECASE,
)
_FT_JA = re.compile(
    r"(\S+?)を条件刺激、(\S+?)を無条件刺激とする順行トレース対呈示を実施した"
    rf"（トレース間隔\s*{_DUR}(?:、CS\s*持続\s*{_DUR})?）",
)


def extract_pair_forward_trace(text: str) -> ExtractResult | None:
    m = _FT_EN.search(text)
    if m:
        ast = {
            "type": "PairForwardTrace",
            "cs": _ident(m.group(1)),
            "us": _ident(m.group(2)),
            "trace_interval": _duration(m.group(3), m.group(4)),
        }
        if m.group(5):
            ast["cs_duration"] = _duration(m.group(5), m.group(6))
        return ExtractResult(ast=ast, confidence=0.85,
                             span=(m.start(), m.end()), source_text=m.group(0))
    m = _FT_JA.search(text)
    if m:
        ast = {
            "type": "PairForwardTrace",
            "cs": _ident(m.group(1)),
            "us": _ident(m.group(2)),
            "trace_interval": _duration(m.group(3), m.group(4)),
        }
        if m.group(5):
            ast["cs_duration"] = _duration(m.group(5), m.group(6))
        return ExtractResult(ast=ast, confidence=0.85,
                             span=(m.start(), m.end()), source_text=m.group(0))
    return None


# --- R3: Simultaneous ------------------------------------------------------

_SIM_EN = re.compile(
    r"(\w+)\s+and\s+(\w+)\s+were\s+presented\s+simultaneously\s+in\s+a\s+"
    r"Pavlovian\s+pairing\s+procedure",
    re.IGNORECASE,
)
_SIM_JA = re.compile(r"(\S+?)と(\S+?)の同時対呈示を実施した")


def extract_pair_simultaneous(text: str) -> ExtractResult | None:
    m = _SIM_EN.search(text) or _SIM_JA.search(text)
    if m is None:
        return None
    ast = {
        "type": "PairSimultaneous",
        "cs": _ident(m.group(1)),
        "us": _ident(m.group(2)),
    }
    return ExtractResult(ast=ast, confidence=0.85,
                         span=(m.start(), m.end()), source_text=m.group(0))


# --- R4: Backward ----------------------------------------------------------

_BW_EN = re.compile(
    r"(\w+)\s+was\s+followed\s+by\s+(\w+)\s+in\s+a\s+backward\s+pairing\s+procedure\s+"
    rf"\(US-CS\s+interval\s+{_DUR}\)",
    re.IGNORECASE,
)
_BW_JA = re.compile(
    rf"(\S+?)の直後に(\S+?)を呈示する逆行対呈示を実施した（US-CS\s*間隔\s*{_DUR}）",
)


def extract_pair_backward(text: str) -> ExtractResult | None:
    m = _BW_EN.search(text) or _BW_JA.search(text)
    if m is None:
        return None
    ast = {
        "type": "PairBackward",
        "us": _ident(m.group(1)),
        "cs": _ident(m.group(2)),
        "isi": _duration(m.group(3), m.group(4)),
    }
    return ExtractResult(ast=ast, confidence=0.85,
                         span=(m.start(), m.end()), source_text=m.group(0))


# --- R5: Extinction --------------------------------------------------------

def extract_resp_extinction(text: str) -> ExtractResult | None:
    m = re.search(
        r"(\w+)\s+was\s+presented\s+alone\s+for\s+extinction\s+testing",
        text, re.IGNORECASE,
    )
    if m is None:
        m = re.search(r"(\S+?)の単独呈示により消去を実施した", text)
    if m is None:
        return None
    return ExtractResult(
        ast={"type": "Extinction", "cs": _ident(m.group(1))},
        confidence=0.80,
        span=(m.start(), m.end()), source_text=m.group(0),
    )


# --- R6/R7: CSOnly / USOnly -----------------------------------------------

def extract_cs_only(text: str) -> ExtractResult | None:
    m = re.search(
        r"(\w+)\s+was\s+presented\s+alone\s+on\s+(\d+)\s+trials",
        text, re.IGNORECASE,
    )
    if m is None:
        m = re.search(r"(\S+?)を単独で(\d+)試行呈示した", text)
    if m is None:
        return None
    return ExtractResult(
        ast={"type": "CSOnly", "cs": _ident(m.group(1)), "trials": int(m.group(2))},
        confidence=0.80,
        span=(m.start(), m.end()), source_text=m.group(0),
    )


def extract_us_only(text: str) -> ExtractResult | None:
    # Disambiguate via a trailing "unconditioned" hint when available; otherwise
    # default to CSOnly. A minimal heuristic: the word "US" or Japanese "US を"
    # immediately preceding.
    m = re.search(
        r"The\s+US\s+(\w+)\s+was\s+presented\s+alone\s+on\s+(\d+)\s+trials",
        text, re.IGNORECASE,
    )
    if m:
        return ExtractResult(
            ast={"type": "USOnly", "us": _ident(m.group(1)), "trials": int(m.group(2))},
            confidence=0.75,
            span=(m.start(), m.end()), source_text=m.group(0),
        )
    return None


# --- R8: Contingency -------------------------------------------------------

def extract_contingency(text: str) -> ExtractResult | None:
    m = re.search(
        r"p\(US\|CS\)\s*=\s*(\d+(?:\.\d+)?).*?p\(US\|(?:no\s+CS|¬CS)\)\s*=\s*(\d+(?:\.\d+)?)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if m is None:
        return None
    return ExtractResult(
        ast={
            "type": "Contingency",
            "p_us_given_cs": float(m.group(1)),
            "p_us_given_no_cs": float(m.group(2)),
        },
        confidence=0.85,
        span=(m.start(), m.end()), source_text=m.group(0),
    )


# --- R9: TrulyRandom -------------------------------------------------------

def extract_truly_random(text: str) -> ExtractResult | None:
    m = re.search(
        r"(\w+)\s+and\s+(\w+)\s+were\s+arranged\s+as\s+a\s+truly\s+random\s+control"
        r"(?:\s+\(p=(\d+(?:\.\d+)?)\))?",
        text, re.IGNORECASE,
    )
    if m is None:
        m = re.search(
            r"(\S+?)と(\S+?)を真のランダム統制として配置した"
            r"(?:（p=(\d+(?:\.\d+)?)）)?",
            text,
        )
    if m is None:
        return None
    ast: dict = {
        "type": "TrulyRandom",
        "cs": _ident(m.group(1)),
        "us": _ident(m.group(2)),
    }
    if m.group(3):
        ast["p"] = float(m.group(3))
    return ExtractResult(ast=ast, confidence=0.80,
                         span=(m.start(), m.end()), source_text=m.group(0))


# --- R10: ExplicitlyUnpaired ----------------------------------------------

def extract_explicitly_unpaired(text: str) -> ExtractResult | None:
    m = re.search(
        r"(\w+)\s+and\s+(\w+)\s+were\s+arranged\s+as\s+an\s+explicitly\s+unpaired\s+control"
        rf"(?:\s+\(minimum\s+separation\s+{_DUR}\))?",
        text, re.IGNORECASE,
    )
    if m:
        ast: dict = {
            "type": "ExplicitlyUnpaired",
            "cs": _ident(m.group(1)),
            "us": _ident(m.group(2)),
        }
        if m.group(3):
            ast["min_separation"] = _duration(m.group(3), m.group(4))
        return ExtractResult(ast=ast, confidence=0.80,
                             span=(m.start(), m.end()), source_text=m.group(0))
    m = re.search(
        r"(\S+?)と(\S+?)を明示的に非対呈示で配置した"
        rf"(?:（最小分離\s*{_DUR}）)?",
        text,
    )
    if m:
        ast = {
            "type": "ExplicitlyUnpaired",
            "cs": _ident(m.group(1)),
            "us": _ident(m.group(2)),
        }
        if m.group(3):
            ast["min_separation"] = _duration(m.group(3), m.group(4))
        return ExtractResult(ast=ast, confidence=0.80,
                             span=(m.start(), m.end()), source_text=m.group(0))
    return None


# --- R11: Compound (respondent) --------------------------------------------

def extract_resp_compound(text: str) -> ExtractResult | None:
    m = re.search(
        r"([\w ,]+?)\s+were\s+presented\s+simultaneously\s+as\s+a\s+compound\s+conditioned\s+stimulus",
        text, re.IGNORECASE,
    )
    if m is None:
        m = re.search(r"([^。]+?)を同時に複合条件刺激として呈示した", text)
    if m is None:
        return None
    raw = re.split(r",\s*|、|\s+and\s+", m.group(1))
    cs_list = [_ident(n) for n in raw if n.strip()]
    if len(cs_list) < 2:
        return None
    return ExtractResult(
        ast={"type": "Compound", "cs_list": cs_list, "mode": "Simultaneous"},
        confidence=0.80,
        span=(m.start(), m.end()), source_text=m.group(0),
    )


# --- R12: Serial -----------------------------------------------------------

def extract_resp_serial(text: str) -> ExtractResult | None:
    m = re.search(
        rf"Conditioned\s+stimuli\s+([\w →]+?)\s+were\s+presented\s+in\s+serial\s+order\s+\(inter-stimulus\s+interval\s+{_DUR}\)",
        text, re.IGNORECASE,
    )
    if m is None:
        m = re.search(
            rf"([^。]+?)の順に条件刺激を連続呈示した（刺激間間隔\s*{_DUR}）",
            text,
        )
    if m is None:
        return None
    raw = re.split(r"→|\s+→\s+", m.group(1))
    cs_list = [_ident(n) for n in raw if n.strip()]
    if len(cs_list) < 2:
        return None
    return ExtractResult(
        ast={
            "type": "Serial",
            "cs_list": cs_list,
            "isi": _duration(m.group(2), m.group(3)),
        },
        confidence=0.80,
        span=(m.start(), m.end()), source_text=m.group(0),
    )


# --- R13: ITI --------------------------------------------------------------

def extract_resp_iti(text: str) -> ExtractResult | None:
    m = re.search(
        rf"The\s+inter-trial\s+interval\s+followed\s+a\s+(fixed|uniform|exponential)\s+distribution\s+with\s+mean\s+{_DUR}",
        text, re.IGNORECASE,
    )
    if m is None:
        m = re.search(
            rf"試行間間隔は平均\s*{_DUR}\s*の(固定|一様|指数)分布に従った",
            text,
        )
        if m:
            dist_ja = m.group(3)
            dist = {"固定": "fixed", "一様": "uniform", "指数": "exponential"}[dist_ja]
            return ExtractResult(
                ast={
                    "type": "ITI",
                    "distribution": dist,
                    "mean": _duration(m.group(1), m.group(2)),
                },
                confidence=0.80,
                span=(m.start(), m.end()), source_text=m.group(0),
            )
    if m is None:
        return None
    return ExtractResult(
        ast={
            "type": "ITI",
            "distribution": m.group(1).lower(),
            "mean": _duration(m.group(2), m.group(3)),
        },
        confidence=0.80,
        span=(m.start(), m.end()), source_text=m.group(0),
    )


# --- R14: Differential -----------------------------------------------------

def extract_differential(text: str) -> ExtractResult | None:
    m = re.search(
        r"Differential\s+conditioning\s+with\s+(\w+)\s+as\s+CS\+\s+and\s+(\w+)\s+as\s+"
        r"CS(?:−|-)(?:\s+\(US:\s*(\w+)\))?",
        text, re.IGNORECASE,
    )
    if m is None:
        m = re.search(
            r"(\S+?)を\s*CS\+、(\S+?)を\s*CS(?:−|-)\s*とする弁別条件づけを実施した"
            r"(?:（US:\s*(\S+?)）)?",
            text,
        )
    if m is None:
        return None
    ast: dict = {
        "type": "Differential",
        "cs_positive": _ident(m.group(1)),
        "cs_negative": _ident(m.group(2)),
    }
    if m.group(3):
        ast["us"] = _ident(m.group(3))
    return ExtractResult(ast=ast, confidence=0.80,
                         span=(m.start(), m.end()), source_text=m.group(0))


# --- Pipeline entry --------------------------------------------------------

def extract_respondent(text: str) -> ExtractResult | None:
    """Run respondent extractors in priority order and return the first hit.

    Ordering places the most specific patterns first (Pair.* before
    Extinction or CSOnly, which share surface phrasing).
    """
    for fn in (
        extract_pair_forward_delay,
        extract_pair_forward_trace,
        extract_pair_backward,
        extract_pair_simultaneous,
        extract_contingency,
        extract_truly_random,
        extract_explicitly_unpaired,
        extract_differential,
        extract_resp_serial,
        extract_resp_compound,
        extract_resp_iti,
        extract_us_only,
        extract_cs_only,
        extract_resp_extinction,
    ):
        res = fn(text)
        if res is not None:
            return res
    return None
