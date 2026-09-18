# CHECKPOINT - recuperacao Selenium / Chrome TOA

Data: 17/09/2026

Alterado `toa_live.py` para recuperar automaticamente sessoes Selenium/DevTools mortas.

Comportamento novo:
- detecta `invalid session id`, `not connected to DevTools`, `chrome not reachable` e janela encerrada;
- descarta o ChromeDriver antigo sem matar um Chrome valido desnecessariamente;
- se havia sessao ativa e ela caiu, recria/reanexa o driver automaticamente;
- o monitor continua passivo quando nunca houve sessao: nao abre Chrome sozinho no primeiro uso;
- operacoes somente-leitura recebem uma unica tentativa automatica apos reconexao;
- consulta de contrato TECHCAP recebe uma unica repeticao segura apos queda;
- estado publico registra `last_recovery_at`.

Testes adicionados em `test_toa_live.py` para monitor, leitura e lookup com desconexao.

Validacao:
- `python -m unittest test_toa_live.py`: 21 OK;
- browser/conector/live lookup: 19 OK;
- `python -m unittest test_app.py`: 25 OK;
- total relacionado executado: 65 testes OK;
- `git diff --check -- toa_live.py test_toa_live.py`: OK.

Backup anterior: `backups/selenium_recovery_20260917/`.
