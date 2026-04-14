from __future__ import annotations

from pathlib import Path

from .codegen import VMCodeGenerator
from .parser import parse_source


def compile_source_to_vm(source: str) -> str:
    ast = parse_source(source)
    generator = VMCodeGenerator()
    return generator.compile(ast)


def compile_file(input_path: str, output_path: str) -> None:
    source = Path(input_path).read_text(encoding="utf-8")
    vm_code = compile_source_to_vm(source)
    Path(output_path).write_text(vm_code + "\n", encoding="utf-8")
