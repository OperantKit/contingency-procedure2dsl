"""Tests for the LLM Layer-2 extractor.

The ``anthropic`` SDK is not a runtime dependency in this venv; tests
inject a stub ``anthropic`` module into ``sys.modules`` to exercise the
response-parsing branches without making network calls.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any

import pytest

from contingency_procedure2dsl.extractors import llm as llm_module
from contingency_procedure2dsl.extractors.llm import (
    extract_all_llm,
    extract_schedule_llm,
)


# --- Stub anthropic SDK -----------------------------------------------------


@dataclass
class _StubContentBlock:
    text: str


@dataclass
class _StubMessage:
    content: list[_StubContentBlock]


@dataclass
class _StubMessagesAPI:
    response_text: str
    last_call: dict = field(default_factory=dict)

    def create(self, **kwargs: Any) -> _StubMessage:
        self.last_call = kwargs
        return _StubMessage(content=[_StubContentBlock(text=self.response_text)])


class _StubAnthropic:
    """Mimics ``anthropic.Anthropic`` enough for llm.py to call ``messages.create``."""

    last_init_kwargs: dict = {}

    def __init__(self, *, api_key: str | None = None) -> None:
        _StubAnthropic.last_init_kwargs = {"api_key": api_key}
        # ``response_text`` is rebound per-test on the class.
        self.messages = _StubMessagesAPI(response_text=_StubAnthropic._response_text)

    _response_text: str = "{}"


def _install_stub(monkeypatch: pytest.MonkeyPatch, response_text: str) -> None:
    """Inject a fake ``anthropic`` module so ``import anthropic`` succeeds."""
    _StubAnthropic._response_text = response_text
    stub = type(sys)("anthropic")
    stub.Anthropic = _StubAnthropic  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", stub)


# --- ImportError branch -----------------------------------------------------


class TestImportError:
    def test_raises_when_anthropic_missing(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Force ``import anthropic`` to fail even if it were installed.
        monkeypatch.setitem(sys.modules, "anthropic", None)
        with pytest.raises(ImportError, match="pip install"):
            extract_schedule_llm("FR 5 was used.")


# --- API-key passthrough ----------------------------------------------------


class TestAPIKeyPassthrough:
    def test_explicit_api_key_forwarded(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _install_stub(monkeypatch, '{"program": {"type": "Program"}, "confidence": 0.9}')
        extract_schedule_llm("text", api_key="sk-test-123")
        assert _StubAnthropic.last_init_kwargs == {"api_key": "sk-test-123"}

    def test_no_api_key_uses_default_constructor(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _install_stub(monkeypatch, '{"program": {"type": "Program"}, "confidence": 0.9}')
        _StubAnthropic.last_init_kwargs = {"api_key": "sentinel"}
        extract_schedule_llm("text")
        # api_key=None branch goes through ``anthropic.Anthropic()``
        # (no kwargs); our stub records {} for that path.
        assert _StubAnthropic.last_init_kwargs == {"api_key": None}


# --- Response parsing -------------------------------------------------------


class TestResponseParsing:
    def test_plain_json_with_program_wrapper(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = {
            "program": {
                "type": "Program",
                "schedule": {"type": "Atomic", "dist": "F", "domain": "R", "value": 5.0},
            },
            "confidence": 0.85,
            "warnings": ["Inferred F dist from 'fixed'"],
        }
        _install_stub(monkeypatch, json.dumps(payload))
        r = extract_schedule_llm("FR 5 was used.")
        assert r.ast == payload["program"]
        assert r.confidence == 0.85
        assert r.warnings == ("Inferred F dist from 'fixed'",)
        assert r.source_text == "FR 5 was used."
        assert r.span == (0, len("FR 5 was used."))

    def test_json_without_program_wrapper_uses_root(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # When the model returns a bare Program dict, parsed.get("program", parsed)
        # falls back to ``parsed`` itself.
        payload = {"type": "Program", "schedule": {"type": "Special", "kind": "EXT"}}
        _install_stub(monkeypatch, json.dumps(payload))
        r = extract_schedule_llm("nothing happened.")
        assert r.ast == payload
        # Default confidence when key absent
        assert r.confidence == 0.7
        assert r.warnings == ()

    def test_markdown_code_fence_stripped(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = {"program": {"type": "Program"}, "confidence": 0.6}
        fenced = "```json\n" + json.dumps(payload) + "\n```"
        _install_stub(monkeypatch, fenced)
        r = extract_schedule_llm("text")
        assert r.ast == payload["program"]
        assert r.confidence == 0.6

    def test_markdown_fence_without_closing_backticks(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The strip logic only removes a trailing ``` if present; the
        # opening fence line is always dropped.
        payload = {"program": {"type": "Program"}, "confidence": 0.55}
        fenced = "```\n" + json.dumps(payload)
        _install_stub(monkeypatch, fenced)
        r = extract_schedule_llm("text")
        assert r.confidence == 0.55


# --- Request payload --------------------------------------------------------


class TestRequestPayload:
    def test_model_and_max_tokens_forwarded(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _install_stub(monkeypatch, '{"program": {}, "confidence": 0.9}')
        # Need to capture the client created inside the call. Patch a hook.
        captured: dict[str, Any] = {}

        original_init = _StubAnthropic.__init__

        def init_capture(self, *, api_key: str | None = None) -> None:
            original_init(self, api_key=api_key)
            captured["client"] = self

        monkeypatch.setattr(_StubAnthropic, "__init__", init_capture)

        extract_schedule_llm(
            "some method text",
            model="claude-haiku-4-5",
            max_tokens=512,
        )
        last_call = captured["client"].messages.last_call
        assert last_call["model"] == "claude-haiku-4-5"
        assert last_call["max_tokens"] == 512
        assert "system" in last_call
        # User message should include the source text
        user_content = last_call["messages"][0]["content"]
        assert "some method text" in user_content

    def test_default_model_is_sonnet_4_6(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _install_stub(monkeypatch, '{"program": {}, "confidence": 0.9}')
        captured: dict[str, Any] = {}

        original_init = _StubAnthropic.__init__

        def init_capture(self, *, api_key: str | None = None) -> None:
            original_init(self, api_key=api_key)
            captured["client"] = self

        monkeypatch.setattr(_StubAnthropic, "__init__", init_capture)
        extract_schedule_llm("text")
        assert captured["client"].messages.last_call["model"] == "claude-sonnet-4-6"


# --- extract_all_llm is a thin wrapper -------------------------------------


class TestExtractAllLLM:
    def test_delegates_to_schedule_extractor(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = {"program": {"type": "Program"}, "confidence": 0.77}
        _install_stub(monkeypatch, json.dumps(payload))
        r = extract_all_llm("text", model="claude-sonnet-4-6", api_key="sk-x")
        assert r.ast == payload["program"]
        assert r.confidence == 0.77


# --- module export sanity --------------------------------------------------


class TestModuleSurface:
    def test_grammar_excerpt_contains_atomic_examples(self) -> None:
        # The system prompt must include the grammar primer so the LLM
        # has the vocabulary needed to produce conforming JSON.
        assert "Atomic schedules" in llm_module._SYSTEM_PROMPT
        assert "FR5" in llm_module._SYSTEM_PROMPT
        assert "Conc(A, B)" in llm_module._SYSTEM_PROMPT
