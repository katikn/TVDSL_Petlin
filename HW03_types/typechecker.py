import sys
import json
import argparse
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple

from parser import (
    parse_source, ASTNode, ModuleNode, FunctionNode, FormulaNode,
    VarDefNode, BlockStmtNode, AssignStmtNode, ArrayAssignStmtNode,
    IfStmtNode, WhileStmtNode, AssertStmtNode, AssumeStmtNode,
    BinaryOpNode, UnaryOpNode, CallNode, ArrayAccessNode,
    VariableNode, IntLiteralNode, BoolLiteralNode, QuantifierNode
)


@dataclass
class SemanticError:
    message: str
    line: int
    col: int

    def __str__(self) -> str:
        return f"[{self.line}:{self.col}] Семантическая ошибка: {self.message}"


@dataclass
class Symbol:
    name: str
    type_str: str
    line: int
    col: int
    is_inferred: bool = False


@dataclass
class FunctionSignature:
    name: str
    param_types: List[str]
    return_types: List[str]
    line: int
    col: int
    is_formula: bool = False


class Scope:
    def __init__(self, parent: Optional["Scope"] = None):
        self.parent: Optional[Scope] = parent
        self.symbols: Dict[str, Symbol] = {}

    def lookup(self, name: str) -> Optional[Symbol]:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def define(self, name: str, symbol: Symbol) -> bool:
        if name in self.symbols:
            return False
        self.symbols[name] = symbol
        return True


