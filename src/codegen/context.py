"""Estruturas de apoio ao codegen."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..ast_nodes import SymbolInfo


@dataclass(frozen=True)
class _ActiveDoLoop:
    variable_index: int
    step_expr: object
    check_label: str
    exit_label: str


@dataclass
class _InlineFunctionContext:
    """Contexto temporario para inlining de callables."""
    tag: str
    return_label: str
    label_map: dict[int, str]
    symbols: Mapping[str, SymbolInfo]
