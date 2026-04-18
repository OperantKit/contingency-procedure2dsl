"""Tests for schedule extraction from JEAB/JABA text."""

from contingency_dsl_reader import extract_schedule, extract_all


class TestAtomicExtraction:
    """Extract atomic schedules from text."""

    def test_vi_abbreviated(self) -> None:
        result = extract_schedule("a VI 30-s schedule")
        assert result is not None
        assert result.ast["type"] == "Atomic"
        assert result.ast["dist"] == "V"
        assert result.ast["domain"] == "I"
        assert result.ast["value"] == 30.0

    def test_fr_abbreviated(self) -> None:
        result = extract_schedule("an FR 5 schedule")
        assert result is not None
        assert result.ast["dist"] == "F"
        assert result.ast["domain"] == "R"
        assert result.ast["value"] == 5.0

    def test_full_name(self) -> None:
        result = extract_schedule("a variable-interval 30-s schedule")
        assert result is not None
        assert result.ast["dist"] == "V"
        assert result.ast["domain"] == "I"
        assert result.ast["value"] == 30.0

    def test_ratio_schedules_do_not_get_time_unit(self) -> None:
        """Regression: the `s` in `schedule` must not be captured as a time unit
        for ratio schedules. Ratios (FR/VR/RR) are count-based and must never
        carry `time_unit`. See e2e_paper_roundtrip DIFF case on
        10.1901/jeab.1982.38-233 (Catania, Matthews & Shimoff 1982).

        Matrix: FR/VR/RR × abbreviation/full-name × with/without paren-alias ×
        EN/JP × trailing word that starts with the time-unit letter.
        """
        for prose in (
            # Full-name, paren alias, trailing "schedule" (the original DIFF case)
            "Responses were reinforced under a random-ratio (RR) 20 schedule.",
            "a fixed-ratio (FR) 5 schedule",
            "a variable-ratio (VR) 10 schedule",
            # Full-name, no paren alias
            "a fixed-ratio 5 schedule",
            "a variable-ratio 10 schedule",
            "a random-ratio 20 schedule",
            # Abbreviation form
            "FR 5 schedule",
            "VR 20 schedule",
            "RR 30 schedule",
            "fr 5 schedule",  # lowercase (re.IGNORECASE)
            # Trailing words starting with 's' / 'm' (second, minute, millisecond)
            # — these must not leak into the time-unit capture.
            "VR 20 seconds was the mean ratio requirement",
            "FR 10 minutes apart had elapsed",
            "RR 40 milliseconds later",
            # Japanese full-name variants
            "固定比率 5 スケジュール",
            "変動比率 10 スケジュール",
        ):
            result = extract_schedule(prose)
            assert result is not None, f"extractor dropped: {prose!r}"
            assert result.ast["domain"] == "R", prose
            assert "time_unit" not in result.ast, (
                f"ratio gained spurious time_unit from {prose!r}: {result.ast!r}"
            )

    def test_interval_retains_time_unit(self) -> None:
        """Sanity check: the fix must not strip legitimate time units
        from interval / time schedules."""
        for prose, expected_unit in (
            ("a VI 30-s schedule", "s"),
            ("a fixed-interval 60-s schedule", "s"),
            ("a VT 120-s schedule", "s"),
        ):
            result = extract_schedule(prose)
            assert result is not None, prose
            assert result.ast.get("time_unit") == expected_unit, (
                f"interval/time lost time_unit from {prose!r}: {result.ast!r}"
            )


class TestCompoundExtraction:
    """Extract compound schedules."""

    def test_concurrent_vi_vi(self) -> None:
        text = "Responses were reinforced under a concurrent VI 30-s VI 60-s schedule."
        result = extract_schedule(text)
        assert result is not None
        assert result.ast["type"] == "Compound"
        assert result.ast["combinator"] == "Conc"
        assert len(result.ast["components"]) == 2
        assert result.ast["components"][0]["value"] == 30.0
        assert result.ast["components"][1]["value"] == 60.0

    def test_multiple_fi_fi(self) -> None:
        text = "a multiple FI 30-s FI 60-s schedule"
        result = extract_schedule(text)
        assert result is not None
        assert result.ast["combinator"] == "Mult"


class TestSpecialExtraction:
    """Extract special schedules."""

    def test_extinction(self) -> None:
        result = extract_schedule("Responses had no programmed consequences (extinction).")
        assert result is not None
        assert result.ast["kind"] == "EXT"

    def test_crf(self) -> None:
        result = extract_schedule("continuous reinforcement was in effect")
        assert result is not None
        assert result.ast["kind"] == "CRF"


class TestParamExtraction:
    """Extract schedule parameters."""

    def test_cod(self) -> None:
        report = extract_all("A 2-s changeover delay was in effect.")
        assert len(report.params) == 1
        assert report.params[0].ast["name"] == "COD"
        assert report.params[0].ast["value"] == 2.0

    def test_limited_hold(self) -> None:
        report = extract_all("with a 5-s limited hold")
        assert len(report.params) == 1
        assert report.params[0].ast["name"] == "LH"
        assert report.params[0].ast["value"] == 5.0


class TestAnnotationExtraction:
    """Extract subject annotations."""

    def test_six_rats(self) -> None:
        report = extract_all("Six Sprague-Dawley rats served as subjects.")
        species = [a for a in report.annotations if a.ast.get("keyword") == "species"]
        n_anns = [a for a in report.annotations if a.ast.get("keyword") == "n"]
        assert len(species) == 1
        assert species[0].ast["positional"] == "rat"
        assert len(n_anns) == 1
        assert n_anns[0].ast["positional"] == 6


class TestToProgramAssembly:
    """ExtractionReport.to_program() assembly."""

    def test_assembles_program(self) -> None:
        text = (
            "Six rats served as subjects. "
            "Responses were reinforced under a concurrent VI 30-s VI 60-s schedule. "
            "A 2-s changeover delay was in effect."
        )
        report = extract_all(text)
        program = report.to_program()
        assert program["type"] == "Program"
        assert program["schedule"]["type"] == "Compound"
        assert program["schedule"]["combinator"] == "Conc"
