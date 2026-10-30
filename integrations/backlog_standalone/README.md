# DOMINIUM Backlog — nova infraestrutura Cloudflare

Data: 30/10/2026. Ambiente de desenvolvimento: `feat/analise-backlog-desc-live-20261030`, PR #29.

## Recursos realmente criados na conta Cloudflare conectada

- Conta: `416ec837ec86eec81dcc8dcade3d32ae`.
- Túnel remoto: `dominium-backlog-tunnel` — `f5d15625-20e7-443c-b33a-04d5e7a07904`; estado após criação: **inactive**.
- Workers VPC Service: `dominium-backlog-api-9342` — `01a18e5e-7364-70e2-8eb0-613c7069f2ca`.
- VPC Service aponta para IPv4 `127.0.0.1`, porta HTTP `9342`, usando o túnel criado.
- Worker antigo `analise-backlog` continua o único Worker publicado na conta neste momento.

## Novo Worker preparado, NÃO publicado

Arquivos: `integrations/backlog_standalone/worker.mjs`, `wrangler.jsonc`, `worker.test.mjs`.

Worker separado `dominium-backlog-bridge`, com binding VPC `BACKLOG_SERVICE`. Ele expõe apenas `GET /health` sem dados sensíveis; as operações `/api/backlog/year/*` ficam **desabilitadas** enquanto não houver a credencial privada `BACKLOG_BRIDGE_TOKEN` no Worker e o binding ativo. Testes cobrem rejeição de rotas desconhecidas, ausência de credencial, roles de leitura e limites de payload.

- Cinco testes Node passaram; `wrangler deploy --dry-run` passou e reconheceu o binding VPC.
- **Tentativa de deploy real foi bloqueada pela ferramenta remota**. Não registrar esse Worker como publicado.
- Nenhuma mudança na `main`, Worker legado, site Hostinger ou baixas de O.S.

## Etapa manual necessária: conectar o túnel no servidor

No painel da conta Cloudflare correta, abra **Workers VPC → Tunnels → dominium-backlog-tunnel → Add replica → Windows**. No computador `DESKTOP-K7J3E1N`, abra PowerShell ou Terminal como **Administrador** e execute o comando **gerado pelo painel** para instalar o `cloudflared` como serviço Windows.

Não colar o token no ChatGPT nem armazená-lo em arquivos públicos. O conector precisa aparecer como `healthy`. Antes de rodar o comando, conferir que não existe serviço `cloudflared` de outra automação; caso exista, usar instalação isolada.

## Após conectar o túnel

1. Confirmar com Cloudflare API que o túnel está `healthy` e que VPC Service aponta a 9342.
2. Publicar `integrations/backlog_standalone` com Wrangler autenticado na conta `416ec837ec86eec81dcc8dcade3d32ae`. No momento o deploy automatizado foi negado pela ferramenta.
3. Configurar `BACKLOG_BRIDGE_TOKEN` como **secret**, nunca como `vars` ou código-fonte. Deve coincidir com o segredo esperado pelo sidecar do servidor. Não reutilizar token por mensagem.
4. Testar `/health`, falha anônima 401/503 e requisição autenticada a `/api/backlog/year/status`.
5. Integrar apenas através do backend autenticado da Hostinger, com RBAC e CSRF. A aplicação deve encaminhar a chamada ao Worker somente depois de autenticar o usuário.
6. Homologar importação manual, 106/404/306, bairros, regras de Fora de Rota e os quatro perfis. **Não habilitar carga anual completa antes de controlar volume, checkpoints e reconciliação.**

## Rollback

Desativar/deletar apenas o Worker novo e o VPC Service novo; parar o conector do túnel novo no Windows. Não remover nada do Worker `analise-backlog` ou dos canais DESC atuais. Preservar dados do SQLite de laboratório e logs sem informações sensíveis.

Fonte: https://developers.cloudflare.com/workers-vpc/get-started/
