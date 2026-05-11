"""Gerador principal de codigo VM."""

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
    """Gera codigo VM a partir da AST e metadados semanticos."""
    def __init__(self) -> None:
        self.instructions: list[str] = []
        self.symbols: dict[str, SymbolInfo] = {}
        self.functions: dict[str, dict[str, object]] = {}
        self.subroutines: dict[str, dict[str, object]] = {}
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
        """Compila a AST para codigo VM."""
        self.instructions = []
        self.symbols = dict(symbols) if symbols is not None else self._build_symbol_table(program)
        self.functions = dict(functions) if functions is not None else {}
        self.subroutines = dict(subroutines) if subroutines is not None else {}
        self._internal_label_counter = 0
        self._active_do_loops_by_label = {}
        self._inline_function_context_stack = []

        if program.functions and functions is None:
            raise CompilerError("Semantic function metadata is required to generate FUNCTION calls.")

        if program.subroutines and subroutines is None:
            raise CompilerError("Semantic subroutine metadata is required to generate CALL statements.")

        self.instructions.append("START")
        self.instructions.append(f"PUSHN {self._global_slots_count()}")

        for statement in program.statements:
            self._emit_statement(statement)

        if self._active_do_loops_by_label:
            missing = ", ".join(self._format_do_key(key) for key in sorted(self._active_do_loops_by_label, key=str))
            raise CompilerError(f"DO loop(s) without closing label: {missing}.")

        self.instructions.append("STOP")
        return "\n".join(self.instructions)
