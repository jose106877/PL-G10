"""Validacao semantica de statements.

Esta fase percorre as instrucoes da AST e confirma que cada uma e coerente:
- atribuicoes respeitam tipos;
- READ/PRINT usam variaveis/expressoes validas;
- GOTO aponta para label existente;
- DO fecha numa label com CONTINUE;
- IF recebe condicao LOGICAL;
- CALL chama uma SUBROUTINE existente.
"""

from __future__ import annotations

from collections.abc import Mapping

from ..ast_nodes import (
    ArrayAssign,
    Assign,
    Call,
    Continue,
    DoLoop,
    Goto,
    IfThenElse,
    Label,
    Number,
    Print,
    Read,
    ReadArrayTarget,
    ReadVarTarget,
    Return,
    StringLiteral,
    SymbolInfo,
)
from ..codegen import CompilerError
from .context import SemanticContext
from .expressions import ExpressionAnalyzer


class StatementAnalyzer:
    """Valida blocos de statements num determinado escopo."""
    def __init__(self, context: SemanticContext, expr_analyzer: ExpressionAnalyzer) -> None:
        self._ctx = context
        self._expr = expr_analyzer

        # Estado do bloco atualmente em analise.
        self._scope: Mapping[str, SymbolInfo] | None = None
        self._current_callable_name: str | None = None
        self._current_callable_kind: str | None = None

        # Labels abertas/definidas/referidas sao locais ao bloco analisado.
        self._open_do_labels: list[int] = []
        self._defined_labels: set[int] = set()
        self._referenced_labels: set[int] = set()

    def analyze_statement_block(
        self,
        statements,
        scope: Mapping[str, SymbolInfo],
        current_callable_name: str | None,
        current_callable_kind: str | None,
    ) -> None:
        """Valida uma lista de statements no escopo indicado."""
        # Inicializamos o estado deste bloco.
        self._scope = scope
        self._current_callable_name = current_callable_name
        self._current_callable_kind = current_callable_kind
        self._open_do_labels = []
        self._defined_labels = set()
        self._referenced_labels = set()
        self._expr.set_context(scope, current_callable_name, current_callable_kind)

        # Valida cada statement individualmente.
        for statement in statements:
            self._analyze_statement(statement)

        # Se sobrar label de DO aberta, nunca apareceu o label de fecho.
        if self._open_do_labels:
            missing = ", ".join(str(label) for label in self._open_do_labels)
            raise CompilerError(f"DO loop(s) without closing label: {missing}.")

        # Depois de ver todas as labels, conseguimos saber se algum GOTO ficou
        # sem destino.
        undefined_labels = sorted(self._referenced_labels - self._defined_labels)
        if undefined_labels:
            labels_text = ", ".join(str(value) for value in undefined_labels)
            raise CompilerError(f"Undefined label(s) referenced by GOTO: {labels_text}.")

    def _analyze_statement(
        self,
        statement,
    ) -> None:
        """Despacha a validacao conforme o tipo concreto do statement."""
        self._require_scope()
        current_callable_kind = self._current_callable_kind
        open_do_labels = self._open_do_labels
        defined_labels = self._defined_labels
        referenced_labels = self._referenced_labels

        # `A = expr`: A deve existir, ser escalar e aceitar o tipo de expr.
        if isinstance(statement, Assign):
            target = self._expr.require_scalar(statement.name)
            self._expr.analyze_expression(statement.expr)
            self._expr.ensure_assign_compatible(
                target.type_name,
                self._expr.expression_type(statement.expr),
            )
            return

        # `A(I) = expr`: A deve ser array, I inteiro e expr compativel.
        if isinstance(statement, ArrayAssign):
            target = self._expr.require_array(statement.name)
            self._expr.analyze_expression(statement.index)
            self._expr.analyze_expression(statement.expr)
            self._expr.ensure_index_integer(statement.index)
            self._expr.ensure_assign_compatible(
                target.type_name,
                self._expr.expression_type(statement.expr),
            )
            return

        # READ so pode escrever em variaveis/arrays existentes.
        if isinstance(statement, Read):
            for target in statement.targets:
                if isinstance(target, ReadVarTarget):
                    self._expr.require_scalar(target.name)
                    continue

                if isinstance(target, ReadArrayTarget):
                    self._expr.require_array(target.name)
                    self._expr.analyze_expression(target.index)
                    self._expr.ensure_index_integer(target.index)
                    continue

                raise CompilerError(f"Unsupported READ target: {type(target).__name__}")
            return

        # PRINT aceita strings e expressoes validas.
        if isinstance(statement, Print):
            for value in statement.values:
                if not isinstance(value, StringLiteral):
                    self._expr.analyze_expression(value)
            return

        # CALL valida a subrotina e os argumentos.
        if isinstance(statement, Call):
            for argument in statement.args:
                self._expr.analyze_expression(argument)

            self._validate_subroutine_call(statement)
            return

        # Label define um destino numerico e pode fechar um DO.
        if isinstance(statement, Label):
            if statement.label in defined_labels:
                raise CompilerError(f"Label {statement.label} was defined more than once.")

            defined_labels.add(statement.label)

            # Se esta label fecha um DO, o statement obrigatorio e CONTINUE.
            closing_index = self._find_last_open_do_label(open_do_labels, statement.label)
            if closing_index is not None and not isinstance(statement.statement, Continue):
                raise CompilerError(
                    f"DO loop ending at label {statement.label} requires CONTINUE at that label."
                )

            # Valida o statement que esta associado a label.
            self._analyze_statement(statement.statement)

            # Agora que o label apareceu, o DO deixou de estar aberto.
            if closing_index is not None:
                open_do_labels.pop(closing_index)
            return

        # GOTO apenas regista a referencia; confirmamos existencia no fim.
        if isinstance(statement, Goto):
            referenced_labels.add(statement.label)
            return

        # DO abre uma label de fecho e valida variavel/limites/passo.
        if isinstance(statement, DoLoop):
            loop_var = self._expr.require_scalar(statement.variable_name)
            if loop_var.type_name != "INTEGER":
                raise CompilerError("DO control variable must be INTEGER.")

            self._expr.analyze_expression(statement.start_expr)
            self._expr.analyze_expression(statement.end_expr)
            self._expr.ensure_integer_compatible(statement.start_expr, "DO start expression")
            self._expr.ensure_integer_compatible(statement.end_expr, "DO end expression")

            if statement.step_expr is not None:
                self._expr.analyze_expression(statement.step_expr)
                self._expr.ensure_integer_compatible(statement.step_expr, "DO step expression")
                # Passo literal zero geraria loop infinito.
                if isinstance(statement.step_expr, Number) and statement.step_expr.value == 0:
                    raise CompilerError("DO step value cannot be 0.")

            # O subset evita loops aninhados a partilhar a mesma label de fim.
            if statement.end_label in open_do_labels:
                raise CompilerError(
                    f"Nested DO loops sharing end label {statement.end_label} are not supported."
                )

            open_do_labels.append(statement.end_label)
            return

        # IF precisa de condicao LOGICAL e depois valida ambos os blocos.
        if isinstance(statement, IfThenElse):
            self._expr.analyze_expression(statement.condition)
            condition_type = self._expr.expression_type(statement.condition)
            if condition_type != "LOGICAL":
                raise CompilerError("IF condition must be LOGICAL.")

            for inner_statement in statement.then_body:
                self._analyze_statement(inner_statement)
            if statement.else_body is not None:
                for inner_statement in statement.else_body:
                    self._analyze_statement(inner_statement)
            return

        # RETURN so faz sentido dentro de FUNCTION/SUBROUTINE.
        if isinstance(statement, (Continue, Return)):
            if isinstance(statement, Return) and current_callable_kind not in {"FUNCTION", "SUBROUTINE"}:
                raise CompilerError("RETURN is only valid inside FUNCTION or SUBROUTINE bodies.")
            return

        raise CompilerError(f"Unsupported statement node: {type(statement).__name__}")

    def _require_scope(self) -> Mapping[str, SymbolInfo]:
        """Garante que estamos dentro de um bloco ativo."""
        if self._scope is None:
            raise CompilerError("Statement analysis requires an active scope.")
        return self._scope

    def _validate_subroutine_call(self, statement: Call) -> None:
        """Valida `CALL nome(args)` contra metadados de SUBROUTINE."""
        current_callable_name = self._current_callable_name
        current_callable_kind = self._current_callable_kind
        name = statement.name.upper()

        # `CALL F(...)` e invalido quando F e FUNCTION.
        if name in self._ctx.functions:
            raise CompilerError(f"CALL requires SUBROUTINE, but {name} is a FUNCTION.")

        if name not in self._ctx.subroutines:
            raise CompilerError(f"Unsupported subroutine call: {statement.name}.")

        # Como o codegen faz inlining, recursao direta nao e suportada.
        if current_callable_kind == "SUBROUTINE" and name == current_callable_name:
            raise CompilerError("Recursive SUBROUTINE calls are not supported.")

        # Aridade e tipos dos argumentos devem bater com a assinatura.
        metadata = self._ctx.subroutines[name]
        expected_types = metadata["param_types"]

        if len(statement.args) != len(expected_types):
            raise CompilerError(
                f"Subroutine {name} expects {len(expected_types)} arguments, got {len(statement.args)}."
            )

        for argument, expected_type in zip(statement.args, expected_types):
            actual_type = self._expr.expression_type(argument)
            self._expr.ensure_assign_compatible(expected_type, actual_type)

    @staticmethod
    def _find_last_open_do_label(open_do_labels: list[int], label: int) -> int | None:
        """Procura a label de DO aberta mais recente com este numero."""
        for index in range(len(open_do_labels) - 1, -1, -1):
            if open_do_labels[index] == label:
                return index
        return None
