#!/usr/bin/env python3
import sys
import json
import argparse
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional, FrozenSet

@dataclass(frozen=True)
class TokenRule:
    name: str
    pattern: str
    priority: int
    is_skip: bool = False

FUNNY_TOKEN_RULES: List[TokenRule] = [
    TokenRule("KEYWORD_FUNCTION",  "function",   100),
    TokenRule("KEYWORD_RETURNS",   "returns",    100),
    TokenRule("KEYWORD_USES",      "uses",       100),
    TokenRule("KEYWORD_WHILE",     "while",      100),
    TokenRule("KEYWORD_IF",        "if",         100),
    TokenRule("KEYWORD_ELSE",      "else",       100),
    TokenRule("KEYWORD_ASSERT",    "assert",     100),
    TokenRule("KEYWORD_ASSUME",    "assume",     100),
    TokenRule("KEYWORD_INVARIANT", "invariant",  100),
    TokenRule("KEYWORD_LENGTH",    "length",     100),
    TokenRule("KEYWORD_TRUE",      "true",       100),
    TokenRule("KEYWORD_FALSE",     "false",      100),
    TokenRule("KEYWORD_FORALL",    "forall",     100),
    TokenRule("KEYWORD_EXISTS",    "exists",     100),
    TokenRule("KEYWORD_INT",       "int",        100),
    TokenRule("KEYWORD_NOT",       "not",        100),
    TokenRule("KEYWORD_AND",       "and",        100),
    TokenRule("KEYWORD_OR",        "or",         100),

    TokenRule("OP_EQ",             "==",         90),
    TokenRule("OP_NEQ",            "!=",         90),
    TokenRule("OP_LE",             "<=",         90),
    TokenRule("OP_GE",             ">=",         90),
    TokenRule("OP_ARROW",          "->",         90),
    TokenRule("OP_FAT_ARROW",      "=>",         90),

    TokenRule("OP_PLUS",           "\\+",        80),
    TokenRule("OP_MINUS",          "-",          80),
    TokenRule("OP_STAR",           "\\*",        80),
    TokenRule("OP_SLASH",          "/",          80),
    TokenRule("OP_LT",             "<",          80),
    TokenRule("OP_GT",             ">",          80),
    TokenRule("OP_ASSIGN",         "=",          80),
    TokenRule("DELIM_COMMA",       ",",          80),
    TokenRule("DELIM_SEMICOLON",   ";",          80),
    TokenRule("DELIM_COLON",       ":",          80),
    TokenRule("DELIM_PIPE",        "\\|",        80),
    TokenRule("DELIM_LPAREN",      "\\(",        80),
    TokenRule("DELIM_RPAREN",      "\\)",        80),
    TokenRule("DELIM_LBRACKET",    "\\[",        80),
    TokenRule("DELIM_RBRACKET",    "\\]",        80),
    TokenRule("DELIM_LBRACE",      "\\{",        80),
    TokenRule("DELIM_RBRACE",      "\\}",        80),

    TokenRule("INT",               "0|[1-9][0-9]*",          50),
    TokenRule("IDENT",             "[A-Za-z_][A-Za-z0-9_]*", 40),

    TokenRule("COMMENT",           "//[^\\r\\n]*",           30, is_skip=True),
    TokenRule("WS",                "[ \\t\\r\\n]+",          20, is_skip=True),
]

# 2. AST и синтаксический анализ регулярных выражений
class RegexNode: pass

@dataclass
class EmptyNode(RegexNode): pass

@dataclass
class LiteralNode(RegexNode): char: str

@dataclass
class CharClassNode(RegexNode): chars: FrozenSet[str]

@dataclass
class ConcatNode(RegexNode): left: RegexNode; right: RegexNode

@dataclass
class AltNode(RegexNode): left: RegexNode; right: RegexNode

@dataclass
class StarNode(RegexNode): child: RegexNode

@dataclass
class PlusNode(RegexNode): child: RegexNode

@dataclass
class QuestNode(RegexNode): child: RegexNode

