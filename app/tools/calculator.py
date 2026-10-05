"""Safe calculator: parses arithmetic with `ast` (no eval)."""
import ast
import operator
from typing import Any

from app.errors import DataValidationError
from app.tools.registry import ToolRegistry, ToolSpec

_BIN = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 10:
            raise DataValidationError("Exponent too large")
        return _BIN[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    raise DataValidationError("Only numbers and + - * / // % ** ( ) are allowed in calculator expressions")


def calculate(expression: Any) -> float:
    if isinstance(expression, (int, float)) and not isinstance(expression, bool):
        return expression
    try:
        tree = ast.parse(str(expression).replace(",", "").strip(), mode="eval")
        result = _eval(tree)
    except ZeroDivisionError:
        raise DataValidationError("Division by zero")
    except SyntaxError:
        raise DataValidationError(f"Invalid expression: {expression!r}")
    return int(result) if float(result).is_integer() else round(result, 2)


def register_tools(registry: ToolRegistry) -> None:
    registry.register(ToolSpec(
        name="calculator", category="tool",
        description="Evaluates an arithmetic expression, e.g. '75000 * 0.18'.",
        params={"expression": "arithmetic expression string or number"},
        required=["expression"],
        func=lambda p: calculate(p["expression"]),
    ))
