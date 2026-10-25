# DOMINIUM — handoff operacional verificado

> Revisado em 24/10/2026, 17:46, America/Sao_Paulo. Confirmar novamente o
> ambiente antes de agir. Não registrar credenciais, URLs privadas ou clientes.

## Prioridade atual: QUERY de Fortaleza

Meta do usuário: só concluir com fluxo da QUERY testado e funcional nas quatro cidades, com planilha e exportações válidas.
**Meta ainda pendente.** Não encerrar como corrigida por existir fila COMPLETO.

| Cidade | Fila existente | Estado | Linhas |
| --- | --- | --- | ---: |
| Fortaleza principal | 276868465 | attachment_wait / attachment_http_404 | — |
| Fortaleza reserva | 276868467 | attachment_wait / attachment_http_404 | — |
| Natal | 276868277 | ready | 20.179 |
| Recife | 276861849 | ready | 55.807 |
| Mossoró | 276855582 | ready | 893 |

- As duas filas de Fortaleza terminaram no NetTask, servidor atlasBatch01,
  às 16:58:19 e 16:59:44. XLS/HTML/ZIP anunciados em app-1 retornam 404.
  XLS com o mesmo caminho em app-2/app-3 também404. Navegação Chrome normal
  e leitura CDP confirmam os dois 404. Falta evidência interna do fornecedor
  para explicar a ausência dos arquivos; não inventar causa de armazenamento.
- Não gerar terceira fila, não reenviar geração, não alterar estoque/O.S. e
  não reiniciar Chrome autenticado. O retry existente consulta os mesmos IDs.
- Natal/Recife/Mossoró foram verificados na interface real, nos arquivos locais
  e nas linhas SQLite. Backend exporta CSV/XLSX equivalentes nas três cidades.
  Downloads Cloud Browser: CSV das três e XLSX de Recife verificados; captura
  dos XLSX de Natal/Mossoró não confirmada no diretório compartilhado.
- Memória detalhada: `docs/agent/ATLAS_QUERY_AUTOMATION.md`. Lá estão testes,
  evidências, horários, hashes de versão e backup. Não repetir geração.
- Meta Work com acompanhamento horário ativo para rever apenas os IDs existentes
  e validar a conclusão quando o anexo estiver disponível. Sem nova evidência,
  preservar o estado e evitar avisos repetidos.

## Ambiente e versão

- Sistema: https://dominium.clarotechnet.com.br; repo clarotechnet/dominium.
- Servidor DESKTOP-K7J3E1N, relay privado 8793,
  `C:\DominiumRuntime\DescRelay-20261010`.
- SQLite operacional: `C:\DominiumRuntime\AtlasQueryData\query_jobs.sqlite3`.
- Três módulos QUERY do servidor coincidem com main `fea43ba` em SHA-256.
- Frontend QUERY servido coincide com main; deploy web Actions 40090652088,
  commit 29197dd, success. fea43ba não altera caminhos de deploy Hostinger.
- Supabase: projeto DOMINIUM ACTIVE_HEALTHY na consulta da sessão. Relatórios
  QUERY ficam em SQLite no servidor; nenhuma alteração Supabase foi necessária.
- Backup SQLite consistente de 17:21:38 íntegro, preservado no servidor. Nenhum
  registro operacional alterado por esta investigação; nenhum deploy de runtime.
- 38 testes Python QUERY + 20 JavaScript passaram. Quality gate completo
  aprovado usando TZ=America/Sao_Paulo. Índices do agente regenerados.

## Contexto permanente

DOMINIUM integra TOA/Oracle Field Service, IMPERIUM/DataSnap, Atlas, estoque,
agenda e DESC/WhatsApp. Código no Git; dados privados e perfis fora do Git.
Consultar Seriais e Pendente atendem Natal/Parnamirim, Fortaleza, Mossoró e
Recife. Confronto em lote é somente leitura; histórico não comprova posse atual.
Não presumir que automações TOA/DESC funcionam apenas pela saúde da QUERY;
esses fluxos não foram retestados nesta sessão.

## Retomada segura

1. Ler este arquivo e ATLAS_QUERY_AUTOMATION.md; executar agent_memory.py brief/search.
2. Descobrir servidor conectado; ler estado dos dois IDs sem expor URLs/linhas.
3. Se continuar404, consultar os mesmos anexos no NetTask e manter o backoff.
4. Se disponível, backup antes de alterar runtime/banco, download válido, parser,
   persistência e exportações. Abrir Recursos → Pendente no Cloud Browser.
5. Corrigir código apenas com defeito reproduzido, teste regressivo e verificação.
6. Atualizar documentação com o que foi implementado, testado e publicado.

## Rechecagem de 24/10/2026, 17:32 (America/Sao_Paulo)

