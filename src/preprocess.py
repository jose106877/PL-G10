"""Pre-processamento do codigo fonte antes da analise lexica.

O parser deste projeto foi escrito para receber codigo em formato livre
("free-form"). Este modulo aceita tambem Fortran 77 fixed-form e converte-o
para o mesmo formato logico antes de chamar o lexer/parser.

Regras principais do fixed-form classico:
- colunas 1-5: label opcional;
- coluna 6: marcador de continuacao;
- colunas 7-72: codigo;
- `C`, `c`, `*` ou `!` na coluna 1: comentario.
"""

from __future__ import annotations

# Nomes publicos usados por testes e por qualquer debug futuro.
FREE_FORM = "free"
FIXED_FORM = "fixed"

# Indices Python para os campos do fixed-form. Como Python usa indices
# baseados em 0, as colunas 1-5 ficam em [0:5], a coluna 6 fica em [5],
# e o codigo comeca em [6].
FIXED_LABEL_END = 5
FIXED_CONTINUATION_INDEX = 5
FIXED_CODE_START = 6
FIXED_CODE_END = 72

# Em fixed-form, a coluna 6 vazia ou com 0 significa "linha nova normal".
# Qualquer outro caracter nessa coluna significa "continuacao da anterior".
FIXED_NO_CONTINUATION_CHARS = {" ", "0"}

# Palavras que, quando aparecem no inicio sem indentacao fixed-form, ajudam
# a reconhecer que o ficheiro esta escrito em free-form.
_STATEMENT_KEYWORDS = (
    "PROGRAM",
    "INTEGER",
    "REAL",
    "LOGICAL",
    "FUNCTION",
    "SUBROUTINE",
    "CALL",
    "RETURN",
    "DO",
    "IF",
    "THEN",
    "ELSE",
    "ENDIF",
    "GOTO",
    "CONTINUE",
    "PRINT",
    "READ",
    "END",
)


def detect_source_format(source: str) -> str:
    """Decide automaticamente entre fixed-form e free-form.

    A deteccao e feita por pontuacao:
    - campos validos de fixed-form aumentam `fixed_score`;
    - linhas claramente free-form aumentam `free_score`;
    - `&` no fim de uma linha e sinal forte de free-form moderno.

    Em caso de duvida escolhemos free-form, porque o parser original ja
    trabalhava nesse formato e porque e menos destrutivo para codigo moderno.
    """
    fixed_score = 0
    free_score = 0
    saw_free_continuation = False
    previous_fixed_statement = False

    for raw_line in source.splitlines():
        # Tabs estragam a contagem de colunas; expandimos antes de olhar para
        # as posicoes fixas do Fortran 77.
        line = raw_line.expandtabs()

        # Linhas vazias nao dao informacao sobre o formato.
        if not line.strip():
            continue

        # Comentarios tambem nao devem decidir o formato. Isto evita que um
        # ficheiro free-form cheio de linhas `! ...` seja confundido com fixed.
        if _is_fixed_comment_signal(line):
            continue

        # O `&` no fim da linha e proprio do free-form. Tem prioridade porque
        # codigo free-form pode estar indentado com seis espacos e parecer
        # fixed-form so pela posicao das colunas.
        if _has_free_continuation_marker(line):
            saw_free_continuation = True
            free_score += 8  # peso alto: & no fim e exclusivo de free-form
            previous_fixed_statement = False
            continue

        # Uma linha fixed normal tem campos 1-5 validos, coluna 6 vazia/0 e
        # codigo a partir da coluna 7.
        if _is_fixed_initial_line(line):
            fixed_score += 3 if _fixed_label(line) else 2  # label numerica e sinal mais forte
            previous_fixed_statement = True
            continue

        # Uma continuacao fixed so faz sentido se ja vimos uma linha fixed
        # imediatamente antes.
        if _is_fixed_continuation_line(line) and previous_fixed_statement:
            fixed_score += 8  # peso alto: coluna 6 preenchida e muito especifico de fixed-form
            continue

        # Se nao parece fixed, damos pontos a free-form. Keywords no inicio
        # da linha sao um sinal mais forte (2) do que codigo generico (1).
        stripped_upper = line.lstrip().upper()
        if stripped_upper.startswith(_STATEMENT_KEYWORDS):
            free_score += 2
        else:
            free_score += 1

        previous_fixed_statement = False

    # Continuacao free-form e um sinal decisivo.
    if saw_free_continuation:
        return FREE_FORM

    # Se o fixed ganhou claramente, usamos fixed. No empate ou ausencia de
    # sinais, mantemos o comportamento antigo: free-form.
    return FIXED_FORM if fixed_score > free_score and fixed_score > 0 else FREE_FORM


