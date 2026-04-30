"""Layer 1: Annotation extraction from Method section text.

Extracts subject, apparatus, measurement, and procedure annotations.
"""

from __future__ import annotations

import re

from ..result import ExtractResult


# ===== Subject annotations =====

_SPECIES = {
    "rats": "rat", "rat": "rat",
    "pigeons": "pigeon", "pigeon": "pigeon",
    "mice": "mouse", "mouse": "mouse",
    "ラット": "rat", "ハト": "pigeon", "マウス": "mouse",
}

# Human-participant terms. These map to @species("human") with an optional
# @population tag capturing the developmental/role descriptor.
_HUMAN_TERMS = {
    "children": "children", "child": "children",
    "adults": "adults", "adult": "adults",
    "infants": "infants", "infant": "infants",
    "adolescents": "adolescents", "adolescent": "adolescents",
    "students": "students", "student": "students",
    "participants": "participants", "participant": "participants",
    "humans": "humans", "human": "humans",
    "individuals": "individuals", "individual": "individuals",
    "boys": "children", "girls": "children",
    "men": "adults", "women": "adults",
    "子ども": "children", "児童": "children", "学生": "students",
    "大人": "adults", "成人": "adults",
}

_HUMAN_PATTERN = re.compile(
    r"\b(\w+)\s+"
    r"(?:(?:typical(?:ly)?\s+developing|male|female|adult|young|older|healthy)\s+)*"
    r"(" + "|".join(re.escape(s) for s in _HUMAN_TERMS) + r")\b",
    re.IGNORECASE,
)

# Matches compile_method's output form "human served as subjects" / "humans
# served as subjects" so the species round-trips even when no count is
# carried through.
_HUMAN_ONLY_PATTERN = re.compile(
    r"\b(humans?|children|adults?|infants?|adolescents?|students?|participants?)\b"
    r"\s+(?:served\s+as\s+subjects|were\s+(?:the\s+)?subjects)",
    re.IGNORECASE,
)

_N_SPECIES_PATTERN = re.compile(
    r"\b(\w+)\s+"
    r"(?:(?:male|female|naive|experimentally\s+naive)\s+)*"
    r"(?:(\S+)\s+)?"
    r"(" + "|".join(re.escape(s) for s in _SPECIES) + r")\b",
    re.IGNORECASE,
)

# Subject sentences without a leading count. Matches the canonical form
# produced by ``contingency_dsl2procedure.sections.subjects`` when n is
# unknown ("rat served as subjects", "Pigeons served as subjects"), so
# a compile → re-extract round-trip converges even without a count.
_SPECIES_ONLY_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in _SPECIES) + r")\b"
    r"\s+(?:served\s+as\s+subjects|were\s+(?:the\s+)?subjects|pressed|pecked)",
    re.IGNORECASE,
)

_N_JA_PATTERN = re.compile(
    r"(\d+)\s*匹の\s*(?:(\S+)\s*系)?\s*(\S+)\s*を被験体",
)

_DEPRIVATION_PATTERN = re.compile(
    r"(\w+)\s+deprivation\s+for\s+approximately\s+(\d+)\s+hr",
    re.IGNORECASE,
)
_DEPRIVATION_JA_PATTERN = re.compile(
    r"約(\d+)時間前から(\w+)摂取を制限",
)


_STRAIN_STOPWORDS = frozenset({
    "a", "an", "the", "of", "in", "by", "for", "with", "and", "or", "to",
    "as", "at", "on", "from", "that", "this", "those", "these", "his", "her",
    "its", "their", "our", "my", "your", "is", "was", "were", "be", "been",
    "being", "had", "has", "have", "cold", "warm", "hot", "wild", "white",
    "black", "gray", "male", "female", "naive", "experimental", "control",
    "trained", "observed", "other", "another", "many", "few", "several",
    "some", "all", "each", "every",
})