class RegexParser:
    def __init__(self, pattern: str):
        self.pattern = pattern
        self.pos = 0

    def peek(self, offset: int = 0) -> Optional[str]:
        idx = self.pos + offset
        return self.pattern[idx] if idx < len(self.pattern) else None

    def consume(self, expected: Optional[str] = None) -> str:
        ch = self.peek()
        if ch is None:
            raise ValueError(f"Неожиданный конец регулярного выражения в позиции {self.pos}")
        if expected and ch != expected:
            raise ValueError(f"Ожидался '{expected}', получен '{ch}' в позиции {self.pos}")
        self.pos += 1
        return ch

    def has_more(self) -> bool:
        return self.pos < len(self.pattern)

    def parse(self) -> RegexNode:
        node = self.parse_alt()
        if self.has_more():
            raise ValueError(f"Лишний символ '{self.peek()}' в позиции {self.pos}")
        return node

    def parse_alt(self) -> RegexNode:
        node = self.parse_concat()
        while self.has_more() and self.peek() == '|':
            self.consume('|')
            node = AltNode(node, self.parse_concat())
        return node

    def parse_concat(self) -> RegexNode:
        nodes: List[RegexNode] = []
        while self.has_more() and self.peek() not in ('|', ')'):
            nodes.append(self.parse_repeat())
        if not nodes:
            return EmptyNode()
        res = nodes[0]
        for n in nodes[1:]:
            res = ConcatNode(res, n)
        return res

    def parse_repeat(self) -> RegexNode:
        node = self.parse_atom()
        while self.has_more() and self.peek() in ('*', '+', '?'):
            op = self.consume()
            if op == '*': node = StarNode(node)
            elif op == '+': node = PlusNode(node)
            elif op == '?': node = QuestNode(node)
        return node

    def parse_atom(self) -> RegexNode:
        ch = self.peek()
        if ch == '(':
            self.consume('(')
            node = self.parse_alt()
            self.consume(')')
            return node
        if ch == '[':
            return self.parse_char_class()
        if ch == '\\':
            self.consume('\\')
            esc = self.consume()
            if esc == 'n': return LiteralNode('\n')
            if esc == 't': return LiteralNode('\t')
            if esc == 'r': return LiteralNode('\r')
            return LiteralNode(esc)
        if ch in ('*', '+', '?', '|', ')'):
            raise ValueError(f"Неожиданный спецсимвол '{ch}' в позиции {self.pos}")
        return LiteralNode(self.consume())

    def parse_char_class(self) -> RegexNode:
        self.consume('[')
        negated = False
        if self.peek() == '^':
            self.consume('^')
            negated = True

        chars: Set[str] = set()
        while self.has_more() and self.peek() != ']':
            c1 = self.parse_class_char()
            if self.peek() == '-' and self.peek(1) != ']':
                self.consume('-')
                c2 = self.parse_class_char()
                for code in range(ord(c1), ord(c2) + 1):
                    chars.add(chr(code))
            else:
                chars.add(c1)

        self.consume(']')
        if negated:
            chars = {chr(i) for i in range(128)} - chars
        return CharClassNode(frozenset(chars))

    def parse_class_char(self) -> str:
        ch = self.consume()
        if ch == '\\':
            esc = self.consume()
            if esc == 'n': return '\n'
            if esc == 't': return '\t'
            if esc == 'r': return '\r'
            return esc
        return ch

# 3. Построение НКА (Томпсон)
class NFA:
    def __init__(self):
        self.num_states = 0
        self.transitions: Dict[int, List[Tuple[Optional[str], int]]] = {}
        self.accept_rules: Dict[int, TokenRule] = {}

    def new_state(self) -> int:
        s = self.num_states
        self.num_states += 1
        self.transitions[s] = []
        return s

    def add_trans(self, src: int, char: Optional[str], dst: int):
        self.transitions[src].append((char, dst))

