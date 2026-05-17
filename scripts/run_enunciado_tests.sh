#!/usr/bin/env bash
set -euo pipefail

# 1) soma2
python -m src.main examples/hello.f77 -o output/hello.vm

# 2) if_goto_demo
python -m src.main examples/fatorial_do.f77 -o output/fatorial_do.vm

# 3) label indefinida (erro esperado)
python -m src.main examples/primo.f77 -o output/primo.vm 

# 4) variavel nao declarada (erro esperado)
python -m src.main examples/soma_array.f77 -o output/soma_array.vm 

# 5) conversor
python -m src.main examples/conversor.f77 -o output/conversor.vm