def preprocess_source(source: str) -> str:
    """Normaliza o fonte para o formato que o parser entende."""
    source_format = detect_source_format(source)
    if source_format == FIXED_FORM:
        return _preprocess_fixed_form(source)
    return _preprocess_free_form(source)


def _preprocess_fixed_form(source: str) -> str:
    """Converte linhas fisicas fixed-form em linhas logicas free-form."""
    logical_lines: list[str] = []
    current_line: str | None = None

    for line_number, raw_line in enumerate(source.splitlines(), start=1):
        # Fixed-form so considera as colunas 1-72; texto depois da coluna 72
        # e ignorado pelo standard classico.
        physical_line = raw_line.expandtabs()[:FIXED_CODE_END].rstrip()

        # Linhas vazias e comentarios fixed-form desaparecem antes do lexer.
        if not physical_line.strip() or _is_fixed_comment_line(physical_line):
            continue

        # Garantimos que existem sempre 6 caracteres para ler os campos fixos.
        fixed_fields = physical_line[:FIXED_CODE_START].ljust(FIXED_CODE_START)
        label = fixed_fields[:FIXED_LABEL_END].strip()
        continuation = fixed_fields[FIXED_CONTINUATION_INDEX]
        body = physical_line[FIXED_CODE_START:].strip()

        # Uma linha sem codigo real nao precisa de chegar ao parser.
        if not body:
            continue

        # Qualquer caracter diferente de espaco/0 na coluna 6 continua a linha
        # logica anterior.
        if continuation not in FIXED_NO_CONTINUATION_CHARS:
            if current_line is None:
                raise SyntaxError(
                    f"Fixed-form continuation without previous statement at line {line_number}."
                )
            current_line = _join_continuation(current_line, body)
            continue

        # Ao encontrar uma nova linha inicial, fechamos a linha logica anterior.
        if current_line is not None:
            logical_lines.append(current_line.rstrip())

        # Labels fixed-form passam para o inicio da linha, porque o parser ja
        # entende `10 CONTINUE`, `20 IF (...) THEN`, etc.
        current_line = f"{label} {body}".strip() if label else body

    # No fim do ficheiro ainda pode haver uma linha logica por fechar.
    if current_line is not None:
        logical_lines.append(current_line.rstrip())

    return _finish_preprocessed_source(logical_lines)


def _preprocess_free_form(source: str) -> str:
    """Remove comentarios free-form e resolve continuacoes com `&`."""
    logical_lines: list[str] = []
    current_line: str | None = None
    continuing = False

    for raw_line in source.splitlines():
        # Em free-form, `!` inicia comentario exceto dentro de strings.
        code = _strip_free_comment(raw_line.rstrip()).strip()
        if not code:
            continue

        # Quando a linha anterior terminou com `&`, a linha seguinte pode
        # comecar tambem por `&`. Esse marcador nao faz parte do codigo.
        if continuing and code.startswith("&"):
            code = code[1:].lstrip()

        # `&` no fim da linha indica que o statement continua na proxima.
        has_continuation = code.endswith("&")
        if has_continuation:
            code = code[:-1].rstrip()

        # Comecamos uma linha logica nova ou juntamos a continuacao atual.
        if current_line is None:
            current_line = code
        else:
            current_line = _join_continuation(current_line, code)

        # Se ainda ha continuacao, esperamos pela proxima linha fisica.
        if has_continuation:
            continuing = True
            continue

        # Sem continuacao, a linha logica esta pronta para o parser.
        logical_lines.append(current_line.rstrip())
        current_line = None
        continuing = False

    # Se o ficheiro termina a meio de uma continuacao, mantemos o que existe;
    # o parser/semantica dara erro se a expressao ficar invalida.
    if current_line is not None:
        logical_lines.append(current_line.rstrip())

    return _finish_preprocessed_source(logical_lines)


