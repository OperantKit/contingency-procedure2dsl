"""Layer 1: Rule-based schedule extraction from text.

Recognizes atomic, compound, modifier, aversive, trial-based, and special
schedules from JEAB/JABA Method-section prose. Output AST conforms to the
current contingency-dsl schema, where LimitedHold / Timeout / ResponseCost
are represented as optional leaf-node properties (``limitedHold`` /
``limitedHoldUnit`` / ``timeout`` / ``responseCost``) rather than wrapper
nodes.
"""

from __future__ import annotations

import re

from ..result import ExtractResult
from ..vocab_reverse import (
    ABBREV_PATTERN,
    COMBINATOR_REVERSE,
    DISTRIBUTION_REVERSE,
    DOMAIN_REVERSE,
    FULL_NAME_PATTERN,
    SPECIAL_REVERSE,
)


# --- Atomic ------------------------------------------------------------------

def extract_atomic_schedules(text: str) -> list[ExtractResult]:
    """Extract all atomic schedule mentions from text."""
    results: list[ExtractResult] = []

    for m in ABBREV_PATTERN.finditer(text):
        dist = m.group(1).upper()
        domain = m.group(2).upper()
        value = float(m.group(3))
        time_unit = m.group(4) or ("s" if domain in ("I", "T") else None)
        ast: dict = {
            "type": "Atomic",
            "dist": dist,
            "domain": domain,
            "value": value,
        }
        if time_unit:
            ast["time_unit"] = time_unit
        results.append(ExtractResult(
            ast=ast,
            confidence=0.95,
            span=(m.start(), m.end()),
            source_text=m.group(0),
        ))

    for m in FULL_NAME_PATTERN.finditer(text):
        dist_name = m.group(1).lower()
        domain_name = m.group(2).lower()
        dist = DISTRIBUTION_REVERSE.get(dist_name)
        domain = DOMAIN_REVERSE.get(domain_name)
        if dist is None or domain is None:
            continue
        value = float(m.group(3))
        time_unit = m.group(4) or ("s" if domain in ("I", "T") else None)
        ast = {
            "type": "Atomic",
            "dist": dist,
            "domain": domain,
            "value": value,
        }
        if time_unit:
            ast["time_unit"] = time_unit
        if not any(r.span[0] <= m.start() < r.span[1] for r in results):
            results.append(ExtractResult(
                ast=ast,
                confidence=0.90,
                span=(m.start(), m.end()),
                source_text=m.group(0),
            ))

    return results


# --- Compound ---------------------------------------------------------------

_COMPONENT_SPECIAL = re.compile(
    r"\b(extinction|continuous\s+reinforcement|EXT|CRF)\b|消去|連続強化",
    re.IGNORECASE,
)


def _extract_components_in_fragment(fragment: str) -> list[tuple[int, dict]]:
    """Return (start_offset, ast) for each schedule-like component in fragment.

    Detects atomic schedules AND Special components (EXT / CRF) so that
    prose like "multiple FR 5 extinction" yields two components.
    """
    components: list[tuple[int, dict]] = []
    for a in extract_atomic_schedules(fragment):
        components.append((a.span[0], a.ast))

    for m in _COMPONENT_SPECIAL.finditer(fragment):
        raw = m.group(0).lower()
        kind = "EXT" if raw.startswith("ext") or raw == "消去" else "CRF"
        # Avoid the trailing word "schedule" pattern: "continuous reinforcement
        # schedule" at the end of a compound with atomic(s) may be the whole-
        # sentence schedule word rather than a component. We still record it;
        # the "multiple ... continuous reinforcement schedule" case is handled
        # by positional merging because any preceding atomic will sort first.
        components.append((m.start(), {"type": "Special", "kind": kind}))

    components.sort(key=lambda x: x[0])
    return components


def extract_compound_schedule(text: str) -> ExtractResult | None:
    for full_name, code in COMBINATOR_REVERSE.items():
        pattern = re.compile(rf"\b{re.escape(full_name)}\b", re.IGNORECASE)
        m = pattern.search(text)
        if m is None:
            continue
        after = text[m.end():]
        sent_end = after.find(".")
        if sent_end == -1:
            sent_end = len(after)
        fragment = after[:sent_end]
        components = _extract_components_in_fragment(fragment)
        if len(components) >= 2:
            return ExtractResult(
                ast={
                    "type": "Compound",
                    "combinator": code,
                    "components": [ast for _, ast in components],
                },
                confidence=0.85,
                span=(m.start(), m.end() + sent_end),
                source_text=text[m.start():m.end() + sent_end],
            )
    return None


