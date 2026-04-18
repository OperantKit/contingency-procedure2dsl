"""Regression tests for extractors added to reach DSL-surface parity."""

from __future__ import annotations

from contingency_dsl2procedure import compile_method
from contingency_procedure2dsl import extract_schedule


def _program(schedule: dict) -> dict:
    return {
        "type": "Program",
        "param_decls": [],
        "bindings": [],
        "schedule": schedule,
    }


class TestExtCompoundComponent:
    def test_mult_fr_ext(self) -> None:
        prose = compile_method(_program({
            "type": "Compound", "combinator": "Mult",
            "components": [
                {"type": "Atomic", "dist": "F", "domain": "R", "value": 5.0},
                {"type": "Special", "kind": "EXT"},
            ],
        })).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["type"] == "Compound"
        assert r.ast["combinator"] == "Mult"
        assert len(r.ast["components"]) == 2
        assert r.ast["components"][1]["type"] == "Special"
        assert r.ast["components"][1]["kind"] == "EXT"

    def test_mult_three_components_with_ext(self) -> None:
        prose = compile_method(_program({
            "type": "Compound", "combinator": "Mult",
            "components": [
                {"type": "Atomic", "dist": "F", "domain": "R", "value": 5.0},
                {"type": "Atomic", "dist": "F", "domain": "I", "value": 30.0, "time_unit": "s"},
                {"type": "Special", "kind": "EXT"},
            ],
        })).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["combinator"] == "Mult"
        assert len(r.ast["components"]) == 3


class TestGoNoGoExtraction:
    def test_gonogo_minimal(self) -> None:
        prose = compile_method(_program({
            "type": "TrialBased", "trial_type": "GoNoGo",
            "responseWindow": 5.0, "responseWindowUnit": "s",
            "consequence": {"type": "Special", "kind": "CRF"},
            "incorrect": {"type": "Special", "kind": "EXT"},
            "falseAlarm": {"type": "Special", "kind": "EXT"},
            "ITI": 10.0, "ITI_unit": "s",
        })).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["type"] == "TrialBased"
        assert r.ast["trial_type"] == "GoNoGo"
        assert r.ast["responseWindow"] == 5.0
        assert r.ast["ITI"] == 10.0

    def test_gonogo_with_vi_consequence(self) -> None:
        prose = compile_method(_program({
            "type": "TrialBased", "trial_type": "GoNoGo",
            "responseWindow": 5.0, "responseWindowUnit": "s",
            "consequence": {
                "type": "Atomic", "dist": "V", "domain": "I",
                "value": 30.0, "time_unit": "s",
            },
            "incorrect": {"type": "Special", "kind": "EXT"},
            "falseAlarm": {"type": "Special", "kind": "EXT"},
            "ITI": 10.0, "ITI_unit": "s",
        })).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["trial_type"] == "GoNoGo"
        assert r.ast["consequence"]["type"] == "Atomic"
        assert r.ast["consequence"]["value"] == 30.0


class TestOverlayExtraction:
    def test_overlay_conc_baseline(self) -> None:
        prose = compile_method(_program({
            "type": "Compound", "combinator": "Overlay",
            "components": [
                {
                    "type": "Compound", "combinator": "Conc",
                    "components": [
                        {"type": "Atomic", "dist": "V", "domain": "I",
                         "value": 60.0, "time_unit": "s"},
                        {"type": "Atomic", "dist": "V", "domain": "I",
                         "value": 180.0, "time_unit": "s"},
                    ],
                },
                {"type": "Atomic", "dist": "F", "domain": "R", "value": 1.0},
            ],
        })).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["combinator"] == "Overlay"


class TestAdjustingExtraction:
    def test_adj_delay(self) -> None:
        prose = compile_method(_program({
            "type": "AdjustingSchedule",
            "adj_target": "delay",
            "adj_start": {"value": 10.0, "time_unit": "s"},
            "adj_step": {"value": 1.0, "time_unit": "s"},
            "adj_min": None,
            "adj_max": None,
        })).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["type"] == "AdjustingSchedule"
        assert r.ast["adj_target"] == "delay"
        assert r.ast["adj_start"]["value"] == 10.0

    def test_adj_ratio_with_bounds(self) -> None:
        prose = compile_method(_program({
            "type": "AdjustingSchedule",
            "adj_target": "ratio",
            "adj_start": {"value": 5},
            "adj_step": {"value": 1},
            "adj_min": {"value": 1},
            "adj_max": {"value": 50},
        })).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["adj_target"] == "ratio"
        assert r.ast["adj_max"] is not None
        assert r.ast["adj_max"]["value"] == 50


class TestInterlockingExtraction:
    def test_interlock_standard(self) -> None:
        prose = compile_method(_program({
            "type": "InterlockingSchedule",
            "interlock_R0": 300,
            "interlock_T": {"value": 10.0, "time_unit": "min"},
        })).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["type"] == "InterlockingSchedule"
        assert r.ast["interlock_R0"] == 300
        assert r.ast["interlock_T"]["time_unit"] == "min"


class TestEscapeExtraction:
    def test_escape_basic(self) -> None:
        prose = compile_method(_program({
            "type": "AversiveSchedule",
            "kind": "Escape",
            "params": {
                "SafeDuration": {"value": 5.0, "time_unit": "s"},
            },
        })).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["type"] == "AversiveSchedule"
        assert r.ast["kind"] == "Escape"
        assert r.ast["params"]["SafeDuration"]["value"] == 5.0

    def test_escape_with_max_shock(self) -> None:
        prose = compile_method(_program({
            "type": "AversiveSchedule",
            "kind": "Escape",
            "params": {
                "SafeDuration": {"value": 5.0, "time_unit": "s"},
                "MaxShock": {"value": 60.0, "time_unit": "s"},
            },
        })).procedure
        r = extract_schedule(prose)
        assert r is not None
        assert r.ast["kind"] == "Escape"
        assert "MaxShock" in r.ast["params"]
        assert r.ast["params"]["MaxShock"]["value"] == 60.0
