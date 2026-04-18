"""Complete roundtrip coverage tests (RT-T01 through RT-T14).

Each test: AST → paper prose → reader extraction → verify AST recovered.
"""

import pytest

from contingency_dsl_paper import compile_method
from contingency_dsl_reader import extract_schedule, extract_all


def _program(schedule: dict, **kw) -> dict:
    return {"type": "Program", "param_decls": kw.get("param_decls", []),
            "bindings": [], "schedule": schedule}


# === RT-T01: Full 3x3 atomic grid JEAB roundtrip ===

_GRID = [
    ("F", "R", 5.0, None),
    ("V", "R", 20.0, None),
    ("R", "R", 10.0, None),
    ("F", "I", 30.0, "s"),
    ("V", "I", 60.0, "s"),
    ("R", "I", 45.0, "s"),
    ("F", "T", 20.0, "s"),
    ("V", "T", 30.0, "s"),
    ("R", "T", 15.0, "s"),
]


@pytest.mark.parametrize("dist,domain,value,unit", _GRID)
def test_atomic_roundtrip_jeab(dist: str, domain: str, value: float, unit: str | None) -> None:
    node: dict = {"type": "Atomic", "dist": dist, "domain": domain, "value": value}
    if unit:
        node["time_unit"] = unit
    prose = compile_method(_program(node)).procedure
    recovered = extract_schedule(prose)
    assert recovered is not None, f"Failed to extract {dist}{domain} {value} from: {prose}"
    assert recovered.ast["dist"] == dist
    assert recovered.ast["domain"] == domain
    assert recovered.ast["value"] == value


# === RT-T02: Full 3x3 atomic grid JABA roundtrip ===

@pytest.mark.parametrize("dist,domain,value,unit", _GRID)
def test_atomic_roundtrip_jaba(dist: str, domain: str, value: float, unit: str | None) -> None:
    node: dict = {"type": "Atomic", "dist": dist, "domain": domain, "value": value}
    if unit:
        node["time_unit"] = unit
    prose = compile_method(_program(node), style="jaba").procedure
    recovered = extract_schedule(prose)
    assert recovered is not None, f"Failed to extract {dist}{domain} from JABA: {prose}"
    assert recovered.ast["dist"] == dist
    assert recovered.ast["value"] == value


# === RT-T03: All combinators JABA roundtrip ===

_COMBINATORS = ["Conc", "Chain", "Alt", "Conj", "Tand", "Mult", "Mix"]


@pytest.mark.parametrize("comb", _COMBINATORS)
def test_compound_roundtrip_jaba(comb: str) -> None:
    ast = _program({
        "type": "Compound", "combinator": comb,
        "components": [
            {"type": "Atomic", "dist": "F", "domain": "R", "value": 5.0},
            {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0, "time_unit": "s"},
        ],
    })
    prose = compile_method(ast, style="jaba").procedure
    recovered = extract_schedule(prose)
    assert recovered is not None, f"Failed to extract {comb} from JABA: {prose}"
    assert recovered.ast["combinator"] == comb


# === RT-T04: Special schedules JABA roundtrip ===

@pytest.mark.parametrize("kind", ["EXT", "CRF"])
def test_special_roundtrip_jaba(kind: str) -> None:
    prose = compile_method(_program({"type": "Special", "kind": kind}), style="jaba").procedure
    recovered = extract_schedule(prose)
    assert recovered is not None
    assert recovered.ast["kind"] == kind


# === RT-T05: LimitedHold roundtrip (leaf property) ===

class TestLimitedHoldRoundtrip:
    def test_fi_with_lh_jeab(self) -> None:
        ast = _program({
            "type": "Atomic",
            "dist": "F", "domain": "I", "value": 30.0, "time_unit": "s",
            "limitedHold": 5.0, "limitedHoldUnit": "s",
        })
        prose = compile_method(ast).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["type"] == "Atomic"
        assert recovered.ast["limitedHold"] == 5.0
        assert recovered.ast["dist"] == "F"
        assert recovered.ast["domain"] == "I"
        assert recovered.ast["value"] == 30.0

    def test_fi_with_lh_jaba(self) -> None:
        ast = _program({
            "type": "Atomic",
            "dist": "F", "domain": "I", "value": 30.0, "time_unit": "s",
            "limitedHold": 5.0, "limitedHoldUnit": "s",
        })
        prose = compile_method(ast, style="jaba").procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["type"] == "Atomic"
        assert recovered.ast["limitedHold"] == 5.0


