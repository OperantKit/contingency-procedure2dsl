# contingency-procedure2dsl

:gb: [English README](README.md)

学術論文の Method セクションから [contingency-dsl](https://github.com/OperantKit/contingency-dsl) AST を抽出する。

[contingency-dsl2procedure](https://github.com/OperantKit/contingency-dsl2procedure)（DSL → 論文）の逆方向。

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

# 曖昧なテキストへの LLM フォールバック（オプトイン: pip install contingency-procedure2dsl[llm]）
from contingency_procedure2dsl import extract_schedule_llm
result = extract_schedule_llm(ambiguous_text, model="claude-sonnet-4-6")
```

## カバレッジ

Layer 1（ルールベース）は、[contingency-dsl2procedure](https://github.com/OperantKit/contingency-dsl2procedure) が
曖昧さなく散文として emit する限り、[contingency-dsl](https://github.com/OperantKit/contingency-dsl) の
全てのサーフェスをカバーする:

- Atomic スケジュール: F/V/R × R/I/T（FR, VR, RR, FI, VI, RI, FT, VT, RT）
- Special: EXT, CRF
- 複合スケジュール: Conc, Alt, Conj, Chain, Tand, Mult, Mix, Overlay, Interpolate
  （構成要素としての EXT/CRF も認識）
- Modifier: DRL, DRH, DRO, PR, Lag, Pctl（英語・日本語変種）
- SecondOrder
- Aversive: Sidman, DiscrimAv（fixed / response-terminated）, Escape
- Stateful: AdjustingSchedule（delay / ratio / amount）, InterlockingSchedule
- TrialBased: MTS（identity / arbitrary）, GoNoGo
- Respondent: Pair 各種, Extinction, Contingency, CS-only, US-only
- スケジュール属性: limitedHold, timeout, responseCost
- パラメータ: COD, LH, BO, RD, FRCO
- アノテーション: subjects, apparatus, measurement, procedure, component

既知の制限（paper 側の散文が曖昧、またはコンポーネントを省略するため、
reader では元の AST を復元できない）:

- 構成要素に stateful スケジュールを持つ複合（例: `Mult(Interlocking, EXT)`）:
  stateful 部分の散文表現が現状では空となる。
- 構成要素にアヴァーシブ primitive あるいは let-binding 識別子を持つ複合:
  当該コンポーネントが散文から省略される。
- 深さ 3 以上のネスト複合: 平坦化された散文から構造を一意に復元できず、
  フラットな atomic 複合として回収される。
- Let-binding 参照（`let av = Sidman(...); Chain(FR 10, av)`）:
  paper が束縛を inline 展開するため識別子参照が失われる。

