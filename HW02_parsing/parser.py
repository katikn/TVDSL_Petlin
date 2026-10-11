import sys
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict, Set

hw01_dir = Path(__file__).resolve().parent.parent / "HW01_regex_dfa"
if str(hw01_dir) not in sys.path:
    sys.path.insert(0, str(hw01_dir))

from lexer import build_pipeline, tokenize, Token

@dataclass
class ASTNode:
    line: int
    col: int

    def to_dict(self) -> Dict[str, Any]:
        res = {"_node": self.__class__.__name__}
        for k, v in self.__dict__.items():
            if isinstance(v, ASTNode):
                res[k] = v.to_dict()
            elif isinstance(v, list):
                res[k] = [item.to_dict() if isinstance(item, ASTNode) else item for item in v]
            else:
                res[k] = v
        return res


@dataclass
class VarDefNode(ASTNode):
    name: str
    type_str: str


@dataclass
class FunctionNode(ASTNode):
    name: str
    params: List[VarDefNode]
    returns: List[VarDefNode]
    body: ASTNode
    requires: Optional[ASTNode] = None
    ensures: Optional[ASTNode] = None
    uses: List[VarDefNode] = field(default_factory=list)


@dataclass
class FormulaNode(ASTNode):
    name: str
    params: List[VarDefNode]
    body: ASTNode


@dataclass
class ModuleNode(ASTNode):
    declarations: List[ASTNode]


@dataclass
class BlockStmtNode(ASTNode):
    statements: List[ASTNode]


@dataclass
class AssignStmtNode(ASTNode):
    targets: List[str]
    value: ASTNode


@dataclass
class ArrayAssignStmtNode(ASTNode):
    array_name: str
    index: ASTNode
    value: ASTNode


@dataclass
class IfStmtNode(ASTNode):
    condition: ASTNode
    then_branch: ASTNode
    else_branch: Optional[ASTNode] = None


@dataclass
class WhileStmtNode(ASTNode):
    condition: ASTNode
    body: ASTNode
    invariant: Optional[ASTNode] = None


@dataclass
class AssertStmtNode(ASTNode):
    predicate: ASTNode


@dataclass
class AssumeStmtNode(ASTNode):
    predicate: ASTNode


@dataclass
class BinaryOpNode(ASTNode):
    op: str
    left: ASTNode
    right: ASTNode


@dataclass
class UnaryOpNode(ASTNode):
    op: str
    operand: ASTNode


@dataclass
class CallNode(ASTNode):
    name: str
    args: List[ASTNode]


@dataclass
class ArrayAccessNode(ASTNode):
    array_name: str
    index: ASTNode


@dataclass
class VariableNode(ASTNode):
    name: str


@dataclass
class IntLiteralNode(ASTNode):
    value: int


@dataclass
class BoolLiteralNode(ASTNode):
    value: bool


@dataclass
class QuantifierNode(ASTNode):
    kind: str
    var_def: VarDefNode
    predicate: ASTNode


@dataclass
class ParseError:
    message: str
    line: int
    col: int

    def __str__(self) -> str:
        return f"[{self.line}:{self.col}] Синтаксическая ошибка: {self.message}"