# === RT-T06: SecondOrder roundtrip ===

class TestSecondOrderRoundtrip:
    def test_fr5_fi30_jeab(self) -> None:
        ast = _program({
            "type": "SecondOrder",
            "overall": {"type": "Atomic", "dist": "F", "domain": "R", "value": 5.0},
            "unit": {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0, "time_unit": "s"},
        })
        prose = compile_method(ast).procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["type"] == "SecondOrder"
        assert recovered.ast["overall"]["dist"] == "F"
        assert recovered.ast["overall"]["domain"] == "R"
        assert recovered.ast["overall"]["value"] == 5.0
        assert recovered.ast["unit"]["dist"] == "F"
        assert recovered.ast["unit"]["domain"] == "I"
        assert recovered.ast["unit"]["value"] == 30.0

    def test_second_order_jaba(self) -> None:
        ast = _program({
            "type": "SecondOrder",
            "overall": {"type": "Atomic", "dist": "F", "domain": "R", "value": 5.0},
            "unit": {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0, "time_unit": "s"},
        })
        prose = compile_method(ast, style="jaba").procedure
        recovered = extract_schedule(prose)
        assert recovered is not None
        assert recovered.ast["type"] == "SecondOrder"


# === RT-T07: session_end variants roundtrip ===

class TestSessionEndRoundtrip:
    def test_time_only(self) -> None:
        ast = _program(
            {"type": "Atomic", "dist": "F", "domain": "R", "value": 5.0},
            param_decls=[],
        )
        ast["program_annotations"] = [
            {"type": "Annotation", "keyword": "session_end",
             "params": {"rule": "time_only", "time": {"value": 60, "time_unit": "min"}}},
        ]
        method = compile_method(ast)
        report = extract_all(method.to_text())
        se = [a for a in report.annotations if a.ast.get("keyword") == "session_end"]
        assert len(se) >= 1
        assert se[0].ast["params"]["rule"] == "time_only"

    def test_reinforcers_only(self) -> None:
        ast = _program(
            {"type": "Atomic", "dist": "F", "domain": "R", "value": 5.0},
            param_decls=[],
        )
        ast["program_annotations"] = [
            {"type": "Annotation", "keyword": "session_end",
             "params": {"rule": "reinforcers_only", "reinforcers": 100}},
        ]
        method = compile_method(ast)
        report = extract_all(method.to_text())
        se = [a for a in report.annotations if a.ast.get("keyword") == "session_end"]
        assert len(se) >= 1
        assert se[0].ast["params"]["rule"] == "reinforcers_only"
        assert se[0].ast["params"]["reinforcers"] == 100


# === RT-T08: Inline compound params roundtrip ===

class TestInlineParamsRoundtrip:
    def test_conc_with_cod(self) -> None:
        ast = _program({
            "type": "Compound", "combinator": "Conc",
            "components": [
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"},
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            ],
            "params": {"COD": {"value": 2.0, "time_unit": "s"}},
        })
        method = compile_method(ast)
        report = extract_all(method.to_text())
        cods = [p for p in report.params if p.ast.get("name") == "COD"]
        assert len(cods) >= 1
        assert cods[0].ast["value"] == 2.0

    def test_mult_with_bo(self) -> None:
        ast = _program({
            "type": "Compound", "combinator": "Mult",
            "components": [
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"},
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            ],
            "params": {"BO": {"value": 5.0, "time_unit": "s"}},
        })
        method = compile_method(ast)
        report = extract_all(method.to_text())
        bos = [p for p in report.params if p.ast.get("name") == "BO"]
        assert len(bos) >= 1
        assert bos[0].ast["value"] == 5.0