# --- Leaf properties: LH / Timeout / ResponseCost ---------------------------

_LH_EN = re.compile(
    r"with\s+a\s+(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+limited\s+hold",
    re.IGNORECASE,
)
_LH_JA = re.compile(
    r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)のリミテッドホールド",
)
_TO_EN = re.compile(
    r"with\s+a\s+(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+"
    r"(resetting|non-resetting)\s+timeout",
    re.IGNORECASE,
)
_TO_JA = re.compile(
    r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)のタイムアウト（(反応で再開する|反応で再開しない)）",
)
_RC_EN = re.compile(
    r"with\s+each\s+target\s+response\s+removing\s+(\d+(?:\.\d+)?)\s+(\w+?)s?\b",
    re.IGNORECASE,
)
_RC_JA = re.compile(
    r"各反応で(\d+(?:\.\d+)?)(トークン|ポイント)が除去された",
)


def extract_limited_hold(text: str) -> ExtractResult | None:
    """Locate a LH phrase and attach it to the primary schedule in text.

    Returns a schedule node with ``limitedHold`` / ``limitedHoldUnit``
    leaf properties set. Modern replacement for the old LimitedHold
    wrapper extractor.
    """
    m = _LH_EN.search(text) or _LH_JA.search(text)
    if m is None:
        return None
    value = float(m.group(1))
    unit = m.group(2)

    before = text[:m.start()]
    atomics = extract_atomic_schedules(before)
    if not atomics:
        return None
    inner = dict(atomics[0].ast)
    inner["limitedHold"] = value
    if unit:
        inner["limitedHoldUnit"] = unit
    return ExtractResult(
        ast=inner,
        confidence=0.80,
        span=(0, m.end()),
        source_text=text[:m.end()],
    )


def attach_leaf_properties(primary: dict, text: str) -> dict:
    """Augment a leaf schedule node with LH / Timeout / ResponseCost
    clauses detected in ``text``. Safe to call on any primary schedule
    AST dict. Respondent nodes are returned unchanged.
    """
    if not isinstance(primary, dict):
        return primary
    t = primary.get("type", "")
    if t in (
        "PairForwardDelay", "PairForwardTrace", "PairSimultaneous",
        "PairBackward", "Extinction", "CSOnly", "USOnly",
        "Contingency", "TrulyRandom", "ExplicitlyUnpaired",
        "Serial", "ITI", "Differential", "ExtensionPrimitive",
    ):
        return primary

    out = dict(primary)

    lh = _LH_EN.search(text) or _LH_JA.search(text)
    if lh and "limitedHold" not in out:
        out["limitedHold"] = float(lh.group(1))
        out["limitedHoldUnit"] = lh.group(2)

    to = _TO_EN.search(text)
    to_ja = _TO_JA.search(text)
    if to and "timeout" not in out:
        mode = to.group(3).lower()
        out["timeout"] = {
            "duration": float(to.group(1)),
            "durationUnit": to.group(2),
            "resetOnResponse": (mode == "resetting"),
        }
    elif to_ja and "timeout" not in out:
        reset_ja = to_ja.group(3)
        out["timeout"] = {
            "duration": float(to_ja.group(1)),
            "durationUnit": to_ja.group(2),
            "resetOnResponse": (reset_ja == "反応で再開する"),
        }

    rc = _RC_EN.search(text)
    rc_ja = _RC_JA.search(text)
    if rc and "responseCost" not in out:
        out["responseCost"] = {
            "amount": float(rc.group(1)),
            "unit": rc.group(2).lower().rstrip("s"),
        }
    elif rc_ja and "responseCost" not in out:
        unit_map = {"トークン": "token", "ポイント": "point"}
        out["responseCost"] = {
            "amount": float(rc_ja.group(1)),
            "unit": unit_map.get(rc_ja.group(2), rc_ja.group(2)),
        }
    return out


# --- Second-order -----------------------------------------------------------

