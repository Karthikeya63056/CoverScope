"""Structured answer schema shared by the prompt and Pydantic validation."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Verdict = Literal["covered", "excluded", "depends", "not_stated", "summary"]
Confidence = Literal["high", "medium", "low"]

VERDICTS: tuple[Verdict, ...] = ("covered", "excluded", "depends", "not_stated", "summary")
CONFIDENCES: tuple[Confidence, ...] = ("high", "medium", "low")


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)

    @field_validator("chunk_id", "quote")
    @classmethod
    def _must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Verdict
    answer: str = Field(min_length=1)
    citations: list[Citation]
    confidence: Confidence
    caveats: list[str]

    @field_validator("answer")
    @classmethod
    def _answer_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("answer must not be blank")
        return value


# Kept as a plain dict so the strict JSON Schema sent to Groq is explicit and
# independent of Pydantic's internal $defs layout. Every field is required and
# every object forbids additional properties, as required by strict mode.
ANSWER_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chunk_id": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["chunk_id", "quote"],
                "additionalProperties": False,
            },
        },
        "confidence": {"type": "string", "enum": list(CONFIDENCES)},
        "caveats": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "answer", "citations", "confidence", "caveats"],
    "additionalProperties": False,
}
