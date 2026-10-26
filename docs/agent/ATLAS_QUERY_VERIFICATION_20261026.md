# QUERY Atlas — execução prática de 25/10 a 26/10/2026

Verificado até 26/10, 00:29, America/Sao_Paulo. **Meta das quatro cidades não
concluída: a geração atual de Natal não entregou anexo disponível.**
Este registro substitui o bloqueio inicial de autenticação e as restrições
históricas de novas QUERYs. Novas gerações continuam autorizadas pelo usuário,
com rastreamento e sem TOA, baixas, alterações de estoques, contratos ou O.S.

## Resultado atual

| Cidade | IDs novos de Atlas | Resultado validado | Linhas novas |
| --- | --- | --- | ---: |
| Fortaleza | principal 276907735; reserva 276907771 | reserva ready, fonte/banco/UI/CSV/XLSX/recarga aprovados | 29.529 |
| Recife | 276907778 | ready, fonte/banco/UI/CSV/XLSX/recarga aprovados | 55.749 |
| Mossoró | 276907784 | ready, fonte/banco/UI/CSV/XLSX/recarga aprovados | 892 |
| Natal, primeira família | principal 276907780; reserva 276907783 | dois anexos 404 em app-2 | 0 |
| Natal, recuperação explícita | principal 276907851; reserva 276907855 | anexos 404 em app-2 / app-1 | 0 |
| Natal, segunda recuperação explícita | principal 276907890; reserva 276907939 | anexos 404 em app-2 / app-1, inclusive navegação Chrome normal | 0 |

Fortaleza inicial foi registrada pela API privada existente enquanto o botão
da UI estava bloqueado por defeito confirmado. Recife, Mossoró, Natal e as
duas recuperações Natal foram acionadas pela interface real do DOMINIUM. O
worker criou as reservas automaticamente, uma por família. Foram dez IDs novos
confirmados; nenhuma submissão foi reenviada quando seu resultado era incerto.

Os relatórios anteriores continuam preservados. Natal histórico276868277,
20.179 linhas, não comprova geração atual e não foi contado como aprovação.

## Causa demonstrada e limite da conclusão

- A sessão Atlas inicialmente estava expirada, apesar da guia NetHome aberta.
  Após intervenção do usuário, foram confirmados controles das quatro cidades,
  leitura real NetTask e geração real com IDs. O login DOMINIUM foi feito pelo
  formulário seguro, separadamente do login Atlas do servidor.
- No Chrome autenticado, a nova Fortaleza 276907735 está COMPLETO no NetTask,
  mas XLS/HTML/ZIP anunciados em app-1 retornam 404. A reserva276907771 também
  está COMPLETO e entrega XLS/HTML/ZIP em app-3 com HTTP 200. Mesma cidade,
  localização EMPREITEIRA e gerador existente; não há evidência de erro de
  parser ou filtro da praça para explicar a ausência do primeiro arquivo.
- Natal 276907890 está COMPLETO, servidor atlasBatch02, com XLS/HTML/ZIP em
  app-2 retornando404. Natal 276907939 está COMPLETO, servidor atlasBatch01,
  com os três tipos em app-1 retornando404.
- Navegação normal do Chrome para cada XLS de Natal confirmou eventos
  Network.responseReceived404/text-html. A falha não depende apenas de
  Network.loadNetworkResource nem do método de download do DOMINIUM.
- Não foi substituído o servidor do link, inventada URL alternativa, ignorada
  validação TLS ou alterado o filtro para obter outro conjunto de dados.
- Conclusão limitada: os anexos anunciados para esses IDs não estão disponíveis
  na origem. A razão interna de armazenamento/publicação exige logs e acesso
  Atlas/BatAtlas que não estão disponíveis neste ambiente. A associação entre
  app-1/app-2 e404 é evidência, não prova isolada da causa interna.

## Correções implementadas e publicadas

1. `a8917e469a92d4bb8d949dd780d66971b2455ec0`: botão de criação deixava uma
   família concluída sem anexo bloqueada indefinidamente, mesmo após a janela
   de reutilização de oito horas do backend. Elegibilidade e guarda do handler
   alinhadas; envio incerto, timeout e filas recentes continuam protegidos.
2. `c94984bf68631408e6066fe22b00d640de1d231f`: a espera de oito horas ainda
   impedia recuperação prática após principal e reserva404. A mesma rota POST
   recebe retry_job_id para recuperação explícita da família mais recente.
   Exige dois IDs confirmados, duas falhas404 por membro e120s de idade.
   retry_of com índice UNIQUE torna replay, clique duplo, concorrência e
   reinício idempotentes. Preserva isolamento por operador/praça, proteção de
   outra QUERY em andamento e todos os IDs antigos. Timer nunca faz esse POST.

A revisão independente encontrou um bypass da proteção entre operadores na
primeira versão da recuperação vinculada. Um teste reproduziu202 indevido;
o código corrigido retorna409. Essa versão intermediária não foi implantada.

