"""Tests for phase / PhaseSequence extraction.

Covers detect_phase_boundaries (EN/JA), criterion detection
(FixedSessions / Stability / ExperimenterJudgment), and the full
extract_phase_sequence pipeline.
"""

from __future__ import annotations

import pytest

from contingency_procedure2dsl.extractors.phase import (
    _detect_criterion,
    detect_phase_boundaries,
    extract_phase_sequence,
)


# --- detect_phase_boundaries -----------------------------------------------


class TestDetectPhaseBoundariesEN:
    def test_single_phase_returns_empty(self) -> None:
        text = "Responses were reinforced on a VI 30-s schedule."
        assert detect_phase_boundaries(text) == []

    def test_two_phases_in_the(self) -> None:
        text = (
            "In the acquisition phase, responses were reinforced on a VI 30-s "
            "schedule. In the extinction phase, responses no longer produced "
            "reinforcers."
        )
        pairs = detect_phase_boundaries(text)
        assert len(pairs) == 2
        labels = [p[0] for p in pairs]
        assert "acquisition" in labels
        assert "extinction" in labels

    def test_two_phases_during(self) -> None:
        text = (
            "During the baseline phase, the FR 1 schedule was in effect. "
            "During the treatment phase, the FR 5 schedule was used."
        )
        pairs = detect_phase_boundaries(text)
        assert len(pairs) == 2
        assert pairs[0][0] == "baseline"
        assert pairs[1][0] == "treatment"

    def test_case_insensitive(self) -> None:
        text = (
            "IN THE ACQUISITION PHASE, FR 10 was used. "
            "IN THE EXTINCTION PHASE, no reinforcers were delivered."
        )
        pairs = detect_phase_boundaries(text)
        assert len(pairs) == 2


class TestDetectPhaseBoundariesJA:
    def test_single_japanese_phase_returns_pair(self) -> None:
        # The JA pattern matches a single 【...】 block too, but multi-phase
        # detection in extract_phase_sequence requires len>=2.
        text = "【獲得】VI 30-s スケジュールに従って反応が強化された。"
        pairs = detect_phase_boundaries(text)
        # detect_phase_boundaries itself returns whatever it finds.
        assert len(pairs) == 1
        assert pairs[0][0] == "獲得"

    def test_two_japanese_phases(self) -> None:
        text = (
            "【獲得】VI 30-s スケジュールに従って反応が強化された。"
            "【消去】反応は強化されなかった。"
        )
        pairs = detect_phase_boundaries(text)
        assert len(pairs) == 2
        assert pairs[0][0] == "獲得"
        assert pairs[1][0] == "消去"

    def test_english_pattern_takes_precedence(self) -> None:
        # When EN matches succeed, the JA branch is not even consulted.
        text = (
            "In the acquisition phase, FR 1 was used. "
            "In the extinction phase, no reinforcers were delivered. "
            "【獲得】これは無視される。"
        )
        pairs = detect_phase_boundaries(text)
        assert all(label != "獲得" for label, _ in pairs)


# --- _detect_criterion ------------------------------------------------------


class TestCriterionFixed:
    def test_english_fixed_sessions(self) -> None:
        crit = _detect_criterion("This phase lasted 10 sessions.")
        assert crit == {"type": "FixedSessions", "count": 10}

    def test_english_fixed_sessions_lowercase(self) -> None:
        crit = _detect_criterion("this phase lasted 5 sessions before reversal")
        assert crit == {"type": "FixedSessions", "count": 5}

    def test_japanese_fixed_sessions(self) -> None:
        crit = _detect_criterion("本フェーズは20セッション実施した。")
        assert crit == {"type": "FixedSessions", "count": 20}


