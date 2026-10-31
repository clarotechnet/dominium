# Backlog DOMINIUM — situação consolidada 30/10/2026

Esta branch é **isolada** da PR #29 (`feat/analise-backlog-unificado-20261030`).
Não deve ser mesclada automaticamente nem implantada na Hostinger.

## Estado verificado

- Cloudflare: conta correta `416ec837ec86eec81dcc8dcade3d32ae`; Tunnel
  `dominium-backlog-tunnel` saudável, com quatro conexões ativas;
  Workers VPC Service `dominium-backlog-api-9342`; Worker isolado
  `dominium-backlog-bridge` publicado, com binding `BACKLOG_SERVICE`.
- Worker publicamente acessível em
  `https://dominium-backlog-bridge.dmv-analise-backlog.workers.dev`:
  `GET /health` = 200; `GET /api/backlog/year/status` sem credencial = 503;
  rota inexistente = 404.
- IMPORTANTE: `/health` testa **somente o Worker**, não o DataSnap.
- Server TECHNET `DESKTOP-K7J3E1N`: cloudflared é serviço Windows
  `Running`; sidecar Python `C:\DominiumRuntime\BacklogLab-20261030\app\backlog_sidecar.py`
  escuta apenas `127.0.0.1:9342`. GET local autenticado em
  `/api/backlog/year/status` foi 200, sem iniciar importação.
- Sidecar usa **atualmente** um arquivo de credencial do Relay DESC;
  um novo arquivo privado dedicado ao Backlog foi gerado e protegido por ACL,
  mas **ainda não está ativo**. Não compartilhar os valores no chat.
- Worker **ainda não possui** o secret `BACKLOG_BRIDGE_TOKEN`; a
  transferência automática do segredo foi recusada pelo controle de segurança.
  Não contornar. Configuração deve ser realizada manualmente por operador autorizado,
  seguida de rotação do sidecar e smoke autenticado.
- PR #29: rascunho e sem merge, não foi modificada nesta intervenção.
  `main`/Hostinger e fechamentos reais de O.S. não foram modificados.

## Supabase

Projeto DOMINIUM (`haqzzxpocwzntyudrbch`), schema **privado**
`backlog_lab`; RLS ativo. Existiam três tabelas vazias:
`history`, `import_batches`, `sent_routes`.
A migração **já aplicada e verificada** `20261031022826_backlog_datasnap_private_history_v1`
acrescentou campos DataSnap em `history` e criou
`datasnap_checkpoints` e `datasnap_sync_runs`.
As cinco tabelas permanecem vazias. `anon` e `authenticated`
não têm `USAGE` no schema. `service_role` tem permissões
de leitura/escrita necessárias no banco, mas o backend ainda não foi
conectado ao Supabase. Não confundir com disponibilidade por REST:
schema privado não está exposto à Data API.

### Mapeamento proposto do SQLite para Supabase

| SQLite `history` | Supabase `backlog_lab.history` |
|---|---|
| `profile:id_os:activity_date` | `legacy_id` (PK idempotente) |
| `profile` | `source_profile`, `cidade` normalizada |
| `id_os` | `source_id_os` |
| `activity_date` | `activity_date`, `baixa_date` se comprovada |
| `os_number` | `os_number` |
| `contract` | `contract` |
| `service` | `service` |
| `code` | `baixa_code` ou `''` quando não confirmado |
| `verification` | `source_verification` |
| `status` | `source_status` |
| `captured_at` | `datasnap_captured_at` |

Não converter `missing_code` em concluído, não inventar códigos.
Gravar dados e checkpoint na mesma transação por dia e perfil,
somente depois da reconciliação DataSnap TODOS/TODOS e validação
dos detalhes da O.S. Repetições devem fazer UPSERT por
`legacy_id = profile:id_os:date`; não multiplicar registros.

O SQLite permanece como recuperação temporária, não como fonte
inquestionável de histórico. A carga anual total permanece
**desabilitada**, aguardando testes de volume, retomada e conciliação.

## Etapas ainda necessárias para operação completa

1. Configurar `BACKLOG_BRIDGE_TOKEN` como *secret* no Worker pelo
   dashboard/ambiente autorizado. Usar uma credencial dedicada e
   distinta da do Relay DESC, sem copiá-la para log, Git ou conversa.
2. Ativar o token dedicado no serviço Backlog 9342 com mudança
   controlada e rollback; configurar supervisão persistente no Windows.
3. Smoke ponta a ponta: 200 em leitura autenticada, 401/403 sem acesso,
   404 em rota desconhecida. Não usar endpoint de carga anual nesse teste.
4. **Adaptador offline implementado e testado:** `integrations/backlog_standalone/supabase_datasnap_sync.py` + `test_supabase_datasnap_sync.py`. São 17 testes aprovados. A função `sync_verified_day` somente lê dias com checkpoint confirmado no SQLite e prepara UPSERT idempotente de histórico + checkpoint numa mesma transação PostgreSQL. O SQL foi validado com `EXPLAIN` no Supabase. **Ainda não há conexão PostgreSQL credenciada nem sincronização real**, e nenhum dado foi gravado.
5. Configurar acesso PostgreSQL exclusivamente no backend privado (nunca no navegador) e testar um dia/uma cidade com DataSnap SOMENTE leitura; comparar contagens e códigos antes de gravar. Depois testar quatro cidades. Só então habilitar carga anual.
6. Ligar UI via backend autenticado Hostinger com RBAC/CSRF,
   sem fetch direto do navegador ao Worker e sem merge cego da PR #29.

### Rollback

Desabilitar apenas `dominium-backlog-bridge` no workers.dev se necessário;
não alterar `analise-backlog`, o túnel existente de outras integrações,
as baixas do Imperium nem o schema `public` do Supabase.
A migração adiciona estruturas sem apagar dados. Não execute DROP
automático em produção.

**Testes efetuados nesta intervenção:** túnel healthy, Worker /health 200,
rotas sem credencial 503, desconhecida 404; sidecar local autenticado 200;
migração Supabase aplicada; campos, permissões e ausência de dados confirmados.
**Não testado:** requisição autenticada Cloudflare→9342,
sincronização Supabase, carga anual, UI autenticada.
