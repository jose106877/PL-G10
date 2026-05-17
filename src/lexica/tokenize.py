"""Helper de tokenizacao para debug.

O compilador normal nao precisa de devolver os tokens ao utilizador, mas esta
funcao e util para confirmar se o lexer reconhece corretamente cada pedaco do
codigo fonte.
"""

from __future__ import annotations

from .lexer import build_lexer, tokens


def tokenize_source(source: str):
    """Devolve todos os tokens produzidos pelo lexer."""
    lexer = build_lexer()
    lexer.input(source)

    # O PLY devolve um token de cada vez. Vamos consumindo ate chegar a None.
    output = []
    token = lexer.token()
    while token is not None:
        output.append(token)
        token = lexer.token()

    return output


__all__ = ["build_lexer", "tokens", "tokenize_source"]
