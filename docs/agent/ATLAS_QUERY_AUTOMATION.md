# QUERY Atlas — relatório analítico por localização

Estado em 2026-10-23: código integrado em staging; validar publicação
e acesso ao anexo antes de declarar a etapa totalmente operacional.

## Fluxo confirmado contra Atlas autenticado

1. Recurso DOMINIUM → Pendente → "Gerar QUERY automaticamente no Atlas".
2. Seleção da praça: Natal (ID 179), Mossoró (592), Fortaleza (198),
   Recife (57). Localização "EMPREITEIRA" (ID 5).
3. Chrome for Testing isolado em
   `C:\DominiumRuntime\ManagedAtlasTOA-20261022`, guia temporária
   `relatorioEquipamentos.do?acao=prepareSearch` com parâmetros
   correspondentes à sessão Atlas. `gerarRelatorio()` chama
   `NetHomeEquipamentoService.relatorioEquipamentosAnaliticoExportacaoTaskV2`.
4. O ID do relatório é salvo em banco privado
   `C:\DominiumRuntime\AtlasQueryData\query_jobs.sqlite3`.
   Nenhuma requisição de geração é reenviada automaticamente se o envio
   ficou incerto (proteção contra filas duplicadas).
5. Consulta ao NET TASK por ID retorna status RELATORIO_EQUIPAMENTOS;
   detalhes → Anexos da Fila → Relatório de Equipamentos Analítico.
6. Espera mínima de 30 segundos após detecção de conclusão; caso o
   armazenamento batatlas responda 404, tenta novamente o MESMO anexo
   com atraso progressivo (30, 60, 120 segundos, máximo 15 minutos).
7. Arquivo obtido passa por parser HTML .xls, OLE .xls (`xlrd`) ou ZIP
   .xlsx. Informação sensível fica somente no servidor privado.
8. Tabela web com colunas reduzidas e coluna calculada "Código SAP sem zeros",
   paginação de 100 linhas, exportação CSV UTF-8 BOM ou XLSX com células texto
   (preserva zeros iniciais e bloqueia fórmulas na exportação).

## Evidência real

Uma solicitação de teste em Mossoró/Empreiteira foi confirmada pelo Atlas:
ID da fila confirmado, status `RELATORIO_EQUIPAMENTOS COMPLETO`.
A página dos anexos apontou para um relatório analítico, mas o servidor
de arquivos respondeu **HTTP 404**, inclusive via sessão Chrome. Isso
é erro de disponibilidade do anexo, não falha da geração. O sistema
não finge que há planilha se o download não terminou.

## Arquitetura

- `integrations/serial_consult/atlas_query_report.py`: formulário Atlas,
  Chrome CDP isolado, registro durável da geração.
- `integrations/serial_consult/atlas_query_pipeline.py`: consulta NetTask,
  recuperação do anexo e retry 404.
- `integrations/serial_consult/atlas_query_data.py`: parser, normalização,
  persistência das linhas, CSV/XLSX.
- `integrations/serial_consult/atlas_query_http.py`: serviço interno
  autorizado, leitor e scheduler sem submissão duplicada.
- `static/atlas-query-ui.js`: interface, progresso e grid.
- `deploy/hostinger-web/atlas-query-policy.js`: allowlist restrita.
- `integrations/import_bridge/worker.mjs`: VPC privado.
- `integrations/serial_consult/desc_review_relay.py`: relay local 8793.

**Jamais publicar** dados, contratos, planilhas, URLs de anexo ou
cookies do Atlas no repositório. Não executar baixa, transferência nem
movimentação de equipamentos.

## Limite explícito

O processo completo é `ready` apenas quando a fonte efetivamente
retornou o anexo e o parser leu os registros. A simples existência de
uma fila COMPLETO não garante documento disponível. Alguns anexos
podem permanecer inacessíveis no Atlas; sinalizar o incidente.


## Hostinger packaging incident and preventive fix (2026-10-23)

The initial automatic QUERY release `89e69df` caused HTTP 503 because
`scripts/build_hostinger_node_release.py` used an explicit `RUNTIME_FILES`
allowlist and omitted `atlas-query-policy.js` even though
`operational-relay.js` required it at Node startup. The website was restored
by reverting the release in `ece0930`. The corrective release adds the
policy to the packaging allowlist, checks the runtime dependency closure
and boots the packaged relay module in CI. Deployment also verifies the
private QUERY list route with a read-only request before upload.

