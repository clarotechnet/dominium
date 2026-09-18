@echo off
REM =============================================================================
REM DOMINIUM | MAPA DE RESPONSABILIDADE
REM
REM IMPERIUM
REM - NAO - este arquivo nao envia operacoes ao Imperium.
REM
REM TOA
REM - SIM - sessao, coleta, importacao, inventario ou monitor do TOA.
REM
REM DOMINIUM COMPARTILHADO
REM - A saida pode alimentar o restante do DOMINIUM em modo leitura.
REM
REM Categoria deste arquivo: TOA.
REM Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
REM A ordem executavel abaixo foi preservada para evitar regressao.
REM =============================================================================
title DOMINIUM TOA - Conectar
cd /d "%~dp0"
py -3 toa_browser.py
if errorlevel 1 pause
