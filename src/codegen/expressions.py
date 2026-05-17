"""Emissao de expressoes em codigo VM.

Convencao importante: toda expressao deixa o seu valor no topo da stack da VM.
Depois, o statement que chamou a expressao decide se faz `STOREG`, `WRITEI`,
`JZ`, etc.
"""

from __future__ import annotations

from .errors import CompilerError
from ..ast_nodes import (
    ArrayAccess,
    BinOp,
    FloatNumber,
    FunctionCall,
    LogicalLiteral,
    Number,
    UnaryMinus,
    UnaryNot,
    Var,
)


class ExpressionEmitterMixin:
    """Rotinas para transformar expressoes AST em instrucoes VM."""
    def _emit_expression(self, expression) -> None:
        """Emite codigo VM para uma expressao e deixa o resultado na stack."""
        # Literais viram PUSH imediato.
        if isinstance(expression, Number):
            self.instructions.append(f"PUSHI {expression.value}")
            return

        if isinstance(expression, FloatNumber):
            self.instructions.append(f"PUSHF {expression.value}")
            return

        if isinstance(expression, LogicalLiteral):
            self.instructions.append(f"PUSHI {1 if expression.value else 0}")
            return

        # Variavel escalar vira leitura de slot global.
        if isinstance(expression, Var):
            symbol = self._require_scalar_declared(expression.name)
            self.instructions.append(f"PUSHG {symbol.base_index}")
            return

        # Acesso a array precisa calcular endereco e depois fazer LOADN.
        if isinstance(expression, ArrayAccess):
            # Grammar parses ID(expr) as ArrayAccess; if the name is a FUNCTION,
            # this is a unary function call and must not be emitted as LOADN.
            if expression.name.upper() in self.functions:
                self._emit_function_call(FunctionCall(name=expression.name, args=[expression.index]))
                return

            symbol = self._require_array_declared(expression.name)
            self.instructions.append("PUSHGP")
            self._emit_array_offset(expression.index, symbol)
            self.instructions.append("LOADN")
            return

        # Chamadas de funcao sao emitidas pelo mixin de calls.
        if isinstance(expression, FunctionCall):
            self._emit_function_call(expression)
            return

        # Menos unario e implementado como `0 - expr`.
        if isinstance(expression, UnaryMinus):
            expr_type = self._infer_expr_type(expression.expr)
            if expr_type == "REAL":
                self.instructions.append("PUSHF 0.0")
                self._emit_expression(expression.expr)
                self.instructions.append("FSUB")
                return

            self.instructions.append("PUSHI 0")
            self._emit_expression(expression.expr)
            self.instructions.append("SUB")
            return

        # NOT e instrucao direta da VM.
        if isinstance(expression, UnaryNot):
            self._emit_expression(expression.expr)
            self.instructions.append("NOT")
            return

        # Binarios tem logica propria para tipos INTEGER/REAL/LOGICAL.
        if isinstance(expression, BinOp):
            self._emit_binary_expression(expression)
            return

        raise CompilerError(f"Unsupported expression node: {type(expression).__name__}")

    def _emit_binary_expression(self, expression: BinOp) -> None:
        """Emite codigo para operadores binarios e relacionais."""
        left_type = self._infer_expr_type(expression.left)
        right_type = self._infer_expr_type(expression.right)
        operator = expression.op

        # Operadores logicos operam diretamente sobre inteiros 0/1.
        if operator in {"AND", "OR"}:
            self._emit_expression(expression.left)
            self._emit_expression(expression.right)
            self.instructions.append("AND" if operator == "AND" else "OR")
            return

        # Igualdade/desigualdade podem precisar de coercao numerica antes.
        if operator == "EQ":
            self._emit_comparable_operands(expression.left, left_type, expression.right, right_type)
            self.instructions.append("EQUAL")
            return

        if operator == "NE":
            self._emit_comparable_operands(expression.left, left_type, expression.right, right_type)
            self._emit_ne()
            return

        # Relacionais escolhem opcode inteiro ou float.
        if operator in {"LT", "LE", "GT", "GE"}:
            use_float = left_type == "REAL" or right_type == "REAL"
            self._emit_comparable_operands(expression.left, left_type, expression.right, right_type)
            self.instructions.append(self._relational_opcode(operator, use_float))
            return

        # Aritmetica tambem escolhe opcode inteiro ou float.
        if operator in {"+", "-", "*", "/"}:
            use_float = left_type == "REAL" or right_type == "REAL"
            self._emit_numeric_operands(expression.left, left_type, expression.right, right_type, use_float)
            self.instructions.append(self._arithmetic_opcode(operator, use_float))
            return

        raise CompilerError(f"Unsupported operator: {operator}")

    def _emit_comparable_operands(
        self,
        left_expr,
        left_type: str,
        right_expr,
        right_type: str,
    ) -> None:
        """Emite dois operandos comparaveis, convertendo para float se preciso."""
        use_float = left_type == "REAL" or right_type == "REAL"
        self._emit_numeric_operands(left_expr, left_type, right_expr, right_type, use_float)

    def _emit_numeric_operands(
        self,
        left_expr,
        left_type: str,
        right_expr,
        right_type: str,
        use_float: bool,
    ) -> None:
        """Emite operandos numericos e aplica ITOF quando necessario."""
        self._emit_expression(left_expr)
        if use_float and left_type != "REAL":
            self.instructions.append("ITOF")

        self._emit_expression(right_expr)
        if use_float and right_type != "REAL":
            self.instructions.append("ITOF")

    def _infer_expr_type(self, expression) -> str:
        """Infere tipo de uma expressao durante codegen.

        A semantica ja validou tudo, mas o codegen ainda precisa do tipo para
        escolher entre opcodes inteiros (`ADD`) e reais (`FADD`), por exemplo.
        """
        if isinstance(expression, Number):
            return "INTEGER"

        if isinstance(expression, FloatNumber):
            return "REAL"

        if isinstance(expression, LogicalLiteral):
            return "LOGICAL"

        if isinstance(expression, Var):
            return self._require_scalar_declared(expression.name).type_name

        if isinstance(expression, ArrayAccess):
            if expression.name.upper() in self.functions:
                return self.functions[expression.name.upper()]["return_type"]
            return self._require_array_declared(expression.name).type_name

        if isinstance(expression, FunctionCall):
            if expression.name.upper() == "MOD":
                return "INTEGER"
            if expression.name.upper() in self.functions:
                return self.functions[expression.name.upper()]["return_type"]
            raise CompilerError(f"Unsupported function call: {expression.name}.")

        if isinstance(expression, UnaryMinus):
            return self._infer_expr_type(expression.expr)

        if isinstance(expression, UnaryNot):
            return "LOGICAL"

        if isinstance(expression, BinOp):
            if expression.op in {"AND", "OR", "EQ", "NE", "LT", "LE", "GT", "GE"}:
                return "LOGICAL"

            left_type = self._infer_expr_type(expression.left)
            right_type = self._infer_expr_type(expression.right)
            if left_type == "REAL" or right_type == "REAL":
                return "REAL"
            return "INTEGER"

        raise CompilerError(f"Unsupported expression node: {type(expression).__name__}")

    @staticmethod
    def _arithmetic_opcode(operator: str, use_float: bool) -> str:
        """Mapeia operador aritmetico para opcode VM."""
        if use_float:
            return {
                "+": "FADD",
                "-": "FSUB",
                "*": "FMUL",
                "/": "FDIV",
            }[operator]

        return {
            "+": "ADD",
            "-": "SUB",
            "*": "MUL",
            "/": "DIV",
        }[operator]

    @staticmethod
    def _relational_opcode(operator: str, use_float: bool) -> str:
        """Mapeia operador relacional para opcode VM."""
        if use_float:
            return {
                "LT": "FINF",
                "LE": "FINFEQ",
                "GT": "FSUP",
                "GE": "FSUPEQ",
            }[operator]

        return {
            "LT": "INF",
            "LE": "INFEQ",
            "GT": "SUP",
            "GE": "SUPEQ",
        }[operator]

    def _emit_ne(self) -> None:
        """A VM nao tem NE direto; fazemos EQUAL seguido de NOT."""
        self.instructions.append("EQUAL")
        self.instructions.append("NOT")
