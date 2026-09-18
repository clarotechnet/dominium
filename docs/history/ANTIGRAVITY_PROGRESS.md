# Antigravity Progress

## Repositório
- caminho: C:\Users\Public\Documents\Consulte Sistemas\Imperium\FerramentaImperiumDireto-OLLAMA
- branch: fix/city-scope-os-refresh
- HEAD: 7015d01b16ef45ed4e2abe7b34132487173a7e70
- project_id: IMPERIUM_OLLAMA

## Objetivo atual
1. Impedir no frontend (`static/app.js` e `static/index.html`) que o operador inicie o caminho HTTP legado, exibindo `official_http_legacy_disabled`.
2. Implementar localizador de candidatos 100% offline em `official_candidate_locator.py` e gerar relatórios.
3. Implementar a fachada unificada de resolução offline de miscelâneas em `official_material_resolver.py`.
4. Garantir 402 testes unitários 100% verdes sem uso de rede.

## Fatos comprovados
- Contrato `2221170` e OS `2646508672`/`2646508683` foram baixadas por outro operador e são marcadas como `closed_fixture_not_eligible`.
- DataSnap direto continua disponível no frontend e backend.
- Mapeamento `22025072` -> `22056408` é comprovadamente ERRADO (`22056408` é CONECTOR ATENUADOR 06DB).
- 22025072 e 22064608 permanecem materiais distintos.
- A opção HTTP oficial no frontend foi desabilitada no `<select>` e travada com lançamento de erro preventivo em `submitClose`.
- Nenhuma rede, consulta ao TOA ao vivo ou requisição POST foi executada.

## Trabalho concluído
- **Etapa 1 (Frontend Legado):** Opção "API oficial" no `<select>` de `static/index.html` alterada para desabilitada com rótulo `API oficial (Desativada - official_http_legacy_disabled)`. Em `static/app.js`, a seleção é forçada para `datasnap` e a função `submitClose` lança o erro preventivo `official_http_legacy_disabled` antes de disparar HTTP se o transport for `official_http`.
- **Etapa 2 (Localizador Offline):** Criado `official_candidate_locator.py` que avalia a elegibilidade de candidatos sem rede e gera `reports/official_candidate_search/CANDIDATOS_API_OFICIAL.json` e `.txt` com status `live_candidate_search_not_executed`.
- **Etapa 3 (Resolvedor Offline):** Criado `official_material_resolver.py` que executa a auditoria de grupos equivalentes e resolução estrita de miscelâneas (prioridade para código exato com saldo, Decimal, imutabilidade de entradas, bloqueio de unidades incompatíveis e auditoria de grupos unverified).
- **Testes:** Criado `test_offline_candidate_and_resolver.py` com 10 novos testes unitários.

## Arquivos alterados
- `app.py`
- `test_app.py`
- `static/app.js`
- `static/index.html`
- `official_candidate_locator.py` [NEW]
- `official_material_resolver.py` [NEW]
- `test_offline_candidate_and_resolver.py` [NEW]
- `reports/official_candidate_search/CANDIDATOS_API_OFICIAL.json` [NEW]
- `reports/official_candidate_search/CANDIDATOS_API_OFICIAL.txt` [NEW]
- `ANTIGRAVITY_PROGRESS.md`

## Testes executados
- `python -m unittest test_app.py test_offline_candidate_and_resolver.py` -> 21 testes OK.
- `python -m unittest discover -p "test_*.py"` -> 402 testes OK.
- `node --check static/app.js` -> OK.
- `python -m py_compile app.py test_app.py official_candidate_locator.py official_material_resolver.py test_offline_candidate_and_resolver.py` -> OK.

## Blockers abertos
- **resolvedor seguro de miscelâneas:** Fachada offline concluída; aguardando validação humana dos grupos equivalentes antes da integração.
- **grupos/equivalências:** Grupos `fiber_connector_sc_apc` e `fixador_rg6` verificados; 4 comparações contextuais classificadas como `unverified_equivalence_group`.
- **nenhuma nova OS aberta selecionada:** Nenhuma OS ao vivo consultada (busca registrada como `live_candidate_search_not_executed`).
- **acesso direto à API sem n8n:** Aguarda autorização para teste de rede/whitelist/proxy.
- **callback/confirmação assíncrona:** Sem endpoint de callback público ou consulta assíncrona oficial.
- **sender seguro:** `official_close_sender.py` ainda não conectado ao painel web.

## Decisões e motivos
- A opção HTTP legada foi mantida no DOM (desabilitada e rotulada) para possibilitar a reutilização pelo sender seguro no futuro, garantindo que o operador não possa disparar requisições acidentalmente.

## Último comando seguro executado
- `python -m unittest discover -p "test_*.py"`

## Próximo passo exato
Aguardar autorização humana para seleção de candidato real em Natal e conexão segura do `official_close_sender.py`.
