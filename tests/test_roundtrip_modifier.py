"""Phase 3: Modifier + Aversive roundtrip tests."""

from contingency_dsl2procedure import compile_method
from contingency_procedure2dsl import extract_schedule


def _program(schedule: dict) -> dict:
    return {"type": "Program", "param_decls": [], "bindings": [], "schedule": schedule}


class TestDRRoundtrip:
    def test_drl_jeab(self) -> None:
        ast = _program({"type": "Modifier", "modifier": "DRL", "value": 5.0, "time_unit": "s"})
        prose = compile_method(ast).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["modifier"] == "DRL"
        assert r.ast["value"] == 5.0

    def test_drh_jeab(self) -> None:
        ast = _program({"type": "Modifier", "modifier": "DRH", "value": 10.0})
        prose = compile_method(ast).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["modifier"] == "DRH"
        assert r.ast["value"] == 10.0

    def test_dro_jeab(self) -> None:
        ast = _program({"type": "Modifier", "modifier": "DRO", "value": 20.0, "time_unit": "s"})
        prose = compile_method(ast).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["modifier"] == "DRO"

    def test_drl_jaba(self) -> None:
        ast = _program({"type": "Modifier", "modifier": "DRL", "value": 5.0, "time_unit": "s"})
        prose = compile_method(ast, style="jaba").procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["modifier"] == "DRL"


class TestPRRoundtrip:
    def test_pr_linear_jeab(self) -> None:
        ast = _program({"type": "Modifier", "modifier": "PR", "pr_step": "linear",
                         "pr_start": 1.0, "pr_increment": 5.0})
        prose = compile_method(ast).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["modifier"] == "PR"
        assert r.ast["pr_step"] == "linear"

    def test_pr_jaba(self) -> None:
        ast = _program({"type": "Modifier", "modifier": "PR", "pr_step": "linear"})
        prose = compile_method(ast, style="jaba").procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["modifier"] == "PR"


class TestLagRoundtrip:
    def test_lag5_jeab(self) -> None:
        ast = _program({"type": "Modifier", "modifier": "Lag", "length": 5})
        prose = compile_method(ast).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["modifier"] == "Lag"
        assert r.ast["length"] == 5

    def test_lag_jaba(self) -> None:
        ast = _program({"type": "Modifier", "modifier": "Lag", "length": 3})
        prose = compile_method(ast, style="jaba").procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["length"] == 3


class TestSidmanRoundtrip:
    def test_sidman_jeab(self) -> None:
        ast = _program({
            "type": "AversiveSchedule", "kind": "Sidman",
            "params": {"SSI": {"value": 5.0, "time_unit": "s"},
                       "RSI": {"value": 20.0, "time_unit": "s"}},
        })
        prose = compile_method(ast).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["kind"] == "Sidman"
        assert r.ast["params"]["SSI"]["value"] == 5.0
        assert r.ast["params"]["RSI"]["value"] == 20.0

    def test_sidman_jaba(self) -> None:
        ast = _program({
            "type": "AversiveSchedule", "kind": "Sidman",
            "params": {"SSI": {"value": 5.0, "time_unit": "s"},
                       "RSI": {"value": 20.0, "time_unit": "s"}},
        })
        prose = compile_method(ast, style="jaba").procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["kind"] == "Sidman"


class TestDiscrimAvRoundtrip:
    def test_discrim_av_jeab(self) -> None:
        ast = _program({
            "type": "AversiveSchedule", "kind": "DiscrimAv",
            "params": {"CSUSInterval": {"value": 10.0, "time_unit": "s"},
                       "ITI": {"value": 30.0, "time_unit": "s"},
                       "mode": "fixed"},
        })
        prose = compile_method(ast).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["kind"] == "DiscrimAv"
        assert r.ast["params"]["CSUSInterval"]["value"] == 10.0
        assert r.ast["params"]["mode"] == "fixed"

    def test_discrim_av_jaba(self) -> None:
        ast = _program({
            "type": "AversiveSchedule", "kind": "DiscrimAv",
            "params": {"CSUSInterval": {"value": 10.0, "time_unit": "s"},
                       "ITI": {"value": 30.0, "time_unit": "s"},
                       "mode": "escape"},
        })
        prose = compile_method(ast, style="jaba").procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["params"]["mode"] == "escape"
