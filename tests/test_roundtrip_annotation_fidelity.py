"""Annotation fidelity across reader → compile_method → reader.

Each annotation the reader extracts from a Method section must either be
written back by compile_method in a form the reader picks up again, or not
be extracted in the first place (when the source phrase does not name the
thing the annotation claims). The texts below are invented.
"""

import json

from contingency_dsl2procedure import compile_method
from contingency_procedure2dsl import extract_all


def _anns(text: str) -> list[dict]:
    return [r.ast for r in extract_all(text).annotations]


def _keyword_values(text: str, keyword: str) -> list:
    return [a.get("positional") for a in _anns(text) if a.get("keyword") == keyword]


def _program_annotations(text: str) -> list[str]:
    program = extract_all(text).to_program()
    return [
        json.dumps(a, sort_keys=True)
        for a in program.get("program_annotations") or []
    ]


class TestSdExtraction:
    def test_quantifier_phrase_is_not_a_stimulus(self) -> None:
        text = "The timers ran only in the presence of each color."
        assert _keyword_values(text, "sd") == []

    def test_numeral_and_another_are_not_stimuli(self) -> None:
        text = (
            "Pecks were reinforced in the presence of one stimulus but never "
            "in the presence of another."
        )
        assert _keyword_values(text, "sd") == []

    def test_role_abbreviation_is_not_a_stimulus(self) -> None:
        text = "Responding became more frequent in the presence of SD."
        assert _keyword_values(text, "sd") == []

    def test_trailing_function_word_is_dropped(self) -> None:
        text = "Pecks in the presence of trees and of other slides were counted."
        assert _keyword_values(text, "sd") == ["trees"]

    def test_named_stimulus_is_kept(self) -> None:
        text = "Pecks were reinforced in the presence of red light."
        assert _keyword_values(text, "sd") == ["red_light"]


class TestSubjectExtraction:
    def test_adult_modifying_a_nonhuman_species_is_not_a_population(self) -> None:
        text = "Four adult male White Carneaux pigeons served as subjects."
        assert _keyword_values(text, "population") == []
        assert "pigeon" in _keyword_values(text, "species")

    def test_adult_before_two_strain_names_is_not_a_population(self) -> None:
        text = "Ten adult White Carneaux and King pigeons served as subjects."
        assert _keyword_values(text, "population") == []

    def test_human_population_is_still_extracted(self) -> None:
        text = "Six adults served as participants."
        assert _keyword_values(text, "population") == ["adults"]

    def test_chamber_descriptor_is_not_a_strain(self) -> None:
        text = (
            "Sessions were run on the center key of a three-key pigeon "
            "chamber. Three pigeons served as subjects."
        )
        assert "three-key" not in _keyword_values(text, "strain")


class TestCompileMethodWritesBack:
    """ast1 annotations survive compile_method → re-extraction verbatim."""

    _TEXT = (
        "Four White Carneaux pigeons served as subjects. "
        "Responses were reinforced under a variable-interval (VI) 30-s schedule. "
        "Interval values were derived from Fleshler and Hoffman (1962). "
        "Pecks were reinforced in the presence of red light and never in the "
        "presence of green light. "
        "A 5-min warm-up period preceded each session."
    )

    def _roundtrip(self) -> tuple[list[str], list[str]]:
        ast1 = extract_all(self._TEXT).to_program()
        compiled = compile_method(ast1).to_text()
        ast2 = extract_all(compiled).to_program()
        dump = lambda p: [  # noqa: E731
            json.dumps(a, sort_keys=True) for a in p.get("program_annotations") or []
        ]
        return dump(ast1), dump(ast2)

    def test_sd_algorithm_and_warmup_are_present_in_ast1(self) -> None:
        ast1, _ = self._roundtrip()
        keywords = [json.loads(a)["keyword"] for a in ast1]
        assert keywords.count("sd") == 2
        assert "algorithm" in keywords
        assert "warmup" in keywords

    def test_program_annotations_identical_after_roundtrip(self) -> None:
        ast1, ast2 = self._roundtrip()
        assert ast1 == ast2
