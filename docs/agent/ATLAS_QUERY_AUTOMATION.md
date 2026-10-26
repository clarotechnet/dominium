# QUERY Atlas — relatório analítico por localização

## Estado vigente — 26/10/2026, 00:29

Ver [validação atual](ATLAS_QUERY_VERIFICATION_20261026.md). Fortaleza, Recife
e Mossoró tiveram relatórios novos com fonte/banco/UI/exportações/recarga
aprovados. Natal teve seis IDs novos;276907890 e276907939 COMPLETO, porém os
anexos XLS/HTML/ZIP retornam 404 inclusive no Chrome autenticado. Meta quatro
cidades não concluída. Correções de recuperação publicadas em c94984b, relay
e web verificados. A ação externa necessária é disponibilizar o anexo atual
Natal na origem Atlas/BatAtlas. Novas QUERYs necessárias seguem autorizadas.
Seções abaixo são checkpoints históricos.

## Checkpoint vigente — 25/10/2026, 23:38

Ver [execução atual](ATLAS_QUERY_EXECUTION_20261025.md). O usuário autoriza novas
QUERYs para investigar e validar as quatro cidades; a proibição histórica de
terceira fila de Fortaleza está substituída. O bloqueio atual é login Atlas no
Chrome gerenciado do servidor: formulário de geração retorna AtlasAuthRequired,
NetTask não disponibiliza FilasForm e os dois links antigos ainda retornam 404.
DOMINIUM autenticado, IDs e aviso de sessão persistem após recarga. Nenhuma nova
fila, patch de runtime ou deploy operacional nesta execução. Meta não concluída.
Os registros abaixo são históricos e não substituem essa autorização atual.

## Estado verificado em 24/10/2026 — Cloud Browser e servidor

Verificação prática entre 17:14 e 17:26 (America/Sao_Paulo), sem gerar filas.
Os registros abaixo prevalecem sobre os checkpoints históricos deste documento.

| Cidade | Fila | Estado comprovado | Registros |
| --- | --- | --- | ---: |
| Natal | 276868277 | ready, tabela e exportação | 20.179 |
| Recife | 276861849 | ready, tabela e exportação | 55.807 |
| Mossoró | 276855582 | ready, tabela e exportação | 893 |
| Fortaleza, principal | 276868465 | COMPLETO no NetTask; anexo HTTP 404 | — |
| Fortaleza, reserva | 276868467 | COMPLETO no NetTask; anexo HTTP 404 | — |

### Bloqueio de Fortaleza reproduzido

- DOMINIUM autenticado → Recursos → Pendente → Fortaleza → Consultar fila:
  mostra os dois IDs, horários e `attachment_wait`; CSV/XLSX desabilitados.
- Consulta direta dos dois IDs no NetTask autenticado: tarefa de geração de
  relatório, status COMPLETO, servidor `atlasBatch01`. A principal terminou
  às **16:58:19** e a reserva às **16:59:44** de 24/10/2026.
- Cada fila lista XLS, HTML e ZIP no BatAtlas `app-1`. Os seis links efetivamente
  listados retornaram **HTTP 404** usando o Chrome autenticado, sem cache.
- Para os dois XLS, o mesmo caminho de arquivo em `app-2` e `app-3` também
  retornou 404. São sondagens controladas, não links anunciados pelo NetTask;
  nenhuma URL alternativa foi gravada no banco.
- Navegação normal do Chromium para cada XLS, em iframe temporário, confirmou
  `Network.responseReceived` com **404 / text/html** para os dois IDs. Portanto,
  o resultado não decorre apenas de `Network.loadNetworkResource` nem de um
  timeout de streaming do CDP. Nenhuma aba operacional foi navegada ou fechada.
- Não havia cópia local correspondente aos dois anexos nos diretórios
  operacionais de anexos/downloads e Downloads do usuário do servidor.
- Limite da conclusão: os arquivos anunciados pelo NetTask não estavam
  disponíveis pelo BatAtlas. Não temos logs internos do fornecedor para afirmar
  por que o armazenamento/publicador `app-1` não entregou os arquivos.
  Não há defeito de parser ou proxy demonstrado para esses dois 404.
- O worker existente mantém as duas filas e continua repetindo apenas a leitura
  e o download, com backoff máximo de 15 minutos. **Não criar terceira fila.**

### Verificações concluídas

- Os três módulos operacionais `atlas_query_report.py`, `atlas_query_pipeline.py`
  e `atlas_query_http.py` coincidem em SHA-256 com `main` no commit `fea43ba`.
- O frontend em produção respondeu HTTP 200 e coincide com `static/atlas-query-ui.js`
  de `main`: SHA-256 `1fbef678842616abcf8a1f5c597eb85f7447e5a6400b03e9fce10f8df168d68c`.
  Último deploy web consultado: Actions `40090652088`, commit `29197dd`, success.
  O commit posterior `fea43ba` altera a integração privada e não dispara deploy
  Hostinger pelo filtro de caminhos. Não confundir versões web e relay.
