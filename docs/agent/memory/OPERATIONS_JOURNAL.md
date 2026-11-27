# DOMINIUM — diário de decisões e entregas dos agentes

Cada agente deve registrar **o que mudou, por quê, testes verificados,
status de publicação e próxima pendência**. Use:
`python scripts/agent_memory.py record --title "..." --why "..." --changed "..." --tests "..." --next "..."`.

Não incluir credenciais, dados pessoais de técnicos ou clientes, seriais
reais, contratos, tokens de autenticação ou informações de sessão.


## 2026-10-23 04:41 UTC — Memoria portatil DOMINIUM

**Motivo:** Continuar trabalho entre agentes sem depender da memoria interna

**Alterado:** Indices FTS5 API MCP skills adaptadores Git hooks e handoff ZIP

**Verificação:** Sete testes de memoria aprovados e smoke FTS5 executado

**Próximo passo/pendência:** Quality gate integrado commit push e validacao de CI

## 2026-10-23 13:58 UTC — QUERY_Atlas_Automatica

**Motivo:** Reproduzir_fluxo_do_video

**Alterado:** Fila_Atlas_autenticada_retry_404_tabela_CSV_XLSX

**Verificação:** Quality_gate_ok_relay_antigo_preservado

**Próximo passo/pendência:** Validar_publicacao_e_anexo_404

## 2026-10-23 14:29 UTC — Hostinger_runtime_dependency_guard

**Motivo:** Restaurar_QUERY_Atlas_com_deploy_seguro

**Alterado:** atlas-query-policy_js_incluido_no_pacote_e_testes_de_dependencias

**Verificação:** hostinger_packaged_node_require_OK_quality_gate_OK

**Próximo passo/pendência:** Validar_github_actions_e_site_publico

## 2026-10-24 20:27 UTC — Fortaleza_QUERY_404_verificado_Cloud_Browser_20261024

**Motivo:** Reproduzir a falta da planilha e recuperar os dois IDs existentes sem duplicar filas

**Alterado:** Diagnostico somente leitura: NetTask COMPLETO em atlasBatch01, ambos XLS e demais anexos em app-1 com HTTP404; navegação Chrome normal confirma; outros tres relatorios validos. Memoria e indices atualizados, sem patch/deploy operacional.

**Verificação:** 38 Python QUERY e 20 JavaScript passaram; quality_gate completo com TZ America/Sao_Paulo aprovado; tres fontes reparseadas, backend CSV/XLSX equivalente; CSV tres cidades e XLSX Recife baixados/verificados; backup SQLite integro.

**Próximo passo/pendência:** Preservar filas 276868465 e 276868467; continuar leitura/download pelo retry existente e acompanhamento horario Work; nao gerar terceira fila; concluir somente apos anexo, parser, ready, tabela e exportacao Fortaleza verificados.

## 2026-10-26 02:40 UTC — QUERY Atlas: sessao atual bloqueia geracao nas quatro cidades

**Motivo:** Executar nova validacao autorizada sem repetir a restricao historica de Fortaleza

**Alterado:** Diagnostico atual de servidor e producao; autorizacao de novas QUERYs registrada; sessao Atlas exige login; dois XLS existentes ainda404; nenhum patch operacional

**Verificação:** 38 Python e 20 JavaScript passaram; Fortaleza persiste apos recarga; fontes e banco iguais em tres cidades; CSV/XLSX equivalentes e integros; backup SQLite ok

**Próximo passo/pendência:** Operador renovar login Atlas no Chrome gerenciado do servidor; depois nova geracao Fortaleza e validacao atual nas quatro cidades

## 2026-10-26 03:31 UTC — QUERY Atlas: tres cidades novas validadas; Natal bloqueada na origem; recuperacao publicada

**Motivo:** Retomar apos login renovado e validar geracao atual sem reutilizar relatorio antigo

**Alterado:** a8917e4 e c94984b publicados: botao apos janela de reutilizacao e recuperacao vinculada idempotente; relay migrado com backup sem reiniciar Chrome; dez IDs novos rastreados

**Verificação:** 42 Python QUERY e33 JS; quality gate904 Python21skip aprovado; fonte banco e CSV/XLSX de Fortaleza29529 Recife55749 Mossoro892 identicos; UI recarga e seis downloads integros; smokes200; SQLite18jobs163049rows ok

**Próximo passo/pendência:** Atlas/BatAtlas disponibilizar anexos Natal276907890 e276907939, completos no NetTask mas XLS HTML ZIP404 inclusive navegacao Chrome; depois validar Natal atual e so entao concluir quatro cidades

## 2026-10-26 03:58 UTC — Retomada Atlas autenticado; Natal novos IDs463572 com anexos404

**Motivo:** Continuar execucao apos usuario citar bloqueio antigo de login

**Alterado:** Somente diagnostico e recuperacao explicita na UI: principal276908463 e reserva276908572, NetTask COMPLETO, XLS HTML ZIP404 e navegacao Chrome404; nenhum patch ou restart

**Verificação:** Consulta NetTask real autenticada; formulario quatro cidades; SQLite20jobs163049rows integrityok; smokes QUERYconfrontreports200; runtimec94984b hashes iguais; sem novos testes de codigo inalterado

**Próximo passo/pendência:** AtlasBatAtlas disponibilizar anexos dos IDs276908463 e276908572 em batch02app2 e batch01app1; apos200 validar Natal e concluir quatro cidades

## 2026-10-26 11:42 UTC — Atlas watchdog comprova sessao por NetTask