class TypeChecker:
    def __init__(self):
        self.errors: List[SemanticError] = []
        self.functions: Dict[str, FunctionSignature] = {}
        self.global_scope = Scope()
        self.current_scope: Scope = self.global_scope
        self.current_function: Optional[FunctionSignature] = None

    def error(self, msg: str, line: int, col: int):
        self.errors.append(SemanticError(msg, line, col))

    def enter_scope(self):
        self.current_scope = Scope(parent=self.current_scope)

    def exit_scope(self):
        if self.current_scope.parent:
            self.current_scope = self.current_scope.parent

    def check_module(self, module: ModuleNode) -> ModuleNode:
        for decl in module.declarations:
            if isinstance(decl, FunctionNode):
                param_t = [p.type_str for p in decl.params]
                ret_t = [r.type_str for r in decl.returns]
                if decl.name in self.functions:
                    self.error(f"Повторное объявление функции '{decl.name}'", decl.line, decl.col)
                else:
                    self.functions[decl.name] = FunctionSignature(
                        name=decl.name,
                        param_types=param_t,
                        return_types=ret_t,
                        line=decl.line,
                        col=decl.col,
                        is_formula=False
                    )
            elif isinstance(decl, FormulaNode):
                param_t = [p.type_str for p in decl.params]
                if decl.name in self.functions:
                    self.error(f"Повторное объявление формулы/функции '{decl.name}'", decl.line, decl.col)
                else:
                    self.functions[decl.name] = FunctionSignature(
                        name=decl.name,
                        param_types=param_t,
                        return_types=["bool"],
                        line=decl.line,
                        col=decl.col,
                        is_formula=True
                    )

        for decl in module.declarations:
            if isinstance(decl, FunctionNode):
                self.check_function(decl)
            elif isinstance(decl, FormulaNode):
                self.check_formula(decl)

        return module

    def check_function(self, node: FunctionNode):
        self.current_function = self.functions.get(node.name)
        self.enter_scope()

        for p in node.params:
            if not self.current_scope.define(p.name, Symbol(p.name, p.type_str, p.line, p.col)):
                self.error(f"Повторное объявление параметра '{p.name}'", p.line, p.col)

        for r in node.returns:
            if not self.current_scope.define(r.name, Symbol(r.name, r.type_str, r.line, r.col)):
                self.error(f"Имя возвращаемой переменной '{r.name}' конфликтует с параметрами", r.line, r.col)

        for u in node.uses:
            if not self.current_scope.define(u.name, Symbol(u.name, u.type_str, u.line, u.col)):
                self.error(f"Повторное объявление переменной в uses: '{u.name}'", u.line, u.col)

        if node.requires:
            req_t = self.check_expression(node.requires)
            if req_t != "bool" and req_t != "error":
                self.error(f"requires должен быть типа bool, получено {req_t}", node.requires.line, node.requires.col)

        if node.ensures:
            ens_t = self.check_expression(node.ensures)
            if ens_t != "bool" and ens_t != "error":
                self.error(f"ensures должен быть типа bool, получено {ens_t}", node.ensures.line, node.ensures.col)

        self.check_statement(node.body)
        self.exit_scope()
        self.current_function = None

    def check_formula(self, node: FormulaNode):
        self.enter_scope()
        for p in node.params:
            if not self.current_scope.define(p.name, Symbol(p.name, p.type_str, p.line, p.col)):
                self.error(f"Повторное объявление параметра '{p.name}'", p.line, p.col)

        body_t = self.check_expression(node.body)
        if body_t != "bool" and body_t != "error":
            self.error(f"Тело формулы должно иметь тип bool, получено {body_t}", node.body.line, node.body.col)

        self.exit_scope()

    def check_statement(self, stmt: ASTNode):
        if isinstance(stmt, BlockStmtNode):
            self.enter_scope()
            for s in stmt.statements:
                self.check_statement(s)
            self.exit_scope()

        elif isinstance(stmt, AssignStmtNode):
            val_t = self.check_expression(stmt.value)
            if len(stmt.targets) == 1:
                target_name = stmt.targets[0]
                sym = self.current_scope.lookup(target_name)
                if sym is None:
                    if val_t != "error":
                        self.current_scope.define(
                            target_name,
                            Symbol(target_name, val_t, stmt.line, stmt.col, is_inferred=True)
                        )
                else:
                    if sym.type_str != val_t and val_t != "error":
                        self.error(
                            f"Несовместимость типов в присваивании: '{target_name}' имеет тип {sym.type_str}, но присваивается {val_t}",
                            stmt.line, stmt.col
                        )
            else:
                if not isinstance(stmt.value, CallNode):
                    self.error(
                        f"Множественное присваивание требует вызова функции в правой части",
                        stmt.line, stmt.col
                    )
                else:
                    fn_sig = self.functions.get(stmt.value.name)
                    if fn_sig:
                        if len(stmt.targets) != len(fn_sig.return_types):
                            self.error(
                                f"Несоответствие числа переменных: ожидалось {len(fn_sig.return_types)}, указано {len(stmt.targets)}",
                                stmt.line, stmt.col
                            )
                        else:
                            for name, expected_t in zip(stmt.targets, fn_sig.return_types):
                                sym = self.current_scope.lookup(name)
                                if sym is None:
                                    self.current_scope.define(
                                        name,
                                        Symbol(name, expected_t, stmt.line, stmt.col, is_inferred=True)
                                    )
                                elif sym.type_str != expected_t:
                                    self.error(
                                        f"Несовместимость типов: '{name}' имеет тип {sym.type_str}, ожидался {expected_t}",
                                        stmt.line, stmt.col
                                    )

        elif isinstance(stmt, ArrayAssignStmtNode):
            sym = self.current_scope.lookup(stmt.array_name)
            if sym is None:
                self.error(f"Использование необъявленного массива '{stmt.array_name}'", stmt.line, stmt.col)
            elif sym.type_str != "int[]":
                self.error(f"Переменная '{stmt.array_name}' не является массивом (тип {sym.type_str})", stmt.line, stmt.col)

            idx_t = self.check_expression(stmt.index)
            if idx_t != "int" and idx_t != "error":
                self.error(f"Индекс массива должен быть int, получено {idx_t}", stmt.index.line, stmt.index.col)

            val_t = self.check_expression(stmt.value)
            if val_t != "int" and val_t != "error":
                self.error(f"Значение для элемента массива int[] должно быть int, получено {val_t}", stmt.value.line, stmt.value.col)

        elif isinstance(stmt, IfStmtNode):
            cond_t = self.check_expression(stmt.condition)
            if cond_t != "bool" and cond_t != "error":
                self.error(f"Условие if должно иметь тип bool, получено {cond_t}", stmt.condition.line, stmt.condition.col)
            self.check_statement(stmt.then_branch)
            if stmt.else_branch:
                self.check_statement(stmt.else_branch)

        elif isinstance(stmt, WhileStmtNode):
            cond_t = self.check_expression(stmt.condition)
            if cond_t != "bool" and cond_t != "error":
                self.error(f"Условие while должно иметь тип bool, получено {cond_t}", stmt.condition.line, stmt.condition.col)
            if stmt.invariant:
                inv_t = self.check_expression(stmt.invariant)
                if inv_t != "bool" and inv_t != "error":
                    self.error(f"Инвариант цикла должен иметь тип bool, получено {inv_t}", stmt.invariant.line, stmt.invariant.col)
            self.check_statement(stmt.body)

        elif isinstance(stmt, AssertStmtNode):
            pred_t = self.check_expression(stmt.predicate)
            if pred_t != "bool" and pred_t != "error":
                self.error(f"Предикат assert должен иметь тип bool, получено {pred_t}", stmt.predicate.line, stmt.predicate.col)

        elif isinstance(stmt, AssumeStmtNode):
            pred_t = self.check_expression(stmt.predicate)
            if pred_t != "bool" and pred_t != "error":
                self.error(f"Предикат assume должен иметь тип bool, получено {pred_t}", stmt.predicate.line, stmt.predicate.col)

    def check_expression(self, expr: ASTNode) -> str:
        t = self._check_expr_internal(expr)
        setattr(expr, "inferred_type", t)
        return t

    def _check_expr_internal(self, expr: ASTNode) -> str:
        if isinstance(expr, IntLiteralNode):
            return "int"

        if isinstance(expr, BoolLiteralNode):
            return "bool"

        if isinstance(expr, VariableNode):
            sym = self.current_scope.lookup(expr.name)
            if sym is None:
                self.error(f"Использование необъявленной переменной '{expr.name}'", expr.line, expr.col)
                return "error"
            return sym.type_str

        if isinstance(expr, ArrayAccessNode):
            sym = self.current_scope.lookup(expr.array_name)
            if sym is None:
                self.error(f"Использование необъявленной переменной '{expr.array_name}'", expr.line, expr.col)
                return "error"
            if sym.type_str != "int[]":
                self.error(f"Обращение по индексу к переменной '{expr.array_name}', не являющейся массивом ({sym.type_str})", expr.line, expr.col)
                return "error"
            idx_t = self.check_expression(expr.index)
            if idx_t != "int" and idx_t != "error":
                self.error(f"Индекс массива должен быть int, получено {idx_t}", expr.index.line, expr.index.col)
                return "error"
            return "int"

        if isinstance(expr, CallNode):
            if expr.name == "length":
                if len(expr.args) != 1:
                    self.error(f"Функция length принимает ровно 1 аргумент, получено {len(expr.args)}", expr.line, expr.col)
                    return "error"
                arg_t = self.check_expression(expr.args[0])
                if arg_t != "int[]" and arg_t != "error":
                    self.error(f"Аргумент length должен быть массивом int[], получено {arg_t}", expr.args[0].line, expr.args[0].col)
                    return "error"
                return "int"

            fn = self.functions.get(expr.name)
            if fn is None:
                self.error(f"Вызов необъявленной функции '{expr.name}'", expr.line, expr.col)
                for a in expr.args:
                    self.check_expression(a)
                return "error"

            if len(expr.args) != len(fn.param_types):
                self.error(
                    f"Неверное число аргументов при вызове '{expr.name}': ожидалось {len(fn.param_types)}, передано {len(expr.args)}",
                    expr.line, expr.col
                )

            for i, (arg_node, exp_t) in enumerate(zip(expr.args, fn.param_types)):
                actual_t = self.check_expression(arg_node)
                if actual_t != exp_t and actual_t != "error":
                    self.error(
                        f"Несовпадение типа аргумента #{i + 1} в '{expr.name}': ожидался {exp_t}, передан {actual_t}",
                        arg_node.line, arg_node.col
                    )

            if len(fn.return_types) == 1:
                return fn.return_types[0]
            return f"({', '.join(fn.return_types)})"

        if isinstance(expr, UnaryOpNode):
            sub_t = self.check_expression(expr.operand)
            if sub_t == "error":
                return "error"
            if expr.op == "-":
                if sub_t != "int":
                    self.error(f"Унарный минус применим только к int, получено {sub_t}", expr.line, expr.col)
                    return "error"
                return "int"
            elif expr.op == "not":
                if sub_t != "bool":
                    self.error(f"Оператор not применим только к bool, получено {sub_t}", expr.line, expr.col)
                    return "error"
                return "bool"

        if isinstance(expr, BinaryOpNode):
            left_t = self.check_expression(expr.left)
            right_t = self.check_expression(expr.right)
            if left_t == "error" or right_t == "error":
                return "error"

            if expr.op in ("+", "-", "*", "/"):
                if left_t != "int" or right_t != "int":
                    self.error(f"Оператор '{expr.op}' требует операнды типа int, получено {left_t} и {right_t}", expr.line, expr.col)
                    return "error"
                return "int"

            if expr.op in ("<", "<=", ">", ">="):
                if left_t != "int" or right_t != "int":
                    self.error(f"Сравнение '{expr.op}' требует операнды типа int, получено {left_t} и {right_t}", expr.line, expr.col)
                    return "error"
                return "bool"

            if expr.op in ("==", "!="):
                if left_t != right_t:
                    self.error(f"Сравнение на равенство '{expr.op}' требует одинаковые типы, получено {left_t} и {right_t}", expr.line, expr.col)
                    return "error"
                return "bool"

            if expr.op in ("and", "or", "->"):
                if left_t != "bool" or right_t != "bool":
                    self.error(f"Логический оператор '{expr.op}' требует операнды bool, получено {left_t} и {right_t}", expr.line, expr.col)
                    return "error"
                return "bool"

        if isinstance(expr, QuantifierNode):
            self.enter_scope()
            self.current_scope.define(
                expr.var_def.name,
                Symbol(expr.var_def.name, expr.var_def.type_str, expr.var_def.line, expr.var_def.col)
            )
            body_t = self.check_expression(expr.predicate)
            self.exit_scope()
            if body_t != "bool" and body_t != "error":
                self.error(f"Тело квантора {expr.kind} должно иметь тип bool, получено {body_t}", expr.predicate.line, expr.predicate.col)
                return "error"
            return "bool"

        return "unknown"


def analyze_semantics(text: str) -> Tuple[ModuleNode, List[SemanticError]]:
    ast, parse_errors = parse_source(text)
    if parse_errors:
        return ast, [SemanticError(f"Синтаксическая ошибка: {e.message}", e.line, e.col) for e in parse_errors]
    checker = TypeChecker()
    checker.check_module(ast)
    return ast, checker.errors


def main():
    arg_parser = argparse.ArgumentParser(description="HW3: Семантический анализатор и проверка типов Funny")
    arg_parser.add_argument("file", nargs="?", help="Путь к исходному файлу Funny")
    arg_parser.add_argument("--json", action="store_true", help="Вывести аннотированный AST в формате JSON")
    args = arg_parser.parse_args()

    source = sys.stdin.read() if not args.file else open(args.file, "r", encoding="utf-8").read()
    ast, errors = analyze_semantics(source)

    if errors:
        print(f"[-] Обнаружено {len(errors)} семантических ошибок:", file=sys.stderr)
        for err in errors:
            print(f"    {err}", file=sys.stderr)

    if args.json or not errors:
        print(json.dumps(ast.to_dict(), indent=2, ensure_ascii=False))

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()