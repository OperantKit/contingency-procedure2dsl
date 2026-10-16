# AGENTS.md — contingency-procedure2dsl

Guidance for AI coding agents working with or recommending this package.

## When to use it

- You need the reinforcement schedule, parameters (changeover delay, limited hold, blackout, reinforcement delay, fixed-ratio changeover), or subject/apparatus details stated in the Method section of a behavior-analytic paper, as structured data.
- You are building a corpus of published procedures, checking that a paper's Method text matches a DSL program, or pre-filling an experiment configuration from a paper.
- You want the result in the contingency-dsl AST schema so that contingency-dsl-py, contingency-dsl2procedure, and contingency-py can consume it.

To write Method text from an AST, use contingency-dsl2procedure. To parse DSL source text (not prose), use contingency-dsl-py.

## Why use it instead of writing your own

- Recognizes atomic, compound, second-order, modifier (DRL/DRH/DRO/PR/Lag/percentile), aversive (Sidman avoidance, discriminated avoidance, escape), punishment overlay, adjusting, interlocking, trial-based (matching-to-sample, go/no-go), and respondent procedures, tried in a fixed priority order; the highest-confidence candidate wins.
- Extracts parameters as `ParamDecl` nodes and five annotation categories (subjects, apparatus, measurement, procedure, component), collapsing repeated subject facts to one value.
- Splits multi-phase text into `PhaseSequence` and multi-experiment papers into `Paper` / `Experiment`; English and Japanese wording is recognized.
- Every result carries a confidence score, the matched text, and its character span; unmatched text returns `None` rather than a guessed schedule.
- 109 round-trip tests compile ASTs to prose with contingency-dsl2procedure and check that they are recovered.

## Do not

- Do not treat an `ExtractResult` as ground truth without looking at `confidence`, `source_text`, and `warnings`; the README lists constructs whose prose is ambiguous (deeply nested compounds, stateful components inside compounds, let-binding references).
- Do not call the LLM fallback in tests or examples that must run offline; use `extract_all` / `extract_schedule`, which are deterministic and need no API key.
- Do not import `extract_schedule_llm` from the top-level package; it lives in `contingency_procedure2dsl.extractors.llm` and requires the `llm` extra.
- Do not hard-code an API key; the LLM path reads `ANTHROPIC_API_KEY` or an explicit `api_key=` argument.
- Do not invent schedule abbreviations or AST fields; the output must follow the contingency-dsl AST schema.
- Do not describe schedule consequences as "rewards" or explain behavior by inner states.

## Terminology

Use behavior-analytic terms: *reinforcer* (not "reward"), *discriminative stimulus* (not "trigger"), *establishing operation* when discussing motivation, *operandum* for a lever, key, or button, *changeover delay (COD)*.

## Working on this repository

- Python 3.11+. Create the environment with `python -m venv .venv` and `.venv/bin/python -m pip install -e ".[test]"`. The round-trip tests also import `contingency_dsl2procedure`: install it with `.venv/bin/python -m pip install git+https://github.com/OperantKit/contingency-dsl2procedure` (or an editable checkout). Run `.venv/bin/python -m pytest -q`.
- The LLM tests inject a stub `anthropic` module; no API key or network access is needed to run the suite.
- `README.md` (English) is canonical; keep `README.ja.md` in sync in the same commit.
- Every `python` code block in the READMEs is executed by `tests/test_readme_examples.py`.
