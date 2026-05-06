"""
Analisador Semantico - Orquestracao
=================================

Coordena a fase semantica: constroi tabelas de simbolos e valida statements.

Fluxo:
- Recolhe cabecalhos de FUNCTION/SUBROUTINE
- Declara variaveis globais, funcoes e subrotinas
- Valida statements do programa e de cada callable
"""

from __future__ import annotations

from ..ast_nodes import Program, SymbolInfo
from .context import SemanticContext
from .expressions import ExpressionAnalyzer
from .statements import StatementAnalyzer
from .symbols import SymbolTableBuilder


class SemanticAnalyzer:
    """Orquestra a analise semantica e devolve tabelas e metadados."""
    def __init__(self) -> None:
        self._context = SemanticContext()

    def analyze(
        self,
        program: Program,
    ) -> tuple[dict[str, SymbolInfo], dict[str, dict[str, object]], dict[str, dict[str, object]]]:
        """Executa a analise semantica completa para um Program."""
        self._context.reset()

        builder = SymbolTableBuilder(self._context)
        builder.collect_callable_headers(program)
        builder.declare_global_variables(program)
        builder.declare_functions(program)
        builder.declare_subroutines(program)

        expr_analyzer = ExpressionAnalyzer(self._context)
        statement_analyzer = StatementAnalyzer(self._context, expr_analyzer)

        statement_analyzer.analyze_statement_block(
            program.statements,
            scope=self._context.symbols,
            current_callable_name=None,
            current_callable_kind=None,
        )

        for function_name, metadata in self._context.functions.items():
            statement_analyzer.analyze_statement_block(
                metadata["statements"],
                scope=metadata["symbols"],
                current_callable_name=function_name,
                current_callable_kind="FUNCTION",
            )

        for subroutine_name, metadata in self._context.subroutines.items():
            statement_analyzer.analyze_statement_block(
                metadata["statements"],
                scope=metadata["symbols"],
                current_callable_name=subroutine_name,
                current_callable_kind="SUBROUTINE",
            )

        return (
            dict(self._context.symbols),
            builder.copy_callable_metadata(self._context.functions),
            builder.copy_callable_metadata(self._context.subroutines),
        )
