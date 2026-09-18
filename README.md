# DOMINIUM

DOMINIUM e o painel operacional da Technet para ordens de servico, TOA, Imperium, estoque, automacoes e controle de acesso.

## Fonte oficial

O checkout de desenvolvimento neste PC e a fonte de verdade. Estado de navegador, credenciais, bancos locais, logs, caches e evidencias geradas nao fazem parte do codigo-fonte.

## Desenvolvimento

Prepare o ambiente de desenvolvimento:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Inicie o painel local:

```powershell
.\.venv\Scripts\python.exe app.py --host 127.0.0.1 --port 8766
```

Os testes ficam em `tests/`. Antes de qualquer push/deploy, execute:

```powershell
.\.venv\Scripts\python.exe .\scripts\quality_gate.py
```

O gate executa a suite Python, os testes JavaScript, lint critico, build do release e auditoria do pacote.

## Release web

Para gerar somente os arquivos necessarios em producao:

```powershell
.\.venv\Scripts\python.exe .\scripts\build_web_release.py
```

Saidas:

- `output/dominium-web-release/`
- `output/dominium-web-release.zip`
- `output/dominium-web-release/RELEASE_MANIFEST.json`

O release nao inclui testes, segredos, `.dat`, perfil do Chrome, dados locais, logs, backups, caches ou helpers Windows de desenvolvimento.

## Autenticacao

O backend recomendado e Supabase. O navegador nunca recebe a Secret Key. Login continua por username; internamente o Auth usa o dominio sintetico `auth.dominium.invalid`.

Novos cadastros ficam pendentes. Administradores aprovam escolhendo o cargo ou recusam com motivo opcional.

## Estrutura

- `app.py`: servidor web e orquestracao principal.
- `static/`: frontend.
- `config/`: somente configuracao fonte; estado de runtime e credenciais sao ignorados pelo Git.
- `tests/`: testes Python e JavaScript.
- `scripts/`: ferramentas de validacao, bootstrap e release.
- `supabase/`: migrations.
- `deploy/`: templates e instrucoes de deploy.
- `docs/`: historico e referencias tecnicas.

## Fluxo de publicacao

Fluxo pretendido: alteracao local -> quality gate -> commit -> push -> deploy/rebuild no servidor -> smoke test.