- Servidor online. Consulta autenticada e somente leitura ao NetTask confirmou
  novamente as filas 276868465 e 276868467 como complete, com XLS em app-1.
  Download CDP sem cache retornou HTTP 404 para ambas. Nenhum anexo recuperado.
- SQLite lido em modo somente leitura: ambas permanecem attachment_wait /
  attachment_http_404, sem linhas. O worker havia atualizado os registros
  aproximadamente às 17:30 e 17:31, respectivamente; retry segue ativo.
- Relatórios ready preservados: Natal 20.179, Recife 55.807 e Mossoró 893
  linhas, contadas diretamente em query_rows. O banco continua com 8 trabalhos.
- Implementado/publicado: somente este registro técnico; nenhum patch ou deploy
  operacional. Testado nesta rechecagem: leitura NetTask, download dos dois XLS
  e estados/contagens SQLite. Não foram repetidos testes automatizados nem UI.
- Sem geração, alteração operacional ou reinício do Chrome. Meta pendente;
  preservar acompanhamento enquanto o fornecedor não disponibiliza os anexos.

## Validação adicional de 24/10/2026, 17:43–17:46

- Critério de conclusão reforçado pelo usuário: as QUATRO cidades precisam estar
  testadas e funcionais. Acompanhamento existente atualizado e mantido ativo.
- Cloud Browser autenticado: Natal mostrou fila 276868277, 20.179 registros e
  primeira página. XLSX baixado pelo botão e efetivamente recebido: 1.228.297
  bytes, ZIP íntegro, 20.179 linhas de dados e nenhuma fórmula.
- Mossoró mostrou 893 registros. XLSX baixado pelo botão e recebido: 57.626 bytes,
  ZIP íntegro, 893 linhas e nenhuma fórmula. Isso resolve a pendência anterior
  de captura dos downloads XLSX de Natal/Mossoró no ambiente compartilhado.
- Serviço real de exportação executado em cópia descartável do backup (worker
  desativado): CSV e XLSX HTTP 200 nas três cidades ready, 11 colunas, conteúdos
  idênticos célula por célula; 893/55.807/20.179 linhas. Banco operacional intacto.
- NetTask/Chrome autenticado: os seis anexos anunciados XLS/HTML/ZIP das duas
  filas de Fortaleza continuam404; os dois XLS equivalentes em app-2/app-3
  também404. Não foi encontrado defeito de código novo.
- Cloud Browser, Fortaleza: principal 276868465 e reserva 276868467, mensagem
  "Fila concluída; aguardando a disponibilidade do anexo", CSV/XLSX desabilitados.
  Ainda sem relatório validado; não encerrar meta nem criar terceira fila.
- Implementado/publicado: somente documentação e critério de acompanhamento.
  Testado: downloads UI, integridade XLSX, exportações do serviço e consultas
  existentes. Nenhum patch de runtime, deploy operacional ou reinício do Chrome.

## Rechecagem de 24/10/2026, 18:36 (America/Sao_Paulo)

- Servidor online. Consulta NetTask autenticada, somente leitura, confirmou as
  filas existentes 276868465 e 276868467 como complete, com XLS anunciado em
  app-1. Download CDP sem cache retornou HTTP 404 para ambos novamente.
- SQLite aberto em modo somente leitura: ambos attachment_wait /
  attachment_http_404, 11 falhas de anexo por fila e nenhuma linha persistida.
  Atualizações recentes do worker e próxima consulta agendada confirmam backoff
  ativo. O banco continua com 8 trabalhos; não houve geração adicional.
- Ready e contagens preservados: Natal 20.179, Recife 55.807 e Mossoró 893.
  Não foram repetidos testes de parser, exportações e UI já aprovados, pois
  nenhum código foi alterado e não surgiu nova falha nessas cidades.
- Implementado/publicado nesta rechecagem: somente este registro técnico.
  Nenhum patch, deploy operacional, alteração de banco ou reinício do Chrome.
  Fortaleza permanece pendente de disponibilidade do anexo; manter acompanhamento.

## Rechecagem de 24/10/2026, 19:31 (America/Sao_Paulo)

- NetTask autenticado confirmou 276868465 e 276868467 como complete; os links
  XLS anunciados em app-1 não mudaram. Download CDP sem cache: HTTP 404 em ambos.
- SQLite somente leitura: attachment_wait / attachment_http_404, zero linhas
  nas duas filas. Principal com 15 tentativas e reserva com 14; timestamps e
  próxima consulta demonstram que o worker continua o retry com backoff.
- Banco preservado com 8 trabalhos. Natal ready/20.179, Recife ready/55.807,
  Mossoró ready/893. Nenhuma geração, alteração operacional ou reinício Chrome.