def _is_species_false_positive(text: str, match: re.Match, species_raw: str) -> bool:
    """Guard against non-biological senses of species words.

    The obvious case: "mouse clicks", "mouse cursor", "mouse button" where
    "mouse" refers to a computer pointing device, not an animal.
    """
    if species_raw.lower() == "mouse":
        tail = text[match.end(): match.end() + 40].lower()
        if re.match(r"\s*(click|clicks|button|cursor|pointer|pad|wheel|over|\-)", tail):
            return True
    return False


def extract_subject_annotations(text: str) -> list[ExtractResult]:
    """Extract @species, @strain, @n, @deprivation, @history from text."""
    results: list[ExtractResult] = []

    for m in _N_SPECIES_PATTERN.finditer(text):
        n_word = m.group(1)
        strain = m.group(2) or ""
        species_raw = m.group(3)
        species = _SPECIES.get(species_raw.lower(), species_raw)
        n = _word_to_number(n_word)

        # Context guard: "mouse" often refers to a computer mouse, not an animal.
        if _is_species_false_positive(text, m, species_raw):
            continue

        # Strain stopword filter: common articles/adjectives are not strain names.
        if strain and strain.lower() in _STRAIN_STOPWORDS:
            strain = ""

        # Gate out spurious matches like "Imagine a rat", "and the rat",
        # "for a cold rat": if neither a valid count nor a plausible strain
        # name is present, the surrounding context is probably generic prose
        # rather than a real subject description.
        strain_looks_real = bool(strain) and (strain[0].isupper() or "-" in strain)

        # "Carneau pigeon" / "Wistar rat" — a proper-noun first word with
        # no optional-strain slot. Shift it from n_word to strain so the
        # strain information isn't lost when the regex's strain slot was
        # skipped. Guard against species-name self-reference at sentence
        # start ("Pigeon served as subjects." → don't promote "Pigeon"
        # to a strain).
        if (
            n is None
            and not strain
            and n_word
            and n_word[0].isupper()
            and n_word.lower() not in _STRAIN_STOPWORDS
            and n_word.lower() not in _SPECIES
            and n_word.lower() not in _HUMAN_TERMS
        ):
            strain = n_word
            strain_looks_real = True

        if n is None and not strain_looks_real:
            # Extra guard: also skip if n_word is a known stopword/article.
            if n_word.lower() in _STRAIN_STOPWORDS:
                continue
            # Otherwise keep @species only; don't emit @strain/@n.
            if species:
                results.append(_ann_result("species", species, m))
            continue

        if species:
            results.append(_ann_result("species", species, m))
        if strain:
            results.append(_ann_result("strain", strain, m))
        if n is not None:
            results.append(_ann_result("n", n, m))

    # Human-participant pattern. Emits @species("human") plus an optional
    # @population tag (children/adults/...) and @n when a count is present.
    # Gating: require a valid count or a descriptor like "typically developing"
    # before the population term so generic prose ("the participants performed
    # the task...") isn't treated as a subject description.
    for m in _HUMAN_PATTERN.finditer(text):
        n_word = m.group(1)
        term_raw = m.group(2).lower()
        population = _HUMAN_TERMS.get(term_raw, term_raw)
        n = _word_to_number(n_word)

        # Reject generic references: "the children", "our participants" etc.
        if n is None and n_word.lower() in _STRAIN_STOPWORDS:
            continue
        # Reject when neither a count nor a descriptor (male/female/typically)
        # precedes the population term — plain "the participants" is prose.
        if n is None:
            before = text[max(0, m.start() - 40): m.start()].lower()
            if not re.search(
                r"(typical(?:ly)?\s+developing|male|female|adult|young|older|healthy)\s*$",
                before,
            ):
                continue

        results.append(_ann_result("species", "human", m))
        if population and population not in {"subjects", "participants", "individuals", "humans"}:
            results.append(_ann_result("population", population, m))
        if n is not None:
            results.append(_ann_result("n", n, m))

    # Species-only pattern for texts like "rat served as subjects."
    for m in _SPECIES_ONLY_PATTERN.finditer(text):
        species_raw = m.group(1)
        species = _SPECIES.get(species_raw.lower(), species_raw)
        if _is_species_false_positive(text, m, species_raw):
            continue
        if species:
            results.append(_ann_result("species", species, m, confidence=0.70))

    for m in _HUMAN_ONLY_PATTERN.finditer(text):
        results.append(_ann_result("species", "human", m, confidence=0.70))

    for m in _N_JA_PATTERN.finditer(text):
        n = int(m.group(1))
        strain = m.group(2) or ""
        species_raw = m.group(3)
        species = _SPECIES.get(species_raw, species_raw)

        results.append(_ann_result("species", species, m, confidence=0.85))
        if strain:
            results.append(_ann_result("strain", strain, m, confidence=0.85))
        results.append(_ann_result("n", n, m, confidence=0.85))

    for m in _DEPRIVATION_PATTERN.finditer(text):
        target = m.group(1).lower()
        hours = int(m.group(2))
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "deprivation",
                 "params": {"hours": hours, "target": target}},
            confidence=0.85, span=(m.start(), m.end()), source_text=m.group(0),
        ))

    for m in _DEPRIVATION_JA_PATTERN.finditer(text):
        hours = int(m.group(1))
        target = m.group(2)
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "deprivation",
                 "params": {"hours": hours, "target": target}},
            confidence=0.85, span=(m.start(), m.end()), source_text=m.group(0),
        ))

    if re.search(r"experimentally\s+naive", text, re.IGNORECASE):
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "history", "positional": "naive"},
            confidence=0.85, span=(0, 0), source_text="experimentally naive",
        ))
    elif "実験経験がなかった" in text:
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "history", "positional": "naive"},
            confidence=0.85, span=(0, 0), source_text="実験経験がなかった",
        ))
    else:
        # @history with experienced (free-form description)
        m_exp = re.search(
            r"subjects\s+had\s+experience\s+with\s+(.+?)(?:\.|$)",
            text, re.IGNORECASE,
        )
        if m_exp:
            results.append(ExtractResult(
                ast={"type": "Annotation", "keyword": "history",
                     "positional": m_exp.group(1).strip()},
                confidence=0.70, span=(m_exp.start(), m_exp.end()),
                source_text=m_exp.group(0),
            ))
        m_exp_ja = re.search(r"被験体は(.+?)の経験があった", text)
        if m_exp_ja:
            results.append(ExtractResult(
                ast={"type": "Annotation", "keyword": "history",
                     "positional": m_exp_ja.group(1).strip()},
                confidence=0.70, span=(m_exp_ja.start(), m_exp_ja.end()),
                source_text=m_exp_ja.group(0),
            ))

    return results


