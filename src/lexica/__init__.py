"""Pacote da analise lexica.

Exporta o lexer PLY e uma funcao utilitaria para ver a lista de tokens de um
programa, o que ajuda bastante em debug e na defesa.
"""

from .lexer import build_lexer, tokens
from .tokenize import tokenize_source

__all__ = ["build_lexer", "tokens", "tokenize_source"]
