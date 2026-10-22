# DOMINIUM | Confronto Atlas × IMPERIUM — Recursos → Pendente

## Implementação em 22/10/2026

A funcionalidade foi desenvolvida no checkout isolado:
`C:\DominiumRuntime\SerialMultiCityPatch-20261022`

### Interface e segurança

- Nova entrada **Pendente** logo após **Consultar Seriais** no menu Recursos.
- Suporte até 500 seriais por trabalho, quatro praças, consulta Analítico/Sintético.
- Backend de trabalhos SQLite durável, fila e progresso, recuperação segura após interrupções.
- Confronto somente leitura e categorização conservadora: convergente, divergente,
  revisão, inconclusivo. Histórico não confirma posse atual.
- CSV protegido contra execução de fórmulas.
- Hostinger: sessão DOMINIUM obrigatória; POST usa CSRF; somente admin/controller.
- Worker privado Cloudflare exige token e papel; VPC encaminha ao relay DESC
  em loopback. Cookies e CSRF do navegador não são encaminhados.
- Relay verifica token novamente e separa trabalhos por **ID autenticado**;
  um operador não abre dados de outro pelo ID do trabalho.

### Infraestrutura Atlas encontrada

- Chrome for Testing em `D:\Dominium\Tools\ChromeForTesting-156\chrome-win64\chrome.exe`
- Extensão real em `C:\DominiumRuntime\ManagedAtlasTOA-20261022\extension`
- Atlas consultado pela fila do BotDMV, não por navegador do operador:
  `POST /atlas/queue-query` → extensão → `POST /atlas/resolve-query`
  → `GET /atlas/query-result/{requestId}`.
- Bridge BotDMV executa no Ubuntu/WSL, Windows porta 8787 mapeada ao WSL.
- Consulta Atlas serial fictício foi enfileirada e respondida como negativa;
  um serial **real** ainda precisa ser validado junto ao estoque.

### Código

- `integrations/serial_consult/confront_engine.py`: regras e lotes.
- `integrations/serial_consult/atlas_bridge_client.py`: cliente de fila existente.
- `integrations/serial_consult/confront_job_runner.py`: SQLite e retomada.
- `integrations/serial_consult/confront_http.py`: API privada e worker.
- `integrations/serial_consult/confront_export.py`: CSV.
- `integrations/serial_consult/desc_review_relay.py`: extensão do relay.
- `deploy/hostinger-web/confront-policy.js`, `operational-relay.js`,
  `server.js`: autenticação, CSRF, isolamento e roteamento.
- `integrations/import_bridge/worker.mjs`: encaminhamento VPC com token.
- `static/confront.js`, `static/index.html`, `static/app.js`: painel.

### Deploy e rollback

- Relay DESC ativo em `C:\DominiumRuntime\DescRelay-20261010` recebeu
  patch mínimo com preservação de REPORTs e serviços existentes.
- Backup: `C:\DominiumRuntime\DescRelay-20261010\backups\pre-confront-20261022-191438`.
- Relay na porta 8793 foi reiniciado e passou o smoke local com autenticação.
- Worker `dominium-import-bridge` foi publicado e passou smoke privado via Node:
  controller=200; viewer=403; sem token=401; trabalho inexistente=404.
- Publicação Hostinger do frontend será realizada após testes e commit Git.
- O bot WSL, Chrome gerenciado e IMPERIUM não foram reiniciados por esta implementação.

### Validações e limites restantes

- Quality gate, testes HTTP, Python e Node executados; os resultados devem
  ser conferidos na versão final antes do push.
- Não há confronto positivo com equipamento real validado. Antes de confiar
  nas categorias de "divergente" ou "convergente", estoque deve conferir casos.
- A fila original do BotDMV ainda opera em memória e não oferece idempotência;
  o adaptador evita novo POST automático quando o envio ficou incerto.
- A porta 8787 do WSL escuta em todas as interfaces; restringir pela rede
  numa etapa posterior sem quebrar acesso do Chrome/WhatsApp existente.
- Nenhuma operação de baixa, movimentação ou alteração de cadastro é
  oferecida pelo módulo.
