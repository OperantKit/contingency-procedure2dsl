# contingency-procedure2dsl

:jp: [日本語版 README](README.ja.md)

Extract [contingency-dsl](https://github.com/OperantKit/contingency-dsl) AST from academic paper Method sections.

Reverse of [contingency-dsl2procedure](https://github.com/OperantKit/contingency-dsl2procedure) (DSL → paper).

```python
from contingency_procedure2dsl import extract_schedule

text = "Responses were reinforced under a concurrent VI 30-s VI 60-s schedule."
result = extract_schedule(text)
print(result.ast)
# {"type": "Compound", "combinator": "Conc", "components": [
#   {"type": "Atomic", "dist": "V", "domain": "I", "value": 30.0, "time_unit": "s"},
#   {"type": "Atomic", "dist": "V", "domain": "I", "value": 60.0, "time_unit": "s"},
# ]}
print(result.confidence)  # 0.95

# LLM fallback for ambiguous text (opt-in: pip install contingency-procedure2dsl[llm])
from contingency_procedure2dsl import extract_schedule_llm
result = extract_schedule_llm(ambiguous_text, model="claude-sonnet-4-6")
```

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

