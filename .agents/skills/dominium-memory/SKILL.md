---
name: dominium-memory
description: Recuperar e atualizar a memória técnica portátil do DOMINIUM, localizar sistemas, consultar decisões, continuar trabalho de agentes anteriores e registrar alterações/testes sem revarrer todo o repositório.
---

# DOMINIUM — memória e handoff

Use esta skill quando:
- Começar um novo chat/agente/conta para desenvolver o DOMINIUM.
- O usuário pedir continuação, diagnóstico, alterações ou localização de módulos.
- Terminar uma entrega, publicar um commit ou declarar testes/deploy concluídos.

1. Leia `AGENTS.md` e `docs/agent/memory/CURRENT_STATE.md`.
2. Rode `python scripts/agent_memory.py brief`, depois
   `python scripts/agent_memory.py search "assunto"`.
3. Use `python scripts/query_agent_context.py "endpoint/símbolo"` para código.
4. Trabalhe apenas no código necessário e execute testes reais.
5. Atualize `CURRENT_STATE.md` se o estado do projeto mudou.
6. Para decisão permanente, atualize `DECISIONS.md` com motivação.
7. Registre motivo, arquivos, verificações e pendências via comando `record`.
8. Confirme `scripts/quality_gate.py` e o Git antes de afirmar publicação.
9. Não inclua credenciais, tokens, pessoas ou dados sensíveis na memória.

Se o agente não tiver acesso ao repositório, não presuma acesso mágico:
solicite acesso ou clone autenticado; jamais invente o estado do sistema.
