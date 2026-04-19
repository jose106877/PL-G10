from __future__ import annotations

import unittest
from pathlib import Path

from src.codegen import CompilerError
from src.compiler import compile_source_to_vm


class CompilerSmokeTests(unittest.TestCase):
    def test_assignment_and_print(self):
        source = """PROGRAM TESTE
INTEGER A
A = 2 + 3
PRINT *, A
END
"""

        vm_code = compile_source_to_vm(source)

        self.assertIn("START", vm_code)
        self.assertIn("PUSHN 1", vm_code)
        self.assertIn("PUSHI 2", vm_code)
        self.assertIn("PUSHI 3", vm_code)
        self.assertIn("ADD", vm_code)
        self.assertIn("STOREG 0", vm_code)
        self.assertIn("PUSHG 0", vm_code)
        self.assertIn("WRITEI", vm_code)
        self.assertIn("WRITELN", vm_code)
        self.assertIn("STOP", vm_code)

    def test_undeclared_variable_raises(self):
        source = """PROGRAM TESTE
INTEGER A
B = 10
END
"""

        with self.assertRaises(CompilerError):
            compile_source_to_vm(source)

    def test_if_else_generates_jumps(self):
        source = """PROGRAM TESTE
INTEGER A, B
A = 3
B = 0
IF (A .GT. 0) THEN
  B = 1
ELSE
  B = 2
ENDIF
PRINT *, B
END
"""

        vm_code = compile_source_to_vm(source)

        self.assertIn("SUP", vm_code)
        self.assertIn("JZ IF_ELSE_", vm_code)
        self.assertIn("JUMP IF_END_", vm_code)
        self.assertIn("IF_ELSE_", vm_code)
        self.assertIn("IF_END_", vm_code)

    def test_goto_and_label(self):
        source = """PROGRAM TESTE
INTEGER A
A = 0
GOTO 100
A = 1
100 CONTINUE
PRINT *, A
END
"""

        vm_code = compile_source_to_vm(source)

        self.assertIn("JUMP L100", vm_code)
        self.assertIn("L100:", vm_code)
        self.assertIn("NOP", vm_code)

    def test_goto_to_undefined_label_raises(self):
        source = """PROGRAM TESTE
INTEGER A
A = 0
GOTO 999
PRINT *, A
END
"""

        with self.assertRaises(CompilerError):
            compile_source_to_vm(source)

    def test_do_loop_generates_condition_and_back_jump(self):
        source = """PROGRAM TESTE
INTEGER I, N, S
N = 4
S = 0
DO 10 I = 1, N
S = S + I
10 CONTINUE
PRINT *, S
END
"""

        vm_code = compile_source_to_vm(source)

        self.assertIn("DO_CHECK_", vm_code)
        self.assertIn("INFEQ", vm_code)
        self.assertIn("DO_EXIT_", vm_code)
        self.assertIn("JUMP DO_CHECK_", vm_code)

    def test_do_loop_requires_continue_at_end_label(self):
        source = """PROGRAM TESTE
INTEGER I, N
N = 3
DO 10 I = 1, N
10 I = I + 1
END
"""

        with self.assertRaises(CompilerError):
            compile_source_to_vm(source)

    def test_do_loop_requires_closing_label(self):
        source = """PROGRAM TESTE
INTEGER I, N
N = 3
DO 10 I = 1, N
I = I + 1
END
"""

        with self.assertRaises(CompilerError):
            compile_source_to_vm(source)

    def test_array_assignment_and_access_generate_loadn_storen(self):
        source = """PROGRAM TESTE
INTEGER A(3), I, S
I = 2
A(1) = 10
A(I) = 20
S = A(1) + A(I)
PRINT *, S
END
"""

        vm_code = compile_source_to_vm(source)

        self.assertIn("CHECK 1, 3", vm_code)
        self.assertIn("STOREN", vm_code)
        self.assertIn("LOADN", vm_code)

    def test_array_requires_index_when_used_as_scalar(self):
        source = """PROGRAM TESTE
INTEGER A(3), X
X = A
END
"""

        with self.assertRaises(CompilerError):
            compile_source_to_vm(source)

    def test_scalar_cannot_be_used_as_array(self):
        source = """PROGRAM TESTE
INTEGER X
X(1) = 5
END
"""

        with self.assertRaises(CompilerError):
            compile_source_to_vm(source)

    def test_real_arithmetic_generates_float_vm_ops(self):
        source = """PROGRAM TESTE
REAL X, Y, Z
X = 1.5
Y = 2
Z = X + Y
PRINT *, Z
END
"""

        vm_code = compile_source_to_vm(source)

        self.assertIn("PUSHF 1.5", vm_code)
        self.assertIn("ITOF", vm_code)
        self.assertIn("FADD", vm_code)
        self.assertIn("WRITEF", vm_code)

    def test_logical_ops_and_if_compile(self):
        source = """PROGRAM TESTE
LOGICAL A, B, C
A = .TRUE.
B = .FALSE.
C = A .OR. B
IF (C) THEN
  PRINT *, 'ok'
ENDIF
END
"""

        vm_code = compile_source_to_vm(source)

        self.assertIn("OR", vm_code)
        self.assertIn("JZ IF_ELSE_", vm_code)

    def test_if_requires_logical_condition(self):
        source = """PROGRAM TESTE
INTEGER A
A = 1
IF (A) THEN
  PRINT *, 'x'
ENDIF
END
"""

        with self.assertRaises(CompilerError):
            compile_source_to_vm(source)

    def test_mod_function_call_compiles(self):
        source = """PROGRAM TESTE
INTEGER A, B, R
A = 10
B = 3
R = MOD(A, B)
PRINT *, R
END
"""

        vm_code = compile_source_to_vm(source)

        self.assertIn("MOD", vm_code)

    def test_mod_requires_integer_args(self):
        source = """PROGRAM TESTE
REAL A
INTEGER B, R
A = 10.0
B = 3
R = MOD(A, B)
END
"""

        with self.assertRaises(CompilerError):
            compile_source_to_vm(source)

    def test_example_fatorial_compiles(self):
        source = Path("examples/fatorial_do.f77").read_text(encoding="utf-8")
        vm_code = compile_source_to_vm(source)
        self.assertIn("MUL", vm_code)

    def test_example_soma_array_compiles(self):
        source = Path("examples/soma_array.f77").read_text(encoding="utf-8")
        vm_code = compile_source_to_vm(source)
        self.assertIn("LOADN", vm_code)

    def test_example_primo_compiles(self):
        source = Path("examples/primo.f77").read_text(encoding="utf-8")
        vm_code = compile_source_to_vm(source)
        self.assertIn("MOD", vm_code)
        self.assertIn("L20:", vm_code)

    def test_example_real_logical_compiles(self):
        source = Path("examples/real_logical_demo.f77").read_text(encoding="utf-8")
        vm_code = compile_source_to_vm(source)
        self.assertIn("FADD", vm_code)
        self.assertIn("WRITEF", vm_code)

    def test_example_conversor_compiles(self):
        source = Path("examples/conversor.f77").read_text(encoding="utf-8")
        vm_code = compile_source_to_vm(source)
        self.assertIn("MOD", vm_code)
        self.assertIn("FN_RET_CONVRT", vm_code)

    def test_undefined_user_function_raises(self):
        source = """PROGRAM TESTE
INTEGER A, B, R
A = 10
B = 3
R = CONVRT(A, B)
END
"""

        with self.assertRaises(CompilerError):
            compile_source_to_vm(source)

    def test_subroutine_call_compiles(self):
        source = """PROGRAM TESTE
INTEGER A, B
A = 2
B = 3
CALL SHOWSUM(A, B)
END
SUBROUTINE SHOWSUM(X, Y)
INTEGER X, Y, S
S = X + Y
PRINT *, S
RETURN
END
"""

        vm_code = compile_source_to_vm(source)

        self.assertIn("SUB_RET_SHOWSUM", vm_code)
        self.assertIn("ADD", vm_code)

    def test_undefined_subroutine_raises(self):
        source = """PROGRAM TESTE
INTEGER A
A = 1
CALL SHOW(A)
END
"""

        with self.assertRaises(CompilerError):
            compile_source_to_vm(source)

    def test_call_on_function_name_raises(self):
        source = """PROGRAM TESTE
INTEGER A, B, F
A = 1
B = 2
CALL F(A, B)
END
INTEGER FUNCTION F(X, Y)
INTEGER X, Y
F = X + Y
RETURN
END
"""

        with self.assertRaises(CompilerError):
            compile_source_to_vm(source)

    def test_example_subroutine_compiles(self):
        source = Path("examples/subroutine_demo.f77").read_text(encoding="utf-8")
        vm_code = compile_source_to_vm(source)
        self.assertIn("SUB_RET_SHOWSUM", vm_code)


if __name__ == "__main__":
    unittest.main()
