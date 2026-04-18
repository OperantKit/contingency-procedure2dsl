"""Full-stack roundtrip with realistic JEAB Method sections.

JEAB paper prose → reader → DSL AST → paper → JEAB prose → reader → verify.

Tests use Method sections modeled after real publications to find
gaps in both reader and paper packages.
"""

from __future__ import annotations

import json

import pytest

from contingency_dsl_paper import compile_method
from contingency_dsl_reader import extract_all, extract_schedule
from contingency_dsl_reader.result import ExtractionReport


def _program(
    schedule: dict,
    param_decls: list[dict] | None = None,
    program_annotations: list[dict] | None = None,
) -> dict:
    d: dict = {
        "type": "Program",
        "param_decls": param_decls or [],
        "bindings": [],
        "schedule": schedule,
    }
    if program_annotations:
        d["program_annotations"] = program_annotations
    return d


# ─────────────────────────────────────────────────────────
# Scenario 1: Simple VI schedule (typical single-schedule)
# Modeled after Catania & Reynolds (1968)
# ─────────────────────────────────────────────────────────

SCENARIO_1_AST = _program(
    schedule={"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
    program_annotations=[
        {"type": "Annotation", "keyword": "species", "positional": "rat", "params": {}},
        {"type": "Annotation", "keyword": "strain", "positional": "Sprague-Dawley", "params": {}},
        {"type": "Annotation", "keyword": "n", "positional": 4, "params": {}},
        {"type": "Annotation", "keyword": "deprivation", "params": {"hours": 22, "target": "food"}},
        {"type": "Annotation", "keyword": "chamber", "positional": "med-associates", "params": {}},
        {"type": "Annotation", "keyword": "operandum", "positional": "left_lever", "params": {}},
        {"type": "Annotation", "keyword": "reinforcer", "positional": "food pellet", "params": {}},
        {
            "type": "Annotation",
            "keyword": "session_end",
            "params": {"rule": "first", "time": 3600, "reinforcers": 60},
        },
    ],
)


class TestScenario1SimpleVI:
    """Simple VI 60-s schedule, full annotations."""

    def test_ast_to_paper(self) -> None:
        ms = compile_method(SCENARIO_1_AST)
        assert "60-s" in ms.procedure
        assert "variable-interval" in ms.procedure.lower() or "VI" in ms.procedure
        assert ms.subjects  # non-empty
        assert ms.apparatus  # non-empty

    def test_ast_to_paper_to_reader_schedule(self) -> None:
        ms = compile_method(SCENARIO_1_AST)
        full_text = ms.to_text()
        recovered = extract_schedule(full_text)
        assert recovered is not None, f"Reader failed to extract from:\n{full_text}"
        assert recovered.ast["dist"] == "V"
        assert recovered.ast["domain"] == "I"
        assert recovered.ast["value"] == 60.0

    def test_ast_to_paper_to_reader_annotations(self) -> None:
        ms = compile_method(SCENARIO_1_AST)
        full_text = ms.to_text()
        report = extract_all(full_text)
        # Check annotations recovery
        ann_kws = {a.ast["keyword"] for a in report.annotations}
        assert "species" in ann_kws, f"species not found. Annotations: {report.annotations}"
        assert "reinforcer" in ann_kws, f"reinforcer not found. Annotations: {report.annotations}"


# ─────────────────────────────────────────────────────────
# Scenario 2: Concurrent VI VI with COD
# Modeled after Herrnstein (1961)
# ─────────────────────────────────────────────────────────

SCENARIO_2_AST = _program(
    schedule={
        "type": "Compound",
        "combinator": "Conc",
        "components": [
            {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"},
            {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
        ],
    },
    param_decls=[],
    program_annotations=[
        {"type": "Annotation", "keyword": "species", "positional": "pigeon", "params": {}},
        {"type": "Annotation", "keyword": "n", "positional": 3, "params": {}},
        {"type": "Annotation", "keyword": "reinforcer", "positional": "mixed grain", "params": {}},
    ],
)


class TestScenario2ConcurrentVIVI:
    """Conc(VI 30-s, VI 60-s) — choice procedure."""

    def test_roundtrip_schedule(self) -> None:
        ms = compile_method(SCENARIO_2_AST)
        recovered = extract_schedule(ms.procedure)
        assert recovered is not None, f"Failed on:\n{ms.procedure}"
        assert recovered.ast["type"] == "Compound"
        assert recovered.ast["combinator"] == "Conc"
        assert len(recovered.ast["components"]) == 2

    def test_paper_mentions_concurrent(self) -> None:
        ms = compile_method(SCENARIO_2_AST)
        text_lower = ms.procedure.lower()
        assert "concurrent" in text_lower or "conc" in text_lower


# ─────────────────────────────────────────────────────────
# Scenario 3: Tandem VI FT (delayed reinforcement)
# Modeled after Sizemore & Lattal (1978)
# ─────────────────────────────────────────────────────────

SCENARIO_3_AST = _program(
    schedule={
        "type": "Compound",
        "combinator": "Tand",
        "components": [
            {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            {"type": "Atomic", "dist": "F", "domain": "T", "value": 5.0, "time_unit": "s"},
        ],
    },
    program_annotations=[
        {"type": "Annotation", "keyword": "species", "positional": "pigeon", "params": {}},
        {"type": "Annotation", "keyword": "n", "positional": 4, "params": {}},
    ],
)


class TestScenario3TandemDelay:
    """Tand(VI 60-s, FT 5-s) — unsignaled delay of reinforcement."""

    def test_roundtrip_schedule(self) -> None:
        ms = compile_method(SCENARIO_3_AST)
        recovered = extract_schedule(ms.procedure)
        assert recovered is not None, f"Failed on:\n{ms.procedure}"
        assert recovered.ast["type"] == "Compound"
        assert recovered.ast["combinator"] == "Tand"

    def test_paper_mentions_tandem(self) -> None:
        ms = compile_method(SCENARIO_3_AST)
        text_lower = ms.procedure.lower()
        assert "tandem" in text_lower or "tand" in text_lower


# ─────────────────────────────────────────────────────────
# Scenario 4: Multiple schedule (behavioral contrast)
# Modeled after Reynolds (1961)
# ─────────────────────────────────────────────────────────

SCENARIO_4_AST = _program(
    schedule={
        "type": "Compound",
        "combinator": "Mult",
        "components": [
            {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            {"type": "Special", "kind": "EXT"},
        ],
    },
)


class TestScenario4MultVIEXT:
    """Mult(VI 60-s, EXT) — behavioral contrast paradigm."""

    def test_roundtrip_schedule(self) -> None:
        ms = compile_method(SCENARIO_4_AST)
        recovered = extract_schedule(ms.procedure)
        assert recovered is not None, f"Failed on:\n{ms.procedure}"
        # Should recover either compound or at least the VI component
        if recovered.ast.get("type") == "Compound":
            assert recovered.ast["combinator"] == "Mult"


# ─────────────────────────────────────────────────────────
# Scenario 5: DRL schedule
# Modeled after Kramer & Rilling (1970)
# ─────────────────────────────────────────────────────────

SCENARIO_5_AST = _program(
    schedule={"type": "Modifier", "modifier": "DRL", "value": 20.0, "time_unit": "s"},
)


class TestScenario5DRL:
    """DRL 20-s — differential reinforcement of low rate."""

    def test_roundtrip_schedule(self) -> None:
        ms = compile_method(SCENARIO_5_AST)
        recovered = extract_schedule(ms.procedure)
        assert recovered is not None, f"Failed on:\n{ms.procedure}"
        assert recovered.ast["modifier"] == "DRL"
        assert recovered.ast["value"] == 20.0


# ─────────────────────────────────────────────────────────
# Scenario 6: Second-order schedule
# Modeled after Kelleher (1966)
# ─────────────────────────────────────────────────────────

SCENARIO_6_AST = _program(
    schedule={
        "type": "SecondOrder",
        "overall": {"type": "Atomic", "dist": "F", "domain": "I", "value": 600.0, "time_unit": "s"},
        "unit": {"type": "Atomic", "dist": "F", "domain": "R", "value": 10.0},
    },
)


class TestScenario6SecondOrder:
    """FI 600-s(FR 10) — second-order schedule."""

    def test_roundtrip_schedule(self) -> None:
        ms = compile_method(SCENARIO_6_AST)
        recovered = extract_schedule(ms.procedure)
        assert recovered is not None, f"Failed on:\n{ms.procedure}"
        assert recovered.ast["type"] == "SecondOrder"


# ─────────────────────────────────────────────────────────
# Scenario 7: RD param_decl (new feature)
# ─────────────────────────────────────────────────────────

SCENARIO_7_AST = _program(
    schedule={"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
    param_decls=[{"type": "ParamDecl", "name": "RD", "value": 500.0, "time_unit": "ms"}],
)


class TestScenario7ReinforcementDelay:
    """VI 60-s with RD = 500ms — session-wide reinforcement delay."""

    def test_paper_compiles(self) -> None:
        """Paper should compile without error even if RD rendering is not yet implemented."""
        ms = compile_method(SCENARIO_7_AST)
        assert ms.procedure  # non-empty

    def test_paper_mentions_delay_or_schedule(self) -> None:
        """At minimum, the base schedule should be rendered."""
        ms = compile_method(SCENARIO_7_AST)
        assert "VI" in ms.procedure or "variable-interval" in ms.procedure.lower()


# ─────────────────────────────────────────────────────────
# Scenario 8: Realistic JEAB prose (hand-written, not generated)
# Modeled after a typical Sizemore & Lattal (1978) Method
# ─────────────────────────────────────────────────────────

REALISTIC_JEAB_PROSE = """\
Subjects. Four White Carneau pigeons served as subjects. The pigeons were \
maintained at approximately 80% of their free-feeding weights by \
supplemental feeding of mixed grain after sessions.

Apparatus. The experimental chamber was a standard Lehigh Valley Electronics \
pigeon chamber. A single response key was located on the front panel. \
Experimental events were controlled and data were recorded by a \
MED-PC IV system.

Procedure. Responses on the key produced food according to a \
variable-interval (VI) 60-s schedule. Sessions terminated after 60 \
reinforcers or 60 min, whichever occurred first.
"""


class TestScenario8RealisticProse:
    """Extract schedule from hand-written JEAB prose."""

    def test_extract_schedule(self) -> None:
        recovered = extract_schedule(REALISTIC_JEAB_PROSE)
        assert recovered is not None, "Failed to extract from realistic JEAB prose"
        assert recovered.ast["dist"] == "V"
        assert recovered.ast["domain"] == "I"
        assert recovered.ast["value"] == 60.0

    def test_extract_annotations(self) -> None:
        report = extract_all(REALISTIC_JEAB_PROSE)
        ann_kws = {a.ast["keyword"] for a in report.annotations}
        # Species should be detected
        assert "species" in ann_kws, f"species not found. Got: {ann_kws}"

    def test_full_roundtrip_prose_to_ast_to_prose(self) -> None:
        """Prose → AST → paper → extract again."""
        # Step 1: Extract from prose
        report = extract_all(REALISTIC_JEAB_PROSE)
        assert report.primary_schedule is not None

        # Step 2: Build AST dict
        program = report.to_program()

        # Step 3: Compile to paper
        ms = compile_method(program)
        generated_text = ms.to_text()

        # Step 4: Extract from generated text
        recovered = extract_schedule(generated_text)
        assert recovered is not None, f"Re-extraction failed on:\n{generated_text}"
        assert recovered.ast["dist"] == "V"
        assert recovered.ast["domain"] == "I"
