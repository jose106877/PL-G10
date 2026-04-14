from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