# === RT-T09: Program-level param_decl roundtrip ===

class TestParamDeclRoundtrip:
    def test_lh_param_decl_jeab(self) -> None:
        ast = _program(
            {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0, "time_unit": "s"},
            param_decls=[{"type": "ParamDecl", "name": "LH", "value": 5.0, "time_unit": "s"}],
        )
        method = compile_method(ast)
        report = extract_all(method.to_text())
        lhs = [p for p in report.params if p.ast.get("name") == "LH"]
        assert len(lhs) >= 1
        assert lhs[0].ast["value"] == 5.0

    def test_lh_param_decl_jaba(self) -> None:
        ast = _program(
            {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0, "time_unit": "s"},
            param_decls=[{"type": "ParamDecl", "name": "LH", "value": 5.0, "time_unit": "s"}],
        )
        method = compile_method(ast, style="jaba")
        report = extract_all(method.to_text())
        lhs = [p for p in report.params if p.ast.get("name") == "LH"]
        assert len(lhs) >= 1
        assert lhs[0].ast["value"] == 5.0

    def test_bo_param_decl_jeab(self) -> None:
        ast = _program(
            {"type": "Atomic", "dist": "F", "domain": "R", "value": 10.0},
            param_decls=[{"type": "ParamDecl", "name": "BO", "value": 10.0, "time_unit": "s"}],
        )
        method = compile_method(ast)
        report = extract_all(method.to_text())
        bos = [p for p in report.params if p.ast.get("name") == "BO"]
        assert len(bos) >= 1
        assert bos[0].ast["value"] == 10.0

    def test_bo_param_decl_jaba(self) -> None:
        ast = _program(
            {"type": "Atomic", "dist": "F", "domain": "R", "value": 10.0},
            param_decls=[{"type": "ParamDecl", "name": "BO", "value": 10.0, "time_unit": "s"}],
        )
        method = compile_method(ast, style="jaba")
        report = extract_all(method.to_text())
        bos = [p for p in report.params if p.ast.get("name") == "BO"]
        assert len(bos) >= 1
        assert bos[0].ast["value"] == 10.0

    def test_frco_param_decl_jeab(self) -> None:
        ast = _program(
            {"type": "Compound", "combinator": "Conc", "components": [
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"},
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            ]},
            param_decls=[{"type": "ParamDecl", "name": "FRCO", "value": 3.0}],
        )
        method = compile_method(ast)
        report = extract_all(method.to_text())
        frcos = [p for p in report.params if p.ast.get("name") == "FRCO"]
        assert len(frcos) >= 1
        assert frcos[0].ast["value"] == 3.0

    def test_frco_param_decl_jaba(self) -> None:
        ast = _program(
            {"type": "Compound", "combinator": "Conc", "components": [
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"},
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            ]},
            param_decls=[{"type": "ParamDecl", "name": "FRCO", "value": 3.0}],
        )
        method = compile_method(ast, style="jaba")
        report = extract_all(method.to_text())
        frcos = [p for p in report.params if p.ast.get("name") == "FRCO"]
        assert len(frcos) >= 1
        assert frcos[0].ast["value"] == 3.0


# === RT-T10: @history(experienced) roundtrip ===

