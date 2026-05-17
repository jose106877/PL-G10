"""Otimizacoes locais sobre TAC (three-address code)."""

from __future__ import annotations

from .tac_types import (
    TacAssignInstr,
    TacBinaryInstr,
    TacConst,
    TacExpression,
    TacInstruction,
    TacOperand,
    TacTempRef,
    TacUnaryInstr,
)


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

        if operator in {"+", "-", "*", "/"}:
            return self._fold_arithmetic(operator, left, right)

        if operator in {"EQ", "NE", "LT", "LE", "GT", "GE"}:
            return self._fold_relational(operator, left, right)

        if operator in {"AND", "OR"}:
            return self._fold_logical(operator, left, right)

        return None

    @staticmethod
    def _fold_arithmetic(operator: str, left: TacConst, right: TacConst) -> TacConst | None:
        """Constant folding para `+`, `-`, `*` e `/`."""
        use_float = left.type_name == "REAL" or right.type_name == "REAL"
        left_value = float(left.value) if use_float else int(left.value)
        right_value = float(right.value) if use_float else int(right.value)

        if operator == "+":
            result = left_value + right_value
        elif operator == "-":
            result = left_value - right_value
        elif operator == "*":
            result = left_value * right_value
        else:
            if right_value == 0:
                return None  # nao dobrar divisao por zero
            if use_float:
                result = left_value / right_value
            else:
                # Fortran trunca para zero (igual a C), nao floor como Python.
                result = int(left_value / right_value)

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
        return (
            isinstance(operand, TacConst)
            and operand.type_name in {"INTEGER", "REAL"}
            and operand.value == 0
        )

    @staticmethod
    def _is_one(operand: TacOperand) -> bool:
        """Verifica se o operando e constante numerica um."""
        return (
            isinstance(operand, TacConst)
            and operand.type_name in {"INTEGER", "REAL"}
            and operand.value == 1
        )

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
