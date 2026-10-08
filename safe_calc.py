"""Safe arithmetic evaluator used by the agent's `calculate` tool.

Replaces ``eval()``: only numbers, a small set of operators and a whitelist of
math functions/constants are accepted. Anything else raises ``CalcError``.
"""
import ast
import math
import operator

MAX_EXPR_LEN = 200
MAX_NODES = 100
MAX_EXPONENT = 1000
MAX_ABS_RESULT = 1e300

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "exp": math.exp,
    "abs": abs, "round": round,
}
_CONSTS = {"pi": math.pi, "e": math.e}


class CalcError(ValueError):
    """Raised for any expression that is invalid or not allowed."""


def _check(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalcError("Only real numbers are allowed.")
    if isinstance(value, float) and not math.isfinite(value):
        raise CalcError("Result is not a finite number.")
    if abs(value) > MAX_ABS_RESULT:
        raise CalcError("Result is too large.")
    return value


def _eval(node):
    if isinstance(node, ast.Constant):
        return _check(node.value)
    if isinstance(node, ast.Name):
        if node.id in _CONSTS:
            return _CONSTS[node.id]
        raise CalcError(f"Unknown name: {node.id}")
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _check(_UNARY_OPS[type(node.op)](_eval(node.operand)))
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise CalcError("Exponent is too large.")
        return _check(_BIN_OPS[type(node.op)](left, right))
    if isinstance(node, ast.Call):
        if (isinstance(node.func, ast.Name) and node.func.id in _FUNCS
                and not node.keywords and 1 <= len(node.args) <= 2):
            return _check(_FUNCS[node.func.id](*[_eval(a) for a in node.args]))
        raise CalcError("Function not allowed.")
    raise CalcError("Expression not allowed.")


def safe_eval(expression: str):
    """Evaluate an arithmetic expression safely and return an int or float."""
    if not isinstance(expression, str) or not expression.strip():
        raise CalcError("Empty expression.")
    if len(expression) > MAX_EXPR_LEN:
        raise CalcError("Expression is too long.")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise CalcError("Invalid syntax.") from exc
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise CalcError("Expression is too complex.")
    try:
        return _eval(tree.body)
    except (ArithmeticError, ValueError, TypeError) as exc:
        if isinstance(exc, CalcError):
            raise
        raise CalcError(f"Cannot compute: {type(exc).__name__}") from exc
