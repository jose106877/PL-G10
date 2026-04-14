from __future__ import annotations

import sys

import ply.yacc as yacc

from .ast_nodes import (
    Assign,
    BinOp,
    Continue,
    Declaration,
    Goto,
    IfThenElse,
    Label,
    Number,
    Print,
    Program,
    Read,
    StringLiteral,
    UnaryMinus,
    UnaryNot,
    Var,
)
from .lexer import build_lexer, tokens

precedence = (
    ("left", "OR_OP"),
    ("left", "AND_OP"),
    ("nonassoc", "EQ_OP", "NE_OP", "LT_OP", "LE_OP", "GT_OP", "GE_OP"),
    ("left", "PLUS", "MINUS"),
    ("left", "TIMES", "DIVIDE"),
    ("right", "NOT_OP", "UMINUS"),
)


def p_program(p):
    "program : opt_newlines PROGRAM ID NEWLINE lines END opt_newlines"
    declarations: list[Declaration] = []
    statements = []

    for node in p[5]:
        if isinstance(node, Declaration):
            declarations.append(node)
        elif node is not None:
            statements.append(node)

    p[0] = Program(name=p[3], declarations=declarations, statements=statements)


def p_opt_newlines(p):
    """opt_newlines : opt_newlines NEWLINE
    | empty"""


def p_lines_many(p):
    "lines : lines line"
    items = p[1]
    if p[2] is not None:
        items.append(p[2])
    p[0] = items


def p_lines_empty(p):
    "lines : empty"
    p[0] = []


def p_line_declaration(p):
    "line : declaration NEWLINE"
    p[0] = p[1]


def p_line_statement(p):
    "line : statement NEWLINE"
    p[0] = p[1]


def p_line_if_statement(p):
    "line : if_statement"
    p[0] = p[1]


def p_line_labeled_statement(p):
    "line : NUMBER simple_statement NEWLINE"
    p[0] = Label(label=p[1], statement=p[2])


def p_line_empty(p):
    "line : NEWLINE"


def p_declaration_integer(p):
    "declaration : INTEGER id_list"
    p[0] = Declaration(type_name="INTEGER", names=p[2])


def p_id_list_many(p):
    "id_list : id_list COMMA ID"
    p[0] = p[1] + [p[3]]


def p_id_list_single(p):
    "id_list : ID"
    p[0] = [p[1]]


def p_statement_assign(p):
    "statement : simple_statement"
    p[0] = p[1]


def p_simple_statement_assign(p):
    "simple_statement : ID EQUALS expression"
    p[0] = Assign(name=p[1], expr=p[3])


def p_simple_statement_print(p):
    "simple_statement : PRINT TIMES COMMA print_list"
    p[0] = Print(values=p[4])


def p_simple_statement_read(p):
    "simple_statement : READ TIMES COMMA id_list"
    p[0] = Read(names=p[4])


def p_simple_statement_goto(p):
    "simple_statement : GOTO NUMBER"
    p[0] = Goto(label=p[2])


def p_simple_statement_continue(p):
    "simple_statement : CONTINUE"
    p[0] = Continue()


def p_if_statement_without_else(p):
    "if_statement : IF LPAREN expression RPAREN THEN NEWLINE block_lines ENDIF NEWLINE"
    p[0] = IfThenElse(condition=p[3], then_body=p[7], else_body=None)


def p_if_statement_with_else(p):
    "if_statement : IF LPAREN expression RPAREN THEN NEWLINE block_lines ELSE NEWLINE block_lines ENDIF NEWLINE"
    p[0] = IfThenElse(condition=p[3], then_body=p[7], else_body=p[10])


def p_block_lines_many(p):
    "block_lines : block_lines block_line"
    items = p[1]
    if p[2] is not None:
        items.append(p[2])
    p[0] = items


def p_block_lines_empty(p):
    "block_lines : empty"
    p[0] = []


def p_block_line_statement(p):
    "block_line : simple_statement NEWLINE"
    p[0] = p[1]


def p_block_line_if_statement(p):
    "block_line : if_statement"
    p[0] = p[1]


def p_block_line_labeled_statement(p):
    "block_line : NUMBER simple_statement NEWLINE"
    p[0] = Label(label=p[1], statement=p[2])


def p_block_line_empty(p):
    "block_line : NEWLINE"


def p_print_list_many(p):
    "print_list : print_list COMMA print_item"
    p[0] = p[1] + [p[3]]


def p_print_list_single(p):
    "print_list : print_item"
    p[0] = [p[1]]


def p_print_item_expr(p):
    "print_item : expression"
    p[0] = p[1]


def p_print_item_string(p):
    "print_item : STRING"
    p[0] = StringLiteral(value=p[1])


def p_expression_binop(p):
    """expression : expression PLUS expression
    | expression MINUS expression
    | expression TIMES expression
    | expression DIVIDE expression
    | expression EQ_OP expression
    | expression NE_OP expression
    | expression LT_OP expression
    | expression LE_OP expression
    | expression GT_OP expression
    | expression GE_OP expression
    | expression AND_OP expression
    | expression OR_OP expression"""
    operator_by_token = {
        "PLUS": "+",
        "MINUS": "-",
        "TIMES": "*",
        "DIVIDE": "/",
        "EQ_OP": "EQ",
        "NE_OP": "NE",
        "LT_OP": "LT",
        "LE_OP": "LE",
        "GT_OP": "GT",
        "GE_OP": "GE",
        "AND_OP": "AND",
        "OR_OP": "OR",
    }

    op = operator_by_token[p.slice[2].type]
    p[0] = BinOp(op=op, left=p[1], right=p[3])


def p_expression_group(p):
    "expression : LPAREN expression RPAREN"
    p[0] = p[2]


def p_expression_number(p):
    "expression : NUMBER"
    p[0] = Number(value=p[1])


def p_expression_var(p):
    "expression : ID"
    p[0] = Var(name=p[1])


def p_expression_uminus(p):
    "expression : MINUS expression %prec UMINUS"
    p[0] = UnaryMinus(expr=p[2])


def p_expression_not(p):
    "expression : NOT_OP expression"
    p[0] = UnaryNot(expr=p[2])


def p_expression_bool_literal(p):
    """expression : TRUE
    | FALSE"""
    p[0] = Number(value=p[1])


def p_empty(p):
    "empty :"


def p_error(token):
    if token is None:
        raise SyntaxError("Unexpected end of file.")
    raise SyntaxError(f"Syntax error at token {token.type} ({token.value!r}) line {token.lineno}")


_PARSER = None


def build_parser():
    global _PARSER
    if _PARSER is None:
        _PARSER = yacc.yacc(
            module=sys.modules[__name__],
            start="program",
            write_tables=False,
            debug=False,
        )
    return _PARSER


def parse_source(source: str) -> Program:
    parser = build_parser()
    lexer = build_lexer()
    ast = parser.parse(source, lexer=lexer)

    if ast is None:
        raise SyntaxError("No program could be parsed.")
    return ast