- Testado nesta rechecagem: NetTask, download existente, estados e contagens.
  Sem código novo ou falha nas cidades ready, testes já aprovados não repetidos.
- Implementado/publicado: somente documentação; nenhum patch/deploy operacional.
  Meta pendente, acompanhamento mantido; nenhum relatório de Fortaleza obtido.

## Rechecagem de 24/10/2026, 20:44 (America/Sao_Paulo)

- Servidor online. NetTask autenticado: 276868465 e 276868467 complete; links
  XLS em app-1 inalterados. Download CDP sem cache retornou HTTP 404 nos dois.
- SQLite somente leitura: ambas attachment_wait / attachment_http_404,
  19 falhas por fila, zero linhas. Atualizações e próximas consultas indicam
  retry ativo. Permanecem 8 trabalhos, sem nova geração.
- Natal ready/20.179, Recife ready/55.807 e Mossoró ready/893 preservados.
- Testado: consultas dos IDs existentes, tentativa dos dois XLS e contagens.
  Testes previamente aprovados não repetidos; nenhum código alterado.
- Implementado/publicado: somente documentação. Nenhum patch, deploy operacional,
  alteração de banco ou reinício Chrome. Meta pendente; manter acompanhamento.

## Rechecagem de 24/10/2026, 21:04 (America/Sao_Paulo)

- NetTask autenticado: 276868465 e 276868467 complete; links XLS em app-1
  inalterados. Nova tentativa CDP sem cache confirmou HTTP 404 em ambos.
- Worker operacional executou às 21:01:13 e 21:02:40, respectivamente:
  21 falhas de anexo por fila, attachment_wait / attachment_http_404,
  zero linhas. Próximas tentativas previstas às 21:16:09 e 21:17:36.
- Leitura SQLite confirmou 8 trabalhos e ready preservados: Natal 20.179,
  Recife 55.807 e Mossoró 893. Nenhuma geração ou alteração operacional.
- Testado: leitura NetTask, tentativa XLS e estados/contagens. Implementado e
  publicado: somente documentação. Sem patch/deploy ou reinício Chrome.
  Meta pendente; a execução está ativa, mas os anexos continuam indisponíveis.

## Rechecagem de 24/10/2026, 21:37 (America/Sao_Paulo)

- Servidor online. Diagnóstico autenticado somente leitura dos IDs existentes:
  276868465 e 276868467 continuam complete no NetTask. Anexos XLS anunciados
  em app-1; download CDP sem cache retornou HTTP 404 em ambos. Nenhum
  relatório recuperado.
- SQLite aberto explicitamente em mode=ro: ambas attachment_wait /
  attachment_http_404, 23 falhas por fila e zero linhas. Últimas atualizações
  do worker às 21:31:23 e 21:32:49. Permanecem 8 trabalhos.
- Ready preservados por contagem direta em query_rows: Natal 20.179,
  Recife 55.807 e Mossoró 893.
- Testado: consulta NetTask, download dos XLS existentes, estados e contagens.
  Implementado/publicado: somente este registro técnico; nenhum patch/deploy
  operacional. Não foram repetidos testes automatizados e UI sem mudança de
  código ou de disponibilidade. Nenhuma fila gerada, alteração operacional
  ou reinício Chrome. Meta pendente; manter acompanhamento sem aviso repetido.

## Rechecagem de 24/10/2026, 22:46 (America/Sao_Paulo)

- Servidor online. Consulta autenticada somente leitura ao NetTask confirmou
  276868465 e 276868467 como complete. Os XLS continuam anunciados em app-1;
  tentativa CDP sem cache retornou HTTP 404 em ambos. Nenhum arquivo recuperado.
- SQLite mode=ro: principal attachment_wait / attachment_http_404, 28 falhas;
  reserva no mesmo estado, 27 falhas; zero linhas nas duas. Timestamps e próxima
  consulta continuam avançando pelo worker. Permanecem 8 trabalhos.
- Contagens diretas preservadas: Natal ready/20.179, Recife ready/55.807,
  Mossoró ready/893. Nenhuma geração, alteração operacional ou reinício Chrome.
- Testado nesta rechecagem: NetTask, download dos dois XLS e estados/contagens.
  Testes automatizados, exportações e UI não repetidos sem alteração de código
  ou disponibilidade. Nenhum defeito novo demonstrado no DOMINIUM.
- Implementado/publicado: somente este registro técnico. Sem patch ou deploy
  operacional. Meta pendente, preservar acompanhamento dos IDs existentes;
  ausência de novidade não exige aviso repetido ao usuário.

## Rechecagem de 24/10/2026, 23:26 (America/Sao_Paulo)