def extract_second_order(text: str) -> ExtractResult | None:
    is_so = re.search(r"second-order|二次", text, re.IGNORECASE)
    if is_so is None:
        return None

    after = text[is_so.start():]
    abbrev_matches = list(re.finditer(
        r"\(?([A-Z]{2})\)?\s+(\d+(?:\.\d+)?)\s*(?:-?\s*(s|ms|min)\b)?",
        after,
    ))
    if len(abbrev_matches) < 2:
        return None

    outer_m, inner_m = abbrev_matches[0], abbrev_matches[1]
    outer_abbrev = outer_m.group(1).upper()
    inner_abbrev = inner_m.group(1).upper()

    def _parse_abbrev(abbrev: str, val: float, unit: str | None) -> dict:
        dist, domain = abbrev[0], abbrev[1]
        node: dict = {"type": "Atomic", "dist": dist, "domain": domain, "value": val}
        if unit:
            node["time_unit"] = unit
        elif domain in ("I", "T"):
            node["time_unit"] = "s"
        return node

    return ExtractResult(
        ast={
            "type": "SecondOrder",
            "overall": _parse_abbrev(outer_abbrev, float(outer_m.group(2)), None),
            "unit": _parse_abbrev(inner_abbrev, float(inner_m.group(2)), inner_m.group(3)),
        },
        confidence=0.80,
        span=(is_so.start(), is_so.start() + inner_m.end()),
        source_text=after[:inner_m.end()],
    )


# --- Modifier: DR / PR / Lag / Pctl -----------------------------------------

def extract_modifier(text: str) -> ExtractResult | None:
    dr_en = re.search(
        r"differential-reinforcement-of-(\w+)-(?:rate|behavior)\s+\((\w+)\)\s+"
        r"(\d+(?:\.\d+)?)\s*(?:-?\s*(s|ms|min)\b)?",
        text, re.IGNORECASE,
    )
    if dr_en:
        modifier = dr_en.group(2).upper()
        value = float(dr_en.group(3))
        unit = dr_en.group(4)
        ast: dict = {"type": "Modifier", "modifier": modifier, "value": value}
        if unit:
            ast["time_unit"] = unit
        return ExtractResult(ast=ast, confidence=0.85,
                             span=(dr_en.start(), dr_en.end()), source_text=dr_en.group(0))

    dr_ja = re.search(
        r"(低反応率分化強化|高反応率分化強化|他行動分化強化)\s+\((\w+)\)\s+"
        r"(\d+(?:\.\d+)?)\s*(?:-?\s*(s|ms|min)\b)?",
        text,
    )
    if dr_ja:
        modifier = dr_ja.group(2).upper()
        value = float(dr_ja.group(3))
        unit = dr_ja.group(4)
        ast = {"type": "Modifier", "modifier": modifier, "value": value}
        if unit:
            ast["time_unit"] = unit
        return ExtractResult(ast=ast, confidence=0.85,
                             span=(dr_ja.start(), dr_ja.end()), source_text=dr_ja.group(0))

    # Progressive Ratio
    pr_en = re.search(
        r"(\w+)\s+progressive-ratio\s+schedule(?:\s*\(([^)]+)\))?",
        text, re.IGNORECASE,
    )
    if pr_en:
        step = pr_en.group(1).lower()
        ast = {"type": "Modifier", "modifier": "PR", "pr_step": step}
        params_str = pr_en.group(2)
        if params_str:
            for part in params_str.split(","):
                part = part.strip()
                if part.startswith("start="):
                    ast["pr_start"] = int(float(part.split("=")[1]))
                elif part.startswith("step="):
                    ast["pr_increment"] = int(float(part.split("=")[1]))
                elif part.startswith("ratio="):
                    ast["pr_ratio"] = float(part.split("=")[1])
        return ExtractResult(ast=ast, confidence=0.80,
                             span=(pr_en.start(), pr_en.end()), source_text=pr_en.group(0))

    pr_ja = re.search(r"(\S+?)漸進比率スケジュール", text)
    if pr_ja:
        step = pr_ja.group(1)
        step_map = {
            "線形": "linear", "Hodos": "hodos",
            "指数": "exponential", "幾何": "geometric",
        }
        ast = {"type": "Modifier", "modifier": "PR", "pr_step": step_map.get(step, step)}
        return ExtractResult(ast=ast, confidence=0.80,
                             span=(pr_ja.start(), pr_ja.end()), source_text=pr_ja.group(0))

    # Lag
    lag_m = re.search(
        r"Lag\s+(\d+)\s*スケジュール|Lag\s+(\d+)\s+schedule",
        text, re.IGNORECASE,
    )
    if lag_m:
        length = int(lag_m.group(1) or lag_m.group(2))
        return ExtractResult(
            ast={"type": "Modifier", "modifier": "Lag", "value": 0.0, "length": length},
            confidence=0.85,
            span=(lag_m.start(), lag_m.end()), source_text=lag_m.group(0),
        )

    # Percentile
    pctl_en = re.search(
        r"percentile\s+schedule\s+targeting\s+responses\s+(at or below|at or above)\s+"
        r"the\s+(\d+(?:\.\d+)?)(?:st|nd|rd|th)?\s+percentile\s+of\s+(\w+)"
        r"(?:\s+\(window=(\d+)\))?",
        text, re.IGNORECASE,
    )
    if pctl_en:
        direction = "below" if pctl_en.group(1).lower().endswith("below") else "above"
        rank = int(float(pctl_en.group(2)))
        target = pctl_en.group(3).upper() if pctl_en.group(3).upper() == "IRT" else pctl_en.group(3).lower()
        ast = {
            "type": "Modifier", "modifier": "Pctl",
            "pctl_target": target, "pctl_rank": rank, "pctl_dir": direction,
        }
        if pctl_en.group(4):
            ast["pctl_window"] = int(pctl_en.group(4))
        return ExtractResult(ast=ast, confidence=0.80,
                             span=(pctl_en.start(), pctl_en.end()),
                             source_text=pctl_en.group(0))

    pctl_ja = re.search(
        r"(\w+)の第(\d+(?:\.\d+)?)百分位(以下|以上)?を満たす反応を強化するパーセンタイルスケジュール"
        r"(?:（ウィンドウ=(\d+)）)?",
        text,
    )
    if pctl_ja:
        target = pctl_ja.group(1)
        target = target.upper() if target.upper() == "IRT" else target
        rank = int(float(pctl_ja.group(2)))
        direction_ja = pctl_ja.group(3) or "以下"
        direction = "below" if direction_ja == "以下" else "above"
        ast = {
            "type": "Modifier", "modifier": "Pctl",
            "pctl_target": target, "pctl_rank": rank, "pctl_dir": direction,
        }
        if pctl_ja.group(4):
            ast["pctl_window"] = int(pctl_ja.group(4))
        return ExtractResult(ast=ast, confidence=0.80,
                             span=(pctl_ja.start(), pctl_ja.end()),
                             source_text=pctl_ja.group(0))

    return None


