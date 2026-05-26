"""Targeted tests for rare branches of schedule extractors.

Closes coverage gaps that the broad roundtrip tests miss:
- ``attach_leaf_properties`` (LH / Timeout / ResponseCost, EN and JA)
- ``extract_modifier`` (DR_JA, PR with ratio= param, Pctl EN+JA)
- ``extract_gonogo`` defaults and JA path
- ``extract_aversive`` Escape JA branch
- ``extract_trial_based`` MTS helper branches
- ``extract_overlay`` short-text / no-component / changeover paths
- ``_parse_number_word`` digit branch
- ``extract_second_order`` early return when <2 abbrevs follow
"""

from __future__ import annotations

from contingency_procedure2dsl.extractors.schedule import (
    _extract_mts_consequence_en,
    _extract_mts_consequence_ja,
    _extract_mts_incorrect_en,
    _extract_mts_incorrect_ja,
    _extract_mts_iti_en,
    _extract_mts_iti_ja,
    _parse_number_word,
    attach_leaf_properties,
    extract_aversive,
    extract_gonogo,
    extract_modifier,
    extract_overlay,
    extract_second_order,
    extract_trial_based,
)


# --- attach_leaf_properties --------------------------------------------------


class TestAttachLeafPropertiesGuards:
    def test_non_dict_returns_input(self) -> None:
        assert attach_leaf_properties(None, "FR 5") is None
        assert attach_leaf_properties("not-a-dict", "FR 5") == "not-a-dict"

    def test_respondent_node_passthrough(self) -> None:
        node = {"type": "PairForwardDelay", "cs": "tone", "us": "shock"}
        out = attach_leaf_properties(node, "with a 3-s limited hold")
        assert out is node  # returned unchanged, same identity


class TestAttachLimitedHold:
    def test_en(self) -> None:
        out = attach_leaf_properties(
            {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0},
            "FR 5 schedule with a 2.5-s limited hold was used.",
        )
        assert out["limitedHold"] == 2.5
        assert out["limitedHoldUnit"] == "s"

    def test_ja(self) -> None:
        # The JA pattern matches "3.0-sのリミテッドホールド" without a space
        # between the unit and "の" (regex literal in source).
        out = attach_leaf_properties(
            {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0},
            "FR 5 スケジュールに 3.0-sのリミテッドホールドを設定した。",
        )
        assert out["limitedHold"] == 3.0
        assert out["limitedHoldUnit"] == "s"

    def test_existing_limitedhold_not_overwritten(self) -> None:
        out = attach_leaf_properties(
            {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0,
             "limitedHold": 1.0, "limitedHoldUnit": "s"},
            "with a 99-s limited hold",
        )
        assert out["limitedHold"] == 1.0  # preserved


class TestAttachTimeout:
    def test_resetting_en(self) -> None:
        out = attach_leaf_properties(
            {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0},
            "FR 5 with a 10-s resetting timeout was used.",
        )
        assert out["timeout"]["duration"] == 10.0
        assert out["timeout"]["resetOnResponse"] is True

    def test_non_resetting_en(self) -> None:
        out = attach_leaf_properties(
            {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0},
            "FR 5 with a 10-s non-resetting timeout was used.",
        )
        assert out["timeout"]["resetOnResponse"] is False

    def test_ja_reset_on_response(self) -> None:
        out = attach_leaf_properties(
            {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0},
            "FR 5 スケジュールに 5-sのタイムアウト（反応で再開する）を設定。",
        )
        assert out["timeout"]["duration"] == 5.0
        assert out["timeout"]["resetOnResponse"] is True

    def test_ja_no_reset(self) -> None:
        out = attach_leaf_properties(
            {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0},
            "FR 5 スケジュールに 5-sのタイムアウト（反応で再開しない）を設定。",
        )
        assert out["timeout"]["resetOnResponse"] is False


class TestAttachResponseCost:
    def test_en_token(self) -> None:
        out = attach_leaf_properties(
            {"type": "Atomic", "dist": "F", "domain": "R", "value": 5.0},
            "FR 5 with each target response removing 1 token.",
        )
        assert out["responseCost"] == {"amount": 1.0, "unit": "token"}

    def test_ja_token(self) -> None:
        out = attach_leaf_properties(
            {"type": "Atomic", "dist": "F", "domain": "R", "value": 5.0},
            "FR 5 スケジュール下で、各反応で2トークンが除去された。",
        )
        assert out["responseCost"] == {"amount": 2.0, "unit": "token"}

    def test_ja_point(self) -> None:
        out = attach_leaf_properties(
            {"type": "Atomic", "dist": "F", "domain": "R", "value": 5.0},
            "FR 5 スケジュール下で、各反応で3ポイントが除去された。",
        )
        assert out["responseCost"]["unit"] == "point"


