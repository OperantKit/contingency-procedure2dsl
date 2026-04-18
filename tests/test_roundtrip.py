"""Roundtrip tests: DSL AST → paper → reader → AST.

Verifies that contingency-dsl2procedure output can be round-tripped through
contingency-procedure2dsl to recover the original schedule structure.
"""

from contingency_dsl2procedure import compile_method
from contingency_procedure2dsl import extract_schedule


def _program(schedule: dict) -> dict:
    return {
        "type": "Program",
        "param_decls": [],
        "bindings": [],
        "schedule": schedule,
    }


class TestRoundtripAtomic:
    """Atomic schedule roundtrip: AST → paper → reader → AST."""

    def test_fr(self) -> None:
        original = {"type": "Atomic", "dist": "F", "domain": "R", "value": 5.0}
        prose = compile_method(_program(original)).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["dist"] == "F"
        assert recovered.ast["domain"] == "R"
        assert recovered.ast["value"] == 5.0

    def test_vi(self) -> None:
        original = {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"}
        prose = compile_method(_program(original)).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["dist"] == "V"
        assert recovered.ast["domain"] == "I"
        assert recovered.ast["value"] == 30.0

    def test_ft(self) -> None:
        original = {"type": "Atomic", "dist": "F", "domain": "T", "value": 20.0, "time_unit": "s"}
        prose = compile_method(_program(original)).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["dist"] == "F"
        assert recovered.ast["domain"] == "T"
        assert recovered.ast["value"] == 20.0

    def test_vr(self) -> None:
        original = {"type": "Atomic", "dist": "V", "domain": "R", "value": 20.0}
        prose = compile_method(_program(original)).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["dist"] == "V"
        assert recovered.ast["domain"] == "R"
        assert recovered.ast["value"] == 20.0


class TestRoundtripCompound:
    """Compound schedule roundtrip."""

    def test_concurrent_vi_vi(self) -> None:
        original = {
            "type": "Compound",
            "combinator": "Conc",
            "components": [
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"},
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            ],
        }
        prose = compile_method(_program(original)).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["type"] == "Compound"
        assert recovered.ast["combinator"] == "Conc"
        assert len(recovered.ast["components"]) == 2
        assert recovered.ast["components"][0]["value"] == 30.0
        assert recovered.ast["components"][1]["value"] == 60.0

    def test_multiple_fi_fi(self) -> None:
        original = {
            "type": "Compound",
            "combinator": "Mult",
            "components": [
                {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0, "time_unit": "s"},
                {"type": "Atomic", "dist": "F", "domain": "I", "value": 60.0, "time_unit": "s"},
            ],
        }
        prose = compile_method(_program(original)).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["combinator"] == "Mult"
        assert len(recovered.ast["components"]) == 2

    def test_chained_fr_fi(self) -> None:
        original = {
            "type": "Compound",
            "combinator": "Chain",
            "components": [
                {"type": "Atomic", "dist": "F", "domain": "R", "value": 10.0},
                {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0, "time_unit": "s"},
            ],
        }
        prose = compile_method(_program(original)).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["combinator"] == "Chain"
        assert len(recovered.ast["components"]) == 2


class TestRoundtripSpecial:
    """Special schedule roundtrip."""

    def test_extinction(self) -> None:
        prose = compile_method(_program({"type": "Special", "kind": "EXT"})).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["kind"] == "EXT"

    def test_crf(self) -> None:
        prose = compile_method(_program({"type": "Special", "kind": "CRF"})).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["kind"] == "CRF"


class TestRoundtripTrialBased:
    """Trial-based (MTS) schedule roundtrip."""

    def test_mts_minimal_jeab(self) -> None:
        """Minimal MTS: arbitrary, 3 comparisons, CRF, EXT, 5-s ITI."""
        original = {
            "type": "TrialBased",
            "trial_type": "MTS",
            "comparisons": 3,
            "consequence": {"type": "Special", "kind": "CRF"},
            "incorrect": {"type": "Special", "kind": "EXT"},
            "ITI": 5.0,
            "ITI_unit": "s",
            "mts_type": "arbitrary",
        }
        prose = compile_method(_program(original)).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["type"] == "TrialBased"
        assert recovered.ast["trial_type"] == "MTS"
        assert recovered.ast["comparisons"] == 3
        assert recovered.ast["consequence"] == {"type": "Special", "kind": "CRF"}
        assert recovered.ast["incorrect"] == {"type": "Special", "kind": "EXT"}
        assert recovered.ast["ITI"] == 5.0
        assert recovered.ast["ITI_unit"] == "s"
        assert recovered.ast["mts_type"] == "arbitrary"

    def test_mts_identity_jeab(self) -> None:
        """Identity MTS with 2 comparisons and FT timeout for incorrect."""
        original = {
            "type": "TrialBased",
            "trial_type": "MTS",
            "comparisons": 2,
            "consequence": {"type": "Special", "kind": "CRF"},
            "incorrect": {
                "type": "Atomic", "dist": "F", "domain": "T",
                "value": 10.0, "time_unit": "s",
            },
            "ITI": 10.0,
            "ITI_unit": "s",
            "mts_type": "identity",
        }
        prose = compile_method(_program(original)).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["mts_type"] == "identity"
        assert recovered.ast["comparisons"] == 2
        assert recovered.ast["incorrect"]["type"] == "Atomic"
        assert recovered.ast["incorrect"]["domain"] == "T"
        assert recovered.ast["incorrect"]["value"] == 10.0
        assert recovered.ast["ITI"] == 10.0

    def test_mts_consequence_ext_jeab(self) -> None:
        """MTS with EXT as consequence (probe trial)."""
        original = {
            "type": "TrialBased",
            "trial_type": "MTS",
            "comparisons": 3,
            "consequence": {"type": "Special", "kind": "EXT"},
            "incorrect": {"type": "Special", "kind": "EXT"},
            "ITI": 5.0,
            "ITI_unit": "s",
            "mts_type": "arbitrary",
        }
        prose = compile_method(_program(original)).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["consequence"] == {"type": "Special", "kind": "EXT"}
        assert recovered.ast["incorrect"] == {"type": "Special", "kind": "EXT"}

    def test_mts_consequence_vi_jeab(self) -> None:
        """MTS with intermittent reinforcement (VI 30-s) as consequence."""
        original = {
            "type": "TrialBased",
            "trial_type": "MTS",
            "comparisons": 3,
            "consequence": {
                "type": "Atomic", "dist": "V", "domain": "I",
                "value": 30.0, "time_unit": "s",
            },
            "incorrect": {"type": "Special", "kind": "EXT"},
            "ITI": 10.0,
            "ITI_unit": "s",
            "mts_type": "arbitrary",
        }
        prose = compile_method(_program(original)).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["consequence"]["type"] == "Atomic"
        assert recovered.ast["consequence"]["dist"] == "V"
        assert recovered.ast["consequence"]["domain"] == "I"
        assert recovered.ast["consequence"]["value"] == 30.0

    def test_mts_six_comparisons_jeab(self) -> None:
        """MTS with six comparisons (Fields et al., 1984 style)."""
        original = {
            "type": "TrialBased",
            "trial_type": "MTS",
            "comparisons": 6,
            "consequence": {"type": "Special", "kind": "CRF"},
            "incorrect": {"type": "Special", "kind": "EXT"},
            "ITI": 8.0,
            "ITI_unit": "s",
            "mts_type": "arbitrary",
        }
        prose = compile_method(_program(original)).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["comparisons"] == 6

    def test_mts_minimal_jaba(self) -> None:
        """MTS roundtrip with JABA (Japanese) style."""
        original = {
            "type": "TrialBased",
            "trial_type": "MTS",
            "comparisons": 3,
            "consequence": {"type": "Special", "kind": "CRF"},
            "incorrect": {"type": "Special", "kind": "EXT"},
            "ITI": 5.0,
            "ITI_unit": "s",
            "mts_type": "arbitrary",
        }
        prose = compile_method(_program(original), style="jaba").procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["type"] == "TrialBased"
        assert recovered.ast["comparisons"] == 3
        assert recovered.ast["consequence"] == {"type": "Special", "kind": "CRF"}
        assert recovered.ast["incorrect"] == {"type": "Special", "kind": "EXT"}
        assert recovered.ast["ITI"] == 5.0
        assert recovered.ast["mts_type"] == "arbitrary"

    def test_mts_identity_jaba(self) -> None:
        """Identity MTS with FT timeout, JABA style."""
        original = {
            "type": "TrialBased",
            "trial_type": "MTS",
            "comparisons": 2,
            "consequence": {"type": "Special", "kind": "CRF"},
            "incorrect": {
                "type": "Atomic", "dist": "F", "domain": "T",
                "value": 5.0, "time_unit": "s",
            },
            "ITI": 10.0,
            "ITI_unit": "s",
            "mts_type": "identity",
        }
        prose = compile_method(_program(original), style="jaba").procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["mts_type"] == "identity"
        assert recovered.ast["comparisons"] == 2
        assert recovered.ast["incorrect"]["type"] == "Atomic"
        assert recovered.ast["incorrect"]["value"] == 5.0


class TestRoundtripJABA:
    """Roundtrip with JABA (Japanese) style."""

    def test_vi_ja(self) -> None:
        original = {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"}
        prose = compile_method(_program(original), style="jaba").procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["dist"] == "V"
        assert recovered.ast["domain"] == "I"
        assert recovered.ast["value"] == 30.0

    def test_concurrent_ja(self) -> None:
        original = {
            "type": "Compound",
            "combinator": "Conc",
            "components": [
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"},
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            ],
        }
        prose = compile_method(_program(original), style="jaba").procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["type"] == "Compound"
        assert recovered.ast["combinator"] == "Conc"
