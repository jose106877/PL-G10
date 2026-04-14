PROGRAM IFGOTO
INTEGER N
PRINT *, 'Introduza um numero:'
READ *, N
IF (N .GT. 0) THEN
  PRINT *, 'Positivo'
ELSE
  PRINT *, 'Zero ou negativo'
ENDIF
GOTO 100
PRINT *, 'Esta linha nao deve correr'
100 CONTINUE
PRINT *, 'Fim'
END
