# DOMINIUM — Backlog Cloudflare + Hostinger: validação 30/10/2026

## Confirmado em produção Cloudflare
- Conta Cloudflare: `416ec837ec86eec81dcc8dcade3d32ae`
- Túnel: `dominium-backlog-tunnel`, healthy, uma conexão ativa no servidor `DESKTOP-K7J3E1N`.
- VPC Service `dominium-backlog-api-9342`, ID `01a18e5e-7364-70e2-8eb0-613c7069f2ca`.
- Worker publicado: `dominium-backlog-bridge` com binding `BACKLOG_SERVICE` para porta 9342.
- Subdomínio workers.dev habilitado via API em 30/10/2026.
- Teste HTTP público `/health`: **200**, resposta `dominium-backlog-bridge / isolated`.
- Teste público sem token `/api/backlog/year/status`: **503**, bloqueado por ausência do segredo, conforme planejado.
- Teste rota não autorizada `/api/orders/1/close`: **404**, sem encaminhamento.
- Worker ainda **não tem** secret `BACKLOG_BRIDGE_TOKEN`. Não colocar esse valor no GitHub, logs, HTML ou conversa.

## Backend Windows
- No `DESKTOP-K7J3E1N`: `Cloudflared` Windows service Running/Auto, porta 9342 ativa, 8765 e 8793 preservadas.
- Sidecar Python em `127.0.0.1:9342`, não substitui o Imperium operacional.
- Sidecar **ainda** lê token legado do Relay DESC. Para isolamento real, criar token dedicado e atualizar o `--token-file` do sidecar antes de configurar o Worker (não copiar o token Relay para o Worker público). Gerar com CSPRNG, proteger ACL da pasta (usuário do serviço, SYSTEM e Administrators), reiniciar **somente o Sidecar**, testar 401/200 na porta 9342 e preservar arquivo antigo para rollback.
- A tentativa de criar ACL/credencial pelo acesso remoto foi bloqueada. Não presumir que token dedicado existe ou que sidecar foi reiniciado.

## Integração Hostinger implementada na branch de LAB
- Novo `deploy/hostinger-web/backlog-proxy.js` e rota `/api/backlog/year` após o middleware global de sessão e CSRF no `server.js`.
- Somente `admin/controller`, rota exata da allowlist, CSRF com hash no POST, ator derivado da sessão, sem forward de cookies, autorização do usuário ou CSRF ao Worker.
- Reenvia pelo Hostinger para `https://dominium-backlog-bridge.dmv-analise-backlog.workers.dev`, usando `DOMINIUM_BACKLOG_BRIDGE_TOKEN` **apenas no servidor Node**.
- Ausência de token provoca 503 seguro; não habilitar o frontend isolado se não houver conexão ponta a ponta.
- `scripts/build_hostinger_node_release.py` atualizado para empacotar e exigir o novo módulo de proxy.
- **5 testes Node** específicos do proxy + **27 testes Node** selecionados totais + **25 testes Python** aprovados. ZIP da Hostinger íntegro, incluindo `backlog-proxy.js`, `server.js` e assets.
- Hostinger publicada **não alterada**; este código está apenas na branch de laboratório/PR #29.

## Bloqueios antes do deploy e de carregar 1 ano
1. Gerar o token privado dedicado e configurar o mesmo valor nos três pontos: arquivo de token do Sidecar Windows, secret `BACKLOG_BRIDGE_TOKEN` do Worker e secret de ambiente `DOMINIUM_BACKLOG_BRIDGE_TOKEN` do Node na Hostinger. **Não expor o token ao navegador**.
2. Teste E2E: negar usuários anônimos e viewers no site; controller autorizado obtém GET status e POST probe; toda baixa de OS fora da allowlist continua recusada.
3. Homologar regras de Fora de Rota, estoque, cidades e reconciliação DataSnap TODOS/TODOS. Só então liberar `DOMINIUM_BACKLOG_YEAR_ENABLE=1`.
4. Backup e rollback do Node Hostinger antes de publicar; a infraestrutura Cloudflare já está isolada, não alterar Worker legado.

## Estado
- Cloudflare tunnel + Worker + VPC: **publicados e validados** quanto a túnel e /health.
- Backend Sidecar local: **ativo**, porém ainda usa segredo Relay anterior.
- Hostinger: **código pronto, ainda não publicado**.
- Secret dedicado: **pendente**.
- Supabase: **não integrado à carga anual**; a persistência atual continua no SQLite isolado.
- Nenhum Worker legado nem baixa de O.S. foi alterado.
