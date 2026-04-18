"""Tests for multi-experiment paper segmentation.

Spec reference: ``contingency-dsl/schema/experiment/experiment.schema.json``
defines ``Experiment`` (``label`` + ``body: Program | PhaseSequence``) and
``Paper`` (``experiments: Experiment[]``). This module tests the reader
side: detect ``Experiment N`` / ``EXPERIMENT N`` / ``Study N`` / ``実験N``
headings, split the document, and emit one Experiment per segment.
"""

from __future__ import annotations

from contingency_procedure2dsl.extractors.experiment import (
    detect_experiment_boundaries,
    extract_experiments,
)
from contingency_procedure2dsl.pipeline import extract_paper


class TestDetectBoundaries:
    """``detect_experiment_boundaries`` returns ``(label, body)`` pairs."""

    def test_no_headings_returns_empty(self) -> None:
        text = (
            "Eight rats were trained under a VI 60-s schedule of food "
            "reinforcement. Sessions lasted 30 minutes."
        )
        assert detect_experiment_boundaries(text) == []

    def test_two_en_experiments(self) -> None:
        text = (
            "General Method. Eight rats served as subjects.\n\n"
            "Experiment 1\n"
            "Responses were reinforced under a VI 30-s schedule.\n\n"
            "Experiment 2\n"
            "Responses were reinforced under a VI 60-s schedule.\n"
        )
        pairs = detect_experiment_boundaries(text)
        labels = [lbl for lbl, _ in pairs]
        assert labels == ["Experiment 1", "Experiment 2"]
        assert "VI 30" in pairs[0][1]
        assert "VI 60" in pairs[1][1]

    def test_all_caps_headings(self) -> None:
        text = (
            "EXPERIMENT 1\n"
            "Subjects were pigeons on FR 10.\n\n"
            "EXPERIMENT 2\n"
            "Subjects were pigeons on FR 20.\n"
        )
        pairs = detect_experiment_boundaries(text)
        assert [lbl for lbl, _ in pairs] == ["EXPERIMENT 1", "EXPERIMENT 2"]

    def test_markdown_heading_prefix(self) -> None:
        text = (
            "## Experiment 1\n"
            "A VI 30-s baseline was used.\n\n"
            "## Experiment 2\n"
            "A VI 120-s schedule replaced the baseline.\n"
        )
        pairs = detect_experiment_boundaries(text)
        assert [lbl for lbl, _ in pairs] == ["Experiment 1", "Experiment 2"]

    def test_alphanumeric_experiment_label(self) -> None:
        text = (
            "Experiment 2a\n"
            "First manipulation.\n\n"
            "Experiment 2b\n"
            "Second manipulation.\n"
        )
        pairs = detect_experiment_boundaries(text)
        assert [lbl for lbl, _ in pairs] == ["Experiment 2a", "Experiment 2b"]

    def test_study_variant(self) -> None:
        text = (
            "Study 1\n"
            "Key-peck training on VI 30-s.\n\n"
            "Study 2\n"
            "Key-peck training on VI 60-s.\n"
        )
        pairs = detect_experiment_boundaries(text)
        assert [lbl for lbl, _ in pairs] == ["Study 1", "Study 2"]

    def test_japanese_experiment_headings(self) -> None:
        text = (
            "実験1\n"
            "ハトを VI 30 秒スケジュールで訓練した。\n\n"
            "実験2\n"
            "ハトを VI 60 秒スケジュールで訓練した。\n"
        )
        pairs = detect_experiment_boundaries(text)
        assert [lbl for lbl, _ in pairs] == ["実験1", "実験2"]

    def test_single_heading_returns_single_pair(self) -> None:
        """A single 'Experiment 1' heading is still a boundary pair.

        Whether the caller treats one-experiment papers as Paper or Program
        is policy belonging to ``extract_paper``; detection is mechanical.
        """
        text = (
            "Experiment 1\n"
            "Responses were reinforced under VI 60-s.\n"
        )
        pairs = detect_experiment_boundaries(text)
        assert len(pairs) == 1
        assert pairs[0][0] == "Experiment 1"

    def test_inline_mentions_are_not_boundaries(self) -> None:
        """'in Experiment 1' in running text is not a heading."""
        text = (
            "As shown in Experiment 1, responses increased under the VI "
            "schedule. In Experiment 2 the pattern reversed."
        )
        pairs = detect_experiment_boundaries(text)
        assert pairs == []

    def test_subtitle_after_colon(self) -> None:
        """JEAB convention: 'Experiment 1: Autoshaping' is a heading.

        Subtitles are treated as heading decoration and discarded; the
        canonical label remains 'Experiment 1'. The body starts on the
        line after the heading.
        """
        text = (
            "Experiment 1: Autoshaping\n"
            "Pigeons were exposed to key-light / food pairings.\n\n"
            "Experiment 2: Omission\n"
            "Responses cancelled the upcoming food delivery.\n"
        )
        pairs = detect_experiment_boundaries(text)
        assert [lbl for lbl, _ in pairs] == ["Experiment 1", "Experiment 2"]
        assert "key-light" in pairs[0][1]
        assert "food delivery" in pairs[1][1]

    def test_sentence_continuation_is_not_a_heading(self) -> None:
        """'Experiment 1 was successful.' is prose, not a heading."""
        text = (
            "Experiment 1 was successful and produced stable responding. "
            "Experiment 2 replicated the effect."
        )
        pairs = detect_experiment_boundaries(text)
        assert pairs == []

    def test_nbsp_between_word_and_number(self) -> None:
        """PDF extractors often emit U+00A0 between the word and the number."""
        text = (
            "Experiment\u00A01\n"
            "Responses on VI 30-s.\n\n"
            "Experiment\u00A02\n"
            "Responses on VI 60-s.\n"
        )
        pairs = detect_experiment_boundaries(text)
        assert len(pairs) == 2
        # Normalized label folds NBSP to ASCII space.
        assert pairs[0][0] == "Experiment 1"
        assert pairs[1][0] == "Experiment 2"

    def test_crlf_line_endings(self) -> None:
        """Windows / Word-exported text uses CRLF — must still match."""
        text = (
            "Experiment 1\r\n"
            "Responses on VI 30-s.\r\n\r\n"
            "Experiment 2\r\n"
            "Responses on VI 60-s.\r\n"
        )
        pairs = detect_experiment_boundaries(text)
        assert [lbl for lbl, _ in pairs] == ["Experiment 1", "Experiment 2"]

    def test_heading_at_end_of_file_without_newline(self) -> None:
        """Final heading with no trailing newline must still match."""
        text = (
            "Experiment 1\nFR 10 training.\n\nExperiment 2\nFR 20 training."
        )
        pairs = detect_experiment_boundaries(text)
        assert [lbl for lbl, _ in pairs] == ["Experiment 1", "Experiment 2"]


