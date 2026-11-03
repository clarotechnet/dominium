# DOMINIUM — escopo global "Todos" e desbloqueio do Backlog (03/11/2026)

## Pedido e causa
- O filtro Todos operava como navegação exclusiva para `Todas as operações`, perdendo o escopo ao abrir Estoque e outras áreas.
- O botão `Analisar arquivos` permanecia desabilitado após importar cinco rotas do TOA, porque o wrapper de ação não restaurava os controles ao terminar.

## Solução implementada na interface
- `state.allCities` é um escopo de **visualização** persistido no parâmetro `scope=all`, independente de `state.profile` (base operacional).
- Em `Análise Backlog`, Todos permite comparar as cinco rotas e gerar o relatório por cidade, sem mudar a base operacional.
- Em `Estoque`, Todos abre `Análises e Relatórios -> Análise de equipamentos`, usando o endpoint já existente `GET /api/stock/analyses/daily?city=all`. Importação e relatórios por base são bloqueados neste escopo.
- Em módulos de execução por cidade, Todos permanece selecionado mas a área operacional fica oculta por aviso. Para executar ações, é obrigatório escolher explicitamente uma cidade; não reutilizar silenciosamente a última base.
- Alternar Todos/cidade limpa dados consolidados do Estoque e reconsulta a fonte correta, quando o painel está aberto.
- `syncRouteButtons` mantém `Buscar 5 rotas`, `Carregar arquivos` e `Analisar arquivos` liberados depois do processamento, e bloqueados somente durante atividade efetiva. Importador histórico permanece indisponível.
- Não foram alterados endpoints, Workers, DataSnap, TOA, escrita de equipamentos, baixa de O.S. ou controles de autenticação.

## Segurança e limitações
- `Todos` não é uma base operacional válida para executar baixas ou movimentações.
- Módulos sem consulta multipraça implementada exibem aviso em vez de apresentar dados de uma base como se fossem todas.
- Os relatórios do Estoque consolidados mostram apenas registros históricos disponíveis; ausência de dado não é zero.
- Questão independente reportada em 03/11: alerta de login TOA de outro técnico ao tentar baixar O.S. 2663233182. **Não corrigir automaticamente**, requer diagnóstico próprio antes de alterar baixa.

## Validação antes de publicação
- 34 testes JavaScript aprovados para filtros, roteamento, bloqueio de escrita, importação TOA, relatório WhatsApp/PNG, estoque e navegação.
- 4 testes Python no catálogo diário de equipamentos aprovados, incluindo rota `city=all` e recusa de importação com `city=all`.
- Teste estrutural de markup (Backlog/Estoque e controles) aprovado; compilação JS passou.
- Publicação pela branch `main` apenas depois dos gates de Hostinger; confirmar status de deployment e resposta HTTP no site.
