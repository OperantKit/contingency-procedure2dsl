# contingency-procedure2dsl

:jp: [日本語版 README](README.ja.md)

contingency-procedure2dsl reads the Method section of a behavior-analytic paper, in English or Japanese, and extracts the schedule of reinforcement, its parameters (such as the changeover delay), and details of the subjects and apparatus as structured data in the [contingency-dsl](https://github.com/OperantKit/contingency-dsl) format. Use it to build a collection of published procedures, to check that a paper's Method text matches a program, or to start an experiment configuration from a paper. It is the reverse of [contingency-dsl2procedure](https://github.com/OperantKit/contingency-dsl2procedure), which writes Method text from a schedule, within [OperantKit](https://github.com/OperantKit).

**In short**

- Rule-based: no API key and no network, and the same text always gives the same result.
- Every result carries a confidence score and the exact passage it was read from, so you can check what was read.
- Text it cannot read returns `None` instead of a guessed schedule.

## Installation

Python 3.11 or newer. The package is not on PyPI yet; install it from GitHub:

```bash
pip install git+https://github.com/OperantKit/contingency-procedure2dsl
```

The rule-based extractor has no dependencies. The optional fallback that sends unreadable text to a language model needs the `llm` extra, which installs the `anthropic` client:

```bash
pip install "contingency-procedure2dsl[llm] @ git+https://github.com/OperantKit/contingency-procedure2dsl"
```

## Example

Extract the schedule, the changeover delay, and the subject details from a Method-section passage:

```python
from contingency_procedure2dsl import extract_all, extract_schedule

text = (
    "Four experimentally naive male Long-Evans rats served as subjects. "
    "Responses on the left and right levers were reinforced under a concurrent "
    "VI 30-s VI 60-s schedule with a 2-s changeover delay."
)
report = extract_all(text)
schedule = report.primary_schedule
print(schedule.ast["combinator"])  # Conc
print([(c["dist"] + c["domain"], c["value"]) for c in schedule.ast["components"]])  # [('VI', 30.0), ('VI', 60.0)]
print(schedule.source_text)  # concurrent VI 30-s VI 60-s schedule with a 2-s changeover delay
print([(p.ast["name"], p.ast["value"]) for p in report.params])  # [('COD', 2.0)]
print([(a.ast["keyword"], a.ast["positional"]) for a in report.annotations])
# [('species', 'rat'), ('strain', 'Long-Evans'), ('n', 4), ('history', 'naive')]

program = report.to_program()  # Program AST dict: schedule + param_decls + program_annotations
print(program["schedule"] == schedule.ast)  # True

print(extract_schedule("The procedure was similar to that of Experiment 1."))  # None
```

For this passage the schedule has confidence `0.85` and was read from characters 130–193 (`schedule.confidence`, `schedule.span`). The program dictionary follows the contingency-dsl AST schema; to print it as contingency-dsl text, pass it to `from_dict` and `format_program` from [contingency-dsl-py](https://github.com/OperantKit/contingency-dsl-py), and to run it, use [contingency-py](https://github.com/OperantKit/contingency-py).

## What it reads

- Atomic schedules FR, VR, RR, FI, VI, RI, FT, VT, RT, and EXT and CRF
- Compound schedules: `Conc`, `Alt`, `Conj`, `Chain`, `Tand`, `Mult`, `Mix`, `Overlay`, `Interpolate`
- DRL, DRH, DRO, progressive ratio, lag, and percentile schedules; second-order schedules
- Sidman avoidance, discriminated avoidance (fixed and response-terminated), and escape
- Adjusting schedules (delay, ratio, amount) and interlocking schedules
- Matching-to-sample (identity and arbitrary) and go/no-go
- Respondent procedures: pairing, extinction, contingency, CS-only, US-only
- Limited hold, timeout, and response cost on a schedule
- Parameters: changeover delay, limited hold, blackout, reinforcement delay, fixed-ratio changeover
- Annotations for subjects, apparatus, measurement, procedure, and components (`@species`, `@n`, `@history`, `@operandum`, and others)

`extract_phase_sequence` splits text that describes several phases (for example acquisition and extinction) into a phase sequence, and `extract_paper` splits a paper with several experiments into one entry per experiment. English and Japanese headings and wording are recognized.

## Optional language-model fallback

`extract_all_with_fallback(text)` runs the rules first and sends the text to the Anthropic API only when no schedule is found or its confidence is below a threshold (0.5 by default). It needs the `llm` extra and an API key in the `ANTHROPIC_API_KEY` environment variable (or `api_key=`). The same call on the example passage above does not reach the API, because the rules are confident enough. `extract_schedule_llm` in `contingency_procedure2dsl.extractors.llm` calls the API directly.

## Limitations

A schedule can be recovered only when the prose states it. These constructs are written ambiguously or incompletely by contingency-dsl2procedure, so they are not recovered:

- Compound schedules with a stateful component (for example `Mult(Interlocking, EXT)`): the stateful component is missing from the prose.
- Compound schedules where one component is an aversive procedure or a name bound with `let`: the component is missing from the prose.
- Compounds nested three or more levels deep: the flattened prose is ambiguous and is read back as one flat compound.
- References to `let` bindings (`let av = Sidman(...); Chain(FR 10, av)`): the prose writes the bound schedule out, so the name is lost.

The language-model fallback is tested with a stand-in client, not against the live API. Check `confidence`, `source_text`, and `warnings` before relying on a result.

## For contributors

The round-trip tests also need contingency-dsl2procedure:

```bash
git clone https://github.com/OperantKit/contingency-procedure2dsl
cd contingency-procedure2dsl
python -m venv .venv
.venv/bin/python -m pip install -e . pytest pytest-cov git+https://github.com/OperantKit/contingency-dsl2procedure
.venv/bin/python -m pytest -q
```

The language-model tests use a stand-in `anthropic` module and need no API key. Every `python` block in this README and in `README.ja.md` is run by `tests/test_readme_examples.py`. Notes for AI coding agents are in [AGENTS.md](AGENTS.md).

## Citation and license

Cite this package with [CITATION.cff](CITATION.cff). MIT License; see [LICENSE](LICENSE).
