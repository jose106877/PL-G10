"""Emissao de chamadas para FUNCTION e SUBROUTINE."""

from __future__ import annotations

from .context import _InlineFunctionContext
from .errors import CompilerError
from ..ast_nodes import Call, FunctionCall


class CallEmitterMixin:
    """Rotinas para emitir chamadas inline."""
    def _emit_function_call(self, expression: FunctionCall) -> None:
        """Emite chamada de FUNCTION (inline) ou builtin."""
        name = expression.name.upper()
        if name == "MOD":
            if len(expression.args) != 2:
                raise CompilerError("MOD requires exactly 2 arguments.")
            self._emit_expression(expression.args[0])
            self._emit_expression(expression.args[1])
            self.instructions.append("MOD")
            return

        if name in self.functions:
            metadata = self.functions[name]
            params = metadata["params"]
            param_types = metadata["param_types"]
            function_symbols = metadata["symbols"]
            function_statements = metadata["statements"]

            if len(expression.args) != len(params):
                raise CompilerError(
                    f"Function {name} expects {len(params)} arguments, got {len(expression.args)}."
                )

            return_label = self._new_internal_label(f"FN_RET_{name}")
            for argument, param_name, param_type in zip(expression.args, params, param_types):
                arg_type = self._infer_expr_type(argument)
                self._emit_expression(argument)
                self._emit_assignment_coercion(arg_type, param_type)
                param_symbol = function_symbols[param_name]
                self.instructions.append(f"STOREG {param_symbol.base_index}")

            inline_context = _InlineFunctionContext(
                tag=self._new_internal_label(f"FN_{name}"),
                return_label=return_label,
                label_map={},
                symbols=function_symbols,
            )

            self._inline_function_context_stack.append(inline_context)
            try:
                for statement in function_statements:
                    self._emit_statement(statement)

                self.instructions.append(f"{return_label}:")
                result_symbol = function_symbols[name]
                self.instructions.append(f"PUSHG {result_symbol.base_index}")
            finally:
                self._inline_function_context_stack.pop()
            return

        raise CompilerError(f"Unsupported function call: {expression.name}.")

    def _emit_subroutine_call(self, statement: Call) -> None:
        """Emite chamada inline de SUBROUTINE."""
        name = statement.name.upper()

        if name in self.functions:
            raise CompilerError(f"CALL requires SUBROUTINE, but {name} is a FUNCTION.")

        if name not in self.subroutines:
            raise CompilerError(f"Unsupported subroutine call: {statement.name}.")

        metadata = self.subroutines[name]
        params = metadata["params"]
        param_types = metadata["param_types"]
        subroutine_symbols = metadata["symbols"]
        subroutine_statements = metadata["statements"]

        if len(statement.args) != len(params):
            raise CompilerError(
                f"Subroutine {name} expects {len(params)} arguments, got {len(statement.args)}."
            )

        return_label = self._new_internal_label(f"SUB_RET_{name}")
        for argument, param_name, param_type in zip(statement.args, params, param_types):
            arg_type = self._infer_expr_type(argument)
            self._emit_expression(argument)
            self._emit_assignment_coercion(arg_type, param_type)
            param_symbol = subroutine_symbols[param_name]
            self.instructions.append(f"STOREG {param_symbol.base_index}")

        inline_context = _InlineFunctionContext(
            tag=self._new_internal_label(f"SUB_{name}"),
            return_label=return_label,
            label_map={},
            symbols=subroutine_symbols,
        )

        self._inline_function_context_stack.append(inline_context)
        try:
            for sub_statement in subroutine_statements:
                self._emit_statement(sub_statement)

            self.instructions.append(f"{return_label}:")
        finally:
            self._inline_function_context_stack.pop()