- Servidor online. Consulta autenticada somente leitura ao NetTask: filas
  276868465 e 276868467 permanecem complete; XLS anunciados em app-1.
  Download CDP sem cache confirmou HTTP 404 nos dois. Nenhum anexo recuperado.
- SQLite mode=ro: ambas attachment_wait / attachment_http_404, 30 falhas
  por fila e zero linhas. Worker atualizou às 23:16:51 e 23:18:18; próximas
  consultas previstas às 23:31:47 e 23:33:14. Permanecem 8 trabalhos.
- Contagens diretas preservadas: Natal ready/20.179, Recife ready/55.807,
  Mossoró ready/893. Nenhuma fila criada, alteração operacional ou reinício Chrome.
- Testado: NetTask, download dos dois XLS e estados/contagens SQLite. Sem
  mudança de código ou disponibilidade, não repetidos parser, exportações e UI.
- Implementado/publicado: somente este registro técnico. Nenhum patch ou deploy
  operacional. Meta pendente, manter acompanhamento dos IDs existentes; sem
  novidade que exija aviso ao usuário.

## Rechecagem de 25/10/2026, 00:30–00:33 (America/Sao_Paulo)

- Servidor online. Leitura direta pelo Chrome autenticado, sem cache, dos
  mesmos XLS anunciados anteriormente: HTTP 404 nas filas 276868465 e
  276868467. Nenhum arquivo recuperado; não houve terceira geração.
- A reconsulta dos IDs no NetTask não pôde confirmar novamente o estado
  COMPLETO nesta execução: o iframe recebeu página "Weblogic Bridge Message",
  sem formulário FilasForm, sem campo de senha nem indicação de login.
  O conector registrou RuntimeError de formulário indisponível. Tratar como
  indisponibilidade a reexaminar; não presumir perda de autenticação nem
  confirmar a causa interna sem evidência adicional.
- SQLite mode=ro: ambas attachment_wait / attachment_http_404, 33 falhas
  por fila e zero linhas. Últimos updated_at observados:
  1792897325.7907596 / 1792897412.358884; next_attachment_check:
  1792898221.4787345 / 1792898308.6661613. Esses horários já haviam passado
  nesta verificação. O log contém avisos de poll indisponível; não afirmar
  que o retry está saudável apenas porque existe uma próxima data no banco.
- Banco preservado com 8 trabalhos; contagens diretas:
  Natal ready/20.179, Recife ready/55.807, Mossoró ready/893.
- Uma sondagem Python HTTPS adicional falhou na verificação da cadeia de
  certificados; não foi desabilitada a validação TLS. O HTTP 404 acima foi
  confirmado separadamente pelo Chrome/CDP, não por essa sondagem.
- Testado: downloads CDP dos dois XLS, disponibilidade do formulário NetTask
  e estados/contagens SQLite. Sem alteração de código, não foram repetidos
  parser, exportações, testes automatizados e UI. Não houve patch/deploy,
  alteração operacional de banco ou reinício do Chrome.
- Implementado/publicado: somente este registro técnico. Meta pendente;
  reexaminar disponibilidade do NetTask e anexos existentes. Preservar
  acompanhamento, sem aviso repetido de 404 nem nova geração.

## Rechecagem de 25/10/2026, 01:52–01:53 (America/Sao_Paulo)

- Servidor online. Os dois XLS existentes de Fortaleza (276868465 e
  276868467) foram consultados diretamente pelo Chrome/CDP autenticado, sem
  cache: ambos retornaram HTTP 404. Nenhum arquivo recuperado.
- Reconsulta somente leitura pelo conector NetTask falhou nos dois IDs:
  RuntimeError de formulário indisponível. Não foi possível reconfirmar
  COMPLETO nesta execução; não atribuir a falha à autenticação sem evidência.
  A indisponibilidade já observada na execução anterior continua pendente.
- SQLite mode=ro: ambas attachment_wait / attachment_http_404, 33 falhas por
  fila e zero linhas. updated_at e next_attachment_check não avançaram em
  relação à verificação de 00:30; não afirmar que o retry está saudável.
- Permanecem 8 trabalhos. Contagens diretas preservadas:
  Natal ready/20.179, Recife ready/55.807, Mossoró ready/893.
- Testado: tentativa dos dois XLS, acesso ao formulário NetTask e
  estados/contagens SQLite. Nenhum patch/deploy operacional, alteração do
  banco, nova geração ou reinício do Chrome. Sem mudança de código ou
  disponibilidade, não repetidos parser, exportações e UI já aprovados.
- Implementado/publicado: somente este registro técnico no GitHub.
  Meta pendente; manter acompanhamento dos mesmos IDs, reexaminar NetTask
  quando a origem voltar e evitar avisos repetidos sem novidade.
