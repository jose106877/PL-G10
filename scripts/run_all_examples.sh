#!/usr/bin/env bash
set -euo pipefail

EXAMPLES_DIR="examples"
OUTPUT_DIR="output"
PASS=0
FAIL=0

mkdir -p "$OUTPUT_DIR"

for src in "$EXAMPLES_DIR"/*.f77; do
    name=$(basename "$src" .f77)
    out="$OUTPUT_DIR/$name.vm"

    if python -m src.main "$src" -o "$out" 2>/dev/null; then
        echo "OK   $src -> $out"
        PASS=$((PASS + 1))
    else
        echo "FAIL $src"
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "Resultados: $PASS ok, $FAIL falhados"
[ "$FAIL" -eq 0 ]
