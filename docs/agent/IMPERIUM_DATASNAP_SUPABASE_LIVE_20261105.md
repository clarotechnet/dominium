# Dominium: Consultar período -> DataSnap -> Supabase (05/11/2026)

## Erro anterior

O botão antigo chamava GET /api/stock/analyses/daily, que consultava
somente um histórico SQLite de arquivos XLSX importados. A API
nunca solicitava os dados atuais ao Imperium no clique.

## Novo fluxo na branch (ainda NÃO publicado)

1. Admin/controller seleciona uma praça homologada e um período.
2. Clica em Consultar período (DataSnap → Supabase).
3. Hostinger valida sessão, papel e CSRF; relay interno autentica
   por token e confirma perfil de escrita.
4. POST /api/stock/analyses/imperium/live recebe somente
   cidade, data inicial e data final (nenhum arquivo/base64).
5. O servidor local verifica a presença das duas tabelas Supabase
   ANTES de executar a consulta DataSnap.
6. Executa a consulta AS_GetRecords nos providers
   DspConsolidadoEquip e DspConsolidadoOS da cidade.
7. Valida o campo Cidade em cada linha e normaliza os seriais;
   classifica chips/equipamentos e preserva zeros à esquerda.
8. Escreve os datasets originais e os seriais normalizados
   no Supabase em lotes de até 180 itens. Grava operador,
   datas, cidade, hash e contagens. Somente marca concluído
   depois da confirmação de todos os lotes.
9. Histórico e visualização paginada usam GET do Supabase,
   em lugar de arquivos locais ou Excel intermediário.

O backend usa service role somente no servidor local. As
tabelas têm RLS habilitada; anon e authenticated não
recebem permissões diretas. O frontend só acessa
as rotas autenticadas Hostinger -> relay.

## SQL necessário no Supabase operacional

Arquivo:
supabase/migrations/20261105173000_dominium_imperium_live_periods.sql

Projeto correto: haqzzxpocwzntyudrbch.
NÃO executar no projeto financeiro bkcnolpwteeqgipweiqs.

A conexão MCP do Supabase disponível no chat só tem permissão
no projeto financeiro. A API privada do projeto operacional
confirmou HTTP 404 para dominium_imperium_consultas e para
dominium_imperium_consulta_lotes. Assim, a migração não foi
aplicada; até instalá-la, o novo fluxo falha explicitamente
antes da consulta DataSnap e não retorna sucesso falso.

## Escopo funcional

O tratamento automático atual prepara os dados originais
e a análise de seriais usados (classificação por equipamento
ou chip, WO, OS, contrato, grupo e responsável da OS).
Não gera automaticamente as seis abas finais do vídeo:
Atlas, Chips Atlas, IMPERIUM, CHIP IMPERIUM, Assinantes, Nomes.
A DATA da referência e a conferência física de Assinantes
dependem de outras fontes verificadas. Os dados não serão
inventados ou apresentados como relatório completo.

Cidades DataSnap homologadas: Natal, Mossoró e Recife.
Fortaleza permanece desabilitada por timeout na tentativa real.
O botão de Excel e a exportação XLSX ficam apenas como
opções avançadas; a consulta principal não exige ambos.

## Verificações

- 36 testes Python passaram (inclui simulação de escrita de
  lotes no Supabase, persistência parcial, idempotência e
  recusa antes do DataSnap quando falta o esquema).
- 12 testes Node passaram (inclui o clique no botão real
  do DOM, rotas do proxy, segurança de escopo e mensagens).
- JavaScript analisado sem erros de sintaxe.
- Uma tentativa real de leitura do esquema operacional
  constatou que ambas as tabelas ainda precisam ser criadas.

## Passos ainda necessários para produção

1. Aplicar o SQL acima SOMENTE no projeto operacional.
2. Confirmar HTTP 200 nas duas tabelas via API privada.
3. Testar sincronização real de Mossoró e conferir contagens,
   histórico Supabase e paginação.
4. Publicar juntos worker/relay e Hostinger da mesma versão.
5. Para concluir a reprodução exata das seis abas, homologar
   as fontes Atlas, Assinantes, Nomes. e coluna DATA.