# ===== Apparatus annotations =====

_CHAMBER_PATTERN = re.compile(
    r"(?:conducted\s+in\s+|実験は)(\S+)"
    r"(?:\s*\(Model\s+([^)]+)\))?"
    r"(?:\s+operant|の)",
    re.IGNORECASE,
)

_HARDWARE_PATTERN = re.compile(
    r"(?:controlled\s+and\s+data\s+were\s+recorded\s+by|"
    r"制御およびデータ記録には)\s*(.+?)(?:\.|。|を使用)",
    re.IGNORECASE,
)

# RT-R01: "Each chamber contained a left lever, and right lever."
_OPERANDUM_EN_PATTERN = re.compile(
    r"[Ee]ach\s+chamber\s+contained\s+(?:a\s+)?(.+?)(?:\.|$)",
)
# JA: "実験箱内にはleft lever、right leverが設置された。"
_OPERANDUM_JA_PATTERN = re.compile(
    r"実験箱内には(.+?)が設置された",
)

# RT-R02: "Responses on the left lever were reinforced according to a VI 30-s schedule"
_COMPONENT_ASSIGN_PATTERN = re.compile(
    r"[Rr]esponses\s+on\s+the\s+(.+?)\s+were\s+reinforced\s+"
    r"according\s+to\s+a\s+([A-Z]{2}\s+\d+(?:\.\d+)?(?:-(?:s|ms|min))?)\s+schedule",
)
# JA: "left leverへの反応はVI 30-sスケジュールに従って強化された。"
_COMPONENT_ASSIGN_JA_PATTERN = re.compile(
    r"(.+?)への反応は([A-Z]{2}\s*\d+(?:\.\d+)?(?:-(?:s|ms|min))?)スケジュール",
)


