"""Emissao de statements em codigo VM.

Cada statement consome/emite expressoes e acrescenta instrucoes a
`self.instructions`. A AST ja passou pela semantica, por isso aqui o foco e
traduzir para a VM.
"""

from __future__ import annotations

from .errors import CompilerError
from ..ast_nodes import (
    ArrayAssign,
    Assign,
    Call,
    Continue,
    DoLoop,
    Goto,
    IfThenElse,
    Label,
    Print,
    Read,
    ReadArrayTarget,
    ReadVarTarget,
    Return,
    StringLiteral,
)


class StatementEmitterMixin:
    """Rotinas para transformar statements AST em instrucoes VM."""
    def _emit_statement(self, statement) -> None:
        """Despacha a emissao conforme o tipo concreto do statement."""
        # Atribuicao escalar: calcula expr, converte se preciso e guarda.
        if isinstance(statement, Assign):
            symbol = self._require_scalar_declared(statement.name)
            expr_type = self._infer_expr_type(statement.expr)
            self._emit_expression(statement.expr)
            self._emit_assignment_coercion(expr_type, symbol.type_name)
            self.instructions.append(f"STOREG {symbol.base_index}")
            return

        # Atribuicao a array: empilha endereco, calcula expr e faz STOREN.
        if isinstance(statement, ArrayAssign):
            symbol = self._require_array_declared(statement.name)
            self.instructions.append("PUSHGP")
            self._emit_array_offset(statement.index, symbol)
            expr_type = self._infer_expr_type(statement.expr)
            self._emit_expression(statement.expr)
            self._emit_assignment_coercion(expr_type, symbol.type_name)
            self.instructions.append("STOREN")
            return

        # Inicio de DO fica no mixin de loops.
        if isinstance(statement, DoLoop):
            self._emit_do_loop_start(statement)
            return

        # Label Fortran vira label VM e pode fechar um DO ativo.
        if isinstance(statement, Label):
            label_name = self._resolve_source_label(statement.label)
            self.instructions.append(f"{label_name}:")
            self._emit_statement(statement.statement)

            do_key = self._do_loop_key(statement.label)
            if do_key in self._active_do_loops_by_label:
                self._emit_do_loop_end(do_key)
            return

        # GOTO vira salto incondicional.
        if isinstance(statement, Goto):
            self.instructions.append(f"JUMP {self._resolve_source_label(statement.label)}")
            return

        # CONTINUE nao faz nada em runtime, mas precisa existir como label alvo.
        if isinstance(statement, Continue):
            self.instructions.append("NOP")
            return

        # CALL de subrotina e emitido por inlining.
        if isinstance(statement, Call):
            self._emit_subroutine_call(statement)
            return

        # RETURN dentro de callable inlined salta para a label de retorno.
        if isinstance(statement, Return):
            inline_context = self._current_inline_context()
            if inline_context is None:
                raise CompilerError("RETURN is only supported inside FUNCTION or SUBROUTINE bodies.")
            self.instructions.append(f"JUMP {inline_context.return_label}")
            return

        # IF: se condicao for zero/falso, salta para ELSE; depois salta para END.
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

        # READ devolve string; depois convertemos conforme o tipo do destino.
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

        # PRINT emite cada valor e fecha com WRITELN.
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