**Motivo:** Aba Atlas aberta e tarefa exit0 nao comprovam autenticacao; Natal atual tem anexos404

**Alterado:** Monitor somente leitura instalado em tarefa existentePT5M; commit5fa3132; backup preservado; pedido tecnico Atlas/BatAtlas preparado sem envio

**Verificação:** 9 novos RED-GREEN;51 QUERY Python;gate913 com21skip;6 verificacoes Windows;revisao independente;execucoes08:37 e08:40 autenticadas;DB20jobs163049linhas integro;UI3cidades ready eNatal404 persistente apos recarga

**Próximo passo/pendência:** Administrador Atlas/BatAtlas investigar anexos276908463e276908572; depois validar Natal ate CSV-XLSX e recarga. Monitor nao renova SSO. Nenhuma tarefa ChatGPT criada

## 2026-10-26 11:57 UTC — Natal novo par pedido pelo usuario e observacao horaria

**Motivo:** Usuario pediu novos IDs para testar apesar da dificuldade com suporte Atlas

**Alterado:** Confirmados276921081e276921083 em lote explicito auditado; backup antes; conector existente; sem terceiro automatico. Automacao ChatGPT horaria criada para observar par, distinta do worker

**Verificação:** IDs confirmados e salvos; manifestotwo_ids_confirmed;SQLiteintegrityok;principalapp2aguarda anexo e reservaem processamento;sem mudanca de codigo

**Próximo passo/pendência:** Observar somente par novo, conferir anexo e validar fonteDBUIexportacoesrecarga se disponivel; nao gerar mais IDs nem repetir avisos404

## 2026-10-26 12:12 UTC — Natal manual valido e parser FALHOU corrigido

**Motivo:** Arquivo manual valido20150NATAL e log NPE manual180 revelaram falha intermitente; estadoFALHOU era classificado processing

**Alterado:** Pipeline ceae3fd publicado e instalado combackup; apenas relay reiniciado; automacao horaria atualizada com manuais180e301; primeiro ID valido ainda falta

**Verificação:** RegressaoREDprocessing_vs_failed depoisGREEN;52QUERY Python;gate914com21skip;revisao14pipelineOK;consulta real180failed;DB24jobs163049linhasintegridadeok;smokes200anon401;parserXLS20150NATAL

**Próximo passo/pendência:** Obter primeiro ID que entregou XLS, comparar parametros/processador e download/hash servidor; nao gerar outras filas

## 2026-10-26 12:54 UTC — Natal manual2051 recuperado e video comparado

**Motivo:** Usuario comprovou downloadsapp3 e forneceu video amarelo-verde; comparar sem inferir garantia

**Alterado:** Manual2051 recuperado combackup no pipeline;20145linhas ready; datasAtlas corrigidas combackup; automacao horaria diferenciada. Nenhum novo ID nem patch produzido nesta etapa

**Verificação:** OriginalDBtodosdadosiguais;servicoCSV-XLSX200integros;browserCSV-XLSX20145x11todascelulasiguais;reloadID2051;DB25jobs183194linhasok;video51s eGETprocessosverde tambem em081404;parametros2051e081iguais

**Próximo passo/pendência:** Validar geracao automatica atual Natal sem depender de recuperacao manual. Nao gerar novas filas na observacao e nao declarar quatro cidades prontas

## 2026-10-27 17:10 UTC — Baixa oficial: ponte verificada, site aguardando publicacao

**Motivo:** POST de baixa ainda usava quick tunnel sem DNS apesar da busca TOA corrigida

**Alterado:** Middleware dedicado de baixa, Worker e release preparados; Worker 45b3f101 publicado com rollback. Main permanece217cc928 apos rejeicao de aprovacao automatica; preparar PR sem contornar.

**Verificação:** 949 Python/22skip, JS/Ruff/build;25focados e3release; canario sem efeito backend400,anonimo401,viewer403,DataSnap400,cidade duplicada404; nenhuma baixa real

**Próximo passo/pendência:** Obter autorizacao reconhecida para main/deploy do PR; depois validar interface e estado Imperium antes de repetir candidata

## 2026-10-27 17:18 UTC — PR21 publicado com autorizacao explicita

**Motivo:** Usuario autorizou integrar PR21 na main e deploy Hostinger

**Alterado:** Merge858dc6a; Actions40548766963success, smokes de producao e HTTP200; Worker45b3f101 preservado; nenhuma baixa real reenviada

**Verificação:** 25testes focados reconferidos; arvore publicada igual a testada; CI/build/smokes success; canario backend400;anonimo401/viewer403

**Próximo passo/pendência:** Entrar no navegador de teste se necessario e validar clique autenticado; conferir estado Imperium e dados de tecnico/equipamentos/materiais antes da baixa produtiva

## 2026-10-27 17:40 UTC — Snapshot produtivo e consulta de tecnico corrigidos para publicacao

**Motivo:** OS2662320818 bloqueada por hash antigo antes de qualquer escrita; GETinstaller404

**Alterado:** Busca atualiza linhas exatas completas; editor usa autorizacao coerente; resposta atrasada nao sobrescreve lista nova; GETinstaller autorizado; guardas backend preservadas

**Verificação:** 34JSfocados,949Python/22skip,JS/Ruff/build,3release; revisao independente e corrida corrigida RED/GREEN; materiais9+equipamento preservados no prepare/submit real simulado

**Próximo passo/pendência:** Concluir Worker e publicacao site; validar leitura instalador e pedir novo teste operacional sem repetir baixa automaticamente

## 2026-10-27 17:49 UTC — PR22 publicado e validado tecnicamente

