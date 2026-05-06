"""
Analisador Semantico - Tabelas de Simbolos
=========================================

Responsavel por recolher cabecalhos e declarar simbolos.

Responsabilidades:
- Cabecalhos de FUNCTION/SUBROUTINE
- Declaracoes globais, de funcoes e de subrotinas
- Validacao de declaracoes externas
"""

from __future__ import annotations

from collections.abc import Mapping

from ..ast_nodes import Program, SymbolInfo
from ..codegen import CompilerError
from .context import SemanticContext


class SymbolTableBuilder:
    """Construtor de tabelas de simbolos e metadados de callables."""
    def __init__(self, context: SemanticContext) -> None:
        self._ctx = context

    def collect_callable_headers(self, program: Program) -> None:
        """Regista cabecalhos de FUNCTION e SUBROUTINE antes do corpo."""
        for function in program.functions:
            if function.return_type not in {"INTEGER", "REAL", "LOGICAL"}:
                raise CompilerError(f"Unsupported function return type: {function.return_type}.")

            if function.name in self._ctx.function_headers:
                raise CompilerError(f"Function {function.name} was defined more than once.")

            if len(set(function.params)) != len(function.params):
                raise CompilerError(f"Function {function.name} has duplicated parameter names.")

            self._ctx.function_headers[function.name] = function

        for subroutine in program.subroutines:
            if subroutine.name in self._ctx.subroutine_headers:
                raise CompilerError(f"Subroutine {subroutine.name} was defined more than once.")

            if subroutine.name in self._ctx.function_headers:
                raise CompilerError(f"Name {subroutine.name} is used by both FUNCTION and SUBROUTINE.")

            if len(set(subroutine.params)) != len(subroutine.params):
                raise CompilerError(f"Subroutine {subroutine.name} has duplicated parameter names.")

            self._ctx.subroutine_headers[subroutine.name] = subroutine

    def declare_global_variables(self, program: Program) -> None:
        """Declara variaveis globais e valida declaracoes externas."""
        for declaration in program.declarations:
            if declaration.type_name not in {"INTEGER", "REAL", "LOGICAL"}:
                raise CompilerError(f"Unsupported declaration type: {declaration.type_name}")

            for item in declaration.items:
                name = item.name

                if name in self._ctx.function_headers:
                    self._validate_external_function_declaration(
                        declaration_type=declaration.type_name,
                        function_name=name,
                        size=item.size,
                    )
                    continue

                if name in self._ctx.subroutine_headers:
                    raise CompilerError(f"Subroutine {name} cannot be declared as variable.")

                if name in self._ctx.symbols:
                    raise CompilerError(f"Variable {name} was declared more than once.")

                if item.size is None:
                    self._ctx.symbols[name] = SymbolInfo(
                        type_name=declaration.type_name,
                        base_index=self._ctx.next_global_slot,
                        size=1,
                        is_array=False,
                    )
                    self._ctx.next_global_slot += 1
                    continue

                if item.size <= 0:
                    raise CompilerError(f"Array {name} must have a positive size.")

                self._ctx.symbols[name] = SymbolInfo(
                    type_name=declaration.type_name,
                    base_index=self._ctx.next_global_slot,
                    size=item.size,
                    is_array=True,
                )
                self._ctx.next_global_slot += item.size

    def declare_functions(self, program: Program) -> None:
        """Declara simbolos locais e metadados de funcoes."""
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
                            base_index=self._ctx.next_global_slot,
                            size=1,
                            is_array=False,
                        )
                        self._ctx.next_global_slot += 1
                        continue

                    if item.size <= 0:
                        raise CompilerError(f"Array {item.name} must have a positive size.")

                    function_symbols[item.name] = SymbolInfo(
                        type_name=declaration.type_name,
                        base_index=self._ctx.next_global_slot,
                        size=item.size,
                        is_array=True,
                    )
                    self._ctx.next_global_slot += item.size

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
                    base_index=self._ctx.next_global_slot,
                    size=1,
                    is_array=False,
                )
                self._ctx.next_global_slot += 1

            self._ctx.functions[function.name] = {
                "name": function.name,
                "return_type": function.return_type,
                "params": tuple(function.params),
                "param_types": tuple(param_types),
                "symbols": function_symbols,
                "statements": list(function.statements),
            }

    def declare_subroutines(self, program: Program) -> None:
        """Declara simbolos locais e metadados de subrotinas."""
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
                            base_index=self._ctx.next_global_slot,
                            size=1,
                            is_array=False,
                        )
                        self._ctx.next_global_slot += 1
                        continue

                    if item.size <= 0:
                        raise CompilerError(f"Array {item.name} must have a positive size.")

                    subroutine_symbols[item.name] = SymbolInfo(
                        type_name=declaration.type_name,
                        base_index=self._ctx.next_global_slot,
                        size=item.size,
                        is_array=True,
                    )
                    self._ctx.next_global_slot += item.size

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

            self._ctx.subroutines[subroutine.name] = {
                "name": subroutine.name,
                "params": tuple(subroutine.params),
                "param_types": tuple(param_types),
                "symbols": subroutine_symbols,
                "statements": list(subroutine.statements),
            }

    def _validate_external_function_declaration(
        self,
        *,
        declaration_type: str,
        function_name: str,
        size: int | None,
    ) -> None:
        function = self._ctx.function_headers[function_name]
        if size is not None:
            raise CompilerError(f"Function declaration {function_name} cannot be an array.")
        if declaration_type != function.return_type:
            raise CompilerError(
                f"Function declaration {function_name} type mismatch: expected {function.return_type}."
            )

    @staticmethod
    def copy_callable_metadata(metadata_map: Mapping[str, dict[str, object]]) -> dict[str, dict[str, object]]:
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
