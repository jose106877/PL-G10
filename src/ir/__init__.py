"""Intermediate representation and optimizations."""

from .tac import optimize_expression_with_tac, optimize_program_with_tac

__all__ = ["optimize_expression_with_tac", "optimize_program_with_tac"]
