# Estado atualizado apos autorizacao explicita

PR21 integrado em main858dc6a2b0a9ca5fa1146780bba653bdb4d7c477.
Usuario autorizou a integracao e o deploy neste chat. Actions40548766963
concluiu success, incluindo build Hostinger e smoke tests de producao.
Arvore publicada9bb247bac3569bbd49d81458b1af194608c8f7c7 igual a testada.
Pagina inicial e API de sessao retornaram HTTP200 apos deploy; baixa anonima401.
Worker45b3f101 reconferido: canario sem efeito backend400; anonimo401,viewer403,
DataSnap400 e cidade duplicada404. Nenhuma baixa real reenviada.
Navegador de validacao exige login DOMINIUM: clique autenticado e baixa produtiva
ainda nao validados. Bloqueio de publicacao nas secoes abaixo e historico superado.

# Baixa via ponte privada — 27/10/2026

## Causa

A pesquisa TOA funcionava via Worker, mas o POST /api/orders/<id>/close ainda
seguia para o quick tunnel antigo. DNS desse tunel falhou; o historico de baixas
nao continha a tentativa de assinatura mostrada no print. A mensagem generica
nao comprovava erro de login TOA.

## Implementacao e testes

Commit 2b15c02 adiciona middleware dedicado de baixa com sessao, CSRF,
admin/controller, cidade unica e ID positivo. Somente official_http cruza essa
ponte: o painel legado nao preserva identidade DataSnap por usuario.
Corpo JSON limitado a 64 KiB, payload original preservado, nenhuma repeticao.
Validacoes reais de escopo, tecnico, seriais e materiais permanecem no backend.
Resposta perdida/redirecionada/invalida registra uncertain e safe_to_retry=false.
Novo modulo incluido no release e nos testes do CI.

25 testes focados passaram. Gate completo: 949 Python, 22 ignorados,
JavaScript, Ruff e build aprovados; tres testes do release Hostinger passaram.
Revisao independente sem problemas importantes. A observacao sobre metadado de
retry foi corrigida com testes RED/GREEN e nova verificacao completa.

## Estado publicado

Worker 45b3f101-812c-499c-b6f9-c4d7ee9b0e51 publicado e conferido por hashes.
Versao anterior c1913378-2671-42eb-98e3-d3751821f3e4 preservada com comando de
rollback em C:\DominiumRuntime\OrderCloseFix-20261027. Backend Windows e Chrome
nao foram modificados/reiniciados.

Canario sem efeito: ID inexistente 2147483647 e codigo INVALID_SMOKE_CODE.
Antes: Worker 404 Rota nao permitida. Depois: backend 400 Codigo de baixa nao
permitido, com cabecalho private-import-bridge. Anonimo401/viewer403,
DataSnap400 e cidade duplicada404. Nenhuma baixa real foi enviada.

Push main foi bloqueado pela revisao automatica por nao reconhecer autorizacao
explicita vigente e por considerar a branch principal consequencial. Main
confirmada ainda217cc9280fad7dc7bf5c0c31d2c3ee866d8cca70. Nao contornar com
merge, API alternativa ou deploy direto da Hostinger; preparar PR para revisao.
Site continua sem o middleware novo. Validacao produtiva de adesao pendente.

A candidata2663076895 apareceu EM CAMPO na primeira leitura. Em leitura posterior,
nao constou da lista atual retornada pelo painel. Ausencia nao comprova baixa;
conferir Imperium diretamente antes de qualquer novo envio real.