def extract_apparatus_annotations(text: str) -> list[ExtractResult]:
    """Extract @chamber, @hardware, @operandum (physical) from text."""
    results: list[ExtractResult] = []

    for m in _CHAMBER_PATTERN.finditer(text):
        name = m.group(1)
        model = m.group(2) or ""
        ann: dict = {"type": "Annotation", "keyword": "chamber", "positional": name}
        if model:
            ann["params"] = {"model": model}
        results.append(ExtractResult(
            ast=ann, confidence=0.80,
            span=(m.start(), m.end()), source_text=m.group(0),
        ))

    for m in _HARDWARE_PATTERN.finditer(text):
        hw = m.group(1).strip()
        if hw:
            results.append(ExtractResult(
                ast={"type": "Annotation", "keyword": "hardware", "positional": hw},
                confidence=0.80,
                span=(m.start(), m.end()), source_text=m.group(0),
            ))

    # RT-R01: operandum physical list
    for m in _OPERANDUM_EN_PATTERN.finditer(text):
        raw = m.group(1).strip()
        names = [n.strip() for n in re.split(r",\s*(?:and\s+)?|、", raw) if n.strip()]
        for name in names:
            name_id = name.replace(" ", "_")
            results.append(ExtractResult(
                ast={"type": "Annotation", "keyword": "operandum", "positional": name_id},
                confidence=0.75,
                span=(m.start(), m.end()), source_text=m.group(0),
            ))

    for m in _OPERANDUM_JA_PATTERN.finditer(text):
        raw = m.group(1).strip()
        names = [n.strip() for n in re.split(r"、", raw) if n.strip()]
        for name in names:
            name_id = name.replace(" ", "_")
            results.append(ExtractResult(
                ast={"type": "Annotation", "keyword": "operandum", "positional": name_id},
                confidence=0.75,
                span=(m.start(), m.end()), source_text=m.group(0),
            ))

    return results


# RT-R02: component assignment extraction
def extract_component_annotations(text: str) -> list[ExtractResult]:
    """Extract @operandum component assignment and @sd from procedure text."""
    results: list[ExtractResult] = []
    comp_idx = 0

    for m in _COMPONENT_ASSIGN_PATTERN.finditer(text):
        comp_idx += 1
        op_name = m.group(1).replace(" ", "_")
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "operandum",
                 "positional": op_name, "params": {"component": comp_idx}},
            confidence=0.80,
            span=(m.start(), m.end()), source_text=m.group(0),
        ))

    comp_idx = 0
    for m in _COMPONENT_ASSIGN_JA_PATTERN.finditer(text):
        comp_idx += 1
        op_name = m.group(1).replace(" ", "_")
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "operandum",
                 "positional": op_name, "params": {"component": comp_idx}},
            confidence=0.80,
            span=(m.start(), m.end()), source_text=m.group(0),
        ))

    # RT-R03: @sd — "in the presence of red light" / "in the presence of the SD"
    # Require the SD name to be a concrete stimulus-like token (alphanumeric,
    # no trailing punctuation). Skip generic phrases like "those stimuli",
    # "his or her peers" etc.
    _SD_STOPWORDS = {
        "the", "a", "an", "this", "that", "those", "these", "such", "other",
        "his", "her", "their", "its", "our", "your", "some", "any", "all",
    }
    for m in re.finditer(
        r"in\s+the\s+presence\s+of\s+([A-Za-z][\w]*(?:\s+[A-Za-z][\w]*)?)",
        text, re.IGNORECASE,
    ):
        sd_raw = m.group(1).rstrip(",.;:").strip()
        first_token = sd_raw.split()[0].lower() if sd_raw else ""
        if not sd_raw or first_token in _SD_STOPWORDS:
            continue
        sd_name = sd_raw.replace(" ", "_")
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "sd", "positional": sd_name},
            confidence=0.75,
            span=(m.start(), m.end()), source_text=m.group(0),
        ))

    # JA @sd: "（red_light点灯時）"
    for m in re.finditer(r"（(.+?)点灯時）", text):
        sd_name = m.group(1).replace(" ", "_")
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "sd", "positional": sd_name},
            confidence=0.75,
            span=(m.start(), m.end()), source_text=m.group(0),
        ))

    return results


