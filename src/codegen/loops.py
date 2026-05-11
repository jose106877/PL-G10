"""Emissao de ciclos DO."""

from __future__ import annotations

from .context import _ActiveDoLoop
from .errors import CompilerError
from ..ast_nodes import DoLoop, Number


class LoopEmitterMixin:
    """Rotinas para emitir loops DO."""
    def _emit_do_loop_start(self, statement: DoLoop) -> None:
        """Emite prologo de um ciclo DO."""
        do_key = self._do_loop_key(statement.end_label)
        if do_key in self._active_do_loops_by_label:
            raise CompilerError(
                f"Nested DO loops sharing end label {statement.end_label} are not supported."
            )

        variable_symbol = self._require_scalar_declared(statement.variable_name)
        variable_index = variable_symbol.base_index
        step_expr = statement.step_expr if statement.step_expr is not None else Number(1)

        check_label = self._new_internal_label("DO_CHECK")
        exit_label = self._new_internal_label("DO_EXIT")

        self._active_do_loops_by_label[do_key] = _ActiveDoLoop(
            variable_index=variable_index,
            step_expr=step_expr,
            check_label=check_label,
            exit_label=exit_label,
        )

        self._emit_expression(statement.start_expr)
        self.instructions.append(f"STOREG {variable_index}")

        self.instructions.append(f"{check_label}:")
        self.instructions.append(f"PUSHG {variable_index}")
        self._emit_expression(statement.end_expr)
        self.instructions.append(self._do_condition_opcode(step_expr))
        self.instructions.append(f"JZ {exit_label}")

    def _emit_do_loop_end(self, do_key: object) -> None:
        """Emite epilogo de um ciclo DO."""
        loop = self._active_do_loops_by_label.pop(do_key)

        self.instructions.append(f"PUSHG {loop.variable_index}")
        self._emit_expression(loop.step_expr)
        self.instructions.append("ADD")
        self.instructions.append(f"STOREG {loop.variable_index}")
        self.instructions.append(f"JUMP {loop.check_label}")
        self.instructions.append(f"{loop.exit_label}:")
