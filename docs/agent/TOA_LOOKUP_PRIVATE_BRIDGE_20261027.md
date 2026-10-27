# Buscar no TOA — correção do transporte em 27/10/2026

## Causa confirmada

TOA autenticado no servidor DESKTOP-K7J3E1N: GET loopback de status HTTP 200,
connected/authenticated true. O POST /api/toa-live/lookup?profile=natal não
constava da lista privada da Hostinger e caía no quick tunnel antigo
citizenship-energy-label-conflict.trycloudflare.com, cujo DNS não resolvia.
A mensagem da tela era indisponibilidade do servidor operacional, não login TOA.

## Mudança

Commit remoto 07e87954f9bce65b432bad3ee40c81de85191e4d adiciona somente esse
POST de leitura com perfil explícito, via Worker e IMPORT_SERVICE existente
em 127.0.0.1:8765. Hostinger mantém sessão, CSRF e admin/controller. Worker mantém
credencial interna, domínio fixo, corpo JSON e limite de 64 KiB; não envia cookie,
CSRF nem token para o backend legado. Não há retry nem ampliação de baixa,
estoque ou conexão do navegador. O timeout dessa leitura passa a 285 segundos.

## Verificação

- Quatro testes novos falharam antes do ajuste e passaram depois.
- 23 testes focados de transporte/JSON, 960 testes Python com 22 ignorados,
  JavaScript, Ruff e builds passaram; três testes de dependências do release Hostinger passaram.
- Revisão independente sem bloqueios. Validado no backend legado efetivo,
  cujo acesso privado já atende imports e leituras sem sessão do navegador.
- Lookup loopback retornou o contrato 4321295 de Natal, uma atividade.
- Worker publicado c1913378-2671-42eb-98e3-d3751821f3e4 retornou HTTP 200,
  contrato 4321295, uma atividade, duas tarefas, nove materiais,
  activity_status complete, sem operation_blockers ou validation_errors.
- Resultado privado salvo apenas no servidor, fora de Git. Não foi executada baixa.

## Publicação e recuperação

Worker instalado antes da Hostinger, a partir de
C:\DominiumRuntime\TOALookupFix-20261027. Versão anterior do Worker:
df06c864-b586-42fb-a200-4da8d4374943, preservada com comando de rollback.
Main anterior 93af2cfcc2f606e8e9cbb9a698d443df02fe1979; os seis arquivos
alterados conferiam com a base. Publicação preservou a correção recente da QUERY.
Deploy Hostinger Actions 40512508841: success; upload/build e smoke de produção aprovados.
Worker real também recusou chamada anônima com 401 e viewer com 403.
Nenhum serviço Python, Chrome ou perfil foi reiniciado nesta mudança.

## Limite da validação

O navegador de validação está sem sessão DOMINIUM. A consulta real foi validada
pela ponte privada; o clique autenticado no site não deve ser declarado testado
sem evidência posterior. Baixa produtiva de adesão continua separada deste ajuste.
