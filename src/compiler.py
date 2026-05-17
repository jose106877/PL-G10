"""Compilation pipeline from source to VM code."""

from __future__ import annotations

from pathlib import Path

from .codegen import VMCodeGenerator
from .ir import optimize_program_with_tac
from .semantica import SemanticAnalyzer
from .sintatica import parse_source


def compile_source_to_vm(source: str) -> str:
    ast = parse_source(source)
    optimized_ast = optimize_program_with_tac(ast)
    symbols, functions, subroutines = SemanticAnalyzer().analyze(optimized_ast)
    generator = VMCodeGenerator()
    return generator.compile(optimized_ast, symbols=symbols, functions=functions, subroutines=subroutines)


def compile_file(input_path: str, output_path: str) -> None:
    source = Path(input_path).read_text(encoding="utf-8")
    vm_code = compile_source_to_vm(source)
    Path(output_path).write_text(vm_code + "\n", encoding="utf-8")
