"""Tests for respondent (Pavlovian) primitive extraction (R1-R14).

Each test exercises the success path for one extractor in EN and JA, plus
a no-match path. The aim is to pin the AST shape and confidence so future
regressions surface as focused failures.
"""

from __future__ import annotations

from contingency_procedure2dsl.extractors.respondent import (
    _duration,
    _ident,
    extract_contingency,
    extract_cs_only,
    extract_differential,
    extract_explicitly_unpaired,
    extract_pair_backward,
    extract_pair_forward_delay,
    extract_pair_forward_trace,
    extract_pair_simultaneous,
    extract_resp_compound,
    extract_resp_extinction,
    extract_resp_iti,
    extract_resp_serial,
    extract_respondent,
    extract_truly_random,
    extract_us_only,
)


# --- helpers ----------------------------------------------------------------


class TestHelpers:
    def test_duration_builds_dict(self) -> None:
        assert _duration("30", "s") == {"value": 30.0, "unit": "s"}
        assert _duration("1.5", "min") == {"value": 1.5, "unit": "min"}

    def test_ident_normalizes(self) -> None:
        assert _ident("  Tone Light ") == "tone_light"
        assert _ident("Shock") == "shock"


# --- R1: ForwardDelay -------------------------------------------------------


class TestForwardDelay:
    def test_en_match(self) -> None:
        text = (
            "tone served as the conditioned stimulus and shock as the "
            "unconditioned stimulus in a forward-delay pairing procedure "
            "(CS-US interval 5-s; CS duration 10-s)."
        )
        r = extract_pair_forward_delay(text)
        assert r is not None
        assert r.ast == {
            "type": "PairForwardDelay",
            "cs": "tone", "us": "shock",
            "isi": {"value": 5.0, "unit": "s"},
            "cs_duration": {"value": 10.0, "unit": "s"},
        }
        assert r.confidence == 0.85

    def test_ja_match(self) -> None:
        text = (
            "音を条件刺激、ショックを無条件刺激とする順行遅延対呈示を実施した"
            "（CS-US 間隔 5-s、CS 持続 10-s）"
        )
        r = extract_pair_forward_delay(text)
        assert r is not None
        assert r.ast["type"] == "PairForwardDelay"
        assert r.ast["cs"] == "音"
        assert r.ast["us"] == "ショック"
        assert r.ast["isi"] == {"value": 5.0, "unit": "s"}

    def test_no_match(self) -> None:
        assert extract_pair_forward_delay("FR 1 was used.") is None


# --- R2: ForwardTrace ------------------------------------------------------


class TestForwardTrace:
    def test_en_match_without_cs_duration(self) -> None:
        text = (
            "tone served as the conditioned stimulus and shock as the "
            "unconditioned stimulus in a forward-trace pairing procedure "
            "(trace interval 2-s)."
        )
        r = extract_pair_forward_trace(text)
        assert r is not None
        assert r.ast["type"] == "PairForwardTrace"
        assert r.ast["trace_interval"] == {"value": 2.0, "unit": "s"}
        assert "cs_duration" not in r.ast

    def test_en_match_with_cs_duration(self) -> None:
        text = (
            "tone served as the conditioned stimulus and shock as the "
            "unconditioned stimulus in a forward-trace pairing procedure "
            "(trace interval 2-s; CS duration 10-s)."
        )
        r = extract_pair_forward_trace(text)
        assert r is not None
        assert r.ast["cs_duration"] == {"value": 10.0, "unit": "s"}

    def test_ja_match(self) -> None:
        text = (
            "音を条件刺激、ショックを無条件刺激とする順行トレース対呈示を実施した"
            "（トレース間隔 2-s、CS 持続 10-s）"
        )
        r = extract_pair_forward_trace(text)
        assert r is not None
        assert r.ast["type"] == "PairForwardTrace"
        assert r.ast["cs_duration"] == {"value": 10.0, "unit": "s"}


# --- R3: Simultaneous ------------------------------------------------------


