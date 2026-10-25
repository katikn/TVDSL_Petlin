# HW03: Семантический анализатор и проверка типов Funny

```
python3 test_types.py - запуск тестов

python3 typechecker.py path/to/program.funny --json - семантический анализ с выводом аннотированного AST в формате JSON

echo "function inc(x: int) returns r: int { r = x + 1; }" | python3 typechecker.py --json - семантический анализ программы Funny из stdin с выводом аннотированного AST в формате JSON
```