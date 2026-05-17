"""Validacao semantica de expressoes.

Aqui respondemos a perguntas como:
- esta variavel existe?
- `A(I)` e mesmo um array?
- o indice do array e INTEGER?
- `.AND.` recebeu operandos LOGICAL?
- `MOD` recebeu dois INTEGER?

Este modulo tambem infere o tipo de cada expressao (`INTEGER`, `REAL` ou
`LOGICAL`), informacao usada tanto pela semantica como pelo codegen.
"""

from __future__ import annotations

from collections.abc import Mapping

from ..ast_nodes import (
    ArrayAccess,
    BinOp,
    FloatNumber,
    FunctionCall,
    LogicalLiteral,
    Number,
    SymbolInfo,
    UnaryMinus,
    UnaryNot,
    Var,
)
from ..codegen import CompilerError
from .context import SemanticContext


class ExpressionAnalyzer:
    """Valida expressoes usando o escopo atual."""
    def __init__(self, context: SemanticContext) -> None:
        self._ctx = context

        # Estes campos mudam conforme analisamos o programa principal, uma
        # FUNCTION ou uma SUBROUTINE.
        self._scope: Mapping[str, SymbolInfo] | None = None
        self._current_callable_name: str | None = None
        self._current_callable_kind: str | None = None

    def set_context(
        self,
        scope: Mapping[str, SymbolInfo],
        current_callable_name: str | None,
        current_callable_kind: str | None,
    ) -> None:
        """Define o escopo/callable antes de analisar um bloco."""
        self._scope = scope
        self._current_callable_name = current_callable_name
        self._current_callable_kind = current_callable_kind

    def analyze_expression(self, expression) -> None:
        """Percorre uma expressao e levanta erro se algo for invalido."""
        self._require_scope()

        # Literais sao sempre validos.
        if isinstance(expression, (Number, FloatNumber, LogicalLiteral)):
            return

        # Variaveis simples precisam existir e nao podem ser arrays.
        if isinstance(expression, Var):
            self.require_scalar(expression.name)
            return

        # `ID(expr)` pode ser array ou funcao unaria. Se `ID` for uma funcao
        # conhecida, validamos como chamada; caso contrario, como array.
        if isinstance(expression, ArrayAccess):
            if expression.name.upper() in self._ctx.functions:
                unary_function_call = FunctionCall(name=expression.name, args=[expression.index])
                self.analyze_expression(expression.index)
                self._function_result_type(unary_function_call)
                return

            self.require_array(expression.name)
            self.analyze_expression(expression.index)
            self.ensure_index_integer(expression.index)
            return

        # Chamadas de funcao validam argumentos e tipo de retorno.
        if isinstance(expression, FunctionCall):
            for argument in expression.args:
                self.analyze_expression(argument)
            self._function_result_type(expression)
            return

        # Menos unario so faz sentido sobre numeros.
        if isinstance(expression, UnaryMinus):
            self.analyze_expression(expression.expr)
            expr_type = self.expression_type(expression.expr)
            if not self._is_numeric(expr_type):
                raise CompilerError("Unary minus requires numeric expression.")
            return

        # `.NOT.` so faz sentido sobre LOGICAL.
        if isinstance(expression, UnaryNot):
            self.analyze_expression(expression.expr)
            expr_type = self.expression_type(expression.expr)
            if expr_type != "LOGICAL":
                raise CompilerError(".NOT. requires LOGICAL expression.")
            return

        # Operadores binarios validam primeiro ambos os lados e depois a
        # compatibilidade entre tipos.
        if isinstance(expression, BinOp):
            self.analyze_expression(expression.left)
            self.analyze_expression(expression.right)
            self._binary_result_type(
                expression.op,
                self.expression_type(expression.left),
                self.expression_type(expression.right),
            )
            return

        raise CompilerError(f"Unsupported expression node: {type(expression).__name__}")

    def expression_type(self, expression) -> str:
        """Infere o tipo da expressao sem gerar codigo."""
        self._require_scope()
        if isinstance(expression, Number):
            return "INTEGER"
        if isinstance(expression, FloatNumber):
            return "REAL"
        if isinstance(expression, LogicalLiteral):
            return "LOGICAL"
        if isinstance(expression, Var):
            return self.require_scalar(expression.name).type_name
        if isinstance(expression, ArrayAccess):
            if expression.name.upper() in self._ctx.functions:
                return self._function_result_type(
                    FunctionCall(name=expression.name, args=[expression.index])
                )
            return self.require_array(expression.name).type_name
        if isinstance(expression, FunctionCall):
            return self._function_result_type(expression)
        if isinstance(expression, UnaryMinus):
            expr_type = self.expression_type(expression.expr)
            if not self._is_numeric(expr_type):
                raise CompilerError("Unary minus requires numeric expression.")
            return expr_type
        if isinstance(expression, UnaryNot):
            expr_type = self.expression_type(expression.expr)
            if expr_type != "LOGICAL":
                raise CompilerError(".NOT. requires LOGICAL expression.")
            return "LOGICAL"
        if isinstance(expression, BinOp):
            left_type = self.expression_type(expression.left)
            right_type = self.expression_type(expression.right)
            return self._binary_result_type(expression.op, left_type, right_type)

        raise CompilerError(f"Unsupported expression node: {type(expression).__name__}")

    def require_declared(self, name: str) -> SymbolInfo:
        """Procura um nome no escopo local e depois no escopo global."""
        scope = self._require_scope()
        if name in scope:
            return scope[name]

        # Dentro de FUNCTION/SUBROUTINE ainda permitimos ler globais.
        if scope is not self._ctx.symbols and name in self._ctx.symbols:
            return self._ctx.symbols[name]

        # Mensagens especificas ajudam a perceber usos errados de callables.
        if name in self._ctx.function_headers:
            raise CompilerError(
                f"Function {name} cannot be used as scalar variable in this context."
            )

        if name in self._ctx.subroutine_headers:
            raise CompilerError(
                f"Subroutine {name} cannot be used as scalar variable in this context."
            )

        if name not in self._ctx.symbols:
            raise CompilerError(f"Variable {name} used before declaration.")

        return self._ctx.symbols[name]

    def require_scalar(self, name: str) -> SymbolInfo:
        """Exige que o nome exista e seja escalar."""
        symbol = self.require_declared(name)
        if symbol.is_array:
            raise CompilerError(f"Array {name} requires an index.")

        return symbol

    def require_array(self, name: str) -> SymbolInfo:
        """Exige que o nome exista e seja array."""
        symbol = self.require_declared(name)
        if not symbol.is_array:
            raise CompilerError(f"Variable {name} is not an array.")

        return symbol

    def ensure_assign_compatible(self, target_type: str, source_type: str) -> None:
        """Valida se uma expressao pode ser atribuida ao alvo."""
        if target_type == source_type:
            return

        # O subset permite conversoes numericas implicitas entre INTEGER/REAL.
        if target_type == "REAL" and source_type == "INTEGER":
            return
        if target_type == "INTEGER" and source_type == "REAL":
            return

        raise CompilerError(f"Cannot assign {source_type} expression to {target_type} variable.")

    def ensure_integer_compatible(self, expression, description: str) -> None:
        """Exige que uma expressao seja INTEGER."""
        expr_type = self.expression_type(expression)
        if expr_type != "INTEGER":
            raise CompilerError(f"{description} must be INTEGER-compatible.")

    def ensure_index_integer(self, expression) -> None:
        """Arrays deste subset so aceitam indices INTEGER."""
        expr_type = self.expression_type(expression)
        if expr_type != "INTEGER":
            raise CompilerError("Array index must be INTEGER.")

    def _binary_result_type(self, operator: str, left_type: str, right_type: str) -> str:
        """Calcula o tipo final de um operador binario e valida operandos."""
        # Aritmetica precisa de numeros; se algum lado for REAL, o resultado e
        # REAL.
        if operator in {"+", "-", "*", "/"}:
            if not self._is_numeric(left_type) or not self._is_numeric(right_type):
                raise CompilerError(f"Operator {operator} requires numeric operands.")
            if left_type == "REAL" or right_type == "REAL":
                return "REAL"
            return "INTEGER"

        # Comparacoes numericas devolvem LOGICAL.
        if operator in {"LT", "LE", "GT", "GE"}:
            if not self._is_numeric(left_type) or not self._is_numeric(right_type):
                raise CompilerError(f"Operator {operator} requires numeric operands.")
            return "LOGICAL"

        # Igualdade/desigualdade aceitam numeros misturados ou tipos iguais.
        if operator in {"EQ", "NE"}:
            if self._is_numeric(left_type) and self._is_numeric(right_type):
                return "LOGICAL"
            if left_type == right_type:
                return "LOGICAL"
            raise CompilerError(f"Operator {operator} received incompatible types: {left_type} and {right_type}.")

        # Operadores logicos so aceitam LOGICAL.
        if operator in {"AND", "OR"}:
            if left_type != "LOGICAL" or right_type != "LOGICAL":
                raise CompilerError(f"Operator {operator} requires LOGICAL operands.")
            return "LOGICAL"

        raise CompilerError(f"Unsupported operator: {operator}")

    def _function_result_type(self, expression: FunctionCall) -> str:
        """Valida uma chamada de funcao e devolve o tipo de retorno."""
        current_callable_name = self._current_callable_name
        current_callable_kind = self._current_callable_kind
        name = expression.name.upper()
        # `MOD` e uma funcao embutida do subset, nao aparece em `functions`.
        if name == "MOD":
            if len(expression.args) != 2:
                raise CompilerError("MOD requires exactly 2 arguments.")

            left_type = self.expression_type(expression.args[0])
            right_type = self.expression_type(expression.args[1])
            if left_type != "INTEGER" or right_type != "INTEGER":
                raise CompilerError("MOD requires INTEGER arguments.")
            return "INTEGER"

        if name not in self._ctx.functions:
            raise CompilerError(f"Unsupported function call: {expression.name}.")

        # Como o codegen faz inlining, recursao nao e suportada.
        if current_callable_kind == "FUNCTION" and name == current_callable_name:
            raise CompilerError("Recursive FUNCTION calls are not supported.")

        # Valida aridade e tipo dos argumentos.
        metadata = self._ctx.functions[name]
        expected_types = metadata["param_types"]
        if len(expression.args) != len(expected_types):
            raise CompilerError(
                f"Function {name} expects {len(expected_types)} arguments, got {len(expression.args)}."
            )

        for argument, expected_type in zip(expression.args, expected_types):
            actual_type = self.expression_type(argument)
            self.ensure_assign_compatible(expected_type, actual_type)

        return metadata["return_type"]

    @staticmethod
    def _is_numeric(type_name: str) -> bool:
        """INTEGER e REAL sao os tipos numericos do subset."""
        return type_name in {"INTEGER", "REAL"}

    def _require_scope(self) -> Mapping[str, SymbolInfo]:
        """Garante que `set_context` foi chamado antes da analise."""
        if self._scope is None:
            raise CompilerError("Expression analysis requires an active scope.")
        return self._scope