**Motivo:** Corrigir stale_snapshot e404 de validacao tecnico mantendo guardas de baixa

**Alterado:** PR22/mainb8bf3e6; Workerf5170254; Actions40553080599 tentativa2success apos restart500na1; assetnovo+hashconfere; GETinstaller200

**Verificação:** 949Python/22skip,34JSfocados,JS/Ruff/build,3release; revisao e guardadecorrida corrigidas; CI+smokes de producao success; nenhuma baixa real repetida

**Próximo passo/pendência:** CtrlF5, nova busca do contrato e revisao da OS2662320818 antes de confirmar; validar resultado no Imperium, nao declarar materiais reais baixados ainda

## 2026-10-27 18:12 UTC — Baixa real confirmada; ponte mesclada preservando Matheus

**Motivo:** Aviso de tecnico404 separado de baixa concluida; publicacao concorrente de Estoque/QC perdeu rota

**Alterado:** Restaurada apenasGETinstaller em copia isolada da base de Matheus; Worker7590af22 comQC preservado; pastaMatheusintacta; main96b5abc ja integra ambos

**Verificação:** Confirmacao409/HTTP200,1instalado1removido9materiais;21JSWorkerQC e30JSmainintegrada;QC200,installeragoraatingebackend400porOSforaCache;POLICYhashconfereWorkerCRLFnormalizado

**Próximo passo/pendência:** Investigar somente identificacao tecnico da busca4321376/TOA_provider_nao_encontrado; nao repetir baixa confirmada; conferir ultima versao compartilhada antes de deploy

## 2026-10-27 18:29 UTC — TOA resource tree fallback restores contract4321376 lookup

**Motivo:** Search/details omitted Provider name although Time.get identifies exact PID66627/loginZ657615

**Alterado:** Added validated tree lookup and regression; surgical runtime patches with hash guards/backups preserve Matheus extras; extension/page reloaded without restarting Chrome

**Verificação:** 955Python22skip JS Ruff build pass; gateway and Worker200 exact aid203706151 two tasks no blockers; unrelated inventory-core auxiliary test remains5vs4

**Próximo passo/pendência:** Publish skip deploy; preserve historical assigned technician vs current route distinction and do not repeat confirmed close2662320818

## 2026-10-29 18:23 UTC — DESC por contrato e correcao de alocacao entre OS

**Motivo:** Mensagens reais dos quatro grupos incluem contratos de nove digitos e varios formatos; equipamento nao pode ser duplicado nem perdido

**Alterado:** Parser regional conservador, caixa de mensagens com nove digitos, dono unico dos equipamentos por codigo, evidencia completa e bloqueio de multiOS sem protocolo homologado

**Verificação:** Nove testes Node e setenta e seis testes Python no staging Windows; quality gate principal aprovado

**Próximo passo/pendência:** Homologar baixa das OS acompanhantes sem movimentacao e validar o fluxo completo de grupos antes de habilitar execucao

## 2026-10-29 18:23 UTC — Adesao com materiais completos e excecao diaria 106 das 23h

**Motivo:** Operador exige todos os itens TOA na Adesao e autorizou manter somente o lote noturno 106 ativo

**Alterado:** Assinatura e GPON somente codigo; qualquer material sem cobertura bloqueia antes de transferencia; lote 106 ativado nas quatro cidades e leituras ocupadas recebem retry limitado

**Verificação:** Quality gate: 982 testes principais com 22 ignorados, mais 14 de agendador e 12 de caixa de mensagens, JavaScript, Ruff e build aprovados; status real do agendador conferido

**Próximo passo/pendência:** Conferir execucao operacional apos 23h e validar transferencia oficial, retorno assincrono e Adesao completa sem reativar o varredor geral

## 2026-10-29 18:57 UTC — Auditoria do backup KNOWN_GOOD de 06/10 e gates DESC

**Motivo:** Operador indicou snapshot antigo para recuperar funcionamento das baixas pelos grupos

**Alterado:** Documentado inventario, integridade e comparacao AST; nenhuma alteracao de codigo ou runtime; Bot e runner continuam desarmados

**Verificação:** 13 hashes SHA-256 conferidos; comparacao AST de cinco metodos centrais; parser reproduzido e consultas TOA/Imperium somente leitura

**Próximo passo/pendência:** Homologar fechamento DESC sem itens das acompanhantes com equipamentos concentrados em uma OS; nao restaurar snapshot como correcao

## 2026-11-04 20:32 UTC — Contrato e sonda somente leitura do relatório Equipamentos Utilizados

**Motivo:** ZIP do fornecedor contém contrato offline mas não pacotes reais ou extrator; providers anteriores foram confundidos com outro fluxo

**Alterado:** Adicionado contrato com dois providers, validações estritas, verificação de versão ClientVCL e probe DataSnap somente connect+prepare; sem rotas, sem deploy

**Verificação:** 8 testes novos + 8 testes existentes aprovados; CLI offline e compilação aprovadas

**Próximo passo/pendência:** Capturar AS_GetRecords sem segredos da versão instalada, homologar payload, conferir saída por OS e código e integrar com seis abas

## 2026-11-04 21:23 UTC — MIDAS BCD legado 18 bytes e captura real de equipamentos utilizados

**Motivo:** ClientVCL de Natal retornou 89 linhas consolidadas e 1142 por OS mas o decodificador MIDAS nao suportava BCD tipo 5

**Alterado:** Corrigida leitura de BCD fixo 18 bytes com Decimal JSON-safe; documentados cabeçalhos obtidos localmente, privacidade da captura e falta de pacote cliente-para-servidor