# --- second_order -----------------------------------------------------------


class TestSecondOrderEarlyReturn:
    def test_no_marker(self) -> None:
        assert extract_second_order("FR 5 schedule.") is None

    def test_marker_without_enough_abbrevs(self) -> None:
        # "second-order" present but only one abbrev follows
        assert extract_second_order("A second-order FR 5 schedule.") is None


# --- modifier ---------------------------------------------------------------


class TestModifierDRJapanese:
    def test_drl_ja(self) -> None:
        text = "低反応率分化強化 (DRL) 10-s スケジュールが使用された。"
        r = extract_modifier(text)
        assert r is not None
        assert r.ast["modifier"] == "DRL"
        assert r.ast["value"] == 10.0
        assert r.ast["time_unit"] == "s"

    def test_dro_ja_without_unit(self) -> None:
        text = "他行動分化強化 (DRO) 30 スケジュールが使用された。"
        r = extract_modifier(text)
        assert r is not None
        assert r.ast["modifier"] == "DRO"
        assert "time_unit" not in r.ast


class TestModifierPR:
    def test_pr_en_with_ratio_param(self) -> None:
        text = "An exponential progressive-ratio schedule (ratio=1.5) was used."
        r = extract_modifier(text)
        assert r is not None
        assert r.ast["modifier"] == "PR"
        assert r.ast["pr_step"] == "exponential"
        assert r.ast["pr_ratio"] == 1.5

    def test_pr_en_with_start_and_step(self) -> None:
        text = "A linear progressive-ratio schedule (start=1, step=2) was used."
        r = extract_modifier(text)
        assert r is not None
        assert r.ast["pr_start"] == 1
        assert r.ast["pr_increment"] == 2

    def test_pr_ja(self) -> None:
        text = "線形漸進比率スケジュールが使用された。"
        r = extract_modifier(text)
        assert r is not None
        assert r.ast["modifier"] == "PR"
        assert r.ast["pr_step"] == "linear"


class TestModifierPercentile:
    def test_pctl_en_below_irt(self) -> None:
        text = (
            "A percentile schedule targeting responses at or below the 50th "
            "percentile of IRT (window=20) was in effect."
        )
        r = extract_modifier(text)
        assert r is not None
        assert r.ast["modifier"] == "Pctl"
        assert r.ast["pctl_target"] == "IRT"
        assert r.ast["pctl_rank"] == 50
        assert r.ast["pctl_dir"] == "below"
        assert r.ast["pctl_window"] == 20

    def test_pctl_en_above_force(self) -> None:
        text = (
            "A percentile schedule targeting responses at or above the 75th "
            "percentile of force was in effect."
        )
        r = extract_modifier(text)
        assert r is not None
        assert r.ast["pctl_target"] == "force"
        assert r.ast["pctl_dir"] == "above"
        assert "pctl_window" not in r.ast

    def test_pctl_ja_below(self) -> None:
        text = "IRTの第50百分位以下を満たす反応を強化するパーセンタイルスケジュール（ウィンドウ=20）"
        r = extract_modifier(text)
        assert r is not None
        assert r.ast["pctl_target"] == "IRT"
        assert r.ast["pctl_rank"] == 50
        assert r.ast["pctl_dir"] == "below"
        assert r.ast["pctl_window"] == 20

    def test_pctl_ja_above(self) -> None:
        text = "forceの第75百分位以上を満たす反応を強化するパーセンタイルスケジュール"
        r = extract_modifier(text)
        assert r is not None
        assert r.ast["pctl_dir"] == "above"


class TestModifierLag:
    def test_lag_en(self) -> None:
        r = extract_modifier("A Lag 4 schedule was used.")
        assert r is not None
        assert r.ast["modifier"] == "Lag"
        assert r.ast["length"] == 4


# --- aversive Escape JA -----------------------------------------------------


class TestAversiveEscapeJA:
    def test_escape_ja(self) -> None:
        text = "自由オペラント逃避スケジュールが用いられた。30-s の安全期間を設定した。"
        r = extract_aversive(text)
        assert r is not None
        assert r.ast["type"] == "AversiveSchedule"
        assert r.ast["kind"] == "Escape"
        assert r.ast["params"]["SafeDuration"]["value"] == 30.0


