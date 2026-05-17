"""PLY parser that builds the AST from tokens."""

from __future__ import annotations

import sys

import ply.yacc as yacc

from ..ast_nodes import (
    ArrayAccess,
    ArrayAssign,
    Assign,
    BinOp,
    Call,
    Continue,
    Declarator,
    Declaration,
    DoLoop,
    FloatNumber,
    FunctionDef,
    FunctionCall,
    Goto,
    IfThenElse,
    Label,
    LogicalLiteral,
    Number,
    Print,
    Program,
    ReadArrayTarget,
    Read,
    ReadVarTarget,
    Return,
    StringLiteral,
    SubroutineDef,
    UnaryMinus,
    UnaryNot,
    Var,
)
from ..lexica.lexer import build_lexer, tokens

precedence = (
    ("left", "OR_OP"),
    ("left", "AND_OP"),
    ("nonassoc", "EQ_OP", "NE_OP", "LT_OP", "LE_OP", "GT_OP", "GE_OP"),
    ("left", "PLUS", "MINUS"),
    ("left", "TIMES", "DIVIDE"),
    ("right", "NOT_OP", "UMINUS"),
)


def p_program(p):
    "program : opt_newlines PROGRAM ID NEWLINE lines END opt_newlines external_defs_opt"
    declarations: list[Declaration] = []
    statements = []
    functions: list[FunctionDef] = []
    subroutines: list[SubroutineDef] = []

    for node in p[5]:
        if isinstance(node, Declaration):
            declarations.append(node)
        elif node is not None:
            statements.append(node)

    for node in p[8]:
        if isinstance(node, FunctionDef):
            functions.append(node)
        elif isinstance(node, SubroutineDef):
            subroutines.append(node)

    p[0] = Program(
        name=p[3],
        declarations=declarations,
        statements=statements,
        functions=functions,
        subroutines=subroutines,
    )


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


def p_external_defs_opt_many(p):
    "external_defs_opt : external_defs"
    p[0] = p[1]


def p_external_defs_opt_empty(p):
    "external_defs_opt : empty"
    p[0] = []


def p_external_defs_many(p):
    "external_defs : external_defs external_def"
    p[0] = p[1] + [p[2]]


def p_external_defs_single(p):
    "external_defs : external_def"
    p[0] = [p[1]]


def p_external_def_function(p):
    "external_def : function_def"
    p[0] = p[1]


def p_external_def_subroutine(p):
    "external_def : subroutine_def"
    p[0] = p[1]


def p_function_def(p):
    "function_def : type_spec FUNCTION ID LPAREN param_list_opt RPAREN NEWLINE lines END opt_newlines"
    declarations: list[Declaration] = []
    statements = []

    for node in p[8]:
        if isinstance(node, Declaration):
            declarations.append(node)
        elif node is not None:
            statements.append(node)

    p[0] = FunctionDef(
        name=p[3],
        return_type=p[1],
        params=p[5],
        declarations=declarations,
        statements=statements,
    )


def p_subroutine_def(p):
    "subroutine_def : SUBROUTINE ID LPAREN param_list_opt RPAREN NEWLINE lines END opt_newlines"
    declarations: list[Declaration] = []
    statements = []

    for node in p[7]:
        if isinstance(node, Declaration):
            declarations.append(node)
        elif node is not None:
            statements.append(node)

    p[0] = SubroutineDef(
        name=p[2],
        params=p[4],
        declarations=declarations,
        statements=statements,
    )


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


def p_line_labeled_if_statement(p):
    "line : NUMBER if_statement"
    p[0] = Label(label=p[1], statement=p[2])


def p_line_empty(p):
    "line : NEWLINE"


def p_declaration(p):
    "declaration : type_spec decl_list"
    p[0] = Declaration(type_name=p[1], items=p[2])


def p_type_spec(p):
    """type_spec : INTEGER
    | REAL
    | LOGICAL"""
    p[0] = p[1]


def p_decl_list_many(p):
    "decl_list : decl_list COMMA decl_item"
    p[0] = p[1] + [p[3]]


def p_decl_list_single(p):
    "decl_list : decl_item"
    p[0] = [p[1]]


def p_param_list_opt_some(p):
    "param_list_opt : param_list"
    p[0] = p[1]


def p_param_list_opt_empty(p):
    "param_list_opt : empty"
    p[0] = []