- Natal, Recife e Mossoró: tabela real com 100 linhas na primeira página,
  contagens totais corretas e controles CSV/XLSX habilitados no Cloud Browser.
- Arquivos originais privados foram reinterpretados: 20.179 / 55.807 / 893 linhas,
  iguais às contagens persistidas. Todos os três anexos válidos ficam em `app-3`.
- Exportações do serviço real verificadas numa cópia descartável do backup:
  HTTP 200 para CSV e XLSX nas três cidades, 11 colunas, conteúdos equivalentes,
  ZIP XLSX íntegro e ausência de fórmulas. Nenhum dado de cliente foi impresso.
- Downloads pelo Cloud Browser: três CSV recebidos e contados; XLSX de Recife
  recebido, ZIP verificado e comparado célula por célula com o CSV (55.807 linhas).
  Os eventos de download dos XLSX de Natal e Mossoró devolveram caminhos, mas os
  arquivos não ficaram disponíveis no diretório compartilhado. Essa captura do
  Cloud Browser permanece não confirmada; não atribuir causa ao DOMINIUM sem
  evidência. Os bytes de exportação do backend foram verificados nas três cidades.
- Testes focados: **38 Python e 20 JavaScript passaram**. Quality gate completo
  aprovado com `TZ=America/Sao_Paulo` e dependências de teste instaladas no
  ambiente isolado. Sem TZ, o teste preexistente do monitor operacional depende
  do fuso local e falha; nenhuma correção desse subsistema foi incluída.
- Backup consistente do SQLite preservado no servidor:
  `AtlasQueryData/backups/query_jobs.before-work-verification-20261024-172138.sqlite3`,
  38.989.824 bytes, `PRAGMA integrity_check=ok`, 8 trabalhos.
  SHA-256 `f72d7942f515dc3ebfb859b7605ac873a5f45e9cbfab581eb5276c717265bc04`.

### Implementado / testado / publicado / pendente

- **Implementado nesta sessão:** somente memória técnica e índices atualizados;
  sondagens privadas de diagnóstico, backup e validações. Nenhum patch de runtime.
- **Testado:** integração existente, interface real, anexos dos dois IDs e
  relatórios das três cidades acima. Nenhuma submissão, baixa ou transferência.
- **Publicado:** documentação desta investigação no GitHub; não houve novo deploy
  de código operacional nesta sessão por não existir defeito demonstrado a corrigir.
- **Pendente:** BatAtlas disponibilizar pelo menos um dos anexos de Fortaleza;
  então confirmar assinatura, parser, linhas persistidas, ready, tabela e CSV/XLSX.
  O acesso ao armazenamento interno do Atlas não está disponível a este agente.
- A meta do Work possui acompanhamento horário para reexaminar os IDs existentes,
  agir diante de nova evidência e avisar quando o relatório estiver validado ou
  surgir intervenção indispensável. O retry de download do servidor segue
  independente desse acompanhamento. A meta **não está concluída**.

## Checkpoints históricos

Estado inicial em 2026-10-23: código integrado em staging; validar publicação
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

## Solicitações sem ID após queda do worker (23/10/2026)

O histórico mostrou QUERY Natal (479289b9) no estado
`submission_uncertain` por dezenas de minutos, sem `remote_queue_id`.
A fila em memória do relay não sobrevive a reinícios e **NUNCA deve
ser reenviada** sem verificar primeiro o Atlas. A reconciliação agora
marca `atlas_submit_unconfirmed` após 150s, preservando o estado e
o identificador, para que o DOMINIUM mostre erro sem duplicar envio.
Não marcar como sucesso/falha definitiva do Atlas por falta de confirmação.

## Investigação de janelas NetScaler e reparo de QUERY travada — 23/10/2026