This file documents the failure so future agents should **never** equate
a successful Hostinger build with a successful Node runtime startup.
Always test the *packaged* runtime and verify authenticated deployment
smokes. Avoid touching managed Atlas/WhatsApp production tabs.


## Release verificado em produção (2026-10-23)

- Publicação corrigida `0a8d121` em `main`.
- GitHub Actions run `39971103661`: **success**, incluindo a
  validação read-only da rota privada da QUERY, build Hostinger,
  startup do pacote Node e smoke tests do site.
- `https://dominium.clarotechnet.com.br/`: HTTP 200 e controles
  `atlasQueryStart` presentes no HTML publicado.
- `/atlas-query-ui.js`: HTTP 200, arquivo novo disponível.
- `/api/atlas-query/jobs` sem login: HTTP 401 esperado.
- O arquivo real gerado anteriormente permaneceu em estado
  `attachment_wait`/`retry_scheduled`; **não há ainda confirmação
  de download nem de planilha real pronta**. Não confundir relatório
  `COMPLETO` com anexo disponível.
- Relay DESC antigo preservado: GET `/api/confront/status` e
  GET `/api/disconnection/reports` retornaram HTTP 200 após
  restart seguro. O bot Atlas foi preservado.
- Checkouts no servidor: staging
  `C:\DominiumRuntime\SerialMultiCityPatch-20261022`, checkout
  separado de publicação `C:\DominiumRuntime\AtlasQueryShip-20261023`.

## Sessão Atlas reutilizada e mensagens persistentes (2026-10-23)

Observação de suporte: no servidor, o watchdog conservava a aba NetHome
aberta, mas a automação anterior criava uma nova guia do Chrome.
O SSO do Claro/NetScaler podia apresentar uma nova janela de login/CAPTCHA.
Agora o conector usa um **iframe oculto e temporário dentro da aba
Atlas gerenciada já autenticada**, sem fechar ou navegar essa aba.
A inspeção read-only confirmou tanto o formulário de equipamentos quanto
a página de filas NetTask nesse modelo, incluindo Mossoró e EMPREITEIRA.
Geração real pelo novo modelo não foi realizada neste registro.

O frontend tinha outro bug: uma atualização periódica apagava o aviso de
resultado do clique depois de uma fração de segundo. Corrigimos a limpeza
indevida e incluímos histórico de ações da sessão com hora, estado e erro.
Se o Atlas solicitar login, o trabalho recebe estado explicativo
`atlas_auth_required`, sem submissão de relatório.

Antes dessa correção, o banco privado de trabalhos tinha somente uma
QUERY de validação da praça Mossoró (sem operador associado) e nenhuma
QUERY nova atribuída a operador. Não confundir clique do usuário com
geração confirmada no Atlas. A observação foi feita sem ler dados de cliente.

## HTTP 415 do botão QUERY e HUD operacional (2026-10-23)

Uma solicitação legítima pela interface de Natal retornou o erro
`Envie JSON` antes de chegar ao relay; nenhuma fila foi criada.
Causa no `deploy/hostinger-web/server.js`: ao remover cabeçalhos do
navegador antes de encaminhar para o Worker privado, removia também
`Content-Type`. O Worker de `integrations/import_bridge/worker.mjs`
recusa POST sem `application/json` (HTTP 415).
Correção: `restorePrivateJsonContentType` em `operational-relay.js`
adiciona estritamente o tipo JSON de volta, apenas para POST de
`/api/atlas-query/jobs` e `/api/confront/jobs`, sem encaminhar
cookie nem CSRF do navegador. Teste Node no pacote:
`tests/test_atlas_query_proxy_json.js`.

A interface da QUERY passa a usar o HUD **DOMINIUM EM AÇÃO** existente
em `static/motion-ui.js`: estados de envio, fila, anexo, conversão,
sucesso e erro; o HTTP 202 nunca é tratado como planilha pronta.
O histórico de mensagens não desaparece na atualização automática.
Se a resposta do Atlas ficar incerta, o backend persiste
`error_code=atlas_submit_unconfirmed` sem gerar solicitação duplicada.
Essa alteração é somente da fila QUERY; nenhuma movimentação de estoque.
