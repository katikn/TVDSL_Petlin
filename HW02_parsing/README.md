# HW02: Синтаксический анализатор языка Funny (LL(1) Recursive Descent)

```aiignore
python3 test_parser.py - запуск тестов

python3 parser.py path/to/program.funny --json - запуск парсера с выводом AST в формате JSON

echo "function inc(x: int) returns r: int { r = x + 1; }" | python3 parser.py --json - разбор программы Funny из stdin с выводом AST в формате JSON
```