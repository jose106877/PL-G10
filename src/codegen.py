from __future__ import annotations

from .ast_nodes import (
    Assign,
    BinOp,
    Continue,
    Goto,
    IfThenElse,
    Label,
    Number,
    Print,
    Program,
    Read,
    StringLiteral,
    UnaryMinus,
    UnaryNot,
    Var,
)


class CompilerError(Exception):
    """Raised when semantic analysis or code generation fails."""


class VMCodeGenerator:
    def __init__(self) -> None:
        self.instructions: list[str] = []
        self.symbols: dict[str, int] = {}
        self._internal_label_counter = 0
        self._defined_labels: set[int] = set()
        self._referenced_labels: set[int] = set()

    def compile(self, program: Program) -> str:
        self.instructions = []
        self.symbols = {}
        self._internal_label_counter = 0
        self._defined_labels = set()
        self._referenced_labels = set()

        self._declare_variables(program)
        self._collect_label_info(program.statements)
        self._validate_referenced_labels()

        self.instructions.append("START")
        self.instructions.append(f"PUSHN {len(self.symbols)}")

        for statement in program.statements:
            self._emit_statement(statement)

        self.instructions.append("STOP")
        return "\n".join(self.instructions)

    def _declare_variables(self, program: Program) -> None:
        for declaration in program.declarations:
            if declaration.type_name != "INTEGER":
                raise CompilerError(f"Unsupported declaration type: {declaration.type_name}")

            for name in declaration.names:
                if name in self.symbols:
                    raise CompilerError(f"Variable {name} was declared more than once.")
                self.symbols[name] = len(self.symbols)

    def _emit_statement(self, statement) -> None:
        if isinstance(statement, Assign):
            index = self._require_declared(statement.name)
            self._emit_expression(statement.expr)
            self.instructions.append(f"STOREG {index}")
            return

        if isinstance(statement, Label):
            self.instructions.append(f"L{statement.label}:")
            self._emit_statement(statement.statement)
            return

        if isinstance(statement, Goto):
            self.instructions.append(f"JUMP L{statement.label}")
            return

        if isinstance(statement, Continue):
            self.instructions.append("NOP")
            return

        if isinstance(statement, IfThenElse):
            else_label = self._new_internal_label("IF_ELSE")
            end_label = self._new_internal_label("IF_END")

            self._emit_expression(statement.condition)
            self.instructions.append(f"JZ {else_label}")

            for inner_statement in statement.then_body:
                self._emit_statement(inner_statement)

            self.instructions.append(f"JUMP {end_label}")
            self.instructions.append(f"{else_label}:")

            if statement.else_body is not None:
                for inner_statement in statement.else_body:
                    self._emit_statement(inner_statement)

            self.instructions.append(f"{end_label}:")
            return

        if isinstance(statement, Read):
            for name in statement.names:
                index = self._require_declared(name)
                self.instructions.append("READ")
                self.instructions.append("ATOI")
                self.instructions.append(f"STOREG {index}")
            return

        if isinstance(statement, Print):
            for value in statement.values:
                if isinstance(value, StringLiteral):
                    escaped = self._escape_vm_string(value.value)
                    self.instructions.append(f'PUSHS "{escaped}"')
                    self.instructions.append("WRITES")
                else:
                    self._emit_expression(value)
                    self.instructions.append("WRITEI")

            self.instructions.append("WRITELN")
            return

        raise CompilerError(f"Unsupported statement node: {type(statement).__name__}")

    def _emit_expression(self, expression) -> None:
        if isinstance(expression, Number):
            self.instructions.append(f"PUSHI {expression.value}")
            return

        if isinstance(expression, Var):
            index = self._require_declared(expression.name)
            self.instructions.append(f"PUSHG {index}")
            return

        if isinstance(expression, UnaryMinus):
            self.instructions.append("PUSHI 0")
            self._emit_expression(expression.expr)
            self.instructions.append("SUB")
            return

        if isinstance(expression, UnaryNot):
            self._emit_expression(expression.expr)
            self.instructions.append("NOT")
            return

        if isinstance(expression, BinOp):
            self._emit_expression(expression.left)
            self._emit_expression(expression.right)
            if expression.op == "NE":
                self._emit_ne()
            else:
                self.instructions.append(self._binary_opcode(expression.op))
            return

        raise CompilerError(f"Unsupported expression node: {type(expression).__name__}")

    def _require_declared(self, name: str) -> int:
        if name not in self.symbols:
            raise CompilerError(f"Variable {name} used before declaration.")
        return self.symbols[name]

    @staticmethod
    def _binary_opcode(operator: str) -> str:
        mapping = {
            "+": "ADD",
            "-": "SUB",
            "*": "MUL",
            "/": "DIV",
            "EQ": "EQUAL",
            "LT": "INF",
            "LE": "INFEQ",
            "GT": "SUP",
            "GE": "SUPEQ",
            "AND": "AND",
            "OR": "OR",
        }

        if operator not in mapping:
            raise CompilerError(f"Unsupported operator: {operator}")
        return mapping[operator]

    def _emit_ne(self) -> None:
        self.instructions.append("EQUAL")
        self.instructions.append("NOT")

    def _collect_label_info(self, statements) -> None:
        for statement in statements:
            self._collect_label_info_from_statement(statement)

    def _collect_label_info_from_statement(self, statement) -> None:
        if isinstance(statement, Label):
            if statement.label in self._defined_labels:
                raise CompilerError(f"Label {statement.label} was defined more than once.")
            self._defined_labels.add(statement.label)
            self._collect_label_info_from_statement(statement.statement)
            return

        if isinstance(statement, Goto):
            self._referenced_labels.add(statement.label)
            return

        if isinstance(statement, IfThenElse):
            self._collect_label_info(statement.then_body)
            if statement.else_body is not None:
                self._collect_label_info(statement.else_body)

    def _validate_referenced_labels(self) -> None:
        undefined_labels = sorted(self._referenced_labels - self._defined_labels)
        if undefined_labels:
            labels_text = ", ".join(str(value) for value in undefined_labels)
            raise CompilerError(f"Undefined label(s) referenced by GOTO: {labels_text}.")

    def _new_internal_label(self, prefix: str) -> str:
        self._internal_label_counter += 1
        return f"{prefix}_{self._internal_label_counter}"

    @staticmethod
    def _escape_vm_string(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')