class TestCriterionStability:
    def test_english_stability_response_rates(self) -> None:
        crit = _detect_criterion(
            "until response rates varied by no more than 10% across 5 "
            "consecutive sessions"
        )
        assert crit is not None
        assert crit["type"] == "Stability"
        assert crit["window_sessions"] == 5
        assert crit["max_change_pct"] == 10.0
        assert crit["measure"] == "rate"

    def test_english_stability_fractional(self) -> None:
        crit = _detect_criterion(
            "until reinforcement rates varied by no more than 7.5% across 3 "
            "consecutive sessions"
        )
        assert crit is not None
        assert crit["max_change_pct"] == 7.5
        assert crit["window_sessions"] == 3

    def test_japanese_stability_response_rate(self) -> None:
        crit = _detect_criterion("直近5セッションの反応率の変動が10%以内")
        assert crit is not None
        assert crit["type"] == "Stability"
        assert crit["window_sessions"] == 5
        assert crit["max_change_pct"] == 10.0
        assert crit["measure"] == "rate"

    def test_japanese_stability_latency_mapping(self) -> None:
        crit = _detect_criterion("直近3セッションの潜時の変動が5%以内")
        assert crit is not None
        assert crit["measure"] == "latency"

    def test_japanese_stability_reinforcers_mapping(self) -> None:
        crit = _detect_criterion("直近4セッションの強化率の変動が8%以内")
        assert crit is not None
        assert crit["measure"] == "reinforcers"

    def test_japanese_stability_unknown_measure_falls_back_to_rate(self) -> None:
        crit = _detect_criterion("直近6セッションの未知指標の変動が9%以内")
        assert crit is not None
        assert crit["measure"] == "rate"  # default fallback


class TestCriterionJudgment:
    def test_english_experimenter_discretion(self) -> None:
        crit = _detect_criterion(
            "Phase termination was at the experimenter's discretion."
        )
        assert crit == {"type": "ExperimenterJudgment"}

    def test_japanese_experimenter_judgment(self) -> None:
        crit = _detect_criterion("実験者の判断によりフェーズを終了した。")
        assert crit == {"type": "ExperimenterJudgment"}

    def test_no_criterion(self) -> None:
        assert _detect_criterion("Some prose without a criterion clause.") is None


# --- extract_phase_sequence -------------------------------------------------


class TestExtractPhaseSequence:
    def test_mono_phase_returns_none(self) -> None:
        text = "Responses were reinforced on a VI 30-s schedule."
        assert extract_phase_sequence(text) is None

    def test_multi_phase_returns_result(self) -> None:
        text = (
            "In the acquisition phase, responses were reinforced on a "
            "fixed-ratio (FR) 5 schedule. This phase lasted 10 sessions. "
            "In the extinction phase, responses no longer produced "
            "reinforcers. This phase lasted 5 sessions."
        )
        result = extract_phase_sequence(text)
        assert result is not None
        ast = result.ast
        assert ast["type"] == "PhaseSequence"
        assert len(ast["phases"]) == 2

        acq, ext = ast["phases"]
        assert acq["label"] == "acquisition"
        assert ext["label"] == "extinction"
        assert acq["criterion"] == {"type": "FixedSessions", "count": 10}
        assert ext["criterion"] == {"type": "FixedSessions", "count": 5}
        assert acq["schedule"] is not None
        assert result.confidence == pytest.approx(0.70)
        assert result.span == (0, len(text))

    def test_multi_phase_without_criteria(self) -> None:
        text = (
            "In the acquisition phase, responses were reinforced on a VI 30-s "
            "schedule. In the extinction phase, responses no longer produced "
            "reinforcers."
        )
        result = extract_phase_sequence(text)
        assert result is not None
        ast = result.ast
        for phase in ast["phases"]:
            assert "criterion" not in phase  # no criterion was attached

    def test_japanese_multi_phase(self) -> None:
        text = (
            "【獲得】VI 30-s スケジュールに従って反応が強化された。"
            "本フェーズは10セッション実施した。"
            "【消去】反応は強化されなかった。本フェーズは5セッション実施した。"
        )
        result = extract_phase_sequence(text)
        assert result is not None
        ast = result.ast
        assert len(ast["phases"]) == 2
        labels = [p["label"] for p in ast["phases"]]
        assert "獲得" in labels
        assert "消去" in labels
