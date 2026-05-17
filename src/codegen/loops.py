"""Emissao de ciclos DO.

O parser representa apenas o inicio do DO (`DO 10 I = 1, N`). O fim real
aparece mais tarde quando o codegen encontra a label `10 CONTINUE`.
Por isso este modulo guarda DOs ativos ate chegar a label de fecho.
"""

from __future__ import annotations

from .context import _ActiveDoLoop
from .errors import CompilerError
from ..ast_nodes import DoLoop, Number


class LoopEmitterMixin:
    """Rotinas para emitir prologo e epilogo de loops DO."""
    def _emit_do_loop_start(self, statement: DoLoop) -> None:
        """Emite inicializacao e teste de um ciclo DO."""
        do_key = self._do_loop_key(statement.end_label)
        if do_key in self._active_do_loops_by_label:
            raise CompilerError(
                f"Nested DO loops sharing end label {statement.end_label} are not supported."
            )

        # Guardamos a variavel de controlo no slot global/local resolvido.
        variable_symbol = self._require_scalar_declared(statement.variable_name)
        variable_index = variable_symbol.base_index

        # Passo omitido em Fortran significa passo 1.
        step_expr = statement.step_expr if statement.step_expr is not None else Number(1)

        # Labels internas: uma para testar a condicao e outra para sair.
        check_label = self._new_internal_label("DO_CHECK")
        exit_label = self._new_internal_label("DO_EXIT")

        # Guardamos este DO para completar quando aparecer a label de fecho.
        self._active_do_loops_by_label[do_key] = _ActiveDoLoop(
            variable_index=variable_index,
            step_expr=step_expr,
            check_label=check_label,
            exit_label=exit_label,
        )

        # I = inicio
        self._emit_expression(statement.start_expr)
        self.instructions.append(f"STOREG {variable_index}")

        # check:
        #   if I <= fim (ou I >= fim para passo negativo) continua;
        #   senao salta para exit.
        self.instructions.append(f"{check_label}:")
        self.instructions.append(f"PUSHG {variable_index}")
        self._emit_expression(statement.end_expr)
        self.instructions.append(self._do_condition_opcode(step_expr))
        self.instructions.append(f"JZ {exit_label}")

    def _emit_do_loop_end(self, do_key: object) -> None:
        """Emite incremento e salto de volta ao teste do DO."""
        loop = self._active_do_loops_by_label.pop(do_key)

        # I = I + passo
        self.instructions.append(f"PUSHG {loop.variable_index}")
        self._emit_expression(loop.step_expr)
        self.instructions.append("ADD")
        self.instructions.append(f"STOREG {loop.variable_index}")
        # Volta ao teste; se falhar, cai na label de saida.
        self.instructions.append(f"JUMP {loop.check_label}")
        self.instructions.append(f"{loop.exit_label}:")
