#!/usr/bin/env python3
"""
HW1: Тестовый набор для лексера языка Funny (test_lexer.py).
Проверяет все сценарии из спецификации HW1 и краевые случаи токенов.

Запуск:
    python3 test_lexer.py
"""

import sys
from lexer import build_pipeline, simulate_dfa_exact, tokenize

# Инициализируем минимизированный ДКА
DFA_MODEL, STATS = build_pipeline()

# 1. Тестовые сценарии точного распознавания одиночных токенов
EXACT_CASES = [
    # Пустая строка
    ("empty_string", "", False, None),

    # Пробелы и переводы строк (WS)
    ("ws_space", " ", True, "WS"),
    ("ws_spaces", "    ", True, "WS"),
    ("ws_tab", "\t", True, "WS"),
    ("ws_crlf", "\r\n", True, "WS"),
    ("ws_lf", "\n", True, "WS"),
    ("ws_mixed", " \t\r\n ", True, "WS"),

    # Числовые литералы и ведущие нули (отрицательные тесты)
    ("int_zero", "0", True, "INT"),
    ("int_positive", "42", True, "INT"),
    ("int_large", "100500", True, "INT"),
    ("int_neg_00", "00", False, None),
    ("int_neg_01", "01", False, None),
    ("int_neg_007", "007", False, None),

    # Идентификаторы (включая подчеркивание)
    ("ident_char", "x", True, "IDENT"),
    ("ident_underscore_only", "_", True, "IDENT"),
    ("ident_underscore_prefix", "_temp", True, "IDENT"),
    ("ident_underscore_middle", "var_name", True, "IDENT"),
    ("ident_with_digits", "val123_", True, "IDENT"),

    # Все 18 ключевых слов Funny
    ("kw_function", "function", True, "KEYWORD_FUNCTION"),
    ("kw_returns", "returns", True, "KEYWORD_RETURNS"),
    ("kw_uses", "uses", True, "KEYWORD_USES"),
    ("kw_while", "while", True, "KEYWORD_WHILE"),
    ("kw_if", "if", True, "KEYWORD_IF"),
    ("kw_else", "else", True, "KEYWORD_ELSE"),
    ("kw_assert", "assert", True, "KEYWORD_ASSERT"),
    ("kw_assume", "assume", True, "KEYWORD_ASSUME"),
    ("kw_invariant", "invariant", True, "KEYWORD_INVARIANT"),
    ("kw_length", "length", True, "KEYWORD_LENGTH"),
    ("kw_true", "true", True, "KEYWORD_TRUE"),
    ("kw_false", "false", True, "KEYWORD_FALSE"),
    ("kw_forall", "forall", True, "KEYWORD_FORALL"),
    ("kw_exists", "exists", True, "KEYWORD_EXISTS"),
    ("kw_int", "int", True, "KEYWORD_INT"),
    ("kw_not", "not", True, "KEYWORD_NOT"),
    ("kw_and", "and", True, "KEYWORD_AND"),
    ("kw_or", "or", True, "KEYWORD_OR"),

    # Операторы и делимитеры
    ("op_eq", "==", True, "OP_EQ"),
    ("op_neq", "!=", True, "OP_NEQ"),
    ("op_le", "<=", True, "OP_LE"),
    ("op_ge", ">=", True, "OP_GE"),
    ("op_lt", "<", True, "OP_LT"),
    ("op_gt", ">", True, "OP_GT"),
    ("op_assign", "=", True, "OP_ASSIGN"),
    ("op_arrow", "->", True, "OP_ARROW"),
    ("op_fat_arrow", "=>", True, "OP_FAT_ARROW"),
    ("op_plus", "+", True, "OP_PLUS"),
    ("op_minus", "-", True, "OP_MINUS"),
    ("op_star", "*", True, "OP_STAR"),
    ("op_slash", "/", True, "OP_SLASH"),
    ("delim_lparen", "(", True, "DELIM_LPAREN"),
    ("delim_rparen", ")", True, "DELIM_RPAREN"),
    ("delim_lbracket", "[", True, "DELIM_LBRACKET"),
    ("delim_rbracket", "]", True, "DELIM_RBRACKET"),
    ("delim_lbrace", "{", True, "DELIM_LBRACE"),
    ("delim_rbrace", "}", True, "DELIM_RBRACE"),
    ("delim_comma", ",", True, "DELIM_COMMA"),
    ("delim_semicolon", ";", True, "DELIM_SEMICOLON"),
    ("delim_colon", ":", True, "DELIM_COLON"),

    # Комментарии
    ("comment_empty", "//", True, "COMMENT"),
    ("comment_text", "// simple comment", True, "COMMENT"),
    ("comment_with_code", "// x = 42; assert;", True, "COMMENT"),

    # Ловушка: символы вне алфавита и non-ASCII
    ("trap_at", "@", False, None),
    ("trap_dollar", "$", False, None),
    ("trap_hash", "#", False, None),
    ("trap_cyrillic", "привет", False, None),
    ("trap_unicode", "café", False, None),
]

