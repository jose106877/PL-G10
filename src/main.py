"""Entrada de linha de comandos do compilador.

Permite usar o projeto como:

    python -m src.main examples/hello.f77 -o hello.vm
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .codegen import CompilerError
from .compiler import compile_file


def main() -> int:
    """Processa argumentos da CLI e devolve codigo de saida Unix."""
    # `argparse` trata automaticamente `--help` e mensagens de uso.
    parser = argparse.ArgumentParser(description="Compile a Fortran 77 subset to VM code.")
    parser.add_argument("input", help="Path to a Fortran source file")
    parser.add_argument("-o", "--output", help="Path to the generated VM file")

    args = parser.parse_args()

    # Se o utilizador nao indicar `-o`, trocamos a extensao do ficheiro fonte
    # para `.vm`.
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path.with_suffix(".vm")

    try:
        compile_file(str(input_path), str(output_path))
    except (CompilerError, SyntaxError, OSError) as exc:
        # Erros esperados do compilador ficam em stderr e devolvem codigo 1.
        print(f"Compilation failed: {exc}", file=sys.stderr)
        return 1

    # Sucesso explicito: util para scripts e para testes manuais.
    print(f"VM code written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
