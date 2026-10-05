"""Data transformation, validation and display tools."""
from typing import Any

from app.errors import DataValidationError
from app.tools.registry import ToolRegistry, ToolSpec


def concat_text(p: dict) -> str:
    parts = p["parts"]
    if not isinstance(parts, list):
        raise DataValidationError("'parts' must be a list")
    return str(p.get("separator", " ")).join(str(x) for x in parts if x not in (None, ""))


def extract_field(p: dict) -> Any:
    source = p["source"]
    if not isinstance(source, dict) or p["field"] not in source:
        raise DataValidationError(f"Field '{p['field']}' not found in source")
    return source[p["field"]]


def to_upper(p: dict) -> str:
    return str(p["value"]).upper()


def format_currency(p: dict) -> str:
    try:
        amount = float(str(p["amount"]).replace(",", ""))
    except ValueError:
        raise DataValidationError(f"Not a number: {p['amount']!r}")
    symbol = str(p.get("symbol", "₹"))
    return f"{symbol}{amount:,.0f}" if amount.is_integer() else f"{symbol}{amount:,.2f}"


def add_field(p: dict) -> dict:
    if not isinstance(p["record"], dict):
        raise DataValidationError("'record' must be an object")
    return {**p["record"], str(p["field"]): p["value"]}


def display(p: dict) -> dict:
    return {"label": str(p["label"]), "value": p["value"]}


def validate_required(p: dict) -> dict:
    values = p["values"]
    if not isinstance(values, dict):
        raise DataValidationError("'values' must be an object of name -> value")
    missing = [k for k, v in values.items() if v is None or str(v).strip() == ""]
    if missing:
        raise DataValidationError(f"Missing required value(s): {', '.join(missing)}")
    return {"valid": True, "checked": list(values)}


def validate_email(p: dict) -> dict:
    from app.tools.email_tool import _EMAIL
    value = str(p["value"]).strip()
    if not _EMAIL.match(value):
        raise DataValidationError(f"Invalid email address: '{value}'")
    return {"valid": True, "value": value}


def validate_number_range(p: dict) -> dict:
    try:
        value = float(str(p["value"]).replace(",", ""))
    except ValueError:
        raise DataValidationError(f"Not a number: {p['value']!r}")
    low, high = p.get("min"), p.get("max")
    if low is not None and value < float(low):
        raise DataValidationError(f"{value:g} is below the minimum {low}")
    if high is not None and value > float(high):
        raise DataValidationError(f"{value:g} is above the maximum {high}")
    return {"valid": True, "value": value}


def register_tools(registry: ToolRegistry) -> None:
    specs = [
        ToolSpec("concat_text", "transform", "Joins a list of text parts into one string (e.g. first + last name).",
                 {"parts": "list of values", "separator": "optional, default a space"}, ["parts"], concat_text),
        ToolSpec("extract_field", "transform", "Reads one field from an object.",
                 {"source": "object", "field": "field name"}, ["source", "field"], extract_field),
        ToolSpec("to_upper", "transform", "Converts text to UPPERCASE.",
                 {"value": "text"}, ["value"], to_upper),
        ToolSpec("format_currency", "transform", "Formats a number as currency text, e.g. 75000 -> '₹75,000'.",
                 {"amount": "number", "symbol": "optional, default ₹"}, ["amount"], format_currency),
        ToolSpec("add_field", "transform", "Returns a copy of an object with one new/updated field.",
                 {"record": "object", "field": "new field name", "value": "value"},
                 ["record", "field", "value"], add_field),
        ToolSpec("display", "tool", "Shows a labelled result to the user. Use it for the final answer.",
                 {"label": "short label", "value": "value to show"}, ["label", "value"], display),
        ToolSpec("validate_required", "validation", "Fails if any value is empty. Use before using data.",
                 {"values": "object of name -> value"}, ["values"], validate_required),
        ToolSpec("validate_email", "validation", "Fails if the value is not a valid email address.",
                 {"value": "email"}, ["value"], validate_email),
        ToolSpec("validate_number_range", "validation", "Fails if a number is outside min/max.",
                 {"value": "number", "min": "optional", "max": "optional"}, ["value"], validate_number_range),
    ]
    for spec in specs:
        registry.register(spec)