**Verificação:** 25 testes dirigidos aprovados; dados reais decodificados em memoria no PC de origem; sem transferir PCAP

**Próximo passo/pendência:** Capturar apenas requisicao AS_GetRecords original e validar filtros/IDs; depois implementar consulta de leitura no Dominium

## 2026-11-05 18:12 UTC — Captura original e requests DataSnap byte a byte de Equipamentos Utilizados

**Motivo:** Duas capturas PktMon omitiam cliente-servidor; Wireshark/Npcap comprovou prepare mais duas chamadas execute

**Alterado:** Novo adaptador de leitura DataSnap com gerador de 605 e 602 bytes idêntico ao ClientVCL, parâmetros explícitos, validações e testes golden SHA256; relatorio em docs sem PCAP nem credenciais

**Verificação:** 28 testes direcionados aprovados; leitura real de Natal em laboratório: 89 consolidado e 1141 por OS, schemas válidos

**Próximo passo/pendência:** Validar adaptador combinado, homologar diferenças de 1 OS, mapear parceiros por cidade, implementar seis abas e download sem quebrar historico

## 2026-11-05 19:28 UTC — API separada de origem Imperium e tela de historico

**Motivo:** Consulta periodo na tela publicada so acessava SQLite e nao o DataSnap; usuario selecionou Mossoro sem arquivos e o botao de extracao estava disabled

**Alterado:** Criados endpoints de extracao com historico e XLSX de duas abas, autentica via relay, UI separa botao Extrair de Consultar historico; apenas Natal parceiro 1 confirmado

**Verificação:** 29 testes Python, 10 testes JS; Python 3.14 SQLite connections closed explicitamente

**Próximo passo/pendência:** Validar parceiros e operacao Mossoro, homologar seis abas e deploy seguro sem confundir fonte de duas abas com resultado final

## 2026-11-05 19:53 UTC — Video de equipamentos: cruzamento real por serial, Nomes e validacao de Mossoro e Recife

**Motivo:** Planilha de referencia 28/10 e DataSnap per OS do mesmo dia confirmam os 40 equipamentos mais 4 chips como intersecao com Nomes; Mossoro e Recife validaram perfil DataSnap e cidade

**Alterado:** Modulo puro equipment_video_transform, perfis Natal Mossoro Recife homologados, validacao fail-closed da cidade no catalogo e UI; Assinantes e Atlas exigem outras fontes

**Verificação:** 27 Python e 10 JS; data real Mossoro 16 e 52; Recife 60 e 480; Fortaleza timeout; workbook referencia privado na pasta Runtime

**Próximo passo/pendência:** Homologar video original e fontes Atlas/Assinantes, validar seis abas geradas, integrar a tela e fazer deploy apenas completo

## 2026-11-05 20:38 UTC — Consulta periodo DataSnap para Supabase operacional, sem Excel

**Motivo:** O botao anterior so pesquisava SQLite de arquivos importados; usuario requer consulta ao vivo diretamente no clique e persistencia Supabase

**Alterado:** Novo servico imperium_supabase_live com normalizacao, lotes JSONB, estados, idempotencia e revisao por cidade, migracao SQL segura, rotas no proxy e frontend com botao de consulta real; importacao Excel agora opcional

**Verificação:** 36 testes Python e 12 testes Node passaram; Supabase operacional respondeu HTTP 404 pois duas novas tabelas ainda precisam de migracao; nenhuma alteracao de banco ou deploy em producao

**Próximo passo/pendência:** Aplicar SQL em haqzzxpocwzntyudrbch, validar sync no Supabase real e publicar worker+Hostinger juntos

## 2026-11-06 15:04 UTC — Consulta e tratativa de seriais do Imperium separadas em duas etapas

**Motivo:** Operador pesquisa periodo no Imperium, salva seriais no Supabase e so depois clica Tratar seriais para executar historico individual

**Alterado:** Nova migration de itens por serial; servico com next status export; rotas relay autenticadas; UI com progresso pausa retomada; nao obriga Excel

**Verificação:** Smoke real DataSnap Natal 05-11-2026: 1096 OS e 209 seriais; historico primeiro serial confirmado e progresso 0 para 1 com repo simulado; 45 Python e 13 JS aprovados; nao gravou no Supabase operacional

**Próximo passo/pendência:** Executar migrations no projeto haqzzxpocwzntyudrbch e homologar escrita real; integrar demais fontes para seis abas

## 2026-11-06 19:36 UTC — Vídeos auditados: Atlas por equipamento após consulta DataSnap e seriais

**Motivo:** O vídeo exige conferência de estado/localização no Atlas após coleta de equipamentos utilizados no Imperium e consulta individual; Assinantes e estoque físico independentes

**Alterado:** Novo serviço imperium_atlas_video com fila segura, retorno Atlas persistido no Supabase via evidencia.atlas_video, UI de terceira etapa e rotas Hostinger autenticadas

**Verificação:** 54 Python, 15 Node; um Atlas real resultou verificado e foi gravado no Supabase; nenhuma consulta em massa e nenhuma modificação em estoque

**Próximo passo/pendência:** Auditar relatório Atlas Por Equipamentos em lote, confirmar baixa e estoque físico via fontes próprias, implantar backend e frontend coordenadamente sem sobrescrever main local divergida

## 2026-11-06 20:00 UTC — Video Atlas revisado; export intermediario com evidencias e pendencias

**Motivo:** O video distingue Equipamentos Utilizados do Imperium, Atlas Por Equipamentos, Atlas Por Localizacao e conferencias Assinantes

