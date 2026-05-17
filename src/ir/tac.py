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

from .optimizations import _TacOptimizer
from .tac_types import (
    TacAssignInstr,
    TacBinaryInstr,
    TacConst,
    TacExpression,
    TacOperand,
    TacOpaqueExpr,
    TacTempRef,
    TacUnaryInstr,
    TacVarRef,
)


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