# --- gonogo defaults ---------------------------------------------------------


class TestGoNoGoConsequenceDefaults:
    def test_gonogo_crf(self) -> None:
        text = (
            "A Go/NoGo discrimination procedure was used. "
            "Go trials produced a reinforcer (continuous reinforcement). "
            "Responses during the 5-s response window on Go trials were "
            "measured. NoGo trials were followed by a 30-s timeout. "
            "A 10-s inter-trial interval separated successive trials."
        )
        r = extract_gonogo(text)
        assert r is not None
        assert r.ast["consequence"] == {"type": "Special", "kind": "CRF"}
        assert r.ast["falseAlarm"]["type"] == "Atomic"
        assert r.ast["falseAlarm"]["value"] == 30.0

    def test_gonogo_ext_no_falsealarm_timeout(self) -> None:
        text = (
            "A Go/NoGo discrimination procedure was used. "
            "Go trials had no programmed consequences (extinction). "
            "Responses during the 5-s response window on Go trials were "
            "measured."
        )
        r = extract_gonogo(text)
        assert r is not None
        assert r.ast["consequence"] == {"type": "Special", "kind": "EXT"}
        # No NoGo timeout → falseAlarm defaults to EXT
        assert r.ast["falseAlarm"] == {"type": "Special", "kind": "EXT"}
        # ITI not present → falls back to (10.0, "s")
        assert r.ast["ITI"] == 10.0
        assert r.ast["ITI_unit"] == "s"

    def test_gonogo_consequence_as_schedule(self) -> None:
        text = (
            "A Go/NoGo discrimination procedure was used. "
            "Go trials were reinforced under a FR 3 schedule. "
            "Responses during the 5-s response window on Go trials were measured."
        )
        r = extract_gonogo(text)
        assert r is not None
        cons = r.ast["consequence"]
        assert cons["type"] == "Atomic"
        assert cons["dist"] == "F"
        assert cons["domain"] == "R"
        assert cons["value"] == 3.0

    def test_gonogo_ja_window_only(self) -> None:
        text = (
            "Go/NoGo 弁別手続きを用いた。Go 試行の 5-s 反応時間内の反応が測定された。"
        )
        r = extract_gonogo(text)
        assert r is not None
        # JA branch: consequence/falseAlarm hard-coded defaults
        assert r.ast["consequence"] == {"type": "Special", "kind": "CRF"}
        assert r.ast["falseAlarm"] == {"type": "Special", "kind": "EXT"}

    def test_gonogo_no_window_returns_none(self) -> None:
        text = "A Go/NoGo discrimination procedure was used. (no window clause)"
        assert extract_gonogo(text) is None


# --- MTS helpers -----------------------------------------------------------


class TestMTSConsequenceHelpersEN:
    def test_crf(self) -> None:
        assert _extract_mts_consequence_en(
            "Correct responses produced a reinforcer (continuous reinforcement)."
        ) == {"type": "Special", "kind": "CRF"}

    def test_ext(self) -> None:
        assert _extract_mts_consequence_en(
            "Correct responses had no programmed consequences (extinction)."
        ) == {"type": "Special", "kind": "EXT"}

    def test_schedule(self) -> None:
        ast = _extract_mts_consequence_en(
            "Correct responses were reinforced under a VI 30-s schedule."
        )
        assert ast["type"] == "Atomic"
        assert ast["dist"] == "V"
        assert ast["domain"] == "I"
        assert ast["time_unit"] == "s"

    def test_default(self) -> None:
        assert _extract_mts_consequence_en("nothing matching") == {
            "type": "Special", "kind": "CRF",
        }


class TestMTSIncorrectHelpersEN:
    def test_ext(self) -> None:
        assert _extract_mts_incorrect_en(
            "Incorrect responses had no programmed consequences (extinction)."
        ) == {"type": "Special", "kind": "EXT"}

    def test_timeout_atomic(self) -> None:
        ast = _extract_mts_incorrect_en(
            "Incorrect responses were followed by a 5-s timeout."
        )
        assert ast["type"] == "Atomic"
        assert ast["dist"] == "F"
        assert ast["domain"] == "T"
        assert ast["value"] == 5.0

    def test_schedule_branch(self) -> None:
        ast = _extract_mts_incorrect_en(
            "Incorrect responses were followed by a FT 10-s schedule."
        )
        assert ast["dist"] == "F"
        assert ast["domain"] == "T"
        assert ast["time_unit"] == "s"

    def test_default(self) -> None:
        assert _extract_mts_incorrect_en("nothing matching") == {
            "type": "Special", "kind": "EXT",
        }