**Alterado:** Validacao de identidade serial na etapa Atlas, colunas de operacao e local, export de 4 abas auditaveis Seriais Tratados/Pendencias/Conferencia Atlas/Pendencias Atlas, documentacao baseada em videos matheusdmc0

**Verificação:** 55 unittest Python e 15 Node passaram; pacote do relay Python312 importado em staging isolado; sem deploy de producao

**Próximo passo/pendência:** Publicar code review com relay/Hostinger coordenados, homologar Atlas em lote e fontes das seis abas finais

## 2026-11-09 12:40 UTC — Controle de Baixas MRO visual 09-11

**Motivo:** Exibir a fila por cidade com Mossoró em destaque e cache produtivo já coletado, sem ativar baixas

**Alterado:** static/index.html static/app.js close-control-*.js close-control.css e testes; nenhuma escrita ou consulta TOA

**Verificação:** 26 testes Node aprovados; Chrome headless HTTP200 e screenshot; integração autenticada do worker pendente de smoke em Hostinger

**Próximo passo/pendência:** Publicar interface, verificar UI autenticada e, depois, instrumentar eventos duráveis e homologar Adesão Mossoró

## 2026-11-11 16:12 UTC — Exportacoes nativas de OS do Imperium

**Motivo:** Disponibilizar os dois XLSX originais Todos e Manutencao VT com periodo na interface

**Alterado:** Nova aba Relatorios de OS; rota privada autenticada somente leitura DspGetOs; 42 colunas com datas e memo iguais ao Excel nativo, IDs longos preservados como texto; politica compartilhada Worker Hostinger

**Verificação:** 9 testes Python; testes JS de escopo data download e ponte; comparacao 10/11 com XLSX originais 889 Todos e 80 Manutencao

**Próximo passo/pendência:** Publicar relay Worker e site; verificar download protegido em producao

## 2026-11-11 16:31 UTC — Relatorios de OS publicados e verificados

**Motivo:** Registrar disponibilidade real apos validar download diario e por periodo

**Alterado:** Publicacao da main na Hostinger concluida com sucesso; Worker e relay complementar atualizados com backup preservando estoque diario qualidade e REPORTs; ativos publicos iguais ao source e acesso anonimo bloqueado

**Verificação:** Testes Python e JS dos relatorios passaram no CI; dia anterior conferido com os dois XLSX originais; periodo de dois dias validado com arquivo de 156 linhas e 42 colunas; quatro cidades NET consultadas; gate geral mantem quatro erros preexistentes documentados

**Próximo passo/pendência:** Atualizar a pagina e acessar Operacao Relatorios de OS para selecionar cidade periodo e XLSX

## 2026-11-17 12:26 UTC — Relatorios usam a credencial do runtime Imperium ativo

**Motivo:** Downloads de OS e comissoes falhavam porque a credencial do checkout legado nao podia mais ser descriptografada pelo Windows

**Alterado:** Padrao compartilhado passa a usar config credentials do runtime Imperium, respeitando a raiz configurada no ambiente; sem copiar senha nem alterar os arquivos protegidos; runtime complementar atualizado com backup

**Verificação:** Teste sintetico reproduziu a selecao do caminho antigo e passou apos a correcao; dezessete testes de credenciais OS e comissoes aprovados; consulta real OS Mossoro e comissoes Natal voltou com a credencial ativa

**Próximo passo/pendência:** Conferir todos os XLSX pela ponte publicada e registrar o resultado do gate

## 2026-11-17 12:28 UTC — Downloads restaurados e validados na ponte publicada

**Motivo:** Confirmar que a troca da origem da credencial resolveu os erros dos dois relatorios

**Alterado:** OS e comissoes retornam Excel novamente; automacao TOA responde normalmente na verificacao atual

**Verificação:** Comissoes das quatro cidades e OS bruto tratado verificadas com resposta de sucesso CRC e XML validos; dezessete testes focados aprovados; gate geral executou mais de mil testes com os mesmos quatro erros antigos de limpeza SQLite e versao fixa do backlog

**Próximo passo/pendência:** Manter a credencial no runtime Imperium ativo e evitar depender da copia protegida do checkout legado

## 2026-11-18 19:52 UTC — Vistoria diária de baixas de materiais

**Motivo:** Comparar baixas do Imperium com os saldos do técnico e o Excel SAP do mesmo dia

**Alterado:** Adicionados histórico por técnico/local, tela e cálculo de divergência. Piloto salvo em Natal, 180 locais.

**Verificação:** Testes de quantidade acumulada, importação por data, coleta incompleta, isolamento por cidade, rotas e captura real.

**Próximo passo/pendência:** Publicar relay, Worker e interface juntos. Confirmar a próxima foto do estoque e o Excel SAP de referência.

## 2026-11-24 17:25 UTC — Homologação da fila de adesão NTL/PWM

**Motivo:** O lote exibia espera após confirmação, podia rejeitar a tarefa TOA exata por encontrar uma linha apenas informativa em outra atividade e confundia smart card de TV com chip móvel.

**Alterado:** Fila consulta TOA para cada contrato, preserva resultado e auditoria por O.S., exige tarefa exata e reconhece o smart card de TV pelo tipo da captura de adesão.

**Verificação:** Testes da fila, da aprovação atualizada e da ponte oficial, com cobertura de confirmação parcial e de GPON.

**Próximo passo/pendência:** Tratar divergências de estoque, técnico e códigos ausentes somente com evidência oficial.

## 2026-11-24 20:26 UTC — Reduzir espera pela lista do Imperium na adesão

