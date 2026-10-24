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
