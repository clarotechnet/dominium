# Recuperação QUERY Atlas — design e execução

Objetivo: permitir nova geração explícita após fila concluída sem anexo por
mais de oito horas; concluir geração atual nas quatro cidades. Autorização:
pedido técnico do usuário, incluindo novas QUERYs, correção/testes/publicação.

Escolha: reutilizar POST existente e sua idempotência SQLite de oito horas.
Não criar nova API, não fechar fila antiga, não fingir ready, não renovar login
automaticamente. Conservar histórico e botões de consulta/exportação.

Alternativas descartadas: alterar estado operacional antigo perderia evidência;
um endpoint de force-resubmit contornaria a proteção existente sem necessidade.

Regra UI: permitir clique quando todos os trabalhos da família têm ID
confirmado, estado attachment_wait/attachment_missing e mais de oito horas,
com erro 404, anexo não listado ou login necessário. Timeout continua bloqueado.
Sem envio automático; intervalo e atualização de tela nunca fazem POST.
Família recente, envio incerto, fila em processamento ou ID ausente continuam
bloqueados. O backend continua como autoridade para criar/reutilizar.

## Plano de implementação

- [x] Isolar checkout e verificar baseline: 14 testes UI passaram.
- [x] Escrever testes: família antiga libera clique explícito; família recente,
  reserva recente, envio incerto, processamento e ID ausente bloqueiam; refresh
  não envia; clique duplo não duplica. Ver RED antes de alterar código.
- [x] Corrigir static/atlas-query-ui.js com uma função de elegibilidade usando
  relatedJobs e Date.now; alinhar guarda create e disabled. Atualizar versão
  do asset em static/index.html e expectativa do teste de carregamento.
- [ ] Verificar testes QUERY, gate completo e revisão independente; publicar
  pelo GitHub/deploy. Conferir bytes da versão publicada.
- [ ] Validar criação real, ID, fila, fonte, banco, tabela, CSV/XLSX e recarga
  nas quatro cidades. Registrar IDs e bloqueios externos sem clientes/segredos.

## Evidências e decisões

- Watchdog Browser é passivo, tarefa agendada conclui com código 0. Conta abas
  e login_page; não prova autenticação de NetHome/NetTask. Keepalive de 80s é
  outra rotina da extensão, não um mecanismo de renovação SSO.
- Sessão renovada: formulário e controles de todas as cidades confirmados;
  evaluate_query de 276868465 retornou complete e anexo listado.
- Requisição inicial de recuperação via relay existente permite acompanhar o
  relatório enquanto o botão é corrigido. Backup consistente antes do POST.
- Nenhuma ação TOA, baixa ou mudança de estoque/contrato/OS autorizada.
- Ciclo RED observado antes do patch: seis falhas, incluindo botão bloqueado
  indevidamente e handler sem guarda. Timeout foi mantido bloqueado por teste.
  Estado atual: 38 Python QUERY e 32 JavaScript QUERY passam.
- Revisão independente não encontrou regressão bloqueante. Fixture de reserva
  recente corrigida para testar idade, com zero POST; casos de limite de oito
  horas, anexo ausente e aviso auth em fila concluída agora têm cobertura direta.
- Fortaleza nova principal 276907735/app-1 retorna404. Reserva automática
  276907771/app-3 chegou a ready com 29.529 linhas. Falta validar exportações/UI.
- Recife foi gerada pela UI: 276907778. Natal pela UI: 276907780. Acompanhamento
  e validação final continuam; não declarar conclusão enquanto faltar cidade.
