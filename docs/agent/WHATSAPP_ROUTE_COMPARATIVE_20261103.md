# DOMINIUM — comparativo histórico das cinco rotas para WhatsApp (03/11/2026)

## Fluxo operacional reproduzido do painel antigo
1. Carregar os cinco XLSX/CSV em **Rotas do dia** ou clicar **Buscar 5 rotas do TOA**.
2. Clicar **Analisar arquivos**.
3. O backend compara os contratos das rotas com os códigos selecionados no histórico anual do Imperium (101/306/404/430 por padrão).
4. A interface mostra **resumo por cidade**, grupos por técnico, contratos, código histórico e data.
5. **Copiar tudo para WhatsApp** gera texto completo pronto para colar manualmente no grupo. Não envia mensagem automaticamente.

Este relatório é um **cruzamento da rota atual com códigos no histórico**. Não é uma listagem de O.S. baixadas no dia. Código **430** é retirada produtiva, mantido no filtro de prevenção e explicitamente identificado, não deve ser denominado baixa improdutiva.

## Filtro de cidade
- Por padrão, segue a aba superior do DOMINIUM:
  - Natal/Parnamirim => NTL e PWM, mantendo dois grupos separados dentro do relatório.
  - Fortaleza => FTZ
  - Mossoró => MRO
  - Recife => JCR
  - Todos => todas as cinco rotas (quando selecionado).
- Há seletor local de escopo, inclusive **Todas as cidades**, que não altera o perfil operacional do DOMINIUM.
- Todos os contadores, registros e o texto copiado obedecem ao mesmo escopo.
- `route_file` identifica NTL/PWM, corrigindo a cidade combinada da normalização anterior. O vínculo ao histórico usa também a base/profíle correspondente para impedir cruzamentos de contratos entre bases.
- Se a rota exceder **1.000 atividades**, o relatório não deve ser copiado como completo: a interface sinaliza truncamento e bloqueia a cópia.

## Implementação e limitações
- Backend: extensão read-only de `BacklogHistoryService.compare`, mantendo a rota privada **GET /api/backlog/year/compare?limit=1000&codes=...` existente no Worker VPC.
- UI: `static/backlog-report.js` (construção determinística), `static/backlog-analysis.js`, HTML e CSS da Análise Backlog.
- Uso de `textContent` e nós DOM para dados de planilha, sem interpolar HTML recebido.
- O histórico SQLite inicial conserva **dia de baixa**, mas não horário. A interface e a mensagem não inventam hora.
- Exportação direta do TOA pode fornecer login em vez de nome amigável; XLSX manual com coluna Recurso conserva o nome.
- O painel antigo usa outro banco D1, portanto os totais podem diferir do SQLite do DOMINIUM até harmonização comprovada.
- Não cria código de O.S., não realiza baixa, não mexe no histórico importado e não faz envio automático ao WhatsApp.

## Validação
- Servidor DESKTOP-K7J3E1N: backup em `C:\DominiumRuntime\BacklogLab-20261030\backups\20261103-whatsapp-comparison-prepatch`.
- 43 testes Python `test_backlog*.py` no PC de trabalho; 33 no Python do servidor.
- API de comparação testada com autenticação e banco real: **388 atividades** analisadas, **136 correspondências históricas** com os quatro códigos, NTL=135, PWM=22, FTZ=114, MRO=34, JCR=83; SQLite original continuou com 101.703 eventos.
- UI: quatro testes adicionais de formatação e filtro; total de dez testes Node (incluindo proxy seguro), parser HTML e empacotamento testados.
