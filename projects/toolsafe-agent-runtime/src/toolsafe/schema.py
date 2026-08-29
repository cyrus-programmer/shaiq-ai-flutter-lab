from __future__ import annotations

from typing import Any


class SchemaError(ValueError):
    pass


def validate_object(value: Any, schema: dict[str, Any]) -> dict[str, Any]:
    if schema.get("type") != "object":
        raise SchemaError("tool schema root must use type=object")
    if not isinstance(value, dict):
        raise SchemaError("arguments must be an object")
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise SchemaError("schema properties and required must be valid")
    missing = [name for name in required if name not in value]
    if missing:
        raise SchemaError(f"missing required arguments: {', '.join(sorted(missing))}")
    if schema.get("additionalProperties", True) is False:
        extra = value.keys() - properties.keys()
        if extra:
            raise SchemaError(f"unexpected arguments: {', '.join(sorted(extra))}")
    for name, item in value.items():
        if name in properties:
            _validate_value(item, properties[name], name)
    return value


def _validate_value(value: Any, rule: dict[str, Any], path: str) -> None:
    expected = rule.get("type")
    checks = {
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "array": lambda item: isinstance(item, list),
        "object": lambda item: isinstance(item, dict),
    }
    if expected not in checks or not checks[expected](value):
        raise SchemaError(f"{path} must be {expected}")
    if "enum" in rule and value not in rule["enum"]:
        raise SchemaError(f"{path} must be one of: {', '.join(map(str, rule['enum']))}")
    if isinstance(value, str):
        if len(value) < rule.get("minLength", 0):
            raise SchemaError(f"{path} is shorter than minLength")
        if "maxLength" in rule and len(value) > rule["maxLength"]:
            raise SchemaError(f"{path} is longer than maxLength")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in rule and value < rule["minimum"]:
            raise SchemaError(f"{path} is below minimum")
        if "maximum" in rule and value > rule["maximum"]:
            raise SchemaError(f"{path} is above maximum")
    if isinstance(value, list) and "items" in rule:
        for index, item in enumerate(value):
            _validate_value(item, rule["items"], f"{path}.{index}")