## Versões realmente implantadas

- Deploy web inicial: GitHub Actions 40262071063, a8917e4, success.
- Deploy web final: GitHub Actions 40262970942, c94984b, success.
- HTML publicado carrega `/atlas-query-ui.js?v=20261026-1`.
- JS servido e código fonte coincidem em SHA-256:
  `501bdfb4b49a4958bd894ef41b5918546b8453522e320a7f149a5cd9b64c7066`.
- Relay privado atualizado com backup e restart exclusivo do relay, sem
  reiniciar ou navegar as guias operacionais Chrome. Migração SQLite aditiva.
  `atlas_query_http.py` SHA-256
  `792813ca9b7ba2b5c11ceb0db1845a8ee1612555fa0db5455d7b601a526d9d21`;
  `atlas_query_pipeline.py`
  `7c2f2ba8bf0860c535542a5ebf27ac05b9d5894ab1aca16500c56966e5c752a8`.
- Verificação final: SQLite integrity_check=ok,18 trabalhos,163.049 linhas.
  GET autenticado QUERY jobs, confront/status e disconnection/reports:200.
  GET anônimo QUERY jobs:401 após implantação. Nenhuma baixa executada.

## Backups e integridade dos relatórios

Backup consistente anterior à migração:
`C:\DominiumRuntime\AtlasQueryData\backups\query_jobs.before-linked-recovery-20261026-001352.sqlite3`.
14 trabalhos e163.049 linhas preservados no restart. Arquivos anteriores
do relay em `DescRelay-20261010/backups/linked-recovery-20261026-001352`.
O script de implantação verifica hashes, compila antes da troca e prevê rollback.

Em cópia descartável de backup, com worker desativado, os três arquivos fonte
novos foram reinterpretados e comparados integralmente com query_rows. CSV e
XLSX do serviço real tiveram HTTP200 e conteúdos equivalentes.

Pelos botões da interface real foram baixados os seis arquivos CSV/XLSX das
três cidades aprovadas. XLSX ZIP íntegro,11 colunas, nenhuma fórmula e igualdade
célula por célula com CSV. Hash do CSV baixado igual ao CSV derivado diretamente
da fonte privada:

| Cidade | SHA-256 CSV fonte = download pelo navegador |
| --- | --- |
| Fortaleza | 0cc396ac0bbbb535b9ca0af4dbbb8e9880d28c20c13ad5bf8e071892433e4cd2 |
| Recife | 9e9294a0da31921a77d0e0a7765bd212ac778833a55f2734320e48d8cbd18445 |
| Mossoró | 5c4702a646c58dafd222b32ee7398de03701ff13fcd108590af5d26209bb1afa |

Após recarga do navegador, as três praças voltaram a mostrar os IDs novos,
100 linhas na primeira página,11 colunas e exportações habilitadas. Natal
retomou a família persistida após recarga sem criar outra fila. Na falha,
exportações permanecem indisponíveis e a recuperação explícita fica visível.

## Watchdog e validade da sessão

`BrowserHealth-20261022/browser_watchdog.py` é um monitor passivo: conta abas,
processos e páginas de login. Tarefa agendada com resultado 0 não comprova
autenticação NetHome/NetTask; a guia pode mostrar conteúdo antigo.

O keepalive é outra rotina, da extensão, configurada para 80s. Logs CDP
confirmaram sucessos de consulta aproximadamente a cada 80s após o novo login.
Há uma lacuna anterior de sucessos; estes dados não identificam por que a
sessão expirou. Não foi implementada renovação SSO automática nem se garante
que consultar um serial impeça expiração absoluta. A validade operacional foi
comprovada por leitura NetTask e geração real, não pela aparência da janela.

## Testes e continuidade

- RED/GREEN observado para defeito de botão, recuperação vinculada e guarda
  entre operadores.42 testes Python QUERY e33 JavaScript QUERY passaram.
- Quality gate completo:904 testes Python,21 ignorados, zero falhas; suites
  JavaScript, Ruff, build e auditoria do pacote aprovados com
  TZ=America/Sao_Paulo. Nenhuma mudança de código após essa verificação.
- Nenhuma tarefa ChatGPT contínua foi configurada ou verificada nesta execução.
  O worker do servidor é separado e mantém leitura/retry dos IDs existentes.
- Ação externa necessária: equipe Atlas/BatAtlas verificar geração/publicação
  dos documentos de Natal 276907890 e276907939 em atlasBatch02/app-2 e
  atlasBatch01/app-1; disponibilizar os arquivos ou indicar geração em nó
  operacional. Não temos acesso ao armazenamento ou logs internos do fornecedor.
- Depois de um anexo atual de Natal retornar200: interpretar, persistir,
  conferir fonte, tabela, CSV/XLSX e recarga. Só então marcar as quatro cidades
  como aprovadas. A UI publicada permite recuperação controlada sem operar
  manualmente o servidor; não criar novas filas em laço sem evidência nova.