# --- Aversive: Sidman / DiscrimAv -------------------------------------------

def extract_aversive(text: str) -> ExtractResult | None:
    sidman = re.search(
        r"Sidman\s+(?:avoidance|回避).*?"
        r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+(?:shock-shock|SS\s*間隔).*?"
        r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+(?:response-shock|RS\s*間隔)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if sidman:
        return ExtractResult(
            ast={
                "type": "AversiveSchedule", "kind": "Sidman",
                "params": {
                    "SSI": {"value": float(sidman.group(1)), "time_unit": sidman.group(2)},
                    "RSI": {"value": float(sidman.group(3)), "time_unit": sidman.group(4)},
                },
            },
            confidence=0.85,
            span=(sidman.start(), sidman.end()), source_text=sidman.group(0),
        )

    sidman_ja = re.search(
        r"Sidman\s*回避.*?"
        r"SS\s*間隔\s*(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min).*?"
        r"RS\s*間隔\s*(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)",
        text,
    )
    if sidman_ja:
        return ExtractResult(
            ast={
                "type": "AversiveSchedule", "kind": "Sidman",
                "params": {
                    "SSI": {"value": float(sidman_ja.group(1)), "time_unit": sidman_ja.group(2)},
                    "RSI": {"value": float(sidman_ja.group(3)), "time_unit": sidman_ja.group(4)},
                },
            },
            confidence=0.85,
            span=(sidman_ja.start(), sidman_ja.end()), source_text=sidman_ja.group(0),
        )

    discrim = re.search(
        r"discriminated\s+avoidance.*?\(([\w-]+)\s+mode\).*?"
        r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+CS-US.*?"
        r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+intertrial",
        text, re.IGNORECASE | re.DOTALL,
    )
    if discrim:
        raw_mode = discrim.group(1).lower()
        mode = {
            "fixed-duration": "fixed",
            "response-terminated": "response_terminated",
        }.get(raw_mode, raw_mode)
        return ExtractResult(
            ast={
                "type": "AversiveSchedule", "kind": "DiscrimAv",
                "params": {
                    "CSUSInterval": {"value": float(discrim.group(2)), "time_unit": discrim.group(3)},
                    "ITI": {"value": float(discrim.group(4)), "time_unit": discrim.group(5)},
                    "mode": mode,
                },
            },
            confidence=0.85,
            span=(discrim.start(), discrim.end()), source_text=discrim.group(0),
        )

    discrim_ja = re.search(
        r"弁別回避.*?（(\S+?)モード）.*?"
        r"CS-US\s*間隔\s*(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min).*?"
        r"試行間間隔\s*(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)",
        text,
    )
    if discrim_ja:
        mode_map = {"固定": "fixed", "逃避": "escape"}
        return ExtractResult(
            ast={
                "type": "AversiveSchedule", "kind": "DiscrimAv",
                "params": {
                    "CSUSInterval": {"value": float(discrim_ja.group(2)), "time_unit": discrim_ja.group(3)},
                    "ITI": {"value": float(discrim_ja.group(4)), "time_unit": discrim_ja.group(5)},
                    "mode": mode_map.get(discrim_ja.group(1), discrim_ja.group(1)),
                },
            },
            confidence=0.85,
            span=(discrim_ja.start(), discrim_ja.end()), source_text=discrim_ja.group(0),
        )

    escape_en = re.search(
        r"free-operant\s+escape\s+schedule\s+was\s+in\s+effect"
        r"\s+with\s+a\s+(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+safe\s+period",
        text, re.IGNORECASE,
    )
    if escape_en:
        params: dict = {
            "SafeDuration": {
                "value": float(escape_en.group(1)),
                "time_unit": escape_en.group(2),
            },
        }
        max_shock = re.search(
            r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+maximum\s+uninterrupted\s+exposure\s+cutoff",
            text, re.IGNORECASE,
        )
        if max_shock:
            params["MaxShock"] = {
                "value": float(max_shock.group(1)),
                "time_unit": max_shock.group(2),
            }
        return ExtractResult(
            ast={
                "type": "AversiveSchedule",
                "kind": "Escape",
                "params": params,
            },
            confidence=0.85,
            span=(escape_en.start(), escape_en.end()),
            source_text=escape_en.group(0),
        )

    escape_ja = re.search(
        r"自由オペラント逃避スケジュール.*?"
        r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s*の?\s*安全期間",
        text, re.DOTALL,
    )
    if escape_ja:
        params = {
            "SafeDuration": {
                "value": float(escape_ja.group(1)),
                "time_unit": escape_ja.group(2),
            },
        }
        return ExtractResult(
            ast={
                "type": "AversiveSchedule",
                "kind": "Escape",
                "params": params,
            },
            confidence=0.85,
            span=(escape_ja.start(), escape_ja.end()),
            source_text=escape_ja.group(0),
        )

    return None


# --- Stateful: Adjusting / Interlocking ------------------------------------

_ADJ_TARGET_MAP = {
    "reinforcement delay": "delay",
    "ratio requirement": "ratio",
    "reinforcer magnitude": "amount",
}
_ADJ_EN = re.compile(
    r"an\s+adjusting\s+schedule\s+varied\s+the\s+"
    r"(reinforcement\s+delay|ratio\s+requirement|reinforcer\s+magnitude)"
    r"\s+\(initial\s+value\s+(\d+(?:\.\d+)?)"
    r"(?:\s*-?\s*(s|ms|min))?"
    r";\s*step\s+(\d+(?:\.\d+)?)"
    r"(?:\s*-?\s*(s|ms|min))?\)",
    re.IGNORECASE,
)
_ADJ_BOUNDS_EN = re.compile(
    r"constrained\s+by"
    r"(?:\s+a\s+lower\s+bound\s+of\s+(\d+(?:\.\d+)?)(?:\s*-?\s*(s|ms|min))?)?"
    r"(?:\s+and)?"
    r"(?:\s+an\s+upper\s+bound\s+of\s+(\d+(?:\.\d+)?)(?:\s*-?\s*(s|ms|min))?)?",
    re.IGNORECASE,
)


def _adj_value(value: str, unit: str | None) -> dict:
    v = float(value)
    out: dict = {"value": v if "." in value else int(v) if v.is_integer() else v}
    if unit:
        out["time_unit"] = unit
    return out


def extract_adjusting(text: str) -> ExtractResult | None:
    m = _ADJ_EN.search(text)
    if m is None:
        return None
    target_phrase = re.sub(r"\s+", " ", m.group(1).lower())
    target = _ADJ_TARGET_MAP.get(target_phrase)
    if target is None:
        return None

    start_unit = m.group(3)
    step_unit = m.group(5)
    adj_start = _adj_value(m.group(2), start_unit)
    adj_step = _adj_value(m.group(4), step_unit)

    adj_min: dict | None = None
    adj_max: dict | None = None
    b = _ADJ_BOUNDS_EN.search(text[m.end():])
    if b:
        lb_val, lb_unit = b.group(1), b.group(2)
        ub_val, ub_unit = b.group(3), b.group(4)
        if lb_val:
            adj_min = _adj_value(lb_val, lb_unit)
        if ub_val:
            adj_max = _adj_value(ub_val, ub_unit)

    ast = {
        "type": "AdjustingSchedule",
        "adj_target": target,
        "adj_start": adj_start,
        "adj_step": adj_step,
        "adj_min": adj_min,
        "adj_max": adj_max,
    }
    return ExtractResult(
        ast=ast, confidence=0.90,
        span=(m.start(), m.end()), source_text=m.group(0),
    )


_INTERLOCK_EN = re.compile(
    r"an\s+interlocking\s+schedule\s+was\s+in\s+effect"
    r"\s+\(initial\s+ratio\s+R0=(\d+);\s*time\s+window\s+T=(\d+(?:\.\d+)?)"
    r"\s*-?\s*(s|ms|min)\)",
    re.IGNORECASE,
)


def extract_interlocking(text: str) -> ExtractResult | None:
    m = _INTERLOCK_EN.search(text)
    if m is None:
        return None
    ast = {
        "type": "InterlockingSchedule",
        "interlock_R0": int(m.group(1)),
        "interlock_T": {
            "value": float(m.group(2)),
            "time_unit": m.group(3),
        },
    }
    return ExtractResult(
        ast=ast, confidence=0.90,
        span=(m.start(), m.end()), source_text=m.group(0),
    )


# --- Trial-based: GoNoGo / MTS ---------------------------------------------

_GONOGO_EN = re.compile(
    r"\bGo/NoGo\s+discrimination\s+procedure\s+was\s+used\b",
    re.IGNORECASE,
)
_GONOGO_JA = re.compile(r"Go/NoGo\s*弁別手続き")
_GONOGO_WINDOW_EN = re.compile(
    r"Responses\s+during\s+the\s+(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+response\s+window\s+on\s+Go\s+trials",
    re.IGNORECASE,
)
_GONOGO_WINDOW_JA = re.compile(
    r"Go\s*試行の\s*(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s*反応時間内の反応"
)
_GONOGO_ITI_EN = re.compile(
    r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+inter-trial\s+interval\s+separated\s+successive\s+trials",
    re.IGNORECASE,
)
_GONOGO_ITI_JA = re.compile(
    r"試行間間隔は\s*(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)"
)


def _extract_gonogo_consequence_en(text: str) -> dict:
    if re.search(r"Go\s+trials\s+produced\s+a\s+reinforcer\s+\(continuous\s+reinforcement\)", text, re.IGNORECASE):
        return {"type": "Special", "kind": "CRF"}
    if re.search(r"Go\s+trials\s+had\s+no\s+programmed\s+consequences\s+\(extinction\)", text, re.IGNORECASE):
        return {"type": "Special", "kind": "EXT"}
    m = re.search(
        r"Go\s+trials\s+were\s+reinforced\s+under\s+a\s+"
        r"([FVR])([RIT])\s*(\d+(?:\.\d+)?)\s*(?:-?\s*(s|ms|min))?\s+schedule",
        text, re.IGNORECASE,
    )
    if m:
        ast: dict = {
            "type": "Atomic", "dist": m.group(1).upper(),
            "domain": m.group(2).upper(), "value": float(m.group(3)),
        }
        unit = m.group(4)
        if unit:
            ast["time_unit"] = unit
        return ast
    return {"type": "Special", "kind": "CRF"}


def _extract_gonogo_falseAlarm_en(text: str) -> dict:
    m = re.search(
        r"NoGo\s+trials\s+were\s+followed\s+by\s+a\s+"
        r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+timeout",
        text, re.IGNORECASE,
    )
    if m:
        return {
            "type": "Atomic", "dist": "F", "domain": "T",
            "value": float(m.group(1)), "time_unit": m.group(2),
        }
    return {"type": "Special", "kind": "EXT"}


def extract_gonogo(text: str) -> ExtractResult | None:
    is_en = _GONOGO_EN.search(text)
    is_ja = _GONOGO_JA.search(text)
    if is_en is None and is_ja is None:
        return None

    if is_en:
        win = _GONOGO_WINDOW_EN.search(text)
        iti = _GONOGO_ITI_EN.search(text)
    else:
        win = _GONOGO_WINDOW_JA.search(text)
        iti = _GONOGO_ITI_JA.search(text)

    if win is None:
        return None

    response_window = float(win.group(1))
    response_window_unit = win.group(2)

    if iti:
        iti_value = float(iti.group(1))
        iti_unit = iti.group(2)
    else:
        iti_value, iti_unit = 10.0, "s"

    consequence = (
        _extract_gonogo_consequence_en(text) if is_en
        else {"type": "Special", "kind": "CRF"}
    )
    false_alarm = (
        _extract_gonogo_falseAlarm_en(text) if is_en
        else {"type": "Special", "kind": "EXT"}
    )

    ast: dict = {
        "type": "TrialBased",
        "trial_type": "GoNoGo",
        "responseWindow": response_window,
        "responseWindowUnit": response_window_unit,
        "consequence": consequence,
        "incorrect": {"type": "Special", "kind": "EXT"},
        "falseAlarm": false_alarm,
        "ITI": iti_value,
        "ITI_unit": iti_unit,
    }
    start = (is_en or is_ja).start()
    end = (iti.end() if iti else win.end())
    return ExtractResult(
        ast=ast, confidence=0.85,
        span=(start, end), source_text=text[start:end],
    )


def extract_trial_based(text: str) -> ExtractResult | None:
    gonogo = extract_gonogo(text)
    if gonogo is not None:
        return gonogo

    mts_en = re.search(
        r"(?:An?\s+)?(identity|arbitrary)\s+matching-to-sample\s+\(MTS\)\s+procedure"
        r"\s+was\s+used\s+with\s+(\w+)\s+comparison\s+stimuli",
        text, re.IGNORECASE,
    )
    if mts_en:
        mts_type = mts_en.group(1).lower()
        comparisons = _parse_number_word(mts_en.group(2))
        consequence = _extract_mts_consequence_en(text)
        incorrect = _extract_mts_incorrect_en(text)
        iti, iti_unit = _extract_mts_iti_en(text)
        ast: dict = {
            "type": "TrialBased",
            "trial_type": "MTS",
            "comparisons": comparisons,
            "consequence": consequence,
            "incorrect": incorrect,
            "ITI": iti,
            "ITI_unit": iti_unit,
            "mts_type": mts_type,
        }
        return ExtractResult(
            ast=ast, confidence=0.85,
            span=(mts_en.start(), mts_en.end()),
            source_text=mts_en.group(0),
        )

    mts_ja = re.search(
        r"(同一|任意)見本合わせ（MTS）手続き\S*\s*"
        r".*?(\d+)\s*個の比較刺激",
        text, re.DOTALL,
    )
    if mts_ja:
        mts_type_ja = mts_ja.group(1)
        mts_type = "identity" if mts_type_ja == "同一" else "arbitrary"
        comparisons = int(mts_ja.group(2))
        consequence = _extract_mts_consequence_ja(text)
        incorrect = _extract_mts_incorrect_ja(text)
        iti, iti_unit = _extract_mts_iti_ja(text)
        ast = {
            "type": "TrialBased",
            "trial_type": "MTS",
            "comparisons": comparisons,
            "consequence": consequence,
            "incorrect": incorrect,
            "ITI": iti,
            "ITI_unit": iti_unit,
            "mts_type": mts_type,
        }
        return ExtractResult(
            ast=ast, confidence=0.85,
            span=(mts_ja.start(), mts_ja.end()),
            source_text=mts_ja.group(0),
        )

    return None


# --- MTS helpers ------------------------------------------------------------

_NUMBER_WORDS: dict[str, int] = {
    "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9,
}


def _parse_number_word(s: str) -> int:
    low = s.lower()
    if low in _NUMBER_WORDS:
        return _NUMBER_WORDS[low]
    return int(s)


def _extract_mts_consequence_en(text: str) -> dict:
    if re.search(r"\bCorrect\s+responses\s+produced\s+a\s+reinforcer\s+\(continuous\s+reinforcement\)", text):
        return {"type": "Special", "kind": "CRF"}
    if re.search(r"\bCorrect\s+responses\s+had\s+no\s+programmed\s+consequences\s+\(extinction\)", text):
        return {"type": "Special", "kind": "EXT"}
    m = re.search(
        r"\bCorrect\s+responses\s+were\s+reinforced\s+under\s+a\s+"
        r"([FVR])([RIT])\s*(\d+(?:\.\d+)?)\s*(?:-?\s*(s|ms|min))?\s+schedule",
        text,
    )
    if m:
        ast: dict = {
            "type": "Atomic", "dist": m.group(1).upper(),
            "domain": m.group(2).upper(), "value": float(m.group(3)),
        }
        unit = m.group(4)
        if unit:
            ast["time_unit"] = unit
        return ast
    return {"type": "Special", "kind": "CRF"}


def _extract_mts_incorrect_en(text: str) -> dict:
    if re.search(r"\bIncorrect\s+responses\s+had\s+no\s+programmed\s+consequences\s+\(extinction\)", text):
        return {"type": "Special", "kind": "EXT"}
    m = re.search(
        r"\bIncorrect\s+responses\s+were\s+followed\s+by\s+a\s+"
        r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+timeout",
        text,
    )
    if m:
        return {
            "type": "Atomic", "dist": "F", "domain": "T",
            "value": float(m.group(1)), "time_unit": m.group(2),
        }
    m2 = re.search(
        r"\bIncorrect\s+responses\s+were\s+followed\s+by\s+a\s+"
        r"([FVR])([RIT])\s+(\d+(?:\.\d+)?)\s*(?:-?\s*(s|ms|min))?\s+schedule",
        text,
    )
    if m2:
        ast: dict = {
            "type": "Atomic", "dist": m2.group(1).upper(),
            "domain": m2.group(2).upper(), "value": float(m2.group(3)),
        }
        unit = m2.group(4)
        if unit:
            ast["time_unit"] = unit
        return ast
    return {"type": "Special", "kind": "EXT"}


def _extract_mts_iti_en(text: str) -> tuple[float, str]:
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+inter-trial\s+interval",
        text, re.IGNORECASE,
    )
    if m:
        return float(m.group(1)), m.group(2)
    return 5.0, "s"


