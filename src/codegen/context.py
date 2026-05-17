"""Estruturas pequenas usadas durante a geracao de codigo."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..ast_nodes import SymbolInfo


@dataclass(frozen=True)
class _ActiveDoLoop:
    """Estado guardado enquanto um ciclo DO ainda nao chegou ao CONTINUE."""
    # Indice global da variavel de controlo do DO.
    variable_index: int

    # Tipo da variavel de controlo (INTEGER ou REAL).
    variable_type: str

    # Expressao do passo; se o fonte omitiu o passo, isto sera Number(1).
    step_expr: object

    # Label interna onde o loop testa a condicao.
    check_label: str

    # Label interna para onde saltamos quando o loop termina.
    exit_label: str


@dataclass
class _InlineFunctionContext:
    """Contexto temporario para inlining de FUNCTION/SUBROUTINE."""
    # Prefixo unico usado para labels internas deste callable.
    tag: str

    # Label para onde RETURN salta.
    return_label: str

    # Mapeia labels Fortran do callable para labels VM unicas.
    label_map: dict[int, str]

    # Tabela de simbolos local do callable durante o inlining.
    symbols: Mapping[str, SymbolInfo]
