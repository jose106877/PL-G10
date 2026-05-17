"""Estado partilhado da analise semantica.

Os varios analisadores da pasta `semantica` precisam de ver os mesmos dados:
tabela de simbolos global, cabecalhos de funcoes/subrotinas e contador de
slots da VM. Esta dataclass e o "quadro branco" comum dessa fase.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ast_nodes import FunctionDef, SubroutineDef, SymbolInfo


@dataclass
class SemanticContext:
    """Guarda tudo o que a semantica descobre durante a analise."""
    # Variaveis globais do programa principal.
    symbols: dict[str, SymbolInfo] = field(default_factory=dict)

    # Metadados completos ja validados de FUNCTIONs e SUBROUTINEs.
    functions: dict[str, dict[str, object]] = field(default_factory=dict)
    subroutines: dict[str, dict[str, object]] = field(default_factory=dict)

    # Cabecalhos recolhidos antes de validar os corpos. Isto permite chamar
    # uma funcao definida mais abaixo no ficheiro.
    function_headers: dict[str, FunctionDef] = field(default_factory=dict)
    subroutine_headers: dict[str, SubroutineDef] = field(default_factory=dict)

    # Proximo indice global livre na memoria da VM.
    next_global_slot: int = 0

    def reset(self) -> None:
        """Limpa tudo para analisar um novo programa."""
        self.symbols = {}
        self.functions = {}
        self.subroutines = {}
        self.function_headers = {}
        self.subroutine_headers = {}
        self.next_global_slot = 0
