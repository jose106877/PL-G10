from __future__ import annotations

from collections.abc import Mapping

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
    FunctionDef,
    Goto,
    IfThenElse,
    Label,
    LogicalLiteral,
    Number,
    Print,
    Program,
    ReadArrayTarget,
    Read,
    ReadVarTarget,
    Return,
    StringLiteral,
    SubroutineDef,
    SymbolInfo,
    UnaryMinus,
    UnaryNot,
    Var,
)
from .codegen import CompilerError


class SemanticAnalyzer:
    def __init__(self) -> None:
        self.symbols: dict[str, SymbolInfo] = {}
        self.functions: dict[str, dict[str, object]] = {}
        self.subroutines: dict[str, dict[str, object]] = {}
        self._function_headers: dict[str, FunctionDef] = {}
        self._subroutine_headers: dict[str, SubroutineDef] = {}
        self._next_global_slot = 0

    def analyze(
        self,
        program: Program,
    ) -> tuple[dict[str, SymbolInfo], dict[str, dict[str, object]], dict[str, dict[str, object]]]:
        self.symbols = {}
        self.functions = {}
        self.subroutines = {}
        self._function_headers = {}
        self._subroutine_headers = {}
        self._next_global_slot = 0

        self._collect_callable_headers(program)
        self._declare_global_variables(program)
        self._declare_functions(program)
        self._declare_subroutines(program)

        self._analyze_statement_block(
            program.statements,
            scope=self.symbols,
            current_callable_name=None,
            current_callable_kind=None,
        )

        for function_name, metadata in self.functions.items():
            function_scope = metadata["symbols"]
            function_statements = metadata["statements"]
            self._analyze_statement_block(
                function_statements,
                scope=function_scope,
                current_callable_name=function_name,
                current_callable_kind="FUNCTION",
            )

        for subroutine_name, metadata in self.subroutines.items():
            subroutine_scope = metadata["symbols"]
            subroutine_statements = metadata["statements"]
            self._analyze_statement_block(
                subroutine_statements,
                scope=subroutine_scope,
                current_callable_name=subroutine_name,
                current_callable_kind="SUBROUTINE",
            )

        return (
            dict(self.symbols),
            self._copy_callable_metadata(self.functions),
            self._copy_callable_metadata(self.subroutines),
        )

    def _collect_callable_headers(self, program: Program) -> None:
        for function in program.functions:
            if function.return_type not in {"INTEGER", "REAL", "LOGICAL"}:
                raise CompilerError(f"Unsupported function return type: {function.return_type}.")

            if function.name in self._function_headers:
                raise CompilerError(f"Function {function.name} was defined more than once.")

            if len(set(function.params)) != len(function.params):
                raise CompilerError(f"Function {function.name} has duplicated parameter names.")

            self._function_headers[function.name] = function

        for subroutine in program.subroutines:
            if subroutine.name in self._subroutine_headers:
                raise CompilerError(f"Subroutine {subroutine.name} was defined more than once.")

            if subroutine.name in self._function_headers:
                raise CompilerError(f"Name {subroutine.name} is used by both FUNCTION and SUBROUTINE.")

            if len(set(subroutine.params)) != len(subroutine.params):
                raise CompilerError(f"Subroutine {subroutine.name} has duplicated parameter names.")

            self._subroutine_headers[subroutine.name] = subroutine

    def _declare_global_variables(self, program: Program) -> None:
        for declaration in program.declarations:
            if declaration.type_name not in {"INTEGER", "REAL", "LOGICAL"}:
                raise CompilerError(f"Unsupported declaration type: {declaration.type_name}")

            for item in declaration.items:
                name = item.name

                if name in self._function_headers:
                    self._validate_external_function_declaration(
                        declaration_type=declaration.type_name,
                        function_name=name,
                        size=item.size,
                    )
                    continue

                if name in self._subroutine_headers:
                    raise CompilerError(f"Subroutine {name} cannot be declared as variable.")

                if name in self.symbols:
                    raise CompilerError(f"Variable {name} was declared more than once.")

                if item.size is None:
                    self.symbols[name] = SymbolInfo(
                        type_name=declaration.type_name,
                        base_index=self._next_global_slot,
                        size=1,
                        is_array=False,
                    )
                    self._next_global_slot += 1
                    continue

                if item.size <= 0:
                    raise CompilerError(f"Array {name} must have a positive size.")

                self.symbols[name] = SymbolInfo(
                    type_name=declaration.type_name,
                    base_index=self._next_global_slot,
                    size=item.size,
                    is_array=True,
                )
                self._next_global_slot += item.size

    def _declare_functions(self, program: Program) -> None:
        for function in program.functions:
            function_symbols: dict[str, SymbolInfo] = {}

            for declaration in function.declarations:
                if declaration.type_name not in {"INTEGER", "REAL", "LOGICAL"}:
                    raise CompilerError(f"Unsupported declaration type: {declaration.type_name}")

                for item in declaration.items:
                    if item.name in function_symbols:
                        raise CompilerError(
                            f"Variable {item.name} was declared more than once in function {function.name}."
                        )

                    if item.size is None:
                        function_symbols[item.name] = SymbolInfo(
                            type_name=declaration.type_name,
                            base_index=self._next_global_slot,
                            size=1,
                            is_array=False,
                        )
                        self._next_global_slot += 1
                        continue

                    if item.size <= 0:
                        raise CompilerError(f"Array {item.name} must have a positive size.")

                    function_symbols[item.name] = SymbolInfo(
                        type_name=declaration.type_name,
                        base_index=self._next_global_slot,
                        size=item.size,
                        is_array=True,
                    )
                    self._next_global_slot += item.size

            param_types: list[str] = []
            for param in function.params:
                if param not in function_symbols:
                    raise CompilerError(
                        f"Function {function.name} parameter {param} must be declared inside the function."
                    )

                symbol = function_symbols[param]
                if symbol.is_array:
                    raise CompilerError(
                        f"Function {function.name} parameter {param} must be scalar."
                    )
                param_types.append(symbol.type_name)

            if function.name in function_symbols:
                symbol = function_symbols[function.name]
                if symbol.is_array or symbol.type_name != function.return_type:
                    raise CompilerError(
                        f"Function result variable {function.name} must match return type {function.return_type}."
                    )
            else:
                function_symbols[function.name] = SymbolInfo(
                    type_name=function.return_type,
                    base_index=self._next_global_slot,
                    size=1,
                    is_array=False,
                )
                self._next_global_slot += 1

            self.functions[function.name] = {
                "name": function.name,
                "return_type": function.return_type,
                "params": tuple(function.params),
                "param_types": tuple(param_types),
                "symbols": function_symbols,
                "statements": list(function.statements),
            }

    def _declare_subroutines(self, program: Program) -> None:
        for subroutine in program.subroutines:
            subroutine_symbols: dict[str, SymbolInfo] = {}

            for declaration in subroutine.declarations:
                if declaration.type_name not in {"INTEGER", "REAL", "LOGICAL"}:
                    raise CompilerError(f"Unsupported declaration type: {declaration.type_name}")

                for item in declaration.items:
                    if item.name in subroutine_symbols:
                        raise CompilerError(
                            f"Variable {item.name} was declared more than once in subroutine {subroutine.name}."
                        )

                    if item.size is None:
                        subroutine_symbols[item.name] = SymbolInfo(
                            type_name=declaration.type_name,
                            base_index=self._next_global_slot,
                            size=1,
                            is_array=False,
                        )
                        self._next_global_slot += 1
                        continue

                    if item.size <= 0:
                        raise CompilerError(f"Array {item.name} must have a positive size.")

                    subroutine_symbols[item.name] = SymbolInfo(
                        type_name=declaration.type_name,
                        base_index=self._next_global_slot,
                        size=item.size,
                        is_array=True,
                    )
                    self._next_global_slot += item.size

            param_types: list[str] = []
            for param in subroutine.params:
                if param not in subroutine_symbols:
                    raise CompilerError(
                        f"Subroutine {subroutine.name} parameter {param} must be declared inside the subroutine."
                    )

                symbol = subroutine_symbols[param]
                if symbol.is_array:
                    raise CompilerError(
                        f"Subroutine {subroutine.name} parameter {param} must be scalar."
                    )
                param_types.append(symbol.type_name)

            self.subroutines[subroutine.name] = {
                "name": subroutine.name,
                "params": tuple(subroutine.params),
                "param_types": tuple(param_types),
                "symbols": subroutine_symbols,
                "statements": list(subroutine.statements),
            }

    def _analyze_statement_block(
        self,
        statements,
        scope: Mapping[str, SymbolInfo],
        current_callable_name: str | None,
        current_callable_kind: str | None,
    ) -> None:
        defined_labels: set[int] = set()
        referenced_labels: set[int] = set()
        open_do_labels: list[int] = []

        for statement in statements:
            self._analyze_statement(
                statement,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
                open_do_labels=open_do_labels,
                defined_labels=defined_labels,
                referenced_labels=referenced_labels,
            )

        if open_do_labels:
            missing = ", ".join(str(label) for label in open_do_labels)
            raise CompilerError(f"DO loop(s) without closing label: {missing}.")

        undefined_labels = sorted(referenced_labels - defined_labels)
        if undefined_labels:
            labels_text = ", ".join(str(value) for value in undefined_labels)
            raise CompilerError(f"Undefined label(s) referenced by GOTO: {labels_text}.")

    def _analyze_statement(
        self,
        statement,
        *,
        scope: Mapping[str, SymbolInfo],
        current_callable_name: str | None,
        current_callable_kind: str | None,
        open_do_labels: list[int],
        defined_labels: set[int],
        referenced_labels: set[int],
    ) -> None:
        if isinstance(statement, Assign):
            target = self._require_scalar(statement.name, scope)
            self._analyze_expression(
                statement.expr,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            self._ensure_assign_compatible(
                target.type_name,
                self._expression_type(
                    statement.expr,
                    scope=scope,
                    current_callable_name=current_callable_name,
                    current_callable_kind=current_callable_kind,
                ),
            )
            return

        if isinstance(statement, ArrayAssign):
            target = self._require_array(statement.name, scope)
            self._analyze_expression(
                statement.index,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            self._analyze_expression(
                statement.expr,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            self._ensure_index_integer(
                statement.index,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            self._ensure_assign_compatible(
                target.type_name,
                self._expression_type(
                    statement.expr,
                    scope=scope,
                    current_callable_name=current_callable_name,
                    current_callable_kind=current_callable_kind,
                ),
            )
            return

        if isinstance(statement, Read):
            for target in statement.targets:
                if isinstance(target, ReadVarTarget):
                    self._require_scalar(target.name, scope)
                    continue

                if isinstance(target, ReadArrayTarget):
                    self._require_array(target.name, scope)
                    self._analyze_expression(
                        target.index,
                        scope=scope,
                        current_callable_name=current_callable_name,
                        current_callable_kind=current_callable_kind,
                    )
                    self._ensure_index_integer(
                        target.index,
                        scope=scope,
                        current_callable_name=current_callable_name,
                        current_callable_kind=current_callable_kind,
                    )
                    continue

                raise CompilerError(f"Unsupported READ target: {type(target).__name__}")
            return

        if isinstance(statement, Print):
            for value in statement.values:
                if not isinstance(value, StringLiteral):
                    self._analyze_expression(
                        value,
                        scope=scope,
                        current_callable_name=current_callable_name,
                        current_callable_kind=current_callable_kind,
                    )
            return

        if isinstance(statement, Call):
            for argument in statement.args:
                self._analyze_expression(
                    argument,
                    scope=scope,
                    current_callable_name=current_callable_name,
                    current_callable_kind=current_callable_kind,
                )

            self._validate_subroutine_call(
                statement,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            return

        if isinstance(statement, Label):
            if statement.label in defined_labels:
                raise CompilerError(f"Label {statement.label} was defined more than once.")

            defined_labels.add(statement.label)

            closing_index = self._find_last_open_do_label(open_do_labels, statement.label)
            if closing_index is not None and not isinstance(statement.statement, Continue):
                raise CompilerError(
                    f"DO loop ending at label {statement.label} requires CONTINUE at that label."
                )

            self._analyze_statement(
                statement.statement,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
                open_do_labels=open_do_labels,
                defined_labels=defined_labels,
                referenced_labels=referenced_labels,
            )

            if closing_index is not None:
                open_do_labels.pop(closing_index)
            return

        if isinstance(statement, Goto):
            referenced_labels.add(statement.label)
            return

        if isinstance(statement, DoLoop):
            loop_var = self._require_scalar(statement.variable_name, scope)
            if loop_var.type_name != "INTEGER":
                raise CompilerError("DO control variable must be INTEGER.")

            self._analyze_expression(
                statement.start_expr,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            self._analyze_expression(
                statement.end_expr,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            self._ensure_integer_compatible(
                statement.start_expr,
                "DO start expression",
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            self._ensure_integer_compatible(
                statement.end_expr,
                "DO end expression",
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )

            if statement.step_expr is not None:
                self._analyze_expression(
                    statement.step_expr,
                    scope=scope,
                    current_callable_name=current_callable_name,
                    current_callable_kind=current_callable_kind,
                )
                self._ensure_integer_compatible(
                    statement.step_expr,
                    "DO step expression",
                    scope=scope,
                    current_callable_name=current_callable_name,
                    current_callable_kind=current_callable_kind,
                )
                if isinstance(statement.step_expr, Number) and statement.step_expr.value == 0:
                    raise CompilerError("DO step value cannot be 0.")

            if statement.end_label in open_do_labels:
                raise CompilerError(
                    f"Nested DO loops sharing end label {statement.end_label} are not supported."
                )

            open_do_labels.append(statement.end_label)
            return

        if isinstance(statement, IfThenElse):
            self._analyze_expression(
                statement.condition,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            condition_type = self._expression_type(
                statement.condition,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            if condition_type != "LOGICAL":
                raise CompilerError("IF condition must be LOGICAL.")

            for inner_statement in statement.then_body:
                self._analyze_statement(
                    inner_statement,
                    scope=scope,
                    current_callable_name=current_callable_name,
                    current_callable_kind=current_callable_kind,
                    open_do_labels=open_do_labels,
                    defined_labels=defined_labels,
                    referenced_labels=referenced_labels,
                )
            if statement.else_body is not None:
                for inner_statement in statement.else_body:
                    self._analyze_statement(
                        inner_statement,
                        scope=scope,
                        current_callable_name=current_callable_name,
                        current_callable_kind=current_callable_kind,
                        open_do_labels=open_do_labels,
                        defined_labels=defined_labels,
                        referenced_labels=referenced_labels,
                    )
            return

        if isinstance(statement, Continue):
            return

        if isinstance(statement, Return):
            if current_callable_kind not in {"FUNCTION", "SUBROUTINE"}:
                raise CompilerError("RETURN is only valid inside FUNCTION or SUBROUTINE bodies.")
            return

        raise CompilerError(f"Unsupported statement node: {type(statement).__name__}")

    def _analyze_expression(
        self,
        expression,
        *,
        scope: Mapping[str, SymbolInfo],
        current_callable_name: str | None,
        current_callable_kind: str | None,
    ) -> None:
        if isinstance(expression, Number):
            return

        if isinstance(expression, FloatNumber):
            return

        if isinstance(expression, LogicalLiteral):
            return

        if isinstance(expression, Var):
            self._require_scalar(expression.name, scope)
            return

        if isinstance(expression, ArrayAccess):
            if expression.name.upper() in self.functions:
                unary_function_call = FunctionCall(name=expression.name, args=[expression.index])
                self._analyze_expression(
                    expression.index,
                    scope=scope,
                    current_callable_name=current_callable_name,
                    current_callable_kind=current_callable_kind,
                )
                self._function_result_type(
                    unary_function_call,
                    scope=scope,
                    current_callable_name=current_callable_name,
                    current_callable_kind=current_callable_kind,
                )
                return

            self._require_array(expression.name, scope)
            self._analyze_expression(
                expression.index,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            self._ensure_index_integer(
                expression.index,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            return

        if isinstance(expression, FunctionCall):
            for argument in expression.args:
                self._analyze_expression(
                    argument,
                    scope=scope,
                    current_callable_name=current_callable_name,
                    current_callable_kind=current_callable_kind,
                )
            self._function_result_type(
                expression,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            return

        if isinstance(expression, UnaryMinus):
            self._analyze_expression(
                expression.expr,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            expr_type = self._expression_type(
                expression.expr,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            if not self._is_numeric(expr_type):
                raise CompilerError("Unary minus requires numeric expression.")
            return

        if isinstance(expression, UnaryNot):
            self._analyze_expression(
                expression.expr,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            expr_type = self._expression_type(
                expression.expr,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            if expr_type != "LOGICAL":
                raise CompilerError(".NOT. requires LOGICAL expression.")
            return

        if isinstance(expression, BinOp):
            self._analyze_expression(
                expression.left,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            self._analyze_expression(
                expression.right,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            self._binary_result_type(
                expression.op,
                self._expression_type(
                    expression.left,
                    scope=scope,
                    current_callable_name=current_callable_name,
                    current_callable_kind=current_callable_kind,
                ),
                self._expression_type(
                    expression.right,
                    scope=scope,
                    current_callable_name=current_callable_name,
                    current_callable_kind=current_callable_kind,
                ),
            )
            return

        raise CompilerError(f"Unsupported expression node: {type(expression).__name__}")

    def _require_declared(self, name: str, scope: Mapping[str, SymbolInfo]) -> SymbolInfo:
        if name in scope:
            return scope[name]

        if scope is not self.symbols and name in self.symbols:
            return self.symbols[name]

        if name in self._function_headers:
            raise CompilerError(
                f"Function {name} cannot be used as scalar variable in this context."
            )

        if name in self._subroutine_headers:
            raise CompilerError(
                f"Subroutine {name} cannot be used as scalar variable in this context."
            )

        if name not in self.symbols:
            raise CompilerError(f"Variable {name} used before declaration.")

        return self.symbols[name]

    def _require_scalar(self, name: str, scope: Mapping[str, SymbolInfo]) -> SymbolInfo:
        symbol = self._require_declared(name, scope)
        if symbol.is_array:
            raise CompilerError(f"Array {name} requires an index.")

        return symbol

    def _require_array(self, name: str, scope: Mapping[str, SymbolInfo]) -> SymbolInfo:
        symbol = self._require_declared(name, scope)
        if not symbol.is_array:
            raise CompilerError(f"Variable {name} is not an array.")

        return symbol

    def _expression_type(
        self,
        expression,
        *,
        scope: Mapping[str, SymbolInfo],
        current_callable_name: str | None,
        current_callable_kind: str | None,
    ) -> str:
        if isinstance(expression, Number):
            return "INTEGER"
        if isinstance(expression, FloatNumber):
            return "REAL"
        if isinstance(expression, LogicalLiteral):
            return "LOGICAL"
        if isinstance(expression, Var):
            return self._require_scalar(expression.name, scope).type_name
        if isinstance(expression, ArrayAccess):
            if expression.name.upper() in self.functions:
                return self._function_result_type(
                    FunctionCall(name=expression.name, args=[expression.index]),
                    scope=scope,
                    current_callable_name=current_callable_name,
                    current_callable_kind=current_callable_kind,
                )
            return self._require_array(expression.name, scope).type_name
        if isinstance(expression, FunctionCall):
            return self._function_result_type(
                expression,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
        if isinstance(expression, UnaryMinus):
            expr_type = self._expression_type(
                expression.expr,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            if not self._is_numeric(expr_type):
                raise CompilerError("Unary minus requires numeric expression.")
            return expr_type
        if isinstance(expression, UnaryNot):
            expr_type = self._expression_type(
                expression.expr,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            if expr_type != "LOGICAL":
                raise CompilerError(".NOT. requires LOGICAL expression.")
            return "LOGICAL"
        if isinstance(expression, BinOp):
            left_type = self._expression_type(
                expression.left,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            right_type = self._expression_type(
                expression.right,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            return self._binary_result_type(expression.op, left_type, right_type)

        raise CompilerError(f"Unsupported expression node: {type(expression).__name__}")

    def _binary_result_type(self, operator: str, left_type: str, right_type: str) -> str:
        if operator in {"+", "-", "*", "/"}:
            if not self._is_numeric(left_type) or not self._is_numeric(right_type):
                raise CompilerError(f"Operator {operator} requires numeric operands.")
            if left_type == "REAL" or right_type == "REAL":
                return "REAL"
            return "INTEGER"

        if operator in {"LT", "LE", "GT", "GE"}:
            if not self._is_numeric(left_type) or not self._is_numeric(right_type):
                raise CompilerError(f"Operator {operator} requires numeric operands.")
            return "LOGICAL"

        if operator in {"EQ", "NE"}:
            if self._is_numeric(left_type) and self._is_numeric(right_type):
                return "LOGICAL"
            if left_type == right_type:
                return "LOGICAL"
            raise CompilerError(f"Operator {operator} received incompatible types: {left_type} and {right_type}.")

        if operator in {"AND", "OR"}:
            if left_type != "LOGICAL" or right_type != "LOGICAL":
                raise CompilerError(f"Operator {operator} requires LOGICAL operands.")
            return "LOGICAL"

        raise CompilerError(f"Unsupported operator: {operator}")

    def _function_result_type(
        self,
        expression: FunctionCall,
        *,
        scope: Mapping[str, SymbolInfo],
        current_callable_name: str | None,
        current_callable_kind: str | None,
    ) -> str:
        name = expression.name.upper()
        if name == "MOD":
            if len(expression.args) != 2:
                raise CompilerError("MOD requires exactly 2 arguments.")

            left_type = self._expression_type(
                expression.args[0],
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            right_type = self._expression_type(
                expression.args[1],
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            if left_type != "INTEGER" or right_type != "INTEGER":
                raise CompilerError("MOD requires INTEGER arguments.")
            return "INTEGER"

        if name not in self.functions:
            raise CompilerError(f"Unsupported function call: {expression.name}.")

        if current_callable_kind == "FUNCTION" and name == current_callable_name:
            raise CompilerError("Recursive FUNCTION calls are not supported.")

        metadata = self.functions[name]
        expected_types = metadata["param_types"]
        if len(expression.args) != len(expected_types):
            raise CompilerError(
                f"Function {name} expects {len(expected_types)} arguments, got {len(expression.args)}."
            )

        for argument, expected_type in zip(expression.args, expected_types):
            actual_type = self._expression_type(
                argument,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            self._ensure_assign_compatible(expected_type, actual_type)

        return metadata["return_type"]

    def _validate_subroutine_call(
        self,
        statement: Call,
        *,
        scope: Mapping[str, SymbolInfo],
        current_callable_name: str | None,
        current_callable_kind: str | None,
    ) -> None:
        name = statement.name.upper()

        if name in self.functions:
            raise CompilerError(f"CALL requires SUBROUTINE, but {name} is a FUNCTION.")

        if name not in self.subroutines:
            raise CompilerError(f"Unsupported subroutine call: {statement.name}.")

        if current_callable_kind == "SUBROUTINE" and name == current_callable_name:
            raise CompilerError("Recursive SUBROUTINE calls are not supported.")

        metadata = self.subroutines[name]
        expected_types = metadata["param_types"]

        if len(statement.args) != len(expected_types):
            raise CompilerError(
                f"Subroutine {name} expects {len(expected_types)} arguments, got {len(statement.args)}."
            )

        for argument, expected_type in zip(statement.args, expected_types):
            actual_type = self._expression_type(
                argument,
                scope=scope,
                current_callable_name=current_callable_name,
                current_callable_kind=current_callable_kind,
            )
            self._ensure_assign_compatible(expected_type, actual_type)

    def _ensure_assign_compatible(self, target_type: str, source_type: str) -> None:
        if target_type == source_type:
            return

        if target_type == "REAL" and source_type == "INTEGER":
            return
        if target_type == "INTEGER" and source_type == "REAL":
            return

        raise CompilerError(f"Cannot assign {source_type} expression to {target_type} variable.")

    def _ensure_integer_compatible(
        self,
        expression,
        description: str,
        *,
        scope: Mapping[str, SymbolInfo],
        current_callable_name: str | None,
        current_callable_kind: str | None,
    ) -> None:
        expr_type = self._expression_type(
            expression,
            scope=scope,
            current_callable_name=current_callable_name,
            current_callable_kind=current_callable_kind,
        )
        if expr_type != "INTEGER":
            raise CompilerError(f"{description} must be INTEGER-compatible.")

    def _ensure_index_integer(
        self,
        expression,
        *,
        scope: Mapping[str, SymbolInfo],
        current_callable_name: str | None,
        current_callable_kind: str | None,
    ) -> None:
        expr_type = self._expression_type(
            expression,
            scope=scope,
            current_callable_name=current_callable_name,
            current_callable_kind=current_callable_kind,
        )
        if expr_type != "INTEGER":
            raise CompilerError("Array index must be INTEGER.")

    def _validate_external_function_declaration(
        self,
        *,
        declaration_type: str,
        function_name: str,
        size: int | None,
    ) -> None:
        function = self._function_headers[function_name]
        if size is not None:
            raise CompilerError(f"Function declaration {function_name} cannot be an array.")
        if declaration_type != function.return_type:
            raise CompilerError(
                f"Function declaration {function_name} type mismatch: expected {function.return_type}."
            )

    @staticmethod
    def _copy_callable_metadata(metadata_map: Mapping[str, dict[str, object]]) -> dict[str, dict[str, object]]:
        copied: dict[str, dict[str, object]] = {}
        for name, metadata in metadata_map.items():
            copied[name] = {
                "name": metadata["name"],
                "params": tuple(metadata["params"]),
                "param_types": tuple(metadata["param_types"]),
                "symbols": dict(metadata["symbols"]),
                "statements": list(metadata["statements"]),
            }
            if "return_type" in metadata:
                copied[name]["return_type"] = metadata["return_type"]
        return copied

    @staticmethod
    def _is_numeric(type_name: str) -> bool:
        return type_name in {"INTEGER", "REAL"}

    @staticmethod
    def _find_last_open_do_label(open_do_labels: list[int], label: int) -> int | None:
        for index in range(len(open_do_labels) - 1, -1, -1):
            if open_do_labels[index] == label:
                return index
        return None
