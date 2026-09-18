@echo off
REM =============================================================================
REM DOMINIUM | MAPA DE RESPONSABILIDADE
REM
REM IMPERIUM
REM - NAO DIRETO - infraestrutura comum, sem regra de negocio Imperium.
REM
REM TOA
REM - NAO DIRETO - infraestrutura comum, sem regra de negocio TOA.
REM
REM DOMINIUM COMPARTILHADO
REM - SIM - seguranca, interface, voz, empacotamento ou inicializacao.
REM
REM Categoria deste arquivo: COMPARTILHADO.
REM Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
REM A ordem executavel abaixo foi preservada para evitar regressao.
REM =============================================================================
title DOMINIUM - Console Unificado
cd /d "%~dp0"
py -3 -m operation_scope --check-project
if errorlevel 1 (
  echo Projeto recusado: execute somente FerramentaImperiumDireto-OLLAMA.
  pause
  exit /b 2
)
py -3 -u app.py --port 8765 --open
if errorlevel 1 pause
