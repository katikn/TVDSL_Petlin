import sys
from parser import parse_source


def test_positive_gcd():
    code = """
    function gcd(x: int, y: int) returns r: int
    uses a: int
    {
        while (y != 0) invariant y >= 0 {
            a = x;
            x = y;
            y = a;
        }
        r = x;
        assert r >= 0;
    }
    """
    ast, errs = parse_source(code)
    assert len(errs) == 0, f"Ошибки не ожидались: {errs}"
    func = ast.declarations[0]
    assert func.name == "gcd"
    assert len(func.params) == 2
    assert func.body.statements[0].invariant is not None
    print("[OK] test_positive_gcd")


def test_positive_arrays_and_contracts():
    code = """
    function setZero(a: int[], i: int)
        requires i >= 0 and i < length(a)
        returns res: int[]
        ensures res[i] == 0
    {
        a[i] = 0;
        res = a;
    }
    """
    ast, errs = parse_source(code)
    assert len(errs) == 0, f"Ошибки не ожидались: {errs}"
    func = ast.declarations[0]
    assert func.requires is not None
    assert func.ensures is not None
    assert func.body.statements[0].__class__.__name__ == "ArrayAssignStmtNode"
    print("[OK] test_positive_arrays_and_contracts")


def test_positive_quantifiers_and_formulas():
    code = """
    isPositive(x: int) => x > 0;

    function checkAll(arr: int[]) returns ok: int {
        assert forall(i: int | i >= 0 -> arr[i] > 0);
        ok = 1;
    }
    """
    ast, errs = parse_source(code)
    assert len(errs) == 0, f"Ошибки не ожидались: {errs}"
    assert ast.declarations[0].__class__.__name__ == "FormulaNode"
    print("[OK] test_positive_quantifiers_and_formulas")


def test_negative_unclosed_paren():
    code = "function f(x: int returns r: int { r = x; }"
    ast, errs = parse_source(code)
    assert len(errs) > 0, "Ожидалась синтаксическая ошибка"
    assert any("Ожидалась ')'" in e.message for e in errs)
    print("[OK] test_negative_unclosed_paren")


def test_negative_missing_semicolon():
    code = """
    function f(x: int) returns r: int {
        r = x
        assert r == x;
    }
    """
    ast, errs = parse_source(code)
    assert len(errs) > 0, "Ожидалась ошибка отсутствия точки с запятой"
    assert any("Ожидалась ';'" in e.message for e in errs)
    print("[OK] test_negative_missing_semicolon")


def test_negative_empty_input():
    code = ""
    ast, errs = parse_source(code)
    assert len(errs) == 1
    assert "пуст" in errs[0].message
    print("[OK] test_negative_empty_input")


def test_panic_mode_recovery():
    code = """
    function f1(x: int) returns r: int {
        r = @;
        r = 10;
    }
    function f2(y: int) returns res: int {
        if y > 0 { res = 1; }
    }
    """
    ast, errs = parse_source(code)
    assert len(errs) >= 2, f"Ожидалось минимум 2 ошибки, получено {len(errs)}"
    f_names = [d.name for d in ast.declarations if hasattr(d, "name")]
    assert "f2" in f_names, "Парсер должен был восстановиться и разобрать f2"
    print("[OK] test_panic_mode_recovery")


def run_all():
    print("=" * 65)
    print("ЗАПУСК ТЕСТОВОГО НАБОРА HW2 (ПАРСЕР И AST)")
    print("=" * 65)
    test_positive_gcd()
    test_positive_arrays_and_contracts()
    test_positive_quantifiers_and_formulas()
    test_negative_unclosed_paren()
    test_negative_missing_semicolon()
    test_negative_empty_input()
    test_panic_mode_recovery()
    print("=" * 65)
    print("ВСЕ ТЕСТЫ HW2 УСПЕШНО ПРОЙДЕНЫ!")


if __name__ == "__main__":
    run_all()
