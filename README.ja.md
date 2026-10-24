# contingency-procedure2dsl

:gb: [English README](README.md)

contingency-procedure2dsl は、行動分析学の論文の方法セクション（Method 節）を英語でも日本語でも読み、強化スケジュール、そのパラメータ（切替遅延など）、被験体と装置の情報を [contingency-dsl](https://github.com/OperantKit/contingency-dsl) の形式の構造化データとして取り出します。公刊された手続きを集めるとき、論文の Method 節がプログラムと一致しているかを確かめるとき、論文から実験の設定を作り始めるときに使います。[OperantKit](https://github.com/OperantKit) の中では、スケジュールから Method 節の文章を書く [contingency-dsl2procedure](https://github.com/OperantKit/contingency-dsl2procedure) の逆の働きをします。

**要点**

- 規則に基づいて読むので、API キーもネットワークも要らず、同じ文章からはいつも同じ結果が出ます。
- どの結果にも確信度と、読み取った元の箇所が付くので、何を読んだかを確かめられます。
- 読めない文章からは、推測したスケジュールではなく `None` が返ります。

## インストール

Python 3.11 以上が必要です。パッケージはまだ PyPI に登録されていないので、GitHub から入れます。

```bash
pip install git+https://github.com/OperantKit/contingency-procedure2dsl
```

規則に基づく抽出には依存パッケージがありません。読めない文章を言語モデルに送る任意の補助機能には `llm` の追加指定が必要で、`anthropic` のクライアントが入ります。

```bash
pip install "contingency-procedure2dsl[llm] @ git+https://github.com/OperantKit/contingency-procedure2dsl"
```

## 例

Method 節の一節から、スケジュール、切替遅延、被験体の情報を取り出します。

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

program = report.to_program()  # Program の AST の dict: schedule + param_decls + program_annotations
print(program["schedule"] == schedule.ast)  # True

print(extract_schedule("The procedure was similar to that of Experiment 1."))  # None
```

この一節では、スケジュールの確信度は `0.85` で、130〜193 文字目から読み取られています（`schedule.confidence`、`schedule.span`）。program の辞書は contingency-dsl の AST スキーマに従います。contingency-dsl のテキストとして出力するには [contingency-dsl-py](https://github.com/OperantKit/contingency-dsl-py) の `from_dict` と `format_program` に渡し、実行するには [contingency-py](https://github.com/OperantKit/contingency-py) を使います。

## 読めるもの

- 単一のスケジュール FR、VR、RR、FI、VI、RI、FT、VT、RT と、EXT・CRF
- 複合スケジュール: `Conc`、`Alt`、`Conj`、`Chain`、`Tand`、`Mult`、`Mix`、`Overlay`、`Interpolate`
- DRL、DRH、DRO、累進比率、ラグ、パーセンタイルの各スケジュールと、二次スケジュール
- Sidman 型回避、弁別回避（固定型と反応終了型）、逃避
- 調整スケジュール（遅延・比率・量）と連動スケジュール
- 見本合わせ（同一見本合わせと恣意的見本合わせ）と go/no-go
- レスポンデントの手続き: 対提示、消去、随伴性、CS のみ、US のみ
- スケジュールに付く制限時間、タイムアウト、反応コスト
- パラメータ: 切替遅延、制限時間、ブラックアウト、強化遅延、固定比率の切替
- 被験体・装置・測定・手続き・成分のアノテーション（`@species`、`@n`、`@history`、`@operandum` など）

`extract_phase_sequence` は複数のフェーズ（例えば獲得と消去）を書いた文章をフェーズの並びに分け、`extract_paper` は複数の実験を含む論文を実験ごとに分けます。英語と日本語の見出しと言い回しを認識します。

## 任意の言語モデルによる補助

`extract_all_with_fallback(text)` はまず規則で読み、スケジュールが見つからないか確信度がしきい値（既定は 0.5）より低いときだけ、文章を Anthropic の API に送ります。`llm` の追加指定と、環境変数 `ANTHROPIC_API_KEY`（または `api_key=`）の API キーが必要です。上の例の一節に同じ呼び出しをしても、規則の確信度が十分なので API には届きません。`contingency_procedure2dsl.extractors.llm` の `extract_schedule_llm` は API を直接呼びます。

## 制限

スケジュールを取り戻せるのは、文章にそれが書かれているときだけです。次の構文は contingency-dsl2procedure が曖昧に、または不完全に書くため、取り戻せません。

- 状態を持つ成分を含む複合スケジュール（例: `Mult(Interlocking, EXT)`）: その成分が文章から抜けています。
- 成分の 1 つが嫌悪性の手続きか、`let` で名前を付けたスケジュールである複合スケジュール: その成分が文章から抜けています。
- 3 段以上入れ子になった複合スケジュール: 平たくした文章が曖昧なので、1 段の複合スケジュールとして読まれます。
- `let` の束縛の参照（`let av = Sidman(...); Chain(FR 10, av)`）: 文章では束縛したスケジュールがそのまま書かれるので、名前が失われます。

言語モデルによる補助のテストは代わりのクライアントで行っていて、実際の API に対しては行っていません。結果を使う前に `confidence`、`source_text`、`warnings` を確かめてください。

## 開発に参加する人へ

往復のテストには contingency-dsl2procedure も必要です。

```bash
git clone https://github.com/OperantKit/contingency-procedure2dsl
cd contingency-procedure2dsl
python -m venv .venv
.venv/bin/python -m pip install -e . pytest pytest-cov git+https://github.com/OperantKit/contingency-dsl2procedure
.venv/bin/python -m pytest -q
```

言語モデルのテストは代わりの `anthropic` モジュールを使うので、API キーは要りません。この README と `README.md` の `python` ブロックは、すべて `tests/test_readme_examples.py` で実行されます。AI のコーディングエージェント向けの説明は [AGENTS.md](AGENTS.md) にあります。

## 引用とライセンス

このパッケージを引用するときは [CITATION.cff](CITATION.cff) を使ってください。MIT License です。[LICENSE](LICENSE) を参照してください。
