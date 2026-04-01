from __future__ import annotations

import sys

import ply.lex as lex

reserved = {
    "PROGRAM": "PROGRAM",
    "INTEGER": "INTEGER",
    "IF": "IF",
    "THEN": "THEN",
    "ELSE": "ELSE",
    "ENDIF": "ENDIF",
    "GOTO": "GOTO",
    "CONTINUE": "CONTINUE",
    "PRINT": "PRINT",
    "READ": "READ",
    "END": "END",
}

tokens = [
    "ID",
    "NUMBER",
    "STRING",
    "PLUS",
    "MINUS",
    "TIMES",
    "DIVIDE",
    "EQUALS",
    "LPAREN",
    "RPAREN",
    "COMMA",
    "EQ_OP",
    "NE_OP",
    "LT_OP",
    "LE_OP",
    "GT_OP",
    "GE_OP",
    "AND_OP",
    "OR_OP",
    "NOT_OP",
    "TRUE",
    "FALSE",
    "NEWLINE",
] + list(reserved.values())

t_PLUS = r"\+"
t_MINUS = r"-"
t_TIMES = r"\*"
t_DIVIDE = r"/"
t_EQUALS = r"="
t_LPAREN = r"\("
t_RPAREN = r"\)"
t_COMMA = r","

t_ignore = " \t\r"


def t_COMMENT(t):
    r"\!.*"


def t_TRUE(t):
    r"\.[Tt][Rr][Uu][Ee]\."
    t.value = 1
    return t


def t_FALSE(t):
    r"\.[Ff][Aa][Ll][Ss][Ee]\."
    t.value = 0
    return t


def t_EQ_OP(t):
    r"\.[Ee][Qq]\."
    t.value = "EQ"
    return t


def t_NE_OP(t):
    r"\.[Nn][Ee]\."
    t.value = "NE"
    return t


def t_LT_OP(t):
    r"\.[Ll][Tt]\."
    t.value = "LT"
    return t


def t_LE_OP(t):
    r"\.[Ll][Ee]\."
    t.value = "LE"
    return t


def t_GT_OP(t):
    r"\.[Gg][Tt]\."
    t.value = "GT"
    return t


def t_GE_OP(t):
    r"\.[Gg][Ee]\."
    t.value = "GE"
    return t


def t_AND_OP(t):
    r"\.[Aa][Nn][Dd]\."
    t.value = "AND"
    return t


def t_OR_OP(t):
    r"\.[Oo][Rr]\."
    t.value = "OR"
    return t


def t_NOT_OP(t):
    r"\.[Nn][Oo][Tt]\."
    t.value = "NOT"
    return t


def t_NEWLINE(t):
    r"\n+"
    t.lexer.lineno += len(t.value)
    return t


def t_STRING(t):
    r"'([^'\n]|'')*'"
    content = t.value[1:-1]
    t.value = content.replace("''", "'")
    return t


def t_NUMBER(t):
    r"\d+"
    t.value = int(t.value)
    return t


def t_ID(t):
    r"[A-Za-z][A-Za-z0-9_]*"
    upper = t.value.upper()
    t.type = reserved.get(upper, "ID")
    t.value = upper
    return t


def t_error(t):
    raise SyntaxError(f"Illegal character {t.value[0]!r} at line {t.lineno}")


def build_lexer():
    return lex.lex(module=sys.modules[__name__], optimize=False)