# ===== Measurement annotations =====

_SESSION_END_FIRST = re.compile(
    r"[Ss]essions?\s+terminated\s+after\s+(\d+)[-\s]+(min|s|ms)\s+"
    r"or\s+(\d+)\s+reinforcer\s+deliveries.*?whichever\s+occurred\s+first",
    re.IGNORECASE,
)
_SESSION_END_TIME = re.compile(
    r"[Ss]essions?\s+terminated\s+after\s+(\d+)[-\s]+(min|s|ms)\b"
    r"(?!.*reinforcer)",
    re.IGNORECASE,
)
_SESSION_END_REINFORCERS = re.compile(
    r"[Ss]essions?\s+terminated\s+after\s+(\d+)\s+reinforcer\s+deliveries",
    re.IGNORECASE,
)
_SESSION_END_JA_FIRST = re.compile(
    r"(\d+)[-\s]*(min|s)\s*経過または(\d+)回の強化子呈示.*?早い方",
)
_SESSION_END_JA_TIME = re.compile(
    r"セッションは(\d+)[-\s]*(min|s)\s*経過後に終了",
)

# RT-R10/R11: steady_state with min_sessions and measure
_STEADY_STATE = re.compile(
    r"[Ss]tability.*?last\s+(\d+)\s+sessions.*?"
    r"(\d+)%\s+variation\s+in\s+(\w+(?:\s+\w+)?)"
    r"(?:\s*\(minimum\s+(\d+)\s+sessions\))?",
    re.IGNORECASE,
)
_STEADY_STATE_JA = re.compile(
    r"直近(\d+)セッションの(.+?)の変動が(\d+)%以内"
    r"(?:.*?最低(\d+)セッション)?",
)

_MEASURE_MAP = {
    "response rates": "rate",
    "reinforcement rates": "reinforcers",
    "interresponse times": "iri",
    "latencies": "latency",
}
_MEASURE_MAP_JA = {
    "反応率": "rate",
    "強化率": "reinforcers",
    "反応間間隔": "iri",
    "潜時": "latency",
}

# RT-R04: baseline
_BASELINE_PATTERN = re.compile(
    r"(\d+)\s+pretraining\s+sessions",
    re.IGNORECASE,
)
_BASELINE_JA_PATTERN = re.compile(
    r"(\d+)セッションの事前訓練",
)

# RT-R05: algorithm — "Fleshler and Hoffman (1962)"
_ALGORITHM_FH_PATTERN = re.compile(
    r"(?:Fleshler\s+and\s+Hoffman\s*\(1962\)|Fleshler\s*&\s*Hoffman\s*,?\s*1962)"
    r"(?:\s+with\s+(\d+)\s+intervals)?",
    re.IGNORECASE,
)

# RT-R06: warmup
_WARMUP_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)\s+warm-?up\s+period",
    re.IGNORECASE,
)
_WARMUP_JA_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)のウォームアップ",
)


