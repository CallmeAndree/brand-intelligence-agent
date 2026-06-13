"""Structured-output LLM call dùng chung — fallback 3 mức như enrich_one.

Tách ra core để module `generation`/`alerting` tái dùng cùng một logic gọi LLM
có cấu trúc: (1) `response_format=schema` → (2) prompt-JSON, extract → (3) repair.
429 (rate-limit) raise ngay để caller giữ trạng thái + thử lại, không đốt fallback.
"""

import json
import re
import typing
from typing import Any, TypeVar

from agent_framework import ChatOptions, Message
from pydantic import BaseModel, ValidationError

from app.core.errors import is_rate_limit_error

SchemaT = TypeVar("SchemaT", bound=BaseModel)


async def call_structured(llm: Any, messages: list[Message], schema: type[SchemaT]) -> SchemaT:
    """Gọi LLM trả về instance `schema` đã validate, fallback 3 mức."""
    try:
        response = await llm.get_response(messages, options=ChatOptions(response_format=schema))
        value = getattr(response, "value", None)
        if isinstance(value, schema):
            return value
        if value is not None:
            return _validate_value(value, schema)
    except Exception as exc:  # noqa: BLE001
        if is_rate_limit_error(exc):
            raise

    fallback_messages = messages + [Message("user", [_schema_prompt(schema)])]
    try:
        response = await llm.get_response(fallback_messages)
        return _validate_value(_extract_json(_response_text(response)), schema)
    except Exception as exc:  # noqa: BLE001
        if is_rate_limit_error(exc):
            raise

    repair_messages = fallback_messages + [
        Message(
            "user",
            [
                "Your previous response was invalid (returned a schema or missed fields). "
                f"Return ONLY this JSON object shape with real values: {_example_object(schema)}"
            ],
        )
    ]
    response = await llm.get_response(repair_messages)
    return _validate_value(_extract_json(_response_text(response)), schema)


def _schema_prompt(schema: type[BaseModel]) -> str:
    properties = schema.model_json_schema().get("properties", {})
    required_fields = ", ".join(properties.keys())
    return (
        "Reply with a single valid JSON object only, no markdown, no JSON schema. "
        f"The object must include exactly these fields with real values: {required_fields}. "
        f"Example shape: {_example_object(schema)}"
    )


def _example_object(schema: type[BaseModel]) -> str:
    examples: dict[str, Any] = {}
    for field_name, field_info in schema.model_fields.items():
        annotation = field_info.annotation
        if annotation is bool:
            examples[field_name] = False
        elif annotation is int:
            examples[field_name] = 3
        elif typing.get_origin(annotation) in (list, set, tuple):
            examples[field_name] = ["..."]
        else:
            examples[field_name] = "..."
    return json.dumps(examples, ensure_ascii=False)


def _validate_value(value: Any, schema: type[SchemaT]) -> SchemaT:
    if isinstance(value, str):
        return schema.model_validate_json(value)
    if (
        isinstance(value, dict)
        and "properties" in value
        and not any(field in value for field in schema.model_fields)
    ):
        raise ValueError("LLM returned a JSON schema instead of field values")
    return schema.model_validate(value)


def _response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if text:
        return str(text)
    value = getattr(response, "value", None)
    if value is not None:
        return str(value)
    return str(response)


def _extract_json(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")
    return text[start : end + 1]
