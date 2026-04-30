"""Tests for subject-annotation extraction edge cases.

Covers behaviours added to make the round-trip harness converge:

- @species/@strain false-positive filtering
- Human-participant extraction with population descriptors
- Proper-noun strain shift ("Carneau pigeon" → @strain("Carneau"))
- Species-only fallback ("rat served as subjects" → @species("rat"))
- Dedup of singleton keywords across multiple matches
"""

from __future__ import annotations

from contingency_procedure2dsl import extract_all
from contingency_procedure2dsl.extractors.annotations import (
    extract_subject_annotations,
)


def _kws(text: str) -> set[str]:
    return {r.ast["keyword"] for r in extract_subject_annotations(text)}


def _items(text: str) -> list[tuple[str, object]]:
    return [
        (r.ast["keyword"], r.ast.get("positional"))
        for r in extract_subject_annotations(text)
    ]


# --- false-positive filtering ------------------------------------------------


def test_imagine_a_rat_does_not_emit_strain():
    """Generic prose like 'Imagine a rat' must not produce @strain('a')."""
    items = _items("Imagine a rat in a chamber.")
    strain_values = [v for k, v in items if k == "strain"]
    assert "a" not in strain_values
    assert "an" not in strain_values


def test_for_a_cold_rat_does_not_emit_strain():
    items = _items("for a cold rat in a refrigerator")
    strain_values = [v for k, v in items if k == "strain"]
    # "cold" is in the stopword list, must not slip through.
    assert "cold" not in strain_values


def test_mouse_click_not_treated_as_species():
    items = _items("mouse clicks on these boxes indicated participants' choices")
    # Computer mouse must not become @species("mouse").
    assert ("species", "mouse") not in items


# --- proper-noun strain shift ------------------------------------------------


def test_carneau_pigeon_promotes_strain():
    items = _items("Carneau pigeon served as subjects.")
    assert ("species", "pigeon") in items
    assert ("strain", "Carneau") in items


def test_wistar_rat_promotes_strain():
    items = _items("Wistar rat used in this study.")
    assert ("species", "rat") in items
    assert ("strain", "Wistar") in items


def test_sentence_initial_pigeon_does_not_self_promote_to_strain():
    """'Pigeon served as subjects.' must not produce @strain('Pigeon')."""
    items = _items("Pigeon served as subjects.")
    strain_values = [v for k, v in items if k == "strain"]
    assert "Pigeon" not in strain_values
    # @species should still be detected via _SPECIES_ONLY_PATTERN.
    assert ("species", "pigeon") in items


# --- species-only fallback ---------------------------------------------------


def test_rat_served_as_subjects_emits_species_only():
    items = _items("rat served as subjects.")
    assert ("species", "rat") in items
    assert all(k != "strain" for k, v in items)


def test_pigeons_served_as_subjects():
    items = _items("Pigeons served as subjects.")
    assert ("species", "pigeon") in items


# --- human extraction --------------------------------------------------------


def test_five_children_extracts_human_population_n():
    items = _items("Five children participated in the experiment.")
    assert ("species", "human") in items
    assert ("population", "children") in items
    assert ("n", 5) in items


def test_typically_developing_children_descriptor_passes():
    items = _items(
        "Three typically developing children attended the program."
    )
    assert ("species", "human") in items
    assert ("population", "children") in items


def test_generic_the_participants_does_not_extract():
    """Generic prose 'the participants' must not produce @species('human')."""
    items = _items("The participants were observed in the classroom.")
    species = [v for k, v in items if k == "species" and v == "human"]
    assert species == []


# --- dedup -------------------------------------------------------------------


def test_singleton_dedup_keeps_first_species():
    """Multiple cross-species mentions collapse to first."""
    text = (
        "Five rats served as subjects. The pigeons in Skinner (1938) "
        "demonstrated similar effects."
    )
    report = extract_all(text)
    species_anns = [a.ast for a in report.annotations if a.ast["keyword"] == "species"]
    assert len(species_anns) == 1
    # First detected mention wins; in this prose 'rats' is detected first
    # (with @n=5) — pigeons mention has no count and arrives later.
    assert species_anns[0]["positional"] == "rat"


def test_singleton_dedup_keeps_first_n():
    """Multiple @n values collapse to the first."""
    text = "Five rats served as subjects. Three rats served as control."
    report = extract_all(text)
    n_anns = [a.ast for a in report.annotations if a.ast["keyword"] == "n"]
    assert len(n_anns) == 1
    assert n_anns[0]["positional"] == 5
