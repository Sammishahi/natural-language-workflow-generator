"""{{reference}} resolution and condition evaluation (no eval() - fully controlled)."""
import json
import re
from typing import Any

from pydantic import BaseModel

from app.errors import ReferenceResolutionError, WorkflowError
from app.models.workflow_schema import Condition

_REF = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_FULL_REF = re.compile(r"^\s*\{\{\s*([^{}]+?)\s*\}\}\s*$")


def resolve_path(path: str, context: dict[str, Any]) -> Any:
    """Look up 'order.amount' or 'items.0.name' in the context."""
    current: Any = context
    for token in path.split("."):
        token = token.strip()
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise ReferenceResolutionError(
                f"Cannot resolve '{{{{{path}}}}}' (nothing named '{token}'). "
                f"Available: {sorted(context.keys())}"
            )
    return current


def resolve_value(value: Any, context: dict[str, Any]) -> Any:
    """Recursively replace {{refs}} inside strings/lists/dicts.

    A string that is exactly one reference keeps the original type (number, dict...).
    """
    if isinstance(value, str):
        full = _FULL_REF.match(value)
        if full:
            return resolve_path(full.group(1), context)

        def _sub(match: re.Match) -> str:
            found = resolve_path(match.group(1), context)
            return json.dumps(found, ensure_ascii=False) if isinstance(found, (dict, list)) else str(found)

        return _REF.sub(_sub, value)
    if isinstance(value, list):
        return [resolve_value(v, context) for v in value]
    if isinstance(value, dict):
        return {k: resolve_value(v, context) for k, v in value.items()}
    return value


def find_references(value: Any) -> set[str]:
    """Return the root names used in {{refs}} (e.g. {{order.amount}} -> 'order')."""
    found: set[str] = set()
    if isinstance(value, BaseModel):
        value = value.model_dump()
    if isinstance(value, str):
        for match in _REF.finditer(value):
            found.add(match.group(1).split(".")[0].strip())
    elif isinstance(value, list):
        for item in value:
            found |= find_references(item)
    elif isinstance(value, dict):
        for item in value.values():
            found |= find_references(item)
    return found


def _to_number(value: Any):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").replace("₹", "").strip())
        except ValueError:
            return None
    return None


def evaluate_condition(condition: Condition, context: dict[str, Any]) -> bool:
    op = condition.operator
    if op == "exists":
        try:
            left = resolve_value(condition.left, context)
        except ReferenceResolutionError:
            return False
        return left is not None and left != ""

    left = resolve_value(condition.left, context)
    right = resolve_value(condition.right, context)

    if op in ("==", "!="):
        ln, rn = _to_number(left), _to_number(right)
        equal = (ln == rn) if (ln is not None and rn is not None) else (left == right)
        return equal if op == "==" else not equal
    if op in (">", ">=", "<", "<="):
        ln, rn = _to_number(left), _to_number(right)
        if ln is None or rn is None:
            raise WorkflowError(f"Cannot compare non-numeric values: {left!r} {op} {right!r}")
        return {">": ln > rn, ">=": ln >= rn, "<": ln < rn, "<=": ln <= rn}[op]
    if op == "contains":
        return right in left if isinstance(left, (str, list, dict)) else False
    if op == "in":
        return left in right if isinstance(right, (str, list, dict)) else False
    raise WorkflowError(f"Unsupported operator '{op}'")
