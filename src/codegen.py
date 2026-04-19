from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .ast_nodes import (
    ArrayAccess,
    ArrayAssign,
    Assign,
    BinOp,
    Call,
    Continue,
    DoLoop,
    FloatNumber,
    FunctionCall,
    Goto,
    IfThenElse,
    Label,
    LogicalLiteral,
    Number,
    Print,
    Program,
    Read,
    ReadArrayTarget,
    ReadVarTarget,
    Return,
    StringLiteral,
    SymbolInfo,
    UnaryMinus,
    UnaryNot,
    Var,
)


class CompilerError(Exception):
    """Raised when semantic analysis or code generation fails."""


@dataclass(frozen=True)
class _ActiveDoLoop:
    variable_index: int
    step_expr: object
    check_label: str
    exit_label: str


@dataclass
class _InlineFunctionContext:
    tag: str
    return_label: str
    label_map: dict[int, str]
    symbols: Mapping[str, SymbolInfo]


class VMCodeGenerator:
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

    def _build_symbol_table(self, program: Program) -> dict[str, SymbolInfo]:
        # Defensive fallback for direct codegen usage without semantic phase.
        symbols: dict[str, SymbolInfo] = {}
        next_slot = 0

        for declaration in program.declarations:
            if declaration.type_name not in {"INTEGER", "REAL", "LOGICAL"}:
                raise CompilerError(f"Unsupported declaration type: {declaration.type_name}")

            for item in declaration.items:
                name = item.name
                if name in symbols:
                    raise CompilerError(f"Variable {name} was declared more than once.")

                if item.size is None:
                    symbols[name] = SymbolInfo(
                        type_name=declaration.type_name,
                        base_index=next_slot,
                        size=1,
                        is_array=False,
                    )
                    next_slot += 1
                    continue

                if item.size <= 0:
                    raise CompilerError(f"Array {name} must have a positive size.")

                symbols[name] = SymbolInfo(
                    type_name=declaration.type_name,
                    base_index=next_slot,
                    size=item.size,
                    is_array=True,
                )
                next_slot += item.size

        return symbols

    def _emit_statement(self, statement) -> None:
        if isinstance(statement, Assign):
            symbol = self._require_scalar_declared(statement.name)
            expr_type = self._infer_expr_type(statement.expr)
            self._emit_expression(statement.expr)
            self._emit_assignment_coercion(expr_type, symbol.type_name)
            self.instructions.append(f"STOREG {symbol.base_index}")
            return

        if isinstance(statement, ArrayAssign):
            symbol = self._require_array_declared(statement.name)
            self.instructions.append("PUSHGP")
            self._emit_array_offset(statement.index, symbol)
            expr_type = self._infer_expr_type(statement.expr)
            self._emit_expression(statement.expr)
            self._emit_assignment_coercion(expr_type, symbol.type_name)
            self.instructions.append("STOREN")
            return

        if isinstance(statement, DoLoop):
            self._emit_do_loop_start(statement)
            return

        if isinstance(statement, Label):
            label_name = self._resolve_source_label(statement.label)
            self.instructions.append(f"{label_name}:")
            self._emit_statement(statement.statement)

            do_key = self._do_loop_key(statement.label)
            if do_key in self._active_do_loops_by_label:
                self._emit_do_loop_end(do_key)
            return

        if isinstance(statement, Goto):
            self.instructions.append(f"JUMP {self._resolve_source_label(statement.label)}")
            return

        if isinstance(statement, Continue):
            self.instructions.append("NOP")
            return

        if isinstance(statement, Call):
            self._emit_subroutine_call(statement)
            return

        if isinstance(statement, Return):
            inline_context = self._current_inline_context()
            if inline_context is None:
                raise CompilerError("RETURN is only supported inside FUNCTION or SUBROUTINE bodies.")
            self.instructions.append(f"JUMP {inline_context.return_label}")
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
            for target in statement.targets:
                if isinstance(target, ReadVarTarget):
                    symbol = self._require_scalar_declared(target.name)
                    self.instructions.append("READ")
                    self.instructions.append(self._read_conversion_opcode(symbol.type_name))
                    self.instructions.append(f"STOREG {symbol.base_index}")
                    continue

                if isinstance(target, ReadArrayTarget):
                    symbol = self._require_array_declared(target.name)
                    self.instructions.append("PUSHGP")
                    self._emit_array_offset(target.index, symbol)
                    self.instructions.append("READ")
                    self.instructions.append(self._read_conversion_opcode(symbol.type_name))
                    self.instructions.append("STOREN")
                    continue

                raise CompilerError(f"Unsupported READ target: {type(target).__name__}")

            return

        if isinstance(statement, Print):
            for value in statement.values:
                if isinstance(value, StringLiteral):
                    escaped = self._escape_vm_string(value.value)
                    self.instructions.append(f'PUSHS "{escaped}"')
                    self.instructions.append("WRITES")
                else:
                    expr_type = self._infer_expr_type(value)
                    self._emit_expression(value)
                    self.instructions.append("WRITEF" if expr_type == "REAL" else "WRITEI")

            self.instructions.append("WRITELN")
            return

        raise CompilerError(f"Unsupported statement node: {type(statement).__name__}")

    def _emit_expression(self, expression) -> None:
        if isinstance(expression, Number):
            self.instructions.append(f"PUSHI {expression.value}")
            return

        if isinstance(expression, FloatNumber):
            self.instructions.append(f"PUSHF {expression.value}")
            return

        if isinstance(expression, LogicalLiteral):
            self.instructions.append(f"PUSHI {1 if expression.value else 0}")
            return

        if isinstance(expression, Var):
            symbol = self._require_scalar_declared(expression.name)
            self.instructions.append(f"PUSHG {symbol.base_index}")
            return

        if isinstance(expression, ArrayAccess):
            symbol = self._require_array_declared(expression.name)
            self.instructions.append("PUSHGP")
            self._emit_array_offset(expression.index, symbol)
            self.instructions.append("LOADN")
            return

        if isinstance(expression, FunctionCall):
            self._emit_function_call(expression)
            return

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

        if isinstance(expression, UnaryNot):
            self._emit_expression(expression.expr)
            self.instructions.append("NOT")
            return

        if isinstance(expression, BinOp):
            self._emit_binary_expression(expression)
            return

        raise CompilerError(f"Unsupported expression node: {type(expression).__name__}")

    def _require_declared(self, name: str) -> SymbolInfo:
        inline_context = self._current_inline_context()
        if inline_context is not None and name in inline_context.symbols:
            return inline_context.symbols[name]

        if name not in self.symbols:
            raise CompilerError(f"Variable {name} used before declaration.")

        return self.symbols[name]

    def _require_scalar_declared(self, name: str) -> SymbolInfo:
        symbol = self._require_declared(name)
        if symbol.is_array:
            raise CompilerError(f"Array {name} requires an index.")

        return symbol

    def _require_array_declared(self, name: str) -> SymbolInfo:
        symbol = self._require_declared(name)
        if not symbol.is_array:
            raise CompilerError(f"Variable {name} is not an array.")

        return symbol

    def _emit_array_offset(self, index_expr, symbol: SymbolInfo) -> None:
        # Fortran arrays are 1-based here, so convert index to 0-based offset.
        self._emit_expression(index_expr)
        self.instructions.append(f"CHECK 1, {symbol.size}")
        self.instructions.append("PUSHI 1")
        self.instructions.append("SUB")

        if symbol.base_index != 0:
            self.instructions.append(f"PUSHI {symbol.base_index}")
            self.instructions.append("ADD")

    def _global_slots_count(self) -> int:
        if not self.symbols:
            return 0

        return max(symbol.base_index + symbol.size for symbol in self.symbols.values())

    def _emit_assignment_coercion(self, source_type: str, target_type: str) -> None:
        if source_type == target_type:
            return

        if target_type == "REAL" and source_type in {"INTEGER", "LOGICAL"}:
            self.instructions.append("ITOF")
            return

        if target_type in {"INTEGER", "LOGICAL"} and source_type == "REAL":
            self.instructions.append("FTOI")
            return

        raise CompilerError(f"Cannot assign {source_type} expression to {target_type} variable.")

    @staticmethod
    def _read_conversion_opcode(target_type: str) -> str:
        if target_type == "REAL":
            return "ATOF"
        if target_type in {"INTEGER", "LOGICAL"}:
            return "ATOI"

        raise CompilerError(f"Unsupported READ target type: {target_type}")

    def _emit_binary_expression(self, expression: BinOp) -> None:
        left_type = self._infer_expr_type(expression.left)
        right_type = self._infer_expr_type(expression.right)
        operator = expression.op

        if operator in {"AND", "OR"}:
            self._emit_expression(expression.left)
            self._emit_expression(expression.right)
            self.instructions.append("AND" if operator == "AND" else "OR")
            return

        if operator == "EQ":
            self._emit_comparable_operands(expression.left, left_type, expression.right, right_type)
            self.instructions.append("EQUAL")
            return

        if operator == "NE":
            self._emit_comparable_operands(expression.left, left_type, expression.right, right_type)
            self._emit_ne()
            return

        if operator in {"LT", "LE", "GT", "GE"}:
            use_float = left_type == "REAL" or right_type == "REAL"
            self._emit_comparable_operands(expression.left, left_type, expression.right, right_type)
            self.instructions.append(self._relational_opcode(operator, use_float))
            return

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
        self._emit_expression(left_expr)
        if use_float and left_type != "REAL":
            self.instructions.append("ITOF")

        self._emit_expression(right_expr)
        if use_float and right_type != "REAL":
            self.instructions.append("ITOF")

    def _infer_expr_type(self, expression) -> str:
        if isinstance(expression, Number):
            return "INTEGER"

        if isinstance(expression, FloatNumber):
            return "REAL"

        if isinstance(expression, LogicalLiteral):
            return "LOGICAL"

        if isinstance(expression, Var):
            return self._require_scalar_declared(expression.name).type_name

        if isinstance(expression, ArrayAccess):
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
        self.instructions.append("EQUAL")
        self.instructions.append("NOT")

    def _emit_function_call(self, expression: FunctionCall) -> None:
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
            inline_context = _InlineFunctionContext(
                tag=self._new_internal_label(f"FN_{name}"),
                return_label=return_label,
                label_map={},
                symbols=function_symbols,
            )

            self._inline_function_context_stack.append(inline_context)
            try:
                for argument, param_name, param_type in zip(expression.args, params, param_types):
                    arg_type = self._infer_expr_type(argument)
                    self._emit_expression(argument)
                    self._emit_assignment_coercion(arg_type, param_type)
                    param_symbol = function_symbols[param_name]
                    self.instructions.append(f"STOREG {param_symbol.base_index}")

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
        inline_context = _InlineFunctionContext(
            tag=self._new_internal_label(f"SUB_{name}"),
            return_label=return_label,
            label_map={},
            symbols=subroutine_symbols,
        )

        self._inline_function_context_stack.append(inline_context)
        try:
            for argument, param_name, param_type in zip(statement.args, params, param_types):
                arg_type = self._infer_expr_type(argument)
                self._emit_expression(argument)
                self._emit_assignment_coercion(arg_type, param_type)
                param_symbol = subroutine_symbols[param_name]
                self.instructions.append(f"STOREG {param_symbol.base_index}")

            for sub_statement in subroutine_statements:
                self._emit_statement(sub_statement)

            self.instructions.append(f"{return_label}:")
        finally:
            self._inline_function_context_stack.pop()

    def _emit_do_loop_start(self, statement: DoLoop) -> None:
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
        loop = self._active_do_loops_by_label.pop(do_key)

        self.instructions.append(f"PUSHG {loop.variable_index}")
        self._emit_expression(loop.step_expr)
        self.instructions.append("ADD")
        self.instructions.append(f"STOREG {loop.variable_index}")
        self.instructions.append(f"JUMP {loop.check_label}")
        self.instructions.append(f"{loop.exit_label}:")

    def _current_inline_context(self) -> _InlineFunctionContext | None:
        if not self._inline_function_context_stack:
            return None
        return self._inline_function_context_stack[-1]

    def _resolve_source_label(self, label: int) -> str:
        inline_context = self._current_inline_context()
        if inline_context is None:
            return f"L{label}"

        if label not in inline_context.label_map:
            inline_context.label_map[label] = self._new_internal_label(f"{inline_context.tag}_L{label}")

        return inline_context.label_map[label]

    def _do_loop_key(self, end_label: int) -> object:
        inline_context = self._current_inline_context()
        if inline_context is None:
            return end_label
        return (inline_context.tag, end_label)

    @staticmethod
    def _format_do_key(do_key: object) -> str:
        if isinstance(do_key, tuple) and len(do_key) == 2:
            return str(do_key[1])
        return str(do_key)

    def _new_internal_label(self, prefix: str) -> str:
        self._internal_label_counter += 1
        return f"{prefix}_{self._internal_label_counter}"

    @staticmethod
    def _do_condition_opcode(step_expr) -> str:
        if isinstance(step_expr, Number) and step_expr.value < 0:
            return "SUPEQ"
        return "INFEQ"

    @staticmethod
    def _escape_vm_string(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')