def build_thompson_fragment(nfa: NFA, node: RegexNode) -> Tuple[int, int]:
    if isinstance(node, EmptyNode):
        s, e = nfa.new_state(), nfa.new_state()
        nfa.add_trans(s, None, e)
        return s, e
    if isinstance(node, LiteralNode):
        s, e = nfa.new_state(), nfa.new_state()
        nfa.add_trans(s, node.char, e)
        return s, e
    if isinstance(node, CharClassNode):
        s, e = nfa.new_state(), nfa.new_state()
        for c in node.chars:
            nfa.add_trans(s, c, e)
        return s, e
    if isinstance(node, ConcatNode):
        s1, e1 = build_thompson_fragment(nfa, node.left)
        s2, e2 = build_thompson_fragment(nfa, node.right)
        nfa.add_trans(e1, None, s2)
        return s1, e2
    if isinstance(node, AltNode):
        s1, e1 = build_thompson_fragment(nfa, node.left)
        s2, e2 = build_thompson_fragment(nfa, node.right)
        s, e = nfa.new_state(), nfa.new_state()
        nfa.add_trans(s, None, s1)
        nfa.add_trans(s, None, s2)
        nfa.add_trans(e1, None, e)
        nfa.add_trans(e2, None, e)
        return s, e
    if isinstance(node, StarNode):
        s1, e1 = build_thompson_fragment(nfa, node.child)
        s, e = nfa.new_state(), nfa.new_state()
        nfa.add_trans(s, None, s1)
        nfa.add_trans(s, None, e)
        nfa.add_trans(e1, None, s1)
        nfa.add_trans(e1, None, e)
        return s, e
    if isinstance(node, PlusNode):
        s1, e1 = build_thompson_fragment(nfa, node.child)
        s, e = nfa.new_state(), nfa.new_state()
        nfa.add_trans(s, None, s1)
        nfa.add_trans(e1, None, s1)
        nfa.add_trans(e1, None, e)
        return s, e
    if isinstance(node, QuestNode):
        s1, e1 = build_thompson_fragment(nfa, node.child)
        s, e = nfa.new_state(), nfa.new_state()
        nfa.add_trans(s, None, s1)
        nfa.add_trans(s, None, e)
        nfa.add_trans(e1, None, e)
        return s, e
    raise TypeError(f"Неизвестный тип AST узла: {type(node)}")

def build_combined_nfa(rules: List[TokenRule]) -> Tuple[NFA, int]:
    nfa = NFA()
    master_start = nfa.new_state()
    for rule in rules:
        ast = RegexParser(rule.pattern).parse()
        frag_start, frag_end = build_thompson_fragment(nfa, ast)
        nfa.add_trans(master_start, None, frag_start)
        nfa.accept_rules[frag_end] = rule
    return nfa, master_start

# 4. Построение ДКА и Ловушка
def epsilon_closure(nfa: NFA, states: Set[int]) -> FrozenSet[int]:
    stack = list(states)
    closure = set(states)
    while stack:
        curr = stack.pop()
        for ch, dest in nfa.transitions.get(curr, []):
            if ch is None and dest not in closure:
                closure.add(dest)
                stack.append(dest)
    return frozenset(closure)

def nfa_move(nfa: NFA, states: FrozenSet[int], char: str) -> Set[int]:
    destinations = set()
    for s in states:
        for ch, dest in nfa.transitions.get(s, []):
            if ch == char:
                destinations.add(dest)
    return destinations

@dataclass
class DFA:
    num_states: int
    start_state: int
    transitions: Dict[int, Dict[str, int]]
    accept_tokens: Dict[int, TokenRule]
    alphabet: List[str]
    trap_state: Optional[int] = None

def nfa_to_dfa(nfa: NFA, start_state: int) -> DFA:
    alphabet_set = set()
    for s in range(nfa.num_states):
        for ch, _ in nfa.transitions.get(s, []):
            if ch is not None:
                alphabet_set.add(ch)
    alphabet = sorted(list(alphabet_set))

    init_closure = epsilon_closure(nfa, {start_state})
    state_map: Dict[FrozenSet[int], int] = {init_closure: 0}
    dfa_states: List[FrozenSet[int]] = [init_closure]
    dfa_trans: Dict[int, Dict[str, int]] = {}
    dfa_accept: Dict[int, TokenRule] = {}
    queue = [init_closure]

    while queue:
        curr_subset = queue.pop(0)
        curr_id = state_map[curr_subset]
        dfa_trans[curr_id] = {}

        matched_rules = [nfa.accept_rules[s] for s in curr_subset if s in nfa.accept_rules]
        if matched_rules:
            dfa_accept[curr_id] = max(matched_rules, key=lambda r: r.priority)

        for ch in alphabet:
            moved = nfa_move(nfa, curr_subset, ch)
            if not moved:
                continue
            closure = epsilon_closure(nfa, moved)
            if not closure:
                continue

            if closure not in state_map:
                new_id = len(dfa_states)
                state_map[closure] = new_id
                dfa_states.append(closure)
                queue.append(closure)

            dfa_trans[curr_id][ch] = state_map[closure]

    return DFA(
        num_states=len(dfa_states),
        start_state=0,
        transitions=dfa_trans,
        accept_tokens=dfa_accept,
        alphabet=alphabet
    )