def extract_measurement_annotations(text: str) -> list[ExtractResult]:
    """Extract @session_end, @steady_state, @baseline, @algorithm, @warmup."""
    results: list[ExtractResult] = []

    # Session end
    m = _SESSION_END_FIRST.search(text)
    if m:
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "session_end",
                 "params": {"rule": "first",
                            "time": {"value": int(m.group(1)), "time_unit": m.group(2)},
                            "reinforcers": int(m.group(3))}},
            confidence=0.90, span=(m.start(), m.end()), source_text=m.group(0),
        ))
    else:
        m = _SESSION_END_REINFORCERS.search(text)
        if m:
            results.append(ExtractResult(
                ast={"type": "Annotation", "keyword": "session_end",
                     "params": {"rule": "reinforcers_only", "reinforcers": int(m.group(1))}},
                confidence=0.85, span=(m.start(), m.end()), source_text=m.group(0),
            ))
        else:
            m = _SESSION_END_TIME.search(text)
            if m:
                results.append(ExtractResult(
                    ast={"type": "Annotation", "keyword": "session_end",
                         "params": {"rule": "time_only",
                                    "time": {"value": int(m.group(1)), "time_unit": m.group(2)}}},
                    confidence=0.85, span=(m.start(), m.end()), source_text=m.group(0),
                ))

    # JA session end
    m = _SESSION_END_JA_FIRST.search(text)
    if m:
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "session_end",
                 "params": {"rule": "first",
                            "time": {"value": int(m.group(1)), "time_unit": m.group(2)},
                            "reinforcers": int(m.group(3))}},
            confidence=0.85, span=(m.start(), m.end()), source_text=m.group(0),
        ))
    else:
        m = _SESSION_END_JA_TIME.search(text)
        if m:
            results.append(ExtractResult(
                ast={"type": "Annotation", "keyword": "session_end",
                     "params": {"rule": "time_only",
                                "time": {"value": int(m.group(1)), "time_unit": m.group(2)}}},
                confidence=0.80, span=(m.start(), m.end()), source_text=m.group(0),
            ))

    # Steady state (EN) — RT-R10/R11 fixed
    m = _STEADY_STATE.search(text)
    if m:
        measure_raw = m.group(3).lower().strip()
        measure = _MEASURE_MAP.get(measure_raw, measure_raw)
        params: dict = {
            "window_sessions": int(m.group(1)),
            "max_change_pct": int(m.group(2)),
            "measure": measure,
        }
        if m.group(4):
            params["min_sessions"] = int(m.group(4))
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "steady_state", "params": params},
            confidence=0.80, span=(m.start(), m.end()), source_text=m.group(0),
        ))

    # RT-R07: Steady state (JA)
    m = _STEADY_STATE_JA.search(text)
    if m:
        measure_raw = m.group(2).strip()
        measure = _MEASURE_MAP_JA.get(measure_raw, measure_raw)
        params_ja: dict = {
            "window_sessions": int(m.group(1)),
            "max_change_pct": int(m.group(3)),
            "measure": measure,
        }
        if m.group(4):
            params_ja["min_sessions"] = int(m.group(4))
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "steady_state", "params": params_ja},
            confidence=0.80, span=(m.start(), m.end()), source_text=m.group(0),
        ))

    # RT-R04: baseline
    for m in _BASELINE_PATTERN.finditer(text):
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "baseline",
                 "params": {"pre_training_sessions": int(m.group(1))}},
            confidence=0.85, span=(m.start(), m.end()), source_text=m.group(0),
        ))
    for m in _BASELINE_JA_PATTERN.finditer(text):
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "baseline",
                 "params": {"pre_training_sessions": int(m.group(1))}},
            confidence=0.85, span=(m.start(), m.end()), source_text=m.group(0),
        ))

    # RT-R05: algorithm
    for m in _ALGORITHM_FH_PATTERN.finditer(text):
        params_alg: dict = {}
        if m.group(1):
            params_alg["n"] = int(m.group(1))
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "algorithm",
                 "positional": "fleshler-hoffman", **({"params": params_alg} if params_alg else {})},
            confidence=0.85, span=(m.start(), m.end()), source_text=m.group(0),
        ))

    # RT-R06: warmup
    for m in _WARMUP_PATTERN.finditer(text):
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "warmup",
                 "params": {"duration": float(m.group(1)), "time_unit": m.group(2)}},
            confidence=0.85, span=(m.start(), m.end()), source_text=m.group(0),
        ))
    for m in _WARMUP_JA_PATTERN.finditer(text):
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "warmup",
                 "params": {"duration": float(m.group(1)), "time_unit": m.group(2)}},
            confidence=0.85, span=(m.start(), m.end()), source_text=m.group(0),
        ))

    return results


