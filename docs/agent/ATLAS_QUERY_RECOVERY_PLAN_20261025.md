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
- [x] Verificar testes QUERY, gate completo e revisão independente; publicar
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

## Ampliação necessária após teste real — 26/10, 00:05

Natal principal276907780 e reserva276907783 retornam404 em app-2; oito horas
impediriam recuperação prática. Adicionar recuperação explícita na mesma rota
POST com retry_job_id, após duas falhas404 por membro e 120s de idade, apenas
para a família mais recente do operador/cidade. Ambas devem ter ID confirmado.
Persistir retry_of com índice UNIQUE; repetição do mesmo POST retorna o mesmo
trabalho. Não alterar IDs antigos nem gerar por timer. Nova família conserva
uma reserva automática. Bloquear envios incertos em qualquer família da cidade.
Adicionar testes de concorrência, propriedade, replay, prazo, erros e restart.
Migrar/deploy relay com backup e sem reiniciar Chrome; verificar UI e produção.

Implementação ampliada: migração aditiva retry_of/índice único; validação da
família mais recente e proteção de concorrência entre operadores preservada.
Revisão encontrou bypass dessa proteção na primeira versão; teste reproduziu
202 indevido, correção passou a retornar409. Sem envio ao Atlas nos testes.
O keepalive em execução foi observado em logs CDP: sucessos a cerca de80s
após o login; existe lacuna extensa anterior. Isso comprova funcionamento
atual da consulta, não renovação automática de SSO nem causa exata da expiração.

## Encerramento desta execução

Código publicado e runtime verificado em c94984b. Validação atual de Fortaleza, Recife e Mossoró aprovada. Natal permanece bloqueada por anexos 404 na origem; meta das quatro cidades não concluída. Evidências, backups, IDs e ação do fornecedor em ATLAS_QUERY_VERIFICATION_20261026.md.
