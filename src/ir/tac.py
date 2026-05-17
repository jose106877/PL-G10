"""Lowering e simplificacao com TAC (three-address code).

TAC e uma forma intermedia em que cada operacao complexa e partida em passos
pequenos com temporarios. Exemplo:

    A + B * 2

vira algo como:

    t1 = B * 2
    t2 = A + t1

Neste projeto usamos TAC para otimizar expressoes localmente e depois
reconstruir uma AST simplificada. Nao geramos VM a partir do TAC diretamente.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ast_nodes import (
    ArrayAccess,
    ArrayAssign,
    Assign,
    BinOp,
    Call,
    Continue,
    DoLoop,
    Expr,
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
    Read,
    ReadArrayTarget,
    ReadVarTarget,
    Return,
    Statement,
    StringLiteral,
    SubroutineDef,
    UnaryMinus,
    UnaryNot,
    Var,
)


@dataclass(frozen=True)
class TacConst:
    """Constante TAC com valor e tipo inferido simples."""
    value: int | float | bool
    type_name: str


@dataclass(frozen=True)
class TacTempRef:
    """Referencia a um temporario TAC, por exemplo `t1`."""
    name: str


@dataclass(frozen=True)
class TacVarRef:
    """Referencia a uma variavel real do programa."""
    name: str


@dataclass(frozen=True)
class TacOpaqueExpr:
    """Expressao que nao queremos decompor em TAC.

    Arrays e chamadas de funcao podem ter efeitos/semantica propria, por isso
    ficam guardados como AST original.
    """
    expr: Expr


TacOperand = TacConst | TacTempRef | TacVarRef | TacOpaqueExpr


@dataclass(frozen=True)
class TacAssignInstr:
    """Instrucao simples: `target = value`."""
    target: str
    value: TacOperand


@dataclass(frozen=True)
class TacUnaryInstr:
    """Instrucao unaria: `target = operator value`."""
    target: str
    operator: str
    value: TacOperand


@dataclass(frozen=True)
class TacBinaryInstr:
    """Instrucao binaria: `target = left operator right`."""
    target: str
    operator: str
    left: TacOperand
    right: TacOperand


TacInstruction = TacAssignInstr | TacUnaryInstr | TacBinaryInstr


@dataclass(frozen=True)
class TacExpression:
    """Conjunto de instrucoes TAC e operando final da expressao."""
    instructions: list[TacInstruction]
    result: TacOperand


class _TacLowerer:
    """Converte uma expressao AST para instrucoes TAC."""
    def __init__(self) -> None:
        self._instructions: list[TacInstruction] = []
        self._temp_counter = 0

    def lower(self, expr: Expr) -> TacExpression:
        """Baixa uma expressao e devolve instrucoes + resultado."""
        result = self._lower_expr(expr)
        return TacExpression(instructions=list(self._instructions), result=result)

    def _new_temp(self) -> str:
        """Cria nomes `t1`, `t2`, ... para resultados intermedios."""
        self._temp_counter += 1
        return f"t{self._temp_counter}"

    def _lower_expr(self, expr: Expr) -> TacOperand:
        """Baixa recursivamente cada tipo de no de expressao."""
        # Literais e variaveis ja sao atomicos em TAC.
        if isinstance(expr, Number):
            return TacConst(value=expr.value, type_name="INTEGER")

        if isinstance(expr, FloatNumber):
            return TacConst(value=expr.value, type_name="REAL")

        if isinstance(expr, LogicalLiteral):
            return TacConst(value=expr.value, type_name="LOGICAL")

        if isinstance(expr, Var):
            return TacVarRef(name=expr.name)

        if isinstance(expr, ArrayAccess):
            return TacOpaqueExpr(expr=expr)

        if isinstance(expr, FunctionCall):
            return TacOpaqueExpr(expr=expr)

        # Operacoes unarias criam um temporario novo.
        if isinstance(expr, UnaryMinus):
            value = self._lower_expr(expr.expr)
            target = self._new_temp()
            self._instructions.append(TacUnaryInstr(target=target, operator="NEG", value=value))
            return TacTempRef(name=target)

        if isinstance(expr, UnaryNot):
            value = self._lower_expr(expr.expr)
            target = self._new_temp()
            self._instructions.append(TacUnaryInstr(target=target, operator="NOT", value=value))
            return TacTempRef(name=target)

        # Operacoes binarias baixam os dois lados e guardam o resultado num
        # temporario.
        if isinstance(expr, BinOp):
            left = self._lower_expr(expr.left)
            right = self._lower_expr(expr.right)
            target = self._new_temp()
            self._instructions.append(
                TacBinaryInstr(target=target, operator=expr.op, left=left, right=right)
            )
            return TacTempRef(name=target)

        return TacOpaqueExpr(expr=expr)


class _TacOptimizer:
    """Aplica otimizacoes locais sobre uma expressao TAC."""
    def optimize(self, tac_expr: TacExpression) -> TacExpression:
        """Executa propagacao simples, constant folding e dead code."""
        aliases: dict[str, TacOperand] = {}
        optimized: list[TacInstruction] = []

        for instruction in tac_expr.instructions:
            # Atribuicoes diretas podem criar aliases de temporarios.
            if isinstance(instruction, TacAssignInstr):
                value = self._resolve_operand(instruction.value, aliases)
                aliases[instruction.target] = value
                optimized.append(TacAssignInstr(target=instruction.target, value=value))
                continue

            # Se o operador unario recebe constante, podemos calcular ja.
            if isinstance(instruction, TacUnaryInstr):
                value = self._resolve_operand(instruction.value, aliases)
                folded = self._fold_unary(instruction.operator, value)
                if folded is not None:
                    aliases[instruction.target] = folded
                    optimized.append(TacAssignInstr(target=instruction.target, value=folded))
                else:
                    aliases[instruction.target] = TacTempRef(name=instruction.target)
                    optimized.append(
                        TacUnaryInstr(
                            target=instruction.target,
                            operator=instruction.operator,
                            value=value,
                        )
                    )
                continue

            # Operacoes binarias sao o caso mais rico: folding de constantes e
            # simplificacoes algebricas como `x + 0`.
            left = self._resolve_operand(instruction.left, aliases)
            right = self._resolve_operand(instruction.right, aliases)

            folded_binary = self._fold_binary(instruction.operator, left, right)
            if folded_binary is not None:
                aliases[instruction.target] = folded_binary
                optimized.append(TacAssignInstr(target=instruction.target, value=folded_binary))
                continue

            simplified_binary = self._simplify_binary(instruction.operator, left, right)
            if simplified_binary is not None:
                aliases[instruction.target] = simplified_binary
                optimized.append(TacAssignInstr(target=instruction.target, value=simplified_binary))
                continue

            aliases[instruction.target] = TacTempRef(name=instruction.target)
            optimized.append(
                TacBinaryInstr(
                    target=instruction.target,
                    operator=instruction.operator,
                    left=left,
                    right=right,
                )
            )

        result = self._resolve_operand(tac_expr.result, aliases)
        # Depois de substituir temporarios por constantes/variaveis, algumas
        # instrucoes podem ter ficado inutilizadas.
        pruned = self._eliminate_dead_code(optimized, result)
        return TacExpression(instructions=pruned, result=result)

    def _resolve_operand(self, operand: TacOperand, aliases: dict[str, TacOperand]) -> TacOperand:
        """Segue a cadeia de aliases ate encontrar o valor real."""
        resolved = operand
        while isinstance(resolved, TacTempRef) and resolved.name in aliases:
            next_value = aliases[resolved.name]
            if next_value == resolved:
                break
            resolved = next_value
        return resolved

    def _fold_unary(self, operator: str, value: TacOperand) -> TacConst | None:
        """Calcula operacoes unarias quando o operando e constante."""
        if not isinstance(value, TacConst):
            return None

        if operator == "NEG":
            if value.type_name == "REAL":
                return TacConst(value=-float(value.value), type_name="REAL")
            if value.type_name == "INTEGER":
                return TacConst(value=-int(value.value), type_name="INTEGER")
            return None

        if operator == "NOT" and value.type_name == "LOGICAL":
            return TacConst(value=not bool(value.value), type_name="LOGICAL")

        return None

    def _fold_binary(self, operator: str, left: TacOperand, right: TacOperand) -> TacConst | None:
        """Calcula operacoes binarias quando ambos os lados sao constantes."""
        if not isinstance(left, TacConst) or not isinstance(right, TacConst):
            return None

        if operator in {"+", "-", "*"}:
            return self._fold_arithmetic(operator, left, right)

        if operator in {"EQ", "NE", "LT", "LE", "GT", "GE"}:
            return self._fold_relational(operator, left, right)

        if operator in {"AND", "OR"}:
            return self._fold_logical(operator, left, right)

        return None

    @staticmethod
    def _fold_arithmetic(operator: str, left: TacConst, right: TacConst) -> TacConst:
        """Constant folding para `+`, `-` e `*`."""
        use_float = left.type_name == "REAL" or right.type_name == "REAL"
        left_value = float(left.value) if use_float else int(left.value)
        right_value = float(right.value) if use_float else int(right.value)

        if operator == "+":
            result = left_value + right_value
        elif operator == "-":
            result = left_value - right_value
        else:
            result = left_value * right_value

        if use_float:
            return TacConst(value=float(result), type_name="REAL")
        return TacConst(value=int(result), type_name="INTEGER")

    @staticmethod
    def _fold_relational(operator: str, left: TacConst, right: TacConst) -> TacConst:
        """Constant folding para comparacoes relacionais."""
        left_value = left.value
        right_value = right.value

        if operator == "EQ":
            result = left_value == right_value
        elif operator == "NE":
            result = left_value != right_value
        elif operator == "LT":
            result = left_value < right_value
        elif operator == "LE":
            result = left_value <= right_value
        elif operator == "GT":
            result = left_value > right_value
        else:
            result = left_value >= right_value

        return TacConst(value=bool(result), type_name="LOGICAL")

    @staticmethod
    def _fold_logical(operator: str, left: TacConst, right: TacConst) -> TacConst | None:
        """Constant folding para `.AND.` e `.OR.`."""
        if left.type_name != "LOGICAL" or right.type_name != "LOGICAL":
            return None

        if operator == "AND":
            return TacConst(value=bool(left.value) and bool(right.value), type_name="LOGICAL")
        if operator == "OR":
            return TacConst(value=bool(left.value) or bool(right.value), type_name="LOGICAL")

        return None

    def _simplify_binary(self, operator: str, left: TacOperand, right: TacOperand) -> TacOperand | None:
        """Aplica identidades simples sem precisar de conhecer valores todos."""
        # x + 0 = x, 0 + x = x
        if operator == "+":
            if self._is_zero(right):
                return left
            if self._is_zero(left):
                return right
            return None

        # x - 0 = x
        if operator == "-":
            if self._is_zero(right):
                return left
            return None

        # x * 1 = x, 1 * x = x
        if operator == "*":
            if self._is_one(right):
                return left
            if self._is_one(left):
                return right
            return None

        # x AND true = x, true AND x = x
        if operator == "AND":
            if self._is_true(right):
                return left
            if self._is_true(left):
                return right
            return None

        # x OR false = x, false OR x = x
        if operator == "OR":
            if self._is_false(right):
                return left
            if self._is_false(left):
                return right
            return None

        return None

    @staticmethod
    def _is_zero(operand: TacOperand) -> bool:
        """Verifica se o operando e constante numerica zero."""
        return isinstance(operand, TacConst) and operand.type_name in {"INTEGER", "REAL"} and operand.value == 0

    @staticmethod
    def _is_one(operand: TacOperand) -> bool:
        """Verifica se o operando e constante numerica um."""
        return isinstance(operand, TacConst) and operand.type_name in {"INTEGER", "REAL"} and operand.value == 1

    @staticmethod
    def _is_true(operand: TacOperand) -> bool:
        """Verifica constante logica verdadeira."""
        return isinstance(operand, TacConst) and operand.type_name == "LOGICAL" and bool(operand.value)

    @staticmethod
    def _is_false(operand: TacOperand) -> bool:
        """Verifica constante logica falsa."""
        return isinstance(operand, TacConst) and operand.type_name == "LOGICAL" and not bool(operand.value)

    def _eliminate_dead_code(self, instructions: list[TacInstruction], result: TacOperand) -> list[TacInstruction]:
        """Remove instrucoes que calculam temporarios nunca usados."""
        used_temps = set(self._temp_names_in_operand(result))
        kept_reversed: list[TacInstruction] = []

        for instruction in reversed(instructions):
            target = instruction.target
            if target not in used_temps:
                continue

            kept_reversed.append(instruction)
            used_temps.discard(target)

            if isinstance(instruction, TacAssignInstr):
                used_temps.update(self._temp_names_in_operand(instruction.value))
            elif isinstance(instruction, TacUnaryInstr):
                used_temps.update(self._temp_names_in_operand(instruction.value))
            else:
                used_temps.update(self._temp_names_in_operand(instruction.left))
                used_temps.update(self._temp_names_in_operand(instruction.right))

        kept_reversed.reverse()
        return kept_reversed

    @staticmethod
    def _temp_names_in_operand(operand: TacOperand) -> set[str]:
        """Devolve o nome do temporario usado por um operando, se existir."""
        if isinstance(operand, TacTempRef):
            return {operand.name}
        return set()


class _TacRebuilder:
    """Reconstroi uma expressao AST a partir do TAC otimizado."""
    def rebuild(self, tac_expr: TacExpression) -> Expr:
        """Converte instrucoes TAC simplificadas de volta para AST."""
        values: dict[str, Expr] = {}

        for instruction in tac_expr.instructions:
            # Cada temporario passa a apontar para uma expressao AST.
            if isinstance(instruction, TacAssignInstr):
                values[instruction.target] = self._operand_to_expr(instruction.value, values)
                continue

            if isinstance(instruction, TacUnaryInstr):
                value_expr = self._operand_to_expr(instruction.value, values)
                if instruction.operator == "NEG":
                    values[instruction.target] = UnaryMinus(expr=value_expr)
                else:
                    values[instruction.target] = UnaryNot(expr=value_expr)
                continue

            left_expr = self._operand_to_expr(instruction.left, values)
            right_expr = self._operand_to_expr(instruction.right, values)
            values[instruction.target] = BinOp(op=instruction.operator, left=left_expr, right=right_expr)

        return self._operand_to_expr(tac_expr.result, values)

    def _operand_to_expr(self, operand: TacOperand, values: dict[str, Expr]) -> Expr:
        """Transforma um operando TAC no no AST equivalente."""
        if isinstance(operand, TacConst):
            if operand.type_name == "REAL":
                return FloatNumber(value=float(operand.value))
            if operand.type_name == "LOGICAL":
                return LogicalLiteral(value=bool(operand.value))
            return Number(value=int(operand.value))

        if isinstance(operand, TacVarRef):
            return Var(name=operand.name)

        if isinstance(operand, TacOpaqueExpr):
            return operand.expr

        if operand.name not in values:
            return Var(name=operand.name)

        return values[operand.name]


def optimize_expression_with_tac(expr: Expr) -> Expr:
    """Otimiza uma unica expressao com o ciclo AST -> TAC -> AST."""
    recursively_optimized = _optimize_expression_tree(expr)
    lowered = _TacLowerer().lower(recursively_optimized)
    optimized = _TacOptimizer().optimize(lowered)
    return _TacRebuilder().rebuild(optimized)


def _optimize_expression_tree(expr: Expr) -> Expr:
    """Otimiza primeiro as subexpressoes para trabalhar de dentro para fora."""
    if isinstance(expr, (Number, FloatNumber, LogicalLiteral, Var)):
        return expr

    if isinstance(expr, ArrayAccess):
        return ArrayAccess(name=expr.name, index=optimize_expression_with_tac(expr.index))

    if isinstance(expr, FunctionCall):
        return FunctionCall(name=expr.name, args=[optimize_expression_with_tac(arg) for arg in expr.args])

    if isinstance(expr, UnaryMinus):
        return UnaryMinus(expr=optimize_expression_with_tac(expr.expr))

    if isinstance(expr, UnaryNot):
        return UnaryNot(expr=optimize_expression_with_tac(expr.expr))

    if isinstance(expr, BinOp):
        return BinOp(
            op=expr.op,
            left=optimize_expression_with_tac(expr.left),
            right=optimize_expression_with_tac(expr.right),
        )

    return expr


def optimize_program_with_tac(program: Program) -> Program:
    """Aplica otimizacao TAC a todas as expressoes do programa."""
    return Program(
        name=program.name,
        declarations=list(program.declarations),
        statements=[_optimize_statement(stmt) for stmt in program.statements],
        functions=[_optimize_function(fn) for fn in program.functions],
        subroutines=[_optimize_subroutine(sub) for sub in program.subroutines],
    )


def _optimize_function(function: FunctionDef) -> FunctionDef:
    """Otimiza todas as expressoes dentro de uma FUNCTION."""
    return FunctionDef(
        name=function.name,
        return_type=function.return_type,
        params=list(function.params),
        declarations=list(function.declarations),
        statements=[_optimize_statement(stmt) for stmt in function.statements],
    )


def _optimize_subroutine(subroutine: SubroutineDef) -> SubroutineDef:
    """Otimiza todas as expressoes dentro de uma SUBROUTINE."""
    return SubroutineDef(
        name=subroutine.name,
        params=list(subroutine.params),
        declarations=list(subroutine.declarations),
        statements=[_optimize_statement(stmt) for stmt in subroutine.statements],
    )


def _optimize_statement(statement: Statement) -> Statement:
    """Reconstroi um statement com as suas expressoes otimizadas."""
    if isinstance(statement, Assign):
        return Assign(name=statement.name, expr=optimize_expression_with_tac(statement.expr))

    if isinstance(statement, ArrayAssign):
        return ArrayAssign(
            name=statement.name,
            index=optimize_expression_with_tac(statement.index),
            expr=optimize_expression_with_tac(statement.expr),
        )

    if isinstance(statement, Print):
        values: list[Expr | StringLiteral] = []
        for value in statement.values:
            if isinstance(value, StringLiteral):
                values.append(value)
            else:
                values.append(optimize_expression_with_tac(value))
        return Print(values=values)

    if isinstance(statement, Read):
        targets = []
        for target in statement.targets:
            if isinstance(target, ReadVarTarget):
                targets.append(target)
            else:
                targets.append(
                    ReadArrayTarget(
                        name=target.name,
                        index=optimize_expression_with_tac(target.index),
                    )
                )
        return Read(targets=targets)

    if isinstance(statement, Call):
        return Call(name=statement.name, args=[optimize_expression_with_tac(arg) for arg in statement.args])

    if isinstance(statement, DoLoop):
        return DoLoop(
            end_label=statement.end_label,
            variable_name=statement.variable_name,
            start_expr=optimize_expression_with_tac(statement.start_expr),
            end_expr=optimize_expression_with_tac(statement.end_expr),
            step_expr=optimize_expression_with_tac(statement.step_expr)
            if statement.step_expr is not None
            else None,
        )

    if isinstance(statement, IfThenElse):
        return IfThenElse(
            condition=optimize_expression_with_tac(statement.condition),
            then_body=[_optimize_statement(stmt) for stmt in statement.then_body],
            else_body=[_optimize_statement(stmt) for stmt in statement.else_body]
            if statement.else_body is not None
            else None,
        )

    if isinstance(statement, Label):
        return Label(label=statement.label, statement=_optimize_statement(statement.statement))

    if isinstance(statement, (Goto, Continue, Return)):
        return statement

    return statement
