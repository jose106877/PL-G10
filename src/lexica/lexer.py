"""Lexer PLY para o subset de Fortran 77.

O lexer e a primeira fase depois do pre-processamento. A sua funcao e partir
texto em tokens: keywords, identificadores, numeros, strings e operadores.

O parser nunca ve caracteres soltos; ve apenas estes tokens.
"""

from __future__ import annotations

import sys

import ply.lex as lex

# Tabela de palavras reservadas. Se o texto lido pelo token `ID` for uma
# destas palavras, o token muda de `ID` para o nome da keyword.
reserved = {
    "PROGRAM": "PROGRAM",
    "INTEGER": "INTEGER",
    "REAL": "REAL",
    "LOGICAL": "LOGICAL",
    "FUNCTION": "FUNCTION",
    "SUBROUTINE": "SUBROUTINE",
    "CALL": "CALL",
    "RETURN": "RETURN",
    "DO": "DO",
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

# Lista obrigatoria do PLY: todos os nomes de tokens que o lexer pode emitir.
tokens = [
    "ID",
    "FNUMBER",
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

# Tokens simples: um caracter no fonte corresponde diretamente a um token.
t_PLUS = r"\+"
t_MINUS = r"-"
t_TIMES = r"\*"
t_DIVIDE = r"/"
t_EQUALS = r"="
t_LPAREN = r"\("
t_RPAREN = r"\)"
t_COMMA = r","

# Espacos horizontais nao interessam ao parser. Newlines interessam porque a
# gramatica usa quebras de linha para separar statements.
t_ignore = " \t\r"


# Ignora comentarios `! ...` ate ao fim da linha.
def t_COMMENT(t):
    r"\!.*"


# Reconhece literal logico verdadeiro.
def t_TRUE(t):
    r"\.[Tt][Rr][Uu][Ee]\."
    t.value = 1
    return t


# Reconhece literal logico falso.
def t_FALSE(t):
    r"\.[Ff][Aa][Ll][Ss][Ee]\."
    t.value = 0
    return t


# Operador relacional `.EQ.`.
def t_EQ_OP(t):
    r"\.[Ee][Qq]\."
    t.value = "EQ"
    return t


# Operador relacional `.NE.`.
def t_NE_OP(t):
    r"\.[Nn][Ee]\."
    t.value = "NE"
    return t


# Operador relacional `.LT.`.
def t_LT_OP(t):
    r"\.[Ll][Tt]\."
    t.value = "LT"
    return t


# Operador relacional `.LE.`.
def t_LE_OP(t):
    r"\.[Ll][Ee]\."
    t.value = "LE"
    return t


# Operador relacional `.GT.`.
def t_GT_OP(t):
    r"\.[Gg][Tt]\."
    t.value = "GT"
    return t


# Operador relacional `.GE.`.
def t_GE_OP(t):
    r"\.[Gg][Ee]\."
    t.value = "GE"
    return t


# Operador logico `.AND.`.
def t_AND_OP(t):
    r"\.[Aa][Nn][Dd]\."
    t.value = "AND"
    return t


# Operador logico `.OR.`.
def t_OR_OP(t):
    r"\.[Oo][Rr]\."
    t.value = "OR"
    return t


# Operador logico `.NOT.`.
def t_NOT_OP(t):
    r"\.[Nn][Oo][Tt]\."
    t.value = "NOT"
    return t


# Atualiza contador de linhas e passa NEWLINE ao parser.
def t_NEWLINE(t):
    r"\n+"
    t.lexer.lineno += len(t.value)
    return t


# String Fortran delimitada por apostrofos.
#
# Em Fortran, dois apostrofos dentro de uma string representam um apostrofo
# real. Por isso `"Ola ''x''"` vira `Ola 'x'`.
def t_STRING(t):
    r"'([^'\n]|'')*'"
    content = t.value[1:-1]
    t.value = content.replace("''", "'")
    return t


# Numero real simples, com parte decimal obrigatoria.
def t_FNUMBER(t):
    r"\d+\.\d+([Ee][+-]?\d+)?"
    t.value = float(t.value)
    return t


# Numero inteiro decimal.
def t_NUMBER(t):
    r"\d+"
    t.value = int(t.value)
    return t


# Identificador ou palavra reservada.
#
# Normalizamos tudo para maiusculas para que `program`, `PROGRAM` e `Program`
# sejam tratados da mesma forma.
def t_ID(t):
    r"[A-Za-z][A-Za-z0-9_]*"
    upper = t.value.upper()
    t.type = reserved.get(upper, "ID")
    t.value = upper
    return t


# Erro lexico: caracter que nenhuma regra reconheceu.
def t_error(t):
    raise SyntaxError(f"Illegal character {t.value[0]!r} at line {t.lineno}")


def build_lexer():
    """Constroi uma instancia nova do lexer PLY."""
    return lex.lex(module=sys.modules[__name__], optimize=False)
