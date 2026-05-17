"""Emissao de chamadas para FUNCTION e SUBROUTINE.

O codegen atual nao cria stack frames reais. Em vez disso, faz inlining:
- avalia argumentos;
- guarda-os nos slots dos parametros;
- emite o corpo da funcao/subrotina no ponto da chamada;
- usa labels internas para RETURN.
"""

from __future__ import annotations

from .context import _InlineFunctionContext
from .errors import CompilerError
from ..ast_nodes import Call, FunctionCall


class CallEmitterMixin:
    """Rotinas para emitir chamadas inline."""
    def _emit_function_call(self, expression: FunctionCall) -> None:
        """Emite chamada de FUNCTION (inline) ou funcao builtin."""
        name = expression.name.upper()

        # MOD e builtin da VM/subset; nao precisa de metadados de usuario.
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

            # Primeiro avaliamos argumentos no escopo do chamador e guardamos
            # nos slots dos parametros da funcao.
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

            # A partir daqui, resolucao de variaveis/labels passa a usar o
            # contexto local da funcao inlined.
            inline_context = _InlineFunctionContext(
                tag=self._new_internal_label(f"FN_{name}"),
                return_label=return_label,
                label_map={},
                symbols=function_symbols,
            )

            self._inline_function_context_stack.append(inline_context)
            try:
                # Emite corpo da funcao exatamente no ponto da chamada.
                for statement in function_statements:
                    self._emit_statement(statement)

                # Se a funcao nao fez RETURN explicito, cai naturalmente aqui.
                self.instructions.append(f"{return_label}:")

                # O valor de retorno fica na variavel com o nome da funcao.
                result_symbol = function_symbols[name]
                self.instructions.append(f"PUSHG {result_symbol.base_index}")
            finally:
                self._inline_function_context_stack.pop()
            return

        raise CompilerError(f"Unsupported function call: {expression.name}.")

    def _emit_subroutine_call(self, statement: Call) -> None:
        """Emite chamada inline de SUBROUTINE."""
        name = statement.name.upper()

        # CALL so pode apontar para SUBROUTINE, nao FUNCTION.
        if name in self.functions:
            raise CompilerError(f"CALL requires SUBROUTINE, but {name} is a FUNCTION.")

        if name not in self.subroutines:
            raise CompilerError(f"Unsupported subroutine call: {statement.name}.")

        # Tal como nas funcoes, argumentos sao copiados para parametros locais.
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

        # Contexto local para labels/variaveis da subrotina.
        inline_context = _InlineFunctionContext(
            tag=self._new_internal_label(f"SUB_{name}"),
            return_label=return_label,
            label_map={},
            symbols=subroutine_symbols,
        )

        self._inline_function_context_stack.append(inline_context)
        try:
            # Emite corpo da subrotina no ponto da chamada.
            for sub_statement in subroutine_statements:
                self._emit_statement(sub_statement)

            # RETURN salta para aqui. Se nao houver RETURN, cai aqui tambem.
            self.instructions.append(f"{return_label}:")
        finally:
            self._inline_function_context_stack.pop()
