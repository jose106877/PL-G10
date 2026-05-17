"""Pacote da analise semantica.

A fase semantica valida se a AST "faz sentido": variaveis declaradas, tipos
compativeis, labels existentes, DO fechado com CONTINUE, funcoes e subrotinas
chamadas corretamente.
"""

from .analyzer import SemanticAnalyzer

__all__ = ["SemanticAnalyzer"]
