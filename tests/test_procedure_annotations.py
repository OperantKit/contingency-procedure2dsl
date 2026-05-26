"""Tests for ``extract_procedure_annotations`` patterns.

Covers @reinforcer, @punisher, @cs, @us, @context, @clock,
@dependent_measure, @session (trials / blocks), and @cs_interval, in
both EN and JA where applicable.
"""

from __future__ import annotations

from contingency_procedure2dsl.extractors.annotations import (
    extract_procedure_annotations,
)


def _by_keyword(results: list, keyword: str) -> list:
    return [r for r in results if r.ast.get("keyword") == keyword]


class TestReinforcerPunisher:
    def test_reinforcer_en(self) -> None:
        results = extract_procedure_annotations(
            "Reinforcement consisted of 3-s grain delivery."
        )
        reinforcers = _by_keyword(results, "reinforcer")
        assert len(reinforcers) == 1
        assert reinforcers[0].ast["positional"] == "3-s grain"

    def test_reinforcer_ja(self) -> None:
        results = extract_procedure_annotations("強化子として餌を使用した。")
        reinforcers = _by_keyword(results, "reinforcer")
        assert len(reinforcers) == 1
        assert reinforcers[0].ast["positional"] == "餌"

    def test_punisher_en(self) -> None:
        results = extract_procedure_annotations(
            "A 0.5-mA footshock served as the punisher."
        )
        punishers = _by_keyword(results, "punisher")
        assert len(punishers) == 1

    def test_punisher_ja(self) -> None:
        results = extract_procedure_annotations("罰刺激として電気ショックを使用した。")
        punishers = _by_keyword(results, "punisher")
        assert len(punishers) == 1
        assert "電気ショック" in punishers[0].ast["positional"]


class TestCSUS:
    def test_cs_en(self) -> None:
        results = extract_procedure_annotations(
            "tone served as the conditioned stimulus."
        )
        cs = _by_keyword(results, "cs")
        assert len(cs) == 1
        assert cs[0].ast["positional"] == "tone"

    def test_cs_ja(self) -> None:
        results = extract_procedure_annotations("音を条件刺激として使用した。")
        cs = _by_keyword(results, "cs")
        assert len(cs) == 1

    def test_us_en(self) -> None:
        results = extract_procedure_annotations(
            "shock served as the unconditioned stimulus."
        )
        us = _by_keyword(results, "us")
        assert len(us) == 1
        assert us[0].ast["positional"] == "shock"

    def test_us_ja(self) -> None:
        results = extract_procedure_annotations("ショックを無条件刺激として使用した。")
        us = _by_keyword(results, "us")
        assert len(us) == 1


class TestContext:
    def test_context_en_simple(self) -> None:
        results = extract_procedure_annotations(
            "The procedure was conducted in context A."
        )
        contexts = _by_keyword(results, "context")
        assert len(contexts) == 1
        assert contexts[0].ast["positional"] == "A"
        assert "params" not in contexts[0].ast

    def test_context_en_with_cues(self) -> None:
        results = extract_procedure_annotations(
            "The procedure was conducted in context B (cues: black walls, mint scent)."
        )
        contexts = _by_keyword(results, "context")
        assert len(contexts) == 1
        ann = contexts[0].ast
        assert ann["positional"] == "B"
        assert "cues" in ann["params"]
        assert "black walls" in ann["params"]["cues"]

    def test_context_ja(self) -> None:
        results = extract_procedure_annotations("文脈Aで実施された。")
        contexts = _by_keyword(results, "context")
        assert len(contexts) == 1
        assert contexts[0].ast["positional"] == "A"


class TestClock:
    def test_clock_en(self) -> None:
        results = extract_procedure_annotations(
            "Session time was recorded in ms."
        )
        clock = _by_keyword(results, "clock")
        assert len(clock) == 1
        assert clock[0].ast["params"]["unit"] == "ms"

    def test_clock_ja(self) -> None:
        results = extract_procedure_annotations("セッションの時間単位は s であった。")
        clock = _by_keyword(results, "clock")
        assert len(clock) == 1
        assert clock[0].ast["params"]["unit"] == "s"


class TestDependentMeasure:
    def test_dependent_en(self) -> None:
        results = extract_procedure_annotations(
            "The primary dependent measure was rate."
        )
        dep = _by_keyword(results, "dependent_measure")
        assert len(dep) == 1
        assert dep[0].ast["params"]["variables"] == ["rate"]

    def test_dependent_ja_multiple_vars(self) -> None:
        results = extract_procedure_annotations(
            "主要従属変数は反応率、強化率、潜時であった。"
        )
        dep = _by_keyword(results, "dependent_measure")
        assert len(dep) == 1
        vars_list = dep[0].ast["params"]["variables"]
        assert "反応率" in vars_list
        assert "強化率" in vars_list
        assert "潜時" in vars_list


class TestSessionStructure:
    def test_session_blocks_en(self) -> None:
        results = extract_procedure_annotations(
            "Each session consisted of 5 blocks of 20 trials."
        )
        sess = _by_keyword(results, "session")
        assert len(sess) == 1
        assert sess[0].ast["params"] == {"blocks": 5, "block_size": 20}

    def test_session_blocks_ja(self) -> None:
        results = extract_procedure_annotations(
            "各セッションは3ブロック×30試行で構成された。"
        )
        sess = _by_keyword(results, "session")
        assert len(sess) == 1
        assert sess[0].ast["params"]["blocks"] == 3
        assert sess[0].ast["params"]["block_size"] == 30

    def test_session_trials_only_en(self) -> None:
        results = extract_procedure_annotations(
            "Each session consisted of 50 trials."
        )
        sess = _by_keyword(results, "session")
        assert len(sess) == 1
        assert sess[0].ast["params"] == {"trials": 50}

    def test_session_blocks_pattern_wins_over_trials(self) -> None:
        # When both could match, the blocks pattern is preferred via the
        # if/else cascade.
        results = extract_procedure_annotations(
            "Each session consisted of 4 blocks of 25 trials."
        )
        sess = _by_keyword(results, "session")
        assert len(sess) == 1
        assert "blocks" in sess[0].ast["params"]
        assert "trials" not in sess[0].ast["params"]


class TestCSInterval:
    def test_cs_interval_en(self) -> None:
        results = extract_procedure_annotations(
            "The CS-US interval was 10-s for all subjects."
        )
        ann = _by_keyword(results, "cs_interval")
        assert len(ann) == 1
        assert ann[0].ast["params"] == {"value": 10.0, "time_unit": "s"}

    def test_cs_interval_ja(self) -> None:
        results = extract_procedure_annotations(
            "CS-US 間隔は 5.0-s に設定された。"
        )
        ann = _by_keyword(results, "cs_interval")
        assert len(ann) == 1
        assert ann[0].ast["params"]["value"] == 5.0


class TestWordToNumber:
    """Cover the digit branch of the internal word→number helper."""

    def test_digit_input_returns_int(self) -> None:
        from contingency_procedure2dsl.extractors.annotations import (
            _word_to_number,
        )

        assert _word_to_number("7") == 7
        assert _word_to_number("12") == 12

    def test_word_input(self) -> None:
        from contingency_procedure2dsl.extractors.annotations import (
            _word_to_number,
        )

        assert _word_to_number("three") == 3
        assert _word_to_number("Twelve") == 12

    def test_unknown_returns_none(self) -> None:
        from contingency_procedure2dsl.extractors.annotations import (
            _word_to_number,
        )

        assert _word_to_number("thirteen") is None