class TestSimultaneous:
    def test_en(self) -> None:
        text = "tone and shock were presented simultaneously in a Pavlovian pairing procedure."
        r = extract_pair_simultaneous(text)
        assert r is not None
        assert r.ast == {"type": "PairSimultaneous", "cs": "tone", "us": "shock"}

    def test_ja(self) -> None:
        text = "音とショックの同時対呈示を実施した。"
        r = extract_pair_simultaneous(text)
        assert r is not None
        assert r.ast == {"type": "PairSimultaneous", "cs": "音", "us": "ショック"}


# --- R4: Backward ----------------------------------------------------------


class TestBackward:
    def test_en(self) -> None:
        text = (
            "shock was followed by tone in a backward pairing procedure "
            "(US-CS interval 3-s)."
        )
        r = extract_pair_backward(text)
        assert r is not None
        assert r.ast == {
            "type": "PairBackward", "us": "shock", "cs": "tone",
            "isi": {"value": 3.0, "unit": "s"},
        }


# --- R5: Extinction --------------------------------------------------------


class TestRespondentExtinction:
    def test_en(self) -> None:
        text = "tone was presented alone for extinction testing."
        r = extract_resp_extinction(text)
        assert r is not None
        assert r.ast == {"type": "Extinction", "cs": "tone"}

    def test_ja(self) -> None:
        text = "音の単独呈示により消去を実施した。"
        r = extract_resp_extinction(text)
        assert r is not None
        assert r.ast["cs"] == "音"

    def test_no_match(self) -> None:
        assert extract_resp_extinction("FR 5 was used.") is None


# --- R6/R7: CSOnly / USOnly -----------------------------------------------


class TestCSOnly:
    def test_en(self) -> None:
        text = "tone was presented alone on 20 trials."
        r = extract_cs_only(text)
        assert r is not None
        assert r.ast == {"type": "CSOnly", "cs": "tone", "trials": 20}

    def test_ja(self) -> None:
        text = "音を単独で30試行呈示した。"
        r = extract_cs_only(text)
        assert r is not None
        assert r.ast["trials"] == 30


class TestUSOnly:
    def test_en(self) -> None:
        text = "The US shock was presented alone on 15 trials."
        r = extract_us_only(text)
        assert r is not None
        assert r.ast == {"type": "USOnly", "us": "shock", "trials": 15}

    def test_no_match(self) -> None:
        assert extract_us_only("tone was presented alone on 20 trials.") is None


# --- R8: Contingency -------------------------------------------------------


class TestContingency:
    def test_en(self) -> None:
        text = "Pavlovian contingencies were arranged: p(US|CS) = 0.8, p(US|no CS) = 0.2."
        r = extract_contingency(text)
        assert r is not None
        assert r.ast == {
            "type": "Contingency",
            "p_us_given_cs": 0.8,
            "p_us_given_no_cs": 0.2,
        }

    def test_negation_glyph(self) -> None:
        text = "Pavlovian contingencies: p(US|CS) = 1.0, p(US|¬CS) = 0.0."
        r = extract_contingency(text)
        assert r is not None
        assert r.ast["p_us_given_cs"] == 1.0
        assert r.ast["p_us_given_no_cs"] == 0.0


# --- R9: TrulyRandom -------------------------------------------------------


class TestTrulyRandom:
    def test_en_without_p(self) -> None:
        text = "tone and shock were arranged as a truly random control."
        r = extract_truly_random(text)
        assert r is not None
        assert r.ast == {"type": "TrulyRandom", "cs": "tone", "us": "shock"}

    def test_en_with_p(self) -> None:
        text = "tone and shock were arranged as a truly random control (p=0.5)."
        r = extract_truly_random(text)
        assert r is not None
        assert r.ast["p"] == 0.5

    def test_ja(self) -> None:
        text = "音とショックを真のランダム統制として配置した（p=0.3）。"
        r = extract_truly_random(text)
        assert r is not None
        assert r.ast["p"] == 0.3


# --- R10: ExplicitlyUnpaired ----------------------------------------------


