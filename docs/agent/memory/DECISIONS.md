# DOMINIUM — decisões arquiteturais permanentes

## ADR-001 — Memória portátil e gratuita

**Data:** 2026-10-23. **Status:** aceita.

Fonte primária versionada em Git e Markdown. Entrada única por `AGENTS.md`,
adaptadores leves para Claude, Gemini, Copilot e Cursor. Índices de código já
existentes e cache de busca SQLite FTS5 reconstruível sem API externa.
Recuperação por tarefa, nunca despejar todo o histórico no prompt.

**Limites:** o agente precisa ter acesso autorizado ao repositório; não existe
contexto infinito nativo nem transferência mágica entre contas.

## ADR-002 — Confrontação de equipamentos é somente leitura

Confronto Atlas × IMPERIUM nunca executa baixa, transferência nem ajuste de
estoque. Histórico antigo e indicação Atlas de SUSPEITO não comprovam posse
atual nem fraude. Retorno parcial ou divergência não comprovada deve ir para
revisão ou inconclusivo. Código: `integrations/serial_consult/`.

## ADR-003 — Segredos e dados operacionais fora do Git

Não versionar credenciais, Chrome profiles, logs, dados de clientes, contratos,
seriais reais, tokens, dumps, SQLite de operações ou backups privados.
Consulte `.gitignore`, `AGENTS.md` e `scripts/quality_gate.py`.

## ADR-004 — Setores DESC e ADESÃO: origem, transporte e movimentação de estoque

**Data:** 2026-10-29. **Status:** regra de negócio aceita; execução automática em homologação, não liberada.

- Setor e transporte são determinados pela **origem autenticada (grupo/bucket/técnico)**, não apenas pelo nome da O.S. ou código de baixa. `NTL-DMV` é Adesão; `NTL-DMV_ADM` e `PWM-DMV_ADM` são DESC.
- DESC: **DataSnap**, sem miscelâneas; equipamento entra/sai uma só vez em **uma O.S. por código**, ainda que existam múltiplas O.S. Não executar múltiplas O.S. com duplicação de seriais. `ENTREGA STREAMING` 409 no bucket ADM permanece DESC.
- ADESÃO: **API oficial Imperium**, com itens reais do TOA, miscelâneas quando existirem, estoque do técnico e complemento pelo **retorno confirmado** quando houver falta. Sem origem/quantidade/código comprovados, bloquear; não criar movimentação fictícia.
- Exceções explícitas ADESÃO: `INST GPON - INST CABO` e O.S. de `ASSINATURA` recebem **somente o código de baixa**, sem equipamentos/miscelâneas. Aplicar apenas ao IdOS exato.
- HTTP 200 da API oficial pode significar apenas **entrada na fila**; callback e estado no Imperium são prova da baixa. Data de agendamento deve conferir com a importação TOA e códigos de material devem conferir com estoque do técnico. Nunca repetir solicitação incerta sem conciliação.
- Executor geral que varria O.S. sem origem de grupo permanece **desativado**. Aprovar execução por fluxo somente depois de testes reais, isolamento de setor e garantia de idempotência.

**Evidências e pendências:** `docs/agent/memory/ADESAO_IMPERIUM_EVIDENCIAS_20261029.md`, issues [#25](https://github.com/clarotechnet/dominium/issues/25) e [#28](https://github.com/clarotechnet/dominium/issues/28). Os ZIPs originais de WhatsApp e seus anexos são privados e não fazem parte do repositório.
