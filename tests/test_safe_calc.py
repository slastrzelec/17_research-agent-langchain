import pytest

from safe_calc import CalcError, safe_eval


@pytest.mark.parametrize("expr,expected", [
    ("1+2*3", 7), ("(1+2)*3", 9), ("2**10", 1024), ("-5 + +3", -2),
    ("10/4", 2.5), ("10//4", 2), ("10%4", 2), ("sqrt(16)", 4.0),
    ("round(3.14159, 2)", 3.14), ("abs(-2)", 2), ("pi*2", 6.283185307179586),
    ("1.5 * 10**-9", 1.5e-9),
])
def test_valid(expr, expected):
    assert safe_eval(expr) == pytest.approx(expected)


@pytest.mark.parametrize("expr", [
    "__import__('os').system('echo x')", "open('x')", "os.getcwd()", "().__class__",
    "[1,2]", "'a'*3", "lambda: 1", "x+1", "True+1", "1 if 1 else 2",
    "print(1)", "eval('1')", "sqrt(1, 2, 3)", "sqrt(x=4)",
])
def test_rejected(expr):
    with pytest.raises(CalcError):
        safe_eval(expr)


@pytest.mark.parametrize("expr", [
    "9**9**9", "10**1001", "10**999 * 10**999", "1/0", "(-8)**0.5",
    "log(0)", "1e308*10", "0**-1",
])
def test_resource_and_math_errors(expr):
    with pytest.raises(CalcError):
        safe_eval(expr)


def test_length_and_complexity_and_empty():
    with pytest.raises(CalcError):
        safe_eval("1+" * 150 + "1")
    with pytest.raises(CalcError):
        safe_eval("+".join(["1"] * 80))
    with pytest.raises(CalcError):
        safe_eval("   ")
    with pytest.raises(CalcError):
        safe_eval("1 +")


def test_calculate_tool_never_executes_code(tmp_path):
    from tools import calculate
    marker = tmp_path / "pwned"
    out = calculate.invoke({"expression": f"__import__('pathlib').Path(r'{marker}').touch()"})
    assert out.startswith("Error")
    assert not marker.exists()
    assert calculate.invoke({"expression": "2+2"}) == "4"
