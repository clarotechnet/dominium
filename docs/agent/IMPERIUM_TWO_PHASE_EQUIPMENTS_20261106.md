# Dominium — consulta Imperium em duas etapas (06/11/2026)

## Objetivo

A tela passa a executar duas tarefas distintas, sem exigir Excel:

1. Pesquisar o período: executar os providers de equipamentos utilizados do
   DataSnap, apresentar a coluna Serial da aba Por Ordem de Serviço, deduplicar
   e salvar a coleta no Supabase (cidade, datas, operador, hash e registros).
   Nenhum histórico individual é consultado nesse primeiro botão.
2. Tratar seriais: clicar em outro botão para consultar cada serial pelo
   DataSnap de movimentos, persistir evidências individuais, permitir
   pausa, retomada e repetição de falhas. Depois da contabilização completa,
   disponibilizar relatório XLSX dos seriais tratados e das pendências.

## Conferência real com 05/11/2026

A consulta read-only DataSnap de Natal retornou:
- Consolidado: 91 registros.
- Por Ordem de Serviço: 1.096 registros.
- Seriais únicos: 209.
- Linhas sem serial: 887.
- Seriais de 12 caracteres: 204; de 20 caracteres: 5.
- Cidades: Natal 948 linhas, Parnamirim 148 linhas.

O resultado coincidiu com o XLSX enviado pelo usuário, sem
usar o arquivo no fluxo de extração. Uma consulta individual
real de serial de 12 caracteres também confirmou identidade
e histórico DataSnap com quatro movimentações; posse atual não
foi confirmada, e nenhum saldo foi alterado.

## APIs e estrutura

Etapa 1:
POST /api/stock/analyses/imperium/live com JSON city,start,end
GET /api/stock/analyses/imperium/live?city=natal&start=...&end=...
GET /api/stock/analyses/imperium/live/{run}/data?city=natal&category=seriais_tratados&page=1

Tabelas: dominium_imperium_consultas,
dominium_imperium_consulta_lotes.
O nome interno legado seriais_tratados designa, nesta etapa,
seriais coletados e normalizados, ainda sem histórico individual.

Etapa 2:
GET /api/stock/analyses/imperium/serial-treatment/status?city=natal&run={uuid}
POST /api/stock/analyses/imperium/serial-treatment/next
GET /api/stock/analyses/imperium/serial-treatment/export?city=natal&run={uuid}

O endpoint next processa UM serial por vez, salva o resultado
e retorna progresso; o navegador decide continuar ou pausar
após concluir o registro em andamento. Resultados persistem
em dominium_imperium_tratamento_itens.

Estados: historico_verificado, sem_movimentos, erro_consulta e
formato_nao_suportado; antes da consulta, aguardando.
Timeout de DataSnap não equivale a equipamento inexistente.
O XLSX possui abas Seriais Tratados e Pendencias e preserva
advertências sobre posse atual não comprovada.

## Escopo e limitações

- Consulta por período homologada em Natal, Mossoró e Recife.
- Consulta individual de históricos homologada apenas para
  Natal com seriais de 12 caracteres; outras cidades devem
  ser testadas antes de habilitar etapa 2.
- Cinco seriais do exemplo possuem 20 caracteres; não
  são passados ao template que só suporta 12 caracteres.
  A pendência é explícita.
- O XLSX de tratativa NÃO representa ainda o relatório final
  de seis abas do vídeo. Essa conciliação ainda exige fontes
  Atlas, Assinantes, Nomes. e validação da coluna DATA.

## Migrations Supabase

Aplicar SOMENTE no projeto operacional haqzzxpocwzntyudrbch:

1. supabase/migrations/20261105173000_dominium_imperium_live_periods.sql
2. supabase/migrations/20261106115000_dominium_imperium_serial_treatments.sql

A conexão MCP Supabase disponível no chat lista somente
o projeto financeiro bkcnolpwteeqgipweiqs. Consulta privada
do projeto operacional confirmou HTTP 404 para ambas as tabelas
da etapa 1 em 06/11. Nenhuma migração foi aplicada. NUNCA
executar no Supabase financeiro.

## Antes da produção

Aplicar os dois SQLs no Supabase operacional, verificar leitura
autenticada das três tabelas. Testar POST /live real de 05/11
com 209 seriais e persistência. Executar poucos seriais da etapa 2
e conferir upsert/status/export. Depois publicar juntos worker local
e proxy/frontend Hostinger. Não publicar frontend isolado.

## Testes

45 testes Python de integração e regras mais 13 testes JavaScript
de UI, isolamento de cidade e proxy passaram. node --check passou.
Todos os testes de gravação Supabase usam repositório simulado
até a instalação do esquema no projeto operacional.


## Smoke integrado real em 06/11/2026

Em ambiente de trabalho isolado, validou-se a mesma operação
de 05/11/2026 com as duas etapas do mesmo serviço, sem arquivo
intermediário e sem qualquer escrita no Supabase de produção.

- A consulta DataSnap original retornou 1.096 linhas Por OS
  e 209 seriais únicos.
- Ao carregar a primeira etapa da coleta em armazenamento
  simulado, a tratativa retornou 0/209 processados, como esperado.
- Ao acionar um POST de tratativa individual real no DataSnap,
  a operação retornou 1/209 e situação historico_verificado.
- O resultado do primeiro serial foi persistido apenas no
  repositório simulado, para não tocar tabelas ausentes.
- Número de gravações no Supabase real durante o smoke: zero.

O teste de segurança confirmou que o botão principal não inicia
tratativa sem clique na segunda etapa. Pausar após a consulta
atual preserva o registro e impede o início do próximo.

Último impeditivo para ativação: executar duas migrações no
projeto operacional correto; não há acesso DDL nesse projeto
pela conexão Supabase atualmente disponível na conversa.
