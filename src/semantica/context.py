"""
Analisador Semantico - Contexto
===============================

Armazena o estado partilhado da analise semantica.

Inclui:
- Tabelas de simbolos globais
- Metadados de funcoes e subrotinas
- Contador de slots globais
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ast_nodes import FunctionDef, SubroutineDef, SymbolInfo


@dataclass
class SemanticContext:
    """Estado partilhado entre as fases da analise semantica."""
    symbols: dict[str, SymbolInfo] = field(default_factory=dict)
    functions: dict[str, dict[str, object]] = field(default_factory=dict)
    subroutines: dict[str, dict[str, object]] = field(default_factory=dict)
    function_headers: dict[str, FunctionDef] = field(default_factory=dict)
    subroutine_headers: dict[str, SubroutineDef] = field(default_factory=dict)
    next_global_slot: int = 0

    def reset(self) -> None:
        """Reinicia o contexto para uma nova analise."""
        self.symbols = {}
        self.functions = {}
        self.subroutines = {}
        self.function_headers = {}
        self.subroutine_headers = {}
        self.next_global_slot = 0