- O navegador Chrome for Testing gerenciado está ativo, com a extensão e NetHome em uma única guia. Não reiniciar esse perfil sem planejar o impacto no bot.
- O monitor `C:\DominiumRuntime\BrowserHealth-20261022\browser_watchdog.py` é **passivo**: observa a cada cinco minutos, não cria janelas. Seu log comprovou aumento de janelas NetScaler até oito e redução subsequente até quatro.
- A origem identificada do Chrome Atlas separado é `/home/technet/BotDMV/src/atlas_rastreio.py`, que usava `--new-window` quando a porta de depuração falhava. Proteção aplicada no WSL, com backup `atlas_rastreio.before-popup-guard-20261023.py`; quando o perfil já está aberto, não criar novo Chrome. Diagnóstico após patch: debugger do Chrome AtlasBot antigo indisponível, perfil já aberto, portanto abertura extra evitada. Código compila em Python.
- A extensão TOA gerenciada foi **configurada em disco** para keepalive de 80 segundos e serial de teste definido pelo operador. Arquivo original preservado em `content-atlas-main.before-keepalive-80s-20261023.js`. **A configuração ainda não está ativa até recarregar a extensão**. Não recarregar enquanto há uma consulta em andamento, e não garantir que consultar o serial evitará timeout de sessão.
- A QUERY Natal, identificador interno prefixo `479289b9`, estava `submission_uncertain` sem ID remoto por mais de uma hora. O serviço de QUERY passou a registrar `atlas_submit_unconfirmed` após 150s; o estado continua incerto para impedir envio duplicado. O relay na porta 8793 foi atualizado com backup e reinício protegido; os endpoints `/api/atlas-query/jobs`, `/api/confront/status` e `/api/disconnection/reports` responderam HTTP 200. O erro foi confirmado persistido no banco.
- Faltam a reconciliação humana pela fila do Atlas, confirmar disponibilização do anexo histórico de Mossoró e uma recarga segura da extensão quando o bot estiver ocioso.


## Recuperação de anexos após 404 recorrente — 23/10/2026

- Correção `995d47a`: quando um download falhou pelo menos três vezes, o
  worker reconsulta a **mesma fila remota**, exclusivamente em modo leitura,
  antes da próxima tentativa. Se o NetTask disponibilizar um **novo** link,
  o serviço aceita-o somente após `valid_report_url()` e reinicia a
  contagem do anexo. Caso contrário preserva o link, o ID e o backoff.
- A rotina **nunca** submete nova geração de relatório nem modifica
  equipamentos, contratos, técnicos ou O.S. após HTTP 404.
- Verificação: 21 testes Python (pipeline, HTTP, parser) e 12 testes
  JavaScript passaram. Arquivo publicado no relay privado após backup e
  reinício com smoke de autenticação (GET anônimo retorna 401).
- Diagnóstico autenticado real de uma fila de Mossoró: NetTask retornou
  `complete`; dois links `.xls` distintos e links `.html` e `.zip`
  foram identificados no painel de anexos. Todas as variantes testadas
  retornaram HTTP 404 pela API CDP `Network.loadNetworkResource`.
  Mesmo resultado com o `frameId` raiz e o frame do NetTask.
- Também foi testada navegação HTTP normal pelo próprio Chromium,
  iniciada por iframe temporário e oculto dentro do NetTask autenticado,
  sem criar outra aba nem registrar cookies. Tanto um anexo HTML quanto
  o relatório XLS retornaram HTTP 404 em eventos `Network.responseReceived`.
  Isso indica que o problema não se limita a `Network.loadNetworkResource`.
  Um clique humano fora do iframe ainda não foi validado; não declarar
  falha definitiva do armazenamento sem verificação do fornecedor.
  Não expor links, tokens, cookies ou conteúdo dos relatórios.
- **Pendente:** confirmar retorno HTTP 200 de um anexo real, magic bytes do
  formato, parsing, persistência das linhas e exportação XLSX. Até isso
  acontecer, o estado correto continua `attachment_wait`, não `ready`.


## Teste controlado com duas filas e validação do BatAtlas app-3 — 23/10/2026

- Contexto autorizado: praça Mossoró, localização EMPREITEIRA. Fila original
  `276850938` concluída no NetTask, mas download do XLS em `app-2`
  retornava HTTP 404.
- A sessão Chrome gerenciada confirmou por dry-run os parâmetros e o gerador.
  Uma única geração adicional foi registrada em banco SQLite privado e
  recebeu o novo ID confirmado `276855582`. Não houve reenvio da fila
  original nem terceira geração.
- Inicialmente a fila `276855582` apareceu em `attachment_missing`:
  a integração reconhecia apenas caminhos `/app-1/` e `/app-2/`,
  enquanto o relatório real estava em `/app-3//RELATORIOS/...`.
  Inspeção sanitizada da estrutura (sem divulgar URL, tokens ou clientes)
  confirmou o endpoint. O download do `.xls` em app-3 retornou HTTP 200.
- Patch `e85e65d`: aceitar exclusivamente `app-1`, `app-2` e
  `app-3` sob a allowlist existente de URL HTTPS do BatAtlas; não
  liberar servidores arbitrários. 21 testes Python + 12 Node passaram.
  Relay privado atualizado com backup, compilação e smoke HTTP 401.
- Com URL app-3 aceita, o arquivo XLS foi baixado e interpretado:
  **893 registros**, estado `ready` em SQLite de laboratório.
  Após backup consistente do banco de produção, o trabalho confirmado
  (com seu ID de Atlas `276855582`) e as 893 linhas foram migrados
  atomicamente para `C:\DominiumRuntime\AtlasQueryData\query_jobs.sqlite3`,
  vinculados ao mesmo operador da fila original, sem apagar a fila 404.
