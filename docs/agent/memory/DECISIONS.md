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
