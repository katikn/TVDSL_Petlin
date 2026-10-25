import sys
from typechecker import analyze_semantics


def test_positive_full_program():
    code = """
    function max(a: int, b: int) returns m: int {
        if (a > b) {
            m = a;
        } else {
            m = b;
        }
        assert m >= a and m >= b;
    }
    """
    ast, errs = analyze_semantics(code)
    assert len(errs) == 0, f"Ошибки не ожидались: {errs}"
    print("[OK] test_positive_full_program")


def test_positive_bonus_type_inference():
    code = """
    function compute(x: int) returns r: int {
        y = x + 10;
        is_pos = y > 0;
        if (is_pos) {
            r = y;
        } else {
            r = 0;
        }
    }
    """
    ast, errs = analyze_semantics(code)
    assert len(errs) == 0, f"Ошибки не ожидались: {errs}"
    print("[OK] test_positive_bonus_type_inference (+2 балла: вывод типов y: int и is_pos: bool)")


def test_positive_arrays_and_calls():
    code = """
    function fillZero(arr: int[])
        requires length(arr) > 0
        returns res: int[]
    {
        arr[0] = 0;
        res = arr;
    }
    """
    ast, errs = analyze_semantics(code)
    assert len(errs) == 0, f"Ошибки не ожидались: {errs}"
    print("[OK] test_positive_arrays_and_calls")


def test_negative_undeclared_variable():
    code = """
    function f(x: int) returns r: int {
        r = unknown_var + 1;
    }
    """
    ast, errs = analyze_semantics(code)
    assert len(errs) >= 1
    assert any("необъявленной переменной 'unknown_var'" in str(e) for e in errs)
    print("[OK] test_negative_undeclared_variable")


def test_negative_type_mismatch():
    code = """
    function f(x: int) returns r: int {
        r = true;
    }
    """
    ast, errs = analyze_semantics(code)
    assert len(errs) >= 1
    assert any("Несовместимость типов в присваивании" in str(e) for e in errs)
    print("[OK] test_negative_type_mismatch")


def test_negative_invalid_condition():
    code = """
    function f(x: int) returns r: int {
        if (x + 5) {
            r = 1;
        }
    }
    """
    ast, errs = analyze_semantics(code)
    assert len(errs) >= 1
    assert any("должно иметь тип bool" in str(e) for e in errs)
    print("[OK] test_negative_invalid_condition")


def test_negative_redefinition():
    code = """
    function dup(x: int, x: int) returns r: int {
        r = x;
    }
    """
    ast, errs = analyze_semantics(code)
    assert len(errs) >= 1
    assert any("Повторное объявление параметра 'x'" in str(e) for e in errs)
    print("[OK] test_negative_redefinition")


def test_negative_call_arg_count_and_types():
    code = """
    function add(a: int, b: int) returns res: int {
        res = a + b;
    }

    function caller() returns ok: int {
        x = add(1);
        y = add(1, true);
        ok = 0;
    }
    """
    ast, errs = analyze_semantics(code)
    assert len(errs) >= 2
    assert any("Неверное число аргументов" in str(e) for e in errs)
    assert any("Несовпадение типа аргумента" in str(e) for e in errs)
    print("[OK] test_negative_call_arg_count_and_types")


def run_all():
    print("=" * 65)
    print("ЗАПУСК ТЕСТОВОГО НАБОРА ЗАДАНИЯ 3 (СЕМАНТИКА И ТИПЫ)")
    print("=" * 65)
    test_positive_full_program()
    test_positive_bonus_type_inference()
    test_positive_arrays_and_calls()
    test_negative_undeclared_variable()
    test_negative_type_mismatch()
    test_negative_invalid_condition()
    test_negative_redefinition()
    test_negative_call_arg_count_and_types()
    print("=" * 65)
    print("ВСЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ!!!!!!!!")


if __name__ == "__main__":
    run_all()