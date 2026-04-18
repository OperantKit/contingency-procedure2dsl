"""Extended tests for reader extraction coverage."""

import pytest

from contingency_procedure2dsl import extract_schedule, extract_all
from contingency_procedure2dsl.extractors.schedule import extract_atomic_schedules


# --- Full name extraction (English) ---

_FULL_NAMES_EN = [
    ("fixed-ratio 5", "F", "R", 5.0),
    ("variable-ratio 20", "V", "R", 20.0),
    ("fixed-interval 30-s", "F", "I", 30.0),
    ("variable-interval 60-s", "V", "I", 60.0),
    ("fixed-time 20-s", "F", "T", 20.0),
    ("variable-time 30-s", "V", "T", 30.0),
]


@pytest.mark.parametrize("text,dist,domain,value", _FULL_NAMES_EN)
def test_full_name_extraction(text: str, dist: str, domain: str, value: float) -> None:
    results = extract_atomic_schedules(f"a {text} schedule")
    assert len(results) >= 1
    r = results[0]
    assert r.ast["dist"] == dist
    assert r.ast["domain"] == domain
    assert r.ast["value"] == value


# --- Abbreviated extraction ---

_ABBREVS = [
    ("FR 5", "F", "R", 5.0),
    ("VR 20", "V", "R", 20.0),
    ("FI 30-s", "F", "I", 30.0),
    ("VI 60-s", "V", "I", 60.0),
    ("FT 20-s", "F", "T", 20.0),
    ("VT 30-s", "V", "T", 30.0),
    ("RI 45-s", "R", "I", 45.0),
    ("RR 10", "R", "R", 10.0),
    ("RT 15-s", "R", "T", 15.0),
]


@pytest.mark.parametrize("text,dist,domain,value", _ABBREVS)
def test_abbrev_extraction(text: str, dist: str, domain: str, value: float) -> None:
    results = extract_atomic_schedules(f"a {text} schedule")
    assert len(results) >= 1
    r = results[0]
    assert r.ast["dist"] == dist
    assert r.ast["domain"] == domain
    assert r.ast["value"] == value


# --- All combinators ---

_COMBINATORS_EN = [
    ("concurrent", "Conc"),
    ("chained", "Chain"),
    ("alternative", "Alt"),
    ("conjunctive", "Conj"),
    ("tandem", "Tand"),
    ("multiple", "Mult"),
    ("mixed", "Mix"),
]


@pytest.mark.parametrize("name,code", _COMBINATORS_EN)
def test_combinator_extraction(name: str, code: str) -> None:
    text = f"a {name} FR 5 FI 30-s schedule."
    result = extract_schedule(text)
    assert result is not None
    assert result.ast["type"] == "Compound"
    assert result.ast["combinator"] == code


# --- Japanese combinators ---

_COMBINATORS_JA = [
    ("並立", "Conc"),
    ("連鎖", "Chain"),
    ("多元", "Mult"),
    ("混合", "Mix"),
]


@pytest.mark.parametrize("name,code", _COMBINATORS_JA)
def test_combinator_extraction_ja(name: str, code: str) -> None:
    text = f"{name} VI 30-s VI 60-s スケジュール。"
    result = extract_schedule(text)
    assert result is not None
    assert result.ast["combinator"] == code


# --- Parameter extraction ---

class TestParamExtractionExtended:
    def test_cod_ja(self) -> None:
        report = extract_all("2-s の切替遅延が設定された。")
        cod = [p for p in report.params if p.ast.get("name") == "COD"]
        assert len(cod) == 1
        assert cod[0].ast["value"] == 2.0

    def test_blackout(self) -> None:
        report = extract_all("A 5-s blackout separated components.")
        bo = [p for p in report.params if p.ast.get("name") == "BO"]
        assert len(bo) == 1
        assert bo[0].ast["value"] == 5.0


# --- Annotation extraction ---

class TestAnnotationExtractionExtended:
    def test_three_pigeons(self) -> None:
        report = extract_all("Three pigeons served as subjects.")
        species = [a for a in report.annotations if a.ast.get("keyword") == "species"]
        n_anns = [a for a in report.annotations if a.ast.get("keyword") == "n"]
        assert len(species) == 1
        assert species[0].ast["positional"] == "pigeon"
        assert len(n_anns) == 1
        assert n_anns[0].ast["positional"] == 3

    def test_japanese_subjects(self) -> None:
        report = extract_all("6匹のSprague-Dawley系ラットを被験体とした。")
        species = [a for a in report.annotations if a.ast.get("keyword") == "species"]
        strain = [a for a in report.annotations if a.ast.get("keyword") == "strain"]
        n_anns = [a for a in report.annotations if a.ast.get("keyword") == "n"]
        assert len(species) == 1
        assert species[0].ast["positional"] == "rat"
        assert len(strain) == 1
        assert strain[0].ast["positional"] == "Sprague-Dawley"
        assert len(n_anns) == 1
        assert n_anns[0].ast["positional"] == 6


# --- Confidence scores ---

class TestConfidence:
    def test_abbrev_higher_than_full(self) -> None:
        """Abbreviated form should have higher confidence than full name."""
        abbrev_results = extract_atomic_schedules("VI 30-s schedule")
        assert all(r.confidence >= 0.90 for r in abbrev_results)

    def test_compound_lower_than_atomic(self) -> None:
        """Compound extraction involves more inference."""
        result = extract_schedule("concurrent VI 30-s VI 60-s schedule.")
        assert result is not None
        assert result.confidence <= 0.90  # compound has more uncertainty
