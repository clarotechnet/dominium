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
