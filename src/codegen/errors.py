"""Erros partilhados pela semantica e pelo codegen."""


class CompilerError(Exception):
    """Erro esperado do compilador.

    Usamos esta excecao para problemas do programa Fortran: variavel nao
    declarada, tipos incompativeis, label inexistente, chamada invalida, etc.
    """
