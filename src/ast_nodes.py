from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class Program:
    name: str
    declarations: list[Declaration]
    statements: list[Statement]


@dataclass(frozen=True)
class Declaration:
    type_name: str
    names: list[str]


@dataclass(frozen=True)
class Assign:
    name: str
    expr: Expr


@dataclass(frozen=True)
class Print:
    values: list[Printable]


@dataclass(frozen=True)
class Read:
    names: list[str]


@dataclass(frozen=True)
class Goto:
    label: int


@dataclass(frozen=True)
class Continue:
    pass


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
class Var:
    name: str


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


Expr = Union[Number, Var, UnaryMinus, UnaryNot, BinOp]
Printable = Union[Expr, StringLiteral]
Statement = Union[Assign, Print, Read, Goto, Continue, IfThenElse, Label]
