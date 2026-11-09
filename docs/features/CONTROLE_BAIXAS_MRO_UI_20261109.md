# Controle de Baixas — Mossoró em foco (09/11/2026)

## Escopo
Interface no DOMINIUM, sem alterações no executor de baixa, DataSnap, TOA, BOT DMV ou Worker Backlog.

- Menu: **Controle de Baixas**; rota `#controle-baixas`.
- Quatro colunas, nesta ordem: Mossoró, Natal/Parnamirim, Fortaleza e Recife.
- Animação FLIP, erro e conclusão **somente simulados** com O.S. fictícias. Respeita `prefers-reduced-motion`.
- Lista atual do Imperium: somente O.S. já carregadas na sessão, sem nova pesquisa TOA.
- Monitor do worker: consulta autenticada GET já existente `/api/auto-improductive-close` via ponte somente leitura em `static/app.js`; campos sanitizados e limitados.
- Cache produtivo: exibe contratos e O.S. já guardados pelo worker improdutivo como **não autorizados para baixa**. TTL operacional de 24h; cache não comprova execução.
- Botões que iniciariam baixa permanecem desabilitados.
- Não incluir a Central de Controladores do PR #33 ou qualquer novo agendador.

## Evidência
O servidor `DESKTOP-K7J3E1N` contém `auto_productive_cache.json` alimentado por `auto_improductive_runtime.py`. Snapshot lido em 09/11: 37 itens em cache, 2 em Mossoró, 17 Natal, 13 Fortaleza e 5 Recife. Contagem dinâmica, não equivalência a baixas concluídas.

## Testes e segurança
- 10 testes do motor, 13 do quadro por cidade e 3 de integração visual/leitura: **26 testes aprovados**.
- `node --check` de JS, `git diff --check`, prévia Chrome headless com HTTP 200 e captura de 1680×1000.
- Visualização de homologação não envia POST ou chamadas Oracle/TOA; GET existente usa autenticação DOMINIUM.
- Publicação restrita ao frontend; preview local fictício não deve entrar no GitHub.
- Não confundir `kind=productive_ignored` com confirmação no Imperium. Estado incerto exige revisão humana.

## Próximas fases
Conectar eventos persistentes de tentativa/erro/sucesso do worker a cada O.S., confirmar IdOS/contrato/AID/técnico/janela/bucket e resultado real no Imperium. Executar homologação específica para Adesão Mossoró antes de habilitar baixas produtivas.

**Rollback:** reverter o commit de frontend sem tocar nos dados ou na configuração das automações.
