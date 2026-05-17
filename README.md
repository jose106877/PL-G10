# PL 2026 - Compilador Fortran 77

Compilador em Python com PLY que traduz um subconjunto de Fortran 77 para código da VM,
com etapa intermédia TAC (three-address code) para otimização de expressões.

**Grupo G10** — Universidade do Minho, Licenciatura em Engenharia Informática, 2025/2026

## Funcionalidades

- Pré-processamento automático de **fixed-form** (colunas 1-72) e **free-form** (com `&`)
- Análise léxica com `ply.lex`
- Análise sintática com `ply.yacc` e construção de AST imutável
- Análise semântica: tipos, declarações, labels, consistência de `DO`/`CONTINUE`, aridade de subprogramas
- Otimização intermédia via TAC: *constant folding*, propagação de cópias, eliminação de código morto
- Geração de código VM para:
  - `PROGRAM ... END`
  - Declarações `INTEGER`, `REAL`, `LOGICAL` — escalares e arrays unidimensionais
  - Atribuições escalares e a arrays (`A(I) = expr`)
  - Expressões aritméticas (`+`, `-`, `*`, `/`, menos unário)
  - Expressões relacionais (`.EQ.`, `.NE.`, `.LT.`, `.LE.`, `.GT.`, `.GE.`)
  - Expressões lógicas (`.AND.`, `.OR.`, `.NOT.`)
  - `PRINT *, ...` e `READ *, ...`
  - `IF (...) THEN ... [ELSE ...] ENDIF`
  - `GOTO <label>` e labels numéricas (`100 CONTINUE`)
  - `DO <label> var = ini, fim [, passo]` com fecho em `<label> CONTINUE`
  - Função embutida `MOD(a, b)`
  - `INTEGER/REAL/LOGICAL FUNCTION nome(...)` — definição e chamada
  - `SUBROUTINE nome(...)` — definição e `CALL`


## Estrutura

```
src/
  preprocess.py          detecção e normalização fixed-form/free-form
  ast_nodes.py           nós da AST (dataclasses imutáveis)
  compiler.py            pipeline completo: preprocess → parse → TAC → semântica → codegen
  main.py                CLI
  lexica/
    lexer.py             tokens e regras léxicas (ply.lex)
  sintatica/
    parser.py            gramática e construção da AST (ply.yacc)
  semantica/
    analyzer.py          orquestrador da análise semântica
    expressions.py       validação e inferência de tipos de expressões
    statements.py        validação de statements e controlo de fluxo
    symbols.py           construção das tabelas de símbolos
    context.py           contexto partilhado entre fases semânticas
  ir/
    tac.py               lowering AST → TAC e reconstrução
    optimizations.py     constant folding, propagação de cópias, dead code
    tac_types.py         tipos de dados do TAC
  codegen/
    generator.py         VMCodeGenerator (agrega os mixins)
    statements.py        emissão de statements
    expressions.py       emissão de expressões
    loops.py             emissão de ciclos DO
    calls.py             inlining de FUNCTION e SUBROUTINE
    helpers.py           utilitários partilhados
    context.py           estado interno do gerador
    errors.py            CompilerError
examples/                programas Fortran 77 de exemplo
output/                  código VM gerado para cada exemplo
tests/                   suite de testes automatizados
relatorio.tex            relatório técnico do projeto
```

## Como correr

### Instalar dependências

```bash
pip install -r requirements.txt
```

### Compilar um programa Fortran

```bash
python -m src.main <ficheiro.f77> -o <saida.vm>
```

### Exemplos do enunciado

```bash
python -m src.main examples/hello.f77        -o output/hello.vm
python -m src.main examples/fatorial_do.f77  -o output/fatorial_do.vm
python -m src.main examples/primo.f77        -o output/primo.vm
python -m src.main examples/soma_array.f77   -o output/soma_array.vm
python -m src.main examples/conversor.f77    -o output/conversor.vm
```

Os ficheiros `.vm` resultantes encontram-se na pasta `output/`.

### Correr os testes

```bash
python -m unittest discover -s tests
```

39 testes, todos a passar.