def p_param_list_many(p):
    "param_list : param_list COMMA ID"
    p[0] = p[1] + [p[3]]


def p_param_list_single(p):
    "param_list : ID"
    p[0] = [p[1]]


def p_decl_item_scalar(p):
    "decl_item : ID"
    p[0] = Declarator(name=p[1])


def p_decl_item_array(p):
    "decl_item : ID LPAREN NUMBER RPAREN"
    p[0] = Declarator(name=p[1], size=p[3])


def p_statement_assign(p):
    "statement : simple_statement"
    p[0] = p[1]


def p_simple_statement_assign(p):
    "simple_statement : ID EQUALS expression"
    p[0] = Assign(name=p[1], expr=p[3])


def p_simple_statement_array_assign(p):
    "simple_statement : ID LPAREN expression RPAREN EQUALS expression"
    p[0] = ArrayAssign(name=p[1], index=p[3], expr=p[6])


def p_simple_statement_print(p):
    "simple_statement : PRINT TIMES COMMA print_list"
    p[0] = Print(values=p[4])


def p_simple_statement_read(p):
    "simple_statement : READ TIMES COMMA read_target_list"
    p[0] = Read(targets=p[4])


def p_simple_statement_goto(p):
    "simple_statement : GOTO NUMBER"
    p[0] = Goto(label=p[2])


def p_simple_statement_continue(p):
    "simple_statement : CONTINUE"
    p[0] = Continue()


def p_simple_statement_call(p):
    "simple_statement : CALL ID LPAREN call_actual_args_opt RPAREN"
    p[0] = Call(name=p[2], args=p[4])


def p_simple_statement_return(p):
    "simple_statement : RETURN"
    p[0] = Return()


def p_simple_statement_do(p):
    "simple_statement : DO NUMBER ID EQUALS expression COMMA expression do_step_opt"
    p[0] = DoLoop(
        end_label=p[2],
        variable_name=p[3],
        start_expr=p[5],
        end_expr=p[7],
        step_expr=p[8],
    )


def p_do_step_opt(p):
    """do_step_opt : COMMA expression
    | empty"""
    if len(p) == 3:
        p[0] = p[2]
        return

    p[0] = None


def p_call_actual_args_opt_some(p):
    "call_actual_args_opt : call_actual_args"
    p[0] = p[1]


def p_call_actual_args_opt_empty(p):
    "call_actual_args_opt : empty"
    p[0] = []


def p_call_actual_args_many(p):
    "call_actual_args : call_actual_args COMMA expression"
    p[0] = p[1] + [p[3]]


def p_call_actual_args_single(p):
    "call_actual_args : expression"
    p[0] = [p[1]]


def p_read_target_list_many(p):
    "read_target_list : read_target_list COMMA read_target"
    p[0] = p[1] + [p[3]]


def p_read_target_list_single(p):
    "read_target_list : read_target"
    p[0] = [p[1]]


def p_read_target_var(p):
    "read_target : ID"
    p[0] = ReadVarTarget(name=p[1])


def p_read_target_array(p):
    "read_target : ID LPAREN expression RPAREN"
    p[0] = ReadArrayTarget(name=p[1], index=p[3])


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


def p_block_line_labeled_if_statement(p):
    "block_line : NUMBER if_statement"
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


def p_expression_float_number(p):
    "expression : FNUMBER"
    p[0] = FloatNumber(value=p[1])


def p_expression_var(p):
    "expression : ID"
    p[0] = Var(name=p[1])


def p_expression_function_call(p):
    "expression : ID LPAREN call_args RPAREN"
    p[0] = FunctionCall(name=p[1], args=p[3])


def p_call_args_many(p):
    "call_args : call_args COMMA expression"
    p[0] = p[1] + [p[3]]


def p_call_args_two(p):
    "call_args : expression COMMA expression"
    p[0] = [p[1], p[3]]


def p_expression_array_access(p):
    "expression : ID LPAREN expression RPAREN"
    p[0] = ArrayAccess(name=p[1], index=p[3])


def p_expression_uminus(p):
    "expression : MINUS expression %prec UMINUS"
    p[0] = UnaryMinus(expr=p[2])


def p_expression_not(p):
    "expression : NOT_OP expression"
    p[0] = UnaryNot(expr=p[2])


def p_expression_bool_literal(p):
    """expression : TRUE
    | FALSE"""
    p[0] = LogicalLiteral(value=bool(p[1]))


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