def _extract_mts_consequence_ja(text: str) -> dict:
    if re.search(r"正反応に対しては.*?強化子が呈示された（連続強化）", text):
        return {"type": "Special", "kind": "CRF"}
    if re.search(r"正反応に対しては.*?プログラムされた結果は呈示されなかった（消去）", text):
        return {"type": "Special", "kind": "EXT"}
    m = re.search(
        r"正反応に対しては\s*([FVR])([RIT])\s+(\d+(?:\.\d+)?)\s*(?:-?\s*(s|ms|min))?\s*スケジュール",
        text,
    )
    if m:
        ast: dict = {
            "type": "Atomic", "dist": m.group(1).upper(),
            "domain": m.group(2).upper(), "value": float(m.group(3)),
        }
        unit = m.group(4)
        if unit:
            ast["time_unit"] = unit
        return ast
    return {"type": "Special", "kind": "CRF"}


def _extract_mts_incorrect_ja(text: str) -> dict:
    if re.search(r"誤反応に対しては.*?プログラムされた結果は呈示されなかった（消去）", text):
        return {"type": "Special", "kind": "EXT"}
    m = re.search(
        r"誤反応に対しては\s*(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s*の\s*タイムアウト",
        text,
    )
    if m:
        return {
            "type": "Atomic", "dist": "F", "domain": "T",
            "value": float(m.group(1)), "time_unit": m.group(2),
        }
    return {"type": "Special", "kind": "EXT"}