# ===== Procedure annotations =====

_REINFORCER_PATTERN = re.compile(
    r"[Rr]einforcement\s+consisted\s+of\s+(.+?)\s+delivery"
    r"|強化子として(.+?)を使用",
)

_PUNISHER_PATTERN = re.compile(
    r"(.+?)\s+served\s+as\s+the\s+punisher"
    r"|罰刺激として(.+?)を使用",
)

_CS_PATTERN = re.compile(
    r"(\w+)\s+served\s+as\s+the\s+conditioned\s+stimulus\b"
    r"|(\S+?)を条件刺激として",
)

_US_PATTERN = re.compile(
    r"(\w+)\s+served\s+as\s+the\s+unconditioned\s+stimulus\b"
    r"|(\S+?)を無条件刺激として",
)

_CONTEXT_PATTERN = re.compile(
    r"procedure\s+was\s+conducted\s+in\s+context\s+([A-Za-z0-9_]+)"
    r"(?:\s+\(cues:\s*(.+?)\))?"
    r"|文脈([A-Za-z0-9_]+)で実施された"
    r"(?:（(.+?)）)?",
    re.IGNORECASE,
)

_CLOCK_PATTERN = re.compile(
    r"[Ss]ession\s+time\s+was\s+recorded\s+in\s+(s|ms|min)\b"
    r"|セッションの時間単位は\s*(s|ms|min)",
)

_DEPENDENT_EN = re.compile(
    r"(?:primary\s+)?dependent\s+measure\s+was\s+(\w+)",
    re.IGNORECASE,
)
_DEPENDENT_JA = re.compile(
    r"主要従属変数は(.+?)であった",
)

_SESSION_TRIALS_EN = re.compile(
    r"[Ee]ach\s+session\s+consisted\s+of\s+(\d+)\s+trials",
)
_SESSION_TRIALS_JA = re.compile(
    r"各セッションは(\d+)試行で構成された",
)
_SESSION_BLOCKS_EN = re.compile(
    r"[Ee]ach\s+session\s+consisted\s+of\s+(\d+)\s+blocks\s+of\s+(\d+)\s+trials",
)
_SESSION_BLOCKS_JA = re.compile(
    r"各セッションは(\d+)ブロック×(\d+)試行で構成された",
)

_CS_INTERVAL_EN = re.compile(
    r"CS-US\s+interval\s+was\s+(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)",
    re.IGNORECASE,
)
_CS_INTERVAL_JA = re.compile(
    r"CS-US\s*間隔は\s*(\d+(?:\.\d+)?)\s*-?\s*(s|ms|min)",
)