**Motivo:** A fila fazia uma consulta inicial redundante e aguardava o terminal compartilhado por até 24 tentativas.

**Alterado:** A preparação reaproveita a lista em campo do snapshot atualizado devolvido pela consulta TOA. A leitura adicional e a aprovação de cada O.S. têm limite de quatro tentativas e 15 segundos.

**Verificação:** 33 testes focados na fila, no TOA e na ponte oficial, incluindo snapshot atualizado, resposta antiga e limite de espera.

**Próximo passo/pendência:** Observar lotes reais sem reabrir envios incertos.

## 2026-11-25 11:59 UTC — Aplicar regras de mudança de endereço na adesão

**Motivo:** O ponto adicional Virtua exigia serial novo mesmo com inventário TOA completo e sem movimentação de equipamento.

**Alterado:** Libera somente o serviço de mudança de endereço para ponto adicional Virtua quando as listas de instalação e retirada do TOA estão explicitamente vazias. A assinatura segue com código apenas. Itens movimentados continuam sujeitos à conciliação.

**Verificação:** 34 testes frontend e 23 testes Python focados, incluindo alocação de miscelâneas no ponto Virtua e payload oficial sem serializados.

**Próximo passo/pendência:** Validar em produção somente com uma O.S. autorizada.

## 2026-11-25 12:49 UTC — Expor falha de estoque anterior à baixa de adesão

**Motivo:** A ponte web convertia o erro de estoque em falha de transporte genérica e o observador legado podia substituir o estado do relatório por envio pendente.

**Alterado:** Preserva a resposta estruturada de transferência incerta quando a baixa ainda não saiu. A fila consulta tentativas anteriores e cruza falhas por O.S., contrato, código e horário antes de consultar o terminal.

**Verificação:** 55 testes focados da fila e da ponte, incluindo erro estruturado, timeout genérico e bloqueio sem reenvio.

**Próximo passo/pendência:** Conciliar a movimentação de estoque pendente antes de qualquer nova tentativa.

## 2026-11-25 13:08 UTC — Priorizar Descrição Atlas antes do RETORNO em Natal

**Motivo:** O saldo do código original no RETORNO podia evitar a consulta à Descrição Atlas no servidor, e a fonte web bloqueava a baixa por falta confirmada.

**Alterado:** Consulta o grupo Atlas antes do RETORNO, usa o saldo de códigos compatíveis no técnico e registra as quantidades dispensadas na baixa oficial de Natal. O patch do servidor altera somente o caminho da API oficial.

**Verificação:** 115 testes Python focados e cinco cenários da versão instalada com leituras e transferências simuladas, incluindo timeout do Atlas e estoque zerado.

**Próximo passo/pendência:** Verificar o serviço após a recarga sem disparar baixas ou transferências.

## 2026-11-25 13:29 UTC — Retomar baixa com revalidação de miscelâneas

**Motivo:** Uma falha antes do envio ao Imperium podia deixar a O.S. permanentemente em tratativa de estoque.

**Alterado:** A fila pede revalidação somente de uma tentativa comprovadamente anterior ao POST. Se o saldo atual permitir montar a baixa sem novo complemento, substitui a tentativa anterior com garantia de idempotência. Um complemento ainda possível no RETORNO mantém a pendência.

**Verificação:** Regressão de ausência de reenvio de transferência, vínculo do log legado, confirmação anterior e dupla submissão.

**Próximo passo/pendência:** Validar no runtime com operações simuladas e verificar flags após publicação.

## 2026-11-25 16:29 UTC — Baixar OS: consulta TOA na abertura do lote

**Motivo:** O Chrome gerenciado manteve uma aba TOA e a ponte respondeu intermitentemente. Leituras de status com limite de um segundo foram registradas como desconexão.

**Alterado:** O lote de adesão consulta o contrato mesmo com status anterior indisponível. Somente o erro específico da ponte antes da consulta recebe até três novas leituras.

**Verificação:** 24 testes do lote aprovados. Consulta real com HTTP 200 e duas O.S. no TOA. Nenhuma baixa ou transferência enviada nos testes.

**Próximo passo/pendência:** Acompanhar a latência do gateway compartilhado e validar o novo ativo público após publicação.

## 2026-11-25 16:43 UTC — Preservar falhas de leitura TOA no proxy web

**Motivo:** O proxy Hostinger transformava HTTP 502 da consulta de TOA em baixa Imperium incerta devido ao metodo POST. A nova tentativa de leitura nao recebia o motivo esperado.

**Alterado:** Apenas o lookup TOA recebe erro de leitura no proxy. A causa pre-consulta conhecida atravessa a ponte para permitir a retentativa do lote.

**Verificação:** Testes do relay, Worker e lote: 50 aprovados. Consulta direta de status nas quatro categorias encontrou ambas as OS de cada contrato ainda em campo.

**Próximo passo/pendência:** Validar publicação Hostinger e acompanhar latência da ponte TOA.

## 2026-11-25 17:41 UTC — Atualização de aprovação de adesão e vistoria de estoque

**Motivo:** O lote recebeu várias listas em cache enquanto o terminal estava ocupado. A vistoria falhava antes do primeiro local por argumento de construtor indisponível no runtime.

**Alterado:** A consulta de O.S. do lote Natal pode esperar o terminal por uma leitura atualizada. A vistoria cria um cliente compatível com o runtime operacional.

**Verificação:** 30 testes Python de escopo, fila e vistoria e 31 testes JS do lote e relay aprovados. Runtime legado preparado por substituições verificadas.

