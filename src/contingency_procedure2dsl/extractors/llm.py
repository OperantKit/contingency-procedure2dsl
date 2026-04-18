"""Layer 2: LLM-based extraction (opt-in).

Requires: pip install contingency-procedure2dsl[llm]

Uses Claude API to extract schedule information from ambiguous or
non-standard Method section text that Layer 1 regex patterns cannot handle.

Example:
    "The procedure was similar to that described by Herrnstein (1961),
     except that the reinforcement rates were adjusted to maintain
     a 2:1 ratio across the two alternatives."
    → Layer 1 extracts nothing; Layer 2 infers Conc(VI, VI) with 2:1 ratio.
"""

from __future__ import annotations

import json

from ..result import ExtractResult

# Grammar excerpt for the prompt (compact form, not the full EBNF)
_GRAMMAR_EXCERPT = """\
contingency-dsl is a text DSL for declaring reinforcement schedules.

Atomic schedules: {F|V|R}{R|I|T} value [time_unit]
  Examples: FR5, VI30s, VT20-s, RR10
  Distribution: F=fixed, V=variable, R=random
  Domain: R=ratio, I=interval, T=time

Special: EXT (extinction), CRF (continuous reinforcement)

Compound: Conc(A, B) | Chain(A, B) | Mult(A, B) | Mix(A, B) | Tand(A, B) | Alt(A, B) | Conj(A, B)
  Params: COD=2s (changeover delay), BO=5s (blackout)

Modifiers: DRL5s, DRH10, DRO20s, PR(linear, start=1, increment=5), Lag5

Second-order: FR5(FI30s) = 5 completions of FI30s unit

Aversive: Sidman(SSI=5s, RSI=20s), DiscrimAv(CSUSInterval=10s, ITI=30s, mode=fixed)

LimitedHold: FI30s LH5s

Annotations (program-level):
  @species("rat") @strain("Sprague-Dawley") @n(6)
  @deprivation(hours=23, target="food") @history("naive")
  @chamber("Med Associates", model="ENV-007") @hardware("MED-PC IV")
  @operandum("left_lever", component=1) @sd("red_light", component=1)
  @reinforcer("food pellet") @session_end(rule="first", time=60min, reinforcers=60)
  @steady_state(window_sessions=5, max_change_pct=10, measure="rate")
  @baseline(pre_training_sessions=3) @algorithm("fleshler-hoffman", n=20)
"""

_SYSTEM_PROMPT = """\
You are a behavioral science expert who reads JEAB/JABA paper Method sections \
and extracts the procedure into contingency-dsl JSON AST format.

""" + _GRAMMAR_EXCERPT + """

Given a Method section text, extract the schedule structure and annotations \
as a JSON object conforming to the contingency-dsl AST schema.

Rules:
1. Output ONLY valid JSON — no markdown, no explanation.
2. Use the exact field names from the schema: type, dist, domain, value, time_unit, combinator, components, etc.
3. If information is ambiguous or missing, use your best inference and set "confidence" to a value < 1.0.
4. Include "confidence" (0.0-1.0) as a top-level field indicating overall certainty.
5. Include "warnings" as a list of strings noting any assumptions or ambiguities.

Output format:
{
  "program": { <Program AST dict> },
  "confidence": 0.85,
  "warnings": ["Assumed VI schedule based on 'variable' mention"]
}
"""


def extract_schedule_llm(
    text: str,
    *,
    model: str = "claude-sonnet-4-6",
    api_key: str | None = None,
    max_tokens: int = 2048,
) -> ExtractResult:
    """Extract schedule using LLM for ambiguous text.

    Args:
        text: Method section text (or fragment).
        model: Claude model ID.
        api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var).
        max_tokens: Maximum tokens for the response.

    Returns:
        ExtractResult with AST dict and confidence score.

    Raises:
        ImportError: If anthropic package is not installed.
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "LLM extraction requires the anthropic package. "
            "Install with: pip install contingency-procedure2dsl[llm]"
        )

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Extract the schedule from this Method section:\n\n{text}"},
        ],
    )

    raw = message.content[0].text
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3]

    parsed = json.loads(raw)

    program = parsed.get("program", parsed)
    confidence = parsed.get("confidence", 0.7)
    warnings = tuple(parsed.get("warnings", []))

    return ExtractResult(
        ast=program,
        confidence=confidence,
        span=(0, len(text)),
        source_text=text,
        warnings=warnings,
    )


def extract_all_llm(
    text: str,
    *,
    model: str = "claude-sonnet-4-6",
    api_key: str | None = None,
) -> ExtractResult:
    """Extract full program (schedule + annotations) using LLM.

    This is the comprehensive LLM extraction — it attempts to recover
    the complete Program AST including all annotations.

    For schedule-only extraction, use extract_schedule_llm().
    """
    return extract_schedule_llm(text, model=model, api_key=api_key)