class TestExplicitlyUnpaired:
    def test_en_without_separation(self) -> None:
        text = "tone and shock were arranged as an explicitly unpaired control."
        r = extract_explicitly_unpaired(text)
        assert r is not None
        assert r.ast["type"] == "ExplicitlyUnpaired"
        assert "min_separation" not in r.ast

    def test_en_with_separation(self) -> None:
        text = (
            "tone and shock were arranged as an explicitly unpaired control "
            "(minimum separation 30-s)."
        )
        r = extract_explicitly_unpaired(text)
        assert r is not None
        assert r.ast["min_separation"] == {"value": 30.0, "unit": "s"}

    def test_ja(self) -> None:
        text = "音とショックを明示的に非対呈示で配置した（最小分離 30-s）。"
        r = extract_explicitly_unpaired(text)
        assert r is not None
        assert r.ast["min_separation"] == {"value": 30.0, "unit": "s"}


# --- R11: Compound (respondent) -------------------------------------------


class TestRespondentCompound:
    def test_en(self) -> None:
        text = "tone, light and buzzer were presented simultaneously as a compound conditioned stimulus."
        r = extract_resp_compound(text)
        assert r is not None
        assert r.ast["type"] == "Compound"
        assert "tone" in r.ast["cs_list"]
        assert "light" in r.ast["cs_list"]
        assert "buzzer" in r.ast["cs_list"]
        assert r.ast["mode"] == "Simultaneous"

    def test_ja(self) -> None:
        text = "音、光、ブザーを同時に複合条件刺激として呈示した。"
        r = extract_resp_compound(text)
        assert r is not None
        assert len(r.ast["cs_list"]) == 3


# --- R12: Serial -----------------------------------------------------------


class TestRespondentSerial:
    def test_en(self) -> None:
        text = (
            "Conditioned stimuli tone → light → buzzer were presented in "
            "serial order (inter-stimulus interval 5-s)."
        )
        r = extract_resp_serial(text)
        assert r is not None
        assert r.ast["type"] == "Serial"
        assert r.ast["cs_list"] == ["tone", "light", "buzzer"]
        assert r.ast["isi"] == {"value": 5.0, "unit": "s"}


# --- R13: ITI --------------------------------------------------------------


class TestRespondentITI:
    def test_en_fixed(self) -> None:
        # Extractor pattern hard-codes "a" as the article, so "fixed" /
        # "uniform" work naturally; "exponential" doesn't because of the
        # article-agreement gap. Pinning the working path here.
        text = (
            "The inter-trial interval followed a fixed distribution "
            "with mean 60-s."
        )
        r = extract_resp_iti(text)
        assert r is not None
        assert r.ast == {
            "type": "ITI",
            "distribution": "fixed",
            "mean": {"value": 60.0, "unit": "s"},
        }

    def test_ja_uniform(self) -> None:
        text = "試行間間隔は平均 30-s の一様分布に従った。"
        r = extract_resp_iti(text)
        assert r is not None
        assert r.ast["distribution"] == "uniform"
        assert r.ast["mean"] == {"value": 30.0, "unit": "s"}


# --- R14: Differential -----------------------------------------------------


class TestDifferential:
    def test_en_without_us(self) -> None:
        text = "Differential conditioning with tone as CS+ and light as CS−."
        r = extract_differential(text)
        assert r is not None
        assert r.ast == {
            "type": "Differential",
            "cs_positive": "tone",
            "cs_negative": "light",
        }

    def test_en_with_us(self) -> None:
        text = "Differential conditioning with tone as CS+ and light as CS- (US: shock)."
        r = extract_differential(text)
        assert r is not None
        assert r.ast["us"] == "shock"

    def test_ja(self) -> None:
        text = "音を CS+、光を CS− とする弁別条件づけを実施した（US: ショック）。"
        r = extract_differential(text)
        assert r is not None
        assert r.ast["us"] == "ショック"


# --- pipeline entry --------------------------------------------------------


class TestExtractRespondentDispatch:
    def test_pair_forward_delay_dispatched_first(self) -> None:
        text = (
            "tone served as the conditioned stimulus and shock as the "
            "unconditioned stimulus in a forward-delay pairing procedure "
            "(CS-US interval 5-s; CS duration 10-s)."
        )
        r = extract_respondent(text)
        assert r is not None
        assert r.ast["type"] == "PairForwardDelay"

    def test_no_match_returns_none(self) -> None:
        assert extract_respondent("FR 5 was used.") is None
