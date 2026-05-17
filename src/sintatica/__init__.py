"""Pacote da analise sintatica.

Exporta o construtor do parser PLY e a funcao de conveniencia `parse_source`,
que transforma codigo pre-processado numa AST.
"""

from .parser import build_parser, parse_source

__all__ = ["build_parser", "parse_source"]