def extract_procedure_annotations(text: str) -> list[ExtractResult]:
    """Extract procedure-category annotations from text.

    Covers:
      - ``@reinforcer`` / ``@punisher`` (procedure-stimulus)
      - ``@cs`` / ``@us`` (procedure-stimulus for respondent work)
      - ``@context`` (procedure-context)
      - ``@clock`` (procedure-temporal time unit)
      - ``@session`` (procedure-trial-structure trial counts)
      - ``@cs_interval`` (procedure-temporal CS-US interval)
      - ``@dependent_measure`` (measurement, keyed here because it lives
        in Procedure sections in JEAB style)
    """
    results: list[ExtractResult] = []

    for m in _REINFORCER_PATTERN.finditer(text):
        name = m.group(1) or m.group(2)
        if name:
            results.append(ExtractResult(
                ast={"type": "Annotation", "keyword": "reinforcer", "positional": name.strip()},
                confidence=0.85, span=(m.start(), m.end()), source_text=m.group(0),
            ))

    for m in _PUNISHER_PATTERN.finditer(text):
        name = m.group(1) or m.group(2)
        if name:
            results.append(ExtractResult(
                ast={"type": "Annotation", "keyword": "punisher", "positional": name.strip()},
                confidence=0.80, span=(m.start(), m.end()), source_text=m.group(0),
            ))

    for m in _CS_PATTERN.finditer(text):
        name = m.group(1) or m.group(2)
        if name:
            results.append(ExtractResult(
                ast={"type": "Annotation", "keyword": "cs", "positional": name.strip()},
                confidence=0.80, span=(m.start(), m.end()), source_text=m.group(0),
            ))

    for m in _US_PATTERN.finditer(text):
        name = m.group(1) or m.group(2)
        if name:
            results.append(ExtractResult(
                ast={"type": "Annotation", "keyword": "us", "positional": name.strip()},
                confidence=0.80, span=(m.start(), m.end()), source_text=m.group(0),
            ))

    for m in _CONTEXT_PATTERN.finditer(text):
        label = m.group(1) or m.group(3)
        cues = m.group(2) or m.group(4)
        if label:
            params: dict = {}
            if cues:
                params["cues"] = cues.strip()
            ast: dict = {
                "type": "Annotation",
                "keyword": "context",
                "positional": label.strip(),
            }
            if params:
                ast["params"] = params
            results.append(ExtractResult(
                ast=ast, confidence=0.80,
                span=(m.start(), m.end()), source_text=m.group(0),
            ))

    for m in _CLOCK_PATTERN.finditer(text):
        unit = m.group(1) or m.group(2)
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "clock",
                 "params": {"unit": unit}},
            confidence=0.85,
            span=(m.start(), m.end()), source_text=m.group(0),
        ))

    m = _DEPENDENT_EN.search(text)
    if m:
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "dependent_measure",
                 "params": {"variables": [m.group(1).strip()]}},
            confidence=0.75,
            span=(m.start(), m.end()), source_text=m.group(0),
        ))
    m = _DEPENDENT_JA.search(text)
    if m:
        vars_raw = [v.strip() for v in re.split(r"、|,", m.group(1)) if v.strip()]
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "dependent_measure",
                 "params": {"variables": vars_raw}},
            confidence=0.75,
            span=(m.start(), m.end()), source_text=m.group(0),
        ))

    m = _SESSION_BLOCKS_EN.search(text) or _SESSION_BLOCKS_JA.search(text)
    if m:
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "session",
                 "params": {"blocks": int(m.group(1)), "block_size": int(m.group(2))}},
            confidence=0.80,
            span=(m.start(), m.end()), source_text=m.group(0),
        ))
    else:
        m = _SESSION_TRIALS_EN.search(text) or _SESSION_TRIALS_JA.search(text)
        if m:
            results.append(ExtractResult(
                ast={"type": "Annotation", "keyword": "session",
                     "params": {"trials": int(m.group(1))}},
                confidence=0.80,
                span=(m.start(), m.end()), source_text=m.group(0),
            ))

    m = _CS_INTERVAL_EN.search(text) or _CS_INTERVAL_JA.search(text)
    if m:
        results.append(ExtractResult(
            ast={"type": "Annotation", "keyword": "cs_interval",
                 "params": {"value": float(m.group(1)), "time_unit": m.group(2)}},
            confidence=0.80,
            span=(m.start(), m.end()), source_text=m.group(0),
        ))

    return results


# ===== Helpers =====

def _ann_result(
    keyword: str, positional: object, m: re.Match, *, confidence: float = 0.80,
) -> ExtractResult:
    return ExtractResult(
        ast={"type": "Annotation", "keyword": keyword, "positional": positional},
        confidence=confidence,
        span=(m.start(), m.end()),
        source_text=m.group(0),
    )


def _word_to_number(word: str) -> int | None:
    words = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12,
    }
    if word.isdigit():
        return int(word)
    return words.get(word.lower())
