"""Tipos base usados pelo TAC (three-address code)."""

from __future__ import annotations

from dataclasses import dataclass

from ..ast_nodes import Expr


@dataclass(frozen=True)
class TacConst:
    """Constante TAC com valor e tipo inferido simples."""
    value: int | float | bool
    type_name: str


@dataclass(frozen=True)
class TacTempRef:
    """Referencia a um temporario TAC, por exemplo `t1`."""
    name: str


@dataclass(frozen=True)
class TacVarRef:
    """Referencia a uma variavel real do programa."""
    name: str


@dataclass(frozen=True)
class TacOpaqueExpr:
    """Expressao que nao queremos decompor em TAC.

    Arrays e chamadas de funcao podem ter efeitos/semantica propria, por isso
    ficam guardados como AST original.
    """
    expr: Expr


TacOperand = TacConst | TacTempRef | TacVarRef | TacOpaqueExpr


@dataclass(frozen=True)
class TacAssignInstr:
    """Instrucao simples: `target = value`."""
    target: str
    value: TacOperand


@dataclass(frozen=True)
class TacUnaryInstr:
    """Instrucao unaria: `target = operator value`."""
    target: str
    operator: str
    value: TacOperand


@dataclass(frozen=True)
class TacBinaryInstr:
    """Instrucao binaria: `target = left operator right`."""
    target: str
    operator: str
    left: TacOperand
    right: TacOperand


TacInstruction = TacAssignInstr | TacUnaryInstr | TacBinaryInstr


@dataclass(frozen=True)
class TacExpression:
    """Conjunto de instrucoes TAC e operando final da expressao."""
    instructions: list[TacInstruction]
    result: TacOperand
