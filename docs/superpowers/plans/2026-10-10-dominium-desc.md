# Dominium e DESCONEXÃO Implementation Plan

> Execução nativa nesta sessão; preservar o checkout principal. Revisão independente ao final.

**Goal:** Aplicar o visual de referência ao Dominium e integrar a revisão DESC com mensagens, fotos e Atlas.
**Architecture:** Preservar os controles existentes; adicionar tema global e módulo DESC separado. Proxy autenticado no backend operacional até o serviço existente do Bot; credenciais nunca chegam ao navegador.
**Tech Stack:** HTML/CSS/JavaScript, Python HTTP server, Node Bot, Hostinger/Supabase Auth existentes.
**Spec:** docs/superpowers/specs/2026-10-10-dominium-desc-design.md

## Restrições e revisão
- Preservar regras 430/409/400, isolamento por OS, estado real de execução, modo silencioso e bloqueio de histórico.
- Conferir: acesso sem sessão; viewer acessando fotos; atravessamento de caminho; ator forjado; backend offline; navegação durante OCR; formulário com conteúdo HTML malicioso.

## Tarefas
- [ ] Testar e implementar desc_review_proxy.py: forward(method,path,body,actor) devolve status, MIME e bytes; permite state/photo/report e refresh/decision/technician/manual; remove CSRF privado e força aprovador da sessão.
- [ ] Integrar proxy em app.py após os gates existentes, restringindo leitura operacional e preservando auditoria.
- [ ] Adicionar workspace e módulo disconnection a static/index.html e static/app.js; desenvolver static/disconnection.js com filtros e evidências reais, sem dados fictícios no produto.
- [ ] Aplicar static/workspace.css a todas as telas; adicionar fundo technet-concrete.png; conferir desktop, celular, login, tabelas e redução de movimento.
- [ ] Conectar o leitor Atlas existente à captura DESC sem alterar o grupo de consulta para executar baixas. Verificar os bloqueios do executor antes de integrar produção.
- [ ] Testar regressões, regenerar mapa, executar quality_gate.py, criar release e revisar diff; instalar somente mudanças verificadas e validar no domínio.