def _extract_mts_iti_ja(text: str) -> tuple[float, str]:
    m = re.search(
        r"試行間間隔は\s*(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)",
        text,
    )
    if m:
        return float(m.group(1)), m.group(2)
    return 5.0, "s"


# --- Overlay (punishment-on-baseline) ---------------------------------------

def extract_overlay(text: str) -> ExtractResult | None:
    m_en = re.search(r"superimposed\s+on\s+(?:the\s+baseline|changeover\s+responses)", text, re.IGNORECASE)
    m_ja = re.search(r"罰刺激が(?:重畳された|重畳)", text)
    if m_en is None and m_ja is None:
        return None

    sentences = re.split(r"(?<=\.)\s+|(?<=。)\s*", text)
    if len(sentences) < 2:
        return None

    baseline_atomics = extract_atomic_schedules(sentences[0])
    baseline_special = extract_special_schedule(sentences[0])
    punisher_atomics = extract_atomic_schedules(sentences[1])
    punisher_special = extract_special_schedule(sentences[1])

    baseline = (baseline_atomics[0].ast if baseline_atomics
                else baseline_special.ast if baseline_special else None)
    punisher = (punisher_atomics[0].ast if punisher_atomics
                else punisher_special.ast if punisher_special else None)
    if baseline is None or punisher is None:
        return None

    params: dict = {}
    if m_en and "changeover" in (m_en.group(0) or "").lower():
        params["target"] = "changeover"

    ast = {
        "type": "Compound",
        "combinator": "Overlay",
        "components": [baseline, punisher],
    }
    if params:
        ast["params"] = params

    return ExtractResult(
        ast=ast, confidence=0.90,
        span=(0, len(text)), source_text=text,
    )


# --- Special (EXT, CRF) -----------------------------------------------------

def extract_special_schedule(text: str) -> ExtractResult | None:
    lower = text.lower()
    for name, kind in SPECIAL_REVERSE.items():
        idx = lower.find(name)
        if idx != -1:
            return ExtractResult(
                ast={"type": "Special", "kind": kind},
                confidence=0.90,
                span=(idx, idx + len(name)),
                source_text=text[idx:idx + len(name)],
            )
    return None