# 2. Тестовые сценарии потокового разбора
STREAM_CASES = [
    (
        "stream_whitespace_only",
        "   \t\r\n  ",
        []
    ),
    (
        "stream_leading_zeros_split",
        "00",
        ['INT', 'INT']
    ),
    (
        "stream_leading_zeros_007",
        "007",
        ['INT', 'INT', 'INT']
    ),
    (
        "stream_ident_with_underscore",
        "foo_bar",
        ['IDENT']
    ),
    (
        "stream_arithmetic",
        "1 + 2 * 3",
        ['INT', 'OP_PLUS', 'INT', 'OP_STAR', 'INT']
    ),
    (
        "stream_comparison",
        "3 <= x",
        ['INT', 'OP_LE', 'IDENT']
    ),
    (
        "stream_assignment_with_comment",
        "a = 1; // comment to eol\nb = 2;",
        ['IDENT', 'OP_ASSIGN', 'INT', 'DELIM_SEMICOLON', 'IDENT', 'OP_ASSIGN', 'INT', 'DELIM_SEMICOLON']
    ),
    (
        "stream_kw_vs_ident",
        "if1 iff while0",
        ['IDENT', 'IDENT', 'IDENT']
    ),
    (
        "stream_trap_error",
        "x = 42 @ foo;",
        ['IDENT', 'OP_ASSIGN', 'INT', 'ERROR', 'IDENT', 'DELIM_SEMICOLON']
    ),
    (
        "stream_funny_function",
        """
        function gcd(x: int, y: int) returns r: int {
            // Compute GCD
            while (y != 0) {
                x = y;
            }
            r = x;
            assert r >= 0;
        }
        """,
        [
            'KEYWORD_FUNCTION', 'IDENT', 'DELIM_LPAREN', 'IDENT', 'DELIM_COLON', 'KEYWORD_INT',
            'DELIM_COMMA', 'IDENT', 'DELIM_COLON', 'KEYWORD_INT', 'DELIM_RPAREN',
            'KEYWORD_RETURNS', 'IDENT', 'DELIM_COLON', 'KEYWORD_INT', 'DELIM_LBRACE',
            'KEYWORD_WHILE', 'DELIM_LPAREN', 'IDENT', 'OP_NEQ', 'INT', 'DELIM_RPAREN',
            'DELIM_LBRACE', 'IDENT', 'OP_ASSIGN', 'IDENT', 'DELIM_SEMICOLON', 'DELIM_RBRACE',
            'IDENT', 'OP_ASSIGN', 'IDENT', 'DELIM_SEMICOLON',
            'KEYWORD_ASSERT', 'IDENT', 'OP_GE', 'INT', 'DELIM_SEMICOLON', 'DELIM_RBRACE'
        ]
    )
]

def run_all_tests() -> bool:
    print("=" * 70)
    print("ЗАПУСК ТЕСТОВОГО НАБОРА HW1 (test_lexer.py)")
    print(f"Состояния: НКА={STATS['nfa_states']} | ДКА={STATS['dfa_states']} | Мин={STATS['min_dfa_states']}")
    print("=" * 70)

    # 1. Прогон одиночных тестов
    passed_exact = 0
    for name, text, should_accept, expected_tok in EXACT_CASES:
        ok, got_tok = simulate_dfa_exact(DFA_MODEL, text)
        is_correct = (ok == should_accept)
        if should_accept and expected_tok:
            is_correct = is_correct and (got_tok == expected_tok)

        status = "[OK  ]" if is_correct else "[FAIL]"
        if is_correct:
            passed_exact += 1
        print(f"{status} (exact)  | {name:<26} | вход: {repr(text):<18}")

    print("-" * 70)
    print(f"Одиночные тесты: {passed_exact}/{len(EXACT_CASES)} пройдено.")
    print("-" * 70)

    # 2. Прогон потоковых тестов
    passed_stream = 0
    for name, text, expected_tokens in STREAM_CASES:
        got = [t.type for t in tokenize(text, DFA_MODEL)]
        is_correct = (got == expected_tokens)
        status = "[OK  ]" if is_correct else "[FAIL]"
        if is_correct:
            passed_stream += 1
            print(f"{status} (stream) | {name:<26}")
        else:
            print(f"{status} (stream) | {name:<26}")
            print(f"       Получено:   {got}")
            print(f"       Ожидалось:  {expected_tokens}")

    print("-" * 70)
    print(f"Потоковые тесты: {passed_stream}/{len(STREAM_CASES)} пройдено.")
    print("=" * 70)

    total_passed = passed_exact + passed_stream
    total_all = len(EXACT_CASES) + len(STREAM_CASES)
    success = (total_passed == total_all)

    print(f"ИТОГ: {total_passed}/{total_all} успешно выполнено.\n")
    return success

if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)