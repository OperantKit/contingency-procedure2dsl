"""Gap analysis: identify what's lost in roundtrip.

Each test documents a specific gap found during realistic roundtrip testing.
Tests marked xfail are KNOWN ISSUES to fix.
"""

from __future__ import annotations

import pytest

from contingency_dsl_paper import compile_method
from contingency_dsl_reader import extract_all, extract_schedule


def _program(schedule, param_decls=None, program_annotations=None):
    d = {"type": "Program", "param_decls": param_decls or [], "bindings": [], "schedule": schedule}
    if program_annotations:
        d["program_annotations"] = program_annotations
    return d


# ─────────────────────────────────────────────────────────
# GAP 1: session_end time unit — paper renders seconds as minutes
# Bug: time=3600 (seconds, normalized by annotation system) → "3600 min"
# Should be: "60 min" or "3600 s"
# ─────────────────────────────────────────────────────────

class TestGap1SessionEndTimeUnit:
    """Paper renders session_end time in wrong unit."""

    def test_session_end_time_unit_correct(self) -> None:
        ast = _program(
            schedule={"type": "Atomic", "dist": "F", "domain": "R", "value": 5.0},
            program_annotations=[
                {"type": "Annotation", "keyword": "session_end",
                 "params": {"rule": "first", "time": 3600, "reinforcers": 60}},
            ],
        )
        ms = compile_method(ast)
        assert "3600 min" not in ms.procedure, \
            f"Bug: time=3600 (seconds) rendered as '3600 min'. Got:\n{ms.procedure}"


# ─────────────────────────────────────────────────────────
# GAP 2: RD prose quality — paper says "RD" instead of natural prose
# Paper generates: "A 500-ms RD was in effect."
# JEAB would say: "A 500-ms delay was imposed between schedule completion
# and reinforcer delivery."
# ─────────────────────────────────────────────────────────

class TestGap2RDProseQuality:
    """Paper renders RD but prose is not publication-ready."""

    def test_rd_is_rendered(self) -> None:
        """Paper DOES mention the delay — this works."""
        ast = _program(
            schedule={"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            param_decls=[{"type": "ParamDecl", "name": "RD", "value": 500.0, "time_unit": "ms"}],
        )
        ms = compile_method(ast)
        assert "500" in ms.procedure

    def test_rd_uses_natural_language(self) -> None:
        """JEAB prose should say 'delay' not 'RD'."""
        ast = _program(
            schedule={"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            param_decls=[{"type": "ParamDecl", "name": "RD", "value": 500.0, "time_unit": "ms"}],
        )
        ms = compile_method(ast)
        proc_lower = ms.procedure.lower()
        assert "delay" in proc_lower, \
            f"Should use 'delay' not 'RD' in JEAB prose. Got:\n{ms.procedure}"


# ─────────────────────────────────────────────────────────
# GAP 3: Reader has no delay extraction pattern
# ─────────────────────────────────────────────────────────

class TestGap3RDNotExtracted:
    """Reader can't extract delay information from prose."""

    def test_extract_delay_from_prose(self) -> None:
        text = (
            "Responses on the key produced food according to a VI 60-s schedule. "
            "A 0.5-s delay was imposed between the response that completed the "
            "schedule requirement and food delivery."
        )
        report = extract_all(text)
        param_names = {p.ast.get("name") for p in report.params}
        assert "RD" in param_names


# ─────────────────────────────────────────────────────────
# GAP 4: Overlay prose quality
# Paper generates: "overlay VI 60-s continuous reinforcement schedule"
# JEAB would say: "Responses were reinforced under a VI 60-s schedule.
# In addition, a response-produced 0.5-s shock was superimposed on the
# baseline (CRF punishment schedule)."
# ─────────────────────────────────────────────────────────

class TestGap4OverlayProseQuality:
    """Paper handles Overlay but prose is not publication-ready."""

    def test_overlay_compiles(self) -> None:
        """Paper DOES compile Overlay — this works."""
        ast = _program(schedule={
            "type": "Compound",
            "combinator": "Overlay",
            "components": [
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
                {"type": "Special", "kind": "CRF"},
            ],
        })
        ms = compile_method(ast)
        assert ms.procedure  # non-empty

    def test_overlay_mentions_punishment(self) -> None:
        ast = _program(schedule={
            "type": "Compound",
            "combinator": "Overlay",
            "components": [
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
                {"type": "Special", "kind": "CRF"},
            ],
        })
        ms = compile_method(ast)
        proc_lower = ms.procedure.lower()
        assert "punishment" in proc_lower or "superimposed" in proc_lower or "added" in proc_lower, \
            f"Overlay should describe punishment. Got:\n{ms.procedure}"


# ─────────────────────────────────────────────────────────
# GAP 5: COD keyword args on Conc — parser doesn't support compound params
# ─────────────────────────────────────────────────────────

    # GAP 5 (COD keyword args) resolved — tested in contingency-dsl-py/tests/test_compound_params.py


# ─────────────────────────────────────────────────────────
# WORKS: Sidman roundtrip through paper → reader
# ─────────────────────────────────────────────────────────

class TestWorksSidmanRoundtrip:
    """Sidman avoidance: paper → reader roundtrip works."""

    def test_sidman_roundtrip(self) -> None:
        ast = _program(schedule={
            "type": "AversiveSchedule",
            "kind": "Sidman",
            "params": {
                "SSI": {"value": 20.0, "time_unit": "s"},
                "RSI": {"value": 5.0, "time_unit": "s"},
            },
        })
        ms = compile_method(ast)
        recovered = extract_schedule(ms.procedure)
        assert recovered is not None
        assert recovered.ast["kind"] == "Sidman"


# ─────────────────────────────────────────────────────────
# WORKS: LH roundtrip
# ─────────────────────────────────────────────────────────

class TestWorksLHRoundtrip:
    """LH paper → reader roundtrip works."""

    def test_lh_roundtrip(self) -> None:
        ast = _program(schedule={
            "type": "Atomic",
            "dist": "F", "domain": "I", "value": 30.0, "time_unit": "s",
            "limitedHold": 10.0, "limitedHoldUnit": "s",
        })
        ms = compile_method(ast)
        recovered = extract_schedule(ms.procedure)
        assert recovered is not None
        assert recovered.ast["type"] == "Atomic"
        assert recovered.ast["limitedHold"] == 10.0
