"""Funcoes auxiliares partilhadas pelo codegen."""

from __future__ import annotations

from collections.abc import Mapping

from .context import _InlineFunctionContext
from .errors import CompilerError
from ..ast_nodes import Number, Program, SymbolInfo


class HelperMixin:
    def _build_symbol_table(self, program: Program) -> dict[str, SymbolInfo]:
        """Constroi tabela de simbolos se alguem usar o codegen isolado.

        No pipeline normal, a semantica ja entrega esta tabela. Isto e apenas
        um fallback defensivo para testes/debug.
        """
        symbols: dict[str, SymbolInfo] = {}
        next_slot = 0

        for declaration in program.declarations:
            if declaration.type_name not in {"INTEGER", "REAL", "LOGICAL"}:
                raise CompilerError(f"Unsupported declaration type: {declaration.type_name}")

            for item in declaration.items:
                name = item.name
                if name in symbols:
                    raise CompilerError(f"Variable {name} was declared more than once.")

                # Escalar ocupa um slot.
                if item.size is None:
                    symbols[name] = SymbolInfo(
                        type_name=declaration.type_name,
                        base_index=next_slot,
                        size=1,
                        is_array=False,
                    )
                    next_slot += 1
                    continue

                # Array ocupa varios slots consecutivos.
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

    def _require_declared(self, name: str) -> SymbolInfo:
        """Resolve simbolo no contexto atual (global ou callable inline)."""
        # Durante inlining, procuramos primeiro nos simbolos locais da funcao
        # ou subrotina.
        inline_context = self._current_inline_context()
        if inline_context is not None and name in inline_context.symbols:
            return inline_context.symbols[name]

        if name not in self.symbols:
            raise CompilerError(f"Variable {name} used before declaration.")

        return self.symbols[name]

    def _require_scalar_declared(self, name: str) -> SymbolInfo:
        """Resolve um simbolo e exige que seja escalar."""
        symbol = self._require_declared(name)
        if symbol.is_array:
            raise CompilerError(f"Array {name} requires an index.")

        return symbol

    def _require_array_declared(self, name: str) -> SymbolInfo:
        """Resolve um simbolo e exige que seja array."""
        symbol = self._require_declared(name)
        if not symbol.is_array:
            raise CompilerError(f"Variable {name} is not an array.")

        return symbol

    def _emit_array_offset(self, index_expr, symbol: SymbolInfo) -> None:
        """Empilha o endereco relativo de um acesso a array."""
        # Arrays Fortran sao 1-based no subset; a VM trabalha com offset
        # 0-based. Por isso fazemos `indice - 1`.
        self._emit_expression(index_expr)

        # CHECK valida limites em runtime antes do LOADN/STOREN.
        self.instructions.append(f"CHECK 1, {symbol.size}")
        self.instructions.append("PUSHI 1")
        self.instructions.append("SUB")

        # Se o array nao comeca no slot 0, somamos o indice base.
        if symbol.base_index != 0:
            self.instructions.append(f"PUSHI {symbol.base_index}")
            self.instructions.append("ADD")

    def _global_slots_count(self) -> int:
        """Calcula quantos slots globais a VM precisa reservar."""
        max_end = 0

        # Variaveis globais do programa principal.
        for symbol in self.symbols.values():
            max_end = max(max_end, symbol.base_index + symbol.size)

        # Locais de funcoes/subrotinas tambem sao guardados em slots globais,
        # porque o codegen atual faz inlining em vez de stack frames reais.
        for metadata in self.functions.values():
            for symbol in metadata["symbols"].values():
                max_end = max(max_end, symbol.base_index + symbol.size)

        for metadata in self.subroutines.values():
            for symbol in metadata["symbols"].values():
                max_end = max(max_end, symbol.base_index + symbol.size)

        return max_end

    def _emit_assignment_coercion(self, source_type: str, target_type: str) -> None:
        """Emite conversao implicita para atribuicoes."""
        if source_type == target_type:
            return

        # INTEGER/LOGICAL para REAL.
        if target_type == "REAL" and source_type in {"INTEGER", "LOGICAL"}:
            self.instructions.append("ITOF")
            return

        # REAL para INTEGER/LOGICAL.
        if target_type in {"INTEGER", "LOGICAL"} and source_type == "REAL":
            self.instructions.append("FTOI")
            return

        raise CompilerError(f"Cannot assign {source_type} expression to {target_type} variable.")

    @staticmethod
    def _read_conversion_opcode(target_type: str) -> str:
        """Escolhe a conversao depois de READ, que devolve texto."""
        if target_type == "REAL":
            return "ATOF"
        if target_type in {"INTEGER", "LOGICAL"}:
            return "ATOI"

        raise CompilerError(f"Unsupported READ target type: {target_type}")

    def _current_inline_context(self) -> _InlineFunctionContext | None:
        """Devolve o callable atualmente em inlining, se existir."""
        if not self._inline_function_context_stack:
            return None
        return self._inline_function_context_stack[-1]

    def _resolve_source_label(self, label: int) -> str:
        """Converte labels Fortran em labels VM."""
        inline_context = self._current_inline_context()
        if inline_context is None:
            return f"L{label}"

        # Dentro de callables inlined, labels precisam ser unicas por chamada.
        if label not in inline_context.label_map:
            inline_context.label_map[label] = self._new_internal_label(f"{inline_context.tag}_L{label}")

        return inline_context.label_map[label]

    def _do_loop_key(self, end_label: int) -> object:
        """Cria chave para DO ativo, separando contexto global e inline."""
        inline_context = self._current_inline_context()
        if inline_context is None:
            return end_label
        return (inline_context.tag, end_label)

    @staticmethod
    def _format_do_key(do_key: object) -> str:
        """Formata chave de DO para mensagens de erro."""
        if isinstance(do_key, tuple) and len(do_key) == 2:
            return str(do_key[1])
        return str(do_key)

    def _new_internal_label(self, prefix: str) -> str:
        """Cria labels internas unicas e aceites pela VM."""
        self._internal_label_counter += 1

        # A VM usada nos testes fica mais feliz com labels alfanumericas.
        safe_prefix = "".join(character for character in prefix if character.isalnum())
        return f"{safe_prefix}{self._internal_label_counter}"

    @staticmethod
    def _do_condition_opcode(step_expr, variable_type: str = "INTEGER") -> str:
        """Escolhe comparacao do DO conforme o sinal do passo e o tipo da variavel."""
        descending = isinstance(step_expr, Number) and step_expr.value < 0
        if variable_type == "REAL":
            return "FSUPEQ" if descending else "FINFEQ"
        return "SUPEQ" if descending else "INFEQ"

    @staticmethod
    def _escape_vm_string(value: str) -> str:
        """Escapa strings para `PUSHS "..."`."""
        return value.replace("\\", "\\\\").replace('"', '\\"')
