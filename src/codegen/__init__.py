"""Pacote de geracao de codigo VM.

Exporta o gerador principal (`VMCodeGenerator`) e o erro comum usado tanto na
semantica como no codegen (`CompilerError`).
"""

from .errors import CompilerError
from .generator import VMCodeGenerator

__all__ = ["CompilerError", "VMCodeGenerator"]
