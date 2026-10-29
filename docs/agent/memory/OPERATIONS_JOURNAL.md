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
