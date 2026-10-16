# contingency-procedure2dsl

:jp: [日本語版 README](README.ja.md)

Extract [contingency-dsl](https://github.com/OperantKit/contingency-dsl) AST from academic paper Method sections.

Reverse of [contingency-dsl2procedure](https://github.com/OperantKit/contingency-dsl2procedure) (DSL → paper).

## Install

```bash
pip install git+https://github.com/OperantKit/contingency-procedure2dsl
```

The rule-based extractor has no runtime dependencies. The optional LLM fallback needs the `llm` extra (`anthropic`):

```bash
pip install "contingency-procedure2dsl[llm] @ git+https://github.com/OperantKit/contingency-procedure2dsl"
```

## 30-second example

Extract the schedule, the changeover delay, and subject annotations from a Method-section paragraph (rule-based; no API key, no network):

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

The Program dict follows the contingency-dsl AST schema. To print it as DSL source, pass it to `contingency_dsl.from_dict` and `format_program` from [contingency-dsl-py](https://github.com/OperantKit/contingency-dsl-py) (`pip install contingency-dsl-py`); for this example that gives `@species("rat")` … `COD = 2s` and `Conc(VI30s, VI60s)`. To run the schedule, use [contingency-py](https://github.com/OperantKit/contingency-py) (`pip install contingency-py`).

## Why not a 50-line hand-written regex?

A regular expression that finds `VI 30-s` loses everything else a Method section states — how schedules are combined, the changeover delay, who the subjects were, and which phase a schedule belongs to:

- **Ordered extractors.** `extract_all` tries respondent procedures, trial-based procedures (matching-to-sample, go/no-go), second-order schedules, modifiers (DRL, DRH, DRO, PR, Lag, percentile), aversive procedures (Sidman avoidance, discriminated avoidance, escape), punishment overlays, adjusting and interlocking schedules, compound schedules, limited hold, and atomic schedules in that order, and keeps the highest-confidence candidate. Limited hold, timeout, and response cost are attached to the leaf schedule.
- **Parameters and annotations.** Changeover delay, limited hold, blackout, reinforcement delay, and fixed-ratio changeover become `ParamDecl` nodes; five annotation extractors (subjects, apparatus, measurement, procedure, component) produce `@species`, `@n`, `@history`, `@operandum`, and similar annotations, with duplicate subject facts collapsed to one value.
- **Round trip with the generator.** 109 tests in the round-trip modules write an AST as Method text with [contingency-dsl2procedure](https://github.com/OperantKit/contingency-dsl2procedure) and check that this package recovers it.
- **Phases and experiments.** `extract_phase_sequence` splits "baseline / extinction" style text into a `PhaseSequence`, and `extract_paper` splits multi-experiment papers into a `Paper` with one `Experiment` per heading. English and Japanese headings are recognized.
- **Confidence and spans.** Every result carries a confidence score, the matched source text, and its character span, so a reviewer can check what was read; text that matches no pattern returns `None` instead of a guessed schedule.
- **Optional LLM fallback.** `extract_all_with_fallback` calls the Anthropic API only when no rule-based schedule is found or its confidence is below a threshold (default 0.5). It needs the `llm` extra and an API key; the response parsing is tested with a stubbed client, not against the live API.

## Usage

```python
from contingency_procedure2dsl import extract_all_with_fallback, extract_schedule

text = "Responses were reinforced under a concurrent VI 30-s VI 60-s schedule."
result = extract_schedule(text)
print(result.ast)
# {'type': 'Compound', 'combinator': 'Conc', 'components': [{'type': 'Atomic', 'dist': 'V', 'domain': 'I', 'value': 30.0, 'time_unit': 's'}, {'type': 'Atomic', 'dist': 'V', 'domain': 'I', 'value': 60.0, 'time_unit': 's'}]}
print(result.confidence)  # 0.85

# Layer 1 is confident enough here, so the LLM fallback is not called.
report = extract_all_with_fallback(text)
print(report.primary_schedule.ast == result.ast)  # True
```

For text the rules cannot read, `extract_all_with_fallback(text)` (or `extract_schedule_llm(text)` from `contingency_procedure2dsl.extractors.llm`) sends the text to the Anthropic API. This requires `pip install "contingency-procedure2dsl[llm] @ git+https://github.com/OperantKit/contingency-procedure2dsl"` and the `ANTHROPIC_API_KEY` environment variable (or `api_key=`).

## Coverage

Layer 1 (rule-based) covers the full [contingency-dsl](https://github.com/OperantKit/contingency-dsl) surface area for constructs that [contingency-dsl2procedure](https://github.com/OperantKit/contingency-dsl2procedure) emits as non-ambiguous prose:

- Atomic schedules: F/V/R × R/I/T (FR, VR, RR, FI, VI, RI, FT, VT, RT)
- Special: EXT, CRF
- Compound combinators: Conc, Alt, Conj, Chain, Tand, Mult, Mix, Overlay, Interpolate (with EXT/CRF components recognized)
- Modifier: DRL, DRH, DRO, PR, Lag, Pctl (English and Japanese variants)
- SecondOrder
- Aversive: Sidman, DiscrimAv (fixed / response-terminated), Escape
- Stateful: AdjustingSchedule (delay / ratio / amount), InterlockingSchedule
- TrialBased: MTS (identity / arbitrary), GoNoGo
- Respondent: Pair variants, Extinction, Contingency, CS-only, US-only
- Schedule-level: limitedHold, timeout, responseCost
- Parameters: COD, LH, BO, RD, FRCO
- Annotations: subjects, apparatus, measurement, procedure, component

Known limitations (paper-side prose is ambiguous or truncates a component; reader cannot recover what is not present in the text):

- Compound schedules with a stateful component (e.g., `Mult(Interlocking, EXT)`): the stateful component's prose slot is empty in the current paper output.
- Compound schedules where one component is an aversive primitive or a let-binding identifier: the component is omitted from prose.
- Deeply nested compounds (depth ≥ 3): the flattened prose is structurally ambiguous and recovered as a flat compound of atomics.
- Let-binding references (`let av = Sidman(...); Chain(FR 10, av)`): paper inlines the bound schedule, losing the identifier reference.