class TestExtractExperiments:
    """``extract_experiments`` returns one ExtractResult per experiment."""

    def test_no_boundaries_returns_empty_list(self) -> None:
        text = "Eight rats were trained under a VI 60-s schedule."
        assert extract_experiments(text) == []

    def test_two_experiments_produce_two_results(self) -> None:
        text = (
            "Experiment 1\n"
            "Responses were reinforced under a VI 30-s schedule.\n\n"
            "Experiment 2\n"
            "Responses were reinforced under a VI 60-s schedule.\n"
        )
        results = extract_experiments(text)
        assert len(results) == 2

    def test_each_result_is_experiment_ast(self) -> None:
        text = (
            "Experiment 1\n"
            "Responses were reinforced under a VI 30-s schedule.\n\n"
            "Experiment 2\n"
            "Responses were reinforced under a VI 60-s schedule.\n"
        )
        results = extract_experiments(text)
        for r in results:
            assert r.ast["type"] == "Experiment"
            assert "label" in r.ast
            assert "body" in r.ast

    def test_labels_preserved_verbatim(self) -> None:
        text = (
            "EXPERIMENT 1\n"
            "Pigeons on FR 10.\n\n"
            "EXPERIMENT 2\n"
            "Pigeons on FR 20.\n"
        )
        results = extract_experiments(text)
        assert [r.ast["label"] for r in results] == ["EXPERIMENT 1", "EXPERIMENT 2"]

    def test_body_is_program_when_single_schedule(self) -> None:
        text = (
            "Experiment 1\n"
            "Responses were reinforced under a VI 30-s schedule.\n\n"
            "Experiment 2\n"
            "Responses were reinforced under a VI 60-s schedule.\n"
        )
        results = extract_experiments(text)
        assert results[0].ast["body"]["type"] == "Program"
        assert results[1].ast["body"]["type"] == "Program"

    def test_per_experiment_schedules_differ(self) -> None:
        text = (
            "Experiment 1\n"
            "Responses were reinforced under a VI 30-s schedule.\n\n"
            "Experiment 2\n"
            "Responses were reinforced under a VI 60-s schedule.\n"
        )
        results = extract_experiments(text)
        sched0 = results[0].ast["body"]["schedule"]
        sched1 = results[1].ast["body"]["schedule"]
        assert sched0["value"] == 30.0
        assert sched1["value"] == 60.0

    def test_body_with_no_schedule_still_emits_program(self) -> None:
        """An experiment whose body has no extractable schedule should
        resolve to a well-formed (if empty) Program rather than crashing."""
        text = (
            "Experiment 1\n"
            "Subjects were observed without programmed contingencies.\n\n"
            "Experiment 2\n"
            "Responses were reinforced under a VI 60-s schedule.\n"
        )
        results = extract_experiments(text)
        assert results[0].ast["body"]["type"] == "Program"
        assert results[0].ast["body"]["schedule"] == {}
        assert results[1].ast["body"]["schedule"]["value"] == 60.0

    def test_span_reports_body_range_not_whole_text(self) -> None:
        """Each ExtractResult's span should cover the body segment, so
        callers can correlate back to source positions."""
        text = (
            "Preamble.\n\n"
            "Experiment 1\n"
            "Body one.\n\n"
            "Experiment 2\n"
            "Body two.\n"
        )
        results = extract_experiments(text)
        assert len(results) == 2
        start0, end0 = results[0].span
        start1, end1 = results[1].span
        assert start0 < end0 <= start1 < end1 <= len(text)
        assert "Body one" in text[start0:end0]
        assert "Body two" in text[start1:end1]