def complete_dfa_with_trap(dfa: DFA) -> DFA:
    trap_id = dfa.num_states
    new_transitions: Dict[int, Dict[str, int]] = {}

    for s in range(dfa.num_states):
        new_transitions[s] = dict(dfa.transitions.get(s, {}))
        for ch in dfa.alphabet:
            if ch not in new_transitions[s]:
                new_transitions[s][ch] = trap_id

    new_transitions[trap_id] = {ch: trap_id for ch in dfa.alphabet}

    return DFA(
        num_states=dfa.num_states + 1,
        start_state=dfa.start_state,
        transitions=new_transitions,
        accept_tokens=dict(dfa.accept_tokens),
        alphabet=dfa.alphabet,
        trap_state=trap_id
    )

# 5. Минимизация ДКА (Алгоритм Хопкрофта)
def minimize_dfa_hopcroft(dfa: DFA) -> DFA:
    token_groups: Dict[Optional[str], Set[int]] = {}
    for s in range(dfa.num_states):
        rule = dfa.accept_tokens.get(s)
        key = rule.name if rule else None
        token_groups.setdefault(key, set()).add(s)

    partitions: List[FrozenSet[int]] = [frozenset(grp) for grp in token_groups.values() if grp]
    worklist: List[FrozenSet[int]] = list(partitions)

    while worklist:
        A = worklist.pop(0)
        for ch in dfa.alphabet:
            X = frozenset(s for s in range(dfa.num_states) if dfa.transitions.get(s, {}).get(ch) in A)
            if not X:
                continue

            new_partitions: List[FrozenSet[int]] = []
            for Y in partitions:
                Y1, Y2 = Y & X, Y - X
                if Y1 and Y2:
                    new_partitions.extend([Y1, Y2])
                    if Y in worklist:
                        worklist.remove(Y)
                        worklist.extend([Y1, Y2])
                    else:
                        worklist.append(Y1 if len(Y1) <= len(Y2) else Y2)
                else:
                    new_partitions.append(Y)
            partitions = new_partitions

    start_block = next(b for b in partitions if dfa.start_state in b)
    other_blocks = [b for b in partitions if b != start_block]
    ordered_blocks = [start_block] + sorted(other_blocks, key=lambda b: min(b))

    block_to_id = {b: i for i, b in enumerate(ordered_blocks)}
    state_to_new_id = {old_s: new_id for b, new_id in block_to_id.items() for old_s in b}

    min_transitions: Dict[int, Dict[str, int]] = {}
    min_accept: Dict[int, TokenRule] = {}
    min_trap_state = state_to_new_id[dfa.trap_state] if dfa.trap_state is not None else None

    for new_id, block in enumerate(ordered_blocks):
        rep = next(iter(block))
        min_transitions[new_id] = {}
        for ch in dfa.alphabet:
            dest = dfa.transitions[rep].get(ch)
            if dest is not None:
                min_transitions[new_id][ch] = state_to_new_id[dest]
        if rep in dfa.accept_tokens:
            min_accept[new_id] = dfa.accept_tokens[rep]

    return DFA(
        num_states=len(ordered_blocks),
        start_state=0,
        transitions=min_transitions,
        accept_tokens=min_accept,
        alphabet=dfa.alphabet,
        trap_state=min_trap_state
    )

# 6. Лексер и сериализация
class Token:
    __slots__ = ('type', 'lexeme', 'line', 'col')

    def __init__(self, type_: str, lexeme: str, line: int = 1, col: int = 1):
        self.type = type_
        self.lexeme = lexeme
        self.line = line
        self.col = col

    def __repr__(self):
        return f"{self.type}({self.lexeme!r}@{self.line}:{self.col})"