class Parser:
    STMT_SYNC = {
        "DELIM_SEMICOLON", "DELIM_RBRACE", "KEYWORD_IF", "KEYWORD_WHILE",
        "KEYWORD_ASSERT", "KEYWORD_ASSUME", "KEYWORD_FUNCTION", "KEYWORD_RETURNS"
    }
    DECL_SYNC = {"KEYWORD_FUNCTION", "IDENT"}

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.errors: List[ParseError] = []

    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        last = self.tokens[-1] if self.tokens else Token("EOF", "", 1, 1)
        return Token("EOF", "", last.line, last.col)

    def check(self, token_type: str) -> bool:
        return self.peek().type == token_type

    def match(self, *token_types: str) -> bool:
        for t in token_types:
            if self.check(t):
                self.pos += 1
                return True
        return False

    def match_keyword(self, kw_name: str, kw_token_type: str) -> bool:
        if self.check(kw_token_type):
            self.pos += 1
            return True
        if self.check("IDENT") and self.peek().lexeme == kw_name:
            self.pos += 1
            return True
        return False

    def consume(self, token_type: str, err_msg: str) -> Token:
        t = self.peek()
        if t.type == token_type:
            self.pos += 1
            return t
        self.record_error(f"{err_msg}. Получено '{t.lexeme or t.type}'", t.line, t.col)
        return t

    def record_error(self, msg: str, line: int, col: int):
        self.errors.append(ParseError(msg, line, col))

    def panic_synchronize(self, sync_set: Set[str]):
        self.pos += 1
        while not self.check("EOF"):
            if self.peek().type in sync_set:
                if self.check("DELIM_SEMICOLON"):
                    self.pos += 1
                return
            self.pos += 1

    def parse_module(self) -> ModuleNode:
        decls: List[ASTNode] = []
        start = self.peek()

        if self.check("EOF"):
            self.record_error("Входной файл пуст", start.line, start.col)
            return ModuleNode(start.line, start.col, [])

        while not self.check("EOF"):
            try:
                if self.check("KEYWORD_FUNCTION") or (self.check("IDENT") and self.peek(1).type == "DELIM_LPAREN"):
                    decl = self.parse_function_or_formula()
                    if decl:
                        decls.append(decl)
                else:
                    t = self.peek()
                    self.record_error(f"Неожиданный токен на верхнем уровне модуля: '{t.lexeme}'", t.line, t.col)
                    self.panic_synchronize(self.DECL_SYNC)
            except Exception as e:
                t = self.peek()
                self.record_error(f"Критический сбой разбора: {e}", t.line, t.col)
                self.panic_synchronize(self.DECL_SYNC)

        return ModuleNode(start.line, start.col, decls)

    def parse_function_or_formula(self) -> Optional[ASTNode]:
        start = self.peek()
        self.match("KEYWORD_FUNCTION")

        name_tok = self.consume("IDENT", "Ожидалось имя функции или формулы")
        self.consume("DELIM_LPAREN", "Ожидалась '(' после имени")
        params = self.parse_param_list()
        self.consume("DELIM_RPAREN", "Ожидалась ')' после списка параметров")

        if self.match("OP_FAT_ARROW"):
            body = self.parse_predicate()
            self.match("DELIM_SEMICOLON")
            return FormulaNode(start.line, start.col, name_tok.lexeme, params, body)

        requires = None
        if self.match_keyword("requires", "KEYWORD_REQUIRES"):
            requires = self.parse_predicate()

        if not self.match_keyword("returns", "KEYWORD_RETURNS"):
            self.consume("KEYWORD_RETURNS", "Ожидалось ключевое слово 'returns'")
        returns = self.parse_param_list()

        ensures = None
        if self.match_keyword("ensures", "KEYWORD_ENSURES"):
            ensures = self.parse_predicate()

        uses: List[VarDefNode] = []
        if self.match_keyword("uses", "KEYWORD_USES"):
            uses = self.parse_param_list()

        body = self.parse_statement()
        return FunctionNode(start.line, start.col, name_tok.lexeme, params, returns, body, requires, ensures, uses)

    def parse_param_list(self) -> List[VarDefNode]:
        params: List[VarDefNode] = []
        if (self.check("DELIM_RPAREN") or self.check("KEYWORD_RETURNS") or
            self.check("KEYWORD_ENSURES") or self.check("KEYWORD_USES") or
            self.check("DELIM_LBRACE") or
            (self.check("IDENT") and self.peek().lexeme in ("returns", "requires", "ensures", "uses"))):
            return params

        params.append(self.parse_var_def())
        while self.match("DELIM_COMMA"):
            params.append(self.parse_var_def())
        return params

    def parse_var_def(self) -> VarDefNode:
        t = self.consume("IDENT", "Ожидалось имя переменной")
        type_str = "int"
        if self.match("DELIM_COLON"):
            type_str = self.parse_type()
        return VarDefNode(t.line, t.col, t.lexeme, type_str)

    def parse_type(self) -> str:
        self.consume("KEYWORD_INT", "Ожидался тип 'int'")
        if self.match("DELIM_LBRACKET"):
            self.consume("DELIM_RBRACKET", "Ожидалась ']' для типа 'int[]'")
            return "int[]"
        return "int"

    def parse_statement(self) -> ASTNode:
        t = self.peek()

        if self.check("DELIM_LBRACE"):
            return self.parse_block()
        if self.check("KEYWORD_IF"):
            return self.parse_if()
        if self.check("KEYWORD_WHILE"):
            return self.parse_while()
        if self.check("KEYWORD_ASSERT"):
            return self.parse_assert()
        if self.check("KEYWORD_ASSUME"):
            return self.parse_assume()
        if self.check("IDENT"):
            return self.parse_assignment()

        self.record_error(f"Ожидался оператор, встречено '{t.lexeme or t.type}'", t.line, t.col)
        self.panic_synchronize(self.STMT_SYNC)
        return BlockStmtNode(t.line, t.col, [])

    def parse_block(self) -> BlockStmtNode:
        start = self.consume("DELIM_LBRACE", "Ожидалась '{'")
        stmts: List[ASTNode] = []
        while not self.check("DELIM_RBRACE") and not self.check("EOF"):
            stmts.append(self.parse_statement())
        self.consume("DELIM_RBRACE", "Ожидалась '}' в конце блока")
        return BlockStmtNode(start.line, start.col, stmts)

    def parse_if(self) -> IfStmtNode:
        start = self.consume("KEYWORD_IF", "Ожидалось 'if'")
        self.consume("DELIM_LPAREN", "Ожидалась '(' после 'if'")
        cond = self.parse_predicate()
        self.consume("DELIM_RPAREN", "Ожидалась ')' после условия")
        then_b = self.parse_statement()
        else_b = None
        if self.match("KEYWORD_ELSE"):
            else_b = self.parse_statement()
        return IfStmtNode(start.line, start.col, cond, then_b, else_b)

    def parse_while(self) -> WhileStmtNode:
        start = self.consume("KEYWORD_WHILE", "Ожидалось 'while'")
        self.consume("DELIM_LPAREN", "Ожидалась '(' после 'while'")
        cond = self.parse_predicate()
        self.consume("DELIM_RPAREN", "Ожидалась ')' после условия")
        inv = None
        if self.match_keyword("invariant", "KEYWORD_INVARIANT"):
            inv = self.parse_predicate()
        body = self.parse_statement()
        return WhileStmtNode(start.line, start.col, cond, body, inv)

    def parse_assert(self) -> AssertStmtNode:
        start = self.consume("KEYWORD_ASSERT", "Ожидалось 'assert'")
        pred = self.parse_predicate()
        self.consume("DELIM_SEMICOLON", "Ожидалась ';' после assert")
        return AssertStmtNode(start.line, start.col, pred)

    def parse_assume(self) -> AssumeStmtNode:
        start = self.consume("KEYWORD_ASSUME", "Ожидалось 'assume'")
        pred = self.parse_predicate()
        self.consume("DELIM_SEMICOLON", "Ожидалась ';' после assume")
        return AssumeStmtNode(start.line, start.col, pred)

    def parse_assignment(self) -> ASTNode:
        start = self.peek()
        first_name = self.consume("IDENT", "Ожидалось имя переменной").lexeme

        if self.match("DELIM_LBRACKET"):
            idx = self.parse_expression()
            self.consume("DELIM_RBRACKET", "Ожидалась ']' после индекса")
            self.consume("OP_ASSIGN", "Ожидалось '=' для обновления массива")
            val = self.parse_expression()
            self.consume("DELIM_SEMICOLON", "Ожидалась ';' после присваивания")
            return ArrayAssignStmtNode(start.line, start.col, first_name, idx, val)

        names = [first_name]
        while self.match("DELIM_COMMA"):
            names.append(self.consume("IDENT", "Ожидался идентификатор").lexeme)

        self.consume("OP_ASSIGN", "Ожидалось '=' в присваивании")
        val = self.parse_expression()
        self.consume("DELIM_SEMICOLON", "Ожидалась ';' после присваивания")
        return AssignStmtNode(start.line, start.col, names, val)

    def parse_predicate(self) -> ASTNode:
        if self.check("KEYWORD_FORALL") or self.check("KEYWORD_EXISTS"):
            q_tok = self.peek()
            self.pos += 1
            self.consume("DELIM_LPAREN", "Ожидалась '(' после квантора")
            vdef = self.parse_var_def()
            self.consume("DELIM_PIPE", "Ожидался '|' в теле квантора")
            body = self.parse_predicate()
            self.consume("DELIM_RPAREN", "Ожидалась ')' после квантора")
            return QuantifierNode(q_tok.line, q_tok.col, q_tok.lexeme, vdef, body)

        return self.parse_implies()

    def parse_implies(self) -> ASTNode:
        node = self.parse_or()
        if self.match("OP_ARROW"):
            right = self.parse_implies()
            return BinaryOpNode(node.line, node.col, "->", node, right)
        return node

    def parse_or(self) -> ASTNode:
        node = self.parse_and()
        while self.match("KEYWORD_OR"):
            right = self.parse_and()
            node = BinaryOpNode(node.line, node.col, "or", node, right)
        return node

    def parse_and(self) -> ASTNode:
        node = self.parse_not()
        while self.match("KEYWORD_AND"):
            right = self.parse_not()
            node = BinaryOpNode(node.line, node.col, "and", node, right)
        return node

    def parse_not(self) -> ASTNode:
        if self.check("KEYWORD_NOT"):
            t = self.peek()
            self.pos += 1
            op = self.parse_not()
            return UnaryOpNode(t.line, t.col, "not", op)
        return self.parse_comparison()

    def parse_comparison(self) -> ASTNode:
        node = self.parse_arithmetic()
        cmp_ops = {"OP_EQ": "==", "OP_NEQ": "!=", "OP_LE": "<=", "OP_GE": ">=", "OP_LT": "<", "OP_GT": ">"}
        if self.peek().type in cmp_ops:
            op_tok = self.peek()
            self.pos += 1
            right = self.parse_arithmetic()
            return BinaryOpNode(node.line, node.col, cmp_ops[op_tok.type], node, right)
        return node

    def parse_arithmetic(self) -> ASTNode:
        return self.parse_term()

    def parse_term(self) -> ASTNode:
        node = self.parse_factor()
        while self.check("OP_PLUS") or self.check("OP_MINUS"):
            op_tok = self.peek()
            self.pos += 1
            right = self.parse_factor()
            node = BinaryOpNode(node.line, node.col, op_tok.lexeme, node, right)
        return node

    def parse_factor(self) -> ASTNode:
        node = self.parse_unary()
        while self.check("OP_STAR") or self.check("OP_SLASH"):
            op_tok = self.peek()
            self.pos += 1
            right = self.parse_unary()
            node = BinaryOpNode(node.line, node.col, op_tok.lexeme, node, right)
        return node

    def parse_unary(self) -> ASTNode:
        if self.match("OP_MINUS"):
            start = self.tokens[self.pos - 1]
            op = self.parse_unary()
            return UnaryOpNode(start.line, start.col, "-", op)
        return self.parse_primary()

    def parse_primary(self) -> ASTNode:
        t = self.peek()

        if self.match("INT"):
            return IntLiteralNode(t.line, t.col, int(t.lexeme))

        if self.match("KEYWORD_TRUE"):
            return BoolLiteralNode(t.line, t.col, True)
        if self.match("KEYWORD_FALSE"):
            return BoolLiteralNode(t.line, t.col, False)

        if self.match("DELIM_LPAREN"):
            node = self.parse_predicate()
            self.consume("DELIM_RPAREN", "Ожидалась ')'")
            return node

        if self.match("KEYWORD_LENGTH"):
            self.consume("DELIM_LPAREN", "Ожидалась '(' после length")
            arg = self.parse_expression()
            self.consume("DELIM_RPAREN", "Ожидалась ')'")
            return CallNode(t.line, t.col, "length", [arg])

        if self.match("IDENT"):
            name = t.lexeme

            if self.match("DELIM_LPAREN"):
                args: List[ASTNode] = []
                if not self.check("DELIM_RPAREN"):
                    args.append(self.parse_expression())
                    while self.match("DELIM_COMMA"):
                        args.append(self.parse_expression())
                self.consume("DELIM_RPAREN", "Ожидалась ')' после аргументов")
                return CallNode(t.line, t.col, name, args)

            if self.match("DELIM_LBRACKET"):
                idx = self.parse_expression()
                self.consume("DELIM_RBRACKET", "Ожидалась ']' после индекса")
                return ArrayAccessNode(t.line, t.col, name, idx)

            return VariableNode(t.line, t.col, name)

        self.record_error(f"Неожиданный токен в выражении: '{t.lexeme or t.type}'", t.line, t.col)
        self.pos += 1
        return VariableNode(t.line, t.col, "<error>")

    def parse_expression(self) -> ASTNode:
        return self.parse_predicate()


def parse_source(text: str) -> Tuple[ModuleNode, List[ParseError]]:
    dfa, _ = build_pipeline()
    tokens = tokenize(text, dfa)
    parser = Parser(tokens)
    ast = parser.parse_module()
    return ast, parser.errors


def main():
    arg_parser = argparse.ArgumentParser(description="HW2: Парсер языка Funny (LL(1) Recursive Descent)")
    arg_parser.add_argument("file", nargs="?", help="Путь к исходному файлу Funny")
    arg_parser.add_argument("--json", action="store_true", help="Вывести AST в формате JSON")
    args = arg_parser.parse_args()

    source = sys.stdin.read() if not args.file else open(args.file, "r", encoding="utf-8").read()
    ast, errors = parse_source(source)

    if errors:
        print(f"[-] Обнаружено {len(errors)} синтаксических ошибок:", file=sys.stderr)
        for err in errors:
            print(f"    {err}", file=sys.stderr)

    if args.json:
        print(json.dumps(ast.to_dict(), indent=2, ensure_ascii=False))
    else:
        print("[+] AST успешно построено:")
        print(json.dumps(ast.to_dict(), indent=2, ensure_ascii=False))

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