- Smoke do serviço `AtlasQueryService`: lista do operador HTTP 200
  com fila `276855582` como mais recente e `ready`, detalhe HTTP 200
  com `total_rows=893`, primeira página HTTP 200 com 100 linhas e 11
  colunas, exportação `export.xlsx` HTTP 200 (57.626 bytes, ZIP válido).
  Dados de clientes e URL real do anexo não foram impressos em logs.
- **Importante:** o fallback com segundo ID foi executado de forma
  controlada para este teste. O fluxo genérico do botão QUERY **ainda
  não gera automaticamente uma segunda fila** depois do 404; esse
  comportamento exigiria uma máquina de estados/idempotência própria
  e controle de carga. A recuperação por reconsulta do MESMO ID após
  404, implementada anteriormente, permanece distinta.


## Fluxo principal + reserva automático, quatro cidades — 23/10/2026

- Nas **novas** QUERYs geradas pelo botão DOMINIUM (Natal, Mossoró,
  Fortaleza e Recife), o serviço habilita `fallback_enabled=1` em
  SQLite; as antigas são migradas com `fallback_enabled=0`.
- Após confirmação do ID principal **e da primeira tentativa de anexo
  que retornar HTTP 404**, o serviço cria uma única solicitação reserva
  da **mesma praça e localização**, no mesmo operador, com
  `fallback_of=<id_da_solicitacao_principal>`.
- O registro da reserva é durável com `state=submission_uncertain`
  **antes de invocar o formulário Atlas**. A restrição UNIQUE em
  `fallback_of` impede mais de uma reserva para a mesma principal,
  mesmo após reinício ou entre dois workers.
- Se o Atlas não confirmar o ID da reserva, a geração **não é
  repetida automaticamente**; após 150 segundos o erro é registrado,
  como na geração principal. Nenhuma reserva nasce de envio incerto,
  de uma fila sem ID, de uma principal pronta ou de uma reserva.
- Principal e reserva mantêm IDs, horários, estados, anexos e resultados
  independentes. Na interface, a mais recente família de fila da cidade
  apresenta os dois IDs. Um resultado `ready` tem preferência sobre
  outro processamento pendente e continua exportável.
- Ao lado do botão **Consultar fila**, ficam as datas de solicitação
  de ambas as filas (quando há reserva), a última atualização da
  tentativa ativa e a hora da última consulta, em
  `America/Fortaleza`, usando data/hora `pt-BR`.
- Tests: 27 Python, 14 JavaScript. Simulação migrando snapshot do
  banco operacional confirmou relatório histórico `ready` com 893
  registros, sem habilitar reservas retroativamente.
- Limite: uma reserva **não garante** arquivo disponível em caso de
  indisponibilidade geral do Atlas. Evitar terceira geração automática.
  Nenhuma atualização de estoque, contratos ou O.S. é realizada.


## Natal: tentativa antiga sem confirmação de fila (23/10/2026)

- Registro local `479289b9d2354c5f8e93991c1d664067`, Natal /
  EMPREITEIRA, criado em **23/10/2026 às 13:51:49 (UTC−3)**.
  Estado `submission_uncertain`, `remote_queue_id=NULL`,
  `error_code=atlas_submit_unconfirmed`. Na consulta por volta das
  20:04, o código reaproveitava essa mesma solicitação pela janela de
  idempotência de oito horas: não ocorreu nova criação de fila.
- A consulta autenticada por intervalo no NetTask encontrou outras
  filas próximas desse horário, mas **não identificou inequivocamente**
  uma fila correspondente à tentativa antiga. É incorreto declarar
  que o Atlas não recebeu a requisição, assim como inventar um ID.
- Recuperação manual: um administrador/controlador deve conferir
  independentemente no Atlas que não existe a fila dessa solicitação.
  Somente então o controle `Reconciliar envio` confirma com
  `POST /api/atlas-query/jobs` e corpo JSON contendo
  `reconcile_job_id` e `atlas_checked_no_queue:true`. Reutiliza a
  rota existente pelas políticas Hostinger/Cloudflare, sem abrir rotas.
- O relay verifica operador, job exato, ausência de ID,
  `submission_uncertain`, erro `atlas_submit_unconfirmed`,
  pelo menos cinco minutos de idade e ausência de vínculo reserva.
  Apenas marca o registro local como `failed` /
  `manually_closed_unconfirmed`; **não transmite nada ao Atlas**.
  A geração seguinte exige outro clique do operador, criando um novo
  registro preservando integralmente o histórico original.
- A confirmação manual é uma declaração do operador, não evidência
  automática de que o Atlas não criou fila. Sem conferência, deixar
  o registro pendente para evitar duplicação.