def simulate_dfa_exact(dfa: DFA, text: str) -> Tuple[bool, Optional[str]]:
    curr = dfa.start_state
    for ch in text:
        if ord(ch) >= 128 or ch not in dfa.alphabet:
            return False, None
        curr = dfa.transitions.get(curr, {}).get(ch, dfa.trap_state)
        if curr == dfa.trap_state:
            return False, None

    if curr in dfa.accept_tokens:
        return True, dfa.accept_tokens[curr].name
    return False, None

def tokenize(text: str, dfa: DFA) -> List[Token]:
    pos, n = 0, len(text)
    line, col = 1, 1
    tokens: List[Token] = []

    while pos < n:
        curr, i = dfa.start_state, pos
        last_accept_pos = None
        last_accept_rule = None

        while i < n:
            ch = text[i]
            if ord(ch) >= 128 or ch not in dfa.alphabet:
                break
            curr = dfa.transitions.get(curr, {}).get(ch, dfa.trap_state)
            if curr == dfa.trap_state:
                break
            if curr in dfa.accept_tokens:
                last_accept_pos = i
                last_accept_rule = dfa.accept_tokens[curr]
            i += 1

        if last_accept_pos is None:
            tokens.append(Token('ERROR', text[pos], line, col))
            if text[pos] == '\n':
                line += 1
                col = 1
            else:
                col += 1
            pos += 1
        else:
            lexeme = text[pos:last_accept_pos + 1]
            if not last_accept_rule.is_skip:
                tokens.append(Token(last_accept_rule.name, lexeme, line, col))

            for ch in lexeme:
                if ch == '\n':
                    line += 1
                    col = 1
                else:
                    col += 1
            pos = last_accept_pos + 1

    return tokens

def export_dfa_json(dfa: DFA, filepath: str = "dfa_table.json"):
    active_chars = sorted(list({ch for t in dfa.transitions.values() for ch in t.keys()}))
    data = {
        "start_state": dfa.start_state,
        "trap_state": dfa.trap_state,
        "num_states": dfa.num_states,
        "alphabet": [c for c in active_chars if 32 <= ord(c) <= 126],
        "accepting_states": {
            str(s): {
                "token": rule.name,
                "is_skip": rule.is_skip,
                "priority": rule.priority
            }
            for s, rule in dfa.accept_tokens.items()
        },
        "transitions": {
            str(s): {
                ch: dest for ch, dest in trans.items()
                if dest != dfa.trap_state and s != dfa.trap_state
            }
            for s, trans in dfa.transitions.items()
            if any(dest != dfa.trap_state for dest in trans.values())
        }
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=True)
    print(f"[+] Таблица переходов ДКА успешно сохранена в: {filepath}")

def build_pipeline() -> Tuple[DFA, Dict[str, int]]:
    nfa, nfa_start = build_combined_nfa(FUNNY_TOKEN_RULES)
    raw_dfa = nfa_to_dfa(nfa, nfa_start)
    complete_dfa = complete_dfa_with_trap(raw_dfa)
    min_dfa = minimize_dfa_hopcroft(complete_dfa)
    stats = {
        'nfa_states': nfa.num_states,
        'dfa_states': raw_dfa.num_states,
        'min_dfa_states': min_dfa.num_states
    }
    return min_dfa, stats

def main():
    parser = argparse.ArgumentParser(description="HW1: Лексер Funny (DFA Generator)")
    parser.add_argument("--export", type=str, default="dfa_table.json", help="Путь для JSON таблицы")
    parser.add_argument("--tokenize", type=str, help="Разобрать переданный текст на токены")
    args = parser.parse_args()

    min_dfa, stats = build_pipeline()
    print(f"[*] НКА: {stats['nfa_states']} состояний")
    print(f"[*] ДКА до минимизации: {stats['dfa_states']} состояний")
    print(f"[*] Минимизированный ДКА: {stats['min_dfa_states']} состояний (ловушка = {min_dfa.trap_state})\n")

    if args.export:
        export_dfa_json(min_dfa, args.export)

    if args.tokenize:
        tokens = tokenize(args.tokenize, min_dfa)
        print(f"[+] Распознано {len(tokens)} токенов:")
        for t in tokens:
            print(f"    {t}")

if __name__ == "__main__":
    main()