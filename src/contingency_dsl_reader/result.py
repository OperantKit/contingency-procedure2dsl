"""Extraction result types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExtractResult:
    """A single schedule extraction from text.

    Attributes:
        ast: JSON AST dict conforming to contingency-dsl/ast-schema.json.
            May be a partial Program (schedule only) or full Program.
        confidence: 0.0-1.0 confidence score.
            1.0 = exact pattern match, 0.5+ = structural inference.
        span: (start, end) character offsets in the source text.
        source_text: The matched substring.
        warnings: Any ambiguities or assumptions made during extraction.
    """

    ast: dict
    confidence: float = 1.0
    span: tuple[int, int] = (0, 0)
    source_text: str = ""
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtractionReport:
    """Complete extraction from a Method section.

    Contains all recognized schedules, parameters, and annotations.
    """

    schedules: tuple[ExtractResult, ...] = ()
    params: tuple[ExtractResult, ...] = ()
    annotations: tuple[ExtractResult, ...] = ()
    unrecognized_fragments: tuple[str, ...] = ()

    @property
    def primary_schedule(self) -> ExtractResult | None:
        """The highest-confidence schedule extraction."""
        if not self.schedules:
            return None
        return max(self.schedules, key=lambda r: r.confidence)

    def to_program(self) -> dict:
        """Assemble extractions into a full Program AST dict.

        Best-effort: uses primary_schedule + all recognized params/annotations.
        """
        primary = self.primary_schedule
        if primary is None:
            return {"type": "Program", "param_decls": [], "bindings": [], "schedule": {}}

        program_annotations = []
        for ann in self.annotations:
            if ann.ast.get("type") == "Annotation":
                program_annotations.append(ann.ast)

        param_decls = []
        for p in self.params:
            if p.ast.get("type") == "ParamDecl":
                param_decls.append(p.ast)

        return {
            "type": "Program",
            "program_annotations": program_annotations,
            "param_decls": param_decls,
            "bindings": [],
            "schedule": primary.ast,
        }
