"""Reverse vocabulary: natural language terms → DSL components.

Inverts the mapping from contingency-dsl2procedure's vocabulary.py.
Supports both JEAB (English) and JABA (Japanese) terminology.
"""

from __future__ import annotations

import re

# --- Distribution: full name → code ---

DISTRIBUTION_REVERSE: dict[str, str] = {
    # English
    "fixed": "F", "variable": "V", "random": "R",
    # Japanese
    "固定": "F", "変動": "V", "ランダム": "R",
}

# --- Domain: full name → code ---

DOMAIN_REVERSE: dict[str, str] = {
    # English
    "ratio": "R", "interval": "I", "time": "T",
    # Japanese
    "比率": "R", "時隔": "I", "時間": "T",
}

# --- Combinator: full name → code ---

COMBINATOR_REVERSE: dict[str, str] = {
    # English
    "concurrent": "Conc", "chained": "Chain", "alternative": "Alt",
    "conjunctive": "Conj", "tandem": "Tand", "multiple": "Mult",
    "mixed": "Mix", "overlay": "Overlay", "interpolated": "Interpolate",
    # Japanese
    "並立": "Conc", "連鎖": "Chain", "二択": "Alt",
    "連言": "Conj", "タンデム": "Tand", "多元": "Mult",
    "混合": "Mix", "重畳": "Overlay", "挿入": "Interpolate",
}

# --- Special schedule: full name → kind ---

SPECIAL_REVERSE: dict[str, str] = {
    "extinction": "EXT", "消去": "EXT",
    "continuous reinforcement": "CRF", "連続強化": "CRF",
    "crf": "CRF", "ext": "EXT",
}

# --- Abbreviation pattern ---
# Matches: FR5, VI 30-s, VR 20, FI30s, VI30-s, etc.
# The trailing \b on the time unit prevents the `s` in words like `schedule`
# or `second` from being captured (ratios must never acquire a time_unit).
ABBREV_PATTERN = re.compile(
    r"\b([FVR])([RIT])\s*(\d+(?:\.\d+)?)\s*(?:-?\s*(s|ms|min)\b)?",
    re.IGNORECASE,
)

# --- Full name pattern ---
# Matches: "fixed-ratio 5", "variable-interval 30-s", "固定比率 5", etc.
_dist_names = "|".join(re.escape(k) for k in DISTRIBUTION_REVERSE)
_domain_names = "|".join(re.escape(k) for k in DOMAIN_REVERSE)
FULL_NAME_PATTERN = re.compile(
    rf"({_dist_names})[\-\s]*({_domain_names})"
    rf"\s*(?:\([A-Z]{{2}}\))?\s*(\d+(?:\.\d+)?)\s*(?:-?\s*(s|ms|min)\b)?",
    re.IGNORECASE,
)

# --- Parameter patterns ---
PARAM_PATTERNS: dict[str, re.Pattern] = {
    "COD": re.compile(
        r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+changeover\s+delay"
        r"|切替遅延\s*(?:が|は|の)?\s*(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)"
        r"|(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s*の?\s*切替遅延",
        re.IGNORECASE,
    ),
    "LH": re.compile(
        r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+limited\s+hold"
        r"|リミテッドホールド\s*(?:が|は|の)?\s*(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)"
        r"|(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s*の?\s*リミテッドホールド",
        re.IGNORECASE,
    ),
    "BO": re.compile(
        r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+blackout"
        r"|ブラックアウト\s*(?:が|は|の)?\s*(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)"
        r"|(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s*の?\s*ブラックアウト",
        re.IGNORECASE,
    ),
    "RD": re.compile(
        r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+delay\s+was\s+imposed\b"
        r"|(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+(?:reinforcement\s+)?delay\b"
        r"|(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s*の?\s*(?:強化)?遅延\s*(?:が|を)",
        re.IGNORECASE,
    ),
}

# FRCO is count-based (no time unit), handled separately from PARAM_PATTERNS
FRCO_PATTERN = re.compile(
    r"(?:fixed-ratio\s+)?(\d+)(?:-response)?\s+(?:fixed-ratio\s+)?changeover"
    r"|(\d+)\s*(?:反応)?\s*の?\s*固定比率切替",
    re.IGNORECASE,
)