class TestExtractPaper:
    """``extract_paper`` emits a Paper wrapper only for multi-experiment papers."""

    def test_no_experiments_returns_none(self) -> None:
        text = "Eight rats were trained under a VI 60-s schedule."
        assert extract_paper(text) is None

    def test_single_experiment_returns_none(self) -> None:
        """Single-experiment inputs defer to plain ``extract_all`` / caller.

        Back-compat: a lone ``Experiment 1`` heading should not coerce the
        output into a Paper wrapper, because most one-experiment papers are
        better expressed as a bare Program.
        """
        text = (
            "Experiment 1\n"
            "Responses were reinforced under a VI 60-s schedule.\n"
        )
        assert extract_paper(text) is None

    def test_multi_experiment_returns_paper(self) -> None:
        text = (
            "Experiment 1\n"
            "Responses were reinforced under a VI 30-s schedule.\n\n"
            "Experiment 2\n"
            "Responses were reinforced under a VI 60-s schedule.\n"
        )
        result = extract_paper(text)
        assert result is not None
        assert result.ast["type"] == "Paper"
        assert len(result.ast["experiments"]) == 2

    def test_paper_experiments_are_well_formed(self) -> None:
        text = (
            "Experiment 1\n"
            "Responses were reinforced under a VI 30-s schedule.\n\n"
            "Experiment 2\n"
            "Responses were reinforced under a VI 60-s schedule.\n"
        )
        result = extract_paper(text)
        assert result is not None
        for exp in result.ast["experiments"]:
            assert exp["type"] == "Experiment"
            assert exp["label"].startswith("Experiment")
            assert exp["body"]["type"] in {"Program", "PhaseSequence"}