def _is_fixed_initial_line(line: str) -> bool:
    """Verifica se uma linha parece uma linha inicial fixed-form."""
    if len(line) < 7:
        return False

    fixed_fields = line[:FIXED_CODE_START].ljust(FIXED_CODE_START)
    label_field = fixed_fields[:FIXED_LABEL_END]
    continuation = fixed_fields[FIXED_CONTINUATION_INDEX]
    body = line[FIXED_CODE_START:].strip()
    return (
        bool(body)
        and _is_fixed_label_field(label_field)
        and continuation in FIXED_NO_CONTINUATION_CHARS
    )


def _is_fixed_continuation_line(line: str) -> bool:
    """Verifica se uma linha parece uma continuacao fixed-form."""
    if len(line) < 7:
        return False

    fixed_fields = line[:FIXED_CODE_START].ljust(FIXED_CODE_START)
    label_field = fixed_fields[:FIXED_LABEL_END]
    continuation = fixed_fields[FIXED_CONTINUATION_INDEX]
    body = line[FIXED_CODE_START:].strip()
    return (
        bool(body)
        and _is_fixed_label_field(label_field)
        and continuation not in FIXED_NO_CONTINUATION_CHARS
    )


def _is_fixed_label_field(label_field: str) -> bool:
    """Labels fixed-form so podem ter digitos ou espacos."""
    return all(character == " " or character.isdigit() for character in label_field)


def _fixed_label(line: str) -> str:
    """Extrai o label das colunas 1-5."""
    return line[:FIXED_LABEL_END].strip()


def _is_fixed_comment_line(line: str) -> bool:
    """Comentarios reais quando ja estamos a processar fixed-form."""
    if not line:
        return False
    return line[0] in {"C", "c", "*", "!"}


def _is_fixed_comment_signal(line: str) -> bool:
    """Comentario usado apenas como sinal fraco durante a deteccao.

    `CALL` em free-form tambem comeca por `C`, por isso so tratamos `C`/`c`
    como comentario na deteccao quando vem seguido de whitespace.
    """
    if not line:
        return False
    if line[0] in {"*", "!"}:
        return True
    if line[0] in {"C", "c"}:
        return len(line) == 1 or line[1].isspace()
    return False


def _has_free_continuation_marker(line: str) -> bool:
    """Indica se a linha tem `&` final fora de comentario free-form."""
    return _strip_free_comment(line).rstrip().endswith("&")


def _join_continuation(left: str, right: str) -> str:
    """Junta duas partes de uma linha logica.

    O subset atual nao suporta continuacao no meio de tokens, por isso inserir
    um espaco entre partes e a opcao mais legivel e segura para expressoes,
    PRINTs, chamadas e declaracoes.
    """
    if not right:
        return left
    if not left:
        return right
    return f"{left.rstrip()} {right.lstrip()}"


def _strip_free_comment(line: str) -> str:
    """Remove comentarios `!` sem cortar strings com apostrofos.

    O `!` so e comentario fora de strings. Strings Fortran usam aspas simples
    e escapam apostrofos internos com `''` (dois apostrofos seguidos, nao
    barra invertida). Por isso percorremos caracter a caracter.
    """
    in_string = False
    index = 0
    while index < len(line):
        character = line[index]
        if character == "'":
            if in_string and index + 1 < len(line) and line[index + 1] == "'":
                # Par de apostrofos dentro de string = apostrofo literal; avanca 2.
                index += 2
                continue
            in_string = not in_string
        elif character == "!" and not in_string:
            return line[:index]
        index += 1
    return line


def _finish_preprocessed_source(lines: list[str]) -> str:
    """Garante newline final para o PLY receber o ultimo statement completo."""
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


__all__ = ["FREE_FORM", "FIXED_FORM", "detect_source_format", "preprocess_source"]
