# Fluxo Atlas: conclusão do processo, reserva e nova geração explícita

> For agentic workers: use superpowers:executing-plans. Implementação local
> com TDD e revisão independente final; autorização de executar/testar/publicar
> já fornecida pelo usuário. Base b333b714e230d99243ee5d69b31c886c273df619.

**Goal:** aplicar o fluxo demonstrado pelo usuário no DOMINIUM: acompanhar
processamento, esperar conclusão e validar o anexo; reservar um único novo ID
45 segundos após a confirmação do ID principal, mesmo se ele já estiver pronto. Nunca declarar pronto só pela cor verde.

**Architecture:** reutilizar ChromeAtlas, evaluate_query, worker e índice único
de fallback existentes. Acrescentar leitura da página oficial processos.do;
máximo dois IDs por ciclo (principal+reserva). Nova geração após relatório pronto
exige clique explícito e referência idempotente ao ciclo anterior.

**Tech Stack:** Python/SQLite/CDP e JavaScript atual, sem nova API/serviço ou dependência.

**Spec/Design:** este documento e ATLAS_QUERY_VIDEO_RECOVERY_20261026.md.
Usuário pediu aplicar fluxo após testes manuais. O limite de dois é decisão
de implementação comunicada; não atribuir ao usuário a escolha numérica.

## Alternativas e decisão

Repetir somente downloads não resolve FALHOU. Geração ilimitada causa duplicações.
Escolha: verificar processo real, reserva única automática temporizada em45s,
e novo clique quando o ciclo se esgota. Históricos com fallback_enabled0 ficam
preservados. O indicador verde não garante que o arquivo foi publicado.

## Global Constraints

- Somente QUERY Atlas nas quatro cidades; sem TOA/baixas/estoques/contratos/OS.
- Backup antes de runtime/banco operacional; preservar Chrome autenticado.
- Sem ID principal confirmado, nunca iniciar reserva. Erro de leitura não autoriza retransmitir submissão.
- Não retransmitir submissão incerta após restart. Preservar IDs e isolamento de operador.
- Máximo principal+uma reserva por ciclo. Reserva não cria outra reserva.
- Sem segredos, URLs privadas ou clientes no Git/logs de diagnóstico.

## Review Focus

- Tabela COMPLETO com gráfico processando/indefinido: não abrir/baixar anexo.
- FALHOU com ID confirmado: uma reserva, inclusive após restart; nenhuma duplicação concorrente.
- Reserva ainda pendente de aparecer: UI continua consultando e bloqueia novo clique.
- Relatório pronto: novo clique cria ciclo novo ligado ao anterior; repetição/restart reutiliza o mesmo novo ciclo.
- Dois IDs esgotados: ação explícita permitida; fonte incerta/timeout/auth bloqueada.

## Task 1 — processo antes de anexo

Arquivos: atlas_query_pipeline.py e tests/test_atlas_query_pipeline.py.
Interface: read_process_state(chrome,remote_id)->complete|processing|failed|unknown.
GET oficial /nettask/filas/processos.do?idFila=ID via CDP autenticado, stream
limitado/fechado, correlação do ID e tipoRELATORIO_EQUIPAMENTOS. Nenhuma navegação
ou popup adicional. evaluate_query só abre Anexos após complete; poll_report
persiste estado desconhecido como processing/process_status_unconfirmed.
Rechecagem de404 não baixa URL antiga se processo voltou aprocessing oufailed.

- [ ] Testes RED: completo/processando/falhou/ID errado/HTMLlogin/limite stream;
  gate impede anexos, falha no recheck preservaID e não baixa arquivo antigo.
- [ ] Implementação mínima; testes QUERY Python GREEN.

## Task 2 — reserva e geração explícita

Arquivos: atlas_query_http.py e tests/test_atlas_query_http.py.
_ensure_fallback usa fallback_delay_seconds45 e fallback_due_at persistidos na
confirmação atômica do ID. Scheduler separado não fica preso em downloads;
apenas raiz nova habilitada com ID válido, no máximo um filho mesmo apósready.
Legados preservam política anterior; não ativar temporizador retroativamente.
índice fallback_of garante singleton. Não alterar históricos desabilitados.

POST existente aceita refresh_job_id para ciclo mais recente que contém ready
com ID e dados. Reutilizar transação/guardas/retry_of da recuperação existente,
mantendo ready fora de retry_job_id. Novo campo não muda rota. Novas tentativas
explícitas de família falha aceitam membros FALHOU ou404>=2 com idade>=120s;
timeout/login/envio incerto bloqueados. Cross-operator guard permanece.

- [ ] RED/GREEN para falha definitiva, reserva única/restart/concorrência,
  bloqueios e refresh pronto idempotente/actor/cidade/último ciclo/dados.

## Task 3 — UI e publicação

Arquivos: static/atlas-query-ui.js, static/index.html e testes UI.
UI prepara reserva após falha confirmada sem novo POST do navegador; mantém
polling enquanto reserva não aparece. Mensagens distinguem processo e arquivo.
Clique em ready envia refresh_job_id da raiz; novo asset20261026-2.

- [ ] RED/GREEN polling/reserva, não-post automático, novo clique ready,
  recuperação de falhas mistas, erro indefinido sem geração.
- [ ] Gate completo, revisão independente, corrigir achados por TDD.
- [ ] Publicar via GitHub, deploy web e runtime combackups/rollback, verificar hashes.
- [ ] Criar QUERY atual Natal pela UI, acompanhar ambos IDs se necessário,
  validar fonte/banco/UI/CSV/XLSX/recarga; conferir demais cidades sem mascarar origem.
- [ ] Atualizar registro, automação horária e versão efetiva. Não concluir quatro cidades se fonte continuar falhando.

## Ledger

Pre-flight: Task1 fornece estados ao worker Task2; Task3 consome estados e
fallback_enabled/retry_of existentes. Sem schema novo. Worktree isolada atual
verificada limpa antes de iniciar. Nenhum teste de geração adicional enviado.

## Aprovação atual
Usuário definiu principal+reserva após45s e autorizou execução nesta sessão.
Implementação inline com testes e revisão final. Reserva não depende de404.
A criação é agendada para45s; confirmação remota depende da latência Atlas.

Final review: dois achados importantes reproduzidos por regressões:
P1 reconciliação de envio incerto temporizado não liberava ciclo explícito;
P2 ready principal+reserva404esgotada bloqueava refresh naUI. Corrigidos
comRED→GREEN. Também cobertos rootfailed antes da reserva e guardentreoperadores.
Verificação exige TZ=America/Sao_Paulo por testes legados do monitor; ambiente
recriado após interrupção, dependências temporárias /tmp/dominium-deps.

## Ajuste solicitado em13:42
Printmanual276934585: FALHOU no mesmo segundo13:41:49. Usuário pediu
reserva imediata quando falhar diretamente. Antecipar SOMENTE após
statefailed/remote_queue_failed eIDconfirmado; erros de sessão, timeout
eestado desconhecido não antecipam. Semfalha, reserva45s; limite2mantido.
