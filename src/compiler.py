"""Pipeline principal: transforma fonte Fortran em codigo VM.

Este ficheiro e o "fio condutor" do compilador. As fases estao todas
separadas em modulos, mas aqui fica a ordem em que acontecem.
"""

from __future__ import annotations

from pathlib import Path

from .codegen import VMCodeGenerator
from .ir import optimize_program_with_tac
from .preprocess import preprocess_source
from .semantica import SemanticAnalyzer
from .sintatica import parse_source


def compile_source_to_vm(source: str) -> str:
    """Compila texto Fortran diretamente para texto VM."""
    # 1) Aceitamos fixed-form ou free-form e normalizamos para o formato que
    # o parser ja entende.
    normalized_source = preprocess_source(source)

    # 2) O parser constroi a AST: uma representacao Python do programa.
    ast = parse_source(normalized_source)

    # 3) O TAC simplifica expressoes locais antes da analise/geracao final.
    optimized_ast = optimize_program_with_tac(ast)

    # 4) A semantica valida declaracoes, tipos, labels e callables.
    symbols, functions, subroutines = SemanticAnalyzer().analyze(optimized_ast)

    # 5) O gerador percorre a AST validada e emite instrucoes da VM.
    generator = VMCodeGenerator()
    return generator.compile(optimized_ast, symbols=symbols, functions=functions, subroutines=subroutines)


def compile_file(input_path: str, output_path: str) -> None:
    """Le um ficheiro fonte, compila-o e escreve o ficheiro `.vm`."""
    source = Path(input_path).read_text(encoding="utf-8")
    vm_code = compile_source_to_vm(source)

    # Escrevemos newline final para os outputs ficarem estaveis em diff.
    Path(output_path).write_text(vm_code + "\n", encoding="utf-8")
