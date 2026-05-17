"""Orquestrador da analise semantica.

Este modulo nao valida detalhes diretamente. Ele coordena os tres blocos da
semantica:
- `symbols.py`: cria tabelas de simbolos;
- `expressions.py`: infere/valida tipos de expressoes;
- `statements.py`: valida atribuicoes, I/O, labels, DO, IF e CALL.
"""

from __future__ import annotations

from ..ast_nodes import Program, SymbolInfo
from .context import SemanticContext
from .expressions import ExpressionAnalyzer
from .statements import StatementAnalyzer
from .symbols import SymbolTableBuilder


class SemanticAnalyzer:
    """Ponto de entrada unico da fase semantica."""
    def __init__(self) -> None:
        # O contexto e recriado logicamente em cada `analyze`.
        self._context = SemanticContext()

    def analyze(
        self,
        program: Program,
    ) -> tuple[dict[str, SymbolInfo], dict[str, dict[str, object]], dict[str, dict[str, object]]]:
        """Executa a analise semantica completa para um `Program`.

        Devolve:
        - simbolos globais;
        - metadados de FUNCTIONs;
        - metadados de SUBROUTINEs.
        """
        self._context.reset()

        # Primeiro declaramos tudo. Isto permite validar chamadas mesmo quando
        # a definicao aparece depois do programa principal.
        builder = SymbolTableBuilder(self._context)
        builder.collect_callable_headers(program)
        builder.declare_global_variables(program)
        builder.declare_functions(program)
        builder.declare_subroutines(program)

        expr_analyzer = ExpressionAnalyzer(self._context)
        statement_analyzer = StatementAnalyzer(self._context, expr_analyzer)

        # Valida o corpo do programa principal no escopo global.
        statement_analyzer.analyze_statement_block(
            program.statements,
            scope=self._context.symbols,
            current_callable_name=None,
            current_callable_kind=None,
        )

        # Valida cada FUNCTION no seu escopo local.
        for function_name, metadata in self._context.functions.items():
            statement_analyzer.analyze_statement_block(
                metadata["statements"],
                scope=metadata["symbols"],
                current_callable_name=function_name,
                current_callable_kind="FUNCTION",
            )

        # Valida cada SUBROUTINE no seu escopo local.
        for subroutine_name, metadata in self._context.subroutines.items():
            statement_analyzer.analyze_statement_block(
                metadata["statements"],
                scope=metadata["symbols"],
                current_callable_name=subroutine_name,
                current_callable_kind="SUBROUTINE",
            )

        # Devolvemos copias para o codegen nao depender do objeto interno.
        return (
            dict(self._context.symbols),
            builder.copy_callable_metadata(self._context.functions),
            builder.copy_callable_metadata(self._context.subroutines),
        )
