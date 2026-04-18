"""Phase 2: Roundtrip tests with annotations.

Tests: annotated AST → paper prose → reader extraction → verify annotations recovered.
"""

from contingency_dsl2procedure import compile_method
from contingency_procedure2dsl import extract_all


def _full_program() -> dict:
    return {
        "type": "Program",
        "program_annotations": [
            {"type": "Annotation", "keyword": "species", "positional": "rat"},
            {"type": "Annotation", "keyword": "strain", "positional": "Sprague-Dawley"},
            {"type": "Annotation", "keyword": "n", "positional": 6},
            {"type": "Annotation", "keyword": "deprivation", "params": {"hours": 23, "target": "food"}},
            {"type": "Annotation", "keyword": "history", "positional": "naive"},
            {"type": "Annotation", "keyword": "chamber", "positional": "med-associates", "params": {"model": "ENV-007"}},
            {"type": "Annotation", "keyword": "hardware", "positional": "MED-PC IV"},
            {"type": "Annotation", "keyword": "reinforcer", "positional": "food pellet"},
            {"type": "Annotation", "keyword": "session_end", "params": {"rule": "first", "time": {"value": 60, "time_unit": "min"}, "reinforcers": 60}},
            {"type": "Annotation", "keyword": "steady_state", "params": {"window_sessions": 5, "max_change_pct": 10, "measure": "rate"}},
        ],
        "param_decls": [{"type": "ParamDecl", "name": "COD", "value": 2.0, "time_unit": "s"}],
        "bindings": [],
        "schedule": {
            "type": "Compound",
            "combinator": "Conc",
            "components": [
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"},
                {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
            ],
        },
    }


class TestAnnotationRoundtripJEAB:
    """JEAB: AST → paper → reader → verify."""

    def _compile_and_extract(self):
        method = compile_method(_full_program())
        full_text = method.to_text()
        return extract_all(full_text)

    def test_species_recovered(self) -> None:
        report = self._compile_and_extract()
        species = [a for a in report.annotations if a.ast.get("keyword") == "species"]
        assert any(a.ast["positional"] == "rat" for a in species)

    def test_n_recovered(self) -> None:
        report = self._compile_and_extract()
        n_anns = [a for a in report.annotations if a.ast.get("keyword") == "n"]
        assert any(a.ast["positional"] == 6 for a in n_anns)

    def test_strain_recovered(self) -> None:
        report = self._compile_and_extract()
        strains = [a for a in report.annotations if a.ast.get("keyword") == "strain"]
        assert any(a.ast["positional"] == "Sprague-Dawley" for a in strains)

    def test_deprivation_recovered(self) -> None:
        report = self._compile_and_extract()
        deps = [a for a in report.annotations if a.ast.get("keyword") == "deprivation"]
        assert any(a.ast["params"]["hours"] == 23 for a in deps)

    def test_history_recovered(self) -> None:
        report = self._compile_and_extract()
        hist = [a for a in report.annotations if a.ast.get("keyword") == "history"]
        assert any(a.ast["positional"] == "naive" for a in hist)

    def test_session_end_recovered(self) -> None:
        report = self._compile_and_extract()
        se = [a for a in report.annotations if a.ast.get("keyword") == "session_end"]
        assert len(se) >= 1
        params = se[0].ast["params"]
        assert params["rule"] == "first"
        assert params["reinforcers"] == 60

    def test_steady_state_recovered(self) -> None:
        report = self._compile_and_extract()
        ss = [a for a in report.annotations if a.ast.get("keyword") == "steady_state"]
        assert len(ss) >= 1
        assert ss[0].ast["params"]["window_sessions"] == 5
        assert ss[0].ast["params"]["max_change_pct"] == 10

    def test_schedule_recovered(self) -> None:
        report = self._compile_and_extract()
        sched = report.primary_schedule
        assert sched is not None
        assert sched.ast["type"] == "Compound"
        assert sched.ast["combinator"] == "Conc"

    def test_cod_recovered(self) -> None:
        report = self._compile_and_extract()
        cods = [p for p in report.params if p.ast.get("name") == "COD"]
        assert len(cods) >= 1
        assert cods[0].ast["value"] == 2.0

    def test_reinforcer_recovered(self) -> None:
        report = self._compile_and_extract()
        refs = [a for a in report.annotations if a.ast.get("keyword") == "reinforcer"]
        assert any("food pellet" in a.ast.get("positional", "") for a in refs)

    def test_to_program_assembles(self) -> None:
        report = self._compile_and_extract()
        program = report.to_program()
        assert program["type"] == "Program"
        assert program["schedule"]["combinator"] == "Conc"
        assert len(program["program_annotations"]) > 0
        assert len(program["param_decls"]) > 0


class TestAnnotationRoundtripJABA:
    """JABA: AST → paper (Japanese) → reader → verify."""

    def _compile_and_extract(self):
        method = compile_method(_full_program(), style="jaba")
        full_text = method.to_text()
        return extract_all(full_text)

    def test_schedule_recovered_ja(self) -> None:
        report = self._compile_and_extract()
        sched = report.primary_schedule
        assert sched is not None
        assert sched.ast["combinator"] == "Conc"

    def test_session_end_recovered_ja(self) -> None:
        report = self._compile_and_extract()
        se = [a for a in report.annotations if a.ast.get("keyword") == "session_end"]
        assert len(se) >= 1
        assert se[0].ast["params"]["reinforcers"] == 60
