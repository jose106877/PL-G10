from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class Program:
    name: str
    declarations: list[Declaration]
    statements: list[Statement]
    functions: list[FunctionDef]
    subroutines: list[SubroutineDef]


@dataclass(frozen=True)
class FunctionDef:
    name: str
    return_type: str
    params: list[str]
    declarations: list[Declaration]
    statements: list[Statement]


@dataclass(frozen=True)
class SubroutineDef:
    name: str
    params: list[str]
    declarations: list[Declaration]
    statements: list[Statement]


@dataclass(frozen=True)
class Declaration:
    type_name: str
    items: list[Declarator]


@dataclass(frozen=True)
class Declarator:
    name: str
    size: int | None = None


@dataclass(frozen=True)
class SymbolInfo:
    type_name: str
    base_index: int
    size: int
    is_array: bool


@dataclass(frozen=True)
class Assign:
    name: str
    expr: Expr


@dataclass(frozen=True)
class Print:
    values: list[Printable]


@dataclass(frozen=True)
class Read:
    targets: list[ReadTarget]


@dataclass(frozen=True)
class ReadVarTarget:
    name: str


@dataclass(frozen=True)
class ReadArrayTarget:
    name: str
    index: Expr


@dataclass(frozen=True)
class Goto:
    label: int


@dataclass(frozen=True)
class Continue:
    pass


@dataclass(frozen=True)
class Call:
    name: str
    args: list[Expr]


@dataclass(frozen=True)
class Return:
    pass


@dataclass(frozen=True)
class DoLoop:
    end_label: int
    variable_name: str
    start_expr: Expr
    end_expr: Expr
    step_expr: Expr | None


@dataclass(frozen=True)
class IfThenElse:
    condition: Expr
    then_body: list[Statement]
    else_body: list[Statement] | None


@dataclass(frozen=True)
class Label:
    label: int
    statement: Statement


@dataclass(frozen=True)
class Number:
    value: int


@dataclass(frozen=True)
class FloatNumber:
    value: float


@dataclass(frozen=True)
class LogicalLiteral:
    value: bool


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class ArrayAccess:
    name: str
    index: Expr


@dataclass(frozen=True)
class UnaryMinus:
    expr: Expr


@dataclass(frozen=True)
class UnaryNot:
    expr: Expr


@dataclass(frozen=True)
class BinOp:
    op: str
    left: Expr
    right: Expr


@dataclass(frozen=True)
class StringLiteral:
    value: str


@dataclass(frozen=True)
class FunctionCall:
    name: str
    args: list[Expr]


@dataclass(frozen=True)
class ArrayAssign:
    name: str
    index: Expr
    expr: Expr


Expr = Union[Number, FloatNumber, LogicalLiteral, Var, ArrayAccess, FunctionCall, UnaryMinus, UnaryNot, BinOp]
Printable = Union[Expr, StringLiteral]
ReadTarget = Union[ReadVarTarget, ReadArrayTarget]
Statement = Union[Assign, ArrayAssign, Print, Read, Goto, Continue, Call, Return, DoLoop, IfThenElse, Label]