class TestHistoryExperiencedRoundtrip:
    def test_history_experienced_jeab(self) -> None:
        ast = _program(
            {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"},
        )
        ast["program_annotations"] = [
            {"type": "Annotation", "keyword": "species", "positional": "rat"},
            {"type": "Annotation", "keyword": "n", "positional": 6},
            {"type": "Annotation", "keyword": "history", "positional": "FR 5 and VI 30-s schedules"},
        ]
        method = compile_method(ast)
        report = extract_all(method.to_text())
        hist = [a for a in report.annotations if a.ast.get("keyword") == "history"]
        assert len(hist) >= 1
        assert "FR 5" in hist[0].ast["positional"]

    def test_history_experienced_jaba(self) -> None:
        ast = _program(
            {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"},
        )
        ast["program_annotations"] = [
            {"type": "Annotation", "keyword": "species", "positional": "rat"},
            {"type": "Annotation", "keyword": "n", "positional": 6},
            {"type": "Annotation", "keyword": "history", "positional": "FR 5 スケジュール"},
        ]
        method = compile_method(ast, style="jaba")
        report = extract_all(method.to_text())
        hist = [a for a in report.annotations if a.ast.get("keyword") == "history"]
        assert len(hist) >= 1
        assert "FR 5" in hist[0].ast["positional"]


# === RT-T11: DRH/DRO JABA roundtrip ===

class TestDRJABARoundtrip:
    def test_drh_jaba(self) -> None:
        ast = _program({"type": "Modifier", "modifier": "DRH", "value": 10.0})
        prose = compile_method(ast, style="jaba").procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["modifier"] == "DRH"

    def test_dro_jaba(self) -> None:
        ast = _program({"type": "Modifier", "modifier": "DRO", "value": 20.0, "time_unit": "s"})
        prose = compile_method(ast, style="jaba").procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["modifier"] == "DRO"


# === RT-T12: Overlay roundtrip ===

class TestOverlayRoundtrip:
    def test_overlay_jeab(self) -> None:
        ast = _program({
            "type": "Compound", "combinator": "Overlay",
            "components": [
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
                {"type": "Special", "kind": "CRF"},
            ],
        })
        method = compile_method(ast)
        report = extract_all(method.to_text())
        sched = report.primary_schedule
        assert sched is not None
        assert sched.ast["type"] == "Compound"
        assert sched.ast["combinator"] == "Overlay"
        assert len(sched.ast["components"]) == 2

    def test_overlay_jaba(self) -> None:
        ast = _program({
            "type": "Compound", "combinator": "Overlay",
            "components": [
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
                {"type": "Special", "kind": "CRF"},
            ],
        })
        method = compile_method(ast, style="jaba")
        report = extract_all(method.to_text())
        sched = report.primary_schedule
        assert sched is not None
        assert sched.ast["type"] == "Compound"
        assert sched.ast["combinator"] == "Overlay"


# === RT-T13: FRCO inline compound param roundtrip ===

class TestFRCOInlineRoundtrip:
    def test_frco_inline_jeab(self) -> None:
        ast = _program({
            "type": "Compound", "combinator": "Conc",
            "components": [
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"},
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            ],
            "params": {"FRCO": {"value": 3}},
        })
        method = compile_method(ast)
        report = extract_all(method.to_text())
        frcos = [p for p in report.params if p.ast.get("name") == "FRCO"]
        assert len(frcos) >= 1
        assert frcos[0].ast["value"] == 3.0

    def test_frco_inline_jaba(self) -> None:
        ast = _program({
            "type": "Compound", "combinator": "Conc",
            "components": [
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"},
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            ],
            "params": {"FRCO": {"value": 3}},
        })
        method = compile_method(ast, style="jaba")
        report = extract_all(method.to_text())
        frcos = [p for p in report.params if p.ast.get("name") == "FRCO"]
        assert len(frcos) >= 1
        assert frcos[0].ast["value"] == 3.0


# === RT-T14: RD param_decl roundtrip ===

class TestRDRoundtrip:
    def test_rd_jeab(self) -> None:
        ast = _program(
            {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            param_decls=[{"type": "ParamDecl", "name": "RD", "value": 500.0, "time_unit": "ms"}],
        )
        method = compile_method(ast)
        report = extract_all(method.to_text())
        rds = [p for p in report.params if p.ast.get("name") == "RD"]
        assert len(rds) >= 1
        assert rds[0].ast["value"] == 500.0
        assert rds[0].ast["time_unit"] == "ms"

    def test_rd_jaba(self) -> None:
        ast = _program(
            {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            param_decls=[{"type": "ParamDecl", "name": "RD", "value": 500.0, "time_unit": "ms"}],
        )
        method = compile_method(ast, style="jaba")
        report = extract_all(method.to_text())
        rds = [p for p in report.params if p.ast.get("name") == "RD"]
        assert len(rds) >= 1
        assert rds[0].ast["value"] == 500.0