**Próximo passo/pendência:** Validar as duas rotas em produção sem executar baixa nem movimentação de estoque.

## 2026-11-25 18:01 UTC — Descrições e unidades do Atlas na baixa de adesão

**Motivo:** O leitor legado rejeitava registros exatos com rótulo de grupo ou só com códigos alternativos. O estoque também não tinha o código original de alguns cabos para confirmar a unidade.

**Alterado:** O leitor mantém o código exato do cadastro, extrai apenas aliases explícitos e usa a unidade lida no Atlas para conferir o saldo alternativo quando necessário.

**Verificação:** Cinco testes do leitor e 24 testes JS do lote aprovados. Simulação com 11 materiais reais conciliou equivalências e faltas, sem transferências previstas.

**Próximo passo/pendência:** Instalar o leitor e o ajuste do runtime em produção por hashes, com backup e validação somente leitura.

## 2026-11-25 18:35 UTC — Retomada segura do lote de adesão e confirmação do técnico

**Motivo:** Consulta ocupada descarregava contratos não enviados, O.S. sem código bloqueava GPON independente e o diretório antigo conflitava com a identificação atual do TOA.

**Alterado:** A fila reconsulta indisponibilidade antes de qualquer envio, mantém a tratativa do estoque incerto e processa serviços de código único estritamente correlacionados. Identidade do técnico usa evidência recente e escopo exato com confirmação no Imperium.

**Verificação:** Testes focados de lote, histórico e identidade. Validar em produção em modo de leitura com a captura e o instalador reais.

**Próximo passo/pendência:** Publicar e validar o ativo da fila após instalar as alterações verificadas no runtime legado.

## 2026-11-26 01:47 UTC — Adesao NTL/PWM: origem online e duplicidade de atividade

**Motivo:** A fila precisa certificar a origem informada pela ponte e distinguir reabertura suspensa da atividade concluida do mesmo contrato e O.S.

**Alterado:** Consultar data selecionada somente no fluxo de adesao. A ponte so seleciona uma atividade concluida com as mesmas O.S. das suspensas no mesmo bucket. Manter validacao do arquivo/identidade aprovada e sinalizar O.S. concorrentes por serial sem vinculo.

**Verificação:** Fila JavaScript, arvore de rotas, transporte de consulta secundario e gate completo.

**Próximo passo/pendência:** Validar leitura em producao e conferir baixas pendentes no Imperium, sem reenviar.

## 2026-11-26 02:13 UTC — Adesao NTL/PWM: grupo do RETORNO e recuperacao da fila

**Motivo:** A ausencia confirmada de um codigo no cadastro Atlas bloqueava toda a OS, havia materiais identicos com codigos diferentes no RETORNO e a fila apagava ao fechar a aba.

**Alterado:** Busca no grupo so aceita nome completo, grupo oficial, unidade e saldo coincidentes. Atlas vazio confirmado segue a rotina de falta de estoque. A fila salva contratos e status por operador/data neste navegador.

**Verificação:** Fixtures de retorno e de aba interrompida, gate completo e consultas de producao em leitura.

**Próximo passo/pendência:** Conferir a primeira execucao supervisionada com o novo planejamento, sem reenviar resultados incertos.

## 2026-11-26 02:31 UTC — Restaurar XLSX do relatorio de baixas

**Motivo:** O painel legado servia o relatorio JSON, mas nao tinha a rota binaria utilizada pelo botao Baixar XLSX.

**Alterado:** Reutilizar o renderer de XLSX e a rota do painel atual no legado. O botao baixa com a sessao ativa e informa erros sem navegar.

**Verificação:** Teste do workbook, rota portada, politica do relay e gate completo.

**Próximo passo/pendência:** Verificar o XLSX do dia 25/11 na origem operacional apos publicar.

## 2026-11-26 12:45 UTC — Adesao: preservar a origem da OS ao recuperar tarefas

**Motivo:** A consulta ao TOA gerava um CSV auxiliar que o indice via como coleta de operacao. Entre capturar e revalidar, mudava o hash de origem e a fila retinha as OS.

**Alterado:** O indice ignora pastas adhesion-readonly ao selecionar a fonte de aprovacao. A recuperacao ainda consulta o CSV auxiliar e uma mudanca da coleta regular continua invalidando o escopo antigo.

**Verificação:** Reproducao da terceira tarefa e da integridade de escopo, suites dirigidas e gate completo.

**Próximo passo/pendência:** Conferir em producao apenas por consulta o caso de tres OS.

## 2026-11-26 12:55 UTC — Adesao: identificar executor atual da atividade TOA

**Motivo:** A atribuicao historica de roteamento do TOA tinha PID e nome de outro tecnico, com o login do responsavel atual. A ponte propagava a atribuicao historica ao preparar a baixa em lote.

**Alterado:** Em consulta explicita de adesao concluida NTL/PWM, usa o responsavel atual quando busca, recurso, inventario e formularios concordam no PID e nome, com o mesmo login. Evidencia incompleta continua em tratativa.

**Verificação:** Regressao de atribuicao antiga com login reaproveitado, rejeicao de provas incompletas e gate completo.

**Próximo passo/pendência:** Conferir captura e titular do estoque no Imperium sem enviar baixa.

## 2026-11-26 13:30 UTC — VoIP isolado: manter o EMTA ja cadastrado no cliente

**Motivo:** TOA repete o serial do EMTA atual nas linhas Cliente e Instalado para o ponto de telefone; o envio acabava exigindo o serial no estoque do tecnico.

