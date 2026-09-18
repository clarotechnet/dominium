@echo off
REM =============================================================================
REM DOMINIUM | MAPA DE RESPONSABILIDADE
REM
REM IMPERIUM
REM - SIM - protocolo, baixa, estoque ou operacao do Imperium.
REM
REM TOA
REM - NAO - este arquivo nao consulta nem automatiza o TOA.
REM
REM DOMINIUM COMPARTILHADO
REM - Apoio local apenas quando necessario ao fluxo Imperium.
REM
REM Categoria deste arquivo: IMPERIUM.
REM Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
REM A ordem executavel abaixo foi preservada para evitar regressao.
REM =============================================================================
title DOMINIUM FlowScope - Leitor de Fluxos
cd /d "%~dp0"
echo ============================================================
echo          DOMINIUM FLOWSCOPE - SOMENTE LEITURA
echo ============================================================
echo.
echo O leitor abrira em http://127.0.0.1:8787
echo Esta ferramenta nao envia nem altera dados no Imperium.
echo Mantenha esta janela aberta enquanto estiver usando o leitor.
echo.
py -3 -m flow_reader.server --port 8787 --open
if errorlevel 1 (
  echo.
  echo Nao foi possivel iniciar o leitor.
  pause
)
