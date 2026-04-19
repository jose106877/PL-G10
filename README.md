# PL 2026 - Compilador Fortran 77 (Starter)

Este repositorio tem uma base inicial para o projeto de PL 2026: um compilador em Python com PLY que traduz um subconjunto de Fortran 77 para codigo da VM.

## O que ja esta implementado

- Analise lexica com `ply.lex`
- Analise sintatica com `ply.yacc`
- AST minima
- Analise semantica basica (variaveis declaradas e sem redeclaracoes)
- Geracao de codigo VM para:
  - `PROGRAM ... END`
  - declaracoes `INTEGER`, `REAL`, `LOGICAL` (escalares e arrays)
  - atribuicoes
  - expressoes inteiras e reais (`+`, `-`, `*`, `/`, parentesis, unario `-`)
  - expressoes relacionais e logicas (`.EQ.`, `.NE.`, `.LT.`, `.LE.`, `.GT.`, `.GE.`, `.AND.`, `.OR.`, `.NOT.`)
  - `PRINT *, ...`
  - `READ *, ...`
  - `IF (...) THEN ... [ELSE ...] ENDIF`
  - `GOTO <label>` e labels numericos (`100 CONTINUE`)
  - `DO <label> I = ini, fim[, passo]` com fecho em `<label> CONTINUE`
  - arrays `INTEGER A(10)` com acesso e atribuicao `A(I)`
  - funcao embutida `MOD(a, b)`
  - definicao e chamada de `FUNCTION` tipada (ex.: `INTEGER FUNCTION F(A, B)`)
  - definicao e chamada de `SUBROUTINE` (ex.: `CALL S(A, B)`)

## Estrutura

- `src/lexer.py`: tokens e regras lexicas
- `src/parser.py`: gramatica e AST
- `src/analise_lexica.py`: ponto de entrada da analise lexica
- `src/analise_sintatica.py`: ponto de entrada da analise sintatica
- `src/analise_semantica.py`: validacoes semanticas
- `src/ast_nodes.py`: nos da AST
- `src/codegen.py`: geracao para VM
- `src/compiler.py`: pipeline parser + codegen
- `src/main.py`: CLI
- `examples/`: programas Fortran de exemplo
- `tests/`: testes de fumo

## Como correr

1. Instalar dependencias:

```bash
pip install -r requirements.txt
```

2. Compilar exemplo:

```bash
python -m src.main examples/hello.f77 -o hello.vm
```

3. Correr testes:

```bash
python -m unittest discover -s tests
```

## Limites desta primeira versao

Esta base ainda nao suporta:

- recursao de `FUNCTION`
- recursao de `SUBROUTINE`
- formato fixed-form classico por colunas do Fortran 77

## Proximos passos recomendados

1. Implementar `SUBROUTINE` e `CALL`.
2. Guardar outputs VM esperados para todos os exemplos.
3. Fechar relatorio tecnico final de entrega.
