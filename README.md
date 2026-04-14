# PL 2026 - Compilador Fortran 77 (Starter)

Este repositorio tem uma base inicial para o projeto de PL 2026: um compilador em Python com PLY que traduz um subconjunto de Fortran 77 para codigo da VM.

## O que ja esta implementado

- Analise lexica com `ply.lex`
- Analise sintatica com `ply.yacc`
- AST minima
- Analise semantica basica (variaveis declaradas e sem redeclaracoes)
- Geracao de codigo VM para:
  - `PROGRAM ... END`
  - `INTEGER` (declaracao de variaveis escalares)
  - atribuicoes
  - expressoes inteiras (`+`, `-`, `*`, `/`, parentesis, unario `-`)
  - expressoes relacionais e logicas (`.EQ.`, `.NE.`, `.LT.`, `.LE.`, `.GT.`, `.GE.`, `.AND.`, `.OR.`, `.NOT.`)
  - `PRINT *, ...`
  - `READ *, ...`
  - `IF (...) THEN ... [ELSE ...] ENDIF`
  - `GOTO <label>` e labels numericos (`100 CONTINUE`)

## Estrutura

- `src/lexer.py`: tokens e regras lexicas
- `src/parser.py`: gramatica e AST
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

- ciclos `DO` com label
- `REAL`, `LOGICAL`, arrays e subprogramas

## Proximos passos recomendados

1. Implementar `DO ... CONTINUE`.
2. Suportar `REAL` e instrucoes VM em virgula flutuante.
3. Suportar `LOGICAL` e verificacoes de tipos mais completas.
4. Adicionar arrays (`INTEGER A(10)`) e respetivo acesso.
5. Adicionar suite de testes com os exemplos do enunciado.
