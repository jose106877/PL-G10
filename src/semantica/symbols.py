"""Construcao de tabelas de simbolos.

A tabela de simbolos liga nomes do programa a informacao concreta:
tipo, posicao global na VM, tamanho e se e array.

Tambem recolhemos metadados de FUNCTION/SUBROUTINE para validar chamadas e
para o codegen conseguir fazer inlining.
"""

from __future__ import annotations

from collections.abc import Mapping

from ..ast_nodes import Program, SymbolInfo
from ..codegen import CompilerError
from .context import SemanticContext


class SymbolTableBuilder:
    """Preenche o `SemanticContext` com simbolos e callables."""
    def __init__(self, context: SemanticContext) -> None:
        self._ctx = context

    def collect_callable_headers(self, program: Program) -> None:
        """Regista nomes/assinaturas antes de declarar corpos.

        Isto permite que o programa principal chame uma funcao que aparece
        escrita mais abaixo no ficheiro.
        """
        for function in program.functions:
            # O subset so suporta estes tres tipos.
            if function.return_type not in {"INTEGER", "REAL", "LOGICAL"}:
                raise CompilerError(f"Unsupported function return type: {function.return_type}.")

            # Nao pode haver duas funcoes com o mesmo nome.
            if function.name in self._ctx.function_headers:
                raise CompilerError(f"Function {function.name} was defined more than once.")

            # Parametros repetidos tornariam a tabela local ambigua.
            if len(set(function.params)) != len(function.params):
                raise CompilerError(f"Function {function.name} has duplicated parameter names.")

            self._ctx.function_headers[function.name] = function

        for subroutine in program.subroutines:
            # Mesmo tipo de validacoes para SUBROUTINE.
            if subroutine.name in self._ctx.subroutine_headers:
                raise CompilerError(f"Subroutine {subroutine.name} was defined more than once.")

            if subroutine.name in self._ctx.function_headers:
                raise CompilerError(f"Name {subroutine.name} is used by both FUNCTION and SUBROUTINE.")

            if len(set(subroutine.params)) != len(subroutine.params):
                raise CompilerError(f"Subroutine {subroutine.name} has duplicated parameter names.")

            self._ctx.subroutine_headers[subroutine.name] = subroutine

    def declare_global_variables(self, program: Program) -> None:
        """Declara variaveis do programa principal."""
        for declaration in program.declarations:
            if declaration.type_name not in {"INTEGER", "REAL", "LOGICAL"}:
                raise CompilerError(f"Unsupported declaration type: {declaration.type_name}")

            for item in declaration.items:
                name = item.name

                # Em Fortran, declarar no programa principal uma FUNCTION
                # externa com o mesmo nome indica o seu tipo de retorno.
                if name in self._ctx.function_headers:
                    self._validate_external_function_declaration(
                        declaration_type=declaration.type_name,
                        function_name=name,
                        size=item.size,
                    )
                    continue

                # SUBROUTINE nao pode ser usada como variavel.
                if name in self._ctx.subroutine_headers:
                    raise CompilerError(f"Subroutine {name} cannot be declared as variable.")

                if name in self._ctx.symbols:
                    raise CompilerError(f"Variable {name} was declared more than once.")

                # Escalares ocupam um slot global.
                if item.size is None:
                    self._ctx.symbols[name] = SymbolInfo(
                        type_name=declaration.type_name,
                        base_index=self._ctx.next_global_slot,
                        size=1,
                        is_array=False,
                    )
                    self._ctx.next_global_slot += 1
                    continue

                # Arrays ocupam `size` slots consecutivos.
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
        """Declara escopo local e metadados de cada FUNCTION."""
        for function in program.functions:
            function_symbols: dict[str, SymbolInfo] = {}

            # Primeiro registamos todas as declaracoes locais.
            for declaration in function.declarations:
                if declaration.type_name not in {"INTEGER", "REAL", "LOGICAL"}:
                    raise CompilerError(f"Unsupported declaration type: {declaration.type_name}")

                for item in declaration.items:
                    # Dentro da funcao tambem nao permitimos redeclaracao.
                    if item.name in function_symbols:
                        raise CompilerError(
                            f"Variable {item.name} was declared more than once in function {function.name}."
                        )

                    # Variavel local escalar.
                    if item.size is None:
                        function_symbols[item.name] = SymbolInfo(
                            type_name=declaration.type_name,
                            base_index=self._ctx.next_global_slot,
                            size=1,
                            is_array=False,
                        )
                        self._ctx.next_global_slot += 1
                        continue

                    # Array local.
                    if item.size <= 0:
                        raise CompilerError(f"Array {item.name} must have a positive size.")

                    function_symbols[item.name] = SymbolInfo(
                        type_name=declaration.type_name,
                        base_index=self._ctx.next_global_slot,
                        size=item.size,
                        is_array=True,
                    )
                    self._ctx.next_global_slot += item.size

            # Cada parametro formal precisa aparecer nas declaracoes locais
            # para sabermos o seu tipo.
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

            # A variavel com o nome da funcao guarda o valor de retorno.
            if function.name in function_symbols:
                symbol = function_symbols[function.name]
                if symbol.is_array or symbol.type_name != function.return_type:
                    raise CompilerError(
                        f"Function result variable {function.name} must match return type {function.return_type}."
                    )
            else:
                # Se o programador nao declarou explicitamente a variavel de
                # retorno, criamos uma automaticamente.
                function_symbols[function.name] = SymbolInfo(
                    type_name=function.return_type,
                    base_index=self._ctx.next_global_slot,
                    size=1,
                    is_array=False,
                )
                self._ctx.next_global_slot += 1

            # Guardamos tudo o que a semantica/codegen precisam.
            self._ctx.functions[function.name] = {
                "name": function.name,
                "return_type": function.return_type,
                "params": tuple(function.params),
                "param_types": tuple(param_types),
                "symbols": function_symbols,
                "statements": list(function.statements),
            }

    def declare_subroutines(self, program: Program) -> None:
        """Declara escopo local e metadados de cada SUBROUTINE."""
        for subroutine in program.subroutines:
            subroutine_symbols: dict[str, SymbolInfo] = {}

            # Declaracoes locais da subrotina.
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

            # Parametros precisam estar declarados para termos tipos.
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

            # SUBROUTINE nao tem retorno, mas precisa de params/simbolos/corpo.
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
        """Confirma que a declaracao externa bate com a FUNCTION definida."""
        function = self._ctx.function_headers[function_name]
        if size is not None:
            raise CompilerError(f"Function declaration {function_name} cannot be an array.")
        if declaration_type != function.return_type:
            raise CompilerError(
                f"Function declaration {function_name} type mismatch: expected {function.return_type}."
            )

    @staticmethod
    def copy_callable_metadata(metadata_map: Mapping[str, dict[str, object]]) -> dict[str, dict[str, object]]:
        """Cria copias simples dos metadados para devolver ao codegen."""
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
