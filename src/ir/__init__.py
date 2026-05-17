"""Representacao intermedia e otimizacoes.

Exporta as funcoes TAC usadas pelo pipeline principal para simplificar
expressoes antes de validar e gerar VM.
"""

from .tac import optimize_expression_with_tac, optimize_program_with_tac

__all__ = ["optimize_expression_with_tac", "optimize_program_with_tac"]