**Alterado:** Na baixa produtiva de adesao em lote, VoIP isolado com EMTA identico em Cliente reaproveita o serial sem movimentar o equipamento e continua preparando as miscelaneas. VoIP com Virtua continua apenas com codigo quando o EMTA e compartilhado.

**Verificação:** Regressao com serial ja instalado, serial diferente, outro tipo de equipamento, substituicao e par Virtua/VoIP. Consulta real da OS concluida sem reenvio.

**Próximo passo/pendência:** Validar o arquivo publicado no Hostinger.

## 2026-11-26 14:08 UTC — Adesao NTL/PWM concilia executor sem movimentos e le separador Atlas

**Motivo:** O TOA pode reter o responsavel anterior em atividade improdutiva, e o nome de estoque do Imperium tem grafia diferente para um ID confirmado. O Atlas envia separador MIDAS dentro do alias do marcador.

**Alterado:** Confirmacao de executor por rota, busca e formulario mesmo com inventario explicitamente vazio em tarefas N com codigo. Grafia de estoque conferida por ID, login e nome de origem. Parser aceita apenas o separador MIDAS entre codigo e underscore.

**Verificação:** 20 testes direcionados passaram, incluindo identidade divergente, ausencia de prova de estoque, tarefas com movimentos e registro Atlas malformado.

**Próximo passo/pendência:** Validar em producao por consulta, incluindo lotes com atividades improdutivas. Nunca reenviar tentativa de resultado incerto.

## 2026-11-26 18:21 UTC — Adesao concilia executor com cadastro incompleto no TOA

**Motivo:** A rota e o inventario do TOA podem fornecer o ID correto do executor sem preencher nome e login; o login pode vir associado ao responsavel anterior na captura.

**Alterado:** Usa busca e formulario concordantes, com IDs da rota e inventario, preservando rejeicao de divergencias. Cadastra grafia de estoque validada para o ID 249803 apenas com prova da OS.

**Verificação:** Testes de regressao cobrem provedores com dados ausentes, inventario divergente e formulario sem identificacao. Suite direcionada aprovada.

**Próximo passo/pendência:** Verificar consulta e plano no runtime antes de repetir apenas baixas elegiveis.

## 2026-11-26 19:09 UTC — Mudança de endereço com equipamento opcional e descrições Atlas longas

**Motivo:** A fila exigia EMTA ou decoder em mudanças sem instalação daquele tipo. O isolador 22056394 falhava com uma descrição Atlas MIDAS de 352 bytes.

**Alterado:** O lote aceita miscelâneas sem equipamento novo em mudança de endereço com inventário explícito. Seriais efetivos continuam sujeitos a identificação, alocação e antirreenvio. A leitura Atlas aceita comprimento de dois octetos com validação do registro.

**Verificação:** 46 testes JavaScript e 19 testes Python focados. Consulta real somente leitura validou o isolador 22056394 e o marcador 22065723.

**Próximo passo/pendência:** Conferir o asset e o parser depois de publicar, usando somente leituras. Acompanhar solicitações pendentes pelo relatório sem reenviar.

## 2026-11-27 12:55 UTC — Identidade visual DOMINIUM em preto e vermelho

**Motivo:** Padronizar a interface operacional com a nova paleta e a estrutura compacta da referência do usuário.

**Alterado:** Tema visual compartilhado, menu, cabeçalho e indicadores. A animação de consulta existente usa a paleta nova sem mudança no controlador ou APIs.

**Verificação:** Chromium no desktop e a 390 px, alternância de tema, navegação, fluxo de animação e movimento reduzido. Empacotamento Hostinger.

**Próximo passo/pendência:** Validar o CSS publicado e a entrada do painel após o deploy.

## 2026-11-27 13:11 UTC — Layout de navegação inspirado no protótipo DOMINIUM

**Motivo:** Migrar a estrutura da interface de referência para o painel operacional.

**Alterado:** Menu de altura integral com grupos e gaveta móvel, cabeçalho com seletor de base e busca de módulos, Visão geral na entrada e painel reorganizado em duas colunas. Fluxos e animação existentes reaproveitados.

**Verificação:** Chromium desktop e celular, rotas diretas, navegação, escopo por base e consolidado, tema e animação. Testes de navegação do Backlog e empacotamento.

**Próximo passo/pendência:** Conferir a publicação do painel web.

## 2026-11-27 13:31 UTC — Lista diária de OS e administração DOMINIUM

**Motivo:** Evitar consulta DataSnap a cada abertura e apresentar módulos administrativos e tema claro consistente.

**Alterado:** Lista de campo por base a cada cinco minutos das 08h à meia-noite, cache volátil autenticado, Query no Estoque, superfícies claras e telas de administração com dados e permissões existentes.

**Verificação:** Testes de janelas de Brasília, renovação, falha, virada do dia, ponte privada, navegação e tema em Chromium, e gate completo.

**Próximo passo/pendência:** Conferir lista e autorização após publicar o painel.

## 2026-11-27 18:46 UTC — Baixa improdutiva da O.S. acompanhante de assinatura ou GPON

**Motivo:** O TOA pode registrar apenas uma tarefa quando o atendimento termina improdutivo.

**Alterado:** Lote Natal/Parnamirim reaproveita o codigo explicito da unica tarefa concluida para a acompanhante validada do mesmo atendimento, sem itens e apos confirmacao da principal.

**Verificação:** Regressao simulada para codigos 106 e 110, ausencia de inventario, concorrencia de atividades e retomada com confirmacao exata.

**Próximo passo/pendência:** Validar a publicacao do frontend sem executar baixas reais.
