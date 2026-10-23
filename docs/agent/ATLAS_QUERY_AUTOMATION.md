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
