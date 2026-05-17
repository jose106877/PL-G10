"""Nos da AST usados por todas as fases do compilador.

AST significa "Abstract Syntax Tree". Depois do parser reconhecer o texto
Fortran, ele transforma cada construcao da linguagem num destes objetos.

Exemplo:
- `A = 2 + 3` vira um `Assign`;
- `2 + 3` vira um `BinOp`;
- `PRINT *, A` vira um `Print`.

A partir daqui, a semantica, o TAC e o codegen deixam de lidar com texto e
passam a lidar com uma estrutura Python tipada e mais facil de percorrer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class Program:
    """Programa completo: corpo principal + subprogramas externos."""
    name: str
    declarations: list[Declaration]
    statements: list[Statement]
    functions: list[FunctionDef]
    subroutines: list[SubroutineDef]


@dataclass(frozen=True)
class FunctionDef:
    """Definicao de `INTEGER/REAL/LOGICAL FUNCTION NOME(...)`."""
    name: str
    return_type: str
    params: list[str]
    declarations: list[Declaration]
    statements: list[Statement]


@dataclass(frozen=True)
class SubroutineDef:
    """Definicao de `SUBROUTINE NOME(...)`."""
    name: str
    params: list[str]
    declarations: list[Declaration]
    statements: list[Statement]


@dataclass(frozen=True)
class Declaration:
    """Declaracao de tipo, por exemplo `INTEGER A, B(10)`."""
    type_name: str
    items: list[Declarator]


@dataclass(frozen=True)
class Declarator:
    """Um item dentro de uma declaracao.

    `size=None` significa escalar; `size=10` significa array com 10 posicoes.
    """
    name: str
    size: int | None = None


@dataclass(frozen=True)
class SymbolInfo:
    """Informacao que a semantica/codegen guarda sobre cada simbolo."""
    type_name: str
    base_index: int
    size: int
    is_array: bool


@dataclass(frozen=True)
class Assign:
    """Atribuicao escalar: `A = expr`."""
    name: str
    expr: Expr


@dataclass(frozen=True)
class Print:
    """Comando `PRINT *, ...`."""
    values: list[Printable]


@dataclass(frozen=True)
class Read:
    """Comando `READ *, ...`."""
    targets: list[ReadTarget]


@dataclass(frozen=True)
class ReadVarTarget:
    """Destino escalar de READ, por exemplo `READ *, A`."""
    name: str


@dataclass(frozen=True)
class ReadArrayTarget:
    """Destino array de READ, por exemplo `READ *, A(I)`."""
    name: str
    index: Expr


@dataclass(frozen=True)
class Goto:
    """Salto incondicional para uma label numerica."""
    label: int


@dataclass(frozen=True)
class Continue:
    """Statement `CONTINUE`; tambem fecha ciclos DO com label."""
    pass


@dataclass(frozen=True)
class Call:
    """Chamada de subrotina: `CALL S(...)`."""
    name: str
    args: list[Expr]


@dataclass(frozen=True)
class Return:
    """Statement `RETURN` dentro de FUNCTION/SUBROUTINE."""
    pass


@dataclass(frozen=True)
class DoLoop:
    """Inicio de ciclo `DO label I = inicio, fim[, passo]`."""
    end_label: int
    variable_name: str
    start_expr: Expr
    end_expr: Expr
    step_expr: Expr | None


@dataclass(frozen=True)
class IfThenElse:
    """Bloco `IF (...) THEN ... [ELSE ...] ENDIF`."""
    condition: Expr
    then_body: list[Statement]
    else_body: list[Statement] | None


@dataclass(frozen=True)
class Label:
    """Statement precedido de label, por exemplo `10 CONTINUE`."""
    label: int
    statement: Statement


@dataclass(frozen=True)
class Number:
    """Literal inteiro."""
    value: int


@dataclass(frozen=True)
class FloatNumber:
    """Literal real."""
    value: float


@dataclass(frozen=True)
class LogicalLiteral:
    """Literal logico `.TRUE.` ou `.FALSE.`."""
    value: bool


@dataclass(frozen=True)
class Var:
    """Referencia a variavel escalar."""
    name: str


@dataclass(frozen=True)
class ArrayAccess:
    """Leitura de array: `A(I)`.

    O parser tambem cria este no para chamadas unarias `F(X)`; depois a
    semantica/codegen distinguem pelo nome estar registado como FUNCTION.
    """
    name: str
    index: Expr


@dataclass(frozen=True)
class UnaryMinus:
    """Menos unario: `-expr`."""
    expr: Expr


@dataclass(frozen=True)
class UnaryNot:
    """Negacao logica: `.NOT. expr`."""
    expr: Expr


@dataclass(frozen=True)
class BinOp:
    """Operador binario aritmetico, relacional ou logico."""
    op: str
    left: Expr
    right: Expr


@dataclass(frozen=True)
class StringLiteral:
    """String imprimivel em `PRINT`."""
    value: str


@dataclass(frozen=True)
class FunctionCall:
    """Chamada de funcao em expressao: `F(A, B)` ou `MOD(A, B)`."""
    name: str
    args: list[Expr]


@dataclass(frozen=True)
class ArrayAssign:
    """Atribuicao a array: `A(I) = expr`."""
    name: str
    index: Expr
    expr: Expr


# Aliases de tipos para deixar assinaturas e listas mais legiveis.
Expr = Union[Number, FloatNumber, LogicalLiteral, Var, ArrayAccess, FunctionCall, UnaryMinus, UnaryNot, BinOp]
Printable = Union[Expr, StringLiteral]
ReadTarget = Union[ReadVarTarget, ReadArrayTarget]
Statement = Union[Assign, ArrayAssign, Print, Read, Goto, Continue, Call, Return, DoLoop, IfThenElse, Label]
