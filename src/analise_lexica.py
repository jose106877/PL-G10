from __future__ import annotations

from .lexer import build_lexer, tokens


def tokenize_source(source: str):
    """Return the token stream for debugging and teaching purposes."""
    lexer = build_lexer()
    lexer.input(source)

    output = []
    token = lexer.token()
    while token is not None:
        output.append(token)
        token = lexer.token()

    return output


__all__ = ["build_lexer", "tokens", "tokenize_source"]
