# contingency-procedure2dsl

:gb: [English README](README.md)

学術論文の Method セクションから [contingency-dsl](https://github.com/OperantKit/contingency-dsl) AST を抽出する。

[contingency-dsl2procedure](https://github.com/OperantKit/contingency-dsl2procedure)（DSL → 論文）の逆方向。

## インストール

```bash
pip install git+https://github.com/OperantKit/contingency-procedure2dsl
```

ルールベースの抽出器は実行時の依存を持たない。任意の LLM フォールバックには `llm` extra（`anthropic`）が要る:

```bash
pip install "contingency-procedure2dsl[llm] @ git+https://github.com/OperantKit/contingency-procedure2dsl"
```

## 30 秒で動く例

Method 節の段落から、スケジュール・切替遅延 (COD)・被験体のアノテーションを抽出する（ルールベース。API キーもネットワークも不要）:

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

program = report.to_program()  # Program の AST dict: schedule + param_decls + program_annotations
print(program["schedule"] == schedule.ast)  # True

print(extract_schedule("The procedure was similar to that of Experiment 1."))  # None
```

Program の dict は contingency-dsl の AST スキーマに従う。DSL のソースとして書き出すには [contingency-dsl-py](https://github.com/OperantKit/contingency-dsl-py) の `contingency_dsl.from_dict` と `format_program` に渡す（`pip install contingency-dsl-py`）。この例では `@species("rat")` … `COD = 2s` と `Conc(VI30s, VI60s)` が得られる。スケジュールを動かすには [contingency-py](https://github.com/OperantKit/contingency-py) を使う（`pip install contingency-py`）。

## 自作の 50 行では足りない理由

`VI 30-s` を拾う正規表現は、Method 節が述べているそれ以外の情報（スケジュールの組み合わせ方、切替遅延、被験体、そのスケジュールがどのフェーズに属するか）を落とす:

- **順序付きの抽出器.** `extract_all` はレスポンデント手続き、試行型の手続き（見本合わせ、go/no-go）、二次スケジュール、修飾子（DRL, DRH, DRO, PR, Lag, パーセンタイル）、嫌悪性の手続き（Sidman 型回避、弁別回避、逃避）、罰の重畳、調整スケジュールとインターロッキングスケジュール、複合スケジュール、Limited Hold、単一スケジュールの順に試し、確信度が最も高い候補を採る。Limited Hold・タイムアウト・反応コストは末端のスケジュールに付与する。
- **パラメータとアノテーション.** 切替遅延 (COD)・Limited Hold・ブラックアウト・強化遅延・固定比率の切替要件 (FRCO) は `ParamDecl` ノードになる。5 つのアノテーション抽出器（subjects, apparatus, measurement, procedure, component）が `@species`・`@n`・`@history`・`@operandum` などを作り、被験体についての重複した記述は 1 つの値にまとめる。
- **生成器との往復変換.** 往復変換のテストモジュールにある 109 件のテストが、AST を [contingency-dsl2procedure](https://github.com/OperantKit/contingency-dsl2procedure) で Method 本文に書き出し、このパッケージで元に戻せることを確かめている。
- **フェーズと実験.** `extract_phase_sequence` は「ベースライン／消去」のような本文を `PhaseSequence` に分け、`extract_paper` は複数実験の論文を見出しごとの `Experiment` を持つ `Paper` に分ける。英語と日本語の見出しを認識する。
- **確信度と位置.** 結果にはすべて確信度・一致した本文・文字位置が付くので、何を読んだかを査読者が確かめられる。どのパターンにも当たらない本文はスケジュールを推測せず `None` を返す。
- **任意の LLM フォールバック.** `extract_all_with_fallback` は、ルールベースでスケジュールが見つからないか確信度が閾値（既定 0.5）未満のときだけ Anthropic API を呼ぶ。`llm` extra と API キーが要る。応答の解釈はスタブのクライアントで試験しており、実際の API に対しては試験していない。

## 使い方

```python
from contingency_procedure2dsl import extract_all_with_fallback, extract_schedule

text = "Responses were reinforced under a concurrent VI 30-s VI 60-s schedule."
result = extract_schedule(text)
print(result.ast)
# {'type': 'Compound', 'combinator': 'Conc', 'components': [{'type': 'Atomic', 'dist': 'V', 'domain': 'I', 'value': 30.0, 'time_unit': 's'}, {'type': 'Atomic', 'dist': 'V', 'domain': 'I', 'value': 60.0, 'time_unit': 's'}]}
print(result.confidence)  # 0.85

# ここでは Layer 1 の確信度が十分なので、LLM フォールバックは呼ばれない。
report = extract_all_with_fallback(text)
print(report.primary_schedule.ast == result.ast)  # True
```

ルールで読めない本文は、`extract_all_with_fallback(text)`（または `contingency_procedure2dsl.extractors.llm` の `extract_schedule_llm(text)`）が Anthropic API に送る。これには `pip install "contingency-procedure2dsl[llm] @ git+https://github.com/OperantKit/contingency-procedure2dsl"` と環境変数 `ANTHROPIC_API_KEY`（または `api_key=`）が要る。

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