class TestMTSITIHelpersEN:
    def test_match(self) -> None:
        assert _extract_mts_iti_en("a 7-s inter-trial interval separated trials") == (7.0, "s")

    def test_default(self) -> None:
        assert _extract_mts_iti_en("no iti") == (5.0, "s")


class TestMTSHelpersJA:
    def test_consequence_ja_crf(self) -> None:
        text = "正反応に対しては餌が呈示された（連続強化）。"
        assert _extract_mts_consequence_ja(text) == {"type": "Special", "kind": "CRF"}

    def test_consequence_ja_ext(self) -> None:
        text = "正反応に対してはプログラムされた結果は呈示されなかった（消去）。"
        assert _extract_mts_consequence_ja(text) == {"type": "Special", "kind": "EXT"}

    def test_consequence_ja_schedule(self) -> None:
        text = "正反応に対しては VI 30-s スケジュールが使用された。"
        ast = _extract_mts_consequence_ja(text)
        assert ast["type"] == "Atomic"
        assert ast["dist"] == "V"
        assert ast["domain"] == "I"

    def test_consequence_ja_default(self) -> None:
        assert _extract_mts_consequence_ja("該当なし") == {
            "type": "Special", "kind": "CRF",
        }

    def test_incorrect_ja_ext(self) -> None:
        assert _extract_mts_incorrect_ja(
            "誤反応に対してはプログラムされた結果は呈示されなかった（消去）。"
        ) == {"type": "Special", "kind": "EXT"}

    def test_incorrect_ja_timeout(self) -> None:
        ast = _extract_mts_incorrect_ja("誤反応に対しては 5-s のタイムアウト")
        assert ast["type"] == "Atomic"
        assert ast["value"] == 5.0

    def test_incorrect_ja_default(self) -> None:
        assert _extract_mts_incorrect_ja("該当なし") == {
            "type": "Special", "kind": "EXT",
        }

    def test_iti_ja_match(self) -> None:
        assert _extract_mts_iti_ja("試行間間隔は 8-s") == (8.0, "s")

    def test_iti_ja_default(self) -> None:
        assert _extract_mts_iti_ja("該当なし") == (5.0, "s")


class TestMTSIntegrationEN:
    def test_identity_mts_with_two_comparisons(self) -> None:
        text = (
            "An identity matching-to-sample (MTS) procedure was used with "
            "two comparison stimuli. "
            "Correct responses produced a reinforcer (continuous reinforcement). "
            "Incorrect responses had no programmed consequences (extinction). "
            "A 5-s inter-trial interval separated trials."
        )
        r = extract_trial_based(text)
        assert r is not None
        assert r.ast["trial_type"] == "MTS"
        assert r.ast["mts_type"] == "identity"
        assert r.ast["comparisons"] == 2


class TestParseNumberWord:
    def test_digit_branch(self) -> None:
        assert _parse_number_word("5") == 5

    def test_word_branch(self) -> None:
        assert _parse_number_word("four") == 4
        assert _parse_number_word("Eight") == 8


# --- overlay edge cases -----------------------------------------------------


class TestOverlay:
    def test_no_marker_returns_none(self) -> None:
        assert extract_overlay("FR 5 schedule.") is None

    def test_single_sentence_returns_none(self) -> None:
        # Marker exists but only one sentence — short-circuits at len(sentences)<2
        assert extract_overlay("punishment superimposed on the baseline") is None

    def test_changeover_target_extracted(self) -> None:
        text = (
            "A VI 30-s baseline was in effect. "
            "Punishment was superimposed on changeover responses with FT 10-s."
        )
        r = extract_overlay(text)
        assert r is not None
        assert r.ast["combinator"] == "Overlay"
        assert r.ast["params"] == {"target": "changeover"}

    def test_baseline_overlay_no_changeover_param(self) -> None:
        text = (
            "A VI 30-s baseline was in effect. "
            "Punishment was superimposed on the baseline with FT 10-s."
        )
        r = extract_overlay(text)
        assert r is not None
        assert "params" not in r.ast

    def test_overlay_ja_passes_through_when_no_components(self) -> None:
        # Marker matches but neither sentence has an atomic/special schedule
        text = "ベースラインを実施した。罰刺激が重畳された。"
        assert extract_overlay(text) is None
