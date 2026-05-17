"""Gerador principal de codigo VM.

`VMCodeGenerator` junta varios mixins especializados:
- statements;
- expressions;
- calls;
- loops;
- helpers partilhados.

Assim o ficheiro principal fica pequeno e cada familia de regras fica num
modulo proprio.
"""

from __future__ import annotations

from collections.abc import Mapping

from .calls import CallEmitterMixin
from .context import _ActiveDoLoop, _InlineFunctionContext
from .errors import CompilerError
from .expressions import ExpressionEmitterMixin
from .helpers import HelperMixin
from .loops import LoopEmitterMixin
from .statements import StatementEmitterMixin
from ..ast_nodes import Program, SymbolInfo


class VMCodeGenerator(
    StatementEmitterMixin,
    ExpressionEmitterMixin,
    CallEmitterMixin,
    LoopEmitterMixin,
    HelperMixin,
):
    """Gera codigo VM a partir da AST validada."""
    def __init__(self) -> None:
        # Lista final de instrucoes VM em texto.
        self.instructions: list[str] = []

        # Tabelas fornecidas pela semantica.
        self.symbols: dict[str, SymbolInfo] = {}
        self.functions: dict[str, dict[str, object]] = {}
        self.subroutines: dict[str, dict[str, object]] = {}

        # Estado temporario durante a geracao.
        self._internal_label_counter = 0
        self._active_do_loops_by_label: dict[object, _ActiveDoLoop] = {}
        self._inline_function_context_stack: list[_InlineFunctionContext] = []

    def compile(
        self,
        program: Program,
        symbols: Mapping[str, SymbolInfo] | None = None,
        functions: Mapping[str, dict[str, object]] | None = None,
        subroutines: Mapping[str, dict[str, object]] | None = None,
    ) -> str:
        """Compila a AST para codigo VM em texto."""
        # Reset completo para permitir reutilizar a mesma instancia.
        self.instructions = []
        self.symbols = dict(symbols) if symbols is not None else self._build_symbol_table(program)
        self.functions = dict(functions) if functions is not None else {}
        self.subroutines = dict(subroutines) if subroutines is not None else {}
        self._internal_label_counter = 0
        self._active_do_loops_by_label = {}
        self._inline_function_context_stack = []

        # FUNCTION/SUBROUTINE precisam dos metadados semanticos para inlining.
        if program.functions and functions is None:
            raise CompilerError("Semantic function metadata is required to generate FUNCTION calls.")

        if program.subroutines and subroutines is None:
            raise CompilerError("Semantic subroutine metadata is required to generate CALL statements.")

        # Prologo padrao da VM: START e reserva de slots globais.
        self.instructions.append("START")
        self.instructions.append(f"PUSHN {self._global_slots_count()}")

        # O programa principal e emitido sequencialmente.
        for statement in program.statements:
            self._emit_statement(statement)

        # Se algum DO ficou aberto, a label de fecho nunca apareceu.
        if self._active_do_loops_by_label:
            missing = ", ".join(self._format_do_key(key) for key in sorted(self._active_do_loops_by_label, key=str))
            raise CompilerError(f"DO loop(s) without closing label: {missing}.")

        # Epilogo padrao.
        self.instructions.append("STOP")
        return "\n".join(self.instructions)
